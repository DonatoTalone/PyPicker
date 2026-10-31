# Configuration & Preferences

PyPicker uses a user-centric configuration model designed to separate distributed defaults from user customizations.

---

## 1. Directory Structure and Synchronization

In the repository or application bundle, defaults are stored in the [`config/`](../config/) directory:

```text
config/
├── config.json              Default user preferences
├── velocity_model.json      1D crustal velocity model (Hypo71 and TauP)
├── picker_utils_qt.py       Reference routines for user extensions
└── plugins/                 Integrated third-party plugins (e.g. hypo71py)
```

### User Configuration Directory Location

On first launch, PyPicker creates a persistent configuration folder in the user's home directory (using Qt's `QStandardPaths.GenericConfigLocation`) and automatically synchronizes the entire `config/` tree into it.

Typical operating system locations:

| Operating System | Path |
| --- | --- |
| **Linux** | `~/.config/PyPicker/` (or `$XDG_CONFIG_HOME/PyPicker/`) |
| **Windows** | `%LOCALAPPDATA%\PyPicker\` |
| **macOS** | `~/Library/Preferences/PyPicker/` |

### Non-Destructive Merging

- Existing files in your user configuration directory are **never overwritten** automatically on subsequent launches.
- When new settings or keys are introduced in updates, PyPicker merges user settings with distributed defaults in memory. Missing keys fall back to defaults, while your customized keys take precedence.
- You can access this folder at any time by clicking **Open Configuration** in the right sidebar or selecting **Plugins → Open Plugins Folder** from the top menu bar.

---

## 2. Customizing `config.json`

The [`config.json`](../config/config.json) file controls shortcuts, colors, and initial defaults:

```json
{
    "shortcuts": {
        "next_station": "D",
        "prev_station": "A",
        "phase_p": "P",
        "phase_s": "S",
        "phase_custom": "C",
        "phase_rotate": "Q",
        "reset_view": "R",
        "save_sac": "Ctrl+S",
        "export_csv": "Ctrl+E",
        "toggle_filter": "F",
        "pick_p": "1",
        "pick_s": "2",
        "localize": "L",
        "focmec": "K",
        "open_map": "M"
    },
    "colors": {
        "Z": "#e74c3c",
        "N": "#f1c40f",
        "E": "#3498db",
        "other": "#7f8c8d",
        "pick_line": "#8e44ad",
        "pick_area_alpha": 60
    },
    "defaults": {
        "low_f": 1.0,
        "high_f": 20.0,
        "filter_type": "BandPass (f1 and f2)",
        "velocity_model": "velocity_model.json",
        "show_theoretical_arrivals": false,
        "picking_mode": "Popup",
        "station_client": "INGV",
        "map_dem_alpha": 0.40,
        "catalog_file": "~/Desktop/seismic_catalog.txt"
    }
}
```

### Configuration Sections

- **`shortcuts`**: Any valid Qt key sequence (e.g., `"M"`, `"L"`, `"K"`, `"Ctrl+S"`, `"F1"`, `"Space"`).
- **`colors`**:
  - `Z`, `N`, `E`: Colors assigned to vertical and horizontal channel orientations.
  - `other`: Fallback color for auxiliary or unrecognized component codes.
  - `pick_line`: Color of vertical pick indicator markers.
  - `pick_area_alpha`: Alpha transparency (0–255) for the shaded uncertainty region.
- **`defaults`**:
  - `low_f`, `high_f`: Initial filter frequency thresholds in Hz.
  - `filter_type`: Initial filter selection (`"None"`, `"BandPass (f1 and f2)"`, `"LowPass (f2)"`, `"HighPass (f1)"`).
  - `velocity_model`: Velocity model filename (e.g. `"velocity_model.json"`) or standard ObsPy TauP model (e.g. `"iasp91"`).
  - `show_theoretical_arrivals`: Boolean (`true` or `false`) to display theoretical P/S arrival lines upon file loading.
  - `picking_mode`: `"Popup"` (shows dialog for pick confirmation) or `"Sidebar"` (uses right-sidebar buttons).
  - `station_client`: Default FDSN webservice client for seismic stations (e.g. `"INGV"`, `"IRIS"`, `"ETH"`).
  - `map_dem_alpha`: Default opacity for the shaded DEM relief layer on the geographic map (0.05 to 1.0).
  - `catalog_file`: Output path for the automatic GIS seismic catalog (`.txt` TSV). Defaults to `~/Desktop/seismic_catalog.txt`.

---

## 3. Modifying the 1D Velocity Model

The [`velocity_model.json`](../config/velocity_model.json) file defines the 1D layered crustal velocity structure:

```json
{
  "name": "Default 1D Crustal Model",
  "layers": [
    {"depth_km": 0.0, "vp": 5.00, "vs": 2.89},
    {"depth_km": 11.1, "vp": 6.50, "vs": 3.75},
    {"depth_km": 38.0, "vp": 8.05, "vs": 4.65}
  ],
  "vp_vs_ratio": 1.73
}
```

- You can edit this file in `~/.config/PyPicker/velocity_model.json` directly or click **Plugins → Edit Velocity Model** in the application menu.
- Layers must be sorted by increasing depth top (`depth_km`).
- If `vs` is omitted or set to `null`, it is automatically computed using `vp / vp_vs_ratio`.
- For complete details on how this model is used by the inversion solver and ObsPy TauP, see the [**Hypocentral Earthquake Location Guide**](./hypo71_localization.md).
