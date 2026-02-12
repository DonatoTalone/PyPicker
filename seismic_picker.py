import dash
from dash import dcc, html, Input, Output, State, callback_context as ctx
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from obspy import UTCDateTime
import picker_utils as utils
import numpy as np

# Palette colori costante
THEME = {
    "bg": "#f0f2f6",
    "sidebar": "#ffffff",
    "text": "#2c3e50",
    "grid": "#d1d9e6",
    "btn": "#636EFA",
}

comp_colors = {"Z": "#ff4757", "N": "#2ed573", "E": "#1e90ff", "default": "#70a1ff"}
phase_colors = {"P": "#ffa502", "S": "#ff4757", "default": "#747d8c"}

class SeismicPicker:
    def __init__(self, stream):
        self.original_stream = stream.copy()
        self.processed_stream = stream.copy()
        self.picks = []
        self.stations = self._get_stations()

    def _get_stations(self):
        seen = set()
        stations = []
        for tr in self.original_stream:
            s_id = f"{tr.stats.network}.{tr.stats.station}"
            if s_id not in seen:
                stations.append(
                    {"id": s_id, "net": tr.stats.network, "sta": tr.stats.station}
                )
                seen.add(s_id)
        return stations


def create_dash_app(picker):
    app = dash.Dash(__name__)

    app.layout = html.Div(
        id="main-container",
        children=[
            html.Div(
                [
                    html.H3(
                        "Seismic Picker",
                        style={"margin": "0", "padding": "10px 20px"},
                    )
                ],
                id="header",
            ),
            html.Div(
                [
                    # SIDEBAR
                    html.Div(
                        [
                            html.Label("Visualizzazione:"),
                            dcc.RadioItems(
                                id="view-type",
                                options=[
                                    {"label": " Waveform", "value": "wave"},
                                    {"label": " Spettro", "value": "spec"},
                                ],
                                value="wave",
                                className="dash-radioitem",
                            ),
                            html.Hr(),
                            html.Label("Fase Attiva:"),
                            dcc.Dropdown(
                                id="ph-sel",
                                options=[
                                    {"label": "P", "value": "P"},
                                    {"label": "S", "value": "S"},
                                    {"label": "Altro", "value": "custom"},
                                ],
                                value="P",
                            ),
                            dcc.Input(
                                id="ph-custom",
                                placeholder="Inserisci fase...",
                                style={"marginTop": "5px"},
                            ),
                            html.Hr(),
                            html.Label("Filtro:"),
                            dcc.Dropdown(
                                id="f-type",
                                options=[
                                    {"label": "Nessuno", "value": "none"},
                                    {"label": "Passa-banda", "value": "bandpass"},
                                ],
                                value="none",
                            ),
                            html.Div(
                                [
                                    dcc.Input(
                                        id="f-low",
                                        type="number",
                                        value=1,
                                        style={"width": "45%"},
                                    ),
                                    dcc.Input(
                                        id="f-high",
                                        type="number",
                                        value=10,
                                        style={"width": "45%", "marginLeft": "10%"},
                                    ),
                                ],
                                style={"marginTop": "5px"},
                            ),
                            html.Hr(),
                            html.Label("Processing:"),
                            dcc.Checklist(
                                id="p-demean",
                                options=[{"label": " Demean", "value": "y"}],
                                value=["y"],
                                className="dash-checklist",
                            ),
                            dcc.Checklist(
                                id="p-detrend",
                                options=[{"label": " Detrend", "value": "y"}],
                                value=["y"],
                                className="dash-checklist",
                            ),
                            html.Hr(),
                            html.Label("Colori:"),
                            dcc.RadioItems(
                                id="color-mode",
                                options=[
                                    {"label": " Componente", "value": "comp"},
                                    {"label": " Mono", "value": "mono"},
                                ],
                                value="comp",
                                className="dash-radioitem",
                            ),
                            html.Hr(),
                            html.Label("V-Zoom:"),
                            dcc.Slider(
                                id="v-zoom",
                                min=1,
                                max=100,
                                value=1,
                                marks={1: "1x", 100: "100x"},
                            ),
                            html.Br(),
                            html.Button(
                                "Esporta picking", id="btn-exp", className="custom-button"
                            ),
                        ],
                        id="sidebar",
                        style={
                            "width": "260px",
                            "padding": "20px",
                            "height": "calc(100vh - 50px)",
                            "overflowY": "auto",
                        },
                    ),
                    # AREA GRAFICA
                    html.Div(
                        [
                            html.Div(
                                [
                                    dcc.Dropdown(
                                        id="sta-sel",
                                        options=[
                                            {"label": s["id"], "value": i}
                                            for i, s in enumerate(picker.stations)
                                        ],
                                        value=0,
                                        style={"width": "250px"},
                                    ),
                                    html.Div(
                                        [
                                            html.Label(
                                                "H-Zoom:",
                                                style={
                                                    "marginLeft": "20px",
                                                    "marginRight": "10px",
                                                },
                                            ),
                                            dcc.Slider(
                                                id="h-zoom",
                                                min=1,
                                                max=20,
                                                value=1,
                                                step=1,
                                                marks={1: "1x", 10: "10x", 20: "20x"},
                                            ),
                                        ],
                                        style={
                                            "flexGrow": "1",
                                            "display": "flex",
                                            "alignItems": "center",
                                        },
                                    ),
                                ],
                                style={
                                    "display": "flex",
                                    "padding": "10px",
                                    "alignItems": "center",
                                },
                            ),
                            dcc.Graph(id="plot", style={"flexGrow": "1"}),
                            html.Div(
                                id="table-out",
                                style={
                                    "padding": "10px",
                                    "overflowY": "auto",
                                    "maxHeight": "150px",
                                },
                            ),
                        ],
                        style={
                            "flexGrow": "1",
                            "display": "flex",
                            "flexDirection": "column",
                        },
                    ),
                ],
                style={"display": "flex", "flexDirection": "row"},
            ),
            dcc.Store(id="pick-store", data=[]),
        ],
    )

    @app.callback(
        [
            Output("plot", "figure"),
            Output("pick-store", "data"),
            Output("table-out", "children"),
        ],
        [
            Input("sta-sel", "value"),
            Input("h-zoom", "value"),
            Input("v-zoom", "value"),
            Input("f-type", "value"),
            Input("f-low", "value"),
            Input("f-high", "value"),
            Input("p-demean", "value"),
            Input("p-detrend", "value"),
            Input("view-type", "value"),
            Input("color-mode", "value"),
            Input("plot", "clickData"),
        ],
        [
            State("ph-sel", "value"),
            State("ph-custom", "value"),
            State("pick-store", "data"),
        ],
    )

    def update_app(
        sta_idx,
        h_zoom,
        v_zoom,
        ft,
        fl,
        fh,
        demean,
        detrend,
        view,
        c_mode,
        click,
        p_sel,
        p_cust,
        picks,
    ):
        active_ph = p_cust if p_sel == "custom" else p_sel

        # 1. Processing
        p_params = {
            "demean": "y" in demean,
            "detrend": "y" in detrend,
            "filter_type": ft,
            "low_f": fl,
            "high_f": fh,
        }
        picker.processed_stream = utils.apply_preprocessing(
            picker.original_stream, p_params
        )

        # 2. Picking
        if (
            ctx.triggered
            and "plot.clickData" in ctx.triggered[0]["prop_id"]
            and click
            and view == "wave"
        ):
            p = click["points"][0]
            # La customdata viene passata nel momento della creazione del trace
            net, sta, cha = p["customdata"]
            tr = picker.original_stream.select(network=net, station=sta, channel=cha)[0]
            abs_t = tr.stats.starttime + p["x"]
            picks.append(
                {"sta": sta, "cha": cha, "phase": active_ph, "time": str(abs_t)}
            )

        # 3. Creazione Figura
        station = picker.stations[sta_idx]
        traces = picker.processed_stream.select(
            network=station["net"], station=station["sta"]
        )
        traces = sorted(traces, key=lambda x: x.stats.channel[-1], reverse=True)

        fig = make_subplots(
            rows=len(traces),
            cols=1,
            shared_xaxes=(view == "wave"),
            vertical_spacing=0.05,
        )

        for i, tr in enumerate(traces, 1):
            ch_last = tr.stats.channel[-1].upper()
            line_color = (
                comp_colors.get(ch_last, comp_colors["default"])
            )

            if view == "wave":
                x, y = tr.times(), tr.data
                fig.add_trace(
                    go.Scatter(
                        x=x,
                        y=y,
                        mode="lines",
                        name=tr.stats.channel,
                        line=dict(color=line_color, width=1),
                        customdata=np.array(
                            [[tr.stats.network, tr.stats.station, tr.stats.channel]]
                            * len(x)
                        ),
                    ),
                    row=i,
                    col=1,
                )

                max_amp = np.max(np.abs(y)) if len(y) > 0 else 1
                fig.update_yaxes(
                    range=[-max_amp / v_zoom, max_amp / v_zoom],
                    row=i,
                    col=1,
                    gridcolor=THEME["grid"],
                )

                yref_name = f"y{i if i > 1 else ''} domain"
                for pk in picks:
                    if pk["sta"] == tr.stats.station:
                        p_rel = UTCDateTime(pk["time"]) - tr.stats.starttime
                        p_col = phase_colors.get(pk["phase"], phase_colors["default"])
                        fig.add_vline(
                            x=p_rel,
                            line=dict(color=p_col, dash="dot", width=2),
                            row=i,
                            col=1,
                        )
                        fig.add_annotation(
                            x=p_rel,
                            y=1,
                            yref=yref_name,
                            text=pk["phase"],
                            showarrow=False,
                            font=dict(color=p_col, size=11),
                            bgcolor=THEME["bg"],
                            row=i,
                            col=1,
                        )
            else:
                # Modalità Spettro
                freq, spec = utils.get_spectrum(tr)
                fig.add_trace(
                    go.Scatter(
                        x=freq,
                        y=spec,
                        mode="lines",
                        name=f"Spec {tr.stats.channel}",
                        line=dict(color=line_color),
                    ),
                    row=i,
                    col=1,
                )
                max_spec = np.max(spec) if len(spec) > 0 else 1
                fig.update_yaxes(
                    range=[0, max_spec / v_zoom],
                    row=i,
                    col=1,
                    title_text="Amp",
                    gridcolor=THEME["grid"],
                )
                fig.update_xaxes(
                    title_text="Freq (Hz)", row=i, col=1, gridcolor=THEME["grid"]
                )

        if view == "wave":
            dur = traces[0].stats.endtime - traces[0].stats.starttime
            fig.update_xaxes(
                range=[0, dur / h_zoom], title_text="Secondi", gridcolor=THEME["grid"]
            )

        fig.update_layout(
            template="plotly_white",
            showlegend=False,
            margin=dict(l=60, r=20, t=30, b=50),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(255,255,255,0.4)",
        )

        table = html.Table(
            [
                html.Thead(
                    html.Tr([html.Th(h) for h in ["STA", "CHA", "PHASE", "UTC TIME"]])
                ),
                html.Tbody(
                    [
                        html.Tr(
                            [
                                html.Td(x["sta"]),
                                html.Td(x["cha"]),
                                html.Td(x["phase"]),
                                html.Td(x["time"][-15:]),
                            ]
                        )
                        for x in picks
                    ]
                ),
            ],
            style={
                "width": "100%",
                "color": THEME["text"],
                "borderCollapse": "collapse",
                "fontSize": "12px",
            },
        )

        return fig, picks, table

    return app
