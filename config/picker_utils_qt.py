import csv
import json
import os
import shutil
import sys
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from obspy import Catalog, UTCDateTime, read_events
from obspy.core.event import Event, Pick, WaveformStreamID
from obspy.geodetics import gps2dist_azimuth, locations2degrees
from obspy.taup import TauPyModel
from PyQt6.QtCore import QStandardPaths
from PyQt6.QtGui import QIcon

__version__ = "2.0.0"

APP_CONFIG_FOLDER = "PyPicker"

DEFAULT_CONFIG = {
    "shortcuts": {
        "next_station": "D",
        "prev_station": "A",
        "phase_p": "P",
        "phase_s": "S",
        "phase_custom": "C",
        "phase_rotate": "Q",
        "reset_view": "R",
        "save_sac": "Ctrl+S",
        "export_csv": "Ctrl+E",
        "toggle_filter": "F",
        "pick_p": "1",
        "pick_s": "2",
        "localize": "L",
        "open_map": "M",
        "help_doc": "F1",
    },
    "colors": {
        "Z": "#e74c3c",
        "N": "#f1c40f",
        "E": "#3498db",
        "other": "#7f8c8d",
        "pick_line": "#8e44ad",
        "pick_area_alpha": 60,
    },
    "defaults": {
        "low_f": 1.0,
        "high_f": 20.0,
        "filter_type": "BandPass (f1 and f2)",
        "velocity_model": "velocity_model.json",
        "show_theoretical_arrivals": False,
        "picking_mode": "Popup",
        "station_client": "INGV",
        "map_dem_alpha": 0.4,
    },
}

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

def get_user_utils_path():
    """Return the path to picker_utils_qt.py in the user configuration directory."""
    return get_config_dir() / "picker_utils_qt.py"

def get_default_config_dir():
    """Locate the default config directory bundled with the application."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            p = Path(meipass) / "config"
            if p.exists():
                return p
    p = Path(__file__).resolve().parent / "config"
    if p.exists():
        return p
    return p

def get_default_config_path():
    """Locate the default config.json bundled with the application."""
    p = get_default_config_dir() / "config.json"
    if p.exists():
        return p
    app_p = Path(__file__).resolve().parent / "config.json"
    if app_p.exists():
        return app_p
    return p

def get_plugins_dir():
    """Return the user plugins directory (~/.config/PyPicker/plugins)."""
    return get_config_dir() / "plugins"

def get_default_plugins_dir():
    """Locate the default plugins directory bundled with the application."""
    p = get_default_config_dir() / "plugins"
    if p.exists():
        return p
    app_p = Path(__file__).resolve().parent / "plugins"
    if app_p.exists():
        return app_p
    return p

def get_velocity_model_path():
    """Return the user velocity_model.json path in the configuration directory."""
    return get_config_dir() / "velocity_model.json"

def get_default_velocity_model_path():
    """Locate the default velocity_model.json bundled with the application."""
    p = get_default_config_dir() / "velocity_model.json"
    if p.exists():
        return p
    app_p = Path(__file__).resolve().parent / "velocity_model.json"
    if app_p.exists():
        return app_p
    return p

def get_doc_dir():
    """Locate the doc/ directory containing documentation markdown files."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            cand = Path(meipass) / "doc"
            if cand.exists():
                return cand
    app_doc = Path(__file__).resolve().parent / "doc"
    if app_doc.exists():
        return app_doc
    root_doc = Path(__file__).resolve().parent.parent / "doc"
    if root_doc.exists():
        return root_doc
def get_icon_dir():
    """Locate the doc/icon/ directory containing application icons and logos."""
    doc_dir = get_doc_dir()
    icon_dir = doc_dir / "icon"
    if icon_dir.exists():
        return icon_dir
    app_icon = Path(__file__).resolve().parent / "doc" / "icon"
    if app_icon.exists():
        return app_icon
    return icon_dir

