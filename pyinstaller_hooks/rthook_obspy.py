# PyInstaller runtime hook for ObsPy
# Fixes KeyError: 'viridis' caused by inspect.getfile inside frozen binaries.
import inspect
import os
import sys

# 1. Patch inspect.getfile for ObsPy in frozen executables (prevent re-wrapping)
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

# 2. Pre-populate obspy.imaging.cm if loaded or when loaded
try:
    import obspy.imaging.cm as obspy_cm

    if "viridis" not in obspy_cm.__dict__:
        from matplotlib import colormaps

        obspy_cm.__dict__["viridis"] = colormaps["viridis"]
        obspy_cm.__dict__["viridis_r"] = colormaps["viridis"].reversed()
        obspy_cm.__dict__["obspy_sequential"] = colormaps["viridis"]
        obspy_cm.__dict__["obspy_sequential_r"] = colormaps["viridis"].reversed()
        if "pqlx" not in obspy_cm.__dict__ and "gist_rainbow" in colormaps:
            obspy_cm.__dict__["pqlx"] = colormaps["gist_rainbow"]
except Exception:
    pass
