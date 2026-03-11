import sys
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
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette, QKeySequence, QShortcut
from obspy import UTCDateTime, read, Stream
import picker_utils_qt as utils


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

        self.init_ui()
        self.setup_shortcuts()
        self.apply_system_theme()

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

        self.btn_save_csv = QPushButton("Export CSV")
        self.btn_save_csv.clicked.connect(self.export_csv)
        self.btn_save_csv.setStyleSheet(
            "font-weight: bold; background-color: #1ea54c; color: white;"
        )

        self.btn_save_sac = QPushButton("Save as SAC")
        self.btn_save_sac.clicked.connect(self.save_to_sac)
        self.btn_save_sac.setStyleSheet(
            "font-weight: bold; background-color: #1ea54c; color: white;"
        )

        left_sidebar.addWidget(self.btn_save_csv)
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

        right_sidebar.addStretch()
        right_group.setLayout(right_sidebar)

        # --- MAIN AREA: Graphics & Table ---
        graph_area = QVBoxLayout()
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.win = pg.GraphicsLayoutWidget()
        self.scroll.setWidget(self.win)
        graph_area.addWidget(self.scroll, stretch=4)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Sta", "Cha", "Phase", "Time", "Unc (s)", "Action"]
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
        self.view_mode.currentIndexChanged.connect(self.update_plots)
        self.sta_sel.currentIndexChanged.connect(self.update_plots)
        self.view_wave.toggled.connect(self.update_plots)
        self.spec_scale.currentIndexChanged.connect(self.update_plots)
        self.color_mode.currentIndexChanged.connect(self.update_plots)
        self.rmmean.stateChanged.connect(self.update_plots)
        self.detrend.stateChanged.connect(self.update_plots)
        self.filt_sel.currentIndexChanged.connect(self.update_plots)
        self.f_low.valueChanged.connect(self.update_plots)
        self.f_high.valueChanged.connect(self.update_plots)
        self.v_zoom.valueChanged.connect(self.update_gain)

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
            "export_csv": self.export_csv,
            "toggle_filter": self.toggle_filter,
        }

        for action, key in sc_config.items():
            if action in self.action_map:
                shortcut = QShortcut(QKeySequence(key), self)
                shortcut.activated.connect(self.action_map[action])

    def toggle_filter(self):
        idx = self.filt_sel.currentIndex()
        self.filt_sel.setCurrentIndex(3 if idx == 0 else 0)

    def apply_system_theme(self):
        """Adjust pyqtgraph theme to match system palette."""
        palette = self.palette()
        bg = palette.color(QPalette.ColorRole.Window)
        fg = palette.color(QPalette.ColorRole.WindowText)
        pg.setConfigOption("background", bg)
        pg.setConfigOption("foreground", fg)
        self.fg_color = fg.name()

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
                except Exception:
                    continue
            if new_st:
                self.original_stream = new_st
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
            self.picks = []
            self.stations = []
            self.sta_sel.clear()
            self.table.setRowCount(0)
            self.win.clear()
            self.update_plots()

    def _setup_after_load(self):
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
        self.sta_sel.blockSignals(False)
        self.update_plots()
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
            self._setup_after_load()

    def rotate_phase(self):
        """Cycle between P-S phases"""
        if self.ph_sel.currentText() == "S":
            self.ph_sel.setCurrentText("P")
        elif self.ph_sel.currentText() == "P":
            self.ph_sel.setCurrentText("S")
        else:
            self.ph_sel.setCurrentText("P")

    def update_plots(self):
        """Redraw all plots based on current filters and view mode."""
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
                pg.LabelItem(f"<b>STATION: {station}</b>", size="12pt"),
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
                label = pg.TextItem(
                    f"{tr.stats.channel}",
                    color=color,
                    anchor=(1, 0),
                    fill=(0, 0, 0, 100),
                )
                p.addItem(label)
                label.setParentItem(p.vb)
                label.setPos(p.vb.boundingRect().width() - 20, 0)

                self.plots.append(p)
        self.update_gain()

    def on_mouse_click_release(self, event):
        """Start or finalize a pick on mouse click."""
        if self.active_pick_item:
            # End picking
            unc = (
                self.active_pick_item.getRegion()[1]
                - self.active_pick_item.getRegion()[0]
            ) / 2
            self.current_picking_data["uncertainty"] = round(unc, 4)
            self.picks.append(self.current_picking_data)

            for p in self.plots:
                p.removeItem(self.active_pick_item)
            self.active_pick_item = None
            self.update_table()
            self.update_plots()
            return

        if event.button() == Qt.MouseButton.LeftButton and self.view_wave.isChecked():
            for p in self.plots:
                if p.sceneBoundingRect().contains(event.scenePos()):
                    mouse_point = p.vb.mapSceneToView(event.scenePos())
                    self.pick_start_point = event.scenePos()

                    phase = self.ph_sel.currentText()
                    if phase == "Custom":
                        phase = self.ph_custom.text()

                    self.current_picking_data = {
                        "sta": p.meta["sta"],
                        "cha_source": p.meta["cha"],
                        "phase": phase,
                        "abs_t": str(p.meta["st"] + mouse_point.x()),
                        "t_rel": mouse_point.x(),
                    }

                    self.active_pick_item = pg.LinearRegionItem(
                        values=[mouse_point.x(), mouse_point.x()],
                        brush=pg.mkBrush(142, 68, 173, 100),
                        movable=False,
                    )
                    p.addItem(self.active_pick_item)
                    break

    def on_mouse_move(self, pos):
        """Update uncertainty visual range based on vertical mouse movement."""
        if self.active_pick_item and self.pick_start_point:
            diff_y = abs(pos.y() - self.pick_start_point.y())
            view_range = self.plots[0].viewRange()[0]
            uncertainty = (diff_y / 500) * (view_range[1] - view_range[0])
            t_center = self.current_picking_data["t_rel"]
            self.active_pick_item.setRegion(
                [t_center - uncertainty, t_center + uncertainty]
            )

    def _add_visual_pick(self, plot, x_pos, label, uncertainty=0.0):
        c_cfg = self.config.get("colors", {})
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
            pen=pg.mkPen(main_color, width=1.5, style=Qt.PenStyle.DashLine),
        )
        plot.addItem(line)

    def update_table(self):
        self.table.setRowCount(len(self.picks))
        for i, pk in enumerate(self.picks):
            self.table.setItem(i, 0, QTableWidgetItem(pk["sta"]))
            self.table.setItem(i, 1, QTableWidgetItem(pk["cha_source"]))
            self.table.setItem(i, 2, QTableWidgetItem(pk["phase"]))
            self.table.setItem(i, 3, QTableWidgetItem(pk["abs_t"][-15:]))
            self.table.setItem(i, 4, QTableWidgetItem(str(pk.get("uncertainty", 0.0))))
            btn = QPushButton("Remove")
            btn.setStyleSheet("background-color: #a2292b; color: white;")
            btn.clicked.connect(lambda _, idx=i: self.delete_pick(idx))
            self.table.setCellWidget(i, 5, btn)

    def delete_pick(self, idx):
        if 0 <= idx < len(self.picks):
            self.picks.pop(idx)
            self.update_table()
            self.update_plots()

    def reset_view(self):
        self.v_zoom.setValue(1)
        self.update_plots()

    def update_gain(self):
        gain = self.v_zoom.value()
        for p in self.plots:
            items = p.listDataItems()
            if items:
                y = items[0].yData
                if y is not None and len(y) > 0:
                    amp = np.max(np.abs(y)) or 1
                    p.setYRange(-amp / gain, amp / gain)

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "picks.csv", "CSV Files (*.csv)"
        )
        if path:
            utils.export_to_csv(self.picks, path)
            QMessageBox.information(self, "Done", "CSV Exported.")

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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SeismicPickerQT()
    window.show()
    sys.exit(app.exec())