def get_app_icon(theme="dark"):
    """
    Return a QIcon for PyPicker.
    theme can be 'dark' or 'white'/'light'.
    Tries PNG, SVG, or ICO formats.
    """
    icon_dir = get_icon_dir()
    prefix = "PyPicker_icon_dark" if theme in ("dark", "System") else "PyPicker_icon_white"
    
    candidates = [
        icon_dir / f"{prefix}.png",
        icon_dir / f"{prefix}.svg",
        icon_dir / "PyPicker_icon_dark.png",
        icon_dir / "PyPicker.ico",
        icon_dir / "PyPicker.png",
    ]
    for p in candidates:
        if p.exists():
            return QIcon(str(p))
    return QIcon()

def get_app_logo_path(theme="dark"):
    """
    Return the Path to the PyPicker logo image (dark or white/light).
    """
    icon_dir = get_icon_dir()
    name = "PyPicker_logo_dark.png" if theme in ("dark", "System") else "PyPicker_logo_white.png"
    p = icon_dir / name
    if p.exists():
        return p
    svg_p = icon_dir / (name.replace(".png", ".svg"))
    if svg_p.exists():
        return svg_p
    return icon_dir / "PyPicker_logo_dark.png"

def sync_configuration(overwrite=False):
    """
    Synchronize the entire default config/ folder structure
    (config.json, velocity_model.json, plugins/, picker_utils_qt.py)
    into the user configuration directory (~/.config/PyPicker/).
    Existing user files are preserved unless overwrite is True.
    """
    user_config_dir = get_config_dir()
    src_config_dir = get_default_config_dir()

    try:
        user_config_dir.mkdir(parents=True, exist_ok=True)
        if src_config_dir.exists():
            for item in src_config_dir.rglob("*"):
                if item.name.startswith(".") or "__pycache__" in item.parts:
                    continue
                rel_path = item.relative_to(src_config_dir)
                target = user_config_dir / rel_path
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                elif item.is_file():  # noqa: SIM102
                    if not target.exists() or overwrite:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, target)

        user_utils = get_user_utils_path()
        if not user_utils.exists() or overwrite:
            src_utils = Path(__file__).resolve()
            if getattr(sys, "frozen", False):
                meipass = getattr(sys, "_MEIPASS", None)
                if meipass:
                    cand = Path(meipass) / "picker_utils_qt.py"
                    if cand.exists():
                        src_utils = cand
            if src_utils.exists() and src_utils.is_file():
                shutil.copy2(src_utils, user_utils)

    except OSError as exc:
        print(f"Warning: Could not sync configuration directory: {exc}")

    # Ensure plugin directories are in sys.path
    for p in (get_plugins_dir(), get_default_plugins_dir()):
        if p.exists() and str(p) not in sys.path:
            sys.path.insert(0, str(p))

def sync_user_utilities(overwrite=False):
    sync_configuration(overwrite=overwrite)

def sync_plugins(overwrite=False):
    sync_configuration(overwrite=overwrite)

def sync_velocity_model(overwrite=False):
    sync_configuration(overwrite=overwrite)

def load_velocity_model(model_path=None):
    """Load 1D velocity model from JSON file."""
    if model_path:
        p = Path(model_path)
        if p.exists():
            return read_config(p)
    user_path = get_velocity_model_path()
    if user_path.exists():
        return read_config(user_path)
    default_path = get_default_velocity_model_path()
    if default_path and default_path.exists():
        return read_config(default_path)
    return {
        "name": "Default 1D Crustal Model",
        "layers": [
            {"depth_km": 0.0, "vp": 4.5, "vs": 2.60},
            {"depth_km": 2.5, "vp": 5.0, "vs": 2.89},
            {"depth_km": 5.0, "vp": 6.2, "vs": 3.58},
            {"depth_km": 15.0, "vp": 8.0, "vs": 4.62}
        ],
        "vp_vs_ratio": 1.73
    }

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
    default_path = get_default_config_path()
    if default_path.exists():
        defaults = read_config(default_path)
    else:
        defaults = deepcopy(DEFAULT_CONFIG)

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

    # Sync default configuration directory to user configuration folder
    sync_configuration()

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
        st = normalize_traces(st, inplace=True)
        norm = 1

    f_type = params.get("filter_type")
    low = params.get("low_f", 1.0)
    high = params.get("high_f", 20.0)

    if f_type == "None" or not f_type:
        if norm == 1:
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

