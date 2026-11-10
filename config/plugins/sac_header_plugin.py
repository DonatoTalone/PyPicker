"""PyPicker Plugin: editable table for SAC headers of loaded waveform traces.

The dialog accepts an ObsPy Stream (or any iterable of Trace objects) and
presents one trace per row and one SAC header field per column. SAC cells can
be edited in place; edits are applied immediately to the in-memory ObsPy
Trace objects. They are not written to disk automatically.
"""  # noqa: EXE002

import csv
import logging
import math
import numbers
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
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

SAC_STRING_FIELDS = {key for key in SAC_HEADER_ORDER if key.startswith("k")}
SAC_STRING_FIELDS.add("kevnm")
SAC_INTEGER_FIELDS = {
    "nzyear", "nzjday", "nzhour", "nzmin", "nzsec", "nzmsec", "nvhdr",
    "norid", "nevid", "npts", "nwfid", "nxsize", "nysize", "iftype",
    "idep", "iztype", "iinst", "istreg", "ievreg", "ievtyp", "iqual",
    "isynth", "imagtyp", "imagsrc", "leven", "lpspol", "lovrok", "lcalda",
}


class SACHeaderDialog(QDialog):
    """Display and edit SAC headers for traces currently loaded in PyPicker.

    Each trace occupies one row and each discovered SAC field occupies one
    column. Double-click a SAC cell (or select it and press F2) to edit it.
    A successful edit is immediately applied to ``trace.stats.sac`` in memory.
    It does not modify the source file on disk.

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
            except Exception:
                logger.debug("Could not set PyPicker application icon", exc_info=True)

        self.stream = stream
        self._records = []
        self._header_keys = []
        self._populating = False
        self._committing_edit = False

        self._init_ui()
        self.refresh_table()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

        # Controls, following the compact toolbar style used by MapDialog.
        ctrl_bar = QHBoxLayout()
        ctrl_bar.setSpacing(8)

        ctrl_bar.addWidget(QLabel("<b>Filter:</b>"))
        self.search_edit = QLineEdit()
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setPlaceholderText("Find in ID or SAC fields...")
        self.search_edit.textChanged.connect(self._apply_filter)
        ctrl_bar.addWidget(self.search_edit, stretch=1)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setToolTip("Refresh the table using the currently loaded stream")
        self.btn_refresh.clicked.connect(self.refresh_table)
        ctrl_bar.addWidget(self.btn_refresh)

        self.btn_copy = QPushButton("Copy Table")
        self.btn_copy.setToolTip("Copy the visible rows to the clipboard")
        self.btn_copy.clicked.connect(self._copy_visible_table)
        ctrl_bar.addWidget(self.btn_copy)

        self.btn_export = QPushButton("Export CSV")
        self.btn_export.setToolTip("Export all SAC headers from the stream to a CSV file")
        self.btn_export.clicked.connect(self._export_csv)
        ctrl_bar.addWidget(self.btn_export)

        layout.addLayout(ctrl_bar)

        self.edit_hint = QLabel(
            "Double click on a SAC cell to modify it. "
            "Changes are applied immediately to the in-memory stream, not to the file on disk."
        )
        self.edit_hint.setWordWrap(True)
        layout.addWidget(self.edit_hint)

        self.table = QTableWidget(self)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked
        )
        self.table.setSortingEnabled(True)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.itemChanged.connect(self._on_item_changed)

        horizontal_header = self.table.horizontalHeader()
        horizontal_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)  # ty: ignore[unresolved-attribute]
        horizontal_header.setStretchLastSection(False)  # ty: ignore[unresolved-attribute]
        self.table.verticalHeader().setVisible(True)  # ty: ignore[unresolved-attribute]
        self.table.verticalHeader().setDefaultSectionSize(24)  # ty: ignore[unresolved-attribute]

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

    @staticmethod
    def _convert_header_value(key, text, old_value):
        """Validate and convert an edited cell to an appropriate SAC value."""
        value = text.strip()
        if value == "":
            return None  # Empty cell means remove this key from stats.sac.

        if key in SAC_STRING_FIELDS:
            max_length = 16 if key == "kevnm" else 8
            if len(value) > max_length:
                raise ValueError(
                    f"Il campo {key} ammette al massimo {max_length} caratteri."
                )
            return value

        old_scalar = old_value
        if hasattr(old_scalar, "item") and callable(old_scalar.item):
            try:
                old_scalar = old_scalar.item()
            except (TypeError, ValueError):
                pass

        if key in SAC_INTEGER_FIELDS:
            # Accept only integral notation: 3.0 is intentionally rejected.
            return int(value, 10)

        if key in SAC_HEADER_ORDER:
            converted = float(value)
            if not math.isfinite(converted):
                raise ValueError("Insert a finite number (not NaN or infinity).")
            return converted

        if isinstance(old_scalar, (str, bytes)):
            return value
        if isinstance(old_scalar, numbers.Integral):
            return int(value, 10)
        if isinstance(old_scalar, numbers.Real):
            converted = float(value)
            if not math.isfinite(converted):
                raise ValueError("Insert a finite number (not NaN or infinity).")
            return converted

        # For non-standard fields with no previous value, preserve the user's
        # text rather than guessing a type that SAC itself may not recognize.
        return value

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
                    "trace": trace,
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
            f"Traces: {len(records)} | With SAC Headers: {with_sac} | "
            f"Distinct SAC Fields: {len(ordered_keys)}"
        )

    def update_stream(self, stream):
        """Replace the active stream and refresh the table."""
        self.stream = stream
        self.refresh_table()

    def _populate_table(self):
        """Fill the table and associate each row with its source Trace."""
        headers = ["Trace ID", "SAC"] + self._header_keys

        # Sorting during insertion can move rows while they are being filled.
        sorting_was_enabled = self.table.isSortingEnabled()
        self._populating = True
        self.table.setSortingEnabled(False)
        self.table.clear()
        self.table.setRowCount(len(self._records))
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)

        for row_index, record in enumerate(self._records):
            trace_item = QTableWidgetItem(record["trace_id"])
            trace_item.setToolTip(record["trace_id"])  # ty: ignore[invalid-argument-type]
            # A stable record index is used instead of the visible row number:
            # sorting can reorder rows while editing is in progress.
            trace_item.setData(Qt.ItemDataRole.UserRole, row_index)
            trace_item.setFlags(trace_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row_index, 0, trace_item)

            sac_item = QTableWidgetItem("Sì" if record["has_sac"] else "No")
            sac_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            sac_item.setFlags(sac_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row_index, 1, sac_item)

            for column_index, key in enumerate(self._header_keys, start=2):
                text = self._format_value(record["header"].get(key))  # ty: ignore[unresolved-attribute]
                item = QTableWidgetItem(text)
                item.setToolTip(f"{key}: {text}\nDoppio clic per modificare")
                self.table.setItem(row_index, column_index, item)

        self.table.setColumnWidth(0, 230)
        self.table.setColumnWidth(1, 55)
        for column_index in range(2, len(headers)):
            self.table.setColumnWidth(column_index, 105)

        self.table.setSortingEnabled(sorting_was_enabled)
        self._populating = False

    def _record_index_for_row(self, row):
        item = self.table.item(row, 0)
        if item is None:
            return None
        index = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(index, int) and 0 <= index < len(self._records):
            return index
        return None

    def _on_item_changed(self, item):
        """Commit an edited SAC cell to the corresponding in-memory Trace."""
        if self._populating or self._committing_edit or item is None:
            return

        column = item.column()
        if column < 2:
            return

        record_index = self._record_index_for_row(item.row())
        if record_index is None:
            return

        key_index = column - 2
        if key_index < 0 or key_index >= len(self._header_keys):
            return

        key = self._header_keys[key_index]
        record = self._records[record_index]
        old_value = record["header"].get(key)
        old_text = self._format_value(old_value)
        trace = record["trace"]

        status_message = None
        try:
            new_value = self._convert_header_value(key, item.text(), old_value)
            stats = getattr(trace, "stats", None)
            if stats is None:
                raise ValueError("The trace does not expose a modifiable stats object.")

            sac = getattr(stats, "sac", None)
            if sac is None:
                stats.sac = {}
                sac = stats.sac

            if new_value is None:
                try:
                    sac.pop(key, None)
                except AttributeError:
                    if hasattr(sac, key):
                        delattr(sac, key)
            else:
                sac[key] = new_value

            # Re-read the source header so the table, CSV export and status all
            # reflect the actual object state after ObsPy's own assignments.
            record["header"] = self._get_sac_header(trace)
            record["has_sac"] = bool(record["header"])

            self._committing_edit = True
            item.setText(self._format_value(record["header"].get(key)))
            item.setToolTip(
                f"{key}: {item.text()}\nDouble click to edit"
            )
            indicator = self.table.item(item.row(), 1)
            if indicator is not None:
                indicator.setText("Yes" if record["has_sac"] else "No")
            self._committing_edit = False

            status_message = (
                f"{record['trace_id']} — {key} updated in memory: "
                f"{self._format_value(record['header'].get(key)) or '(field removed)'}. "
                "Not yet saved to disk."
            )
        except (ValueError, TypeError, AttributeError, KeyError) as exc:
            self._committing_edit = True
            item.setText(old_text)
            item.setToolTip(f"{key}: {old_text}\nDouble click to edit")
            self._committing_edit = False
            status_message = f"Invalid value for {key}: {exc}"

        self._apply_filter(self.search_edit.text())
        if status_message:
            self.status_bar.showMessage(status_message, 6000)

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
                record_index = self._record_index_for_row(row)
                if record_index is not None and self._records[record_index]["has_sac"]:
                    visible_with_sac += 1

        total = len(self._records)
        total_with_sac = sum(1 for record in self._records if record["has_sac"])
        self.status_bar.showMessage(
            f"Visible traces: {visible_count}/{total} | "
            f"With SAC header: {visible_with_sac} (total {total_with_sac}) | "
            f"Distinct SAC fields: {len(self._header_keys)}"
        )

    def _visible_row_indexes(self):
        return [row for row in range(self.table.rowCount()) if not self.table.isRowHidden(row)]

    def _copy_visible_table(self):
        """Copy the header row and visible trace rows as tab-separated text."""
        if self.table.columnCount() == 0:
            return

        lines = [
            "\t".join(self.table.horizontalHeaderItem(col).text() for col in range(self.table.columnCount()))  # ty: ignore[unresolved-attribute]
        ]
        for row in self._visible_row_indexes():
            values = []
            for column in range(self.table.columnCount()):
                item = self.table.item(row, column)
                values.append(item.text() if item else "")
            lines.append("\t".join(values))

        from PyQt6.QtWidgets import QApplication

        QApplication.clipboard().setText("\n".join(lines))  # ty: ignore[unresolved-attribute]
        self.status_bar.showMessage(
            f"Copied {max(len(lines) - 1, 0)} rows to clipboard", 3000
        )

    def _export_csv(self):
        """Export every loaded trace and all discovered SAC fields to CSV."""
        if not self._records:
            QMessageBox.information(self, "Export CSV", "There are no traces to export.")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export SAC Headers",
            "sac_headers.csv",
            "CSV File (*.csv);;All Files (*)",
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
                        self._format_value(record["header"].get(key))  # ty: ignore[unresolved-attribute]
                        for key in self._header_keys
                    )
                    writer.writerow(row)
        except OSError as exc:
            logger.exception("Failed to export SAC headers to %s", path)
            QMessageBox.critical(
                self,
                "Export Error",
                f"Unable to save file:\n{path}\n\n{exc}",
            )
            return

        self.status_bar.showMessage(f"Exported {len(self._records)} records to {path}", 5000)


# Alias with conventional mixed-case spelling, useful for integrations that
# prefer CamelCase class names.
SacHeaderDialog = SACHeaderDialog
