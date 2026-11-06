# hook-obspy.py
import os
from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
    copy_metadata,
    get_package_paths,
)

# Percorsi base del pacchetto obspy
(_, obspy_root) = get_package_paths("obspy")

# Librerie dinamiche standard (.so, .dll, .dylib) usate da obspy
binaries = collect_dynamic_libs("obspy")

# Raccogli esplicitamente tutti i binari C in obspy/lib (mseed, segy, gse2, signal, tau, etc.)
obspy_lib_dir = os.path.join(obspy_root, "lib")
datas = collect_data_files("obspy")
if os.path.isdir(obspy_lib_dir):
    for fname in os.listdir(obspy_lib_dir):
        fpath = os.path.join(obspy_lib_dir, fname)
        if os.path.isfile(fpath):
            binaries.append((fpath, "obspy/lib"))
            datas.append((fpath, "obspy/lib"))

# Metadati di distribuzione per entry points
try:
    datas += copy_metadata("obspy", recursive=True)
except Exception:
    pass

# Sottomoduli critici
hiddenimports = (
    collect_submodules("obspy.io")
    + collect_submodules("obspy.signal")
    + collect_submodules("obspy.imaging")
    + collect_submodules("obspy.core")
    + collect_submodules("obspy.taup")
)