_TAUP_MODEL_CACHE = {}

def get_or_create_taup_model(model_name="velocity_model.json"):
    """
    Get or compile a TauPyModel instance.
    Supports standard ObsPy models (iasp91, ak135, etc.) or a custom 1D velocity
    model defined in a JSON file (e.g. velocity_model.json).
    """
    global _TAUP_MODEL_CACHE  # noqa: PLW0602
    if model_name in _TAUP_MODEL_CACHE:
        return _TAUP_MODEL_CACHE[model_name]

    model_str = str(model_name)
    if model_str.endswith(".json") or model_str == "velocity_model.json":
        json_path = Path(model_str)
        if not json_path.is_file():
            user_cand = get_velocity_model_path()
            if user_cand.is_file():
                json_path = user_cand
            else:
                default_cand = get_default_velocity_model_path()
                if default_cand and default_cand.is_file():
                    json_path = default_cand

        if json_path.is_file():
            try:
                from obspy.taup.taup_create import build_taup_model
                model_data = read_config(json_path)
                layers = model_data.get("layers", [])
                if not layers:
                    raise ValueError("No layers defined in velocity model JSON.")

                cache_dir = get_config_dir() / "cache"
                cache_dir.mkdir(parents=True, exist_ok=True)
                npz_path = cache_dir / f"{json_path.stem}.npz"
                tvel_path = cache_dir / f"{json_path.stem}.tvel"

                rebuild = True
                if npz_path.exists():  # noqa: SIM102
                    if npz_path.stat().st_mtime >= json_path.stat().st_mtime:
                        rebuild = False

                if rebuild:
                    vp_vs = float(model_data.get("vp_vs_ratio", 1.73))
                    lines = [model_data.get("name", "1D Model"), "PyPicker generated model"]
                    for i, l in enumerate(layers):
                        top_z = float(l["depth_km"])
                        bot_z = float(layers[i+1]["depth_km"]) if i + 1 < len(layers) else 6371.0
                        vp = float(l["vp"])
                        if "vs" in l and l["vs"] is not None and float(l["vs"]) > 0:
                            vs = float(l["vs"])
                        else:
                            vs = vp / vp_vs
                        lines.append(f"{top_z:8.2f} {vp:6.2f} {vs:6.2f} NaN")
                        lines.append(f"{bot_z:8.2f} {vp:6.2f} {vs:6.2f} NaN")

                    tvel_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    build_taup_model(str(tvel_path), output_folder=str(cache_dir))

                model = TauPyModel(model=str(npz_path))
                _TAUP_MODEL_CACHE[model_name] = model
                return model
            except Exception as e:  # noqa: BLE001
                print(f"Warning: Failed to build/load TauPyModel from {json_path}: {e}. Falling back to iasp91.")
                model = TauPyModel(model="iasp91")
                _TAUP_MODEL_CACHE[model_name] = model
                return model

    model = TauPyModel(model=model_name)
    _TAUP_MODEL_CACHE[model_name] = model
    return model

