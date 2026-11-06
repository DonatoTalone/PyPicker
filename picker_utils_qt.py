import csv  # noqa: EXE002
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

__version__ = "3.0.1"

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
        "export_picks": "Ctrl+E",
        "import_picks": "Ctrl+I",
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

def detect_system_dark_mode():
    """
    Detect whether the host OS is configured in Dark Mode.
    Returns True for Dark, False for Light, or None if undetermined.
    """
    # 1. darkdetect package (if installed)
    try:
        import darkdetect
        detected = darkdetect.theme()
        if detected:
            return detected.lower() == "dark"
    except Exception:  # noqa: BLE001, S110
        pass

    # 2. Linux
    if sys.platform.startswith("linux"):
        # a) Freedesktop portal Settings appearance color-scheme
        try:
            import subprocess
            res = subprocess.run(
                [
                    "dbus-send",
                    "--session",
                    "--print-reply=literal",
                    "--dest=org.freedesktop.portal.Desktop",
                    "/org/freedesktop/portal/desktop",
                    "org.freedesktop.portal.Settings.Read",
                    "string:org.freedesktop.appearance",
                    "string:color-scheme",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=0.5,
            )
            if res.returncode == 0:
                val = res.stdout.strip()
                if "uint32 1" in val:
                    return True
                elif "uint32 2" in val:
                    return False
        except Exception:  # noqa: BLE001, S110
            pass

        # b) GNOME / XDG gsettings
        try:
            import subprocess
            res = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                check=False,
                capture_output=True,
                text=True,
                timeout=0.5,
            )
            if "dark" in res.stdout.lower():
                return True
            elif "light" in res.stdout.lower():
                return False
        except Exception:  # noqa: BLE001, S110
            pass

        try:
            import subprocess
            res = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
                check=False,
                capture_output=True,
                text=True,
                timeout=0.5,
            )
            if "-dark" in res.stdout.lower():
                return True
        except Exception:  # noqa: BLE001, S110
            pass

        # c) KDE Plasma kdeglobals
        try:
            kde_cfg = Path.home() / ".config" / "kdeglobals"
            if kde_cfg.exists():
                content = kde_cfg.read_text(errors="ignore")
                for line in content.splitlines():
                    if line.strip().startswith("ColorScheme="):
                        if "dark" in line.lower():
                            return True
                        elif "light" in line.lower():
                            return False
        except Exception:  # noqa: BLE001, S110
            pass

        # d) Desktop Environment Variables
        for var in ("QT_STYLE_OVERRIDE", "GTK_THEME"):
            val = os.environ.get(var, "").lower()
            if "dark" in val:
                return True
            elif "light" in val:
                return False

    # 3. macOS
    elif sys.platform == "darwin":
        try:
            import subprocess
            res = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                check=False,
                capture_output=True,
                text=True,
                timeout=0.5,
            )
            return "dark" in res.stdout.lower()
        except Exception:  # noqa: BLE001
            return False

    # 4. Windows
    elif sys.platform.startswith("win"):
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return val == 0
        except Exception:  # noqa: BLE001, S110
            pass

    return None

def open_path_in_system(target_path):
    """
    Open a file or directory using the operating system's default application or file manager.
    Ensures directory exists and provides multi-tier fallbacks (os.startfile, xdg-open with clean env, open, QDesktopServices).
    """
    import subprocess

    from PyQt6.QtCore import QUrl
    from PyQt6.QtGui import QDesktopServices

    path = Path(os.path.expanduser(os.path.expandvars(str(target_path)))).resolve()
    if not path.exists():
        if path.suffix:
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            path.mkdir(parents=True, exist_ok=True)

    # Clean environment for external subprocess calls so child processes on Linux (xdg-open, file managers)
    # do not inherit PyInstaller's LD_LIBRARY_PATH which causes glibc symbol conflicts.
    clean_env = dict(os.environ)
    if "LD_LIBRARY_PATH_ORIG" in clean_env:
        clean_env["LD_LIBRARY_PATH"] = clean_env["LD_LIBRARY_PATH_ORIG"]
    else:
        clean_env.pop("LD_LIBRARY_PATH", None)

    # 1. Windows: Native ShellExecuteW via os.startfile is the most reliable for both files and directories
    if sys.platform.startswith("win"):
        try:
            os.startfile(str(path))
            return True
        except Exception:
            pass

    # 2. macOS: "open" command
    elif sys.platform == "darwin":
        try:
            subprocess.Popen(["open", str(path)])
            return True
        except Exception:
            pass

    # 3. Linux / Unix: "xdg-open" with sanitized LD_LIBRARY_PATH
    else:
        try:
            subprocess.Popen(["xdg-open", str(path)], env=clean_env)
            return True
        except Exception:
            pass

    # 4. Fallback: QDesktopServices
    try:
        url = QUrl.fromLocalFile(str(path))
        if QDesktopServices.openUrl(url):
            return True
    except Exception:
        pass

    return False

