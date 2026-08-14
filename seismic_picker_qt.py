import sys
import os

# Prevent ObsPy from attempting to run git describe on host repo in frozen PyInstaller builds
if getattr(sys, "frozen", False):
    import subprocess
    import warnings
    warnings.filterwarnings("ignore", message=".*ObsPy could not determine its version number.*")
    _orig_check_output = getattr(subprocess, "check_output", None)
    if _orig_check_output:
        def _safe_check_output(cmd, *args, **kwargs):
            if isinstance(cmd, (list, tuple)) and len(cmd) > 0 and cmd[0] == "git":
                raise subprocess.CalledProcessError(1, cmd)
            return _orig_check_output(cmd, *args, **kwargs)
        subprocess.check_output = _safe_check_output

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QLabel,
    QRadioButton,
    QDoubleSpinBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSlider,
    QFileDialog,
    QMessageBox,
    QCheckBox,
    QLineEdit,
    QScrollArea,
    QGroupBox,
    QDialog,
    QFormLayout,
    QDialogButtonBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette, QKeySequence, QShortcut
from obspy import UTCDateTime, read, Stream
import picker_utils_qt as utils

class PickDetailsDialog(QDialog):
    def __init__(self, parent=None, default_phase="P", custom_phase=""):
        super().__init__(parent)
        self.setWindowTitle("Pick Details")
        self.setModal(True)

        layout = QFormLayout(self)

        self.phase_cb = QComboBox()
        self.phase_cb.addItems(["P", "S", "Custom"])
        self.phase_cb.setCurrentText(default_phase if default_phase in ["P", "S"] else "Custom")
        
        self.custom_phase_le = QLineEdit()
        self.custom_phase_le.setText(custom_phase)
        self.custom_phase_le.setVisible(self.phase_cb.currentText() == "Custom")
        self.phase_cb.currentTextChanged.connect(
            lambda t: self.custom_phase_le.setVisible(t == "Custom")
        )

        self.polarity_cb = QComboBox()
        self.polarity_cb.addItems(["undecidable", "positive", "negative"])
        self.polarity_cb.setCurrentText("undecidable")

        self.onset_cb = QComboBox()
        self.onset_cb.addItems(["Unknown", "Emergent", "Impulsive"])
        self.onset_cb.setCurrentText("Unknown")

        layout.addRow("Phase:", self.phase_cb)
        layout.addRow("Custom Phase:", self.custom_phase_le)
        layout.addRow("Polarity:", self.polarity_cb)
        layout.addRow("Onset:", self.onset_cb)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_data(self):
        phase = self.phase_cb.currentText()
        if phase == "Custom":
            phase = self.custom_phase_le.text()
        return {
            "phase": phase,
            "polarity": self.polarity_cb.currentText(),
            "onset": self.onset_cb.currentText()
        }