def calculate_theoretical_arrivals(stream, model_name=None):
    """Calculate theoretical P and S arrivals for each station."""
    if model_name is None:
        try:
            cfg = load_config()
            model_name = cfg.get("defaults", {}).get("velocity_model", "velocity_model.json")
        except Exception:  # noqa: BLE001
            model_name = "velocity_model.json"

    try:
        model = get_or_create_taup_model(model_name)
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
        if all(k in sac and sac[k] != -12345.0 for k in ["evla", "evlo", "stla", "stlo"]):
            evdp_val = sac.get("evdp", 0.0)
            if evdp_val == -12345.0 or evdp_val is None:
                evdp_val = 0.0
            depth_km = float(evdp_val / 1000.0 if evdp_val > 800.0 else max(0.0, evdp_val))
            dist_deg = locations2degrees(sac["evla"], sac["evlo"], sac["stla"], sac["stlo"])
            
            try:
                arrs = model.get_travel_times(source_depth_in_km=depth_km, distance_in_degree=dist_deg, phase_list=["P", "S", "p", "s"])
                
                if "o" in sac and sac["o"] != -12345.0 and sac["o"] is not None:
                    b = sac.get("b", 0.0)
                    if b == -12345.0 or b is None:
                        b = 0.0
                    origin_time = tr.stats.starttime - float(b) + float(sac["o"])
                    
                    sta_arrs = {}
                    for a in arrs:
                        ph = a.name
                        ph_key = ph.upper()
                        if ph_key in ["P", "S"] and ph_key not in sta_arrs:
                            sta_arrs[ph_key] = origin_time + a.time
                    
                    arrivals[sta] = sta_arrs
            except Exception as e:  # noqa: BLE001
                print(f"Error calculating travel times for {sta}: {e}")
                
    return arrivals

def update_sac_headers_with_location(stream, evla, evlo, depth_km, origin_time, output_dir=None, suffix="_hypo71", picks=None):
    """
    Update SAC headers (evla, evlo, evdp, o, dist, az, baz, gcarc) with relocated hypocenter.
    If picks list is provided, active picks are also written into SAC headers (a, ka, f, t0-t9, kt0-kt9).
    Saves the modified traces into output_dir (defaults to 'h71_localized/' alongside original files)
    with the given suffix without overwriting original files.

    Parameters
    ----------
    stream : obspy.Stream
        Stream with SAC headers to update and save.
    evla : float
        Relocated event latitude.
    evlo : float
        Relocated event longitude.
    depth_km : float
        Relocated event focal depth in km.
    origin_time : UTCDateTime
        Relocated origin time.
    output_dir : str or Path or None
        Destination directory. If None, creates 'h71_localized' in the parent directory of each file.
    suffix : str
        Filename suffix before extension (default: '_hypo71').
    picks : list of dict or None
        Active picks to write into SAC headers.

    Returns
    -------
    list of Path
        List of saved file paths.
    """
    # If picks are provided, apply them to SAC headers of the stream
    if picks:
        for tr in stream:
            if not hasattr(tr.stats, "sac"):
                continue
            sac = tr.stats.sac
            for key in ["a", "f"]:
                if key in sac:
                    sac[key] = -12345.0
            if "ka" in sac:
                sac["ka"] = "-12345"
            for i in range(10):
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

    saved_files = []
    for tr in stream:
        if not hasattr(tr.stats, "sac"):
            tr.stats.sac = {}
        sac = tr.stats.sac

        sac["evla"] = float(evla)
        sac["evlo"] = float(evlo)
        sac["evdp"] = float(depth_km)

        b = float(sac.get("b", 0.0))
        if b == -12345.0:
            b = 0.0
        ref_start = tr.stats.starttime - b
        sac["o"] = float(origin_time - ref_start)

        stla = sac.get("stla")
        stlo = sac.get("stlo")
        if (
            stla is not None
            and stlo is not None
            and stla != -12345.0
            and stlo != -12345.0
        ):
            dist_m, az, baz = gps2dist_azimuth(float(evla), float(evlo), float(stla), float(stlo))
            sac["dist"] = float(dist_m / 1000.0)
            sac["az"] = float(az)
            sac["baz"] = float(baz)
            sac["gcarc"] = float(locations2degrees(float(evla), float(evlo), float(stla), float(stlo)))

        orig_filename = getattr(tr.stats, "filename", None)
        if orig_filename:
            orig_path = Path(orig_filename)
            if output_dir is None:
                target_dir = orig_path.parent / "h71_localized"
            else:
                target_dir = Path(output_dir)

            target_dir.mkdir(parents=True, exist_ok=True)
            new_filename = f"{orig_path.stem}{suffix}{orig_path.suffix}"
            dest_file = target_dir / new_filename
            try:
                tr.write(str(dest_file), format="SAC")
                saved_files.append(dest_file)
            except Exception as e:  # noqa: BLE001
                print(f"Error saving relocated file {dest_file}: {e}")

    return saved_files


