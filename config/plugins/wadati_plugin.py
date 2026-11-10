"""PyPicker plugin: Standard and Modified Wadati plots.

The dialog reads the active application's in-memory picks (``parent.picks``),
selects one P and one S pick per station, and displays both Wadati analyses.
It never modifies picks or waveform data.
"""  # noqa: EXE002

from __future__ import annotations

import csv
import logging
import math
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QCheckBox,
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


class WadatiAnalysisDialog(QDialog):
    """Display standard and modified Wadati plots for the active PyPicker picks.

    ``parent`` is expected to be the main ``SeismicPickerQT`` window. Picks are
    read from ``parent.picks`` and are refreshed automatically while the
    dialog is visible. For each station, the pick with the smallest available
    non-negative uncertainty is selected when duplicate P or S picks exist.
    """

    POLL_INTERVAL_MS = 750

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.setWindowTitle("PyPicker - Wadati Analysis")
        self.resize(1450, 760)

        theme_mode = getattr(parent, "current_theme_mode", "dark") if parent else "dark"
        if parent is not None and hasattr(parent, "theme_sel"):
            try:
                selected = parent.theme_sel.currentText()
                if selected in ("Dark", "Light"):
                    theme_mode = selected.lower()
            except Exception:  # noqa: BLE001, S110
                pass
        if utils is not None and hasattr(utils, "get_app_icon"):
            try:
                self.setWindowIcon(utils.get_app_icon(theme_mode))
            except Exception:
                logger.debug("Could not set PyPicker application icon", exc_info=True)

        self._signature = None
        self._station_rows = []
        self._standard_rows = []
        self._modified_rows = []
        self._standard_fit = None
        self._modified_fit = None
        self._origin_epoch = None
        self._origin_description = None
        self._contexts = {}
        self._pinned = {"standard": None, "modified": None}
        self._base_status = ""

        self._init_ui()
        self.refresh_data()

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(self.POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll_parent_picks)
        self._poll_timer.start()

    # ------------------------------------------------------------------ UI
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        controls = QHBoxLayout()
        controls.setSpacing(8)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setToolTip("Recalculate both Wadati plots from the current picks")
        self.btn_refresh.clicked.connect(self.refresh_data)
        controls.addWidget(self.btn_refresh)

        self.chk_regression = QCheckBox("Show linear regression")
        self.chk_regression.setChecked(True)
        self.chk_regression.toggled.connect(self._redraw)
        controls.addWidget(self.chk_regression)
        controls.addStretch(1)

        self.btn_png = QPushButton("Export PNG")
        self.btn_png.clicked.connect(lambda: self._export_figure("png"))
        controls.addWidget(self.btn_png)

        self.btn_pdf = QPushButton("Export PDF")
        self.btn_pdf.clicked.connect(lambda: self._export_figure("pdf"))
        controls.addWidget(self.btn_pdf)

        self.btn_csv = QPushButton("Export CSV")
        self.btn_csv.clicked.connect(self._export_csv)
        controls.addWidget(self.btn_csv)

        layout.addLayout(controls)

        self.info_label = QLabel(
            "Standard: S−P versus P arrival time. Modified: pairwise ΔS versus ΔP. "
            "Move the mouse over a point to identify it; click a point to pin its annotation."
        )
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        self.figure = Figure(figsize=(13.5, 5.8), constrained_layout=False)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.ax_standard, self.ax_modified = self.figure.subplots(1, 2)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)

        layout.addWidget(self.canvas, stretch=1)
        layout.addWidget(self.toolbar)

        self.status_label = QLabel("Waiting for picks...")
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(24)
        layout.addWidget(self.status_label)

        self.canvas.mpl_connect("motion_notify_event", self._on_mouse_move)
        self.canvas.mpl_connect("button_press_event", self._on_mouse_click)
        self._apply_plot_theme()

    # ------------------------------------------------------------ pick input
    def _get_parent_picks(self):
        if self.main_window is None:
            return []
        picks = getattr(self.main_window, "picks", None)
        try:
            return list(picks or [])
        except TypeError:
            return []

    @staticmethod
    def _pick_signature(picks):
        """Cheap immutable signature used to detect edits/additions/removals."""
        rows = []
        for pick in picks:
            if not isinstance(pick, dict):
                rows.append((repr(pick),))
                continue
            rows.append((
                str(pick.get("sta", "")),
                str(pick.get("phase", "")),
                str(pick.get("abs_t", "")),
                str(pick.get("uncertainty", "")),
                str(pick.get("cha_source", "")),
            ))
        return tuple(sorted(rows))

    def _poll_parent_picks(self):
        if not self.isVisible():
            return
        picks = self._get_parent_picks()
        signature = self._pick_signature(picks)
        if signature != self._signature:
            self.refresh_data()

    @staticmethod
    def _parse_epoch(value):
        """Convert PyPicker's ISO UTC pick time to POSIX seconds."""
        if value is None or value == "":
            return None
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            return float(value)

        # ObsPy UTCDateTime objects expose a numeric ``timestamp`` property.
        timestamp = getattr(value, "timestamp", None)
        if isinstance(timestamp, (int, float)) and math.isfinite(float(timestamp)):
            return float(timestamp)

        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()

    @staticmethod
    def _format_utc(epoch):
        return datetime.fromtimestamp(float(epoch), tz=timezone.utc).isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z")

    @staticmethod
    def _finite_uncertainty(pick):
        try:
            value = float(pick.get("uncertainty"))
        except (TypeError, ValueError, AttributeError):
            return None
        if not math.isfinite(value) or value < 0:
            return None
        return value

    def _station_display_names(self):
        """Use NET.STA labels when the loaded stream identifies one network."""
        by_station = {}
        stream = getattr(self.main_window, "original_stream", None)
        try:
            traces = list(stream or [])
        except TypeError:
            traces = []
        for trace in traces:
            stats = getattr(trace, "stats", None)
            if stats is None:
                continue
            sta = str(getattr(stats, "station", "") or "").strip()
            net = str(getattr(stats, "network", "") or "").strip()
            if sta:
                by_station.setdefault(sta, set()).add(net)

        result = {}
        for sta, networks in by_station.items():
            nonempty = {net for net in networks if net}
            result[sta] = f"{next(iter(nonempty))}.{sta}" if len(nonempty) == 1 else sta
        return result

    def _get_origin_reference(self):
        """Return a Hypo71 origin time when the main window has a solution."""
        dialog = getattr(self.main_window, "_hypo71_dialog", None)
        result = getattr(dialog, "results", None) if dialog is not None else None
        if not isinstance(result, dict):
            return None, None
        raw_origin = result.get("origin_time")
        epoch = self._parse_epoch(raw_origin)
        if epoch is None:
            return None, None
        return epoch, f"current Hypo71 origin ({self._format_utc(epoch)})"

    def _select_station_picks(self, picks):
        candidates = {}
        invalid_times = 0
        relevant_count = 0
        duplicate_count = 0

        for pick in picks:
            if not isinstance(pick, dict):
                continue
            phase = str(pick.get("phase", "")).strip().upper()
            if phase not in ("P", "S"):
                continue
            relevant_count += 1
            sta = str(pick.get("sta", "")).strip()
            epoch = self._parse_epoch(pick.get("abs_t"))
            if not sta or epoch is None:
                invalid_times += 1
                continue
            candidates.setdefault(sta, {"P": [], "S": []})[phase].append({
                "station": sta,
                "phase": phase,
                "epoch": epoch,
                "uncertainty": self._finite_uncertainty(pick),
                "channel": str(pick.get("cha_source", "") or ""),
                "pick": pick,
            })

        selected = []
        display_names = self._station_display_names()
        for sta in sorted(candidates, key=str.casefold):
            chosen = {"station": sta, "display": display_names.get(sta, sta)}
            for phase in ("P", "S"):
                options = candidates[sta][phase]
                if not options:
                    continue
                # A known smaller uncertainty wins. Missing uncertainty sorts
                # after measured values; ties are resolved by earlier time.
                options.sort(key=lambda item: (
                    item["uncertainty"] if item["uncertainty"] is not None else math.inf,
                    item["epoch"],
                    item["channel"].casefold(),
                ))
                duplicate_count += max(0, len(options) - 1)
                chosen[phase] = options[0]
            if "P" in chosen and "S" in chosen:
                chosen["p_epoch"] = chosen["P"]["epoch"]
                chosen["s_epoch"] = chosen["S"]["epoch"]
                selected.append(chosen)

        return selected, {
            "relevant_picks": relevant_count,
            "invalid_times": invalid_times,
            "duplicates_ignored": duplicate_count,
            "stations_with_pair": len(selected),
            "stations_seen": len(candidates),
        }

    # --------------------------------------------------------- calculations
    @staticmethod
    def _linear_fit(x_values, y_values, vpvs_offset):
        x = np.asarray(x_values, dtype=float)
        y = np.asarray(y_values, dtype=float)
        if len(x) < 2 or len(y) != len(x) or not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
            return None
        if float(np.ptp(x)) <= 1.0e-12:
            return None
        try:
            slope, intercept = np.polyfit(x, y, 1)
        except (ValueError, np.linalg.LinAlgError, FloatingPointError):
            return None
        predicted = slope * x + intercept
        ss_res = float(np.sum((y - predicted) ** 2))
        ss_tot = float(np.sum((y - float(np.mean(y))) ** 2))
        r_squared = 1.0 - ss_res / ss_tot if ss_tot > 1.0e-15 else float("nan")
        return {
            "slope": float(slope),
            "intercept": float(intercept),
            "r_squared": r_squared,
            "vp_vs": float(slope + vpvs_offset),
            "n": len(x),
        }

    def refresh_data(self):
        """Rebuild datasets and plots from the active application's pick list."""
        picks = self._get_parent_picks()
        self._signature = self._pick_signature(picks)
        self._station_rows, diagnostics = self._select_station_picks(picks)
        self._origin_epoch, self._origin_description = self._get_origin_reference()

        if self._station_rows:
            if self._origin_epoch is not None:
                reference = self._origin_epoch
                self._standard_x_label = "P travel time from current origin (s)"
                self._standard_reference_note = self._origin_description
            else:
                reference = min(row["p_epoch"] for row in self._station_rows)
                self._standard_x_label = "P arrival time relative to earliest P pick (s)"
                self._standard_reference_note = "earliest P pick used as zero reference"

            self._standard_rows = []
            for row in self._station_rows:
                self._standard_rows.append({
                    "station": row["station"],
                    "station_display": row["display"],
                    "p_epoch": row["p_epoch"],
                    "s_epoch": row["s_epoch"],
                    "x": row["p_epoch"] - reference,
                    "y": row["s_epoch"] - row["p_epoch"],
                    "p_uncertainty": row["P"]["uncertainty"],
                    "s_uncertainty": row["S"]["uncertainty"],
                    "p_channel": row["P"]["channel"],
                    "s_channel": row["S"]["channel"],
                })
        else:
            self._standard_rows = []
            self._standard_x_label = "P arrival time (s)"
            self._standard_reference_note = "No station has both P and S picks"

        self._modified_rows = []
        for first, second in combinations(self._station_rows, 2):
            self._modified_rows.append({
                "station_a": first["station"],
                "station_b": second["station"],
                "station_a_display": first["display"],
                "station_b_display": second["display"],
                "x": abs(first["p_epoch"] - second["p_epoch"]),
                "y": abs(first["s_epoch"] - second["s_epoch"]),
                "p_a_epoch": first["p_epoch"],
                "s_a_epoch": first["s_epoch"],
                "p_b_epoch": second["p_epoch"],
                "s_b_epoch": second["s_epoch"],
            })

        self._standard_fit = self._linear_fit(
            [row["x"] for row in self._standard_rows],
            [row["y"] for row in self._standard_rows],
            vpvs_offset=1.0,
        )
        self._modified_fit = self._linear_fit(
            [row["x"] for row in self._modified_rows],
            [row["y"] for row in self._modified_rows],
            vpvs_offset=0.0,
        )

        self._diagnostics = diagnostics
        self._redraw()

    # --------------------------------------------------------------- plots
    def _is_dark_theme(self):
        mode = getattr(self.main_window, "current_theme_mode", "dark") if self.main_window else "dark"
        if self.main_window is not None and hasattr(self.main_window, "theme_sel"):
            try:
                selected = self.main_window.theme_sel.currentText()
                if selected in ("Dark", "Light"):
                    mode = selected.lower()
            except Exception:  # noqa: BLE001, S110
                pass
        return str(mode).lower() == "dark"

    def _apply_plot_theme(self):
        dark = self._is_dark_theme()
        self._plot_bg = "#1e1e1e" if dark else "#ffffff"
        self._plot_fg = "#f0f0f0" if dark else "#222222"
        self._grid_color = "#777777" if dark else "#b0b0b0"
        self.figure.set_facecolor(self._plot_bg)
        for ax in (self.ax_standard, self.ax_modified):
            ax.set_facecolor(self._plot_bg)
            ax.tick_params(colors=self._plot_fg)
            ax.xaxis.label.set_color(self._plot_fg)
            ax.yaxis.label.set_color(self._plot_fg)
            ax.title.set_color(self._plot_fg)
            for spine in ax.spines.values():
                spine.set_color(self._plot_fg)

    def _redraw(self, *_args):
        self._apply_plot_theme()
        self._pinned = {"standard": None, "modified": None}
        self._contexts = {}

        self._draw_one_plot(
            name="standard",
            ax=self.ax_standard,
            rows=self._standard_rows,
            fit=self._standard_fit,
            title="Standard Wadati Plot",
            xlabel=self._standard_x_label,
            ylabel="S − P arrival-time difference (s)",
            fit_vpvs_text="m + 1",
        )
        self._draw_one_plot(
            name="modified",
            ax=self.ax_modified,
            rows=self._modified_rows,
            fit=self._modified_fit,
            title="Modified Wadati Plot",
            xlabel="P-time difference between station pairs, ΔP (s)",
            ylabel="S-time difference between station pairs, ΔS (s)",
            fit_vpvs_text="m",
        )

        self.figure.subplots_adjust(left=0.07, right=0.98, bottom=0.13, top=0.90, wspace=0.28)
        self.canvas.draw_idle()

        diag = getattr(self, "_diagnostics", {})
        self._base_status = (
            f"P/S stations: {len(self._station_rows)} | "
            f"Standard points: {len(self._standard_rows)} | "
            f"Modified station pairs: {len(self._modified_rows)} | "
            f"Duplicate P/S picks ignored: {diag.get('duplicates_ignored', 0)} | "
            f"Invalid P/S times: {diag.get('invalid_times', 0)}"
        )
        if not self._station_rows:
            self._base_status += " — at least one P and one S pick at the same station are required."
        self.status_label.setText(self._base_status)

    def _draw_one_plot(self, name, ax, rows, fit, title, xlabel, ylabel, fit_vpvs_text):
        ax.clear()
        ax.set_facecolor(self._plot_bg)
        ax.set_title(title, fontsize=12, fontweight="bold", pad=10, color=self._plot_fg)
        ax.set_xlabel(xlabel, color=self._plot_fg)
        ax.set_ylabel(ylabel, color=self._plot_fg)
        ax.grid(True, linestyle=":", linewidth=0.7, alpha=0.45, color=self._grid_color)
        ax.tick_params(colors=self._plot_fg)
        for spine in ax.spines.values():
            spine.set_color(self._plot_fg)

        context = {"ax": ax, "rows": rows, "scatter": None, "annotation": None, "name": name}
        if rows:
            x = np.asarray([row["x"] for row in rows], dtype=float)
            y = np.asarray([row["y"] for row in rows], dtype=float)
            scatter = ax.scatter(
                x,
                y,
                s=42,
                alpha=0.88,
                edgecolors=self._plot_fg,
                linewidths=0.45,
                picker=8,
                label=f"Observations (N={len(rows)})",
                zorder=3,
            )
            context["scatter"] = scatter

            if self.chk_regression.isChecked() and fit is not None:
                xmin = float(np.min(x))
                xmax = float(np.max(x))
                x_line = np.linspace(xmin, xmax, 100)
                y_line = fit["slope"] * x_line + fit["intercept"]
                r2_text = f"{fit['r_squared']:.4f}" if math.isfinite(fit["r_squared"]) else "n/a"
                fit_label = (
                    f"OLS: y = {fit['slope']:.4f}x {fit['intercept']:+.4f}\n"
                    f"Vp/Vs = {fit['vp_vs']:.4f} ({fit_vpvs_text}) | "
                    f"R² = {r2_text} | N = {fit['n']}"
                )
                ax.plot(x_line, y_line, linewidth=1.8, label=fit_label, zorder=2)
            elif self.chk_regression.isChecked() and len(rows) >= 2:
                ax.plot([], [], " ", label="OLS unavailable: insufficient distinct X values")

            legend = ax.legend(loc="best", fontsize=8, framealpha=0.88)
            if legend is not None:
                legend.get_frame().set_facecolor(self._plot_bg)
                legend.get_frame().set_edgecolor(self._grid_color)
                for text in legend.get_texts():
                    text.set_color(self._plot_fg)
        else:
            ax.text(
                0.5,
                0.5,
                "No valid points\n(require paired P and S picks)",
                transform=ax.transAxes,
                ha="center",
                va="center",
                color=self._plot_fg,
                fontsize=10,
            )

        annotation = ax.annotate(
            "",
            xy=(0, 0),
            xytext=(12, 12),
            textcoords="offset points",
            bbox={"boxstyle": "round,pad=0.45", "fc": "#fff7d6", "ec": "#665c3b", "alpha": 0.96},
            arrowprops={"arrowstyle": "->", "color": "#d18b00", "lw": 1.0},
            fontsize=8,
            color="#222222",
            zorder=10,
        )
        annotation.set_visible(False)
        context["annotation"] = annotation
        self._contexts[name] = context

    def _nearest_point_index(self, context, event):
        scatter = context.get("scatter")
        if scatter is None or event.x is None or event.y is None:
            return None
        contains, details = scatter.contains(event)
        if not contains:
            return None
        indices = details.get("ind", [])
        if len(indices) == 0:
            return None
        rows = context["rows"]
        ax = context["ax"]
        candidates = []
        for index in indices:
            if 0 <= int(index) < len(rows):
                point_px = ax.transData.transform((rows[int(index)]["x"], rows[int(index)]["y"]))
                distance = (point_px[0] - event.x) ** 2 + (point_px[1] - event.y) ** 2
                candidates.append((distance, int(index)))
        return min(candidates)[1] if candidates else None

    def _annotation_text(self, name, row):
        if name == "standard":
            p_unc = row.get("p_uncertainty")
            s_unc = row.get("s_uncertainty")
            p_unc_text = f"{p_unc:.3f} s" if p_unc is not None else "n/a"
            s_unc_text = f"{s_unc:.3f} s" if s_unc is not None else "n/a"
            return (
                f"Station: {row['station_display']}\n"
                f"P: {self._format_utc(row['p_epoch'])}\n"
                f"S: {self._format_utc(row['s_epoch'])}\n"
                f"P reference: {row['x']:.4f} s\n"
                f"S − P: {row['y']:.4f} s\n"
                f"Uncertainty P/S: {p_unc_text} / {s_unc_text}"
            )
        return (
            f"Station pair: {row['station_a_display']} − {row['station_b_display']}\n"
            f"ΔP (A − B): {row['x']:+.4f} s\n"
            f"ΔS (A − B): {row['y']:+.4f} s\n"
            f"A: P {self._format_utc(row['p_a_epoch'])} | S {self._format_utc(row['s_a_epoch'])}\n"
            f"B: P {self._format_utc(row['p_b_epoch'])} | S {self._format_utc(row['s_b_epoch'])}"
        )

    def _show_annotation(self, name, index, pinned=False):
        context = self._contexts.get(name)
        if not context or not (0 <= index < len(context["rows"])):
            return
        row = context["rows"][index]
        annotation = context["annotation"]
        annotation.xy = (row["x"], row["y"])
        annotation.set_text(self._annotation_text(name, row))
        annotation.set_visible(True)
        self.canvas.draw_idle()
        prefix = "Pinned" if pinned else "Hovered"
        if name == "standard":
            detail = row["station_display"]
        else:
            detail = f"{row['station_a_display']} − {row['station_b_display']}"
        self.status_label.setText(f"{prefix}: {detail} | " + self._base_status)

    def _hide_annotation(self, name):
        context = self._contexts.get(name)
        if context and context.get("annotation") is not None:
            context["annotation"].set_visible(False)
            self.canvas.draw_idle()

    def _on_mouse_move(self, event):
        if event.inaxes is None:
            for name, context in self._contexts.items():
                if self._pinned.get(name) is None:
                    self._hide_annotation(name)
            if not any(value is not None for value in self._pinned.values()):
                self.status_label.setText(self._base_status)
            return

        for name, context in self._contexts.items():
            if self._pinned.get(name) is not None:
                continue
            if event.inaxes is not context["ax"]:
                self._hide_annotation(name)
                continue
            index = self._nearest_point_index(context, event)
            if index is None:
                self._hide_annotation(name)
                self.status_label.setText(self._base_status)
            else:
                self._show_annotation(name, index, pinned=False)

    def _on_mouse_click(self, event):
        if event.button != 1 or getattr(self.toolbar, "mode", ""):
            return
        for name, context in self._contexts.items():
            if event.inaxes is not context["ax"]:
                continue
            index = self._nearest_point_index(context, event)
            if index is None or self._pinned.get(name) == index:
                self._pinned[name] = None
                self._hide_annotation(name)
                self.status_label.setText(self._base_status)
            else:
                self._pinned[name] = index
                self._show_annotation(name, index, pinned=True)
            break

    # --------------------------------------------------------------- export
    def _export_figure(self, extension):
        file_filter = "PNG Image (*.png)" if extension == "png" else "PDF Document (*.pdf)"
        filename, _ = QFileDialog.getSaveFileName(
            self,
            f"Export Wadati plots ({extension.upper()})",
            f"wadati_plots.{extension}",
            file_filter,
        )
        if not filename:
            return
        path = Path(filename)
        if path.suffix.lower() != f".{extension}":
            path = path.with_suffix(f".{extension}")
        try:
            self.figure.savefig(
                path,
                format=extension,
                dpi=300 if extension == "png" else None,
                bbox_inches="tight",
                facecolor=self.figure.get_facecolor(),
            )
        except (OSError, ValueError) as exc:
            logger.exception("Could not export Wadati figure to %s", path)
            QMessageBox.critical(self, "Export Error", f"Unable to save figure:\n{path}\n\n{exc}")
            return
        self.status_label.setText(f"Exported Wadati plots to {path}")

    def _export_csv(self):
        if not self._standard_rows and not self._modified_rows:
            QMessageBox.information(self, "Export CSV", "There are no Wadati points to export.")
            return
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Wadati data",
            "wadati_data.csv",
            "CSV File (*.csv);;All Files (*)",
        )
        if not filename:
            return
        path = Path(filename)
        if path.suffix.lower() != ".csv":
            path = path.with_suffix(".csv")

        columns = [
            "plot_type", "station", "station_a", "station_b", "x_s", "y_s",
            "p_utc", "s_utc", "p_a_utc", "s_a_utc", "p_b_utc", "s_b_utc",
            "p_uncertainty_s", "s_uncertainty_s", "p_channel", "s_channel",
        ]
        try:
            with path.open("w", newline="", encoding="utf-8-sig") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=columns, extrasaction="ignore")
                writer.writeheader()
                for row in self._standard_rows:
                    writer.writerow({
                        "plot_type": "standard",
                        "station": row["station_display"],
                        "x_s": f"{row['x']:.9g}",
                        "y_s": f"{row['y']:.9g}",
                        "p_utc": self._format_utc(row["p_epoch"]),
                        "s_utc": self._format_utc(row["s_epoch"]),
                        "p_uncertainty_s": row["p_uncertainty"],
                        "s_uncertainty_s": row["s_uncertainty"],
                        "p_channel": row["p_channel"],
                        "s_channel": row["s_channel"],
                    })
                for row in self._modified_rows:
                    writer.writerow({
                        "plot_type": "modified",
                        "station_a": row["station_a_display"],
                        "station_b": row["station_b_display"],
                        "x_s": f"{row['x']:.9g}",
                        "y_s": f"{row['y']:.9g}",
                        "p_a_utc": self._format_utc(row["p_a_epoch"]),
                        "s_a_utc": self._format_utc(row["s_a_epoch"]),
                        "p_b_utc": self._format_utc(row["p_b_epoch"]),
                        "s_b_utc": self._format_utc(row["s_b_epoch"]),
                    })
        except OSError as exc:
            logger.exception("Could not export Wadati CSV to %s", path)
            QMessageBox.critical(self, "Export Error", f"Unable to save CSV:\n{path}\n\n{exc}")
            return
        self.status_label.setText(f"Exported {len(self._standard_rows)} standard points and "
                                    f"{len(self._modified_rows)} modified pairs to {path}")