def get_system_desktop_dir():
    """
    Return the localized desktop directory for the current operating system.
    Supports localized folder names (e.g. ~/Scrivania in Italian, ~/Bureau in French, ~/Escritorio in Spanish)
    via QStandardPaths, with fallbacks.
    """
    loc = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
    if loc:
        d = Path(loc)
        if d.is_dir():
            return d

    fallback = Path.home() / "Desktop"
    if fallback.is_dir():
        return fallback

    return Path.home()

def get_app_icon(theme="dark"):
    """
    Return a QIcon for PyPicker.
    theme can be 'dark', 'white'/'light', or 'System'.
    Tries PNG, SVG, or ICO formats.
    """
    if str(theme).lower() == "system":
        is_dark = detect_system_dark_mode()
        theme_key = "dark" if (is_dark is not False) else "white"
    else:
        theme_key = "dark" if str(theme).lower() == "dark" else "white"

    icon_dir = get_icon_dir()
    prefix = f"PyPicker_icon_{theme_key}"
    
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
    if str(theme).lower() == "system":
        is_dark = detect_system_dark_mode()
        theme_key = "dark" if (is_dark is not False) else "white"
    else:
        theme_key = "dark" if str(theme).lower() == "dark" else "white"

    icon_dir = get_icon_dir()
    name = f"PyPicker_logo_{theme_key}.png"
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
    dm, dt, f = 0, 0, 0

    if params.get("demean"):
        st.detrend("demean")
        dm = 1
    if params.get("detrend"):
        st.detrend("linear")
        dt = 1
    if params.get("normalize"):
        if dm != 1:
            st.detrend("demean")
            dm = 1
        if dt != 1:
            st.detrend("linear")
            dt = 1

    f_type = params.get("filter_type")
    low = params.get("low_f", 1.0)
    high = params.get("high_f", 20.0)

    if f_type and f_type != "None":
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

    if dm == 1 or dt == 1 or f == 1 or params.get("normalize"):
        st.taper(max_percentage=0.05, type="cosine")

    if params.get("normalize"):
        st = normalize_traces(st, inplace=True)

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

def normalize_polarity(val):
    """
    Normalize polarity to one of 'positive', 'negative', or 'undecidable'.
    """
    if val is None:
        return "undecidable"
    if isinstance(val, (int, float)):
        if val > 0:
            return "positive"
        elif val < 0:
            return "negative"
        return "undecidable"
    s = str(val).strip().lower()
    if s in ("positive", "+", "+1", "1", "1.0", "pos", "u", "up", "c", "comp", "compression"):
        return "positive"
    elif s in ("negative", "-", "-1", "-1.0", "neg", "d", "down", "dil", "dilatation"):
        return "negative"
    return "undecidable"

def normalize_onset(val):
    """
    Normalize onset to one of 'Impulsive', 'Emergent', or 'Unknown'.
    """
    if val is None:
        return "Unknown"
    s = str(val).strip().lower()
    if s in ("i", "impulsive"):
        return "Impulsive"
    elif s in ("e", "emergent"):
        return "Emergent"
    return "Unknown"

def parse_sac_phase_identification(raw_name, default_phase="P"):
    """
    Parse a SAC arrival identification string (e.g. 'IPU', 'EPD', 'P+', 'P-', 'P')
    into (phase, onset, polarity).
    """
    if not raw_name or raw_name == "-12345":
        return default_phase, "Unknown", "undecidable"

    s = raw_name.strip()
    onset = "Unknown"
    polarity = "undecidable"

    # 1. Check onset prefix (I or E) if followed by standard phase letter (P or S)
    if len(s) >= 2 and s[0].upper() in ("I", "E") and s[1].upper() in ("P", "S"):
        onset = "Impulsive" if s[0].upper() == "I" else "Emergent"
        s = s[1:]

    # 2. Check polarity suffix (+, -, U, D, C)
    if s.endswith(("+", "U", "u", "C", "c")):
        polarity = "positive"
        s = s[:-1].rstrip("_")
    elif s.endswith(("-", "D", "d")):
        polarity = "negative"
        s = s[:-1].rstrip("_")

    phase = s.upper() if s else default_phase
    return phase, onset, polarity