_STATION_INVENTORY_CACHE = {}

def get_cache_dir():
    """Return the user cache directory (~/.config/PyPicker/cache)."""
    cache_dir = get_config_dir() / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir

def get_stations_cache_path(client_name="INGV"):
    """Return Path to local StationXML cache file for given FDSN client."""
    cache_dir = get_cache_dir()
    clean_name = "".join(c for c in str(client_name) if c.isalnum() or c in ("-", "_")).upper()
    return cache_dir / f"stations_{clean_name}.xml"

def get_station_inventory(client_name="INGV", force_refresh=False):
    """
    Get or download FDSN station inventory for client_name (default: INGV).
    Checks cache directory first. If present and not force_refresh, loads from cache.
    Otherwise queries FDSN client for all stations, saves to cache, and returns inventory.
    """
    global _STATION_INVENTORY_CACHE  # noqa: PLW0602
    client_key = str(client_name).upper()
    if not force_refresh and client_key in _STATION_INVENTORY_CACHE:
        return _STATION_INVENTORY_CACHE[client_key]

    cache_path = get_stations_cache_path(client_name)
    clean_name = "".join(c for c in str(client_name) if c.isalnum() or c in ("-", "_")).upper()

    if not cache_path.exists() and not force_refresh:
        # Check if default bundled copy exists
        for cand in [
            get_default_config_dir() / f"stations_{clean_name}.xml",
            Path(__file__).resolve().parent / "config" / f"stations_{clean_name}.xml",
            Path("config") / f"stations_{clean_name}.xml",
        ]:
            if cand.exists():
                try:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(cand, cache_path)
                    break
                except Exception:  # noqa: BLE001, S110
                    pass

    if cache_path.exists() and not force_refresh:
        try:
            import obspy
            inv = obspy.read_inventory(str(cache_path))
            _STATION_INVENTORY_CACHE[client_key] = inv
            return inv
        except Exception as e:  # noqa: BLE001
            print(f"Warning: Could not read cached station inventory {cache_path}: {e}")

    try:
        from obspy.clients.fdsn import Client
        client = Client(client_name)
        inv = client.get_stations(level="station")
        try:
            inv.write(str(cache_path), format="STATIONXML")
        except Exception as e:  # noqa: BLE001
            print(f"Warning: Could not write station cache to {cache_path}: {e}")
        _STATION_INVENTORY_CACHE[client_key] = inv
        return inv
    except Exception as e:  # noqa: BLE001
        print(f"Error fetching stations from FDSN client '{client_name}': {e}")
        if cache_path.exists():
            try:
                import obspy
                return obspy.read_inventory(str(cache_path))
            except Exception:  # noqa: BLE001, S110
                pass
        return None

def build_station_index(inventory):
    """
    Build a lookup dictionary station_code -> {latitude, longitude, elevation, network}
    from an ObsPy Inventory.
    """
    index = {}
    if not inventory:
        return index
    for net in inventory:
        for sta in net:
            code = sta.code.upper()
            if code not in index:
                index[code] = {
                    "latitude": float(sta.latitude),
                    "longitude": float(sta.longitude),
                    "elevation": float(sta.elevation) if sta.elevation is not None else 0.0,
                    "network": str(net.code),
                }
    return index

