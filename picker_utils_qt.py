import os
import json
import csv
import numpy as np
from obspy import UTCDateTime, Catalog, read_events
from obspy.core.event import Event, Pick, WaveformStreamID
from obspy.geodetics import locations2degrees
from obspy.taup import TauPyModel

def load_config(filename="config.json"):
    """
    Load configuration from a JSON file.
    Returns a default dictionary if the file is missing or corrupted.
    """
    default_config = {
        "shortcuts": {
            "next_station": "D",
            "prev_station": "A",
            "phase_p": "P",
            "phase_s": "S",
            "reset_view": "R",
        },
        "colors": {
            "Z": "#e74c3c",
            "N": "#f1c40f",
            "E": "#3498db",
            "other": "gray",
            "pick_line": "#8e44ad",
            "pick_area_alpha": 50,
        },
        "defaults": {"low_f": 1.0, "high_f": 20.0},
    }

    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
    return default_config

def apply_preprocessing(stream, params):
    """
    Apply detrending, demeaning, and filtering to the ObsPy stream.
    """
    st = stream.copy()

    if params.get("demean"):
        st.detrend("demean")
    if params.get("detrend"):
        st.detrend("linear")

    f_type = params.get("filter_type")
    low = params.get("low_f", 1.0)
    high = params.get("high_f", 20.0)

    if f_type == "None" or not f_type:
        return st

    try:
        if "BandPass" in f_type and low < high:
            st.taper(max_percentage=0.05, type="cosine")
            st.filter("bandpass", freqmin=low, freqmax=high, zerophase=True)
        elif "LowPass" in f_type:
            st.taper(max_percentage=0.05, type="cosine")
            st.filter("lowpass", freq=high, zerophase=True)
        elif "HighPass" in f_type:
            st.taper(max_percentage=0.05, type="cosine")
            st.filter("highpass", freq=low, zerophase=True)
    except Exception as e:
        print(f"Error while filtering: {e}")

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
            ("t0", "kt0", "std0"),
            ("t1", "kt1", "std1"),
            ("t2", "kt2", "std2"),
            ("t3", "kt3", "std3"),
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

def save_picks_to_sac(stream, picks):
    """
    Write picks back into the SAC headers of the loaded stream and save files.
    """
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
                tr.stats.sac["std0"] = unc
            else:
                i += 1
                if i <= 9:
                    tr.stats.sac[f"t{i}"] = rel_time
                    tr.stats.sac[f"kt{i}"] = p_name
                    tr.stats.sac[f"std{i}"] = unc

            # Save to disk
            if "filename" in tr.stats and tr.stats.filename:
                try:
                    tr.write(tr.stats.filename, format="SAC")
                except Exception as e:
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

def get_epicentral_distance(tr):
    """Calculate epicentral distance in degrees from SAC headers if available."""
    if not hasattr(tr.stats, "sac"):
        return None
    sac = tr.stats.sac
    if "evla" in sac and "evlo" in sac and "stla" in sac and "stlo" in sac:
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
            
    all_stas = list(set([tr.stats.station for tr in stream]))
    for sta in all_stas:
        if sta not in sta_time:
            sta_time[sta] = UTCDateTime(2100, 1, 1)
            
    sorted_stas = sorted(all_stas, key=lambda x: sta_time[x])
    
    new_st = stream.__class__()
    for sta in sorted_stas:
        new_st += stream.select(station=sta)
    return new_st

def calculate_theoretical_arrivals(stream, model_name="iasp91"):
    """Calculate theoretical P and S arrivals for each station."""
    try:
        model = TauPyModel(model=model_name)
    except Exception as e:
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
            except Exception as e:
                print(f"Error calculating travel times for {sta}: {e}")
                
    return arrivals