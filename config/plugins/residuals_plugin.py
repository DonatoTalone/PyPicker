"""
PyPicker plugin: Interactive Travel-Time Residual Diagnostics.

Displays 3 interrogable subplots:
1. Residuals vs Pick Index (Station Order)
2. Residuals vs Epicentral Distance (km)
3. Residuals vs Event-to-Station Azimuth (degrees)

Features Wadati-style interactive inspection:
- Hover over any point to inspect station, phase, observed/calculated time, residual, distance, azimuth, weight.
- Click a point to pin/unpin its annotation box.
- Matplotlib Navigation Toolbar (zoom, pan, home).
- High-resolution export to PNG, PDF, CSV, and summary TXT.
- Full dark/light theme awareness.
"""

from __future__ import annotations

import csv
import logging
import math
from pathlib import Path
from typing import Any

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

try:
    import picker_utils_qt as utils
except ImportError:
    try:
        import config.picker_utils_qt as utils
    except ImportError:
        utils = None

logger = logging.getLogger(__name__)


class ResidualDiagnosticsDialog(QDialog):
    """
    Interactive diagnostic dialog for earthquake relocation travel-time residuals.
    Provides Wadati-style inspection with point picking, hover tooltips, and click-pinning.
    """

    def __init__(
        self,
        residuals: list[dict[str, Any]] | None = None,
        hypocenter: dict[str, Any] | None = None,
        model_name: str | None = None,
        stats: dict[str, Any] | None = None,
        parent: Any = None,
    ):
        super().__init__(parent)
        self.main_window = parent
        self.residuals = list(residuals or [])
        self.hypocenter = dict(hypocenter or {})
        self.model_name = model_name or self.hypocenter.get("velocity_model_name", "1D Velocity Model")
        self.stats = stats or (utils.calculate_residual_statistics(self.residuals) if utils else {})

        self.setWindowTitle(f"Travel-Time Residual Diagnostics — {self.model_name}")
        self.resize(1150, 680)

        theme_mode = getattr(parent, "current_theme_mode", None)
        if not theme_mode and parent and hasattr(parent, "theme_sel"):
            theme_mode = parent.theme_sel.currentText()
        if not theme_mode:
            theme_mode = "System"
        if utils and hasattr(utils, "get_app_icon"):
            self.setWindowIcon(utils.get_app_icon(theme_mode))

        self._pinned: dict[str, int | None] = {"index": None, "distance": None, "azimuth": None}
        self._contexts: dict[str, dict[str, Any]] = {}
        self._base_status = "Hover over a point to inspect; click to pin/unpin annotation."

        self._init_theme_colors(theme_mode)
        self.init_ui()
        self.plot_residuals()

    def _init_theme_colors(self, theme_mode: str):
        is_dark = False
        if theme_mode.lower() == "dark":
            is_dark = True
        elif theme_mode.lower() == "light":
            is_dark = False
        elif utils and hasattr(utils, "detect_system_dark_mode"):
            is_dark = bool(utils.detect_system_dark_mode())

        if is_dark:
            self._plot_bg = "#1e1e1e"
            self._plot_fg = "#e0e0e0"
            self._grid_color = "#333333"
            self._color_p = "#3498db"   # Bright Blue
            self._color_s = "#e74c3c"   # Bright Red
            self._box_bg = "#2c3e50"
            self._box_fg = "#ffffff"
            self._box_edge = "#34495e"
            self._arrow_color = "#f39c12"
        else:
            self._plot_bg = "#ffffff"
            self._plot_fg = "#222222"
            self._grid_color = "#e0e0e0"
            self._color_p = "#1f77b4"   # Navy Blue
            self._color_s = "#d62728"   # Deep Red
            self._box_bg = "#fff7d6"
            self._box_fg = "#222222"
            self._box_edge = "#665c3b"
            self._arrow_color = "#d18b00"

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Top Control & Export Bar
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.info_label = QLabel(self._build_info_header())
        self.info_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        top_bar.addWidget(self.info_label, stretch=1)

        self.btn_export_png = QPushButton("Export PNG")
        self.btn_export_png.clicked.connect(lambda: self._export_figure("png"))
        top_bar.addWidget(self.btn_export_png)

        self.btn_export_pdf = QPushButton("Export PDF")
        self.btn_export_pdf.clicked.connect(lambda: self._export_figure("pdf"))
        top_bar.addWidget(self.btn_export_pdf)

        self.btn_export_csv = QPushButton("Export CSV")
        self.btn_export_csv.clicked.connect(self._export_csv)
        top_bar.addWidget(self.btn_export_csv)

        self.btn_export_txt = QPushButton("Export Summary (.txt)")
        self.btn_export_txt.clicked.connect(self._export_summary)
        top_bar.addWidget(self.btn_export_txt)

        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.close)
        top_bar.addWidget(self.btn_close)

        layout.addLayout(top_bar)

        # Matplotlib Figure with 3 Subplots
        self.figure = Figure(figsize=(14.0, 5.8), constrained_layout=True)
        self.figure.patch.set_facecolor(self._plot_bg)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.ax_index, self.ax_dist, self.ax_azim = self.figure.subplots(1, 3)

        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        layout.addWidget(self.canvas, stretch=1)
        layout.addWidget(self.toolbar)

        # Bottom Status Label
        self.status_label = QLabel(self._base_status)
        self.status_label.setMinimumHeight(24)
        self.status_label.setStyleSheet("padding: 2px 4px; font-size: 11px;")
        layout.addWidget(self.status_label)

        # Connect Canvas Interactivity Events
        self.canvas.mpl_connect("motion_notify_event", self._on_mouse_move)
        self.canvas.mpl_connect("button_press_event", self._on_mouse_click)

    def _build_info_header(self) -> str:
        s_p = self.stats.get("P", {})
        s_s = self.stats.get("S", {})
        s_tot = self.stats.get("Total", {})

        p_txt = f"P (N={s_p.get('count', 0)}, RMS={s_p.get('rms', 0.0):.3f}s)" if s_p.get("count") else "P: N=0"
        s_txt = f"S (N={s_s.get('count', 0)}, RMS={s_s.get('rms', 0.0):.3f}s)" if s_s.get("count") else "S: N=0"
        tot_txt = f"Total (N={s_tot.get('count', 0)}, RMS={s_tot.get('rms', 0.0):.3f}s, MAE={s_tot.get('mae', 0.0):.3f}s)" if s_tot.get("count") else "Total: N=0"

        return f"Model: {self.model_name} | {tot_txt} | {p_txt} | {s_txt}"

    def plot_residuals(self):
        """Plot residuals in all 3 diagnostic subplots."""
        self.figure.clear()
        self.figure.patch.set_facecolor(self._plot_bg)
        self.ax_index, self.ax_dist, self.ax_azim = self.figure.subplots(1, 3)
        self._contexts.clear()
        self._pinned = {"index": None, "distance": None, "azimuth": None}

        # Filter valid residuals
        valid_rows = []
        for i, r in enumerate(self.residuals):
            res = r.get("residual_sec")
            if res is None:
                res = r.get("residual_obs_minus_calc_s")
            if res is None:
                continue
            try:
                res_val = float(res)
                if not math.isfinite(res_val):
                    continue
            except (ValueError, TypeError):
                continue

            ph = str(r.get("phase") or r.get("phase_observed") or "").strip().upper()
            sta = str(r.get("station", ""))
            dist = float(r.get("distance_km", 0.0))
            azim = float(r.get("azimuth_deg", 0.0))
            obs = r.get("observed_time")
            calc = r.get("calculated_time")
            wt = float(r.get("weight", 1.0))

            valid_rows.append({
                "raw_index": i,
                "order": len(valid_rows) + 1,
                "station": sta,
                "phase": ph,
                "is_p": ph.startswith("P"),
                "residual": res_val,
                "distance": dist,
                "azimuth": azim,
                "observed_time": obs,
                "calculated_time": calc,
                "weight": wt,
                "raw": r,
            })

        if not valid_rows:
            for ax in (self.ax_index, self.ax_dist, self.ax_azim):
                ax.set_facecolor(self._plot_bg)
                ax.text(0.5, 0.5, "No valid residuals available", transform=ax.transAxes,
                        ha="center", va="center", color=self._plot_fg, fontsize=11)
            self.canvas.draw()
            return

        p_rows = [r for r in valid_rows if r["is_p"]]
        s_rows = [r for r in valid_rows if not r["is_p"]]

        panels = [
            ("index", self.ax_index, "Pick Index (Order)", "Residuals by Pick",
             [r["order"] for r in p_rows], [r["order"] for r in s_rows], None),
            ("distance", self.ax_dist, "Epicentral Distance (km)", "Residuals vs Distance",
             [r["distance"] for r in p_rows], [r["distance"] for r in s_rows], None),
            ("azimuth", self.ax_azim, "Event-to-Station Azimuth (°)", "Residuals vs Azimuth",
             [r["azimuth"] for r in p_rows], [r["azimuth"] for r in s_rows], (0.0, 360.0)),
        ]

        for name, ax, xlabel, title, x_p, x_s, xlim in panels:
            ax.set_facecolor(self._plot_bg)
            ax.axhline(0.0, linestyle="--", linewidth=1.1, color=self._grid_color, alpha=0.9, zorder=1)

            scatter_p = None
            if p_rows:
                y_p = [r["residual"] for r in p_rows]
                scatter_p = ax.scatter(
                    x_p, y_p,
                    s=40,
                    color=self._color_p,
                    marker="o",
                    alpha=0.85,
                    edgecolors=self._plot_fg,
                    linewidths=0.5,
                    picker=8,
                    label=f"P picks (N={len(p_rows)})",
                    zorder=3,
                )

            scatter_s = None
            if s_rows:
                y_s = [r["residual"] for r in s_rows]
                scatter_s = ax.scatter(
                    x_s, y_s,
                    s=42,
                    color=self._color_s,
                    marker="s",
                    alpha=0.85,
                    edgecolors=self._plot_fg,
                    linewidths=0.5,
                    picker=8,
                    label=f"S picks (N={len(s_rows)})",
                    zorder=3,
                )

            ax.set_title(title, fontsize=11, fontweight="bold", color=self._plot_fg)
            ax.set_xlabel(xlabel, fontsize=9, color=self._plot_fg)
            ax.set_ylabel("Residual (Obs − Calc) [s]", fontsize=9, color=self._plot_fg)
            ax.tick_params(colors=self._plot_fg, labelsize=8)
            ax.grid(True, linestyle=":", alpha=0.5, color=self._grid_color)
            for spine in ax.spines.values():
                spine.set_color(self._grid_color)

            if xlim is not None:
                ax.set_xlim(xlim[0], xlim[1])
                ax.set_xticks(range(0, 361, 45))

            legend = ax.legend(loc="best", fontsize=8, framealpha=0.85)
            if legend:
                legend.get_frame().set_facecolor(self._plot_bg)
                legend.get_frame().set_edgecolor(self._grid_color)
                for t in legend.get_texts():
                    t.set_color(self._plot_fg)

            # Wadati-style interactive annotation box
            annotation = ax.annotate(
                "",
                xy=(0, 0),
                xytext=(14, 14),
                textcoords="offset points",
                bbox={"boxstyle": "round,pad=0.45", "fc": self._box_bg, "ec": self._box_edge, "alpha": 0.96},
                arrowprops={"arrowstyle": "->", "color": self._arrow_color, "lw": 1.2},
                fontsize=8,
                color=self._box_fg,
                zorder=10,
            )
            annotation.set_visible(False)

            self._contexts[name] = {
                "name": name,
                "ax": ax,
                "scatter_p": scatter_p,
                "scatter_s": scatter_s,
                "p_rows": p_rows,
                "s_rows": s_rows,
                "x_p": x_p,
                "x_s": x_s,
                "annotation": annotation,
            }

        self.canvas.draw()

    # -------------------------------------------------------------------------
    # Wadati-style Hover & Click Interactivity
    # -------------------------------------------------------------------------
    def _find_nearest_item(self, context: dict[str, Any], event: Any) -> tuple[dict[str, Any], float, float] | None:
        """Find the nearest scatter point under mouse cursor in the given subplot."""
        if event.x is None or event.y is None:
            return None

        ax = context["ax"]
        candidates = []

        # Check P scatter
        sc_p = context.get("scatter_p")
        if sc_p is not None:
            contains_p, details_p = sc_p.contains(event)
            if contains_p:
                for idx in details_p.get("ind", []):
                    if 0 <= int(idx) < len(context["p_rows"]):
                        row = context["p_rows"][int(idx)]
                        px = context["x_p"][int(idx)]
                        py = row["residual"]
                        pt_px = ax.transData.transform((px, py))
                        dist_sq = (pt_px[0] - event.x) ** 2 + (pt_px[1] - event.y) ** 2
                        candidates.append((dist_sq, row, px, py))

        # Check S scatter
        sc_s = context.get("scatter_s")
        if sc_s is not None:
            contains_s, details_s = sc_s.contains(event)
            if contains_s:
                for idx in details_s.get("ind", []):
                    if 0 <= int(idx) < len(context["s_rows"]):
                        row = context["s_rows"][int(idx)]
                        px = context["x_s"][int(idx)]
                        py = row["residual"]
                        pt_px = ax.transData.transform((px, py))
                        dist_sq = (pt_px[0] - event.x) ** 2 + (pt_px[1] - event.y) ** 2
                        candidates.append((dist_sq, row, px, py))

        if not candidates:
            return None

        candidates.sort(key=lambda c: c[0])
        _, best_row, bx, by = candidates[0]
        return best_row, bx, by

    def _annotation_text(self, row: dict[str, Any]) -> str:
        sta = row.get("station", "--")
        ph = row.get("phase", "--")
        res = row.get("residual", 0.0)
        dist = row.get("distance", 0.0)
        azim = row.get("azimuth", 0.0)
        wt = row.get("weight", 1.0)
        obs = row.get("observed_time")
        calc = row.get("calculated_time")

        obs_str = obs.strftime("%H:%M:%S.%f")[:-3] if hasattr(obs, "strftime") else (str(obs) if obs else "--")
        calc_str = calc.strftime("%H:%M:%S.%f")[:-3] if hasattr(calc, "strftime") else (str(calc) if calc else "--")

        return (
            f"Station: {sta} ({ph})\n"
            f"Residual: {res:+.4f} s\n"
            f"Obs Time:  {obs_str}\n"
            f"Calc Time: {calc_str}\n"
            f"Distance:  {dist:.2f} km\n"
            f"Azimuth:   {azim:.1f}° | Wt: {wt:.2f}"
        )

    def _show_annotation(self, name: str, row: dict[str, Any], x: float, y: float, pinned: bool = False):
        context = self._contexts.get(name)
        if not context:
            return
        annot = context["annotation"]
        annot.xy = (x, y)
        annot.set_text(self._annotation_text(row))
        annot.set_visible(True)
        self.canvas.draw_idle()

        prefix = "Pinned" if pinned else "Hovered"
        self.status_label.setText(
            f"{prefix}: {row['station']} ({row['phase']}) | Residual: {row['residual']:+.4f}s | "
            f"Dist: {row['distance']:.2f}km | Azim: {row['azimuth']:.1f}° | {self._base_status}"
        )

    def _hide_annotation(self, name: str):
        context = self._contexts.get(name)
        if context and context.get("annotation"):
            context["annotation"].set_visible(False)
            self.canvas.draw_idle()

    def _on_mouse_move(self, event: Any):
        if event.inaxes is None:
            for name in self._contexts:
                if self._pinned.get(name) is None:
                    self._hide_annotation(name)
            if not any(v is not None for v in self._pinned.values()):
                self.status_label.setText(self._base_status)
            return

        for name, context in self._contexts.items():
            if self._pinned.get(name) is not None:
                continue
            if event.inaxes is not context["ax"]:
                self._hide_annotation(name)
                continue

            hit = self._find_nearest_item(context, event)
            if hit is None:
                self._hide_annotation(name)
                self.status_label.setText(self._base_status)
            else:
                row, px, py = hit
                self._show_annotation(name, row, px, py, pinned=False)

    def _on_mouse_click(self, event: Any):
        if event.button != 1 or getattr(self.toolbar, "mode", ""):
            return

        for name, context in self._contexts.items():
            if event.inaxes is not context["ax"]:
                continue
            hit = self._find_nearest_item(context, event)
            if hit is None:
                self._pinned[name] = None
                self._hide_annotation(name)
                self.status_label.setText(self._base_status)
            else:
                row, px, py = hit
                # If already pinned on this station/phase, unpin
                pt_id = row.get("raw_index")
                if self._pinned.get(name) == pt_id:
                    self._pinned[name] = None
                    self._hide_annotation(name)
                    self.status_label.setText(self._base_status)
                else:
                    self._pinned[name] = pt_id
                    self._show_annotation(name, row, px, py, pinned=True)
            break

    # -------------------------------------------------------------------------
    # Export Functions
    # -------------------------------------------------------------------------
    def _export_figure(self, extension: str):
        file_filter = "PNG Image (*.png)" if extension == "png" else "PDF Document (*.pdf)"
        filename, _ = QFileDialog.getSaveFileName(
            self,
            f"Export Residual Diagnostics ({extension.upper()})",
            f"residual_diagnostics.{extension}",
            file_filter,
        )
        if not filename:
            return
        path = Path(filename)
        if path.suffix.lower() != f".{extension}":
            path = path.with_suffix(f".{extension}")
        try:
            self.figure.savefig(
                str(path),
                format=extension,
                dpi=300 if extension == "png" else None,
                bbox_inches="tight",
                facecolor=self.figure.get_facecolor(),
            )
            QMessageBox.information(self, "Export Successful", f"Figure successfully exported to:\n{path}")
            self.status_label.setText(f"Exported figure to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Unable to save figure:\n{e}")

    def _export_csv(self):
        if not self.residuals:
            QMessageBox.information(self, "Export CSV", "No residuals to export.")
            return
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Residuals CSV",
            "residuals.csv",
            "CSV File (*.csv);;All Files (*)",
        )
        if not filename:
            return
        path = Path(filename)
        if path.suffix.lower() != ".csv":
            path = path.with_suffix(".csv")
        try:
            if utils and hasattr(utils, "export_residuals_to_csv"):
                utils.export_residuals_to_csv(self.residuals, path, hypocenter=self.hypocenter, model_name=self.model_name)
            else:
                fieldnames = ["station", "phase", "residual_sec", "distance_km", "azimuth_deg", "weight", "model"]
                with path.open("w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                    writer.writeheader()
                    for r in self.residuals:
                        writer.writerow(r)
            QMessageBox.information(self, "Export Successful", f"Residuals CSV successfully exported to:\n{path}")
            self.status_label.setText(f"Exported residuals CSV to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Unable to save CSV:\n{e}")

    def _export_summary(self):
        if not self.residuals and not self.stats:
            QMessageBox.information(self, "Export Summary", "No residual data to summarize.")
            return
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Residual Summary Text",
            "residuals_summary.txt",
            "Text File (*.txt);;All Files (*)",
        )
        if not filename:
            return
        path = Path(filename)
        if path.suffix.lower() != ".txt":
            path = path.with_suffix(".txt")
        try:
            if utils and hasattr(utils, "export_residuals_summary"):
                utils.export_residuals_summary(self.stats, path, model_name=self.model_name, hypocenter=self.hypocenter)
            else:
                summary_txt = f"Residual Summary\nModel: {self.model_name}\nPicks: {len(self.residuals)}"
                path.write_text(summary_txt, encoding="utf-8")
            QMessageBox.information(self, "Export Successful", f"Residual summary successfully exported to:\n{path}")
            self.status_label.setText(f"Exported summary TXT to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Unable to save summary text:\n{e}")
