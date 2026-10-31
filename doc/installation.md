# Installation Guide

PyPicker can be run from precompiled standalone binaries, system packages, or installed from source within a Python virtual environment.

---

## 1. Precompiled Packages

Binaries are automatically built for every tagged release on [GitHub Releases](https://github.com/DonatoTalone/PyPicker/releases).

### Linux System Packages
Packages are generated for major package managers:

```bash
# Debian / Ubuntu / Linux Mint (.deb)
sudo dpkg -i ./pypicker-<version>-debian-ubuntu.deb

# Fedora / RHEL / CentOS (.rpm)
sudo dnf install ./pypicker-<version>-fedora-rhel.rpm

# Arch Linux / Manjaro (.pkg.tar.zst)
sudo pacman -U ./pypicker-<version>-archlinux.pkg.tar.zst
```

The system package installs the executable to `/usr/bin/pypicker`. Launch it from your terminal or desktop application menu:
```bash
pypicker
```

### Standalone Archives
If you do not want to install system-wide packages:

- **Linux (x86_64)**: Extract `PyPicker-Linux-x86_64.zip` and run `./PyPicker`. (Run `chmod +x PyPicker` if executable permissions were lost).
- **Windows (x64)**: Extract `PyPicker-Windows-x64.zip` and launch `PyPicker.exe`.
- **macOS**: Extract `PyPicker-macOS-arm64.zip` (Apple Silicon) or `PyPicker-macOS-x86_64.zip` (Intel) and open `PyPicker.app`.

---

## 2. Installation from Source

Running from source is recommended for development, testing the latest `dev` branch, or customizing code routines.

### Requirements
- **Python**: 3.10, 3.11, or 3.12 (Python 3.12 recommended).
- **Git**

### Step-by-Step Setup

1. **Clone the repository**:
   ```bash
   git clone --branch dev https://github.com/DonatoTalone/PyPicker.git
   cd PyPicker
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python -m venv .venv
   ```

   Activate according to your platform:
   - **Linux / macOS (Bash/Zsh)**:
     ```bash
     source .venv/bin/activate
     ```
   - **Windows (Command Prompt)**:
     ```cmd
     .venv\Scripts\activate.bat
     ```
   - **Windows (PowerShell)**:
     ```powershell
     .venv\Scripts\Activate.ps1
     ```

3. **Install dependencies**:
   ```bash
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

4. **Install PyPicker in editable mode**:
   ```bash
   python -m pip install -e .
   ```

5. **Launch PyPicker**:
   Once installed, you can launch PyPicker from any directory by typing:
   ```bash
   pypicker
   ```
   Or execute the main script directly:
   ```bash
   python seismic_picker_qt.py
   ```

---

## 3. Core Dependencies

PyPicker relies on standard, battle-tested scientific Python libraries:

| Library | Version | Role |
| --- | --- | --- |
| `obspy` | $\ge 1.4.0$ | Seismic waveform parsing, SAC handling, travel-time ray tracing |
| `PyQt6` | $\ge 6.5.0$ | Qt6 graphical user interface and event loop |
| `pyqtgraph` | $\ge 0.13.0$ | High-performance interactive waveform and spectrum plotting |
| `numpy` | $\ge 1.22.0$ | Numerical calculations and array manipulations |
| `scipy` | $\ge 1.9.0$ | Signal processing, filtering, and Morlet wavelet transform |
| `matplotlib` | $\ge 3.5.0$ | Scientific colormaps and auxiliary plotting utilities |
| `pandas` | $\ge 2.0.0$ | Tabular phase indexing and residuals handling in `hypo71py` |
