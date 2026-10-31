# PyPicker Plugin System Architecture & Development Guide

PyPicker is designed around a modular, non-intrusive **Plugin Architecture**. This allows researchers and developers to extend the application with specialized seismological tools (such as hypocentral location, geographic mapping, focal mechanism estimation, or spectral ratio calculations) without modifying core visualization and picking routines.

---

## 1. Directory Structure & Discovery

PyPicker manages plugins through a dual-directory system that separates bundled defaults from user-installed scripts:

```text
PyPicker/
└── config/
    ├── config.json              # Main preferences & shortcut mappings
    ├── velocity_model.json      # 1D crustal velocity model
    ├── picker_utils_qt.py       # Shared utility module
    └── plugins/                 # Bundled plugin scripts and packages
        ├── hypo71_plugin.py     # Hypo71 wrapper & dialog logic
        ├── hypo71py/            # Pure-Python HYPO71 solver package
        ├── focmec_plugin.py     # FOCMEC wrapper & dialog logic
        ├── focmecpy/            # Pure-Python FOCMEC solver & beachball engine
        └── map_plugin.py        # Interactive Cartopy geographic map
```

### User Configuration Directory
On first launch, the contents of `config/plugins/` are automatically synchronized to the persistent user configuration directory:
- **Linux**: `~/.config/PyPicker/plugins/`
- **Windows**: `%LOCALAPPDATA%\PyPicker\plugins\`
- **macOS**: `~/Library/Preferences/PyPicker/plugins/`

### Automatic Module Path Resolution
At startup, `seismic_picker_qt.py` and `picker_utils_qt.py` automatically inject both plugin directories into `sys.path`:
```python
_config_plugins_dir = str(Path(__file__).resolve().parent / "config" / "plugins")
if _config_plugins_dir not in sys.path:
    sys.path.insert(0, _config_plugins_dir)

user_plugins_dir = str(utils.get_plugins_dir())
if user_plugins_dir not in sys.path:
    sys.path.insert(0, user_plugins_dir)
```
This guarantees that:
1. Plugins can import standard project utilities via `import picker_utils_qt as utils`.
2. Core PyPicker can dynamically import plugins with simple `import my_plugin` or `from config.plugins.my_plugin import MyPluginDialog`.
3. Standalone and frozen PyInstaller builds resolve all plugin assets cleanly without path mismatches.

---

## 2. Core Integration Points

Plugins have full access to PyPicker's in-memory data structures and Qt window hierarchy:

### 1. Accessing Waveforms & SAC Headers
A plugin dialog receives `parent` (the `SeismicPickerQT` main window) or the active `stream`:
```python
# In your plugin dialog:
stream = self.parent.original_stream   # Loaded waveforms (obspy.Stream)
for tr in stream:
    station = tr.stats.station
    sac = getattr(tr.stats, "sac", {})
    stla = sac.get("stla")             # Station latitude
    stlo = sac.get("stlo")             # Station longitude
    evla = sac.get("evla")             # Event latitude (if set)
```

### 2. Accessing Picks
Manual and automatic picks placed in PyPicker are stored in `self.parent.picks` as a list of dictionaries:
```python
picks = self.parent.picks
# Format:
# [
#   {
#       "sta": "CSTH",
#       "phase": "P",
#       "abs_t": "2026-07-31T17:46:39.800000Z",
#       "uncertainty": 0.05,
#       "polarity": "+",
#       "onset": "I"
#   },
#   ...
# ]
```

### 3. Local Cache Directory
Plugins requiring disk caching (e.g. downloaded station catalogs, compiled ray-tracing tables, temporary model files) should store them inside the PyPicker cache directory:
```python
cache_dir = utils.get_config_dir() / "cache"
cache_dir.mkdir(parents=True, exist_ok=True)
my_cache_file = cache_dir / "my_plugin_cache.dat"
```

### 4. Non-Destructive Data Handling
A foundational rule in PyPicker is **safe data preservation**:
- Never overwrite original files opened by the user.
- Export modified or processed waveforms (such as relocated SAC files) into dedicated subdirectories (e.g. `h71_localized/`) or prompt the user for an output path.
- In-memory updates (e.g., `tr.stats.sac['evla'] = ...`) are permitted to allow instant live updates across other plugins and waveform displays.

---

## 3. Step-by-Step: Creating a New Plugin

To add a new plugin to PyPicker, follow these steps:

### Step 1: Write the Plugin Module
Create a new file in `config/plugins/my_custom_plugin.py`:
```python
"""
My Custom Plugin for PyPicker.
"""

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QMessageBox
import picker_utils_qt as utils

class MyCustomDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("My Custom Plugin")
        self.resize(500, 350)
        
        layout = QVBoxLayout(self)
        
        self.lbl_info = QLabel("Custom analysis tool ready.")
        layout.addWidget(self.lbl_info)
        
        self.btn_run = QPushButton("Analyze Picks")
        self.btn_run.clicked.connect(self.run_analysis)
        layout.addWidget(self.btn_run)

    def run_analysis(self):
        picks = getattr(self.parent, "picks", [])
        if not picks:
            QMessageBox.warning(self, "No Picks", "Please pick some arrivals first!")
            return
            
        p_count = sum(1 for p in picks if p.get("phase") == "P")
        s_count = sum(1 for p in picks if p.get("phase") == "S")
        self.lbl_info.setText(f"Found {p_count} P-picks and {s_count} S-picks.")
```

### Step 2: Register in `config.json`
Add a keyboard shortcut or default parameter in [`config/config.json`](../config/config.json):
```json
{
    "shortcuts": {
        "custom_plugin": "K"
    }
}
```

### Step 3: Add Action to the `Plugins` Menu
In `seismic_picker_qt.py`:
```python
# In init_ui():
custom_key = self.config.get("shortcuts", {}).get("custom_plugin", "K")
act_custom = plugins_menu.addAction(f"My Custom Tool ({custom_key})")
act_custom.triggered.connect(self.open_custom_dialog)

# In setup_shortcuts():
self.action_map["custom_plugin"] = self.open_custom_dialog

# Define the launcher method:
def open_custom_dialog(self):
    from config.plugins.my_custom_plugin import MyCustomDialog
    if not hasattr(self, "_custom_dialog") or self._custom_dialog is None:
        self._custom_dialog = MyCustomDialog(parent=self)
    self._custom_dialog.show()
    self._custom_dialog.raise_()
    self._custom_dialog.activateWindow()
```

---

## 4. Built-in Integrated Plugins

PyPicker currently includes two standard plugins built on this architecture:

1. [**Hypo71 Earthquake Location**](./hypo71_localization.md)
   - Code: [`config/plugins/hypo71_plugin.py`](file:///run/media/donato/Storage/GitHub/PyPicker/config/plugins/hypo71_plugin.py)
   - Purpose: Computes hypocentral coordinates ($X, Y, Z$) and origin time ($T_0$) from arrival picks using an iterative Geiger inversion on a 1D crustal velocity model.
   - Shortcut: **`L`**

2. [**Earthquake Focal Mechanism (FOCMEC)**](./focmec_focal_mechanism.md)
   - Code: [`config/plugins/focmec_plugin.py`](file:///run/media/donato/Storage/GitHub/PyPicker/config/plugins/focmec_plugin.py)
   - Purpose: Computes double-couple fault planes (Strike, Dip, Rake), kinematic P/T axes, and tectonic regime from P-wave first-motion polarities via systematic grid search, featuring stereographic beachball plotting and full CSV reporting.
   - Shortcut: **`K`**

3. [**Geographic Map & Network Visualization**](./geographic_map.md)
   - Code: [`config/plugins/map_plugin.py`](file:///run/media/donato/Storage/GitHub/PyPicker/config/plugins/map_plugin.py)
   - Purpose: Renders interactive Cartopy maps with shaded DEM relief in transparency, FDSN station inventories (default: INGV), and dynamic epicenter tracking.
   - Shortcut: **`M`**
