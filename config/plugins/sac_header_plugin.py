"""PyPicker Plugin: tabular viewer for SAC headers of loaded waveform traces.

The dialog accepts an ObsPy Stream (or any iterable of Trace objects) and
presents one trace per row and one SAC header field per column.  It can be
refreshed when the stream changes, filtered, copied to the clipboard, and
exported to CSV.
"""

import csv
import logging
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QHeaderView,
)

try:
    import picker_utils_qt as utils
except ImportError:
    try:
        import config.picker_utils_qt as utils
    except ImportError:  # Allow the dialog to be used outside the full app.
        utils = None


logger = logging.getLogger(__name__)


# Standard SAC fields in a useful reading order. Any additional fields found
# in a trace are appended alphabetically, so non-standard/custom headers are
# not lost.
SAC_HEADER_ORDER = (
    "delta", "depmin", "depmax", "scale", "odelta", "b", "e", "o", "a",
    "internal0", "t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8", "t9",
    "f", "resp0", "resp1", "resp2", "resp3", "resp4", "resp5", "resp6", "resp7", "resp8", "resp9",
    "stla", "stlo", "stel", "stdp", "evla", "evlo", "evel", "evdp", "mag",
    "user0", "user1", "user2", "user3", "user4", "user5", "user6", "user7", "user8", "user9",
    "dist", "az", "baz", "gcarc", "internal1", "internal2", "depmen", "cmpaz", "cmpinc",
    "xminimum", "xmaximum", "yminimum", "ymaximum",
    "nzyear", "nzjday", "nzhour", "nzmin", "nzsec", "nzmsec", "nvhdr", "norid", "nevid",
    "npts", "internal3", "nwfid", "nxsize", "nysize",
    "iftype", "idep", "iztype", "iinst", "istreg", "ievreg", "ievtyp", "iqual", "isynth",
    "imagtyp", "imagsrc", "leven", "lpspol", "lovrok", "lcalda",
    "kstnm", "kevnm", "khole", "ko", "ka",
    "kt0", "kt1", "kt2", "kt3", "kt4", "kt5", "kt6", "kt7", "kt8", "kt9",
    "kf", "kuser0", "kuser1", "kuser2", "kcmpnm", "knetwk", "kdatrd", "kinst",
)


