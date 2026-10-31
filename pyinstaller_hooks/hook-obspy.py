# hook-obspy.py
from PyInstaller.utils.hooks import (
    collect_dynamic_libs,
    collect_data_files,
    collect_submodules,
    get_package_paths,
)

import os

# Percorsi base del pacchetto obspy
(_, obspy_root) = get_package_paths("obspy")

# Librerie dinamiche (.so) usate da obspy
binaries = collect_dynamic_libs("obspy")

# Dati (es. entry_points, plugin, ecc.)
datas = collect_data_files("obspy")

# Molti plugin stanno in obspy.io.*
hiddenimports = collect_submodules("obspy.io") + collect_submodules("obspy.signal") + collect_submodules("obspy.imaging")