def format_sac_pick_name(phase, onset, polarity):
    """
    Format a standard SAC arrival identification string (e.g. 'IPU', 'EPD', 'P+', 'P').
    """
    p = phase.upper() if phase else "P"
    onset_char = ""
    if onset:
        ons_norm = normalize_onset(onset)
        if ons_norm == "Impulsive":
            onset_char = "I"
        elif ons_norm == "Emergent":
            onset_char = "E"

    pol_char = ""
    if polarity:
        pol_clean = normalize_polarity(polarity)
        if pol_clean == "positive":
            pol_char = "U"
        elif pol_clean == "negative":
            pol_char = "D"

    # For standard P or S arrivals
    if p in ("P", "S"):
        return f"{onset_char}{p}{pol_char}" if (onset_char or pol_char) else p
    else:
        # For other phases like Pg, Sg
        if pol_char:
            return f"{p}{'+' if pol_char == 'U' else '-'}"[:8]
        return p[:8]

def apply_picks_to_stream_sac_headers(stream, picks):
    """
    Write picks back into the SAC headers of the loaded stream.
    Clears old picks first so that deleted picks are actually removed from the headers.
    """
    for tr in stream:
        if not hasattr(tr.stats, "sac"):
            continue
        sac = tr.stats.sac
        for key in ["a", "f", "user0"]:
            if key in sac:
                sac[key] = -12345.0
        for kkey in ["ka", "kuser0"]:
            if kkey in sac:
                sac[kkey] = "-12345"
        for i in range(10):
            t_key = f"t{i}"
            err_key = f"resp{i}"
            name_key = f"kt{i}"
            usr_key = f"user{i+1}" if i < 9 else None
            kusr_key = f"kuser{i+1}" if i + 1 <= 2 else None
            if t_key in sac:
                sac[t_key] = -12345.0
            if err_key in sac:
                sac[err_key] = -12345.0
            if name_key in sac:
                sac[name_key] = "-12345"
            if usr_key and usr_key in sac:
                sac[usr_key] = -12345.0
            if kusr_key and kusr_key in sac:
                sac[kusr_key] = "-12345"

    if not picks:
        return

    sta_other_idx = {}

    for pk in picks:
        target_traces = stream.select(station=pk["sta"])
        if not target_traces:
            continue

        unc = float(pk.get("uncertainty", 0.0))
        pol = normalize_polarity(pk.get("polarity"))
        onset = normalize_onset(pk.get("onset"))
        p_name = pk.get("phase", "").upper()
        pick_time = UTCDateTime(pk["abs_t"])

        pol_val = 1.0 if pol == "positive" else (-1.0 if pol == "negative" else 0.0)
        pol_str = "POSITIVE" if pol == "positive" else ("NEGATIVE" if pol == "negative" else "UNDECID")

        if p_name == "P":
            ka_label = format_sac_pick_name("P", onset, pol)
            for tr in target_traces:
                if not hasattr(tr.stats, "sac"):
                    tr.stats.sac = {}
                rel_time = pick_time - tr.stats.starttime
                tr.stats.sac["a"] = rel_time
                tr.stats.sac["ka"] = ka_label
                tr.stats.sac["f"] = unc
                tr.stats.sac["user0"] = pol_val
                tr.stats.sac["kuser0"] = pol_str
        elif p_name == "S":
            kt0_label = format_sac_pick_name("S", onset, pol)
            for tr in target_traces:
                if not hasattr(tr.stats, "sac"):
                    tr.stats.sac = {}
                rel_time = pick_time - tr.stats.starttime
                tr.stats.sac["t0"] = rel_time
                tr.stats.sac["kt0"] = kt0_label
                tr.stats.sac["resp0"] = unc
                tr.stats.sac["user1"] = pol_val
                tr.stats.sac["kuser1"] = pol_str
        else:
            cur_idx = sta_other_idx.get(pk["sta"], 0) + 1
            sta_other_idx[pk["sta"]] = cur_idx
            if cur_idx <= 9:
                label = format_sac_pick_name(p_name, onset, pol)
                for tr in target_traces:
                    if not hasattr(tr.stats, "sac"):
                        tr.stats.sac = {}
                    rel_time = pick_time - tr.stats.starttime
                    tr.stats.sac[f"t{cur_idx}"] = rel_time
                    tr.stats.sac[f"kt{cur_idx}"] = label
                    tr.stats.sac[f"resp{cur_idx}"] = unc
                    if cur_idx + 1 <= 9:
                        tr.stats.sac[f"user{cur_idx+1}"] = pol_val

