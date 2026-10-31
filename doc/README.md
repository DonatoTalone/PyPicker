# PyPicker Documentation

![PyPicker Logo](./icon/PyPicker_logo_dark.png)

Welcome to the comprehensive documentation for **PyPicker**, a desktop application for seismic waveform visualization, spectral and time-frequency analysis, manual arrival picking, and hypocentral earthquake location.

![PyPicker Interactive Demonstration](./images/PyPicker_demo.gif)

🎬 *Full-resolution video available: [PyPicker_use.mp4](./images/PyPicker_use.mp4)*

---

## Documentation Sections

1. [**Installation Guide**](./installation.md)
   - Precompiled standalone binaries (Linux, Windows, macOS).
   - System packages (Debian/Ubuntu, Fedora/RHEL, Arch Linux).
   - Installing from source with Python virtual environments (`pip install -e .`).
   - Platform-specific notes and system requirements.

2. [**Configuration & Preferences**](./configuration.md)
   - Configuration folder structure (`config/` and user directory `~/.config/PyPicker/`).
   - Customizing keyboard shortcuts and color schemes.
   - Default filter parameters, velocity model, and picking modes.
   - User customization routines and fallback mechanisms.

3. [**Waveform Analysis & Visualization**](./waveform_analysis.md)
   - Supported waveform data formats (SAC, MiniSEED, etc.).
   - Display modes: Single Station, All Stations, and Focus Mode.
   - Preprocessing: demeaning, linear detrending, station normalization, and filtering.
   - Frequency spectrum analysis (linear and logarithmic scaling).
   - Time-frequency Morlet scalograms in Focus Mode.

4. [**Arrival Picking Guide**](./picking_guide.md)
   - Placing P, S, and custom phase picks (mouse interaction and quick keys `1` / `2`).
   - Setting time uncertainty intervals, first-motion polarity, and onset clarity.
   - Editing and reviewing picks in the interactive pick table.
   - Pick import and export formats (CSV, QuakeML, SeisGram2K).
   - Writing and updating SAC header markers (`a`, `ka`, `f`, `t0`–`t9`).

5. [**Plugin System & Architecture**](./plugin_system.md)
   - Extensibility model and dual-directory layout (`config/plugins/` and `~/.config/PyPicker/plugins/`).
   - Module resolution, dynamic `sys.path` injection, and packaging.
   - Accessing waveforms, picks, SAC headers, and UI widgets from plugins.
   - Step-by-step tutorial: developing and registering a new plugin.
   - Overview of integrated plugins (Hypo71 and Geographic Map).

6. [**Hypocentral Earthquake Location (Hypo71)**](./hypo71_localization.md)
   - Principles of Geiger's iterative linearization method.
   - 1D crustal velocity model specification (`velocity_model.json`).
   - Strict kinematic coherence between Hypo71 and ObsPy TauP theoretical ray tracer.
   - In-depth solver parameters: **Trial Depth ($Z_{TR}$)**, why it is a starting point and not a depth step.
   - Running locations with `hypo71py` (shortcut `L`).
   - Location metrics: Hypocenter, Origin Time, RMS, ERH, ERZ, and statistical quality code (QSD).
   - Detailed phase residuals table and station statistics.
   - Safe output management: saving to `h71_localized/` without touching original files.
   - Scientific references and citations (`hypo71py` and HYPO71).

7. [**Earthquake Focal Mechanism (FOCMEC)**](./focmec_focal_mechanism.md)
   - Double-couple point-source theory and Aki & Richards convention.
   - P-wave radiation pattern and first-motion polarities on the focal sphere.
   - Systematic grid search over Strike, Dip, and Rake (Snoke, 1984, 2003).
   - Equal-area (Schmidt) stereographic beachball projection with station polarities.
   - Uncertainty representation via acceptable solution ensemble (SurfQuake `--all_solutions`).
   - Principal stress axes (P, T, B) and Frohlich ternary tectonic classification.
   - Complete CSV report export and standard FOCMEC `.inp` interoperability.
   - Shortcut `K` and seamless handoff from Hypo71 dialog.

8. [**Geographic Map & Network Visualization**](./geographic_map.md)
   - Cartopy projection, national borders, coastlines, oceans, and lakes.
   - Digital Elevation Model (DEM) with shaded relief and adjustable transparency.
   - FDSN station inventory client (default INGV) and local XML caching.
   - Distinct visualization for background network stations vs. loaded picker stations.
   - Automatic coordinate recovery for traces missing SAC geographic headers.
   - Dynamic epicenter tracking and real-time synchronization with Hypo71 (shortcut `M`).

9. [**Building & Release Automation**](./building_and_release.md)
   - Creating standalone executables using PyInstaller (`PyPicker.spec`).
   - Packaging configuration files and pure-Python plugins.
   - Automated GitHub Actions release pipeline across Linux, Windows, and macOS.
