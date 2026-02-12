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
    QButtonGroup,
    QCheckBox,
    QDoubleSpinBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSlider,
    QLineEdit,
    QFileDialog,
    QMessageBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette
import pyqtgraph as pg
from obspy import UTCDateTime, read, Stream
import picker_utils_qt as utils


class SeismicPickerQT(QMainWindow):
    def __init__(self, stream=None):
        super().__init__()
        self.setWindowTitle("Seismic Picker Pro")
        self.resize(1200, 850)

        self.original_stream = stream if stream else Stream()
        self.picks = []
        self.plots = []

        self.init_ui()
        self.apply_system_theme()

        if self.original_stream:
            self._setup_after_load()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # --- SIDEBAR ---
        sidebar = QVBoxLayout()

        btn_open = QPushButton("📂 Apri File SAC/mseed")
        btn_open.clicked.connect(self.open_files)
        sidebar.addWidget(btn_open)

        sidebar.addWidget(QLabel("<b>Stazione:</b>"))
        self.sta_sel = QComboBox()
        sidebar.addWidget(self.sta_sel)

        sidebar.addWidget(QLabel("<b>Visualizzazione:</b>"))
        self.view_wave = QRadioButton("Waveform")
        self.view_spec = QRadioButton("Spettro")
        self.view_wave.setChecked(True)
        sidebar.addWidget(self.view_wave)
        sidebar.addWidget(self.view_spec)

        sidebar.addWidget(QLabel("<b>Fase:</b>"))
        self.ph_sel = QComboBox()
        self.ph_sel.addItems(["P", "S", "Custom"])
        sidebar.addWidget(self.ph_sel)
        self.ph_custom = QLineEdit()
        self.ph_custom.setPlaceholderText("Altro...")
        sidebar.addWidget(self.ph_custom)

        sidebar.addWidget(QLabel("<b>Filtro BP (Hz):</b>"))
        self.f_low = QDoubleSpinBox()
        self.f_low.setValue(1.0)
        self.f_high = QDoubleSpinBox()
        self.f_high.setValue(20.0)
        sidebar.addWidget(self.f_low)
        sidebar.addWidget(self.f_high)

        sidebar.addWidget(QLabel("<b>Gain:</b>"))
        self.v_zoom = QSlider(Qt.Orientation.Horizontal)
        self.v_zoom.setRange(1, 100)
        self.v_zoom.setValue(1)
        sidebar.addWidget(self.v_zoom)

        sidebar.addStretch()

        self.btn_save_csv = QPushButton("📊 Esporta CSV")
        self.btn_save_csv.clicked.connect(self.export_csv)
        sidebar.addWidget(self.btn_save_csv)

        self.btn_save_sac = QPushButton("💾 Salva in Header SAC")
        self.btn_save_sac.clicked.connect(self.save_to_sac)
        self.btn_save_sac.setStyleSheet("background-color: #27ae60; color: white;")
        sidebar.addWidget(self.btn_save_sac)

        # --- AREA GRAFICA ---
        graph_area = QVBoxLayout()
        self.win = pg.GraphicsLayoutWidget()
        graph_area.addWidget(self.win, stretch=4)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["STA", "REF", "FASE", "TEMPO", "ELIMINA"])
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        graph_area.addWidget(self.table, stretch=1)

        main_layout.addLayout(sidebar, 1)
        main_layout.addLayout(graph_area, 4)

        # Segnali
        self.sta_sel.currentIndexChanged.connect(self.update_plots)
        self.view_wave.toggled.connect(self.update_plots)
        self.v_zoom.valueChanged.connect(self.update_gain)
        self.win.scene().sigMouseClicked.connect(self.on_plot_click)

    def apply_system_theme(self):
        palette = self.palette()
        bg = palette.color(QPalette.ColorRole.Window)
        fg = palette.color(QPalette.ColorRole.WindowText)
        pg.setConfigOption("background", bg)
        pg.setConfigOption("foreground", fg)
        self.win.setBackground(bg)

    def open_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Seleziona file sismici",
            "",
            "Seismic Files (*.sac *.mseed *.dat);;All Files (*)",
        )
        if files:
            new_st = Stream()
            for f in files:
                try:
                    tr = read(f)[0]
                    tr.stats.filename = f  # Conserviamo il path per il salvataggio
                    new_st += tr
                except:
                    continue

            if new_st:
                self.original_stream = new_st
                self._setup_after_load()

    def _setup_after_load(self):
        seen = set()
        self.sta_sel.clear()
        self.stations = []
        for tr in self.original_stream:
            s_id = f"{tr.stats.network}.{tr.stats.station}"
            if s_id not in seen:
                self.stations.append(
                    {"id": s_id, "net": tr.stats.network, "sta": tr.stats.station}
                )
                self.sta_sel.addItem(s_id)
                seen.add(s_id)
        self.update_plots()

    def update_plots(self):
        if not self.original_stream:
            return
        self.win.clear()
        self.plots = []

        params = {
            "demean": True,
            "detrend": True,
            "filter_type": "bandpass",
            "low_f": self.f_low.value(),
            "high_f": self.f_high.value(),
        }

        proc_st = utils.apply_preprocessing(self.original_stream, params)
        sta_idx = self.sta_sel.currentIndex()
        if sta_idx < 0:
            return

        station = self.stations[sta_idx]
        traces = proc_st.select(station=station["sta"])
        traces = sorted(traces, key=lambda x: x.stats.channel[-1], reverse=True)

        first_p = None
        for i, tr in enumerate(traces):
            p = self.win.addPlot(row=i, col=0)
            if first_p:
                p.setXLink(first_p)
            else:
                first_p = p

            ch = tr.stats.channel[-1].upper()
            color = {"Z": "#e74c3c", "N": "#2ecc71", "E": "#3498db"}.get(ch, "gray")

            if self.view_wave.isChecked():
                p.plot(tr.times(), tr.data, pen=pg.mkPen(color, width=1.5))
                p.meta = {
                    "sta": tr.stats.station,
                    "cha": tr.stats.channel,
                    "st": tr.stats.starttime,
                }
                # Disegna i pick esistenti per questa stazione
                for pk in self.picks:
                    if pk["sta"] == tr.stats.station:
                        t_rel = UTCDateTime(pk["abs_t"]) - tr.stats.starttime
                        self._add_visual_pick(p, t_rel, pk["phase"])
            else:
                f, s = utils.get_spectrum(tr)
                p.plot(f, s, pen=pg.mkPen(color))

            self.plots.append(p)
        self.update_gain()

    def _add_visual_pick(self, plot, x_pos, label):
        color = "yellow" if label == "P" else "#f39c12"
        line = pg.InfiniteLine(
            pos=x_pos,
            angle=90,
            pen=pg.mkPen(color, width=2, style=Qt.PenStyle.DashLine),
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
                        phase = self.ph_custom.text()

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
                    self.update_plots()  # Refresh per mostrare su tutti i canali
                    break

    def update_table(self):
        self.table.setRowCount(len(self.picks))
        for i, pk in enumerate(self.picks):
            self.table.setItem(i, 0, QTableWidgetItem(pk["sta"]))
            self.table.setItem(i, 1, QTableWidgetItem(pk["cha_source"]))
            self.table.setItem(i, 2, QTableWidgetItem(pk["phase"]))
            self.table.setItem(i, 3, QTableWidgetItem(pk["abs_t"][-15:]))
            btn = QPushButton("🗑")
            btn.clicked.connect(lambda chk, idx=i: self.delete_pick(idx))
            self.table.setCellWidget(i, 4, btn)

    def delete_pick(self, idx):
        self.picks.pop(idx)
        self.update_table()
        self.update_plots()

    def update_gain(self):
        gain = self.v_zoom.value()
        for p in self.plots:
            items = p.listDataItems()
            if items:
                y = items[0].yData
                if y is not None:
                    amp = np.max(np.abs(y)) or 1
                    p.setYRange(-amp / gain, amp / gain)

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Esporta CSV", "picks.csv", "CSV Files (*.csv)"
        )
        if path:
            utils.export_to_csv(self.picks, path)
            QMessageBox.information(
                self, "Successo", "Picking esportati correttamente!"
            )

    def save_to_sac(self):
        reply = QMessageBox.question(
            self,
            "Conferma",
            "Questo sovrascriverà i file originali inserendo i pick negli header T0 (P) e T1 (S). Continuare?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            utils.save_picks_to_sac(self.original_stream, self.picks)
            QMessageBox.information(self, "Successo", "Header SAC aggiornati!")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SeismicPickerQT()
    window.show()
    sys.exit(app.exec())