def extract_existing_picks(stream):
    """
    Extract picking information from SAC headers.
    Looks for markers: a (P), t0 (S), and t1-t9, along with polarity and onset.
    """
    found_picks = []
    seen_identifiers = set()

    for tr in stream:
        if not hasattr(tr.stats, "sac"):
            continue

        sac = tr.stats.sac
        # Map: (SAC time key, SAC label key, SAC error key, SAC user float key, SAC user str key, default_phase)
        markers = [
            ("a", "ka", "f", "user0", "kuser0", "P"),
            ("t0", "kt0", "resp0", "user1", "kuser1", "S"),
        ]
        for i in range(1, 10):
            markers.append((f"t{i}", f"kt{i}", f"resp{i}", f"user{i+1}" if i < 9 else None, None, f"T{i}"))

        for time_key, name_key, err_key, usr_key, kusr_key, def_phase in markers:
            if time_key in sac:
                rel_time = sac[time_key]
                if rel_time == -12345.0:
                    continue

                abs_t = tr.stats.starttime + rel_time

                raw_name = str(sac.get(name_key, def_phase)).strip()
                if not raw_name or raw_name == "-12345":
                    raw_name = def_phase

                phase_name, onset, pol_from_name = parse_sac_phase_identification(raw_name, default_phase=def_phase)

                # Handle uncertainty; SAC uses -12345.0 as null
                uncertainty = sac.get(err_key, 0.0)
                if uncertainty == -12345.0:
                    uncertainty = 0.0

                # Polarity check order:
                # 1. kuser
                # 2. user
                # 3. name-derived
                polarity = "undecidable"
                if kusr_key and kusr_key in sac and str(sac[kusr_key]).strip() not in ("", "-12345"):
                    polarity = normalize_polarity(sac[kusr_key])
                elif usr_key and usr_key in sac and sac[usr_key] != -12345.0:
                    polarity = normalize_polarity(sac[usr_key])
                else:
                    polarity = pol_from_name

                pick_id = (tr.stats.station, phase_name, str(abs_t))

                if pick_id not in seen_identifiers:
                    found_picks.append(
                        {
                            "sta": tr.stats.station,
                            "cha_source": tr.stats.channel,
                            "phase": phase_name,
                            "abs_t": str(abs_t),
                            "uncertainty": uncertainty,
                            "polarity": polarity,
                            "onset": onset,
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
                    "polarity": normalize_polarity(row[5]) if len(row) > 5 else "undecidable",
                    "onset": normalize_onset(row[6]) if len(row) > 6 else "Unknown",
                }
                picks.append(pk)
    return picks

def extract_picks_from_seisgram_pick(filename):
    """
    Extract the pick list from a .pick file created by Seisgram2k.
    """
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
                "polarity": normalize_polarity(row[5]),
                "onset": normalize_onset(row[3]),
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
                "polarity": normalize_polarity(pick.polarity),
                "onset": normalize_onset(pick.onset),
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
                    normalize_polarity(p.get("polarity", "undecidable")),
                    normalize_onset(p.get("onset", "Unknown")),
                ]
            )

def save_picks_to_sac(stream, picks):
    """
    Write picks back into the SAC headers of the loaded stream and save files.
    Clears old picks first so that deleted picks are actually removed from the files.
    """
    apply_picks_to_stream_sac_headers(stream, picks)
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
        
        pol = normalize_polarity(pk.get("polarity"))
        if pol in ("positive", "negative", "undecidable"):
            pick.polarity = pol
        ons = normalize_onset(pk.get("onset"))
        if ons in ("Impulsive", "Emergent"):
            pick.onset = ons.lower()
            
        event.picks.append(pick)
    
    cat.append(event)
    cat.write(filename, format="QUAKEML")

def uncertainty_to_hypo71_weight(unc):
    """Map pick uncertainty in seconds to HYPO71 weight code (0-4)."""
    try:
        u = float(unc)
    except Exception:
        return 0
    if u <= 0.05:
        return 0
    elif u <= 0.10:
        return 1
    elif u <= 0.20:
        return 2
    elif u <= 0.50:
        return 3
    return 4

