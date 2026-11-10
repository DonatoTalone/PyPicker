# SAC Header Plugin: Read & Edit SAC Metadata

PyPicker includes an interactive **SAC Header plugin** for inspecting and editing the SAC metadata associated with the waveform traces currently loaded in the application.

---

## 1. Overview & Key Capabilities

- **Stream-Wide Header Table**: Displays one waveform trace per row, with its trace ID, SAC-header availability, and one column for each SAC field found in the loaded stream.
- **Standard SAC Field Ordering**: Known SAC fields are displayed in a predefined reading order. Additional or custom fields are appended alphabetically, so non-standard metadata is retained and accessible.
- **In-Place Editing**: SAC cells can be edited directly in the table. Valid changes are immediately applied to the corresponding in-memory ObsPy `Trace` object.
- **Automatic Value Validation**: Standard string, integer, and floating-point fields are converted according to their expected type. Invalid values are rejected and the previous value is restored.
- **Dynamic Filtering**: Searches trace IDs and SAC values, hiding rows that do not match the search text.
- **Sorting & Selection**: Table sorting is enabled, and multiple rows can be selected.
- **Clipboard Export**: Copies the table header and currently visible rows as tab-separated text.
- **CSV Export**: Exports all loaded traces and all discovered SAC fields to a CSV file.
- **Non-Destructive to Source Files**: Editing changes the in-memory stream only. The plugin does not automatically write modifications to the original SAC files.

---

## 2. Opening the SAC Header Window

The SAC Header plugin opens in a dedicated **PyPicker - SAC Headers** dialog. It operates on the stream passed to it by the application.

The dialog can be initialized with the active ObsPy `Stream` (or another iterable containing `Trace` objects):

```python
header_dialog = SACHeaderDialog(stream=active_stream, parent=main_window)
header_dialog.show()
```

When PyPicker replaces the active stream, the dialog should be updated with the new stream using `update_stream(stream)`.

---

## 3. Table Layout & Controls

The main table contains one row for each loaded trace. Its first two columns identify the trace and indicate whether a SAC header is available. The remaining columns contain the SAC fields discovered across the stream.

| Column | Description |
|---|---|
| **Trace ID** | Readable SEED identifier (`network.station.location.channel`). |
| **SAC** | Indicates whether the trace currently has SAC header information. |
| **SAC fields** | One column for each distinct header key found in the loaded traces. |

The toolbar above the table provides the following controls:

| Control | Description |
|---|---|
| **Filter** | Finds text in trace IDs and SAC field values. Matching is case-insensitive. |
| **Refresh** | Rebuilds the table from the stream currently assigned to the dialog. |
| **Copy Table** | Copies the column headings and visible rows to the system clipboard as tab-separated text. |
| **Export CSV** | Saves the SAC headers of all loaded traces to a CSV file. |

### Table Navigation

- **Sort**: Click a column header to sort the table by that column.
- **Select Rows**: Click a row to select it. Multiple rows can be selected.
- **Scroll**: Use the horizontal and vertical scroll bars to navigate large tables.
- **Filter**: Type in the Filter field to show only rows containing the search text. Clear the field to show all traces again.

The status bar reports the number of loaded traces, traces with SAC headers, and distinct SAC fields. While a filter is active, it also reports the number of visible traces and the corresponding SAC-header count.

---

## 4. Editing SAC Header Values

To edit a field, **double-click the corresponding SAC cell** or select the cell and press **F2**. The Trace ID and SAC availability columns are informational and cannot be edited.

A valid edit is committed immediately to the corresponding `trace.stats.sac` object in memory. The table is then updated to reflect the value stored by the trace.

### Value Types & Validation

The editor applies type-aware conversion to the entered text:

| Field type | Fields / behavior |
|---|---|
| **String** | SAC string fields (names beginning with `k`) and `kevnm`. The maximum length is 8 characters, or 16 characters for `kevnm`. |
| **Integer** | Integer fields such as `nzyear`, `nzjday`, `npts`, `nvhdr`, and SAC type/flag fields. Integer notation is required; for example, `3.0` is not accepted as an integer. |
| **Floating-point** | Other standard SAC fields. The entered value must be a finite number; `NaN` and infinity are rejected. |
| **Additional/custom fields** | The plugin uses the existing value's type when it can be identified. If no previous value is available, the entered value is preserved as text. |

### Removing a Header Field

Clearing a SAC cell and confirming the edit removes that field from the trace's SAC header. It does not write a replacement value to the source file.

### Invalid Values

If a value fails validation or cannot be assigned, the edit is cancelled, the previous cell value is restored, and an explanatory message is displayed in the status bar.

---

## 5. Copying & Exporting Header Data

### Copy Table

Click **Copy Table** to copy the table headings and the rows currently visible after filtering. The clipboard content is tab-separated and can be pasted into spreadsheet software or a text editor.

### Export CSV

Click **Export CSV** and choose the destination file. The plugin exports:

- Every trace in the dialog's assigned stream, including traces hidden by the current filter.
- The trace ID and SAC-header availability indicator.
- Every distinct SAC field discovered across the stream, using the same column order as the table.

The CSV file is written using UTF-8 with a byte-order mark (`utf-8-sig`) to improve compatibility with common spreadsheet applications. If the selected filename does not have a `.csv` extension, the plugin adds it automatically.

---

## 6. Stream Updates & Data Persistence

The dialog reads header values from the `stats.sac` metadata of each trace in its assigned stream.

- **Refresh**: Re-reads the currently assigned stream and rebuilds the table. Use this after changes made elsewhere in the application.
- **Stream replacement**: Call `update_stream(new_stream)` when the active waveform stream is replaced. This updates the dialog's data source and refreshes the table.
- **Traces without SAC headers**: These traces remain visible in the table. If a SAC field is added to one of them, the plugin creates a SAC header container for that trace.
- **In-memory edits**: Changes are applied immediately to the corresponding trace object, so other components using the same in-memory stream can access the updated metadata.
- **Original files**: The plugin does **not** save edited headers to disk automatically. The source SAC files remain unchanged unless a separate application save/write operation is performed.

No plugin-specific configuration options or local cache are defined in this dialog module.

---