class SACHeaderDialog(QDialog):
    """Display the SAC headers of the traces currently loaded in PyPicker.

    Parameters
    ----------
    stream
        ObsPy Stream containing the currently loaded traces. Traces without a
        ``stats.sac`` dictionary are still listed, with their SAC cells empty.
    parent
        Optional Qt parent widget.

    Notes
    -----
    Call :meth:`update_stream` whenever the application's active stream is
    replaced. The dialog also provides a manual Refresh button.
    """

    def __init__(self, stream=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PyPicker - SAC Headers")
        self.resize(1180, 700)

        if utils is not None and hasattr(utils, "get_app_icon"):
            try:
                self.setWindowIcon(utils.get_app_icon("dark"))
            except Exception:  # noqa: BLE001
                logger.debug("Could not set PyPicker application icon", exc_info=True)

        self.stream = stream
        self._records = []
        self._header_keys = []

        self._init_ui()
        self.refresh_table()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

        # Controls, following the compact toolbar style used by MapDialog.
        ctrl_bar = QHBoxLayout()
        ctrl_bar.setSpacing(8)

        ctrl_bar.addWidget(QLabel("<b>Filtro:</b>"))
        self.search_edit = QLineEdit()
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setPlaceholderText("Cerca in ID traccia e campi SAC...")
        self.search_edit.textChanged.connect(self._apply_filter)
        ctrl_bar.addWidget(self.search_edit, stretch=1)

        self.btn_refresh = QPushButton("Aggiorna")
        self.btn_refresh.setToolTip("Aggiorna la tabella usando lo stream attualmente caricato")
        self.btn_refresh.clicked.connect(self.refresh_table)
        ctrl_bar.addWidget(self.btn_refresh)

        self.btn_copy = QPushButton("Copia tabella")
        self.btn_copy.setToolTip("Copia negli appunti le righe attualmente visibili")
        self.btn_copy.clicked.connect(self._copy_visible_table)
        ctrl_bar.addWidget(self.btn_copy)

        self.btn_export = QPushButton("Esporta CSV")
        self.btn_export.setToolTip("Esporta tutti gli header SAC dello stream in un file CSV")
        self.btn_export.clicked.connect(self._export_csv)
        ctrl_bar.addWidget(self.btn_export)

        layout.addLayout(ctrl_bar)

        self.table = QTableWidget(self)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

        horizontal_header = self.table.horizontalHeader()
        horizontal_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        horizontal_header.setStretchLastSection(False)
        self.table.verticalHeader().setVisible(True)
        self.table.verticalHeader().setDefaultSectionSize(24)

        layout.addWidget(self.table, stretch=1)

        self.status_bar = QStatusBar()
        self.status_bar.setSizeGripEnabled(False)
        layout.addWidget(self.status_bar)

    @staticmethod
    def _get_sac_header(trace):
        """Return a plain dictionary of SAC fields for an ObsPy Trace."""
        stats = getattr(trace, "stats", None)
        if stats is None:
            return {}

        try:
            sac = stats.get("sac")
        except (AttributeError, TypeError):
            sac = getattr(stats, "sac", None)

        if sac is None:
            return {}

        try:
            return {str(key): value for key, value in sac.items()}
        except (AttributeError, TypeError, ValueError):
            try:
                return {str(key): value for key, value in dict(sac).items()}
            except (TypeError, ValueError):
                logger.warning("Unable to read SAC header from trace %r", trace, exc_info=True)
                return {}

    @staticmethod
    def _get_trace_id(trace):
        """Build a readable SEED id, with a fallback for non-ObsPy objects."""
        trace_id = getattr(trace, "id", None)
        if trace_id:
            return str(trace_id)

        stats = getattr(trace, "stats", None)
        if stats is None:
            return "Trace"

        def get_value(key):
            try:
                value = stats.get(key, "")
            except (AttributeError, TypeError):
                value = getattr(stats, key, "")
            return "" if value is None else str(value)

        return ".".join(
            get_value(key) for key in ("network", "station", "location", "channel")
        )

    @staticmethod
    def _format_value(value):
        """Convert SAC values to readable table/CSV strings."""
        if value is None:
            return ""

        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace").rstrip("\x00 ")

        # Support NumPy scalar values without making NumPy a hard dependency.
        if hasattr(value, "item") and callable(value.item):
            try:
                value = value.item()
            except (TypeError, ValueError):
                pass

        if isinstance(value, (list, tuple)):
            return ", ".join(SACHeaderDialog._format_value(item) for item in value)

        if hasattr(value, "isoformat") and callable(value.isoformat):
            try:
                return value.isoformat()
            except (TypeError, ValueError):
                pass

        return str(value)

    def _read_stream(self):
        if self.stream is None:
            return []
        try:
            return list(self.stream)
        except TypeError:
            logger.warning("The supplied stream is not iterable")
            return []

    def refresh_table(self):
        """Rebuild the table from the currently assigned ObsPy Stream."""
        traces = self._read_stream()
        records = []
        all_keys = set()

        for trace in traces:
            sac_header = self._get_sac_header(trace)
            all_keys.update(sac_header.keys())
            records.append(
                {
                    "trace_id": self._get_trace_id(trace),
                    "has_sac": bool(sac_header),
                    "header": sac_header,
                }
            )

        ordered_keys = [key for key in SAC_HEADER_ORDER if key in all_keys]
        ordered_keys.extend(sorted(all_keys.difference(ordered_keys), key=str.lower))

        self._records = records
        self._header_keys = ordered_keys
        self._populate_table()
        self._apply_filter(self.search_edit.text())

        with_sac = sum(1 for record in records if record["has_sac"])
        self.status_bar.showMessage(
            f"Tracce: {len(records)} | Con header SAC: {with_sac} | "
            f"Campi SAC distinti: {len(ordered_keys)}"
        )

    def update_stream(self, stream):
        """Replace the active stream and refresh the table."""
        self.stream = stream
        self.refresh_table()

    def _populate_table(self):
        """Fill the QTableWidget, retaining all SAC keys found in the stream."""
        headers = ["Trace ID", "SAC"] + self._header_keys

        # Sorting during insertion can move rows while they are being filled.
        sorting_was_enabled = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)
        self.table.clear()
        self.table.setRowCount(len(self._records))
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)

        for row_index, record in enumerate(self._records):
            trace_item = QTableWidgetItem(record["trace_id"])
            trace_item.setToolTip(record["trace_id"])
            self.table.setItem(row_index, 0, trace_item)

            sac_item = QTableWidgetItem("Sì" if record["has_sac"] else "No")
            sac_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row_index, 1, sac_item)

            for column_index, key in enumerate(self._header_keys, start=2):
                text = self._format_value(record["header"].get(key))
                item = QTableWidgetItem(text)
                if text:
                    item.setToolTip(text)
                self.table.setItem(row_index, column_index, item)

        self.table.setColumnWidth(0, 230)
        self.table.setColumnWidth(1, 55)
        for column_index in range(2, len(headers)):
            self.table.setColumnWidth(column_index, 105)

        self.table.setSortingEnabled(sorting_was_enabled)

    def _apply_filter(self, text):
        """Show only traces with at least one matching cell."""
        query = (text or "").strip().casefold()
        visible_count = 0
        visible_with_sac = 0

        for row in range(self.table.rowCount()):
            matches = not query
            if query:
                for column in range(self.table.columnCount()):
                    item = self.table.item(row, column)
                    if item and query in item.text().casefold():
                        matches = True
                        break
            self.table.setRowHidden(row, not matches)
            if matches:
                visible_count += 1
                sac_item = self.table.item(row, 1)
                if sac_item and sac_item.text() == "Sì":
                    visible_with_sac += 1

        total = len(self._records)
        total_with_sac = sum(1 for record in self._records if record["has_sac"])
        self.status_bar.showMessage(
            f"Tracce visibili: {visible_count}/{total} | "
            f"Con header SAC: {visible_with_sac} (totale {total_with_sac}) | "
            f"Campi SAC distinti: {len(self._header_keys)}"
        )

    def _visible_row_indexes(self):
        return [row for row in range(self.table.rowCount()) if not self.table.isRowHidden(row)]

    def _copy_visible_table(self):
        """Copy the header row and visible trace rows as tab-separated text."""
        if self.table.columnCount() == 0:
            return

        lines = ["\t".join(self.table.horizontalHeaderItem(col).text() for col in range(self.table.columnCount()))]
        for row in self._visible_row_indexes():
            values = []
            for column in range(self.table.columnCount()):
                item = self.table.item(row, column)
                values.append(item.text() if item else "")
            lines.append("\t".join(values))

        from PyQt6.QtWidgets import QApplication

        QApplication.clipboard().setText("\n".join(lines))
        self.status_bar.showMessage(
            f"Copiate {max(len(lines) - 1, 0)} righe negli appunti", 3000
        )

    def _export_csv(self):
        """Export every loaded trace and all discovered SAC fields to CSV."""
        if not self._records:
            QMessageBox.information(self, "Esporta CSV", "Non ci sono tracce da esportare.")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Esporta header SAC",
            "sac_headers.csv",
            "File CSV (*.csv);;Tutti i file (*)",
        )
        if not filename:
            return

        path = Path(filename)
        if path.suffix.lower() != ".csv":
            path = path.with_suffix(".csv")

        headers = ["Trace ID", "SAC"] + self._header_keys
        try:
            # utf-8-sig makes the file open cleanly in common spreadsheet tools.
            with path.open("w", newline="", encoding="utf-8-sig") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(headers)
                for record in self._records:
                    row = [record["trace_id"], "Sì" if record["has_sac"] else "No"]
                    row.extend(
                        self._format_value(record["header"].get(key))
                        for key in self._header_keys
                    )
                    writer.writerow(row)
        except OSError as exc:
            logger.exception("Failed to export SAC headers to %s", path)
            QMessageBox.critical(
                self,
                "Errore esportazione",
                f"Impossibile salvare il file:\n{path}\n\n{exc}",
            )
            return

        self.status_bar.showMessage(f"Esportati {len(self._records)} record in {path}", 5000)


# Alias with conventional mixed-case spelling, useful for integrations that
# prefer CamelCase class names.
SacHeaderDialog = SACHeaderDialog
