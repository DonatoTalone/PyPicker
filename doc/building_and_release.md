# Building Standalone Executables & Release Automation

PyPicker uses **PyInstaller** to package the Python runtime, Qt6 libraries, ObsPy scientific modules, and the configuration directory into self-contained standalone executables and application bundles.

---

## 1. Local Build with PyInstaller

### Setup
Ensure you have activated your virtual environment with all dependencies installed:

```bash
source .venv/bin/activate
python -m pip install pyinstaller
```

### Running the Build
Run PyInstaller against the project specification file [`PyPicker.spec`](../PyPicker.spec):

```bash
python -m PyInstaller --clean --noconfirm PyPicker.spec
```

### Build Artifacts
Outputs are placed in the `dist/` directory:
- **Linux**: Single-file executable `dist/PyPicker`.
- **Windows**: Single-file executable `dist/PyPicker.exe`.
- **macOS**: Application bundle `dist/PyPicker.app`.

---

## 2. Specification File Architecture (`PyPicker.spec`)

The specification file is carefully configured to handle complex dependencies:
- **`datas`**:
  - `('config', 'config')`: Embeds default configuration files, velocity model, and pure-Python plugins.
  - `('doc', 'doc')`: Embeds comprehensive documentation, screenshots (`images/`), and application icons (`icon/`).
  - `('picker_utils_qt.py', '.')`: Distributes utilities module.
  - ObsPy `RELEASE-VERSION` and package data.
- **`icon`**:
  - `doc/icon/PyPicker.ico`: High-resolution multi-size Windows icon embedded directly in the `.exe`.
  - `doc/icon/PyPicker.icns`: Native macOS icon bundle embedded in `PyPicker.app`.
- **`hiddenimports`**:
  - `pandas`, `lxml`, `scipy.signal`, `obspy.taup`, `obspy.imaging`, `config.plugins.hypo71_plugin`, etc.
- **macOS BUNDLE**:
  - Configures `info_plist` with identifier `com.donatotalone.pypicker` and creates the `.app` bundle structure without console windows.

---

## 3. GitHub Actions Release Pipeline

The repository includes a multi-platform release workflow in [`.github/workflows/release.yml`](../.github/workflows/release.yml):
- **Triggers**: Automatically runs whenever a Git tag matching `v*` (e.g. `v2.0.0`) is pushed to the repository.
- **Matrix OS**:
  - `ubuntu-latest` (Linux x86_64)
  - `windows-latest` (Windows x64)
  - `macos-latest` (macOS Apple Silicon arm64)
  - `macos-13` (macOS Intel x86_64)
- **Artifacts Generated**:
  - Linux: ZIP archive, plus native Debian/Ubuntu (`.deb`), Fedora/RHEL (`.rpm`), and Arch Linux (`.pkg.tar.zst`) packages containing `/usr/bin/pypicker`, `/usr/share/applications/pypicker.desktop`, and hicolor scalable/256x256 app icons.
  - Windows: ZIP archive with `PyPicker.exe` with embedded `.ico`.
  - macOS: ZIP archives containing `PyPicker.app` with native `.icns` bundle.
- **Publication**: Automatically uploads all release packages directly as downloadable assets on the GitHub Release page.
