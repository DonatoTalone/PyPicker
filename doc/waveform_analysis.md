# Waveform Analysis & Visualization

PyPicker provides high-performance interactive waveform plotting and frequency analysis for single stations, network arrays, and multi-component records.

---

## 1. Loading & Managing Waveforms

### Supported File Formats
Thanks to ObsPy, PyPicker natively supports any waveform format ObsPy can read, including:
- **SAC** (Seismic Analysis Code, binary and alphanumeric)
- **MiniSEED** and full SEED
- **GSE2 / SEG-Y / SU**

### Loading Files
1. Click **Open Waveforms** in the left sidebar or select **File → Open Waveforms...** (`Ctrl+O`).
2. Select one or multiple waveform files.
3. If an existing session is already open:
   - **Add to session**: Appends new traces to the current session (skipping identical duplicates).
   - **Overwrite**: Clears the current session and pick list, replacing it with the newly selected files.
   - **Cancel**: Aborts loading.

---

## 2. Display Modes

### Single Station Mode
- Displays all components (e.g. Z, N, E) for the currently selected station.
- Plots are stacked vertically and share a synchronized time axis.
- Use the **Station** dropdown or the `A` (previous) and `D` (next) keys to navigate between stations.

### All Stations Mode
- Displays waveforms from all loaded stations simultaneously.
- Useful for an overall network view, record section inspection, and identifying regional event arrivals.

### Focus Mode & Morlet Scalograms
Focus Mode provides an in-depth three-panel view for the current station:
1. **Raw Waveform**: Unfiltered original recording with original amplitude scaling.
2. **Processed Waveform**: Filtered, demeaned, and detrended trace (labeled *Filtered*).
3. **Morlet Scalogram**: Continuous wavelet transform computed from the raw trace:
   - Calculated with logarithmically spaced frequency bins (from 1 to 30 Hz).
   - The **Scalogram Duration** factor allows tuning the Morlet wavelet time-frequency resolution (default: `1.0`).
   - Time axes across all three panels remain strictly synchronized during pan and zoom operations.
   - Existing picks and theoretical arrival lines are plotted across all panels.

---

## 3. Waveform Preprocessing

Preprocessing is applied in real time to in-memory copies, preserving raw trace integrity:

- **Demean**: Removes trace mean offset ($\bar{x}$).
- **Detrend**: Removes linear trends.
- **Normalize**: Scales components based on the shared maximum absolute amplitude across all channels of that station, maintaining accurate relative component amplitudes.
- **Filtering**:
  - **None**: Displays unfiltered data (with optional cosine tapering).
  - **BandPass (f1 and f2)**: Zero-phase Butterworth filter between low threshold `f1` and high threshold `f2`.
  - **LowPass (f2)**: Butterworth low-pass filter below `f2`.
  - **HighPass (f1)**: Butterworth high-pass filter above `f1`.
  - Press **`F`** to quickly toggle the filter on and off.

---

## 4. Frequency Spectrum Analysis

Toggle between **Waveform** and **Spectrum** display using the radio buttons in the left sidebar:
- Computes amplitude spectra via FFT for the visible or loaded window.
- **Spectrum Scale**:
  - **Linear / Linear**: Linear frequency (Hz) vs. linear amplitude.
  - **Log / Log**: Logarithmic frequency vs. logarithmic amplitude (Bode plot style).
  - **Log / Linear**: Logarithmic frequency vs. linear amplitude.
