"""
PyPicker Plugin: Earthquake Focal Mechanism Determination (FOCMEC).
Bridges PyPicker picks and ObsPy Stream SAC headers to focmecpy solver and Beachball UI.
"""

from copy import deepcopy
import os
from pathlib import Path
import sys

import numpy as np
from obspy import UTCDateTime

# Path resolution for local and user plugins
_plugins_dir = str(Path(__file__).resolve().parent)
if _plugins_dir not in sys.path:
    sys.path.insert(0, _plugins_dir)

import focmecpy as fm

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QDoubleSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT


def extract_stations_and_polarities(stream, picks, velocity_model=None, hypocenter=None):
    """
    Extract station metadata, coordinates, P-wave polarities, azimuths, and take-off angles.
    
    Parameters
    ----------
    stream : obspy.Stream
        Waveforms with SAC headers.
    picks : list of dict
        Picks from PyPicker.
    velocity_model : optional
        1D crustal velocity model.
    hypocenter : dict, optional
        Pre-computed hypocenter (latitude, longitude, depth_km, origin_time).
        If None, extracted from first trace SAC headers (evla, evlo, evdp).
        
    Returns
    -------
    tuple (station_data, hypo_dict, missing_stations)
    """
    station_meta = {}
    evla = None
    evlo = None
    evdp = None
    ot = None

    for tr in stream:
        sta = tr.stats.station
        sac = getattr(tr.stats, "sac", {})

        # Extract event coordinates from SAC if not explicitly passed
        if evla is None and sac.get("evla") is not None and sac.get("evla") != -12345.0:
            evla = float(sac["evla"])
            evlo = float(sac["evlo"])
            evdp = float(sac.get("evdp", 5.0))
            if evdp > 1000.0:  # in meters in some SAC variants
                evdp /= 1000.0
            o_offset = sac.get("o", 0.0)
            if o_offset != -12345.0:
                ot = tr.stats.starttime + float(o_offset)
            else:
                ot = tr.stats.starttime

        if sta in station_meta:
            continue

        stla = sac.get("stla")
        stlo = sac.get("stlo")
        stel = sac.get("stel", 0.0)
        if stel == -12345.0 or stel is None:
            stel = 0.0

        if stla is not None and stlo is not None and stla != -12345.0 and stlo != -12345.0:
            station_meta[sta] = {
                "stla": float(stla),
                "stlo": float(stlo),
                "stel": float(stel),
                "channel": tr.stats.channel,
            }

    if hypocenter:
        evla = float(hypocenter.get("latitude", evla if evla is not None else 0.0))
        evlo = float(hypocenter.get("longitude", evlo if evlo is not None else 0.0))
        evdp = float(hypocenter.get("depth_km", evdp if evdp is not None else 5.0))
        ot = hypocenter.get("origin_time", ot)

    hypo_dict = {
        "latitude": evla,
        "longitude": evlo,
        "depth_km": evdp,
        "origin_time": ot,
        "rms": hypocenter.get("rms", 0.0) if hypocenter else 0.0,
        "erh": hypocenter.get("erh", 0.0) if hypocenter else 0.0,
        "erz": hypocenter.get("erz", 0.0) if hypocenter else 0.0,
        "quality": hypocenter.get("quality", "--") if hypocenter else "--",
        "velocity_model_name": hypocenter.get("velocity_model_name", "1D Model") if hypocenter else "1D Model",
    }

    # Load TauP model for takeoff angles
    taup_model = None
    try:
        import picker_utils_qt as utils
        taup_model = utils.get_or_create_taup_model()
    except Exception:
        pass

    station_data = []
    missing_stations = []

    # Map polarity strings to values: +1 (Up/Compression), -1 (Down/Dilatation)
    for pk in picks:
        phase = pk.get("phase", "").upper()
        if not phase.startswith("P"):
            continue

        sta = pk.get("sta")
        if sta not in station_meta:
            missing_stations.append(sta)
            continue

        meta = station_meta[sta]
        pol_raw = str(pk.get("polarity", "")).strip().lower()

        if pol_raw in ("positive", "+", "u", "c", "up", "compression"):
            pol_val = 1
            pol_symbol = "+"
        elif pol_raw in ("negative", "-", "d", "down", "dilatation"):
            pol_val = -1
            pol_symbol = "-"
        else:
            pol_val = 0
            pol_symbol = "?"

        # Calculate ray geometry if hypocenter is available
        dist_km = 0.0
        az = 0.0
        takeoff = 90.0
        if evla is not None and evlo is not None and evdp is not None:
            dist_km, az, takeoff, _, _ = fm.calculate_takeoff_and_azimuth(
                evla, evlo, evdp, meta["stla"], meta["stlo"], taup_model=taup_model
            )

        station_data.append({
            "station": sta,
            "component": meta["channel"],
            "stla": meta["stla"],
            "stlo": meta["stlo"],
            "dist_km": dist_km,
            "azimuth": az,
            "takeoff": takeoff,
            "polarity": pol_symbol,
            "polarity_val": pol_val,
        })

    return station_data, hypo_dict, missing_stations


