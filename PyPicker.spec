# -*- mode: python ; coding: utf-8 -*-
import os
import obspy
os.environ["QT_API"] = "pyqt6"

from PyInstaller.utils.hooks import collect_all, copy_metadata

datas, binaries, hiddenimports = collect_all('obspy')

# Collect distribution metadata for dependencies so pkg_resources/importlib.metadata can find them
pkgs_metadata = [
    'obspy', 'decorator', 'greenlet', 'requests', 'urllib3', 'certifi',
    'charset_normalizer', 'colorama', 'idna', 'lxml', 'numpy', 'scipy',
    'matplotlib', 'setuptools', 'packaging', 'pyqtgraph', 'pytz',
    'contourpy', 'cycler', 'fonttools', 'kiwisolver', 'pillow',
    'pyparsing', 'sqlalchemy', 'six', 'python-dateutil', 'PyQt6'
]
for pkg in pkgs_metadata:
    try:
        datas += copy_metadata(pkg)
    except Exception:
        pass

hiddenimports += ['decorator', 'greenlet', 'requests', 'urllib3', 'lxml', 'lxml.etree']

obspy_dir = os.path.dirname(obspy.__file__)
rel_ver = os.path.join(obspy_dir, 'RELEASE-VERSION')
if os.path.exists(rel_ver):
    datas.append((rel_ver, 'obspy'))
else:
    import tempfile
    tmp_rel_ver = os.path.join(tempfile.gettempdir(), 'RELEASE-VERSION')
    with open(tmp_rel_ver, 'w') as f:
        f.write(getattr(obspy, '__version__', '1.4.2') + '\n')
    datas.append((tmp_rel_ver, 'obspy'))

datas.append(('config.json', '.'))

a = Analysis(
    ['seismic_picker_qt.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
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
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