def lookup_station_coordinates(station_code, inventory_or_index):
    """
    Lookup station coordinates by station code.
    Returns (latitude, longitude, elevation) or None.
    """
    if not station_code or not inventory_or_index:
        return None
    if isinstance(inventory_or_index, dict):
        info = inventory_or_index.get(str(station_code).upper())
        if info:
            return float(info["latitude"]), float(info["longitude"]), float(info["elevation"])
        return None

    # Assume ObsPy Inventory
    code_upper = str(station_code).upper()
    for net in inventory_or_index:
        for sta in net:
            if sta.code.upper() == code_upper:
                elev = float(sta.elevation) if sta.elevation is not None else 0.0
                return float(sta.latitude), float(sta.longitude), elev
    return None

def autofill_missing_station_coordinates(stream, inventory=None, client_name="INGV"):
    """
    Check if traces in stream are missing SAC stla/stlo coordinates.
    If missing, query the station inventory (cached or FDSN) to match by station code
    and populate in-memory sac headers without modifying original files on disk.
    Returns the count of updated stations.
    """
    if not stream:
        return 0

    # Check which stations need coordinates
    missing_codes = set()
    for tr in stream:
        sac = getattr(tr.stats, "sac", None)
        stla = sac.get("stla") if sac else None
        stlo = sac.get("stlo") if sac else None
        if stla is None or stlo is None or stla == -12345.0 or stlo == -12345.0:
            missing_codes.add(tr.stats.station.upper())

    if not missing_codes:
        return 0

    if inventory is None:
        inventory = get_station_inventory(client_name=client_name)
    if not inventory:
        return 0

    index = build_station_index(inventory) if not isinstance(inventory, dict) else inventory

    updated_count = 0
    updated_stations = set()
    for tr in stream:
        if not hasattr(tr.stats, "sac"):
            tr.stats.sac = {}
        sac = tr.stats.sac
        stla = sac.get("stla")
        stlo = sac.get("stlo")
        if stla is None or stlo is None or stla == -12345.0 or stlo == -12345.0:
            sta_code = tr.stats.station.upper()
            coords = index.get(sta_code)
            if coords:
                sac["stla"] = float(coords["latitude"])
                sac["stlo"] = float(coords["longitude"])
                sac["stel"] = float(coords["elevation"])
                if sta_code not in updated_stations:
                    updated_stations.add(sta_code)
                    updated_count += 1

    return updated_count

def normalize_traces(stream, inplace=False):
    "Normalize stream traces."

    from collections import defaultdict
    
    new_stream = stream if inplace else stream.copy()
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
    
    from scipy.signal import fftconvolve

    data = np.asarray(data, dtype=np.float64)
    freqs = np.geomspace(f_range[0], f_range[1], n_freqs)
    t_wavelet = np.arange(-2, 2, dt)
    power = np.empty((n_freqs, len(data)))
    for i, f in enumerate(freqs):
        wavelet = np.exp(1j * 2 * np.pi * f * t_wavelet) * np.exp(-(t_wavelet * f / duration) ** 2)
        power[i] = np.abs(fftconvolve(data, wavelet, mode='same')) ** 2
    _, n = power.shape
    pmax = power.max()
    if not np.isfinite(pmax) or pmax <= 0:
        return None

    db = 10 * np.log10(np.maximum(power, pmax * 10 ** (-db_range / 10)))
    levels = tuple(np.percentile(db, percentiles))
    return db, freqs, n * dt, levels


# -----------------------------------------------------------------------------
# Seismic Catalog Table (.txt / TSV) Management for GIS
# -----------------------------------------------------------------------------

