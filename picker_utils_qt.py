import numpy as np
import csv
from obspy import UTCDateTime


def apply_preprocessing(stream, params):
    """Applica filtri e correzioni a una copia dello stream"""
    st = stream.copy()
    if params.get("demean"):
        st.detrend("demean")
    if params.get("detrend"):
        st.detrend("linear")

    f_type = params.get("filter_type")
    low = params.get("low_f", 1.0)
    high = params.get("high_f", 20.0)

    try:
        if f_type == "bandpass" and low < high:
            st.filter("bandpass", freqmin=low, freqmax=high)
    except Exception as e:
        print(f"Errore filtro: {e}")
    return st


def get_spectrum(trace):
    """Calcola lo spettro di frequenza di una traccia"""
    data = trace.data - np.mean(trace.data)
    n = len(data)
    freq = np.fft.rfftfreq(n, d=trace.stats.delta)
    spec = np.abs(np.fft.rfft(data))
    return freq, spec


def export_to_csv(picks, filename):
    """Esporta i picking in formato CSV tabellare"""
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["STAZIONE", "CANALE_REF", "FASE", "TEMPO_UTC"])
        for p in picks:
            writer.writerow([p["sta"], p["cha_source"], p["phase"], p["abs_t"]])


def save_picks_to_sac(stream, picks):
    """
    Salva i picking direttamente negli header dei file SAC originali.
    P -> header T0, S -> header T1
    """
    for pk in picks:
        # Cerchiamo la traccia corrispondente nello stream
        # (Idealmente salviamo su tutti i canali della stazione)
        target_traces = stream.select(station=pk["sta"])

        for tr in target_traces:
            if not hasattr(tr.stats, "sac"):
                tr.stats.sac = {}

            # Calcoliamo il tempo relativo dall'inizio del file
            pick_time = UTCDateTime(pk["abs_t"])
            rel_time = pick_time - tr.stats.starttime

            if pk["phase"].upper() == "P":
                tr.stats.sac["t0"] = rel_time
                tr.stats.sac["kt0"] = "P"
            elif pk["phase"].upper() == "S":
                tr.stats.sac["t1"] = rel_time
                tr.stats.sac["kt1"] = "S"

            # Sovrascrive il file originale se esiste il path
            if "filename" in tr.stats and tr.stats.filename:
                tr.write(tr.stats.filename, format="SAC")