class SeismicPickerQT(QMainWindow):
    def __init__(self, stream=None):
        super().__init__()
        self.config = utils.load_config()
        self.setWindowTitle("PyPicker - Seismic Waveform Analyzer")
        self.resize(1200, 900)

        # Data initialization
        self.original_stream = stream if stream else Stream()
        self.picks = []
        self.plots = []
        self.stations = []

        # Picking state
        self.active_pick_item = None  # The visual LinearRegionItem
        self.pick_start_point = None  # Mouse coordinate (px)
        self.current_picking_data = None
        self.last_mouse_pos = None    # Last mouse scene position

        self.init_ui()
        self.setup_shortcuts()
        self.update_shortcuts_reminder()
        self.apply_theme(self.theme_sel.currentText())

        if self.original_stream:
            self._setup_after_load()

    def init_ui(self):
        """Initialize the layout, sidebars, and main plotting area."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # --- LEFT SIDEBAR: Navigation & Display ---
        left_group = QGroupBox("Manage/Show data")
        left_sidebar = QVBoxLayout()

        self.btn_open = QPushButton("Open Waveforms")
        self.btn_open.clicked.connect(self.open_files)
        self.btn_open.setStyleSheet(
            "font-weight: bold; background-color: #2746ae; color: white;"
        )

        self.btn_clear = QPushButton("Clear All Data")
        self.btn_clear.clicked.connect(self.clear_all_data)
        self.btn_clear.setStyleSheet(
            "font-weight: bold; background-color: #2746ae; color: white;"
        )

        left_sidebar.addWidget(self.btn_open)
        left_sidebar.addWidget(self.btn_clear)
        left_sidebar.addWidget(QLabel("<b>View Mode:</b>"))

        self.view_mode = QComboBox()
        self.view_mode.addItems(["Single Station", "All Stations"])
        left_sidebar.addWidget(self.view_mode)

        # Station selection controls
        left_sidebar.addWidget(QLabel("<b>Station:</b>"))
        sta_layout = QHBoxLayout()
        self.sta_sel = QComboBox()
        self.sta_count_label = QLabel("0/0")
        self.sta_count_label.setStyleSheet("font-weight: bold; color: #2746ae;")

        self.btn_remove_sta = QPushButton("Del")
        self.btn_remove_sta.setFixedWidth(30)
        self.btn_remove_sta.setStyleSheet("background-color: #a2292b; color: white;")
        self.btn_remove_sta.clicked.connect(self.remove_current_station)

        sta_layout.addWidget(self.sta_sel)
        sta_layout.addWidget(self.sta_count_label)
        sta_layout.addWidget(self.btn_remove_sta)
        left_sidebar.addLayout(sta_layout)

        nav_layout = QHBoxLayout()
        self.btn_prev = QPushButton(" < ")
        self.btn_next = QPushButton(" > ")
        self.btn_prev.clicked.connect(self.prev_station)
        self.btn_next.clicked.connect(self.next_station)
        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.btn_next)
        left_sidebar.addLayout(nav_layout)

        # Plot settings
        self.view_wave = QRadioButton("Waveform")
        self.view_spec = QRadioButton("Spectrum")
        self.view_wave.setChecked(True)
        left_sidebar.addWidget(self.view_wave)
        left_sidebar.addWidget(self.view_spec)

        left_sidebar.addWidget(QLabel("<b>Spectrum Scale:</b>"))
        self.spec_scale = QComboBox()
        self.spec_scale.addItems(["Lin-Lin", "Log-Lin", "Lin-Log", "Log-Log"])
        left_sidebar.addWidget(self.spec_scale)

        left_sidebar.addWidget(QLabel("<b>Color Mode:</b>"))
        self.color_mode = QComboBox()
        self.color_mode.addItems(["Channel-based", "Uniform"])
        left_sidebar.addWidget(self.color_mode)

        left_sidebar.addWidget(QLabel("<b>Theme:</b>"))
        self.theme_sel = QComboBox()
        self.theme_sel.addItems(["System", "Dark", "Light"])
        left_sidebar.addWidget(self.theme_sel)

        left_sidebar.addWidget(QLabel("<b>Gain:</b>"))
        self.v_zoom = QSlider(Qt.Orientation.Horizontal)
        self.v_zoom.setRange(1, 100)
        self.v_zoom.setValue(1)
        left_sidebar.addWidget(self.v_zoom)

        self.btn_reset = QPushButton("Reset Zoom")
        self.btn_reset.clicked.connect(self.reset_view)
        self.btn_reset.setStyleSheet(
            "font-weight: bold; background-color: #2746ae; color: white;"
        )
        left_sidebar.addWidget(self.btn_reset)

        left_sidebar.addStretch()

        left_sidebar.addWidget(QLabel("<b>Sort Stations:</b>"))
        self.sort_sel = QComboBox()
        self.sort_sel.addItems(["Original", "By Distance", "By P/S Arrival"])
        self.sort_sel.currentIndexChanged.connect(self.sort_stations)
        left_sidebar.addWidget(self.sort_sel)

        self.btn_import_picks = QPushButton("Import Picks")
        self.btn_import_picks.clicked.connect(self.import_picks)
        self.btn_import_picks.setStyleSheet(
            "font-weight: bold; background-color: #e67e22; color: white;"
        )
        
        self.btn_export_picks = QPushButton("Export Picks")
        self.btn_export_picks.clicked.connect(self.export_picks)
        self.btn_export_picks.setStyleSheet(
            "font-weight: bold; background-color: #1ea54c; color: white;"
        )

        left_sidebar.addWidget(self.btn_import_picks)
        left_sidebar.addWidget(self.btn_export_picks)

        self.btn_save_sac = QPushButton("Save as SAC")
        self.btn_save_sac.clicked.connect(self.save_to_sac)
        self.btn_save_sac.setStyleSheet(
            "font-weight: bold; background-color: #1ea54c; color: white;"
        )
        
        left_sidebar.addWidget(self.btn_save_sac)
        left_group.setLayout(left_sidebar)

        # --- RIGHT SIDEBAR: Processing & Picking ---
        right_group = QGroupBox("Processing")
        right_sidebar = QVBoxLayout()

        right_sidebar.addWidget(QLabel("<b>Correction:</b>"))
        self.rmmean = QCheckBox("Remove mean")
        self.detrend = QCheckBox("Remove trend")
        right_sidebar.addWidget(self.rmmean)
        right_sidebar.addWidget(self.detrend)

        right_sidebar.addWidget(QLabel("<b>Filter:</b>"))
        self.filt_sel = QComboBox()
        self.filt_sel.addItems(
            ["None", "HighPass (f1)", "LowPass (f2)", "BandPass (f1/f2)"]
        )
        right_sidebar.addWidget(self.filt_sel)

        right_sidebar.addWidget(QLabel("<b>Freqs (Hz):</b>"))
        self.f_low = QDoubleSpinBox()
        self.f_low.setRange(0.01, 200)
        self.f_low.setValue(1.0)
        self.f_high = QDoubleSpinBox()
        self.f_high.setRange(0.01, 200)
        self.f_high.setValue(20.0)
        right_sidebar.addWidget(self.f_low)
        right_sidebar.addWidget(self.f_high)

        right_sidebar.addWidget(QLabel("<b>Phase:</b>"))
        self.ph_sel = QComboBox()
        self.ph_sel.addItems(["P", "S", "Custom"])
        self.ph_custom = QLineEdit()
        self.ph_custom.setPlaceholderText("Enter custom phase...")
        right_sidebar.addWidget(self.ph_sel)
        right_sidebar.addWidget(self.ph_custom)

        right_sidebar.addWidget(QLabel("<b>Polarity:</b>"))
        self.polarity_sel = QComboBox()
        self.polarity_sel.addItems(["undecidable", "positive", "negative"])
        right_sidebar.addWidget(self.polarity_sel)

        right_sidebar.addWidget(QLabel("<b>Onset:</b>"))
        self.onset_sel = QComboBox()
        self.onset_sel.addItems(["Unknown", "Emergent", "Impulsive"])
        right_sidebar.addWidget(self.onset_sel)

        right_sidebar.addWidget(QLabel("<b>Picking Mode:</b>"))
        self.picking_mode_sel = QComboBox()
        self.picking_mode_sel.addItems(["Sidebar", "Popup"])
        default_mode = self.config.get("defaults", {}).get("picking_mode", "Popup")
        self.picking_mode_sel.setCurrentText(default_mode)
        right_sidebar.addWidget(self.picking_mode_sel)

        right_sidebar.addWidget(QLabel("<b>Theoretical:</b>"))
        self.show_theo = QCheckBox("Show Arrivals")
        default_theo = self.config.get("defaults", {}).get("show_theoretical_arrivals", False)
        self.show_theo.setChecked(default_theo)
        self.show_theo.setStyleSheet("font-weight: bold; color: #d35400;") # highlight
        right_sidebar.addWidget(self.show_theo)

        right_sidebar.addStretch()

        # Shortcuts reminder card
        sc_group = QGroupBox("Shortcuts")
        sc_layout = QVBoxLayout()
        self.shortcuts_label = QLabel()
        self.shortcuts_label.setWordWrap(True)
        self.shortcuts_label.setTextFormat(Qt.TextFormat.RichText)
        self.shortcuts_label.setStyleSheet("font-size: 11px;")
        sc_layout.addWidget(self.shortcuts_label)
        sc_group.setLayout(sc_layout)

        right_sidebar.addWidget(sc_group)
        right_group.setLayout(right_sidebar)

        # --- MAIN AREA: Graphics & Table ---
        graph_area = QVBoxLayout()
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.win = pg.GraphicsLayoutWidget()
        self.scroll.setWidget(self.win)
        graph_area.addWidget(self.scroll, stretch=4)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            ["Sta", "Cha", "Phase", "Date", "Time", "Unc (s)", "Polarity", "Onset", "Action"]
        )
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        graph_area.addWidget(self.table, stretch=1)

        main_layout.addWidget(left_group, 1)
        main_layout.addLayout(graph_area, 4)
        main_layout.addWidget(right_group, 1)

        # Signal connections
        self._connect_signals()

    def _connect_signals(self):
        """Register events and UI updates."""
        self.view_mode.currentIndexChanged.connect(lambda: self.update_plots(reset_zoom=True))
        self.sta_sel.currentIndexChanged.connect(lambda: self.update_plots(reset_zoom=True))
        self.view_wave.toggled.connect(lambda: self.update_plots(reset_zoom=True))
        self.spec_scale.currentIndexChanged.connect(self.update_plots)
        self.color_mode.currentIndexChanged.connect(self.update_plots)
        self.rmmean.stateChanged.connect(self.update_plots)
        self.detrend.stateChanged.connect(self.update_plots)
        self.filt_sel.currentIndexChanged.connect(self.update_plots)
        self.f_low.valueChanged.connect(self.update_plots)
        self.f_high.valueChanged.connect(self.update_plots)
        self.v_zoom.valueChanged.connect(self.update_gain)
        self.show_theo.stateChanged.connect(self.update_plots)
        self.theme_sel.currentTextChanged.connect(self.apply_theme)

        self.win.scene().sigMouseMoved.connect(self.on_mouse_move)
        self.win.scene().sigMouseClicked.connect(self.on_mouse_click_release)

    def setup_shortcuts(self):
        """Map keyboard shortcuts based on config.json."""
        sc_config = self.config.get("shortcuts", {})
        self.action_map = {
            "next_station": self.next_station,
            "prev_station": self.prev_station,
            "phase_p": lambda: self.ph_sel.setCurrentText("P"),
            "phase_s": lambda: self.ph_sel.setCurrentText("S"),
            "phase_custom": lambda: self.ph_sel.setCurrentText("Custom"),
            "phase_rotate": self.rotate_phase,
            "reset_view": self.reset_view,
            "save_sac": self.save_to_sac,
            "export_csv": self.export_picks,
            "toggle_filter": self.toggle_filter,
            "pick_p": lambda: self.start_pick_from_shortcut("P"),
            "pick_s": lambda: self.start_pick_from_shortcut("S"),
        }

        for action, key in sc_config.items():
            if action in self.action_map:
                shortcut = QShortcut(QKeySequence(key), self)
                shortcut.activated.connect(self.action_map[action])

    def toggle_filter(self):
        idx = self.filt_sel.currentIndex()
        self.filt_sel.setCurrentIndex(3 if idx == 0 else 0)

    def _is_light_bg(self, color_val):
        qcol = pg.mkColor(color_val)
        lum = 0.299 * qcol.red() + 0.587 * qcol.green() + 0.114 * qcol.blue()
        return lum > 128

    def apply_theme(self, mode="System"):
        """Adjust pyqtgraph theme and application palette colors without modifying layout metrics or borders."""
        app = QApplication.instance()
        
        if mode == "Dark":
            bg_color = "#1e1e1e"
            fg_color = "#ffffff"
            input_bg = "#2b2b2b"
            
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, pg.mkColor(bg_color))
            palette.setColor(QPalette.ColorRole.WindowText, pg.mkColor(fg_color))
            palette.setColor(QPalette.ColorRole.Base, pg.mkColor(input_bg))
            palette.setColor(QPalette.ColorRole.AlternateBase, pg.mkColor("#333333"))
            palette.setColor(QPalette.ColorRole.ToolTipBase, pg.mkColor(fg_color))
            palette.setColor(QPalette.ColorRole.ToolTipText, pg.mkColor(fg_color))
            palette.setColor(QPalette.ColorRole.Text, pg.mkColor(fg_color))
            palette.setColor(QPalette.ColorRole.Button, pg.mkColor(input_bg))
            palette.setColor(QPalette.ColorRole.ButtonText, pg.mkColor(fg_color))
            palette.setColor(QPalette.ColorRole.BrightText, pg.mkColor("#ff0000"))
            palette.setColor(QPalette.ColorRole.Highlight, pg.mkColor("#2746ae"))
            palette.setColor(QPalette.ColorRole.HighlightedText, pg.mkColor("#ffffff"))
            if app:
                app.setPalette(palette)
            self.setPalette(palette)
            self.setStyleSheet("") # Clear custom stylesheet to preserve native widget dimensions/icons
            
        elif mode == "Light":
            bg_color = "#ffffff"
            fg_color = "#000000"
            input_bg = "#f9f9f9"
            
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, pg.mkColor("#f4f4f4"))
            palette.setColor(QPalette.ColorRole.WindowText, pg.mkColor(fg_color))
            palette.setColor(QPalette.ColorRole.Base, pg.mkColor(input_bg))
            palette.setColor(QPalette.ColorRole.AlternateBase, pg.mkColor("#e9e9e9"))
            palette.setColor(QPalette.ColorRole.ToolTipBase, pg.mkColor(fg_color))
            palette.setColor(QPalette.ColorRole.ToolTipText, pg.mkColor(fg_color))
            palette.setColor(QPalette.ColorRole.Text, pg.mkColor(fg_color))
            palette.setColor(QPalette.ColorRole.Button, pg.mkColor("#e8e8e8"))
            palette.setColor(QPalette.ColorRole.ButtonText, pg.mkColor(fg_color))
            palette.setColor(QPalette.ColorRole.Highlight, pg.mkColor("#2746ae"))
            palette.setColor(QPalette.ColorRole.HighlightedText, pg.mkColor("#ffffff"))
            if app:
                app.setPalette(palette)
            self.setPalette(palette)
            self.setStyleSheet("")

        else: # System
            if app:
                app.setPalette(app.style().standardPalette())
            self.setPalette(self.style().standardPalette())
            self.setStyleSheet("")
            palette = self.palette()
            bg_color = palette.color(QPalette.ColorRole.Window).name()
            fg_color = palette.color(QPalette.ColorRole.WindowText).name()

        self.current_bg = bg_color
        self.fg_color = fg_color

        pg.setConfigOption("background", bg_color)
        pg.setConfigOption("foreground", fg_color)

        if hasattr(self, "win"):
            self.win.setBackground(bg_color)

        if hasattr(self, "plots") and self.plots:
            self.update_plots()

    def update_shortcuts_reminder(self):
        """Update shortcuts reminder box dynamically based on config.json."""
        sc_config = self.config.get("shortcuts", {})
        descriptions = {
            "prev_station": "Prev Station",
            "next_station": "Next Station",
            "pick_p": "Quick Pick P",
            "pick_s": "Quick Pick S",
            "phase_p": "Select P",
            "phase_s": "Select S",
            "phase_rotate": "Toggle P/S",
            "toggle_filter": "Toggle Filter",
            "reset_view": "Reset Zoom",
            "save_sac": "Save SAC",
            "export_csv": "Export Picks",
        }
        items = []
        for key, desc in descriptions.items():
            if key in sc_config:
                val = sc_config[key]
                items.append(f"<b>{val}</b>: {desc}")
        
        if items:
            text = "<br>".join(items)
        else:
            text = "<i>No shortcuts configured</i>"
            
        self.shortcuts_label.setText(text)

    def open_files(self):
        """Load seismic data from disk."""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Waveforms",
            "",
            "Waveforms (*.sac *.mseed *.dat);;All Files (*)",
        )
        if files:
            new_st = Stream()
            for f in files:
                try:
                    st_file = read(f)
                    for tr in st_file:
                        tr.stats.filename = f
                        new_st += tr
                except Exception as e:
                    print(f"Error while loading waveforms: {e}")
                    continue
            if new_st:
                self.original_stream = new_st
                self.base_stream = new_st.copy()
                self.picks = utils.extract_existing_picks(self.original_stream)
                self._setup_after_load()

    def clear_all_data(self):
        if not self.original_stream:
            return
        msg = "Are you sure you want to clear all data?"
        reply = QMessageBox.question(
            self,
            "Clear",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.original_stream = Stream()
            self.base_stream = Stream()
            self.picks = []
            self.stations = []
            self.sta_sel.clear()
            self.table.setRowCount(0)
            self.win.clear()
            self.update_plots(reset_zoom=True)

    def _setup_after_load(self, target_idx=0):
        """Populate the station list after data loading."""
        seen = set()
        self.sta_sel.blockSignals(True)
        self.sta_sel.clear()
        self.stations = []
        for tr in self.original_stream:
            s_id = f"{tr.stats.network}.{tr.stats.station}"
            if s_id not in seen:
                self.stations.append({"id": s_id, "sta": tr.stats.station})
                self.sta_sel.addItem(s_id)
                seen.add(s_id)
        
        if self.sta_sel.count() > 0:
            target_idx = min(max(0, target_idx), self.sta_sel.count() - 1)
            self.sta_sel.setCurrentIndex(target_idx)
            
        self.sta_sel.blockSignals(False)
        self.update_plots(reset_zoom=True)
        self.update_table()

    def prev_station(self):
        cur = self.sta_sel.currentIndex()
        if cur > 0:
            self.sta_sel.setCurrentIndex(cur - 1)

    def next_station(self):
        cur = self.sta_sel.currentIndex()
        if cur < self.sta_sel.count() - 1:
            self.sta_sel.setCurrentIndex(cur + 1)

    def remove_current_station(self):
        """Remove currently selected station from the stream."""
        if self.sta_sel.currentIndex() < 0:
            return
        idx = self.sta_sel.currentIndex()
        sta = self.stations[idx]["sta"]

        reply = QMessageBox.question(
            self,
            "Remove",
            f"Remove station {sta}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.original_stream = Stream(
                [tr for tr in self.original_stream if tr.stats.station != sta]
            )
            self.picks = [p for p in self.picks if p["sta"] != sta]
            self._setup_after_load(target_idx=idx)

    def rotate_phase(self):
        """Cycle between P-S phases"""
        if self.ph_sel.currentText() == "S":
            self.ph_sel.setCurrentText("P")
        elif self.ph_sel.currentText() == "P":
            self.ph_sel.setCurrentText("S")
        else:
            self.ph_sel.setCurrentText("P")

    def update_plots(self, *args, reset_zoom=False):
        """Redraw all plots based on current filters and view mode."""
        old_view_range = None
        if not reset_zoom and self.plots and self.view_wave.isChecked() and hasattr(self.plots[0], 'viewRange'):
            old_view_range = self.plots[0].viewRange()

        self.win.clear()
        self.plots = []
        if not self.original_stream or not self.stations:
            self.sta_count_label.setText("0/0")
            return

        params = {
            "demean": self.rmmean.isChecked(),
            "detrend": self.detrend.isChecked(),
            "filter_type": self.filt_sel.currentText(),
            "low_f": self.f_low.value(),
            "high_f": self.f_high.value(),
        }

        proc_st = utils.apply_preprocessing(self.original_stream, params)
        
        model_name = self.config.get("defaults", {}).get("velocity_model", "")
        theo_arrs = {}
        if model_name and self.show_theo.isChecked():
            theo_arrs = utils.calculate_theoretical_arrivals(proc_st, model_name=model_name)
        mode = self.view_mode.currentText()

        if mode == "Single Station":
            sta_idx = self.sta_sel.currentIndex()
            target_sta = [self.stations[sta_idx]["sta"]] if sta_idx >= 0 else []
            self.sta_count_label.setText(f"{sta_idx + 1}/{self.sta_sel.count()}")
            total_h = self.scroll.height() - 20
        else:
            target_sta = sorted(list(set(tr.stats.station for tr in proc_st)))
            self.sta_count_label.setText("All")
            num_traces = sum([len(proc_st.select(station=s)) for s in target_sta])
            total_h = (num_traces * 150) + (len(target_sta) * 40)

        self.win.setMinimumHeight(max(total_h, 400))
        first_p = None
        current_row = 0
        colors_cfg = self.config.get("colors", {})

        for station in target_sta:
            traces = sorted(
                proc_st.select(station=station),
                key=lambda x: x.stats.channel[-1],
                reverse=True,
            )
            self.win.addItem(
                pg.LabelItem(f"<b>STATION: {station}</b>", size="12pt", color=self.fg_color),
                row=current_row,
                col=0,
            )
            current_row += 1

            for tr in traces:
                p = self.win.addPlot(row=current_row, col=0)
                current_row += 1
                if first_p is None:
                    first_p = p
                else:
                    p.setXLink(first_p)

                # Color logic
                chan = tr.stats.channel.upper()
                if self.color_mode.currentIndex() == 0:
                    color = colors_cfg.get(chan[-1], colors_cfg.get("other", "gray"))
                    if chan[-1] == "N" and self._is_light_bg(getattr(self, "current_bg", "#1e1e1e")):
                        color = "#b7950b"
                else:
                    color = self.fg_color

                if self.view_wave.isChecked():
                    dur = tr.stats.npts * tr.stats.delta
                    data_max = np.max(np.abs(tr.data)) if len(tr.data) > 0 else 1
                    p.setLimits(
                        xMin=0,
                        xMax=dur,
                        yMin=-data_max * 10,
                        yMax=data_max * 10,
                    )
                    if old_view_range is not None:
                        p.setXRange(old_view_range[0][0], old_view_range[0][1], padding=0)
                    else:
                        p.setXRange(0, dur, padding=0)
                    p.plot(tr.times(), tr.data, pen=pg.mkPen(color, width=1.2))
                    p.meta = {
                        "sta": tr.stats.station,
                        "cha": tr.stats.channel,
                        "st": tr.stats.starttime,
                    }

                    # Draw existing picks
                    for pk in self.picks:
                        if pk["sta"] == tr.stats.station:
                            t_rel = UTCDateTime(pk["abs_t"]) - tr.stats.starttime
                            if 0 <= t_rel <= dur:
                                self._add_visual_pick(
                                    p, t_rel, pk["phase"], pk.get("uncertainty", 0.0)
                                )
                                
                    # Draw theoretical arrivals
                    if tr.stats.station in theo_arrs:
                        for ph, arr_time in theo_arrs[tr.stats.station].items():
                            t_rel = arr_time - tr.stats.starttime
                            if 0 <= t_rel <= dur:
                                ph_u = ph.upper()
                                if ph_u == "P":
                                    t_col = "#e74c3c" # Red
                                elif ph_u == "S":
                                    t_col = "#2980b9" # Blue
                                else:
                                    t_col = "#1abc9c" # Teal
                                self._add_visual_pick(
                                    p, t_rel, f"{ph} (theo)", 0.0, color=t_col, style=Qt.PenStyle.DotLine
                                )
                else:
                    # Spectrum view
                    f, s = utils.get_spectrum(tr)
                    f_max = max(f)
                    s_max = max(s)
                    p.setLimits(xMin=0, xMax=f_max)
                    p.setXRange(0, f_max, padding=0)
                    p.setLimits(yMin=0, yMax=s_max)
                    p.setXRange(0, s_max, padding=0)
                    p.plot(f, s, pen=pg.mkPen(color))
                    scale = self.spec_scale.currentText()
                    p.setLogMode(
                        "Log" in scale.split("-")[0], "Log" in scale.split("-")[1]
                    )

                # Draw channel name
                fill_col = (255, 255, 255, 180) if self._is_light_bg(getattr(self, "current_bg", "#1e1e1e")) else (0, 0, 0, 180)
                label = pg.TextItem(
                    f"{tr.stats.channel}",
                    color=color,
                    anchor=(1, 0),
                    fill=fill_col,
                )
                p.addItem(label)
                label.setParentItem(p.vb)
                label.setPos(p.vb.boundingRect().width() - 20, 0)

                self.plots.append(p)
        self.update_gain()

    def _start_picking(self, scene_pos):
        for p in self.plots:
            if p.sceneBoundingRect().contains(scene_pos):
                mouse_point = p.vb.mapSceneToView(scene_pos)
                self.pick_start_point = scene_pos

                phase = self.ph_sel.currentText()
                if phase == "Custom":
                    phase = self.ph_custom.text()

                self.current_picking_data = {
                    "sta": p.meta["sta"],
                    "cha_source": p.meta["cha"],
                    "phase": phase,
                    "abs_t": str(p.meta["st"] + mouse_point.x()),
                    "t_rel": mouse_point.x(),
                    "polarity": self.polarity_sel.currentText(),
                    "onset": self.onset_sel.currentText(),
                }

                self.active_pick_item = pg.LinearRegionItem(
                    values=[mouse_point.x(), mouse_point.x()],
                    brush=pg.mkBrush(142, 68, 173, 100),
                    movable=False,
                )
                p.addItem(self.active_pick_item)
                break

    def start_pick_from_shortcut(self, phase):
        if not self.last_mouse_pos or not self.view_wave.isChecked() or self.active_pick_item:
            return
        self.ph_sel.setCurrentText(phase)
        self._start_picking(self.last_mouse_pos)

    def on_mouse_click_release(self, event):
        """Start or finalize a pick on mouse click."""
        if self.active_pick_item:
            # End picking
            unc = (
                self.active_pick_item.getRegion()[1]
                - self.active_pick_item.getRegion()[0]
            ) / 2
            self.current_picking_data["uncertainty"] = round(unc, 4)
            
            if self.picking_mode_sel.currentText() == "Popup":
                dialog = PickDetailsDialog(
                    self, 
                    default_phase=self.current_picking_data["phase"],
                    custom_phase=self.ph_custom.text()
                )
                if dialog.exec():
                    data = dialog.get_data()
                    self.current_picking_data["phase"] = data["phase"]
                    self.current_picking_data["polarity"] = data["polarity"]
                    self.current_picking_data["onset"] = data["onset"]
                    self.picks.append(self.current_picking_data)
            else:
                self.picks.append(self.current_picking_data)

            for p in self.plots:
                p.removeItem(self.active_pick_item)
            self.active_pick_item = None
            self.update_table()
            self.update_plots()
            return

        if event.button() == Qt.MouseButton.LeftButton and self.view_wave.isChecked():
            self._start_picking(event.scenePos())

    def on_mouse_move(self, pos):
        """Update uncertainty visual range based on vertical mouse movement."""
        self.last_mouse_pos = pos
        if self.active_pick_item and self.pick_start_point:
            diff_y = abs(pos.y() - self.pick_start_point.y())
            view_range = self.plots[0].viewRange()[0]
            uncertainty = (diff_y / 500) * (view_range[1] - view_range[0])
            t_center = self.current_picking_data["t_rel"]
            self.active_pick_item.setRegion(
                [t_center - uncertainty, t_center + uncertainty]
            )

    def _add_visual_pick(self, plot, x_pos, label, uncertainty=0.0, color=None, style=Qt.PenStyle.DashLine):
        c_cfg = self.config.get("colors", {})
        
        if color:
            main_color = color
        else:
            lbl_up = label.upper()
            if "P" in lbl_up:
                main_color = "#c0392b" # Darker Red
            elif "S" in lbl_up:
                main_color = "#2980b9" # Darker Blue
            else:
                main_color = c_cfg.get("pick_line", "#8e44ad")

        if uncertainty > 0:
            brush_color = pg.mkColor(main_color)
            brush_color.setAlpha(c_cfg.get("pick_area_alpha", 50))
            region = pg.LinearRegionItem(
                values=[x_pos - uncertainty, x_pos + uncertainty],
                brush=pg.mkBrush(brush_color),
                pen=pg.mkPen(None),
                movable=False,
            )
            plot.addItem(region)

        line = pg.InfiniteLine(
            pos=x_pos,
            angle=90,
            pen=pg.mkPen(main_color, width=1.5, style=style),
        )
        plot.addItem(line)
        
        text = pg.TextItem(label, color=main_color, anchor=(0, 1))
        plot.addItem(text)
        text.setPos(x_pos, 0)

    def update_table(self):
        self.table.setRowCount(len(self.picks))
        for i, pk in enumerate(self.picks):
            self.table.setItem(i, 0, QTableWidgetItem(pk["sta"]))
            self.table.setItem(i, 1, QTableWidgetItem(pk["cha_source"]))
            self.table.setItem(i, 2, QTableWidgetItem(pk["phase"]))
            self.table.setItem(i, 3, QTableWidgetItem(pk["abs_t"].split('T')[0]))
            self.table.setItem(i, 4, QTableWidgetItem(pk["abs_t"].split("T")[-1][:-1]))
            self.table.setItem(i, 5, QTableWidgetItem(str(pk.get("uncertainty", 0.0))))
            self.table.setItem(i, 6, QTableWidgetItem(pk.get("polarity", "Unknown")))
            self.table.setItem(i, 7, QTableWidgetItem(pk.get("onset", "Unknown")))
            btn = QPushButton("Remove")
            btn.setStyleSheet("background-color: #a2292b; color: white;")
            btn.clicked.connect(lambda _, idx=i: self.delete_pick(idx))
            self.table.setCellWidget(i, 8, btn)

    def delete_pick(self, idx):
        if 0 <= idx < len(self.picks):
            self.picks.pop(idx)
            self.update_table()
            self.update_plots()

    def reset_view(self):
        self.v_zoom.setValue(1)
        self.update_plots(reset_zoom=True)

    def update_gain(self):
        gain = self.v_zoom.value()
        for p in self.plots:
            items = p.listDataItems()
            if items:
                y = items[0].yData
                if y is not None and len(y) > 0:
                    amp = np.max(np.abs(y)) or 1
                    p.setYRange(-amp / gain, amp / gain)

    def import_picks(self):
        path, filt = QFileDialog.getOpenFileName(
            self, "Import Picks", "", "QuakeML (*.qml *.xml);;CSV Files (*.csv)"
        )
        if path:
            try:
                if path.endswith('.csv'):
                    new_picks = utils.extract_picks_from_csv(path)
                else:
                    new_picks = utils.extract_picks_from_quakeml(path)
                self.picks.extend(new_picks)
                self.update_table()
                self.update_plots()
                QMessageBox.information(self, "Done", "Picks imported.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not import picks: {e}")

    def export_picks(self):
        if not self.picks:
            return
        path, filt = QFileDialog.getSaveFileName(
            self, "Export Picks", "picks", "QuakeML (*.qml);;QuakeML (*.xml);;CSV Files (*.csv)"
        )
        if path:
            try:
                if path.endswith('.csv') or "CSV" in filt:
                    if not path.endswith('.csv'): path += ".csv"
                    utils.export_to_csv(self.picks, path)
                else:
                    if not path.endswith('.qml') and not path.endswith('.xml'): 
                        path += ".qml" if "qml" in filt else ".xml"
                    utils.export_to_quakeml(self.picks, path)
                QMessageBox.information(self, "Done", "Picks Exported.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not export picks: {e}")

    def save_to_sac(self):
        if not self.picks:
            return
        reply = QMessageBox.question(
            self,
            "Save",
            "Update SAC headers?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            utils.save_picks_to_sac(self.original_stream, self.picks)
            QMessageBox.information(self, "Saved", "SAC files updated.")

    def sort_stations(self):
        mode = self.sort_sel.currentText()
        if mode == "Original":
            if hasattr(self, "base_stream") and self.base_stream:
                self.original_stream = self.base_stream.copy()
        elif mode == "By Distance":
            self.original_stream = utils.reorder_stream_by_distance(self.original_stream)
        elif mode == "By P/S Arrival":
            self.original_stream = utils.reorder_stream_by_arrival(self.original_stream, self.picks)
        
        self._setup_after_load()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SeismicPickerQT()
    window.show()
    sys.exit(app.exec())