SEISMIC_CATALOG_COLUMNS = [
    "Event_ID",
    "Origin_Time_UTC",
    "Latitude",
    "Longitude",
    "Depth_km",
    "RMS_sec",
    "ERH_km",
    "ERZ_km",
    "Quality_Loc",
    "Phases_Used",
    "Stations_Used",
    "Velocity_Model",
    "NP1_Strike",
    "NP1_Dip",
    "NP1_Rake",
    "NP2_Strike",
    "NP2_Dip",
    "NP2_Rake",
    "P_Trend",
    "P_Plunge",
    "T_Trend",
    "T_Plunge",
    "Faulting_Regime",
    "Quality_Focmec",
    "Misfits_Focmec",
    "Num_Polarities",
    "Azimuthal_Gap",
    "Solutions_Count",
]


def get_default_catalog_path(cfg=None):
    """
    Get the configured or default path for the seismic catalog .txt file.
    Default: ~/Desktop/seismic_catalog.txt (fallback to ~/seismic_catalog.txt if Desktop not present).
    """
    if cfg is None:
        cfg = load_config()

    cat_path_str = cfg.get("defaults", {}).get("catalog_file", "")
    if cat_path_str:
        return Path(os.path.expanduser(os.path.expandvars(cat_path_str)))

    desktop = Path.home() / "Desktop"
    if desktop.is_dir():
        return desktop / "seismic_catalog.txt"
    return Path.home() / "seismic_catalog.txt"


def calculate_focmec_quality(num_polarities, misfits, gap_deg):
    """
    Calculate focal mechanism quality grade (A, B, C, D) based on polarities, misfits, and azimuthal gap.
    """
    if num_polarities <= 0:
        return ""
    misfit_ratio = float(misfits) / float(num_polarities)
    if num_polarities >= 12 and misfits <= 1 and gap_deg <= 120.0:
        return "A"
    elif num_polarities >= 8 and misfits <= 2 and gap_deg <= 180.0:
        return "B"
    elif num_polarities >= 5 and misfit_ratio <= 0.25 and gap_deg <= 270.0:
        return "C"
    else:
        return "D"


def get_or_create_event_id(stream, picks=None, hypocenter=None):
    """
    Extract or synthesize a stable, unique Event_ID for the loaded seismic dataset.
    """
    # 1. Check SAC header 'kevnm' or event name
    if stream:
        for tr in stream:
            sac = getattr(tr.stats, "sac", {})
            kevnm = str(sac.get("kevnm", "")).strip()
            if kevnm and kevnm not in ("-12345", "-12345.0", "None", ""):
                return kevnm

    # 2. Check if hypocenter has an explicit ID
    if hypocenter and hypocenter.get("event_id"):
        return str(hypocenter["event_id"])

    # 3. Check folder name if all traces reside in a common parent folder
    if stream:
        filenames = [getattr(tr.stats, "filename", None) for tr in stream]
        valid_paths = [Path(f) for f in filenames if f]
        if valid_paths:
            parents = {p.parent.name for p in valid_paths}
            if len(parents) == 1:
                parent_name = list(parents)[0]
                if parent_name and parent_name not in (".", "/", "\\", "h71_localized"):
                    return parent_name

    # 4. Synthesize from origin time or earliest trace starttime
    t_ref = None
    if hypocenter and hypocenter.get("origin_time"):
        t_ref = hypocenter["origin_time"]
    elif stream and len(stream) > 0:
        t_ref = min(tr.stats.starttime for tr in stream)

    if t_ref:
        if not isinstance(t_ref, UTCDateTime):
            try:
                t_ref = UTCDateTime(t_ref)
            except Exception:
                t_ref = None
        if t_ref:
            return f"EV_{t_ref.strftime('%Y%m%d_%H%M%S')}"

    return "EV_UNKNOWN"