def hypo71_weight_to_uncertainty(weight_code):
    """Map HYPO71 weight code (0-4) to representative uncertainty in seconds."""
    mapping = {0: 0.02, 1: 0.10, 2: 0.20, 3: 0.50, 4: 1.00}
    try:
        return mapping.get(int(weight_code), 0.0)
    except Exception:
        return 0.0

def export_to_seisgram_pick(picks, filename):
    """
    Export the pick list to a SeisGram2K .pick / NonLinLoc observation file.
    """
    with open(filename, "w") as f:
        for p in picks:
            t = UTCDateTime(p["abs_t"])
            sta = str(p.get("sta", "?")).strip().ljust(6)
            inst = "?".ljust(4)
            cmp = (str(p.get("cha_source", "?")).strip() or "?").ljust(4)
            onset = normalize_onset(p.get("onset"))
            ons_char = "i" if onset == "Impulsive" else ("e" if onset == "Emergent" else "?")
            phase = str(p.get("phase", "?")).strip().ljust(6)
            pol = normalize_polarity(p.get("polarity"))
            pol_char = "U" if pol == "positive" else ("D" if pol == "negative" else "?")
            date_str = t.strftime("%Y%m%d")
            time_str = t.strftime("%H%M")
            sec_val = t.second + t.microsecond * 1e-6
            unc = float(p.get("uncertainty", 0.0))
            f.write(
                f"{sta} {inst} {cmp} {ons_char} {phase} {pol_char} "
                f"{date_str} {time_str} {sec_val:7.4f} GAU {unc:9.2e} -1.00e+00 -1.00e+00 -1.00e+00\n"
            )
        f.write("\n")

def export_to_nlloc(picks, filename):
    """
    Export the pick list to a NonLinLoc Phase Observation file (.obs).
    Uses standard NLLOC_OBS space-delimited format identical to SeisGram2K.
    """
    export_to_seisgram_pick(picks, filename)

def extract_picks_from_nlloc(filename):
    """
    Extract picks from a NonLinLoc phase file (.obs, .nll, .hyp, or .dat).
    Supports standard 11-column and 14-column phase line variants.
    """
    picks = []
    with open(filename, "r") as f:
        for line in f:
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue
            row = line_str.split()
            if row[0].upper() == "PHASE":
                row = row[1:]
            if len(row) < 8:
                continue
            sta = row[0]
            cmp = row[2] if len(row) > 2 else "?"
            onset = row[3] if len(row) > 3 else "?"
            phase = row[4] if len(row) > 4 else "?"
            polarity = row[5] if len(row) > 5 else "?"

            try:
                if len(row[6]) == 8:
                    # YYYYMMDD HHMM SS.SSS
                    date_part = row[6]
                    time_part = row[7]
                    sec_float = float(row[8])
                    unc_idx = 10
                elif len(row[6]) == 4:
                    # YYYY MM DD HH MM SS.SSS
                    date_part = f"{row[6]}{int(row[7]):02d}{int(row[8]):02d}"
                    time_part = f"{int(row[9]):02d}{int(row[10]):02d}"
                    sec_float = float(row[11])
                    unc_idx = 13
                else:
                    continue

                t0 = datetime.strptime(date_part + time_part, "%Y%m%d%H%M")
                abs_t = t0 + timedelta(seconds=sec_float)
                uncertainty = float(row[unc_idx]) if len(row) > unc_idx else 0.0

                picks.append({
                    "sta": sta,
                    "cha_source": cmp if cmp != "?" else "",
                    "phase": phase,
                    "abs_t": abs_t.isoformat(timespec="milliseconds"),
                    "uncertainty": uncertainty,
                    "polarity": normalize_polarity(polarity),
                    "onset": normalize_onset(onset),
                })
            except Exception:
                continue
    return picks

