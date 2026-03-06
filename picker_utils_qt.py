import os
import json
import csv
import numpy as np
from obspy import UTCDateTime


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
        writer.writerow(["Station", "Channel", "Phase", "UTC_Time", "Uncertainty_sec"])
        for p in picks:
            writer.writerow(
                [
                    p["sta"],
                    p["cha_source"],
                    p["phase"],
                    p["abs_t"],
                    p.get("uncertainty", 0.0),
                ]
            )


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
