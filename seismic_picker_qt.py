from numpy.ma import left_shift
import logging
import re
import sys
from pathlib import Path

# Ensure script and plugin directories are in sys.path for local module resolution
_app_dir = str(Path(__file__).resolve().parent)
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)
_config_plugins_dir = str(Path(__file__).resolve().parent / "config" / "plugins")
if _config_plugins_dir not in sys.path:
    sys.path.insert(0, _config_plugins_dir)
_plugins_dir = str(Path(__file__).resolve().parent / "plugins")
if _plugins_dir not in sys.path:
    sys.path.insert(0, _plugins_dir)

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
            return _orig_check_output(cmd, *args, **kwargs)  # ty: ignore[call-non-callable]
        subprocess.check_output = _safe_check_output  # ty: ignore[invalid-assignment]

logger = logging.getLogger(__name__)

__version__ = "2.0.0"

import numpy as np
import pyqtgraph as pg

# Prevent PyQtGraph AttributeError in PlotDataItem when getViewBox falls back to GraphicsView / GraphicsLayoutWidget
if not hasattr(pg.GraphicsView, "autoRangeEnabled"):
    pg.GraphicsView.autoRangeEnabled = lambda self: [False, False]  # ty: ignore[attr-defined]
if not hasattr(pg.GraphicsLayoutWidget, "autoRangeEnabled"):
    pg.GraphicsLayoutWidget.autoRangeEnabled = lambda self: [False, False]  # ty: ignore[attr-defined]
from obspy import Stream, UTCDateTime, read
from PyQt6.QtCore import QRectF, Qt, QTimer, QUrl
from PyQt6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QKeySequence,
    QPalette,
    QPixmap,
    QShortcut,
    QTextCursor,
    QTextDocument,
)
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

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


