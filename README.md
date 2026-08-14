# PyPicker - Seismic Waveform Picker

A simple Python-based GUI for seismic waveform visualization, frequency analysis, and manual arrival picking. It utilizes **PyQt6** for the interface, **PyQtGraph** for high-performance plotting, and **ObsPy** for seismic data handling.
It is partially written by Gemini 3.6 Flash (High) Antigravity.

## Features
- **Waveform Visualization:** Load SAC, MSEED, and other formats supported by ObsPy.
- **Spectrum Analysis:** Toggle between time-domain waveforms and frequency-domain spectra (Log/Lin scales).
- **Signal Processing:** Integrated demeaning, detrending, and filtering (HighPass, LowPass, BandPass).
- **Interactive Picking:** 
  - Single-click to pick arrival times.
  - Drag vertically while picking to define uncertainty.
  - Supports P, S, and custom phase labels.
  - Set Polarity (Up/Down) and Onset (Emergent/Impulsive) attributes.
  - Two picking modes ("Sidebar" or "Popup") to streamline metadata entry.
- **Station Reordering:** Dynamically sort stations by Epicentral Distance or earliest P/S arrival.
- **Theoretical Arrivals:** Automatically calculate and plot theoretical travel times (P and S) using `obspy.taup` and the velocity model defined in `config.json` (e.g. `iasp91`).
- **Data Export & Import:** Save picks back into SAC headers, export a picking summary to CSV, or Import/Export fully compliant **QuakeML** files.
- **Customizable:** Use `config.json` to define keyboard shortcuts and UI colors.

## Project Structure
- `seismic_picker_qt.py`: The main application script (GUI and logic).
- `picker_utils_qt.py`: Utility functions for signal processing, file I/O, and SAC header management.
- `config.json`: Configuration file for shortcuts and visual themes.
- `requirements.txt`: List of Python dependencies.

## License
The code is released under [GNU General Public License](./LICENSE)

## Installation

### 1. Create a Virtual Environment
It is recommended to use a virtual environment to avoid dependency conflicts.

```bash
# Create environment
python -m venv pypicker

# Activate (Windows)
pypicker\Scripts\activate

# Activate (macOS/Linux)
source pypicker/bin/activate
```

### 2. Install Dependencies

Use the provided requirements.txt file:

```bash
pip install -r requirements.txt
```

Note: The requirements include PyQt6, Obspy, pyqtgraph, and numpy.

## How to Use

1. Run the application:

```bash
python seismic_picker_qt.py
```

2. Open Data: Click "Open Waveforms" and select your seismic files.

3. Pick Arrivals:

  - Ensure "Waveform" mode is active.

  - **Option 1 (Mouse):** Click on the trace to set a pick.

  - **Option 2 (Keyboard):** Hover your mouse over the trace and press `1` (for P phase) or `2` (for S phase).

  - While holding/moving the mouse vertically, the purple shaded area (uncertainty) will expand/contract.

  - Release or click again to finalize. If "Popup" picking mode is active, a dialog will ask you to confirm Phase, Polarity, and Onset.

4. Navigation & View: 
  - Use the sidebar or keyboard shortcuts (default: A for previous, D for next) to cycle through stations.

5. Save: Use "Save as SAC" to modify the original file headers or "Export Picks" to save the picks to various formats file. Use "Import Picks" to load picks from existing files (e.g. CSV, QuakeML).

## Default Shortcuts

Can be modified in config.json:

  - 1 / 2: Quick pick P phase / S phase at current mouse position

  - A / D: Previous / Next Station

  - P: Select P phase

  - S: Select S phase

  - R: Reset Zoom

  - F: Toggle BandPass filter

  - C: Select Custom phase

  - Q: Rotate/Cycle between P and S phases

  - Ctrl+S: Save picks to SAC headers

  - Ctrl+E: Export picks to CSV/QuakeML