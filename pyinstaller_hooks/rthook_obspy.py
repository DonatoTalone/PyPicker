# PyInstaller runtime hook for ObsPy
# Fixes:
# 1. KeyError: 'viridis' in obspy.imaging.cm
# 2. FileNotFoundError / Git crash on obspy/RELEASE-VERSION
# 3. Waveform format detection (populating ENTRY_POINTS and resolving plugins without strict requires)
# 4. Loading C shared libraries in obspy/lib (mseed, segy, gse2, signal, tau, gcf, evresp)

import ctypes
import importlib
import inspect
import io
import os
import subprocess
import sys
from pathlib import Path

# --- 1. Intercept io.open and builtins.open for RELEASE-VERSION ---
_real_io_open = io.open
_real_builtins_open = open


def _safe_obspy_open(file, *args, **kwargs):
    if isinstance(file, (str, bytes, os.PathLike)) and "RELEASE-VERSION" in str(file):
        mode = args[0] if args else kwargs.get("mode", "r")
        if any(c in mode for c in ("w", "a", "+")):
            return io.BytesIO() if "b" in mode else io.StringIO()
        content = b"1.4.2\n" if "b" in mode else "1.4.2\n"
        return io.BytesIO(content) if "b" in mode else io.StringIO(content)
    return _real_io_open(file, *args, **kwargs)


io.open = _safe_obspy_open


def _safe_builtins_open(file, *args, **kwargs):
    if isinstance(file, (str, bytes, os.PathLike)) and "RELEASE-VERSION" in str(file):
        mode = args[0] if args else kwargs.get("mode", "r")
        if any(c in mode for c in ("w", "a", "+")):
            return io.BytesIO() if "b" in mode else io.StringIO()
        content = b"1.4.2\n" if "b" in mode else "1.4.2\n"
        return io.BytesIO(content) if "b" in mode else io.StringIO(content)
    return _real_builtins_open(file, *args, **kwargs)


import builtins  # noqa: E402

builtins.open = _safe_builtins_open

# --- 2. Prevent ObsPy from querying Git for PyPicker repository version ---
_real_check_output = subprocess.check_output


def _safe_check_output(cmd, *args, **kwargs):
    if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "git":
        raise subprocess.CalledProcessError(1, cmd, output=b"")
    return _real_check_output(cmd, *args, **kwargs)


subprocess.check_output = _safe_check_output

# --- 3. Patch inspect.getfile for ObsPy in frozen executables (prevent re-wrapping) ---
if not getattr(inspect.getfile, "_is_obspy_patched", False):
    _real_getfile = inspect.getfile

    def _frozen_getfile(obj):
        filename = _real_getfile(obj)
        if getattr(sys, "frozen", False):
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass and isinstance(filename, str) and not os.path.exists(filename):
                idx = filename.find("obspy")
                if idx != -1:
                    cand = os.path.join(meipass, filename[idx:])
                    if os.path.exists(cand) or os.path.exists(os.path.dirname(cand)):
                        return cand
        return filename

    _frozen_getfile._is_obspy_patched = True
    inspect.getfile = _frozen_getfile

# --- 4. Patch pkg_resources EntryPoint.load to avoid DistributionNotFound failures ---
try:
    import pkg_resources

    _orig_ep_load = pkg_resources.EntryPoint.load

    def _safe_ep_load(self, *args, **kwargs):
        try:
            return self.resolve()
        except Exception:
            return _orig_ep_load(self, *args, **kwargs)

    pkg_resources.EntryPoint.load = _safe_ep_load

    _orig_load_ep = getattr(pkg_resources, "load_entry_point", None)

    def _safe_load_entry_point(dist, group, name):
        try:
            ep = pkg_resources.get_entry_info(dist, group, name)
            if ep is not None:
                return ep.resolve()
        except Exception:
            pass
        if _orig_load_ep:
            return _orig_load_ep(dist, group, name)
        raise ImportError(f"Cannot load entry point {group}:{name} from {dist}")

    pkg_resources.load_entry_point = _safe_load_entry_point
except Exception:
    pass

# --- 5. On Windows, register DLL directories for ctypes dependencies ---
if sys.platform.startswith("win") and getattr(sys, "frozen", False):
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass and hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(meipass)
            p_lib = os.path.join(meipass, "obspy", "lib")
            if os.path.exists(p_lib):
                os.add_dll_directory(p_lib)
        except Exception:
            pass

