import csv
import json
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from obspy import Catalog, UTCDateTime, read_events
from obspy.core.event import Event, Pick, WaveformStreamID
from obspy.geodetics import locations2degrees
from obspy.taup import TauPyModel
from PyQt6.QtCore import QStandardPaths

APP_CONFIG_FOLDER = "PyPicker"

def get_config_dir():
    "Return default configuration directory for PyPicker."
    base = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.GenericConfigLocation
    )

    if not base:
        raise RuntimeError(
            "Impossible to define the configuration directory."
        )

    return Path(base) / APP_CONFIG_FOLDER

def get_config_path():
    """Return the path to the editable config.json file."""
    return get_config_dir() / "config.json"

def read_config(path):
    """Read a JSON file and verify that it contains an object."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            config = json.load(handle)
    except (OSError, ValueError) as exc:
        raise RuntimeError(
            f"Impossible to read the configuration:\n{path}\n\n{exc}"
        ) from exc

    if not isinstance(config, dict):
        raise RuntimeError(  # noqa: TRY004
            f"The configuration must contain a JSON object:\n{path}"
        )

    return config

def merge_config(defaults, overrides):
    "Merge user configs to the defaults"
    result = deepcopy(defaults)

    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_config(result[key], value)
        else:
            result[key] = deepcopy(value)

    return result

def load_config(filename="config.json"):
    """
    Load configuration from a JSON file.
    Returns a default dictionary if the file is missing or corrupted.
    """

    default_path = Path(__file__).resolve().parent / "config.json"
    defaults = read_config(default_path)
    user_path = get_config_path()

    try:
        user_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with user_path.open("x", encoding="utf-8") as handle:
                json.dump(
                    defaults,
                    handle,
                    indent=4,
                    ensure_ascii=False,
                )
                handle.write("\n")
        except FileExistsError:
            pass
    except OSError as exc:
        raise RuntimeError(
            "Impossible to create the user configuration:\n"
            f"{user_path}\n\n{exc}"
        ) from exc

    user_config = read_config(user_path)
    return merge_config(defaults, user_config)

def apply_preprocessing(stream, params):
    """
    Apply detrending, demeaning, and filtering to the ObsPy stream.
    """
    st = stream.copy()
    dm, dt, norm, f = 0, 0, 0, 0

    if params.get("demean"):
        st.detrend("demean")
        dm = 1
    if params.get("detrend"):
        st.detrend("linear")
        dt = 1
    if params.get("normalize"):
        if dm != 1:
            st.detrend("demean")
        if dt != 1:
            st.detrend("linear")
        st = normalize_traces(st)
        norm = 1

    f_type = params.get("filter_type")
    low = params.get("low_f", 1.0)
    high = params.get("high_f", 20.0)

    if f_type == "None" or not f_type:
        if dm == 1 or dt == 1 or norm == 1:
            st.taper(max_percentage=0.05, type="cosine")
        return st

    try:
        if "BandPass" in f_type and low < high:
            st.filter("bandpass", freqmin=low, freqmax=high, zerophase=True)
            f = 1
        elif "LowPass" in f_type:
            st.filter("lowpass", freq=high, zerophase=True)
            f = 1
        elif "HighPass" in f_type:
            st.filter("highpass", freq=low, zerophase=True)
            f = 1
    except Exception as e:  # noqa: BLE001
        print(f"Error while filtering: {e}")

    if dm == 1 or dt == 1 or norm == 1 or f == 1:
        st.taper(max_percentage=0.05, type="cosine")
    return st

def get_spectrum(trace):
    """
    Calculate the frequency spectrum of a single trace using RFFT.
    """
    data = trace.data - np.mean(trace.data)
    if len(data) == 0:
        return np.array([]), np.array([])

    n = len(data)
    freq = np.fft.rfftfreq(n, d=trace.stats.delta)
    spec = np.abs(np.fft.rfft(data))

    # Remove DC component
    if freq[0] == 0:
        freq = freq[1:]
        spec = spec[1:]

    return freq, spec

def extract_existing_picks(stream):
    """
    Extract picking information from SAC headers.
    Looks for markers: a (P), t0 (S), and t1-t3.
    """
    found_picks = []
    seen_identifiers = set()

    for tr in stream:
        if not hasattr(tr.stats, "sac"):
            continue

        sac = tr.stats.sac
        # Map: (SAC time key, SAC label key, SAC error key)
        markers = [
            ("a", "ka", "f"),
            ("t0", "kt0", "resp0"),   # era "std0"
            ("t1", "kt1", "resp1"),   # era "std1"
            ("t2", "kt2", "resp2"),   # era "std2"
            ("t3", "kt3", "resp3"),   # era "std3"

        ]

        for time_key, name_key, err_key in markers:
            if time_key in sac:
                rel_time = sac[time_key]
                abs_t = tr.stats.starttime + rel_time

                phase_name = sac.get(name_key, time_key.upper()).strip()
                if not phase_name:
                    phase_name = time_key.upper()

                # Handle uncertainty; SAC uses -12345.0 as null
                uncertainty = sac.get(err_key, 0.0)
                if uncertainty == -12345.0:
                    uncertainty = 0.0

                pick_id = (tr.stats.station, phase_name, str(abs_t))

                if pick_id not in seen_identifiers:
                    found_picks.append(
                        {
                            "sta": tr.stats.station,
                            "cha_source": tr.stats.channel,
                            "phase": phase_name,
                            "abs_t": str(abs_t),
                            "uncertainty": uncertainty,
                        }
                    )
                    seen_identifiers.add(pick_id)
    return found_picks

def extract_picks_from_csv(filename):
    """
    Extract the pick list from a CSV file.
    """
    picks = []
    with open(filename, "r") as f:
        reader = csv.reader(f, delimiter=";")
        next(reader, None)  # skip header
        for row in reader:
            if len(row) >= 4:
                pk = {
                    "sta": row[0],
                    "cha_source": row[1],
                    "phase": row[2],
                    "abs_t": row[3],
                    "uncertainty": float(row[4]) if len(row) > 4 else 0.0,
                    "polarity": row[5] if len(row) > 5 else "Unknown",
                    "onset": row[6] if len(row) > 6 else "Unknown",
                }
                picks.append(pk)
    return picks

def extract_picks_from_seisgram_pick(filename):
    """
    Extract the pick list from a .pick file created by Seisgram2k.
    """
    _ONSET_MAP = {"i": "impulsive", "e": "emergent"}
    _POLARITY_MAP = {"c": "positive", "u": "positive", "+": "positive",
        "d": "negative", "-": "negative",}
    picks = []
    with open(filename, "r") as f:
        for line in f:
            row = line.split()
            if len(row) < 9:
                continue
            t0 = datetime.strptime(row[6] + row[7], "%Y%m%d%H%M")
            abs_t = t0 + timedelta(seconds=float(row[8]))
            pk = {
                "sta": row[0],
                "cha_source": row[2],
                "phase": row[4],
                "abs_t": abs_t.isoformat(timespec="milliseconds"),
                "uncertainty": float(row[10]) if len(row) > 10 else 0.0,
                "polarity": _POLARITY_MAP.get(row[5].lower(), "Unknown"),
                "onset": _ONSET_MAP.get(row[3].lower(), "Unknown"),
            }
            picks.append(pk)
    return picks

def extract_picks_from_quakeml(filename):
    """
    Extract picks from a QuakeML file.
    """
    cat = read_events(filename)
    picks = []
    for event in cat:
        for pick in event.picks:
            pk = {
                "sta": pick.waveform_id.station_code if pick.waveform_id else "",
                "cha_source": pick.waveform_id.channel_code if pick.waveform_id else "",
                "phase": pick.phase_hint if pick.phase_hint else "",
                "abs_t": str(pick.time),
                "uncertainty": pick.time_errors.uncertainty if pick.time_errors and pick.time_errors.uncertainty else 0.0,
                "polarity": pick.polarity.capitalize() if pick.polarity else "Unknown",
                "onset": pick.onset.capitalize() if pick.onset else "Unknown"
            }
            picks.append(pk)
    return picks

def export_to_csv(picks, filename):
    """
    Export the pick list to a CSV file.
    """
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Station", "Channel", "Phase", "UTC_Time", "Uncertainty_sec", "Polarity", "Onset"])
        for p in picks:
            writer.writerow(
                [
                    p["sta"],
                    p["cha_source"],
                    p["phase"],
                    p["abs_t"],
                    p.get("uncertainty", 0.0),
                    p.get("polarity", "Unknown"),
                    p.get("onset", "Unknown"),
                ]
            )

def save_picks_to_sac(stream, picks):
    """
    Write picks back into the SAC headers of the loaded stream and save files.
    Clears old picks first so that deleted picks are actually removed from the files.
    """
    for tr in stream:
        if not hasattr(tr.stats, "sac"):
            continue
        sac = tr.stats.sac
        for key in ["a", "f"]:    # Pulisci i marker della fase P
            if key in sac:
                sac[key] = -12345.0
        if "ka" in sac:
            sac["ka"] = "-12345"
        for i in range(10):    # Pulisci i marker delle fasi S e altre (t0 - t9)
            t_key = f"t{i}"
            err_key = f"resp{i}"
            name_key = f"kt{i}"
            
            if t_key in sac: 
                sac[t_key] = -12345.0
            if err_key in sac: 
                sac[err_key] = -12345.0
            if name_key in sac: 
                sac[name_key] = "-12345"
    for pk in picks:
        target_traces = stream.select(station=pk["sta"])
        unc = float(pk.get("uncertainty", 0.0))
        i = 0
        for tr in target_traces:
            if not hasattr(tr.stats, "sac"):
                tr.stats.sac = {}
            pick_time = UTCDateTime(pk["abs_t"])
            rel_time = pick_time - tr.stats.starttime
            p_name = pk["phase"].upper()
            # Mapping logic
            if p_name == "P":
                tr.stats.sac["a"] = rel_time
                tr.stats.sac["ka"] = "P"
                tr.stats.sac["f"] = unc
            elif p_name == "S":
                tr.stats.sac["t0"] = rel_time
                tr.stats.sac["kt0"] = "S"
                tr.stats.sac["resp0"] = unc
            else:
                i += 1
                if i <= 9:
                    tr.stats.sac[f"t{i}"] = rel_time
                    tr.stats.sac[f"kt{i}"] = p_name
                    tr.stats.sac[f"resp{i}"] = unc
    for tr in stream:
        if "filename" in tr.stats and tr.stats.filename:
            try:
                tr.write(tr.stats.filename, format="SAC")
            except Exception as e:  # noqa: BLE001
                print(f"Error saving SAC file for {tr.id}: {e}")

def export_to_quakeml(picks, filename):
    """
    Export the pick list to a QuakeML file.
    """
    cat = Catalog()
    event = Event()
    for pk in picks:
        pick = Pick()
        pick.time = UTCDateTime(pk["abs_t"])
        pick.waveform_id = WaveformStreamID(station_code=pk["sta"], channel_code=pk["cha_source"])
        pick.phase_hint = pk["phase"]
        
        if pk.get("uncertainty", 0.0) > 0:
            pick.time_errors = {"uncertainty": pk["uncertainty"]}
        
        if "polarity" in pk and pk["polarity"] != "Unknown":
            pick.polarity = pk["polarity"].lower()
        if "onset" in pk and pk["onset"] != "Unknown":
            pick.onset = pk["onset"].lower()
            
        event.picks.append(pick)
    
    cat.append(event)
    cat.write(filename, format="QUAKEML")

def get_epicentral_distance(tr):
    """Calculate epicentral distance in degrees from SAC headers if available."""
    if not hasattr(tr.stats, "sac"):
        return None
    sac = tr.stats.sac
    if "evla" in sac and "evlo" in sac and "stla" in sac and "stlo" in sac:  # noqa: SIM102
        if sac["evla"] != -12345.0 and sac["evlo"] != -12345.0 and sac["stla"] != -12345.0 and sac["stlo"] != -12345.0:
            return locations2degrees(sac["evla"], sac["evlo"], sac["stla"], sac["stlo"])
    return None

def reorder_stream_by_distance(stream):
    """Reorder stream by epicentral distance."""
    sta_dist = {}
    for tr in stream:
        sta = tr.stats.station
        if sta not in sta_dist:
            dist = get_epicentral_distance(tr)
            sta_dist[sta] = dist if dist is not None else float('inf')
            
    sorted_stas = sorted(sta_dist.keys(), key=lambda x: sta_dist[x])
    
    new_st = stream.__class__()
    for sta in sorted_stas:
        new_st += stream.select(station=sta)
    return new_st

def reorder_stream_by_arrival(stream, picks):
    """Reorder stream by earliest pick arrival time."""
    sta_time = {}
    for pk in picks:
        sta = pk["sta"]
        t = UTCDateTime(pk["abs_t"])
        if sta not in sta_time or t < sta_time[sta]:
            sta_time[sta] = t
            
    all_stas = list({tr.stats.station for tr in stream})
    for sta in all_stas:
        if sta not in sta_time:
            sta_time[sta] = UTCDateTime(2100, 1, 1)
            
    sorted_stas = sorted(all_stas, key=lambda x: sta_time[x])
    
    new_st = stream.__class__()
    for sta in sorted_stas:
        new_st += stream.select(station=sta)
    return new_st

def reorder_stream_by_name(stream):
    """Reorder stream by station name."""
    sta_names = []
    for tr in stream:
        sta = tr.stats.station
        if sta not in sta_names:
            sta_names.append(sta)
            
    sta_names.sort()
    
    new_st = stream.__class__()
    for sta in sta_names:
        new_st += stream.select(station=sta)
    return new_st

def remove_pick_from_sac(stream, station, channel, phase_name):
    "Remove a specific pick from SAC headers of matching traces by setting them to -12345.0"
    target_traces = stream.select(station=station, channel=channel)
    if not target_traces:
        target_traces = stream.select(station=station)

    p_name = phase_name.upper()
    for tr in target_traces:
        if not hasattr(tr.stats, "sac"):
            continue
        sac = tr.stats.sac
        if p_name == "P":
            if sac.get("ka", "").strip().upper() == "P" or "a" in sac:
                sac["a"] = -12345.0
                sac["ka"] = "-12345"
                sac["f"] = -12345.0
        elif p_name == "S":  # noqa: SIM102
            if sac.get("kt0", "").strip().upper() == "S" or "t0" in sac:
                sac["t0"] = -12345.0
                sac["kt0"] = "-12345"
                sac["resp0"] = -12345.0

        for i in range(10):
            name_key = f"kt{i}"
            t_key = f"t{i}"
            err_key = f"resp{i}"
            if sac.get(name_key, "").strip().upper() == p_name:
                sac[t_key] = -12345.0
                sac[name_key] = "-12345"
                sac[err_key] = -12345.0

        if "filename" in tr.stats and tr.stats.filename:
            try:
                tr.write(tr.stats.filename, format="SAC")
            except Exception as e:  # noqa: BLE001
                print(f"Error updating SAC file after pick deletion: {e}")

def calculate_theoretical_arrivals(stream, model_name="iasp91"):
    """Calculate theoretical P and S arrivals for each station."""
    try:
        model = TauPyModel(model=model_name)
    except Exception as e:  # noqa: BLE001
        print(f"Error loading velocity model {model_name}: {e}")
        return {}
        
    arrivals = {}
    for tr in stream:
        sta = tr.stats.station
        if sta in arrivals:
            continue

        if not hasattr(tr.stats, "sac"):
            continue

        sac = tr.stats.sac
        if all(k in sac and sac[k] != -12345.0 for k in ["evla", "evlo", "stla", "stlo", "evdp"]):
            dist_deg = locations2degrees(sac["evla"], sac["evlo"], sac["stla"], sac["stlo"])
            depth_km = sac["evdp"]
            
            try:
                arrs = model.get_travel_times(source_depth_in_km=depth_km, distance_in_degree=dist_deg, phase_list=["P", "S", "p", "s"])
                
                if "o" in sac and sac["o"] != -12345.0:
                    b = sac.get("b", 0.0)
                    if b == -12345.0: b = 0.0
                    origin_time = tr.stats.starttime - b + sac["o"]
                    
                    sta_arrs = {}
                    for a in arrs:
                        ph = a.name
                        if ph.upper() in ["P", "S"] and ph.upper() not in sta_arrs:
                            sta_arrs[ph.upper()] = origin_time + a.time
                    
                    arrivals[sta] = sta_arrs
            except Exception as e:  # noqa: BLE001
                print(f"Error calculating travel times for {sta}: {e}")
                
    return arrivals

def normalize_traces(stream):
    "Normalize stream traces."

    from collections import defaultdict
    
    new_stream = stream.copy()
    station_max = defaultdict(float)

    for tr in new_stream:
        station = tr.stats.station
        d = tr.data[np.isfinite(tr.data)]
        if d.size > 0:
            trace_max = np.max(np.abs(d))
            station_max[station] = max(station_max[station], trace_max)
    
    for tr in new_stream:
        station = tr.stats.station
        data_max = station_max.get(station, 1.0)
        if data_max == 0:
            data_max = 1.0
        if len(tr.data) > 0:
            tr.data = tr.data.astype(np.float64) / data_max
    
    return new_stream

def jet_colormap(n=256):
    "Matplotlib 'jet' colormap as an (n, 3) uint8 lookup table for pyqtgraph."

    x = np.linspace(0, 1, n)
    red = np.interp(x, [0, 0.35, 0.66, 0.89, 1], [0, 0, 1, 1, 0.5])
    green = np.interp(x, [0, 0.125, 0.375, 0.64, 0.91, 1], [0, 0, 1, 1, 0, 0])
    blue = np.interp(x, [0, 0.11, 0.34, 0.65, 1], [0.5, 1, 1, 0, 0])
    return np.round(np.column_stack([red, green, blue]) * 255).astype(np.uint8)

def Morlet_scalogram(data, dt, duration, f_range=(1.0, 30.0), n_freqs=100,
                        max_cols=4000, db_range=100.0, percentiles=(1, 99)):
    """
    Compute the Morlet scalogram of the given data.
    
    Parameters:
    - data: 1D array of the signal (not modified)
    - dt: Sampling interval (time step), in seconds
    - duration: Duration factor for the Morlet wavelet
    - f_range: (f_min, f_max) in Hz, sampled log-spaced
    - n_freqs: Number of frequencies
    - max_cols: Maximum number of time columns of the output
    - db_range: Dynamic range in dB below the maximum power (floor of the dB image)
    - percentiles: Percentiles of the dB image used as colour limits
    
    Returns:
    - (db, freqs, width, levels), or None if the trace is flat or not finite, where
        db is the (n_freq, n_time) power in dB, freqs the frequencies in Hz (evenly spaced
        in log10), width the time covered by the columns of db in seconds and levels the
        (low, high) dB colour limits
    """
    if duration <= 0:
        raise ValueError("Duration must be greater than zero.")
    
    data = np.asarray(data, dtype=np.float64)
    freqs = np.geomspace(f_range[0], f_range[1], n_freqs)
    t_wavelet = np.arange(-2, 2, dt)
    power = np.empty((n_freqs, len(data)))
    for i, f in enumerate(freqs):
        wavelet = np.exp(1j * 2 * np.pi * f * t_wavelet) * np.exp(-(t_wavelet * f / duration) ** 2)
        power[i] = np.array(np.abs(np.convolve(data, wavelet, mode='same'))) ** 2
    _, n = power.shape
    pmax = power.max()
    if not np.isfinite(pmax) or pmax <= 0:
        return None

    db = 10 * np.log10(np.maximum(power, pmax * 10 ** (-db_range / 10)))
    levels = tuple(np.percentile(db, percentiles))
    return db, freqs, n * dt, levels