import numpy as np
import csv
from obspy import UTCDateTime


def apply_preprocessing(stream, params):
    "Detrend and/or filter the waveform"
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
            st.filter("bandpass", freqmin=low, freqmax=high)
        elif "LowPass" in f_type:
            st.filter("lowpass", freq=high)
        elif "HighPass" in f_type:
            st.filter("highpass", freq=low)
    except Exception as e:
        print(f"Error while filtering: {e}")
    return st


def get_spectrum(trace):
    "Get spectra from traces"
    data = trace.data - np.mean(trace.data)
    if len(data) == 0:
        return np.array([]), np.array([])
    n = len(data)
    freq = np.fft.rfftfreq(n, d=trace.stats.delta)
    spec = np.abs(np.fft.rfft(data))
    if freq[0] == 0:
        freq = freq[1:]
        spec = spec[1:]
    return freq, spec


def extract_existing_picks(stream):
    """
    Cerca negli header SAC se ci sono pick esistenti (a, t0, t1...)
    e li restituisce nel formato della lista 'picks' dell'app.
    """
    found_picks = []
    seen_identifiers = (
        set()
    )  # Per evitare duplicati se lo stesso pick è su più componenti

    for tr in stream:
        if not hasattr(tr.stats, "sac"):
            continue

        sac = tr.stats.sac
        # Mappa i marker SAC standard
        # 'a' è solitamente P, 't0' è solitamente S. Altri sono t1-t9
        markers = [
            ("a", "ka"),
            ("t0", "kt0"),
            ("t1", "kt1"),
            ("t2", "kt2"),
            ("t3", "kt3"),
        ]

        for time_key, name_key in markers:
            if time_key in sac:
                rel_time = sac[time_key]
                abs_t = tr.stats.starttime + rel_time

                # Determina il nome della fase
                phase_name = sac.get(name_key, time_key.upper()).strip()
                if not phase_name:
                    phase_name = time_key.upper()

                # Identificatore unico per evitare di aggiungere 3 volte lo stesso pick (Z,N,E)
                # se hanno lo stesso tempo esatto
                pick_id = (tr.stats.station, phase_name, str(abs_t))

                if pick_id not in seen_identifiers:
                    found_picks.append(
                        {
                            "sta": tr.stats.station,
                            "cha_source": tr.stats.channel,
                            "phase": phase_name,
                            "abs_t": str(abs_t),
                        }
                    )
                    seen_identifiers.add(pick_id)
    return found_picks


def export_to_csv(picks, filename):
    "Export picking in .csv file"
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Station", "Channel", "Phase", "UTC_Time"])
        for p in picks:
            writer.writerow([p["sta"], p["cha_source"], p["phase"], p["abs_t"]])


def save_picks_to_sac(stream, picks):
    for pk in picks:
        target_traces = stream.select(station=pk["sta"])
        i = 0
        for tr in target_traces:
            if not hasattr(tr.stats, "sac"):
                tr.stats.sac = {}
            pick_time = UTCDateTime(pk["abs_t"])
            rel_time = pick_time - tr.stats.starttime

            p_name = pk["phase"].upper()
            if p_name == "P":
                tr.stats.sac["a"] = rel_time
                tr.stats.sac["ka"] = "P"
            elif p_name == "S":
                tr.stats.sac["t0"] = rel_time
                tr.stats.sac["kt0"] = "S"
            else:
                i += 1
                tr.stats.sac[f"t{i}"] = rel_time
                tr.stats.sac[f"kt{i}"] = p_name

            if "filename" in tr.stats and tr.stats.filename:
                tr.write(tr.stats.filename, format="SAC")
