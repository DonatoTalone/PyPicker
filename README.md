# PyPicker - Seismic Waveform Picker

A simple Python-based GUI for seismic waveform visualization, frequency analysis, and manual arrival picking. It utilizes **PyQt6** for the interface, **PyQtGraph** for high-performance plotting, and **ObsPy** for seismic data handling.

## Features
- **Waveform Visualization:** Load SAC, MSEED, and other formats supported by ObsPy.
- **Spectrum Analysis:** Toggle between time-domain waveforms and frequency-domain spectra (Log/Lin scales).
- **Signal Processing:** Integrated demeaning, detrending, and filtering (HighPass, LowPass, BandPass).
- **Interactive Picking:** 
  - Single-click to pick arrival times.
  - Drag vertically while picking to define uncertainty.
  - Supports P, S, and custom phase labels.
- **Data Export:** Save picks back into SAC headers or export a picking summary to CSV.
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

  - Click on the trace to set a pick.

  - While holding/moving the mouse vertically, the purple shaded area (uncertainty) will expand/contract.

  - Release or click again to finalize.

4. Navigation: Use the sidebar or keyboard shortcuts (default: A for previous, D for next) to cycle through stations.

5. Save: Use "Save as SAC" to modify the original file headers or "Export CSV" for a text summary.

## Default Shortcuts

Can be modified in config.json:

  - A / D: Previous / Next Station

  - P: Select P phase

  - S: Select S phase

  - R: Reset Zoom

  - F: Toggle BandPass filter