class FocmecDialog(QDialog):
    """
    Interactive GUI Dialog for Earthquake Focal Mechanism Determination (FOCMEC).
    """

    def __init__(self, parent=None, hypocenter=None):
        super().__init__(parent)
        self.parent = parent
        self.hypocenter = deepcopy(hypocenter) if hypocenter else {}
        self.station_data = []
        self.focmec_results = None

        self.setWindowTitle("FOCMEC: Earthquake Focal Mechanism Determination")
        self.resize(1080, 720)
        self.setMinimumSize(920, 620)

        self._init_ui()
        self._load_data()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # ----------------- LEFT PANEL: CONTROLS & TABLES -----------------
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(4, 4, 4, 4)

        # 1. Hypocenter Summary Box
        hypo_box = QGroupBox("Earthquake Hypocenter")
        hypo_form = QFormLayout(hypo_box)
        hypo_form.setContentsMargins(6, 6, 6, 6)

        self.lbl_hypo_time = QLabel("--")
        self.lbl_hypo_coords = QLabel("--")
        self.lbl_hypo_quality = QLabel("--")
        hypo_form.addRow("Origin Time:", self.lbl_hypo_time)
        hypo_form.addRow("Coordinates:", self.lbl_hypo_coords)
        hypo_form.addRow("Location Quality:", self.lbl_hypo_quality)
        left_layout.addWidget(hypo_box)

        # 2. Inversion Parameters Box
        params_box = QGroupBox("FOCMEC Parameters")
        params_form = QFormLayout(params_box)
        params_form.setContentsMargins(6, 6, 6, 6)

        self.grid_step_spin = QDoubleSpinBox()
        self.grid_step_spin.setRange(1.0, 15.0)
        self.grid_step_spin.setSingleStep(1.0)
        self.grid_step_spin.setValue(5.0)
        self.grid_step_spin.setSuffix(" °")

        self.max_errors_spin = QSpinBox()
        self.max_errors_spin.setRange(0, 20)
        self.max_errors_spin.setValue(1)
        self.max_errors_spin.setToolTip("Maximum allowed wrong polarities (SurfQuake default: 1.0)")

        self.chk_all_solutions = QCheckBox("Show all acceptable nodal planes")
        self.chk_all_solutions.setChecked(True)
        self.chk_all_solutions.toggled.connect(self._update_plot)

        self.chk_plot_polarities = QCheckBox("Plot station polarities on beachball")
        self.chk_plot_polarities.setChecked(True)
        self.chk_plot_polarities.toggled.connect(self._update_plot)

        params_form.addRow("Grid Step (Δ):", self.grid_step_spin)
        params_form.addRow("Accepted Misfits:", self.max_errors_spin)
        params_form.addRow("", self.chk_all_solutions)
        params_form.addRow("", self.chk_plot_polarities)

        btn_run = QPushButton("Calculate Focal Mechanism (FOCMEC)")
        btn_run.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        btn_run.setStyleSheet("background-color: #16a085; color: white; padding: 6px; border-radius: 4px;")
        btn_run.clicked.connect(self.run_inversion)
        params_form.addRow(btn_run)

        left_layout.addWidget(params_box)

        # 3. Station Polarities Table
        table_box = QGroupBox("Station First-Motion Polarities (P-waves)")
        table_layout = QVBoxLayout(table_box)
        table_layout.setContentsMargins(6, 6, 6, 6)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Station", "Comp", "Dist (km)", "Azimuth (°)", "Take-off (°)", "Polarity"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table_layout.addWidget(self.table)
        left_layout.addWidget(table_box)

        # 4. Results Card
        res_box = QGroupBox("Focal Mechanism Results")
        res_form = QFormLayout(res_box)
        res_form.setContentsMargins(6, 6, 6, 6)

        self.lbl_regime = QLabel("<b>Faulting Regime:</b> --")
        self.lbl_np1 = QLabel("<b>Nodal Plane 1:</b> --")
        self.lbl_np2 = QLabel("<b>Nodal Plane 2:</b> --")
        self.lbl_axes = QLabel("<b>P / T Axes:</b> --")
        self.lbl_stats = QLabel("<b>Misfit / Solutions:</b> --")

        res_form.addRow(self.lbl_regime)
        res_form.addRow(self.lbl_np1)
        res_form.addRow(self.lbl_np2)
        res_form.addRow(self.lbl_axes)
        res_form.addRow(self.lbl_stats)

        # Action Buttons
        btn_row = QHBoxLayout()
        self.btn_save_img = QPushButton("Save Beachball Image...")
        self.btn_save_img.clicked.connect(self.save_image)
        self.btn_save_img.setEnabled(False)

        self.btn_export_csv = QPushButton("Export CSV Report...")
        self.btn_export_csv.clicked.connect(self.export_csv)
        self.btn_export_csv.setEnabled(False)

        self.btn_export_inp = QPushButton("Export FOCMEC .inp...")
        self.btn_export_inp.clicked.connect(self.export_inp)
        self.btn_export_inp.setEnabled(False)

        btn_row.addWidget(self.btn_save_img)
        btn_row.addWidget(self.btn_export_csv)
        btn_row.addWidget(self.btn_export_inp)
        res_form.addRow(btn_row)

        left_layout.addWidget(res_box)

        # ----------------- RIGHT PANEL: INTERACTIVE BEACHBALL -----------------
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        self.fig, self.ax = plt.subplots(figsize=(6, 6), dpi=100)
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)

        right_layout.addWidget(self.toolbar)
        right_layout.addWidget(self.canvas)

        self.status_label = QLabel("Ready. Review station polarities and click 'Calculate Focal Mechanism'.")
        self.status_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
        right_layout.addWidget(self.status_label)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 5)

    def _load_data(self):
        """Extract stream waveforms, picks, and hypocenter from parent or parameters."""
        if not self.parent:
            return

        stream = getattr(self.parent, "original_stream", None)
        picks = getattr(self.parent, "picks", [])

        if not stream:
            self.status_label.setText("No waveforms loaded in PyPicker.")
            return

        st_data, hypo_dict, missing = extract_stations_and_polarities(
            stream, picks, hypocenter=self.hypocenter
        )
        self.station_data = st_data
        self.hypocenter = hypo_dict

        # Populate Hypocenter UI
        lat = hypo_dict.get("latitude")
        lon = hypo_dict.get("longitude")
        depth = hypo_dict.get("depth_km")
        ot = hypo_dict.get("origin_time")

        if lat is not None and lon is not None:
            self.lbl_hypo_coords.setText(f"Lat: {lat:.4f}°, Lon: {lon:.4f}°, Depth: {depth:.2f} km")
        else:
            self.lbl_hypo_coords.setText("<span style='color:red;'>Missing hypocenter coordinates</span>")

        if ot:
            ot_str = ot.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] if isinstance(ot, UTCDateTime) else str(ot)
            self.lbl_hypo_time.setText(f"{ot_str} UTC")
        else:
            self.lbl_hypo_time.setText("--")

        qsd = hypo_dict.get("quality", "--")
        rms = hypo_dict.get("rms", 0.0)
        self.lbl_hypo_quality.setText(f"RMS: {rms:.3f} s | Quality: {qsd}")

        # Populate Station Table
        self.table.setRowCount(0)
        for i, row_data in enumerate(self.station_data):
            row = self.table.rowCount()
            self.table.insertRow(row)

            sta_item = QTableWidgetItem(row_data["station"])
            sta_item.setFlags(sta_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
            comp_item = QTableWidgetItem(row_data["component"])
            comp_item.setFlags(comp_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
            dist_item = QTableWidgetItem(f"{row_data['dist_km']:.2f}")
            dist_item.setFlags(dist_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
            az_item = QTableWidgetItem(f"{row_data['azimuth']:.1f}")
            az_item.setFlags(az_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
            to_item = QTableWidgetItem(f"{row_data['takeoff']:.1f}")
            to_item.setFlags(to_item.flags() ^ Qt.ItemFlag.ItemIsEditable)

            # Polarity combo box
            cb = QComboBox()
            cb.addItems(["Compression (+)", "Dilatation (-)", "Undecided (?)"])
            cur_pol = row_data["polarity"]
            if cur_pol == "+":
                cb.setCurrentIndex(0)
            elif cur_pol == "-":
                cb.setCurrentIndex(1)
            else:
                cb.setCurrentIndex(2)

            cb.currentIndexChanged.connect(lambda idx, r=row: self._on_polarity_changed(r, idx))

            self.table.setItem(row, 0, sta_item)
            self.table.setItem(row, 1, comp_item)
            self.table.setItem(row, 2, dist_item)
            self.table.setItem(row, 3, az_item)
            self.table.setItem(row, 4, to_item)
            self.table.setCellWidget(row, 5, cb)

        # Draw empty beachball preview
        self.ax.clear()
        fm.plot_beachball(0, 90, 0, ax=self.ax, title="Beachball Preview (Click Calculate)")
        self.canvas.draw()

    def _on_polarity_changed(self, row, combo_idx):
        """Update polarity when user edits the table combo box."""
        if 0 <= row < len(self.station_data):
            if combo_idx == 0:
                self.station_data[row]["polarity"] = "+"
                self.station_data[row]["polarity_val"] = 1
            elif combo_idx == 1:
                self.station_data[row]["polarity"] = "-"
                self.station_data[row]["polarity_val"] = -1
            else:
                self.station_data[row]["polarity"] = "?"
                self.station_data[row]["polarity_val"] = 0

    def run_inversion(self):
        """Execute FOCMEC grid-search solver."""
        valid_stations = [s for s in self.station_data if s["polarity_val"] != 0]
        if len(valid_stations) < 4:
            QMessageBox.warning(
                self,
                "Insufficient Polarities",
                f"FOCMEC requires at least 4 clear station polarities (+ or -).\nCurrently declared: {len(valid_stations)}."
            )
            return

        if self.hypocenter.get("latitude") is None:
            QMessageBox.critical(
                self,
                "Missing Hypocenter",
                "Earthquake hypocenter coordinates are missing.\nPlease run Hypo71 localization or load SAC files with evla/evlo headers."
            )
            return

        stas = [s["station"] for s in valid_stations]
        azs = [s["azimuth"] for s in valid_stations]
        tos = [s["takeoff"] for s in valid_stations]
        pols = [s["polarity_val"] for s in valid_stations]

        step = self.grid_step_spin.value()
        max_err = self.max_errors_spin.value()

        self.status_label.setText("Performing grid search across focal sphere...")
        self.status_label.setStyleSheet("color: #2980b9; font-weight: bold;")
        QApplication.processEvents()

        try:
            res = fm.solve_focal_mechanism(
                stas, azs, tos, pols, max_errors=max_err, grid_step=step
            )
            self.focmec_results = res
            best = res["best_solution"]

            # Update Results Labels
            self.lbl_regime.setText(f"<b>Faulting Regime:</b> <span style='color:#16a085;'>{best['regime']}</span>")
            self.lbl_np1.setText(f"<b>Nodal Plane 1:</b> Strike={best['strike']:.1f}° | Dip={best['dip']:.1f}° | Rake={best['rake']:.1f}°")
            self.lbl_np2.setText(f"<b>Nodal Plane 2:</b> Strike={best['strike2']:.1f}° | Dip={best['dip2']:.1f}° | Rake={best['rake2']:.1f}°")
            p_ax = best["p_axis"]
            t_ax = best["t_axis"]
            self.lbl_axes.setText(f"<b>P-axis:</b> Trend={p_ax[0]:.1f}°, Plunge={p_ax[1]:.1f}° | <b>T-axis:</b> Trend={t_ax[0]:.1f}°, Plunge={t_ax[1]:.1f}°")
            self.lbl_stats.setText(
                f"<b>Misfits:</b> {best['misfit']} / {res['num_polarities']} | <b>Acceptable Solutions:</b> {res['num_acceptable']} | <b>Gap:</b> {res['azimuthal_gap']:.1f}°"
            )

            self.btn_save_img.setEnabled(True)
            self.btn_export_csv.setEnabled(True)
            self.btn_export_inp.setEnabled(True)

            status_msg = f"Inversion complete! Best solution found with {best['misfit']} misfits among {res['num_acceptable']} valid solutions."

            # Update GIS Seismic Catalog (.txt)
            try:
                import picker_utils_qt as utils
                cfg = getattr(self.parent, "config", {}) if self.parent else {}
                cat_path = utils.get_default_catalog_path(cfg)
                ev_id = getattr(self.parent, "current_event_id", None)
                if not ev_id:
                    ev_id = utils.get_or_create_event_id(
                        getattr(self.parent, "original_stream", None),
                        picks=getattr(self.parent, "picks", None),
                        hypocenter=self.hypocenter,
                    )
                    if self.parent:
                        self.parent.current_event_id = ev_id

                focmec_qual = utils.calculate_focmec_quality(
                    res["num_polarities"], best["misfit"], res["azimuthal_gap"]
                )

                cat_event = {
                    "Event_ID": ev_id,
                    "Origin_Time_UTC": self.hypocenter.get("origin_time"),
                    "Latitude": self.hypocenter.get("latitude"),
                    "Longitude": self.hypocenter.get("longitude"),
                    "Depth_km": self.hypocenter.get("depth_km"),
                    "Faulting_Regime": best.get("regime", ""),
                    "NP1_Strike": best["strike"],
                    "NP1_Dip": best["dip"],
                    "NP1_Rake": best["rake"],
                    "NP2_Strike": best["strike2"],
                    "NP2_Dip": best["dip2"],
                    "NP2_Rake": best["rake2"],
                    "P_Trend": best["p_axis"][0],
                    "P_Plunge": best["p_axis"][1],
                    "T_Trend": best["t_axis"][0],
                    "T_Plunge": best["t_axis"][1],
                    "Quality_Focmec": focmec_qual,
                    "Misfits_Focmec": best["misfit"],
                    "Num_Polarities": res["num_polarities"],
                    "Azimuthal_Gap": res["azimuthal_gap"],
                    "Solutions_Count": res["num_acceptable"],
                }
                actual_cat_path = utils.update_seismic_catalog(cat_path, cat_event)
                status_msg += f" Catalog updated: {actual_cat_path.name}"
            except Exception as cat_err:  # noqa: BLE001
                print(f"Could not update seismic catalog: {cat_err}")

            self.status_label.setText(status_msg)
            self.status_label.setStyleSheet("color: #27ae60; font-weight: bold;")

            # Update parent picker and map dialog with focal mechanism
            if self.parent:
                self.parent.focal_mechanism = best
                if hasattr(self.parent, "_map_dialog") and self.parent._map_dialog:
                    try:
                        self.parent._map_dialog.update_focal_mechanism(best)
                    except Exception as map_err:
                        print(f"Could not update map with focal mechanism: {map_err}")

            self._update_plot()

        except Exception as e:
            QMessageBox.critical(self, "Solver Error", f"FOCMEC inversion failed:\n{e}")
            self.status_label.setText("Inversion failed.")
            self.status_label.setStyleSheet("color: #c0392b; font-weight: bold;")

    def _update_plot(self):
        """Redraw beachball on canvas."""
        if not self.focmec_results:
            return

        best = self.focmec_results["best_solution"]
        all_sols = self.focmec_results["acceptable_solutions"] if self.chk_all_solutions.isChecked() else None
        pols = self.focmec_results["station_evaluations"] if self.chk_plot_polarities.isChecked() else None

        title_str = (
            f"{best['regime']}\n"
            f"NP1: {best['strike']:.0f}°/{best['dip']:.0f}°/{best['rake']:.0f}° | "
            f"NP2: {best['strike2']:.0f}°/{best['dip2']:.0f}°/{best['rake2']:.0f}°"
        )

        fm.plot_beachball(
            best["strike"],
            best["dip"],
            best["rake"],
            station_evaluations=pols,
            p_axis=best["p_axis"],
            t_axis=best["t_axis"],
            all_solutions=all_sols,
            ax=self.ax,
            title=title_str,
        )
        self.canvas.draw()

    def save_image(self):
        """Save beachball figure to image file."""
        if not self.focmec_results:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Beachball Image",
            "beachball.png",
            "PNG Image (*.png);;PDF Document (*.pdf);;SVG Vector (*.svg)",
        )
        if file_path:
            try:
                fm.save_beachball_figure(self.fig, file_path)
                QMessageBox.information(self, "Success", f"Beachball figure saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to save image:\n{e}")

    def export_csv(self):
        """Export localization and focal mechanism report to CSV."""
        if not self.focmec_results:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Focal Mechanism CSV Report",
            "focal_mechanism_report.csv",
            "CSV Files (*.csv)",
        )
        if file_path:
            try:
                fm.export_focal_mechanism_to_csv(file_path, self.hypocenter, self.focmec_results)
                QMessageBox.information(self, "Success", f"CSV report exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export CSV:\n{e}")

    def export_inp(self):
        """Export standard FOCMEC input (.inp) file."""
        valid_stations = [s for s in self.station_data if s["polarity_val"] != 0]
        if not valid_stations:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export FOCMEC Input File",
            "focmec.inp",
            "FOCMEC Input (*.inp *.txt)",
        )
        if file_path:
            try:
                comment = f"PyPicker FOCMEC event at {self.hypocenter.get('origin_time', 'unknown')}"
                stas = [s["station"] for s in valid_stations]
                azs = [s["azimuth"] for s in valid_stations]
                tos = [s["takeoff"] for s in valid_stations]
                pols = [s["polarity_val"] for s in valid_stations]
                fm.write_focmec_inp(file_path, comment, stas, azs, tos, pols)
                QMessageBox.information(self, "Success", f"FOCMEC input file exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export .inp file:\n{e}")
