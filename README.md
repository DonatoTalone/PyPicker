# PyPicker - Seismic Waveform Picker

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21976300.svg)](https://doi.org/10.5281/zenodo.21976300)

A Python desktop application for seismic waveform visualization, frequency and time-frequency analysis, and manual arrival picking. PyPicker uses PyQt6 for the interface, PyQtGraph for plotting, and ObsPy for seismic data handling.

This README describes the `dev` branch. Published release binaries may not yet include all features documented here.

## Features

- Load SAC, MiniSEED, and other waveform formats readable by ObsPy. Add traces to an existing session or replace it; duplicate traces are skipped when adding data.
- Display a single station, all stations, or a detailed Focus Mode view.
- Analyze amplitude spectra with linear or logarithmic frequency and amplitude axes.
- Compare raw and processed waveforms with Morlet scalograms in Focus Mode.
- Apply mean removal, linear detrending, station-based amplitude normalization, and high-pass, low-pass, or band-pass filtering.
- Pick P, S, and custom phases; assign time uncertainty, polarity, and onset using Sidebar or Popup picking mode.
- View and edit picks in a table, with corresponding plot updates.
- Sort stations alphabetically, by epicentral distance, or by earliest picked arrival.
- Calculate theoretical P/S arrivals with ObsPy TauP when the required SAC event and station metadata are available.
- Import picks from CSV, QuakeML, and SeisGram2K `.pick` files; export to CSV or QuakeML. Read existing picks from SAC headers and save picks back to SAC.
- Customize shortcuts and colors through a persistent per-user configuration file. Choose System, Dark, or Light appearance in the interface.

## Installation

### Precompiled packages

Download an asset from [GitHub Releases](https://github.com/DonatoTalone/PyPicker/releases). The release workflow builds Linux x86_64 and Windows x64 binaries. It does not currently build macOS packages.

Use the actual version and filename of the downloaded package:

```bash
# Debian / Ubuntu / Mint
sudo dpkg -i ./pypicker-<version>-debian-ubuntu.deb

# Fedora / RHEL
sudo dnf install ./pypicker-<version>-fedora-rhel.rpm

# Arch Linux / Manjaro
sudo pacman -U ./pypicker-<version>-archlinux.pkg.tar.zst
```

The Linux system packages install the executable as `/usr/bin/pypicker`. Start it with:

```bash
pypicker
```

Alternatively:

- Linux standalone: extract `PyPicker-Linux-x86_64.zip` and run `./PyPicker`. Set executable permission with `chmod +x PyPicker` if needed.
- Windows standalone: extract `PyPicker-Windows-x64.zip` and run `PyPicker.exe`.

For the latest development features, run the `dev` branch from source or build it locally. A successful package build alone does not establish compatibility with every distribution.

### Run the development branch from source

The release workflow uses Python 3.11. Use a virtual environment and install the pinned dependencies in `requirements.txt`.

```bash
git clone --branch dev https://github.com/DonatoTalone/PyPicker.git
cd PyPicker
python -m venv .venv
```

Activate the environment using the command for your shell:

```bash
# Linux / macOS
source .venv/bin/activate

# Windows Command Prompt
.venv\Scripts\activate.bat

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Then install dependencies and start the application:

```bash
python -m pip install -r requirements.txt
python seismic_picker_qt.py
```

## Configuration

### Location and first launch

The `config.json` distributed with the application provides the defaults. On first launch, PyPicker creates a user configuration directory and copies those defaults into a new `config.json`. Existing user files are not overwritten on subsequent launches.

PyPicker uses Qt's `QStandardPaths.GenericConfigLocation` and appends a `PyPicker` subdirectory. Typical locations are:

| System | User configuration file |
| --- | --- |
| Linux | `~/.config/PyPicker/config.json` |
| Windows | `%LOCALAPPDATA%\PyPicker\config.json` |
| macOS | `~/Library/Preferences/PyPicker/config.json` |

System settings can change these locations; for example, Linux can use `$XDG_CONFIG_HOME/PyPicker/config.json`. Use the Open Configuration button in the right sidebar to open the actual directory. The button opens the folder, not an in-app settings editor.

Edit the user file and restart PyPicker to apply changes. Configuration loading does not depend on the directory from which the application is launched. In a packaged application, the user file remains outside PyInstaller's temporary extraction directory.

### Defaults and user overrides

User settings are recursively merged with the distributed defaults. Missing keys use the bundled values, while user values take precedence. Newly introduced defaults can therefore be used without overwriting existing preferences; they are not automatically written into the existing user file.

The configuration includes:

- `shortcuts`: key bindings listed below.
- `colors`: component colors (`Z`, `N`, `E`, `other`), pick-line color, and uncertainty-area transparency.
- `defaults.velocity_model`: TauP model, such as `iasp91`.
- `defaults.show_theoretical_arrivals`: initial state of Show Arrivals.
- `defaults.picking_mode`: `Popup` or `Sidebar`.
- `defaults.scalogram_duration`: initial Morlet duration factor; optional, with a fallback of `1.0`.

Current limitations:

- The initial theme is System. A JSON theme preference is not currently implemented, and changing the theme in the GUI does not save a preference.
- The GUI currently initializes the filter to None and the frequency controls to 1.0 and 20.0 Hz. Although `low_f`, `high_f`, and `filter_type` are present in the distributed JSON, they do not currently initialize those controls.
- Invalid or unreadable configuration files produce a startup error rather than silently reverting to defaults. Back up the user file before editing it. To reset preferences, close PyPicker and rename or remove the user `config.json`; it will be recreated at the next launch.

## Usage

### Load and navigate waveforms

1. Click Open Waveforms and select one or more files. Example datasets are available under `examples/`.
2. If a session is already open, choose Add to session, Overwrite, or Cancel. Overwrite replaces the current session and its pick list.
3. Choose Single Station or All Stations and use Waveform or Spectrum display.
4. Navigate stations with the selector, arrow buttons, or `A` / `D`. Use Sort Stations to change their order. Distance sorting requires SAC coordinates; arrival sorting uses the earliest pick available for each station.

### Focus Mode and scalograms

Select Focus Mode to inspect the current station with linked time axes across three panels per displayed block:

1. Raw waveform.
2. Processed waveform, labeled Filtered.
3. Morlet scalogram calculated from the raw waveform, with logarithmically spaced frequencies from 1 to 30 Hz and power expressed in dB.

Entering Focus Mode selects the band-pass filter. Adjust the frequency controls and processing checkboxes as needed. The scalogram continues to use the raw trace, not the filtered waveform.

The Scalogram duration control adjusts the Morlet wavelet duration factor, not the recording length or visible time window. It is enabled only in Focus Mode; the Waveform/Spectrum and Spectrum Scale controls are disabled there.

Focus Mode groups traces by source file. A file containing multiple components contributes one selected component; separate component files contribute separate blocks. It does not necessarily display every component from a multi-component file. Existing picks and theoretical arrivals are also drawn on the scalogram.

### Pick and edit arrivals

- Use a time-domain waveform view to place picks with the mouse.
- Alternatively, hover over a trace and press `1` for a P pick or `2` for an S pick.
- Move vertically during the active pick operation to adjust the shaded uncertainty interval, then finalize the pick.
- In Sidebar mode, use the phase, polarity, and onset controls. In Popup mode, confirm these attributes in the pick-details dialog.
- Edit pick values in the table to update their plotted representation.

Normalization uses a shared maximum absolute amplitude across a station's components, rather than independently scaling each component. The normalization path also removes the mean and linear trend. Processing operates on a copy of the loaded stream.

### Theoretical arrivals

Enable Show Arrivals to display theoretical P/S arrival markers. Calculation requires valid SAC station/event coordinates (`stla`, `stlo`, `evla`, `evlo`), event depth (`evdp`), and origin marker (`o`). The origin time is derived using the trace start time and SAC `b`/`o` values. Files without the required metadata will not receive theoretical markers.

### Import, export, and SAC writes

- Import Picks loads CSV, QuakeML, or SeisGram2K `.pick` data.
- Export Picks writes CSV or QuakeML. CSV output uses semicolons and includes station, channel, phase, UTC time, uncertainty in seconds, polarity, and onset.
- Save as SAC writes pick information to the loaded files using SAC output. It is not a separate Save As dialog.

Keep backups of input files before using SAC write operations. The save routine clears existing pick markers before writing the current picks; deleting a pick can also write changes back to its source file. CSV or QuakeML export is preferable when you want a separate pick file without invoking SAC writes.

## Default shortcuts

Edit `shortcuts` in the user configuration file and restart the application to change these bindings.

| Shortcut | Action |
| --- | --- |
| `1` / `2` | Quick P / S pick at the mouse position |
| `A` / `D` | Previous / next station |
| `P` / `S` | Select P / S phase |
| `C` | Select custom phase |
| `Q` | Cycle between P and S |
| `R` | Reset zoom |
| `F` | Toggle filtering off, or enable band-pass when off |
| `Ctrl+S` | Save picks to SAC |
| `Ctrl+E` | Open pick export |

## Build a standalone executable

From the repository root, with the virtual environment active:

```bash
python -m pip install pyinstaller
python -m PyInstaller --clean --noconfirm PyPicker.spec
```

The spec includes the distributed `config.json`, scientific packages, and distribution metadata required by the application. Output is `dist/PyPicker` on Linux or `dist/PyPicker.exe` on Windows. Build and test on each target platform.

The GitHub Actions release workflow runs for tags matching `v*`. It uses Python 3.11 and generates Linux ZIP, DEB, RPM, and Arch packages, plus a Windows ZIP. The workflow's platform coverage should not be interpreted as verification of all runtime features on every target system.

## Project structure

```text
seismic_picker_qt.py       GUI, session handling, plotting, and picking
picker_utils_qt.py         Configuration, processing, scalograms, and pick I/O
config.json               Distributed configuration defaults
requirements.txt          Pinned Python dependencies
PyPicker.spec             PyInstaller build definition
.github/workflows/        Release automation
examples/                 Example waveform datasets
CITATION.cff              Citation metadata
LICENSE                   License text
```

## Citation and development

Use the DOI badge above or the repository's `CITATION.cff` for citation information.

Development attribution retained from the original README: It is partially written by Gemini 3.6 Flash (High) Antigravity.

## License

The code is released under the [GNU General Public License](./LICENSE).
