import sys
import numpy as np
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
from PyQt6.QtGui import QPalette
import pyqtgraph as pg
from obspy import UTCDateTime, read, Stream
import picker_utils_qt as utils


class SeismicPickerQT(QMainWindow):
    def __init__(self, stream=None):
        super().__init__()
        self.setWindowTitle("PyPicker")
        self.resize(1200, 900)

        self.original_stream = stream if stream else Stream()
        self.picks = []
        self.plots = []
        self.stations = []

        self.init_ui()
        self.apply_system_theme()

        if self.original_stream:
            self._setup_after_load()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # --- LEFT SIDEBAR ---
        left = QGroupBox("Manage/Show data")
        left_sidebar = QVBoxLayout()

        self.btn_open = QPushButton("Open Waveforms")
        self.btn_open.clicked.connect(self.open_files)
        self.btn_open.setStyleSheet(
            "font-weight: bold; background-color: #2746ae; color: white;"
        )
        left_sidebar.addWidget(self.btn_open)

        left_sidebar.addWidget(QLabel("<b>View Mode:</b>"))
        self.view_mode = QComboBox()
        self.view_mode.addItems(["Single Station", "All Stations"])
        left_sidebar.addWidget(self.view_mode)

        left_sidebar.addWidget(QLabel("<b>Station:</b>"))
        sta_layout = QHBoxLayout()
        self.sta_sel = QComboBox()
        self.btn_remove_sta = QPushButton("Del")
        self.btn_remove_sta.setFixedWidth(30)
        self.btn_remove_sta.setToolTip("Remove this station from current session")
        self.btn_remove_sta.setStyleSheet("background-color: #a2292b; color: white;")
        self.btn_remove_sta.clicked.connect(self.remove_current_station)
        sta_layout.addWidget(self.sta_sel)
        sta_layout.addWidget(self.btn_remove_sta)
        left_sidebar.addLayout(sta_layout)

        nav_layout = QHBoxLayout()
        self.btn_prev = QPushButton(" < ")
        self.btn_prev.setStyleSheet("font-weight: bold;")
        self.btn_next = QPushButton(" > ")
        self.btn_next.setStyleSheet("font-weight: bold;")
        self.btn_prev.clicked.connect(self.prev_station)
        self.btn_next.clicked.connect(self.next_station)
        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.btn_next)
        left_sidebar.addLayout(nav_layout)

        left_sidebar.addWidget(QLabel("<b>Visualization:</b>"))
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
        left_sidebar.addWidget(self.btn_save_csv)

        self.btn_save_sac = QPushButton("Save as SAC")
        self.btn_save_sac.clicked.connect(self.save_to_sac)
        self.btn_save_sac.setStyleSheet(
            "font-weight: bold; background-color: #1ea54c; color: white;"
        )
        left_sidebar.addWidget(self.btn_save_sac)

        left.setLayout(left_sidebar)

        # --- RIGHT SIDEBAR ---
        right = QGroupBox("Elaborate data")
        right_sidebar = QVBoxLayout()

        right_sidebar.addWidget(QLabel("<b>Correct traces:</b>"))
        self.rmmean = QCheckBox("Remove mean")
        self.detrend = QCheckBox("Remove linear trend")
        right_sidebar.addWidget(self.rmmean)
        right_sidebar.addWidget(self.detrend)

        right_sidebar.addWidget(QLabel("<b>Filter:</b>"))
        self.filt_sel = QComboBox()
        self.filt_sel.addItems(
            ["None", "HighPass (use f1)", "LowPass (use f2)", "BandPass (f1 and f2)"]
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
        right_sidebar.addWidget(self.ph_sel)
        self.ph_custom = QLineEdit()
        self.ph_custom.setPlaceholderText("Custom...")
        right_sidebar.addWidget(self.ph_custom)

        right_sidebar.addStretch()

        right.setLayout(right_sidebar)

        # --- MAIN AREA ---
        graph_area = QVBoxLayout()
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)

        self.win = pg.GraphicsLayoutWidget()
        self.scroll.setWidget(self.win)

        graph_area.addWidget(self.scroll, stretch=4)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Sta", "Cha", "Phase", "Time", "Action"])
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        graph_area.addWidget(self.table, stretch=1)

        main_layout.addWidget(left, 1)
        main_layout.addLayout(graph_area, 4)
        main_layout.addWidget(right, 1)

        # --- SIGNALS ---
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
        self.win.scene().sigMouseClicked.connect(self.on_plot_click)

    def apply_system_theme(self):
        palette = self.palette()
        bg = palette.color(QPalette.ColorRole.Window)
        fg = palette.color(QPalette.ColorRole.WindowText)
        pg.setConfigOption("background", bg)
        pg.setConfigOption("foreground", fg)
        self.fg_color = fg.name()

    def open_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select waveforms",
            "",
            "Waveforms (*.sac *.mseed *.dat *.asc);;All Files (*)",
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

    def remove_current_station(self):
        if not self.original_stream or self.sta_sel.currentIndex() < 0:
            return

        current_idx = self.sta_sel.currentIndex()
        sta_to_remove = self.stations[current_idx]["sta"]

        if current_idx == self.sta_sel.count() - 1:
            next_idx = current_idx - 1
        else:
            next_idx = current_idx

        msg = f"Are you sure you want to remove station {sta_to_remove}?"
        reply = QMessageBox.question(self, "Confirm", msg, 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            new_st = Stream()
            for tr in self.original_stream:
                if tr.stats.station != sta_to_remove:
                    new_st += tr
            self.original_stream = new_st

            self.picks = [p for p in self.picks if p["sta"] != sta_to_remove]
            self.update_table()

            if len(self.original_stream) == 0:
                self.sta_sel.clear()
                self.stations = []
                self.win.clear()
                QMessageBox.information(self, "Empty", "No more stations.")
            else:
                self.sta_sel.blockSignals(True)
                self._setup_after_load_minimal()
                self.sta_sel.blockSignals(False)

                target = max(0, next_idx)
                self.sta_sel.setCurrentIndex(target)
                self.update_plots()
                self.update_table()

    def _setup_after_load(self):
        seen = set()
        self.sta_sel.clear()
        self.stations = []
        for tr in self.original_stream:
            s_id = f"{tr.stats.network}.{tr.stats.station}"
            if s_id not in seen:
                self.stations.append({"id": s_id, "sta": tr.stats.station})
                self.sta_sel.addItem(s_id)
                seen.add(s_id)
        self.update_plots()
        self.update_table()

    def _setup_after_load_minimal(self):
        seen = set()
        self.sta_sel.clear()
        self.stations = []
        for tr in self.original_stream:
            s_id = f"{tr.stats.network}.{tr.stats.station}"
            if s_id not in seen:
                self.stations.append({"id": s_id, "sta": tr.stats.station})
                self.sta_sel.addItem(s_id)
                seen.add(s_id)

    def prev_station(self):
        current = self.sta_sel.currentIndex()
        if current > 0:
            self.sta_sel.setCurrentIndex(current - 1)
    
    def next_station(self):
        current = self.sta_sel.currentIndex()
        if current < self.sta_sel.count() - 1:
            self.sta_sel.setCurrentIndex(current + 1)

    def reset_view(self):
        if not self.original_stream or not self.plots:
            return

        self.v_zoom.setValue(1)

        max_dur = 0
        for tr in self.original_stream:
            dur = tr.stats.npts * tr.stats.delta
            if dur > max_dur:
                max_dur = dur

        for p in self.plots:
            p.setXRange(0, max_dur, padding=0)

        self.update_gain()

    def update_plots(self):
        if not self.original_stream:
            return
        self.win.clear()
        self.plots = []

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
            if sta_idx < 0:
                return
            target_sta = [self.stations[sta_idx]["sta"]]
            self.sta_sel.setEnabled(True)
            self.btn_prev.setEnabled(True)
            self.btn_next.setEnabled(True)
            total_height = self.scroll.height() - 20
        else:
            target_sta = sorted(list(set(tr.stats.station for tr in proc_st)))
            self.sta_sel.setEnabled(False)
            self.btn_prev.setEnabled(False)
            self.btn_next.setEnabled(False)
            num_traces = sum([len(proc_st.select(station=s)) for s in target_sta])
            total_height = (num_traces * 150) + (len(target_sta) * 40)

        self.win.setMinimumHeight(max(total_height, 400))

        first_p = None
        current_row = 0

        for station in target_sta:
            traces = proc_st.select(station=station)
            traces = sorted(traces, key=lambda x: x.stats.channel[-1], reverse=True)

            title = pg.LabelItem(f"<b>STATION: {station}</b>", size="12pt")
            self.win.addItem(title, row=current_row, col=0)
            current_row += 1

            for tr in traces:
                p = self.win.addPlot(row=current_row, col=0)
                current_row += 1

                if first_p is None:
                    first_p = p
                else:
                    p.setXLink(first_p)

                chan_name = tr.stats.channel.upper()[-3:]
                if "Z" in chan_name:
                    ch = "Z"
                elif "N" in chan_name:
                    ch = "N"
                elif "E" in chan_name:
                    ch = "E"
                else:
                    ch = "gray"
                color = (
                    {"Z": "#e74c3c", "N": "#f1c40f", "E": "#3498db"}.get(ch, "gray")
                    if self.color_mode.currentIndex() == 0
                    else self.fg_color
                )

                if self.view_wave.isChecked():
                    max_duration = tr.stats.npts * tr.stats.delta
                    data_max = np.max(np.abs(tr.data)) if len(tr.data) > 0 else 1

                    p.setLimits(
                        xMin=0,
                        xMax=max_duration,
                        yMin=-data_max * 10,
                        yMax=data_max * 10,
                    )
                    p.setXRange(0, max_duration, padding=0)

                    p.plot(tr.times(), tr.data, pen=pg.mkPen(color, width=1.2))

                    p.meta = {
                        "sta": tr.stats.station,
                        "cha": tr.stats.channel,
                        "st": tr.stats.starttime,
                    }

                    for pk in self.picks:
                        if pk["sta"] == tr.stats.station:
                            t_rel = UTCDateTime(pk["abs_t"]) - tr.stats.starttime
                            if 0 <= t_rel <= max_duration:
                                self._add_visual_pick(p, t_rel, pk["phase"])
                else:
                    f, s = utils.get_spectrum(tr)
                    f_max = tr.stats.sampling_rate / 2
                    p.setLimits(xMin=0, xMax=f_max)
                    p.setXRange(0, f_max, padding=0)
                    p.plot(f, s, pen=pg.mkPen(color))
                    scale = self.spec_scale.currentText()
                    p.setLogMode("Log" in scale.split("-")[0], "Log" in scale.split("-")[1])

                label = pg.TextItem(
                    f"{tr.stats.channel}", color=color, anchor=(1, 0)
                )
                p.addItem(label)
                label.setParentItem(p.vb)
                label.setPos(p.vb.boundingRect().width()-20, 0)

                self.plots.append(p)

            self.win.nextRow()
            current_row += 1

        self.update_gain()

    def _add_visual_pick(self, plot, x_pos, label):
        color = "#8e44ad"
        line = pg.InfiniteLine(
            pos=x_pos,
            angle=90,
            pen=pg.mkPen(color, width=1.5, style=Qt.PenStyle.DashLine),
        )
        plot.addItem(line)
        text = pg.TextItem(label, color=color, anchor=(0, 1))
        text.setPos(x_pos, 0)
        plot.addItem(text)

    def on_plot_click(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.view_wave.isChecked():
            for p in self.plots:
                if p.sceneBoundingRect().contains(event.scenePos()):
                    mouse_point = p.vb.mapSceneToView(event.scenePos())
                    phase = self.ph_sel.currentText()
                    if phase == "Custom":
                        phase = self.ph_custom.text() or ""
                    abs_t = p.meta["st"] + mouse_point.x()
                    self.picks.append(
                        {
                            "sta": p.meta["sta"],
                            "cha_source": p.meta["cha"],
                            "phase": phase,
                            "abs_t": str(abs_t),
                        }
                    )
                    self.update_table()
                    self.update_plots()
                    event.accept()
                    break

    def update_table(self):
        self.table.setRowCount(len(self.picks))
        for i, pk in enumerate(self.picks):
            self.table.setItem(i, 0, QTableWidgetItem(pk["sta"]))
            self.table.setItem(i, 1, QTableWidgetItem(pk["cha_source"]))
            self.table.setItem(i, 2, QTableWidgetItem(pk["phase"]))
            self.table.setItem(i, 3, QTableWidgetItem(pk["abs_t"][-15:]))
            btn = QPushButton("Remove")
            btn.setStyleSheet("background-color: #a2292b; color: white;")
            btn.clicked.connect(lambda chk, idx=i: self.delete_pick(idx))
            self.table.setCellWidget(i, 4, btn)

    def delete_pick(self, idx):
        if 0 <= idx < len(self.picks):
            self.picks.pop(idx)
            self.update_table()
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
            "Confirm",
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
