# -*- mode: python ; coding: utf-8 -*-
import os
import sys
import obspy
os.environ["QT_API"] = "pyqt6"

from PyInstaller.utils.hooks import collect_all, copy_metadata

datas = []
binaries = []
hiddenimports = []

for pkg in ['obspy', 'matplotlib', 'pyqtgraph', 'scipy', 'pandas', 'cartopy', 'shapely', 'pyproj']:
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# Collect distribution metadata for dependencies so pkg_resources/importlib.metadata can find them
datas += copy_metadata("obspy", recursive=True)
pkgs_metadata = [
    'decorator', 'greenlet', 'requests', 'urllib3', 'certifi',
    'charset_normalizer', 'colorama', 'idna', 'lxml', 'numpy', 'scipy',
    'matplotlib', 'setuptools', 'packaging', 'pyqtgraph', 'pytz',
    'contourpy', 'cycler', 'fonttools', 'kiwisolver', 'pillow',
    'pyparsing', 'sqlalchemy', 'six', 'python-dateutil', 'PyQt6', 'pandas',
    'cartopy', 'shapely', 'pyproj', 'darkdetect'
]
for pkg in pkgs_metadata:
    try:
        datas += copy_metadata(pkg)
    except Exception:
        pass

hiddenimports += [
    'decorator', 'greenlet', 'requests', 'urllib3', 'lxml', 'lxml.etree',
    'obspy.signal', 'obspy.signal.filter', 'obspy.signal.invsim', 'obspy.signal.headers',
    'obspy.taup', 'obspy.imaging', 'obspy.imaging.cm', 'matplotlib.colormaps',
    'pandas', 'cartopy', 'shapely', 'pyproj', 'darkdetect',
    'config', 'config.plugins', 'config.plugins.hypo71_plugin', 'config.plugins.hypo71py', 'config.plugins.map_plugin',
    'config.plugins.focmec_plugin', 'config.plugins.focmecpy'
]

obspy_dir = os.path.dirname(obspy.__file__)
obspy_lib_dir = os.path.join(obspy_dir, 'lib')
if os.path.isdir(obspy_lib_dir):
    for fname in os.listdir(obspy_lib_dir):
        fpath = os.path.join(obspy_lib_dir, fname)
        if os.path.isfile(fpath):
            binaries.append((fpath, 'obspy/lib'))
            datas.append((fpath, 'obspy/lib'))

rel_ver = os.path.join(obspy_dir, 'RELEASE-VERSION')
if os.path.exists(rel_ver):
    datas.append((rel_ver, 'obspy'))
else:
    import tempfile
    tmp_rel_ver = os.path.join(tempfile.gettempdir(), 'RELEASE-VERSION')
    with open(tmp_rel_ver, 'w') as f:
        f.write(getattr(obspy, '__version__', '1.4.2') + '\n')
    datas.append((tmp_rel_ver, 'obspy'))

datas.append(('config', 'config'))
datas.append(('doc', 'doc'))
datas.append(('picker_utils_qt.py', '.'))

a = Analysis(
    ['seismic_picker_qt.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=['pyinstaller_hooks'],
    hooksconfig={},
    runtime_hooks=['pyinstaller_hooks/rthook_obspy.py'],
    excludes=['PyQt5', 'PySide2', 'PySide6', 'matplotlib.backends.backend_qt5agg'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='PyPicker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False if sys.platform == 'darwin' else True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False if sys.platform == 'darwin' else True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='doc/icon/PyPicker.ico' if os.path.exists('doc/icon/PyPicker.ico') else None,
)

if sys.platform == 'darwin':
    app_version = '3.0.1'
    try:
        with open('picker_utils_qt.py', 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('__version__'):
                    app_version = line.split('=')[1].strip().strip('"').strip("'")
                    break
    except Exception:
        pass

    app = BUNDLE(
        exe,
        name='PyPicker.app',
        icon='doc/icon/PyPicker.icns' if os.path.exists('doc/icon/PyPicker.icns') else None,
        bundle_identifier='com.donatotalone.pypicker',
        info_plist={
            'CFBundleName': 'PyPicker',
            'CFBundleDisplayName': 'PyPicker',
            'CFBundleGetInfoString': 'PyPicker - Seismic Waveform Picker',
            'CFBundleIdentifier': 'com.donatotalone.pypicker',
            'CFBundleVersion': app_version,
            'CFBundleShortVersionString': app_version,
            'NSHighResolutionCapable': True,
            'NSRequiresAquaSystemAppearance': False,
        },
    )