def export_to_hypo71(picks, filename):
    """
    Export picks to a HYPO71 / HYPOELLIPSE phase card file (.pha).
    Cards are grouped by station, encoding P and S arrivals on fixed-column lines.
    """
    sta_picks = {}
    for pk in picks:
        sta = pk.get("sta", "")
        if not sta:
            continue
        if sta not in sta_picks:
            sta_picks[sta] = {}
        p_name = pk.get("phase", "").upper()
        if p_name.startswith("P") and "P" not in sta_picks[sta]:
            sta_picks[sta]["P"] = pk
        elif p_name.startswith("S") and "S" not in sta_picks[sta]:
            sta_picks[sta]["S"] = pk
        elif p_name not in sta_picks[sta]:
            sta_picks[sta][p_name] = pk

    with open(filename, "w") as f:
        for sta, ph_map in sta_picks.items():
            p_pick = ph_map.get("P")
            s_pick = ph_map.get("S")

            ref_pick = p_pick or s_pick or next(iter(ph_map.values()), None)
            if not ref_pick:
                continue

            t_ref = UTCDateTime(ref_pick["abs_t"])
            yy = t_ref.year % 100
            dt_str = f"{yy:02d}{t_ref.month:02d}{t_ref.day:02d}{t_ref.hour:02d}{t_ref.minute:02d}"

            if p_pick:
                t_p = UTCDateTime(p_pick["abs_t"])
                p_ons_code = "I" if normalize_onset(p_pick.get("onset")) == "Impulsive" else ("E" if normalize_onset(p_pick.get("onset")) == "Emergent" else " ")
                p_pol_code = "U" if normalize_polarity(p_pick.get("polarity")) == "positive" else ("D" if normalize_polarity(p_pick.get("polarity")) == "negative" else " ")
                p_wt_code = str(uncertainty_to_hypo71_weight(p_pick.get("uncertainty", 0.0)))
                p_sec = (t_p - UTCDateTime(t_ref.year, t_ref.month, t_ref.day, t_ref.hour, t_ref.minute))
                p_sec_str = f"{p_sec:5.2f}"
            else:
                p_ons_code = " "
                p_pol_code = " "
                p_wt_code = " "
                p_sec_str = "     "

            if s_pick:
                t_s = UTCDateTime(s_pick["abs_t"])
                s_ons_code = "I" if normalize_onset(s_pick.get("onset")) == "Impulsive" else ("E" if normalize_onset(s_pick.get("onset")) == "Emergent" else " ")
                s_rmk = f"{s_ons_code}S "
                s_wt_code = str(uncertainty_to_hypo71_weight(s_pick.get("uncertainty", 0.0)))
                s_sec = (t_s - UTCDateTime(t_ref.year, t_ref.month, t_ref.day, t_ref.hour, t_ref.minute))
                s_sec_str = f"{s_sec:5.2f}"
            else:
                s_sec_str = "     "
                s_rmk = "   "
                s_wt_code = " "

            sta_str = sta[:4].ljust(4)
            p_p_char = "P" if p_pick else " "
            line = f"{sta_str}{p_ons_code}{p_p_char}{p_pol_code}{p_wt_code} {dt_str}{p_sec_str}       {s_sec_str}{s_rmk}{s_wt_code}\n"
            f.write(line)

        # Terminator instruction card (blank card)
        f.write("\n")

def extract_picks_from_hypo71(filename):
    """
    Extract picks from a HYPO71 / HYPOELLIPSE phase card file (.pha, .h71, .dat).
    """
    picks = []
    with open(filename, "r") as f:
        for line in f:
            if len(line.rstrip("\r\n")) < 20:
                continue
            sta = line[0:4].strip()
            if not sta or sta.startswith("#"):
                continue

            p_rem = line[4:8]
            dt_str = line[9:19].strip()
            p_sec_str = line[19:24].strip() if len(line) >= 24 else ""
            s_sec_str = line[31:36].strip() if len(line) >= 36 else ""
            s_rem = line[36:40] if len(line) >= 40 else ""

            if len(dt_str) != 10:
                continue

            try:
                yy = int(dt_str[0:2])
                year = 2000 + yy if yy < 70 else 1900 + yy
                month = int(dt_str[2:4])
                day = int(dt_str[4:6])
                hour = int(dt_str[6:8])
                minute = int(dt_str[8:10])
                t_base = UTCDateTime(year, month, day, hour, minute)

                # 1. P arrival
                if p_sec_str:
                    p_sec = float(p_sec_str)
                    p_abs_t = t_base + p_sec
                    p_ons = "Impulsive" if p_rem[0].upper() == "I" else ("Emergent" if p_rem[0].upper() == "E" else "Unknown")
                    p_pol = "positive" if p_rem[2].upper() in ("U", "C", "+") else ("negative" if p_rem[2].upper() in ("D", "-") else "undecidable")
                    p_wt = p_rem[3] if len(p_rem) > 3 and p_rem[3].isdigit() else "0"
                    p_unc = hypo71_weight_to_uncertainty(p_wt)

                    picks.append({
                        "sta": sta,
                        "cha_source": "",
                        "phase": "P",
                        "abs_t": str(p_abs_t),
                        "uncertainty": p_unc,
                        "polarity": p_pol,
                        "onset": p_ons,
                    })

                # 2. S arrival
                if s_sec_str:
                    s_sec = float(s_sec_str)
                    s_abs_t = t_base + s_sec
                    s_ons = "Impulsive" if "I" in s_rem.upper() else ("Emergent" if "E" in s_rem.upper() else "Unknown")
                    s_wt = s_rem[-1] if s_rem.strip() and s_rem.strip()[-1].isdigit() else "0"
                    s_unc = hypo71_weight_to_uncertainty(s_wt)

                    picks.append({
                        "sta": sta,
                        "cha_source": "",
                        "phase": "S",
                        "abs_t": str(s_abs_t),
                        "uncertainty": s_unc,
                        "polarity": "undecidable",
                        "onset": s_ons,
                    })
            except Exception:
                continue

    return picks

