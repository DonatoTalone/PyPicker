# Wadati Analysis Plugin: Standard & Modified Wadati Plots

PyPicker includes a **Wadati Analysis plugin** for comparing P- and S-wave arrival times from the picks currently loaded in the waveform viewer. It creates a standard Wadati plot and a modified, pairwise-difference Wadati plot, each with an independent least-squares linear regression.

---

## 1. Overview & Key Capabilities

- **Standard Wadati Plot**: Displays the S−P arrival-time difference against the P arrival time.
- **Modified Wadati Plot**: Displays S-time differences against P-time differences for every unique pair of stations with both P and S picks.
- **Independent Linear Regressions**: Fits each plot separately and reports the slope, intercept, coefficient of determination (R²), number of observations, and estimated Vp/Vs ratio.
- **Interactive Station Identification**: Hover over a point to show the station or station pair and its pick times. Click a point to pin its annotation; click it again or click empty plot space to release it.
- **Automatic Pick Refresh**: Checks the active PyPicker pick list while the dialog is visible and redraws when picks are added, removed, or edited.
- **Figure Export**: Exports both plots together as a high-resolution PNG or PDF.
- **Data Export**: Exports the observations used by both plots to a single CSV file.
- **Read-only Analysis**: The plugin does not change picks, waveform samples, or SAC headers.

---

## 2. Launching Wadati Analysis

Open the plugin from either location:
- Press the **`W`** key (default shortcut).
- Select **Plugins → Wadati Analysis (W)** from the top menu bar.

The shortcut can be changed in `config/config.json` or the user configuration file:

```json
{
    "shortcuts": {
        "open_wadati": "W"
    }
}
```

The dialog can remain open beside the waveform viewer. It reads the in-memory picks from the current PyPicker session.

---

## 3. Standard Wadati Plot

The standard plot uses stations for which both a P and an S pick are available:

\[
 x_i = t_{P_i}, \qquad y_i = t_{S_i} - t_{P_i}
\]

It fits a straight line:

\[
 y = mx + q
\]

The slope gives the Vp/Vs estimate:

\[
 \frac{V_P}{V_S} = m + 1
\]

### P-time reference

When a completed Hypo71 solution is available, the x-axis uses the P travel time measured from that solution's origin time. Otherwise, the plugin subtracts the earliest P pick from all P times and labels the axis as a relative P-arrival time. This constant time shift does not change the fitted slope, but it does change the fitted intercept. The fallback reference must therefore be considered when interpreting `q`.

---

## 4. Modified Wadati Plot

The modified plot uses every unique, unordered pair of stations that have both P and S picks. For a pair of stations A and B:

\[
 x_{AB} = t_{P_A} - t_{P_B}
\]

\[
 y_{AB} = t_{S_A} - t_{S_B}
\]

The fitted relation is:

\[
 y = mx + q
\]

For this plot, the slope directly estimates:

\[
 \frac{V_P}{V_S} = m
\]

Only one point is generated for each station pair; the reversed pair is not added as a duplicate. The intercept is displayed as a diagnostic and should ideally be close to zero.

Because pairwise points share stations, they are not statistically independent. The modified regression is therefore useful as a complementary diagnostic, but its R² should not be interpreted as if every pair were an independent station observation.

---

## 5. Pick Selection & Data Requirements

- Only phases named exactly **P** and **S** (case-insensitive) are used. Custom phases are ignored.
- A station contributes to either plot only when it has at least one valid P pick and one valid S pick.
- If multiple P or S picks exist for the same station, the plugin selects the pick with the smallest non-negative uncertainty. Missing uncertainties sort after numeric uncertainties; ties are resolved using the earlier pick time.
- Additional picks for the same station and phase are not included in the analysis. Their number is reported in the status line.
- Picks with missing station identifiers or unparseable times are excluded.
- The plugin does not automatically reject negative S−P values or statistical outliers; these remain visible for inspection.

At least two paired stations with distinct P-time values are needed to fit the standard regression. The modified plot needs at least two distinct pairwise x-values to fit a line (normally at least three paired stations).

---

## 6. Controls & Interaction

| Control | Description |
|---|---|
| **Refresh** | Rebuilds both plots immediately from the current pick list. |
| **Show linear regression** | Toggles the fitted lines and their regression details in the legends. |
| **Export PNG** | Saves the two-panel figure as a 300 dpi PNG image. |
| **Export PDF** | Saves the two-panel figure as a vector PDF. |
| **Export CSV** | Exports standard station observations and modified station-pair observations in one CSV file. |

### Point annotations

- **Hover** over a standard Wadati point to display its station, P and S pick times, S−P value, and pick uncertainties.
- **Hover** over a modified Wadati point to display the station pair, ΔP, ΔS, and the four corresponding pick times.
- **Left-click** a point to pin its annotation while moving the cursor. Click the same point again or click empty space in that plot to unpin it.
- The Matplotlib navigation toolbar provides normal zoom, pan, and figure navigation tools.

---

## 7. Regression Parameters

Each plot's legend reports:

- **Slope (`m`)** and **intercept (`q`)** of the fitted line.
- **Vp/Vs estimate** (`m + 1` for the standard plot; `m` for the modified plot).
- **R²**, the coefficient of determination for the fitted observations.
- **N**, the number of plotted observations (stations in the standard plot; unique station pairs in the modified plot).

Both regressions use ordinary least squares with an intercept. No uncertainty weighting or automatic outlier removal is applied.