class Hypo71Dialog(QDialog):
    """
    Dedicated dialog for earthquake location using the hypo71py plugin.
    Displays pick summary, allows setting trial depth and velocity model,
    runs location, shows quality statistics and residuals, and allows
    saving relocated SAC files to h71_localized/ and applying in memory.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent  # ty: ignore[invalid-assignment]
        self.setWindowTitle("Hypo71 Earthquake Location")
        self.setWindowIcon(utils.get_app_icon("dark"))
        self.resize(850, 700)
        self.results = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 1. Picks & Stations Summary Box
        picks_group = QGroupBox("Available Picks & Station Coordinates")
        picks_layout = QVBoxLayout(picks_group)

        self.summary_label = QLabel("Loading picks...")
        self.summary_label.setStyleSheet("font-weight: bold; color: #2746ae;")
        picks_layout.addWidget(self.summary_label)

        self.picks_table = QTableWidget(0, 7)
        self.picks_table.setHorizontalHeaderLabels([
            "Station", "Phase", "Pick Time (UTC)", "Uncertainty (s)", "St. Lat (°)", "St. Lon (°)", "St. Elev (m)"
        ])
        self.picks_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)  # ty: ignore[unresolved-attribute]
        self.picks_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.picks_table.setMaximumHeight(160)
        picks_layout.addWidget(self.picks_table)
        layout.addWidget(picks_group)

        # 2. Solver Parameters Box
        param_group = QGroupBox("Location Parameters")
        param_layout = QHBoxLayout(param_group)

        param_layout.addWidget(QLabel("Trial Depth (ZTR km):"))
        self.ztr_spin = QDoubleSpinBox()
        self.ztr_spin.setRange(0.0, 200.0)
        self.ztr_spin.setValue(5.0)
        self.ztr_spin.setSingleStep(0.5)
        self.ztr_spin.setToolTip(
            "Initial starting hypocentral depth (ZTR) in km for the iterative Geiger inversion algorithm.\n"
            "This is the starting depth for the solver, not a displacement step."
        )
        param_layout.addWidget(self.ztr_spin)

        param_layout.addSpacing(15)
        self.model_info_label = QLabel("Velocity Model:")
        param_layout.addWidget(self.model_info_label)

        self.btn_edit_model = QPushButton("Edit Model")
        self.btn_edit_model.clicked.connect(self.on_edit_model)
        param_layout.addWidget(self.btn_edit_model)

        self.btn_reload_model = QPushButton("Reload")
        self.btn_reload_model.clicked.connect(self.on_reload_model)
        param_layout.addWidget(self.btn_reload_model)

        param_layout.addStretch()

        self.btn_run_loc = QPushButton("Run Location")
        self.btn_run_loc.setStyleSheet(
            "font-weight: bold; font-size: 13px; background-color: #27ae60; color: white; padding: 6px 14px;"
        )
        self.btn_run_loc.clicked.connect(self.run_location)
        param_layout.addWidget(self.btn_run_loc)

        layout.addWidget(param_group)

        # 3. Status Label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("font-weight: bold; padding: 2px;")
        layout.addWidget(self.status_label)

        # 4. Results Box
        results_group = QGroupBox("Hypocenter Solution & Quality")
        results_layout = QVBoxLayout(results_group)

        self.grid_results = QHBoxLayout()

        col1 = QVBoxLayout()
        self.lbl_lat = QLabel("Latitude: --")
        self.lbl_lon = QLabel("Longitude: --")
        self.lbl_depth = QLabel("Depth: --")
        self.lbl_time = QLabel("Origin Time: --")
        for lbl in (self.lbl_lat, self.lbl_lon, self.lbl_depth, self.lbl_time):
            lbl.setStyleSheet("font-size: 13px;")
            col1.addWidget(lbl)

        col2 = QVBoxLayout()
        self.lbl_rms = QLabel("RMS: --")
        self.lbl_erh = QLabel("ERH: --")
        self.lbl_erz = QLabel("ERZ: --")
        self.lbl_quality = QLabel("Quality (QSD): --")
        for lbl in (self.lbl_rms, self.lbl_erh, self.lbl_erz, self.lbl_quality):
            lbl.setStyleSheet("font-size: 13px;")
            col2.addWidget(lbl)

        self.grid_results.addLayout(col1)
        self.grid_results.addSpacing(30)
        self.grid_results.addLayout(col2)
        self.grid_results.addStretch()
        results_layout.addLayout(self.grid_results)

        layout.addWidget(results_group)

        # 5. Residuals Table
        res_group = QGroupBox("Phase Residuals")
        res_layout = QVBoxLayout(res_group)

        self.res_table = QTableWidget(0, 8)
        self.res_table.setHorizontalHeaderLabels([
            "Station", "Phase", "Obs Time", "Calc Time", "Res (s)", "Dist (km)", "Azimuth (°)", "Weight"
        ])
        self.res_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)  # ty: ignore[unresolved-attribute]
        self.res_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        res_layout.addWidget(self.res_table)
        layout.addWidget(res_group)

        # 6. Bottom Actions
        act_layout = QHBoxLayout()

        self.btn_save_localized = QPushButton("Save in h71_localized/")
        self.btn_save_localized.setStyleSheet("font-weight: bold; background-color: #2746ae; color: white;")
        self.btn_save_localized.setEnabled(False)
        self.btn_save_localized.clicked.connect(self.save_localized_files)
        act_layout.addWidget(self.btn_save_localized)

        self.btn_focmec = QPushButton("Focal Mechanism (FOCMEC)")
        self.btn_focmec.setStyleSheet("font-weight: bold; background-color: #16a085; color: white;")
        self.btn_focmec.setEnabled(False)
        self.btn_focmec.clicked.connect(self.open_focmec_from_loc)
        act_layout.addWidget(self.btn_focmec)

        act_layout.addStretch()

        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.close)
        act_layout.addWidget(self.btn_close)

        layout.addLayout(act_layout)

        self.on_reload_model()

    def open_focmec_from_loc(self):
        """Open FOCMEC dialog passing the resolved hypocenter."""
        if self.parent and hasattr(self.parent, "open_focmec_dialog"):
            self.parent.open_focmec_dialog(hypocenter=self.results)

    def on_edit_model(self):
        if self.parent:
            self.parent.open_velocity_model_file()  # ty: ignore[unresolved-attribute]

    def on_reload_model(self):
        try:
            vmod = utils.load_velocity_model()
            name = vmod.get("name", "1D Model")
            n_layers = len(vmod.get("layers", []))
            self.model_info_label.setText(f"<b>Model:</b> {name} ({n_layers} layers)")
        except Exception as e:  # noqa: BLE001
            self.model_info_label.setText(f"<b>Model:</b> Error ({e})")

    def refresh_picks(self):
        """Populate the picks table with current picks from parent."""
        if not self.parent:
            return

        stream = self.parent.original_stream  # ty: ignore[unresolved-attribute]
        picks = self.parent.picks  # ty: ignore[unresolved-attribute]

        coords = {}
        for tr in stream:
            sta = tr.stats.station
            if sta not in coords:
                sac = getattr(tr.stats, "sac", {})
                stla = sac.get("stla")
                stlo = sac.get("stlo")
                stel = sac.get("stel", 0.0)
                if stel == -12345.0 or stel is None:
                    stel = 0.0
                if stla is not None and stlo is not None and stla != -12345.0 and stlo != -12345.0:
                    coords[sta] = (float(stla), float(stlo), float(stel))

        p_count = sum(1 for p in picks if p.get("phase", "").upper() == "P")
        s_count = sum(1 for p in picks if p.get("phase", "").upper() == "S")
        sta_with_picks = {p.get("sta") for p in picks if p.get("phase", "").upper() in ("P", "S")}
        valid_sta = [s for s in sta_with_picks if s in coords]

        self.summary_label.setText(
            f"Picks: {len(picks)} (P: {p_count}, S: {s_count}) across {len(sta_with_picks)} stations. "
            f"Stations with coordinates: {len(valid_sta)}/{len(sta_with_picks)}."
        )

        self.picks_table.setRowCount(0)
        sorted_picks = sorted(picks, key=lambda x: (x.get("sta", ""), x.get("phase", ""), x.get("abs_t", "")))
        for p in sorted_picks:
            row = self.picks_table.rowCount()
            self.picks_table.insertRow(row)

            sta = p.get("sta", "")
            ph = p.get("phase", "")
            abs_t = str(p.get("abs_t", ""))
            unc = f"{float(p.get('uncertainty', 0.0)):.3f}"

            st_coord = coords.get(sta)
            stla_str = f"{st_coord[0]:.4f}" if st_coord else "Missing"
            stlo_str = f"{st_coord[1]:.4f}" if st_coord else "Missing"
            stel_str = f"{st_coord[2]:.1f}" if st_coord else "Missing"

            self.picks_table.setItem(row, 0, QTableWidgetItem(sta))
            self.picks_table.setItem(row, 1, QTableWidgetItem(ph))
            self.picks_table.setItem(row, 2, QTableWidgetItem(abs_t))
            self.picks_table.setItem(row, 3, QTableWidgetItem(unc))
            self.picks_table.setItem(row, 4, QTableWidgetItem(stla_str))
            self.picks_table.setItem(row, 5, QTableWidgetItem(stlo_str))
            self.picks_table.setItem(row, 6, QTableWidgetItem(stel_str))

    def run_location(self):
        """Execute hypo71 location solver."""
        if not self.parent:
            return

        try:
            from hypo71_plugin import run_hypo71_localization  # ty: ignore[unresolved-import]
        except ImportError:
            try:
                from config.plugins.hypo71_plugin import run_hypo71_localization
            except ImportError:
                try:
                    from plugins.hypo71_plugin import run_hypo71_localization  # ty: ignore[unresolved-import]
                except ImportError as e:
                    QMessageBox.critical(self, "Plugin Error", f"Could not import hypo71_plugin: {e}")
                    return

        ztr = self.ztr_spin.value()
        try:
            self.status_label.setText("Calculating hypocenter...")
            self.status_label.setStyleSheet("color: #2746ae; font-weight: bold;")
            QApplication.processEvents()

            res = run_hypo71_localization(
                self.parent.original_stream,  # ty: ignore[unresolved-attribute]
                self.parent.picks,  # ty: ignore[unresolved-attribute]
                ztr=ztr,
            )
            self.results = res

            lat = res["latitude"]
            lon = res["longitude"]
            depth = res["depth_km"]
            ot = res["origin_time"]
            rms = res["rms"]
            erh = res["erh"]
            erz = res["erz"]
            qsd = res["quality"]
            ni = res["iterations"]

            self.lbl_lat.setText(f"<b>Latitude:</b> {lat:.4f} °")
            self.lbl_lon.setText(f"<b>Longitude:</b> {lon:.4f} °")
            self.lbl_depth.setText(f"<b>Depth:</b> {depth:.2f} km (ERZ: ±{erz:.2f} km)")
            self.lbl_time.setText(f"<b>Origin Time:</b> {ot.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} UTC")

            self.lbl_rms.setText(f"<b>RMS:</b> {rms:.3f} s")
            self.lbl_erh.setText(f"<b>ERH:</b> ±{erh:.2f} km")
            self.lbl_erz.setText(f"<b>ERZ:</b> ±{erz:.2f} km")
            self.lbl_quality.setText(f"<b>Quality (QSD):</b> {qsd} ({ni} iterations, {res['phases_used']} phases)")

            self.res_table.setRowCount(0)
            for r in res.get("residuals", []):
                row = self.res_table.rowCount()
                self.res_table.insertRow(row)

                sta = r.get("station", "")
                ph = r.get("phase", "")
                obs = r.get("observed_time")
                calc = r.get("calculated_time")
                res_sec = r.get("residual_sec")
                dist = r.get("distance_km", 0.0)
                az = r.get("azimuth_deg", 0.0)
                wt = r.get("weight", 0.0)

                obs_str = obs.strftime("%H:%M:%S.%f")[:-3] if obs else "--"
                calc_str = calc.strftime("%H:%M:%S.%f")[:-3] if calc else "--"
                res_str = f"{res_sec:+.3f}" if res_sec is not None else "--"
                dist_str = f"{dist:.2f}"
                az_str = f"{az:.1f}"
                wt_str = f"{wt:.2f}"

                self.res_table.setItem(row, 0, QTableWidgetItem(sta))
                self.res_table.setItem(row, 1, QTableWidgetItem(ph))
                self.res_table.setItem(row, 2, QTableWidgetItem(obs_str))
                self.res_table.setItem(row, 3, QTableWidgetItem(calc_str))

                res_item = QTableWidgetItem(res_str)
                if res_sec is not None and abs(res_sec) > 0.5:
                    res_item.setForeground(pg.mkColor("#e74c3c"))
                self.res_table.setItem(row, 4, res_item)

                self.res_table.setItem(row, 5, QTableWidgetItem(dist_str))
                self.res_table.setItem(row, 6, QTableWidgetItem(az_str))
                self.res_table.setItem(row, 7, QTableWidgetItem(wt_str))

            self.status_label.setText(
                f"Location completed successfully in {ni} iterations! RMS = {rms:.3f} s."
            )
            self.status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
            self.btn_save_localized.setEnabled(True)
            self.btn_focmec.setEnabled(True)

            # Update SAC headers (coordinates, depth, origin time, distance) and auto-sort waveforms by distance
            if self.parent and hasattr(self.parent, "original_stream") and self.parent.original_stream:
                streams_to_update = [self.parent.original_stream]
                if hasattr(self.parent, "base_stream") and self.parent.base_stream:
                    streams_to_update.append(self.parent.base_stream)

                for st_target in streams_to_update:
                    for tr in st_target:  # ty: ignore[not-iterable]
                        if not hasattr(tr.stats, "sac"):
                            tr.stats.sac = {}
                        sac = tr.stats.sac
                        sac["evla"] = float(lat)
                        sac["evlo"] = float(lon)
                        sac["evdp"] = float(depth)
                        b = float(sac.get("b", 0.0))
                        if b == -12345.0 or b is None:
                            b = 0.0
                        ref_start = tr.stats.starttime - b
                        sac["o"] = float(ot - ref_start)

                        stla = sac.get("stla")
                        stlo = sac.get("stlo")
                        if stla is not None and stlo is not None and stla != -12345.0 and stlo != -12345.0:
                            dist_m, az, baz = utils.gps2dist_azimuth(float(lat), float(lon), float(stla), float(stlo))
                            sac["dist"] = float(dist_m / 1000.0)
                            sac["az"] = float(az)
                            sac["baz"] = float(baz)
                            sac["gcarc"] = float(utils.locations2degrees(float(lat), float(lon), float(stla), float(stlo)))

                self.parent.original_stream = utils.reorder_stream_by_distance(self.parent.original_stream)  # ty: ignore[invalid-assignment]
                if hasattr(self.parent, "sort_sel"):
                    self.parent.sort_sel.blockSignals(True)  # ty: ignore[unresolved-attribute]
                    self.parent.sort_sel.setCurrentText("By Distance")  # ty: ignore[unresolved-attribute]
                    self.parent.sort_sel.blockSignals(False)  # ty: ignore[unresolved-attribute]

                if hasattr(self.parent, "show_theo") and not self.parent.show_theo.isChecked():  # ty: ignore[unresolved-attribute]
                    self.parent.show_theo.setChecked(True)  # ty: ignore[unresolved-attribute]

                self.parent._setup_after_load()  # ty: ignore[unresolved-attribute]

            if hasattr(self.parent, "_map_dialog") and self.parent._map_dialog:
                try:
                    self.parent._map_dialog.update_event_location(lat, lon, depth, ot)  # ty: ignore[unresolved-attribute]
                except Exception as e:  # noqa: BLE001
                    logger.debug(f"Could not update map event location: {e}")

            # Update GIS Seismic Catalog (.txt)
            try:
                cfg = getattr(self.parent, "config", {}) if self.parent else {}
                cat_path = utils.get_default_catalog_path(cfg)
                ev_id = getattr(self.parent, "current_event_id", None)
                if not ev_id:
                    ev_id = utils.get_or_create_event_id(
                        getattr(self.parent, "original_stream", None),
                        picks=getattr(self.parent, "picks", None),
                        hypocenter=res,
                    )
                    if self.parent:
                        self.parent.current_event_id = ev_id

                vmod_name = utils.load_velocity_model().get("name", "1D Model")

                cat_event = {
                    "Event_ID": ev_id,
                    "Origin_Time_UTC": ot,
                    "Latitude": lat,
                    "Longitude": lon,
                    "Depth_km": depth,
                    "RMS_sec": rms,
                    "ERH_km": erh,
                    "ERZ_km": erz,
                    "Quality_Loc": qsd,
                    "Phases_Used": res.get("phases_used", 0),
                    "Stations_Used": len(set(r.get("station") for r in res.get("residuals", []) if r.get("station"))),
                    "Velocity_Model": vmod_name,
                }
                actual_cat_path = utils.update_seismic_catalog(cat_path, cat_event)
                self.status_label.setText(
                    f"Location completed ({qsd}, RMS={rms:.3f}s)! Catalog updated: {actual_cat_path.name}"
                )
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Could not update seismic catalog: {e}")

        except Exception as exc:  # noqa: BLE001
            self.status_label.setText(f"Error: {exc}")
            self.status_label.setStyleSheet("color: #c0392b; font-weight: bold;")
            QMessageBox.critical(self, "Location Error", f"Failed to compute earthquake location:\n\n{exc}")

    def save_localized_files(self):
        """Save SAC files with relocated hypocenter into h71_localized/ directory."""
        if not self.results or not self.parent:
            return

        try:
            saved = utils.update_sac_headers_with_location(
                self.parent.original_stream,  # ty: ignore[unresolved-attribute]
                evla=self.results["latitude"],
                evlo=self.results["longitude"],
                depth_km=self.results["depth_km"],
                origin_time=self.results["origin_time"],
                suffix="_hypo71",
                picks=getattr(self.parent, "picks", None),
            )
            if saved:
                save_dir = saved[0].parent
                QMessageBox.information(
                    self,
                    "Files Saved",
                    f"Successfully saved {len(saved)} relocated SAC files in:\n{save_dir}\n\nOriginal files were NOT modified."
                )
            else:
                QMessageBox.warning(
                    self,
                    "No Files Saved",
                    "No file paths associated with current stream traces."
                )
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Save Error", f"Error saving relocated files:\n\n{e}")

    def apply_to_memory(self):
        """Apply relocated hypocenter to in-memory traces and refresh theoretical arrival lines."""
        if not self.results or not self.parent:
            return

        try:
            evla = self.results["latitude"]
            evlo = self.results["longitude"]
            depth_km = self.results["depth_km"]
            origin_time = self.results["origin_time"]

            for st in (self.parent.original_stream, getattr(self.parent, "base_stream", None), getattr(self.parent, "stream", None)):  # ty: ignore[unresolved-attribute]
                if not st:
                    continue
                for tr in st:
                    if not hasattr(tr.stats, "sac"):
                        tr.stats.sac = {}
                    sac = tr.stats.sac
                    sac["evla"] = float(evla)
                    sac["evlo"] = float(evlo)
                    sac["evdp"] = float(depth_km)

                    b = float(sac.get("b", 0.0))
                    if b == -12345.0:
                        b = 0.0
                    ref_start = tr.stats.starttime - b
                    sac["o"] = float(origin_time - ref_start)

                    stla = sac.get("stla")
                    stlo = sac.get("stlo")
                    if (
                        stla is not None
                        and stlo is not None
                        and stla != -12345.0
                        and stlo != -12345.0
                    ):
                        dist_m, az, baz = utils.gps2dist_azimuth(float(evla), float(evlo), float(stla), float(stlo))
                        sac["dist"] = float(dist_m / 1000.0)
                        sac["az"] = float(az)
                        sac["baz"] = float(baz)
                        sac["gcarc"] = float(utils.locations2degrees(float(evla), float(evlo), float(stla), float(stlo)))

            if hasattr(self.parent, "show_theo") and not self.parent.show_theo.isChecked():  # ty: ignore[unresolved-attribute]
                self.parent.show_theo.setChecked(True)  # ty: ignore[unresolved-attribute]

            if hasattr(self.parent, "_map_dialog") and self.parent._map_dialog:
                try:
                    self.parent._map_dialog.update_event_location(evla, evlo, depth_km, origin_time)  # ty: ignore[unresolved-attribute]
                except Exception as e:  # noqa: BLE001
                    logger.debug(f"Could not update map event location: {e}")

            # Automatically sort waveforms by distance
            self.parent.original_stream = utils.reorder_stream_by_distance(self.parent.original_stream)  # ty: ignore[invalid-assignment, unresolved-attribute]
            if hasattr(self.parent, "sort_sel"):
                self.parent.sort_sel.blockSignals(True)  # ty: ignore[unresolved-attribute]
                self.parent.sort_sel.setCurrentText("By Distance")  # ty: ignore[unresolved-attribute]
                self.parent.sort_sel.blockSignals(False)  # ty: ignore[unresolved-attribute]
            self.parent._setup_after_load()  # ty: ignore[unresolved-attribute]

            self.parent.update_plots()  # ty: ignore[unresolved-attribute]
            QMessageBox.information(
                self,
                "Applied to Memory",
                "Relocated hypocenter applied to in-memory traces.\n"
                "Traces have been sorted by epicentral distance and theoretical arrivals are displayed."
            )
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Apply Error", f"Error applying hypocenter to memory:\n\n{e}")


class DocumentationViewerDialog(QDialog):
    """
    In-app markdown documentation viewer allowing users to browse, navigate,
    and search through all PyPicker documentation files directly inside the application.
    """
    def __init__(self, parent=None, initial_doc="README.md"):
        super().__init__(parent)
        self.setWindowTitle("PyPicker - Documentation Viewer")
        self.setWindowIcon(utils.get_app_icon("dark"))
        self.resize(1020, 740)
        self.doc_dir = utils.get_doc_dir()
        self.history = []
        self.history_idx = -1
        self._navigating_history = False

        self.docs_map = [
            ("1. Overview", "README.md"),
            ("2. Installation Guide", "installation.md"),
            ("3. Configuration & Preferences", "configuration.md"),
            ("4. Waveform Analysis", "waveform_analysis.md"),
            ("5. Arrival Picking Guide", "picking_guide.md"),
            ("6. Plugin Architecture", "plugin_system.md"),
            ("7. Hypocentral Location (Hypo71)", "hypo71_localization.md"),
            ("8. Focal Mechanism (FOCMEC)", "focmec_focal_mechanism.md"),
            ("9. Geographic Map & Stations", "geographic_map.md"),
            ("10. Building & Releases", "building_and_release.md"),
        ]

        self.init_ui()

        # Configure search paths so relative image paths resolve properly
        paths = [str(self.doc_dir.resolve()), str(self.doc_dir.parent.resolve())]
        icon_dir = utils.get_icon_dir()
        if icon_dir.exists():
            paths.append(str(icon_dir.resolve()))
        self.browser.setSearchPaths(paths)

        self.load_doc(initial_doc)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Panel: Document Index
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        lbl_index = QLabel("<b>Documentation Index</b>")
        left_layout.addWidget(lbl_index)

        self.doc_list = QListWidget()
        for title, filename in self.docs_map:
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, filename)
            self.doc_list.addItem(item)

        self.doc_list.currentItemChanged.connect(self._on_item_changed)
        left_layout.addWidget(self.doc_list)
        left_widget.setMaximumWidth(280)
        left_widget.setMinimumWidth(200)

        # Right Panel: Viewer & Controls
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        # Top Control Bar
        bar = QHBoxLayout()
        bar.setSpacing(6)

        self.btn_back = QPushButton("◀ Back")
        self.btn_back.setEnabled(False)
        self.btn_back.clicked.connect(self.navigate_back)
        bar.addWidget(self.btn_back)

        self.btn_forward = QPushButton("Forward ▶")
        self.btn_forward.setEnabled(False)
        self.btn_forward.clicked.connect(self.navigate_forward)
        bar.addWidget(self.btn_forward)

        bar.addSpacing(10)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Find in document...")
        self.search_input.returnPressed.connect(self.search_text)
        bar.addWidget(self.search_input)

        self.btn_search = QPushButton("Find")
        self.btn_search.clicked.connect(self.search_text)
        bar.addWidget(self.btn_search)

        bar.addSpacing(10)
        self.btn_zoom_in = QPushButton("A+")
        self.btn_zoom_in.setToolTip("Increase font size")
        self.btn_zoom_in.clicked.connect(lambda: self.browser.zoomIn(1))
        bar.addWidget(self.btn_zoom_in)

        self.btn_zoom_out = QPushButton("A-")
        self.btn_zoom_out.setToolTip("Decrease font size")
        self.btn_zoom_out.clicked.connect(lambda: self.browser.zoomOut(1))
        bar.addWidget(self.btn_zoom_out)

        self.btn_external = QPushButton("Open locally")
        self.btn_external.setToolTip("Open currently displayed document in local default software")
        self.btn_external.clicked.connect(self.open_in_browser)
        bar.addWidget(self.btn_external)

        right_layout.addLayout(bar)

        # Markdown Browser
        self.browser = QTextBrowser()
        self.browser.setOpenLinks(False)
        self.browser.anchorClicked.connect(self._on_anchor_clicked)
        self.browser.setStyleSheet("""
            QTextBrowser {
                padding: 12px;
                selection-background-color: #2746ae;
                selection-color: white;
            }
        """)
        right_layout.addWidget(self.browser, stretch=1)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)

    def load_doc(self, filename):
        file_path = self.doc_dir / filename
        if not file_path.exists():
            file_path = Path("doc") / filename
        if not file_path.exists():
            self.browser.setHtml(f"<h3>Document not found</h3><p>{file_path}</p>")
            return

        try:
            content = file_path.read_text(encoding="utf-8")
            self.current_filename = filename
            self.current_path = file_path

            # Clean and normalize Markdown for Qt's QTextBrowser renderer:
            # 1. Convert <picture> tags to markdown images
            content = re.sub(
                r'<picture>[\s\S]*?<img\s+src=[\"\']([^\"\']+)[\"\'][^>]*>[\s\S]*?</picture>',
                r'![\1](\1)',
                content
            )
            # 2. Convert raw <img src="..."> tags to standard markdown ![]()
            def _repl_img(match):
                tag = match.group(0)
                src_m = re.search(r'src=[\"\']([^\"\']+)[\"\']', tag)
                alt_m = re.search(r'alt=[\"\']([^\"\']+)[\"\']', tag)
                src = src_m.group(1) if src_m else ''
                alt = alt_m.group(1) if alt_m else ''
                return f'![{alt}]({src})'
            content = re.sub(r'<img\s+[^>]*>', _repl_img, content)

            # 3. Strip HTML layout tags that break Qt markdown parsing
            content = re.sub(r'</?(?:p|div|span|center|picture|source)[^>]*>', '', content)
            # 4. Remove standalone unrendered <a href=...><img ...></a>
            content = re.sub(r'<a\s+href=[\"\'][^\"\']*[\"\']>\s*(!\[[^\]]*\]\([^\)]+\))\s*</a>', r'\1', content)

            self.browser.setMarkdown(content)
            self._scale_document_images()

            # Update selected item in doc_list without triggering signal recursion
            self.doc_list.blockSignals(True)
            for i in range(self.doc_list.count()):
                item = self.doc_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == filename:  # ty: ignore[unresolved-attribute]
                    self.doc_list.setCurrentItem(item)
                    break
            self.doc_list.blockSignals(False)

            if not self._navigating_history:
                if self.history_idx < len(self.history) - 1:
                    self.history = self.history[:self.history_idx + 1]
                self.history.append(filename)
                self.history_idx = len(self.history) - 1

            self._update_history_buttons()

        except Exception as e:  # noqa: BLE001
            self.browser.setHtml(f"<h3>Error loading document</h3><p>{e}</p>")

    def _scale_document_images(self, max_width=720):
        """Fit oversized embedded images within the readable viewing area of the text browser."""
        doc = self.browser.document()
        cursor = QTextCursor(doc)
        while not cursor.atEnd():
            cursor.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor)
            fmt = cursor.charFormat()
            if fmt.isImageFormat():
                img_fmt = fmt.toImageFormat()
                name = img_fmt.name()
                img_var = doc.resource(QTextDocument.ResourceType.ImageResource, QUrl(name))  # ty: ignore[unresolved-attribute]
                if img_var is not None and not img_var.isNull():
                    orig_w = img_var.width()
                    orig_h = img_var.height()
                    target_max = 240 if "logo" in name.lower() else max_width
                    if orig_w > target_max:
                        ratio = target_max / float(orig_w)
                        img_fmt.setWidth(target_max)
                        img_fmt.setHeight(orig_h * ratio)
                        cursor.setCharFormat(img_fmt)
            cursor.clearSelection()

    def _on_item_changed(self, current, previous):
        if current:
            filename = current.data(Qt.ItemDataRole.UserRole)
            if filename:
                self.load_doc(filename)

    def _on_anchor_clicked(self, url):
        url_str = url.toString()
        if url.scheme() in ("http", "https"):
            QDesktopServices.openUrl(url)
            return

        # Handle local links
        clean = url_str.lstrip("./")
        anchor = None
        if "#" in clean:
            parts = clean.split("#", 1)
            clean, anchor = parts[0], parts[1]

        # Check if link points to a media/video file or file in filesystem
        local_cand = (self.doc_dir / clean) if (self.doc_dir / clean).exists() else (Path(clean) if Path(clean).exists() else None)
        if local_cand and local_cand.suffix.lower() in (".mp4", ".mkv", ".avi", ".mov", ".gif", ".png", ".jpg", ".pdf"):
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(local_cand.resolve())))
            return

        target_file = clean if clean.endswith(".md") else f"{clean}.md" if clean else self.current_filename
        if target_file and (self.doc_dir / target_file).exists():
            self.load_doc(target_file)
            if anchor:
                self.browser.scrollToAnchor(anchor)
        elif anchor:
            self.browser.scrollToAnchor(anchor)
        else:
            QDesktopServices.openUrl(url)

    def navigate_back(self):
        if self.history_idx > 0:
            self.history_idx -= 1
            self._navigating_history = True
            self.load_doc(self.history[self.history_idx])
            self._navigating_history = False
            self._update_history_buttons()

    def navigate_forward(self):
        if self.history_idx < len(self.history) - 1:
            self.history_idx += 1
            self._navigating_history = True
            self.load_doc(self.history[self.history_idx])
            self._navigating_history = False
            self._update_history_buttons()

    def _update_history_buttons(self):
        self.btn_back.setEnabled(self.history_idx > 0)
        self.btn_forward.setEnabled(self.history_idx < len(self.history) - 1)

    def search_text(self):
        query = self.search_input.text().strip()
        if not query:
            return
        found = self.browser.find(query)
        if not found:
            # Wrap around to start of document
            cursor = self.browser.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            self.browser.setTextCursor(cursor)
            self.browser.find(query)

    def open_in_browser(self):
        if hasattr(self, "current_path") and self.current_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.current_path)))


class SeismicPickerQT(QMainWindow):
    def __init__(self, stream=None):
        super().__init__()
        self.config = utils.load_config()
        self.setWindowTitle("PyPicker - Seismic Waveform Analyzer")
        self.setWindowIcon(utils.get_app_icon("dark"))
        self.resize(1200, 900)

        # Data initialization
        if stream:
            self.base_stream = stream.copy()
            self.original_stream = utils.reorder_stream_by_name(stream)
        else:
            self.original_stream = Stream()
            self.base_stream = Stream()
        self.picks = []
        self.plots = []
        self.stations = []
        self.current_event_id = None
        self._scalo_cache = {}
        self._proc_cache = {}
        self._theo_cache = None

        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(250)
        self._filter_timer.timeout.connect(self._on_filter_timer_timeout)

        # Picking state
        self.active_pick_items = None  # The visual LinearRegionItem
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
        # --- MENU BAR ---
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu("&File")  # ty: ignore[unresolved-attribute]
        act_open = file_menu.addAction("&Open Waveforms...")  # ty: ignore[unresolved-attribute]
        act_open.triggered.connect(self.open_files)  # ty: ignore[unresolved-attribute]
        act_save_sac = file_menu.addAction("&Save SAC...")  # ty: ignore[unresolved-attribute]
        act_save_sac.triggered.connect(self.save_to_sac)  # ty: ignore[unresolved-attribute]
        act_export_csv = file_menu.addAction("&Export Picks (CSV)...")  # ty: ignore[unresolved-attribute]
        act_export_csv.triggered.connect(self.export_picks)  # ty: ignore[unresolved-attribute]
        file_menu.addSeparator()  # ty: ignore[unresolved-attribute]
        act_exit = file_menu.addAction("E&xit")  # ty: ignore[unresolved-attribute]
        act_exit.triggered.connect(self.close)  # ty: ignore[unresolved-attribute]

        # Plugins Menu
        plugins_menu = menubar.addMenu("&Plugins")  # ty: ignore[unresolved-attribute]
        loc_key = self.config.get("shortcuts", {}).get("localize", "L")
        act_loc = plugins_menu.addAction(f"&Localize with Hypo71 ({loc_key})")  # ty: ignore[unresolved-attribute]
        act_loc.triggered.connect(self.open_hypo71_dialog)  # ty: ignore[unresolved-attribute]

        focmec_key = self.config.get("shortcuts", {}).get("focmec", "K")
        act_focmec = plugins_menu.addAction(f"&Focal Mechanism (FOCMEC) ({focmec_key})")  # ty: ignore[unresolved-attribute]
        act_focmec.triggered.connect(self.open_focmec_dialog)  # ty: ignore[unresolved-attribute]

        map_key = self.config.get("shortcuts", {}).get("open_map", "M")
        act_map = plugins_menu.addAction(f"&Geographic Map ({map_key})")  # ty: ignore[unresolved-attribute]
        act_map.triggered.connect(self.open_map_window)  # ty: ignore[unresolved-attribute]

        plugins_menu.addSeparator()  # ty: ignore[unresolved-attribute]
        act_open_plugins = plugins_menu.addAction("Open &Plugins Folder")  # ty: ignore[unresolved-attribute]
        act_open_plugins.triggered.connect(self.open_plugins_folder)  # ty: ignore[unresolved-attribute]

        act_edit_model = plugins_menu.addAction("&Edit Velocity Model")  # ty: ignore[unresolved-attribute]
        act_edit_model.triggered.connect(self.open_velocity_model_file)  # ty: ignore[unresolved-attribute]

        plugins_menu.addSeparator()  # ty: ignore[unresolved-attribute]
        act_open_cat = plugins_menu.addAction("Open Seismic &Catalog (.txt)")  # ty: ignore[unresolved-attribute]
        act_open_cat.triggered.connect(self.open_seismic_catalog)  # ty: ignore[unresolved-attribute]

        # Help Menu
        help_menu = menubar.addMenu("&Help")  # ty: ignore[unresolved-attribute]
        doc_key = self.config.get("shortcuts", {}).get("help_doc", "F1")
        act_doc = help_menu.addAction(f"&Documentation ({doc_key})")  # ty: ignore[unresolved-attribute]
        act_doc.triggered.connect(lambda: self.open_documentation_viewer("README.md"))  # ty: ignore[unresolved-attribute]
        help_menu.addSeparator()  # ty: ignore[unresolved-attribute]
        act_about = help_menu.addAction("&About PyPicker...")  # ty: ignore[unresolved-attribute]
        act_about.triggered.connect(self.show_about_dialog)  # ty: ignore[unresolved-attribute]

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(main_splitter)

        # --- LEFT SIDEBAR: Navigation & Display ---
        left_group = QGroupBox()
        left_group.setMinimumWidth(200)
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
        self.view_mode.addItems(["Single Station", "All Stations", "Focus Mode"])
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

        left_sidebar.addWidget(QLabel("<b>Scalogram duration:</b>"))
        self.scalo_duration = QDoubleSpinBox()
        self.scalo_duration.setRange(0.1, 10.0)
        self.scalo_duration.setDecimals(1)
        self.scalo_duration.setSingleStep(0.1)
        self.scalo_duration.setValue(self.config.get("defaults", {}).get("scalogram_duration", 1.0))
        self.scalo_duration.setKeyboardTracking(False)
        self.scalo_duration.setEnabled(False)
        left_sidebar.addWidget(self.scalo_duration)

        left_sidebar.addWidget(QLabel("<b>Color Mode:</b>"))
        self.color_mode = QComboBox()
        self.color_mode.addItems(["Channel-based", "Uniform"])
        left_sidebar.addWidget(self.color_mode)

        left_sidebar.addWidget(QLabel("<b>Theme:</b>"))
        self.theme_sel = QComboBox()
        self.theme_sel.addItems(["System", "Dark", "Light"])
        left_sidebar.addWidget(self.theme_sel)

        self.btn_reset = QPushButton("Reset Zoom")
        self.btn_reset.clicked.connect(self.reset_view)
        self.btn_reset.setStyleSheet(
            "font-weight: bold; background-color: #2746ae; color: white;"
        )
        left_sidebar.addWidget(self.btn_reset)

        left_sidebar.addStretch()

        left_sidebar.addWidget(QLabel("<b>Sort Stations:</b>"))
        self.sort_sel = QComboBox()
        self.sort_sel.addItems(["Original", "Alphabetical", "By Distance", "By Arrival"])
        self.sort_sel.setCurrentText("Alphabetical")
        self.sort_sel.currentIndexChanged.connect(self.sort_stations)
        left_sidebar.addWidget(self.sort_sel)

        self.btn_import_picks = QPushButton("Import Picks")
        self.btn_import_picks.clicked.connect(self.import_picks)
        self.btn_import_picks.setStyleSheet(
            "font-weight: bold; background-color: #2746ae; color: white;"
        )
        
        self.btn_export_picks = QPushButton("Export Picks")
        self.btn_export_picks.clicked.connect(self.export_picks)
        self.btn_export_picks.setStyleSheet(
            "font-weight: bold; background-color: #2746ae; color: white;"
        )

        left_sidebar.addWidget(self.btn_import_picks)
        left_sidebar.addWidget(self.btn_export_picks)

        self.btn_save_sac = QPushButton("Save as SAC")
        self.btn_save_sac.clicked.connect(self.save_to_sac)
        self.btn_save_sac.setStyleSheet(
            "font-weight: bold; background-color: #2746ae; color: white;"
        )
        
        left_sidebar.addWidget(self.btn_save_sac)
        left_group.setLayout(left_sidebar)

        # --- RIGHT SIDEBAR: Processing & Picking ---
        right_group = QGroupBox()
        right_group.setMinimumWidth(200)
        right_sidebar = QVBoxLayout()

        right_sidebar.addWidget(QLabel("<b>Correction:</b>"))
        self.rmmean = QCheckBox("Remove mean")
        self.detrend = QCheckBox("Remove trend")
        self.normalize = QCheckBox("Normalize waveform")
        right_sidebar.addWidget(self.rmmean)
        right_sidebar.addWidget(self.detrend)
        right_sidebar.addWidget(self.normalize)

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
        self.f_low.setKeyboardTracking(False)
        self.f_high = QDoubleSpinBox()
        self.f_high.setRange(0.01, 200)
        self.f_high.setValue(20.0)
        self.f_high.setKeyboardTracking(False)
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
        right_sidebar.addWidget(self.show_theo)

        right_sidebar.addStretch()

        # Configuration button
        self.btn_open_config = QPushButton("Open Configuration")
        self.btn_open_config.clicked.connect(self.open_config_folder)
        self.btn_open_config.setStyleSheet(
            "font-weight: bold; background-color: #2746ae; color: white;"
        )

        right_sidebar.addWidget(self.btn_open_config)
        # Shortcuts reminder card
        sc_group = QGroupBox("Shortcuts")
        sc_layout = QVBoxLayout()
        self.shortcuts_label = QLabel()
        self.shortcuts_label.setWordWrap(True)
        self.shortcuts_label.setTextFormat(Qt.TextFormat.RichText)
        sc_layout.addWidget(self.shortcuts_label)
        sc_group.setLayout(sc_layout)

        right_sidebar.addWidget(sc_group)
        right_group.setLayout(right_sidebar)

        # --- MAIN AREA: Graphics & Table ---
        center_widget = QWidget()
        graph_area = QVBoxLayout(center_widget)
        graph_area.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()  # ty: ignore[invalid-assignment]
        self.scroll.setWidgetResizable(True)
        self.win = pg.GraphicsLayoutWidget()
        self.scroll.setWidget(self.win)
        graph_area.addWidget(self.scroll, stretch=4)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            ["Sta", "Cha", "Phase", "Date", "Time", "Unc (s)", "Polarity", "Onset", "Action"]
        )
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(  # ty: ignore[unresolved-attribute]
            QHeaderView.ResizeMode.Stretch
        )
        graph_area.addWidget(self.table, stretch=1)

        main_splitter.addWidget(left_group)
        main_splitter.addWidget(center_widget)
        main_splitter.addWidget(right_group)
        main_splitter.setCollapsible(0, False)  # left_group
        main_splitter.setCollapsible(1, False)  # center_widget
        main_splitter.setCollapsible(2, False)  # right_group
        main_splitter.setSizes([250, 800, 250])

        # Signal connections
        self._connect_signals()

    def open_config_folder(self):
        folder = utils.get_config_dir()

        if not QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(folder))
        ):
            QMessageBox.warning(
                self,
                "Configuration Folder",
                f"Open the configuration folder:\n{folder}",
            )

    def _connect_signals(self):
        """Register events and UI updates."""
        self.view_mode.currentIndexChanged.connect(self._on_view_mode_changed)
        self.sta_sel.currentIndexChanged.connect(lambda: self.update_plots(reset_zoom=True))
        self.view_wave.toggled.connect(lambda: self.update_plots(reset_zoom=True))
        self.spec_scale.currentIndexChanged.connect(self.update_plots)
        self.color_mode.currentIndexChanged.connect(self.update_plots)
        self.rmmean.stateChanged.connect(self._on_filter_changed)
        self.detrend.stateChanged.connect(self._on_filter_changed)
        self.normalize.stateChanged.connect(self._on_filter_changed)
        self.filt_sel.currentIndexChanged.connect(self._on_filter_changed)
        self.f_low.valueChanged.connect(self._on_freq_changed)
        self.f_high.valueChanged.connect(self._on_freq_changed)
        self.show_theo.stateChanged.connect(self._on_theo_changed)
        self.theme_sel.currentTextChanged.connect(self.apply_theme)

        self.win.scene().sigMouseMoved.connect(self.on_mouse_move)  # ty: ignore[unresolved-attribute]
        self.win.scene().sigMouseClicked.connect(self.on_mouse_click_release)  # ty: ignore[unresolved-attribute]
        self.table.cellChanged.connect(self.on_table_cell_changed)
        self.table.cellDoubleClicked.connect(self.on_table_row_double_clicked)

        self._scalo_timer = QTimer(self)
        self._scalo_timer.setSingleShot(True)
        self._scalo_timer.setInterval(300)
        self._scalo_timer.timeout.connect(self.update_plots)
        self.scalo_duration.valueChanged.connect(lambda _: self._scalo_timer.start())

    def _on_filter_changed(self):
        self._proc_cache.clear()
        self.update_plots()

    def _on_freq_changed(self):
        self._filter_timer.start()

    def _on_filter_timer_timeout(self):
        self._proc_cache.clear()
        self.update_plots()

    def _on_theo_changed(self):
        self.update_pick_overlays()

    def _get_theoretical_arrivals(self):
        """Get theoretical arrivals for current stream, using cache when possible."""
        if not self.show_theo.isChecked():
            return {}
        model_name = self.config.get("defaults", {}).get("velocity_model", "")
        if not model_name or not self.original_stream:
            return {}
        if self._theo_cache is not None:
            return self._theo_cache
        try:
            self._theo_cache = utils.calculate_theoretical_arrivals(self.original_stream, model_name=model_name)
        except Exception as e:
            logger.debug(f"Error calculating theoretical arrivals: {e}")
            self._theo_cache = {}
        return self._theo_cache

    def _get_preprocessed_stream(self, raw_st, params):
        """Get preprocessed stream for given raw traces, using cache when possible."""
        p_key = (
            params.get("demean"),
            params.get("detrend"),
            params.get("normalize"),
            params.get("filter_type"),
            round(params.get("low_f", 1.0), 3),
            round(params.get("high_f", 20.0), 3),
        )
        proc_traces = []
        to_process = Stream()
        for tr in raw_st:
            t_key = (self._trace_key(tr), p_key)
            if t_key in self._proc_cache:
                proc_traces.append(self._proc_cache[t_key])
            else:
                to_process.append(tr)

        if to_process:
            new_proc = utils.apply_preprocessing(to_process, params)
            for tr_raw, tr_proc in zip(to_process, new_proc):
                t_key = (self._trace_key(tr_raw), p_key)
                self._proc_cache[t_key] = tr_proc
                proc_traces.append(tr_proc)

        return Stream(proc_traces)

    def _on_view_mode_changed(self):
        self._sync_view_widgets()
        if self.view_mode.currentText() == "Focus Mode":
            idx = self.filt_sel.findText("BandPass", Qt.MatchFlag.MatchStartsWith)
            if idx >= 0 and self.filt_sel.currentIndex() != idx:
                self.filt_sel.blockSignals(True)  # a single redraw, below
                self.filt_sel.setCurrentIndex(idx)
                self.filt_sel.blockSignals(False)
        self.update_plots(reset_zoom=True)

    def _sync_view_widgets(self):
        """Enable only the controls used by the current view mode."""
        detail = self.view_mode.currentText() == "Focus Mode"
        self.scalo_duration.setEnabled(detail)
        for w in (self.view_wave, self.view_spec, self.spec_scale):
            w.setEnabled(not detail)  # not used in Focus Mode

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
            "localize": self.open_hypo71_dialog,
            "focmec": self.open_focmec_dialog,
            "open_map": self.open_map_window,
            "help_doc": lambda: self.open_documentation_viewer("README.md"),
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
                app.setPalette(palette)  # ty: ignore[unresolved-attribute]
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
                app.setPalette(palette)  # ty: ignore[unresolved-attribute]
            self.setPalette(palette)
            self.setStyleSheet("")

        else: # System
            # Detect system dark/light appearance reliably
            is_dark = False
            # 1. Check Qt6 styleHints colorScheme if available
            try:
                hints = QApplication.styleHints()
                if hasattr(Qt, "ColorScheme"):
                    cs = hints.colorScheme()
                    if cs == Qt.ColorScheme.Dark:
                        is_dark = True
                    elif cs == Qt.ColorScheme.Light:
                        is_dark = False
                    else:
                        is_dark = None
            except Exception:
                is_dark = None

            # 2. Check freedesktop / GNOME dark theme setting via gsettings or XDG (Linux)
            if is_dark is None:
                import os, subprocess
                color_scheme_env = os.environ.get("QT_STYLE_OVERRIDE", "").lower()
                if "dark" in color_scheme_env:
                    is_dark = True
                else:
                    try:
                        out = subprocess.run(
                            ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                            capture_output=True, text=True, timeout=0.5
                        )
                        if "dark" in out.stdout.lower():
                            is_dark = True
                        elif "default" in out.stdout.lower() or "light" in out.stdout.lower():
                            is_dark = False
                    except Exception:
                        pass

            # 3. Fallback to standardPalette luminance
            if is_dark is None:
                std_pal = app.style().standardPalette() if app else self.style().standardPalette()
                win_col = std_pal.color(QPalette.ColorRole.Window)
                lum = 0.299 * win_col.red() + 0.587 * win_col.green() + 0.114 * win_col.blue()
                is_dark = lum < 128

            if is_dark:
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
                self.setStyleSheet("")
            else:
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
            "localize": "Hypo71 Location",
            "focmec": "Focal Mechanism (FOCMEC)",
            "open_map": "Geographic Map",
            "help_doc": "Documentation",
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

    def _trace_key(self, tr):
        """Identify a trace: same id, start time and length = same data."""
        return (tr.id, tr.stats.starttime.ns, tr.stats.npts)

    def _ask_load_mode(self, n_new):
        """Ask whether to add new traces to the session or replace it.
        Returns "append", "overwrite" or None (cancelled)."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Open Waveforms")
        box.setText(f"A session with {len(self.original_stream)} traces is already open.")
        box.setInformativeText(
            f"Add the {n_new} new traces to it, or replace the current session?"
        )
        btn_add = box.addButton("Add to session", QMessageBox.ButtonRole.AcceptRole)
        btn_over = box.addButton("Overwrite", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(btn_add)
        box.exec()

        clicked = box.clickedButton()
        if clicked is btn_add:
            return "append"
        if clicked is btn_over:
            return "overwrite"
        return None

    def open_files(self):
        "Load seismic data from disk"
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Waveforms",
            "",
            "Waveforms (*.sac *.mseed *.dat);;All Files (*)",)
        if files:
            new_st = Stream()
            for f in files:
                try:
                    st_file = read(f)
                    for tr in st_file:
                        tr.stats.filename = f
                        new_st += tr
                except Exception as e:  # noqa: BLE001
                    print(f"Error while loading waveforms: {e}")
                    continue

            if not new_st:
                return
            mode = "overwrite"
            if self.original_stream:
                mode = self._ask_load_mode(len(new_st))
                if mode is None:
                    return
            if mode == "overwrite":
                self._proc_cache.clear()
                self._theo_cache = None
                self._scalo_cache.clear()
                self.base_stream = new_st.copy()
                self.original_stream = utils.reorder_stream_by_name(new_st)
                self.picks = utils.extract_existing_picks(self.original_stream)
                self.current_event_id = utils.get_or_create_event_id(self.original_stream, picks=self.picks)
                if hasattr(self, "sort_sel"):
                    self.sort_sel.blockSignals(True)
                    self.sort_sel.setCurrentText("Alphabetical")
                    self.sort_sel.blockSignals(False)
                self._setup_after_load()
                return
            known = {self._trace_key(tr) for tr in self.original_stream}
            to_add = Stream()
            for tr in new_st:
                k = self._trace_key(tr)
                if k not in known:
                    known.add(k)
                    to_add.append(tr)
            n_skipped = len(new_st) - len(to_add)
            if not to_add:
                QMessageBox.information(
                    self, "Open Waveforms", 
                    "All selected traces are already in the session.")
                return
            
            base = getattr(self, "base_stream", None)
            if not base:
                base = self.original_stream.copy()
            base_keys = {self._trace_key(tr) for tr in base}
            base.extend([tr.copy() for tr in to_add if self._trace_key(tr) not in base_keys])
            self.base_stream = base
            self.original_stream.extend(to_add.traces)
            self._proc_cache.clear()
            self._theo_cache = None
            self._scalo_cache.clear()
            self.picks.extend(utils.extract_existing_picks(to_add))
            if hasattr(self, "sort_sel"):
                if self.sort_sel.currentText() == "Alphabetical":
                    self.original_stream = utils.reorder_stream_by_name(self.original_stream)
                elif self.sort_sel.currentText() == "By Distance":
                    self.original_stream = utils.reorder_stream_by_distance(self.original_stream)
            self._setup_after_load(target_idx=self.sta_sel.currentIndex())
            if n_skipped:
                QMessageBox.information(
                    self, "Open Waveforms", 
                    f"{n_skipped} duplicate traces were skipped.")

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
            self.current_event_id = None
            self._proc_cache.clear()
            self._theo_cache = None
            self._scalo_cache.clear()
            self.sta_sel.clear()
            self.table.setRowCount(0)
            for p in self.plots:
                try:
                    p.clear()
                except Exception:
                    pass
            self.win.clear()  # ty: ignore[unresolved-attribute]
            self.plots = []
            self.update_plots(reset_zoom=True)

    def _setup_after_load(self, target_idx=0):
        "Populate the station list after data loading"
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

        # Auto-fill missing station coordinates from configured FDSN client
        if self.original_stream:
            client_name = self.config.get("defaults", {}).get("station_client", "INGV")
            utils.autofill_missing_station_coordinates(self.original_stream, client_name=client_name)
            if hasattr(self, "base_stream") and self.base_stream:
                utils.autofill_missing_station_coordinates(self.base_stream, client_name=client_name)
            self._theo_cache = None

        if hasattr(self, "_map_dialog") and self._map_dialog:
            try:
                self._map_dialog.update_stream(self.original_stream)
            except Exception as e:  # noqa: BLE001
                logger.debug(f"Could not update map stream: {e}")

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
            self.base_stream = Stream(
                [tr for tr in self.base_stream if tr.stats.station != sta]
            )
            self.picks = [p for p in self.picks if p["sta"] != sta]
            self._setup_after_load(target_idx=idx)

    def rotate_phase(self):
        "Cycle between P-S phases"
        if self.ph_sel.currentText() == "S":
            self.ph_sel.setCurrentText("P")
        elif self.ph_sel.currentText() == "P":
            self.ph_sel.setCurrentText("S")
        else:
            self.ph_sel.setCurrentText("P")

    def update_plots(self, *args, reset_zoom=False):
        "Redraw all plots based on current filters and view mode"
        old_view_range = None
        if not reset_zoom and self.plots and self.view_wave.isChecked() and hasattr(self.plots[0], 'viewRange'):
            old_view_range = self.plots[0].viewRange()

        for p in self.plots:
            try:
                p.clear()
            except Exception:
                pass
        self.win.clear()  # ty: ignore[unresolved-attribute]
        self.plots = []
        if not self.original_stream or not self.stations:
            self.sta_count_label.setText("0/0")
            return

        params = {
            "demean": self.rmmean.isChecked(),
            "detrend": self.detrend.isChecked(),
            "normalize": self.normalize.isChecked(),
            "filter_type": self.filt_sel.currentText(),
            "low_f": self.f_low.value(),
            "high_f": self.f_high.value(),
        }

        if self.view_mode.currentText() == "Focus Mode":
            self._plot_detail(params, old_view_range)
            return

        mode = self.view_mode.currentText()
        theo_arrs = self._get_theoretical_arrivals()

        if mode == "Single Station":
            sta_idx = self.sta_sel.currentIndex()
            target_sta = [self.stations[sta_idx]["sta"]] if sta_idx >= 0 else []
            self.sta_count_label.setText(f"{sta_idx + 1}/{self.sta_sel.count()}")
            total_h = self.scroll.height() - 20  # ty: ignore[unresolved-attribute]
            raw_target_st = Stream([tr for tr in self.original_stream if tr.stats.station in target_sta])
            try:
                proc_st = self._get_preprocessed_stream(raw_target_st, params)
            except Exception as exc:
                logger.exception("Error in pre-processing signals")
                QMessageBox.critical(
                    self,
                    "Error in pre-processing signals",
                    f"{type(exc).__name__}: {exc}",
                )
                return
        else:
            try:
                proc_st = self._get_preprocessed_stream(self.original_stream, params)
            except Exception as exc:
                logger.exception("Error in pre-processing signals")
                QMessageBox.critical(
                    self,
                    "Error in pre-processing signals",
                    f"{type(exc).__name__}: {exc}",
                )
                return

            seen_sta = set()
            target_sta = []
            for s in self.stations:
                sta_name = s["sta"]
                if sta_name not in seen_sta and any(tr.stats.station == sta_name for tr in proc_st):
                    seen_sta.add(sta_name)
                    target_sta.append(sta_name)
            for tr in proc_st:
                if tr.stats.station not in seen_sta:
                    seen_sta.add(tr.stats.station)
                    target_sta.append(tr.stats.station)

            self.sta_count_label.setText("All")
            num_traces = sum([len(proc_st.select(station=s)) for s in target_sta])
            total_h = (num_traces * 150) + (len(target_sta) * 40)

        self.win.setMinimumHeight(max(total_h, 400))
        first_p = None
        current_row = 0

        for station in target_sta:
            traces = sorted(
                proc_st.select(station=station),
                key=lambda x: x.stats.channel[-1],
                reverse=True,
            )
            self.win.addItem(
                pg.LabelItem(f"<b>STATION: {station}</b>", size="12pt", color=self.fg_color),
                row=current_row,  # ty: ignore[unknown-argument]
                col=0,  # ty: ignore[unknown-argument]
            )
            current_row += 1

            for tr in traces:
                p = self.win.addPlot(row=current_row, col=0)  # ty: ignore[unresolved-attribute]
                current_row += 1
                if first_p is None:
                    first_p = p
                else:
                    p.setXLink(first_p)

                # Color logic
                color = self._trace_color(tr.stats.channel)

                if self.view_wave.isChecked():
                    self._plot_waveform(
                        p, tr, color, theo_arrs, old_view_range,
                        normalized=self.normalize.isChecked(),
                    )
                else:
                    # Spectrum view
                    f, s = utils.get_spectrum(tr)
                    if len(f) == 0 or len(s) == 0:
                        continue
                    scale = self.spec_scale.currentText()
                    log_x = "Log" in scale.split("-")[0]
                    log_y = "Log" in scale.split("-")[1]
                    p.setLogMode(x=log_x, y=log_y)
                    if log_x:
                        valid_x = f > 0
                        f_plot = f[valid_x]
                        s_plot = s[valid_x]
                    else:
                        f_plot, s_plot = f, s
                    if log_y and len(s_plot) > 0:
                        valid_y = s_plot > 0
                        f_plot = f_plot[valid_y]
                        s_plot = s_plot[valid_y]
                    if len(f_plot) == 0 or len(s_plot) == 0:
                        continue

                    f_min, f_max = np.min(f_plot), np.max(f_plot)
                    s_min, s_max = np.min(s_plot), np.max(s_plot)
                    p.plot(
                        f_plot,
                        s_plot,
                        pen=pg.mkPen(color),
                        autoDownsample=True,
                        downsampleMethod='peak',
                        clipToView=True,
                    )

                    if log_x:
                        p.setXRange(np.log10(f_min), np.log10(f_max), padding=0.05)
                        p.setLimits(xMin=np.log10(f_min) - 1, xMax=np.log10(f_max) + 1)
                    else:
                        p.setXRange(0, f_max, padding=0.02)
                        p.setLimits(xMin=0, xMax=f_max * 1.1)
                    
                    if log_y:
                        s_min_safe = s_min if s_min > 0 else 1e-6
                        p.setYRange(np.log10(s_min_safe), np.log10(s_max), padding=0.05)
                        p.setLimits(yMin=np.log10(s_min_safe) - 1, yMax=np.log10(s_max) + 1)
                    else:
                        p.setYRange(0, s_max * 1.05, padding=0)
                        p.setLimits(yMin=0, yMax=s_max * 1.5)

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

    def _trace_color(self, chan):
        "Colour of a channel according to the Color Mode combo"
        chan = chan.upper()
        if self.color_mode.currentIndex() == 0:
            colors_cfg = self.config.get("colors", {})
            color = colors_cfg.get(chan[-1], colors_cfg.get("other", "gray"))
            if chan[-1] == "N" and self._is_light_bg(getattr(self, "current_bg", "#1e1e1e")):
                color = "#b7950b"
            return color
        return self.fg_color

    def _plot_waveform(self, p, tr, color, theo_arrs, old_view_range=None, normalized=False):
        "Time-domain trace on plot `p`, with its picks"
        dur = tr.stats.npts * tr.stats.delta
        data_max = float(np.max(np.abs(tr.data))) if len(tr.data) > 0 else 1.0
        if not np.isfinite(data_max) or data_max <= 0:
            data_max = 1.0
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
        if normalized:
            p.setYRange(-1, 1)
        else:
            p.setYRange(-data_max, data_max)

        times = getattr(tr, "_cached_times", None)
        if times is None or len(times) != tr.stats.npts:
            times = tr.times()
            tr._cached_times = times

        p.plot(
            times,
            tr.data,
            pen=pg.mkPen(color, width=1.2),
            autoDownsample=True,
            downsampleMethod='peak',
            clipToView=True,
        )
        p.meta = {
            "sta": tr.stats.station,
            "cha": tr.stats.channel,
            "st": tr.stats.starttime,
        }
        p.pick_items = []
        self._draw_picks(p, tr, theo_arrs)

    def _draw_picks(self, p, tr, theo_arrs):
        "Existing picks and theoretical arrivals of `tr` on plot `p`"
        dur = tr.stats.npts * tr.stats.delta

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
            y_max = 1.0
            if hasattr(p, "viewRange"):
                try:
                    vr = p.viewRange()
                    if len(vr) > 1 and len(vr[1]) > 1:
                        y_max = float(vr[1][1])
                except Exception:
                    y_max = 1.0
            y_theo = y_max * 0.65

            for ph, arr_time in theo_arrs[tr.stats.station].items():
                t_rel = arr_time - tr.stats.starttime
                if 0 <= t_rel <= dur:
                    ph_u = ph.upper()
                    if "P" in ph_u:
                        t_col = QColor(46, 204, 113, 140)  # Muted picked P emerald green
                    elif "S" in ph_u:
                        t_col = QColor(224, 86, 253, 140)  # Muted picked S magenta
                    else:
                        t_col = QColor(142, 68, 173, 140)  # Muted other pick purple
                    self._add_visual_pick(
                        p, t_rel, f"{ph} (theo)", 0.0, color=t_col, style=Qt.PenStyle.DashDotLine, y_pos=y_theo
                    )

    def _detail_blocks(self, raw_st, raw_disp_st, proc_st):
        """One (raw, raw_disp, processed) trio per source file: the first component of each file.

        One file per component -> every file gives a block.
        One file per station   -> a single block, for the first component (Z before N, E).
        """
        by_file = {}
        for raw, raw_disp, proc in zip(raw_st, raw_disp_st, proc_st):
            key = raw.stats.get("filename") or raw.id  # no filename: one trace = one block
            by_file.setdefault(key, []).append((raw, raw_disp, proc))
        firsts = [
            max(pairs, key=lambda rp: rp[0].stats.channel[-1])
            for pairs in by_file.values()
        ]
        return sorted(firsts, key=lambda rp: rp[0].stats.channel[-1], reverse=True)

    def _plot_detail(self, params, old_view_range=None):
        """Focus Mode panels for the current station, one block per file."""
        sta_idx = self.sta_sel.currentIndex()
        if sta_idx < 0:
            return
        sta = self.stations[sta_idx]["sta"]
        self.sta_count_label.setText(f"{sta_idx + 1}/{self.sta_sel.count()}")

        # The whole station is preprocessed, so normalisation is shared between its
        # components as in the other modes. select() keeps the order, hence the zip.
        raw_st = self.original_stream.select(station=sta)
        raw_params = {
            "demean": params.get("demean", False),
            "detrend": params.get("detrend", False),
            "normalize": False,
            "filter_type": "None",
            "low_f": 1.0,
            "high_f": 20.0,
        }
        raw_disp_st = self._get_preprocessed_stream(raw_st, raw_params)
        proc_st = self._get_preprocessed_stream(raw_st, params)
        blocks = self._detail_blocks(raw_st, raw_disp_st, proc_st)
        if not blocks:
            return

        theo_arrs = self._get_theoretical_arrivals()

        self.win.setMinimumHeight(max(len(blocks) * (3 * 150 + 40), 400))
        duration = self.scalo_duration.value()
        first_p = None
        row = 0
        for raw, raw_disp, proc in blocks:
            cha = raw.stats.channel
            color = self._trace_color(cha)
            self.win.addItem(
                pg.LabelItem(f"<b>STATION: {sta} - {cha}</b>", size="12pt", color=self.fg_color),
                row=row,  # ty: ignore[unknown-argument]
                col=0,  # ty: ignore[unknown-argument]
            )
            p_raw = self.win.addPlot(row=row + 1, col=0)  # ty: ignore[unresolved-attribute]
            p_filt = self.win.addPlot(row=row + 2, col=0)  # ty: ignore[unresolved-attribute]
            p_scalo = self.win.addPlot(row=row + 3, col=0)  # ty: ignore[unresolved-attribute]
            row += 4
            for p in (p_raw, p_filt, p_scalo):
                p.getAxis("left").setWidth(60)  # same width: linked X axes stay aligned

            if first_p is None:
                first_p = p_raw
            else:
                p_raw.setXLink(first_p)
            p_filt.setXLink(first_p)
            p_scalo.setXLink(first_p)

            self._plot_waveform(p_raw, raw_disp, color, theo_arrs, old_view_range, normalized=False)
            self._plot_waveform(
                p_filt, proc, color, theo_arrs, old_view_range, normalized=params["normalize"]
            )
            p_scalo.meta = p_raw.meta  # needed by _start_picking when clicking on the scalogram
            self._plot_scalogram(p_scalo, raw, duration, old_view_range, theo_arrs)

            p_raw.setLabel("left", "Raw")
            p_filt.setLabel("left", "Filtered")
            p_scalo.setLabel("bottom", "Time (s)")
            self.plots.extend([p_raw, p_filt, p_scalo])  # plots[0] is always a raw panel

        # Linked X axes sync through the on-screen geometry of the panels: compute the layout
        # first and re-apply the range, otherwise the view can start a few seconds later
        self.win.ci.layout.activate()  # ty: ignore[unresolved-attribute]
        if old_view_range is not None:
            first_p.setXRange(old_view_range[0][0], old_view_range[0][1], padding=0)  # ty: ignore[unresolved-attribute]
        else:
            first_p.setXRange(0, blocks[0][0].stats.npts * blocks[0][0].stats.delta, padding=0)  # ty: ignore[unresolved-attribute]

    def _plot_scalogram(self, p, tr, duration, old_view_range, theo_arrs):
        "Scalogram of the raw trace."
        if tr.stats.npts < 2:
            return
        key = (self._trace_key(tr), round(duration, 3))
        if key not in self._scalo_cache:
            if len(self._scalo_cache) >= 12:
                self._scalo_cache.pop(next(iter(self._scalo_cache)))
            # Apply cosine taper on a copy to eliminate edge artifacts/flaring
            scalo_tr = tr.copy()
            scalo_tr.taper(max_percentage=0.05, type="cosine")
            self._scalo_cache[key] = utils.Morlet_scalogram(scalo_tr.data, scalo_tr.stats.delta, duration)
        if self._scalo_cache[key] is None:  # flat or non-finite trace
            return
        db, freqs, width, levels = self._scalo_cache[key]

        # Rows are evenly spaced in log10(f): the Y axis is log10(f) with ticks in Hz
        dur = tr.stats.npts * tr.stats.delta
        y = np.log10(freqs)
        dy = (y[-1] - y[0]) / (len(y) - 1)

        img = pg.ImageItem()
        img.setImage(db.T, autoLevels=False)  # (n_time, n_freq): x = time, y = frequency
        img.setLevels(levels)
        img.setLookupTable(utils.jet_colormap())
        img.setRect(QRectF(0, y[0] - dy / 2, width, (y[-1] - y[0]) + dy))
        p.addItem(img)

        # Frequencies of interest: tick labels and thin horizontal guide lines
        ticks = [f for f in (1, 2, 5, 10, 20, 30) if freqs[0] <= f <= freqs[-1]]
        for f in ticks:
            p.addItem(pg.InfiniteLine(pos=np.log10(f), angle=0, pen=pg.mkPen((0, 0, 0, 77))))
        p.getAxis("left").setTicks([[(np.log10(f), f"{f:g}") for f in ticks]])
        p.setLabel("left", "Wavelet frequency (Hz)")

        # The view starts exactly at the lowest frequency (1 Hz)
        p.setLimits(xMin=0, xMax=dur, yMin=y[0], yMax=y[-1] + dy / 2)
        p.setYRange(y[0], y[-1] + dy / 2, padding=0)
        if old_view_range is not None:
            p.setXRange(old_view_range[0][0], old_view_range[0][1], padding=0)
        else:
            p.setXRange(0, dur, padding=0)

        p.pick_items = []
        self._draw_picks(p, tr, theo_arrs)  # picks are shown on the scalogram too

    def _start_picking(self, scene_pos):
        target_p = None
        for p in self.plots:
            if p.sceneBoundingRect().contains(scene_pos):
                target_p = p
                break
        if not target_p:
            return
        
        mouse_point = target_p.vb.mapSceneToView(scene_pos)
        self.pick_start_point = scene_pos

        phase = self.ph_sel.currentText()
        if phase == "Custom":
            phase = self.ph_custom.text()

        self.current_picking_data = {
            "sta": target_p.meta["sta"],
            "cha_source": target_p.meta["cha"],
            "phase": phase,
            "abs_t": str(target_p.meta["st"] + mouse_point.x()),
            "t_rel": mouse_point.x(),
            "polarity": self.polarity_sel.currentText(),
            "onset": self.onset_sel.currentText(),
        }

        self.active_pick_items = []
        for p in self.plots:
            pick_item = pg.LinearRegionItem(
                values=[mouse_point.x(), mouse_point.x()],
                brush=pg.mkBrush(142, 68, 173, 100),
                pen=pg.mkPen("black", width=2),   # Linea nera e SPESSA 2
                movable=False,
            )
            p.addItem(pick_item)
            self.active_pick_items.append(pick_item)

    def start_pick_from_shortcut(self, phase):
        if not self.last_mouse_pos or not self.view_wave.isChecked() or self.active_pick_items:
            return
        self.ph_sel.setCurrentText(phase)
        self._start_picking(self.last_mouse_pos)

    def on_mouse_click_release(self, event):
        """Start or finalize a pick on mouse click."""
        if hasattr(self, "active_pick_items") and self.active_pick_items:
            # End picking
            unc = (
                self.active_pick_items[0].getRegion()[1]
                - self.active_pick_items[0].getRegion()[0]
            ) / 2
            self.current_picking_data["uncertainty"] = round(unc, 4)  # ty: ignore[invalid-assignment]
            
            if self.picking_mode_sel.currentText() == "Popup":
                dialog = PickDetailsDialog(
                    self, 
                    default_phase=self.current_picking_data["phase"],  # ty: ignore[not-subscriptable]
                    custom_phase=self.ph_custom.text()
                )
                if dialog.exec():
                    data = dialog.get_data()
                    self.current_picking_data["phase"] = data["phase"]  # ty: ignore[invalid-assignment]
                    self.current_picking_data["polarity"] = data["polarity"]  # ty: ignore[invalid-assignment]
                    self.current_picking_data["onset"] = data["onset"]  # ty: ignore[invalid-assignment]
                    self.picks.append(self.current_picking_data)
            else:
                self.picks.append(self.current_picking_data)

            for i, p in enumerate(self.plots):
                if i < len(self.active_pick_items):
                    p.removeItem(self.active_pick_items[i])
            self.active_pick_items = []
            self.update_table()
            self.update_pick_overlays()
            return

        if event.button() == Qt.MouseButton.LeftButton and self.view_wave.isChecked():
            self._start_picking(event.scenePos())

    def on_mouse_move(self, pos):
        """Update uncertainty visual range based on vertical mouse movement."""
        self.last_mouse_pos = pos
        if self.active_pick_items and self.pick_start_point and self.plots:
            diff_y = abs(pos.y() - self.pick_start_point.y())
            view_range = self.plots[0].viewRange()[0]
            uncertainty = (diff_y / 500) * (view_range[1] - view_range[0])
            t_center = self.current_picking_data["t_rel"]  # ty: ignore[not-subscriptable]
            new_region = [t_center - uncertainty, t_center + uncertainty]
            for item in self.active_pick_items:
                item.setRegion(new_region)

    def _add_visual_pick(self, plot, x_pos, label, uncertainty=0.0, color=None, style=Qt.PenStyle.DashLine, y_pos=0):
        c_cfg = self.config.get("colors", {})
        
        if color:
            main_color = color
        else:
            lbl_up = label.upper()
            if "P" in lbl_up:
                main_color = "#2ecc71" 
            elif "S" in lbl_up:
                main_color = "magenta" 
            else:
                main_color = c_cfg.get("pick_line", "#8e44ad")

        items = []
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
            items.append(region)

        line = pg.InfiniteLine(
            pos=x_pos,
            angle=90,
            pen=pg.mkPen(main_color, width=1.7, style=style),
        )
        plot.addItem(line)
        items.append(line)
        
        text = pg.TextItem(label, color=main_color, anchor=(0, 1))
        font = QFont()
        font.setBold(True)
        if "(theo)" in label:
            font.setPointSize(12)
        else:
            font.setPointSize(16)
        text.setFont(font)
        plot.addItem(text)
        text.setPos(x_pos, y_pos)
        items.append(text)

        if hasattr(plot, "pick_items"):
            plot.pick_items.extend(items)

    def update_table(self):
        self.table.blockSignals(True) 
        self.table.setSortingEnabled(False)
        
        self.table.setRowCount(len(self.picks))
        for i, pk in enumerate(self.picks):
            items = [
                QTableWidgetItem(pk["sta"]),
                QTableWidgetItem(pk["cha_source"]),
                QTableWidgetItem(pk["phase"]),
                QTableWidgetItem(pk["abs_t"].split('T')[0]),
                QTableWidgetItem(pk["abs_t"].split("T")[-1][:-1]),
                QTableWidgetItem(str(pk.get("uncertainty", 0.0))),
                QTableWidgetItem(pk.get("polarity", "Unknown")),
                QTableWidgetItem(pk.get("onset", "Unknown"))
            ]
            
            for col, item in enumerate(items):
                item.setData(Qt.ItemDataRole.UserRole, i)
                if col in (0, 1, 6, 7):
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                else:
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(i, col, item)

            cb_pol = QComboBox()
            cb_pol.addItems(["undecidable", "positive", "negative"])
            cur_pol = pk.get("polarity", "undecidable")
            if cur_pol in ["undecidable", "positive", "negative"]:
                cb_pol.setCurrentText(cur_pol)
            else:
                cb_pol.setCurrentIndex(0)
            cb_pol.currentTextChanged.connect(
                lambda val, idx=i, row_idx=i: self._on_table_polarity_changed(idx, row_idx, val)
            )
            self.table.setCellWidget(i, 6, cb_pol)

            cb_onset = QComboBox()
            cb_onset.addItems(["Unknown", "Emergent", "Impulsive"])
            cur_onset = pk.get("onset", "Unknown")
            if cur_onset in ["Unknown", "Emergent", "Impulsive"]:
                cb_onset.setCurrentText(cur_onset)
            else:
                cb_onset.setCurrentIndex(0)
            cb_onset.currentTextChanged.connect(
                lambda val, idx=i, row_idx=i: self._on_table_onset_changed(idx, row_idx, val)
            )
            self.table.setCellWidget(i, 7, cb_onset)

            btn = QPushButton("Remove")
            btn.setStyleSheet("background-color: #a2292b; color: white;")
            btn.clicked.connect(lambda _, idx=i: self.delete_pick(idx))
            self.table.setCellWidget(i, 8, btn)
            
        self.table.blockSignals(False)
        self.table.setSortingEnabled(True)

    def _on_table_polarity_changed(self, pk_idx, row, val):
        if 0 <= pk_idx < len(self.picks):
            self.picks[pk_idx]["polarity"] = val
            item = self.table.item(row, 6)
            if item:
                item.setText(val)

    def _on_table_onset_changed(self, pk_idx, row, val):
        if 0 <= pk_idx < len(self.picks):
            self.picks[pk_idx]["onset"] = val
            item = self.table.item(row, 7)
            if item:
                item.setText(val)

    def delete_pick(self, idx):
        if 0 <= idx < len(self.picks):
            pk = self.picks.pop(idx)
            if hasattr(self, "original_stream") and self.original_stream:
                utils.remove_pick_from_sac(
                    self.original_stream, 
                    pk["sta"], 
                    pk["cha_source"], 
                    pk["phase"]
                )
            self.update_table()
            self.update_pick_overlays()

    def update_pick_overlays(self):
        """Update only pick lines and labels on existing plots without rebuilding."""
        if not self.plots:
            return
        theo_arrs = self._get_theoretical_arrivals()
        for p in self.plots:
            if not hasattr(p, "meta"):
                continue
            if hasattr(p, "pick_items"):
                for item in p.pick_items:
                    try:
                        p.removeItem(item)
                    except Exception:
                        pass
                p.pick_items = []
            sta = p.meta.get("sta")
            cha = p.meta.get("cha")
            matched_tr = next((tr for tr in self.original_stream if tr.stats.station == sta and tr.stats.channel == cha), None)
            if matched_tr:
                self._draw_picks(p, matched_tr, theo_arrs)
            
    def on_table_cell_changed(self, row, col):
        """Apply changes made in the table to the corresponding pick data."""
        pk_idx = self._pick_index_from_row(row)
        if pk_idx is None:
            return
        item = self.table.item(row, col)
        if not item:
            return
        new_text = item.text().strip()
        pk = self.picks[pk_idx]

        try:
            if col == 0:    # Colonna 0: Stazione (Sta)
                pk["sta"] = new_text
            elif col == 1:    # Colonna 1: Canale (Cha)
                pk["cha_source"] = new_text
            if col == 2:    # Colonna 2: Fase (Phase)
                pk["phase"] = new_text
            elif col == 3 or col == 4:    # Colonna 3 (Data) o Colonna 4 (Ora)
                current_abs = pk["abs_t"]
                if 'T' in current_abs:
                    date_part, time_part = current_abs.split('T')
                else:
                    date_part, time_part = current_abs.split(' ') if ' ' in current_abs else (current_abs, "00:00:00Z")
                if col == 3:
                    date_part = new_text
                else:
                    time_part = new_text
                    if not time_part.endswith('Z'):
                        time_part += 'Z'
                new_abs_t = f"{date_part}T{time_part}"
                dt_new = UTCDateTime(new_abs_t)                
                pk["abs_t"] = str(dt_new)
                for p in self.plots:
                    if p.meta["sta"] == pk["sta"] and p.meta["cha"] == pk["cha_source"]:
                        pk["t_rel"] = float(dt_new - p.meta["st"])
                        break
            elif col == 5:    # Colonna 5: Incertezza (Unc (s))
                new_unc = abs(float(new_text))
                pk["uncertainty"] = round(new_unc, 4)
            elif col == 6:    # Colonna 6: Polarità (Polarity)
                pk["polarity"] = new_text
            elif col == 7:    # Colonna 7: Onset
                pk["onset"] = new_text

            self.update_pick_overlays()
        except Exception as e:  # noqa: BLE001
            print(f"Error in the format: {e}")
            self.update_table()      

    def _pick_index_from_row(self, row):
        """Convert selected row in the table to the corresponding index in self.picks."""
        item = self.table.item(row, 0)
        if item is None:
            return None
        idx = item.data(Qt.ItemDataRole.UserRole)
        if idx is None or not (0 <= idx < len(self.picks)):
            return None
        return idx

    def on_table_row_double_clicked(self, row, _col):
        """Show the waveform for the pick in the selected row."""
        if _col not in (0, 1):
            return
        idx = self._pick_index_from_row(row)
        if idx is None:
            return
        pk = self.picks[idx]

        sta_idx = next(
            (i for i, s in enumerate(self.stations) if s["sta"] == pk["sta"]), -1
        )
        if sta_idx < 0:
            QMessageBox.information(
                self, "Station not found", f"No waveform loaded for station {pk['sta']}."
            )
            return

        detail = self.view_mode.currentText() == "Focus Mode"
        widgets = (self.view_mode, self.sta_sel, self.view_wave)
        for w in widgets:
            w.blockSignals(True)
        if not detail:
            self.view_mode.setCurrentText("Single Station")
            self.view_wave.setChecked(True)
        self.view_mode.setCurrentText("Single Station")
        self.sta_sel.setCurrentIndex(sta_idx)
        for w in widgets:
            w.blockSignals(False)
        self._sync_view_widgets()
        self.update_plots(reset_zoom=True)

    def reset_view(self):
        self.update_plots(reset_zoom=True)

    def import_picks(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Picks", "", "QuakeML (*.qml *.xml);;CSV Files (*.csv);;Seisgram2k pick (*.pick)"
        )
        if path:
            try:
                if path.endswith('.csv'):
                    new_picks = utils.extract_picks_from_csv(path)
                elif path.endswith('.pick'):
                    new_picks = utils.extract_picks_from_seisgram_pick(path)
                elif path.endswith(('.qml', '.xml')):
                    new_picks = utils.extract_picks_from_quakeml(path)
                else:
                    QMessageBox.critical(self, "Error", "Unsupported picking format")
                self.picks.extend(new_picks)
                self.update_table()
                self.update_pick_overlays()
                QMessageBox.information(self, "Done", "Picks imported.")
            except Exception as e:  # noqa: BLE001
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
            except Exception as e:  # noqa: BLE001
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
        elif mode == "Alphabetical":
            self.original_stream = utils.reorder_stream_by_name(self.original_stream)
        elif mode == "By Distance":
            self.original_stream = utils.reorder_stream_by_distance(self.original_stream)
        elif mode == "By P/S Arrival":
            self.original_stream = utils.reorder_stream_by_arrival(self.original_stream, self.picks)
        
        self._setup_after_load()

    def open_plugins_folder(self):
        """Open user plugins directory in file manager."""
        p_dir = utils.get_plugins_dir()
        p_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(p_dir)))

    def open_velocity_model_file(self):
        """Open user velocity_model.json file in system default editor."""
        v_path = utils.get_velocity_model_path()
        if not v_path.exists():
            utils.sync_velocity_model()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(v_path)))

    def open_seismic_catalog(self):
        """Open the GIS-ready tab-separated seismic catalog (.txt) in system default editor/spreadsheet viewer."""
        cat_path = utils.get_default_catalog_path(self.config)
        if not cat_path.exists():
            # If not yet created, initialize with headers so the user can inspect it
            utils.update_seismic_catalog(cat_path, {})
            # Wait or ensure file exists
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(cat_path)))

    def open_hypo71_dialog(self):
        """Open or show the Hypo71 earthquake location dialog."""
        if not self.original_stream or len(self.original_stream) == 0:
            QMessageBox.warning(
                self,
                "No Data Loaded",
                "Please open seismic waveforms and pick at least 4 arrivals before running earthquake location."
            )
            return

        if not hasattr(self, "_hypo71_dialog") or self._hypo71_dialog is None:
            self._hypo71_dialog = Hypo71Dialog(parent=self)
        self._hypo71_dialog.refresh_picks()
        self._hypo71_dialog.show()
        self._hypo71_dialog.raise_()
        self._hypo71_dialog.activateWindow()

    def open_map_window(self):
        """Open or show the geographic map window with stations and event."""
        try:
            try:
                from config.plugins.map_plugin import MapDialog
            except ImportError:
                try:
                    from plugins.map_plugin import MapDialog  # ty: ignore[unresolved-import]
                except ImportError:
                    import map_plugin  # ty: ignore[unresolved-import]
                    MapDialog = map_plugin.MapDialog
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(
                self,
                "Plugin Error",
                f"Failed to load geographic map plugin:\n\n{e}"
            )
            return

        stream = getattr(self, "original_stream", None)
        client_name = self.config.get("defaults", {}).get("station_client", "INGV")

        fm = getattr(self, "focal_mechanism", None)
        if not hasattr(self, "_map_dialog") or self._map_dialog is None:
            self._map_dialog = MapDialog(stream=stream, parent=self, client_name=client_name)
            if fm:
                self._map_dialog.focal_mechanism = fm
        else:
            self._map_dialog.update_stream(stream)
            if fm:
                self._map_dialog.focal_mechanism = fm
                self._map_dialog.refresh_map(initial=False)

        self._map_dialog.show()
        self._map_dialog.raise_()
        self._map_dialog.activateWindow()

    def open_focmec_dialog(self, hypocenter=None):
        """Open or show the FOCMEC focal mechanism determination dialog."""
        if not self.original_stream or len(self.original_stream) == 0:
            QMessageBox.warning(
                self,
                "No Data Loaded",
                "Please open seismic waveforms and pick at least 4 P arrivals with polarities before calculating focal mechanism."
            )
            return

        try:
            try:
                from config.plugins.focmec_plugin import FocmecDialog
            except ImportError:
                try:
                    from plugins.focmec_plugin import FocmecDialog  # ty: ignore[unresolved-import]
                except ImportError:
                    import focmec_plugin  # ty: ignore[unresolved-import]
                    FocmecDialog = focmec_plugin.FocmecDialog
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(
                self,
                "Plugin Error",
                f"Failed to load FOCMEC plugin:\n\n{e}"
            )
            return

        # If hypocenter not passed, check if hypo71 dialog has a completed result
        if hypocenter is None and hasattr(self, "_hypo71_dialog") and self._hypo71_dialog is not None:
            hypocenter = getattr(self._hypo71_dialog, "results", None)

        self._focmec_dialog = FocmecDialog(parent=self, hypocenter=hypocenter)
        self._focmec_dialog.show()
        self._focmec_dialog.raise_()
        self._focmec_dialog.activateWindow()

    def open_documentation_viewer(self, doc="README.md"):
        """Open or show the in-app documentation viewer dialog."""
        if not hasattr(self, "_doc_dialog") or self._doc_dialog is None:
            self._doc_dialog = DocumentationViewerDialog(parent=self, initial_doc=doc)
        else:
            self._doc_dialog.load_doc(doc)
        self._doc_dialog.show()
        self._doc_dialog.raise_()
        self._doc_dialog.activateWindow()

    def show_about_dialog(self):
        """Show About PyPicker dialog with application logo and build details."""
        about_box = QMessageBox(self)
        about_box.setWindowTitle("About PyPicker")
        about_box.setWindowIcon(utils.get_app_icon("dark"))

        logo_path = utils.get_app_logo_path(self.theme_sel.currentText())
        if logo_path.exists():
            pix = QPixmap(str(logo_path))
            if not pix.isNull():
                about_box.setIconPixmap(pix.scaledToWidth(160, Qt.TransformationMode.SmoothTransformation))

        about_box.setText(
            f"<h2>PyPicker</h2>"
            f"<p><b>Version:</b> {__version__}<br>"
            f"<b>License:</b> GPL-3.0</p>"
            f"<p>A modern seismic waveform analyzer and arrival picking tool with "
            f"Hypo71 hypocenter inversion, ObsPy TauP theoretical ray tracing, "
            f"and Cartopy station mapping.</p>"
            f"<p><a href='https://github.com/DonatoTalone/PyPicker'>https://github.com/DonatoTalone/PyPicker</a></p>"
        )
        about_box.exec()

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PyPicker")
    app.setWindowIcon(utils.get_app_icon("dark"))
    try:
        window = SeismicPickerQT()
    except RuntimeError as exc:
        QMessageBox.critical(
            None,
            "Configuration Error",
            str(exc),
        )
        sys.exit(1)

    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