def load_seismic_catalog(catalog_path):
    """
    Read tab-separated seismic catalog file into a list of row dicts.
    Preserves all standard columns.
    """
    path = Path(os.path.expanduser(os.path.expandvars(str(catalog_path))))
    if not path.is_file():
        return []

    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for r in reader:
            clean_row = {col: str(r.get(col, "")).strip() for col in SEISMIC_CATALOG_COLUMNS}
            rows.append(clean_row)
    return rows


def update_seismic_catalog(catalog_path, event_dict):
    """
    Update or insert an event record into the tab-separated GIS seismic catalog (.txt).
    
    If the event already exists (matched by Event_ID or Origin_Time within 30 s),
    its row is updated in-place (overwritten/merged), preserving existing non-empty values.
    Otherwise, a new row is appended.
    All SEISMIC_CATALOG_COLUMNS are strictly maintained on every row.
    
    Parameters
    ----------
    catalog_path : str or Path
        Target file path (e.g. ~/Desktop/seismic_catalog.txt).
    event_dict : dict
        Dictionary with updated event attributes.
        
    Returns
    -------
    Path
        Resolved path to the updated catalog file.
    """
    path = Path(os.path.expanduser(os.path.expandvars(str(catalog_path))))
    path.parent.mkdir(parents=True, exist_ok=True)

    rows = load_seismic_catalog(path)

    # Determine match
    new_ev_id = str(event_dict.get("Event_ID", "")).strip()
    new_ot_str = str(event_dict.get("Origin_Time_UTC", "")).strip()
    new_ot = None
    if new_ot_str:
        try:
            new_ot = UTCDateTime(new_ot_str)
        except Exception:
            pass

    match_idx = -1
    for i, r in enumerate(rows):
        r_id = r.get("Event_ID", "").strip()
        # Direct ID match
        if new_ev_id and r_id and new_ev_id == r_id:
            match_idx = i
            break

        # Time-proximity match (same event relocalized slightly changes OT)
        r_ot_str = r.get("Origin_Time_UTC", "").strip()
        if new_ot and r_ot_str:
            try:
                r_ot = UTCDateTime(r_ot_str)
                if abs(new_ot - r_ot) <= 30.0:
                    match_idx = i
                    break
            except Exception:
                pass

    # Normalize incoming fields
    clean_incoming = {}
    for k in SEISMIC_CATALOG_COLUMNS:
        if k in event_dict and event_dict[k] is not None:
            val = event_dict[k]
            if isinstance(val, float):
                if k in ("Latitude", "Longitude"):
                    clean_incoming[k] = f"{val:.4f}"
                elif k in ("Depth_km", "ERH_km", "ERZ_km"):
                    clean_incoming[k] = f"{val:.2f}"
                elif k in ("RMS_sec",):
                    clean_incoming[k] = f"{val:.3f}"
                elif k in (
                    "NP1_Strike", "NP1_Dip", "NP1_Rake",
                    "NP2_Strike", "NP2_Dip", "NP2_Rake",
                    "P_Trend", "P_Plunge", "T_Trend", "T_Plunge",
                    "Azimuthal_Gap",
                ):
                    clean_incoming[k] = f"{val:.1f}"
                else:
                    clean_incoming[k] = f"{val:.2f}"
            elif isinstance(val, UTCDateTime):
                clean_incoming[k] = val.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            else:
                clean_incoming[k] = str(val).strip()

    if match_idx >= 0:
        # Merge/Overwrite into existing row
        for k, v in clean_incoming.items():
            if v != "":
                rows[match_idx][k] = v
    else:
        # Create brand-new row with all columns initialized to empty strings
        new_row = {col: "" for col in SEISMIC_CATALOG_COLUMNS}
        new_row.update(clean_incoming)
        rows.append(new_row)

    # Write out as tab-separated .txt file
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SEISMIC_CATALOG_COLUMNS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for r in rows:
            # Ensure every column is present
            full_r = {c: r.get(c, "") for c in SEISMIC_CATALOG_COLUMNS}
            writer.writerow(full_r)

    return path