def load_picks_from_file(filename, format_hint=None):
    """
    Universal picks loader that auto-detects or uses format_hint for:
    CSV, QuakeML, SeisGram2K (.pick), NonLinLoc (.obs/.hyp), HYPO71/HYPOELLIPSE (.pha/.h71).
    """
    p = Path(filename)
    ext = p.suffix.lower()

    if ext == ".csv" or (format_hint and "csv" in format_hint.lower()):
        return extract_picks_from_csv(filename)
    elif ext in (".qml", ".xml") or (format_hint and ("qml" in format_hint.lower() or "quakeml" in format_hint.lower())):
        return extract_picks_from_quakeml(filename)
    elif ext == ".pick" or (format_hint and "seisgram" in format_hint.lower()):
        return extract_picks_from_seisgram_pick(filename)
    elif ext in (".obs", ".nll") or (format_hint and "nonlinloc" in format_hint.lower()):
        return extract_picks_from_nlloc(filename)
    elif ext in (".pha", ".h71") or (format_hint and ("hypo71" in format_hint.lower() or "hypoellipse" in format_hint.lower())):
        return extract_picks_from_hypo71(filename)

    # Content auto-detection for .dat, .txt or ambiguous extensions
    try:
        with open(filename, "r") as f:
            head_lines = [f.readline() for _ in range(10)]
        non_empty = [l.strip() for l in head_lines if l.strip()]
        if not non_empty:
            return []
        first = non_empty[0]

        if first.startswith("<?xml") or "<q:quakeml" in first or "<quakeml" in first:
            return extract_picks_from_quakeml(filename)
        if ";" in first or "," in first or "UTC_Time" in first:
            return extract_picks_from_csv(filename)
        if any("GAU" in l or l.startswith("PHASE") for l in non_empty):
            return extract_picks_from_nlloc(filename)
        if len(first) >= 20 and len(first.split()[0]) <= 5 and any(c in first for c in ("P", "S")):
            return extract_picks_from_hypo71(filename)
    except Exception:
        pass

    # Fallback cascade
    for fn in (extract_picks_from_nlloc, extract_picks_from_hypo71, extract_picks_from_csv):
        try:
            res = fn(filename)
            if res:
                return res
        except Exception:
            pass
    return extract_picks_from_csv(filename)

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
            sac_ka = sac.get("ka", "").strip().upper()
            ka_phase, _, _ = parse_sac_phase_identification(sac_ka, default_phase="P")
            if ka_phase == "P" or "a" in sac:
                sac["a"] = -12345.0
                sac["ka"] = "-12345"
                sac["f"] = -12345.0
                sac["user0"] = -12345.0
                sac["kuser0"] = "-12345"
        elif p_name == "S":
            sac_kt0 = sac.get("kt0", "").strip().upper()
            kt0_phase, _, _ = parse_sac_phase_identification(sac_kt0, default_phase="S")
            if kt0_phase == "S" or "t0" in sac:
                sac["t0"] = -12345.0
                sac["kt0"] = "-12345"
                sac["resp0"] = -12345.0
                sac["user1"] = -12345.0
                sac["kuser1"] = "-12345"

        for i in range(10):
            name_key = f"kt{i}"
            t_key = f"t{i}"
            err_key = f"resp{i}"
            usr_key = f"user{i+1}" if i < 9 else None
            kusr_key = f"kuser{i+1}" if i + 1 <= 2 else None
            kt_val = sac.get(name_key, "").strip().upper()
            kt_phase, _, _ = parse_sac_phase_identification(kt_val, default_phase=f"T{i}")
            if kt_phase == p_name or kt_val == p_name:
                sac[t_key] = -12345.0
                sac[name_key] = "-12345"
                sac[err_key] = -12345.0
                if usr_key and usr_key in sac:
                    sac[usr_key] = -12345.0
                if kusr_key and kusr_key in sac:
                    sac[kusr_key] = "-12345"

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
        apply_picks_to_stream_sac_headers(stream, picks)

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
    """
    Normalize stream traces.

    Each 3-component set of traces for a given station and channel/instrument
    is normalized by the shared maximum absolute amplitude among those traces,
    preserving relative component amplitudes.
    """
    from collections import defaultdict

    new_stream = stream if inplace else stream.copy()
    if len(new_stream) == 0:
        return new_stream

    def _get_group_key(tr):
        sta = (getattr(tr.stats, "station", "") or "").strip()
        loc = (getattr(tr.stats, "location", "") or "").strip()
        cha = (getattr(tr.stats, "channel", "") or "").strip().upper()
        if len(cha) >= 2 and cha[-1] in "ZNE123RT":
            chan_prefix = cha[:-1]
        elif len(cha) == 1 and cha in "ZNE123RT":
            chan_prefix = ""
        else:
            chan_prefix = cha[:2] if len(cha) >= 2 else cha
        return (sta, loc, chan_prefix)

    groups = defaultdict(list)
    for tr in new_stream:
        base_key = _get_group_key(tr)
        st_time = getattr(tr.stats, "starttime", None)

        matched_cluster = None
        for (b_key, cluster_idx), tr_list in groups.items():
            if b_key == base_key and tr_list and st_time is not None:
                c_start = min(t.stats.starttime for t in tr_list)
                c_end = max(t.stats.endtime for t in tr_list)
                if abs(float(st_time - c_start)) < 30.0 or (c_start <= st_time <= c_end):
                    matched_cluster = (b_key, cluster_idx)
                    break

        if matched_cluster is not None:
            groups[matched_cluster].append(tr)
        else:
            cluster_idx = sum(1 for (b, _) in groups if b == base_key)
            groups[(base_key, cluster_idx)].append(tr)

    for (base_key, cluster_idx), tr_list in groups.items():
        group_max = 0.0
        for tr in tr_list:
            if tr.data is not None and len(tr.data) > 0:
                d = tr.data[np.isfinite(tr.data)]
                if d.size > 0:
                    trace_max = float(np.max(np.abs(d)))
                    group_max = max(group_max, trace_max)

        if not np.isfinite(group_max) or group_max <= 0:
            group_max = 1.0

        for tr in tr_list:
            if tr.data is not None and len(tr.data) > 0:
                tr.data = tr.data.astype(np.float64) / group_max

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
    Default: OS localized Desktop (e.g. ~/Scrivania/seismic_catalog.txt or ~/Desktop/seismic_catalog.txt).
    """
    if cfg is None:
        cfg = load_config()

    cat_path_str = str(cfg.get("defaults", {}).get("catalog_file", "")).strip()
    desktop_dir = get_system_desktop_dir()

    if not cat_path_str:
        target = desktop_dir / "seismic_catalog.txt"
    else:
        norm = cat_path_str.replace("\\", "/").rstrip("/")
        # If user has the legacy hardcoded default "~/Desktop/seismic_catalog.txt"
        # but the localized desktop is different (e.g. ~/Scrivania), redirect to localized desktop
        if norm in ("~/desktop/seismic_catalog.txt", "~/Desktop/seismic_catalog.txt", "seismic_catalog.txt"):
            target = desktop_dir / "seismic_catalog.txt"
        else:
            target = Path(os.path.expanduser(os.path.expandvars(cat_path_str)))

    # Seamless migration: if a catalog already exists at ~/Desktop/seismic_catalog.txt
    # but the localized desktop is different (e.g. ~/Scrivania/seismic_catalog.txt) and does not exist yet,
    # copy the existing catalog to the real desktop so no user data is lost.
    legacy_path = Path.home() / "Desktop" / "seismic_catalog.txt"
    if legacy_path.exists() and target != legacy_path and not target.exists():
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(legacy_path, target)
        except Exception:  # noqa: BLE001, S110
            pass

    return target


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
                parent_name = next(iter(parents))
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
            except Exception:  # noqa: BLE001
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
        except Exception:  # noqa: BLE001, S110
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
            except Exception:  # noqa: BLE001, S110
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
