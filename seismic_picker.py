import dash
from dash import dcc, html, Input, Output, State, callback_context
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from obspy import UTCDateTime
import picker_utils as utils  # Importiamo le utility
from datetime import datetime


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
        [
            html.H2(
                "Seismic Picker v2.0", style={"textAlign": "center", "color": "#2c3e50"}
            ),
            html.Div(
                [
                    # Pannello di Controllo (Sinistra)
                    html.Div(
                        [
                            html.H4("Preprocessing"),
                            dcc.Checklist(
                                id="proc-check",
                                options=[
                                    {
                                        "label": " Rimuovi Trend/Media",
                                        "value": "detrend",
                                    },
                                ],
                                value=["detrend"],
                                style={"marginBottom": "10px"},
                            ),
                            html.Label("Filtro:"),
                            dcc.Dropdown(
                                id="f-type",
                                options=[
                                    {"label": "Nessuno", "value": "none"},
                                    {"label": "Passa-Banda", "value": "bandpass"},
                                    {"label": "Passa-Alto", "value": "highpass"},
                                    {"label": "Passa-Basso", "value": "lowpass"},
                                ],
                                value="none",
                            ),
                            html.Div(
                                [
                                    html.Label("Freq (Hz) L - H:"),
                                    html.Div(
                                        [
                                            dcc.Input(
                                                id="f-low",
                                                type="number",
                                                value=1.0,
                                                style={"width": "45%"},
                                            ),
                                            dcc.Input(
                                                id="f-high",
                                                type="number",
                                                value=20.0,
                                                style={
                                                    "width": "45%",
                                                    "marginLeft": "5%",
                                                },
                                            ),
                                        ]
                                    ),
                                ],
                                style={"marginTop": "10px"},
                            ),
                            html.Hr(),
                            html.Label("Visualizzazione:"),
                            dcc.RadioItems(
                                id="view-type",
                                options=[
                                    {"label": " Waveform", "value": "wave"},
                                    {"label": " Spettro FFT", "value": "spec"},
                                ],
                                value="wave",
                            ),
                            html.Hr(),
                            html.Label("Fase:"),
                            dcc.RadioItems(
                                id="phase",
                                options=[
                                    {"label": " P", "value": "P"},
                                    {"label": " S", "value": "S"},
                                ],
                                value="P",
                                inline=True,
                            ),
                            html.Br(),
                            html.Button(
                                "Esporta JSON",
                                id="btn-exp",
                                style={
                                    "width": "100%",
                                    "backgroundColor": "#3498db",
                                    "color": "white",
                                },
                            ),
                        ],
                        style={
                            "width": "20%",
                            "float": "left",
                            "padding": "20px",
                            "backgroundColor": "#ecf0f1",
                            "borderRadius": "10px",
                        },
                    ),
                    # Area Grafica (Destra)
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Label("Stazione:"),
                                            dcc.Dropdown(
                                                id="sta-sel",
                                                options=[
                                                    {"label": s["id"], "value": i}
                                                    for i, s in enumerate(
                                                        picker.stations
                                                    )
                                                ],
                                                value=0,
                                            ),
                                        ],
                                        style={
                                            "width": "30%",
                                            "display": "inline-block",
                                        },
                                    ),
                                    html.Div(
                                        [
                                            html.Label("Zoom Tempo:"),
                                            dcc.Slider(
                                                id="zoom-t",
                                                min=1,
                                                max=10,
                                                value=1,
                                                step=1,
                                            ),
                                        ],
                                        style={
                                            "width": "60%",
                                            "display": "inline-block",
                                            "marginLeft": "5%",
                                        },
                                    ),
                                ]
                            ),
                            dcc.Graph(id="plot", style={"height": "70vh"}),
                            html.Div(
                                id="pick-table",
                                style={"marginTop": "20px", "fontSize": "small"},
                            ),
                        ],
                        style={"width": "75%", "float": "right"},
                    ),
                ]
            ),
            dcc.Store(id="store-picks", data=[]),
        ],
        style={"fontFamily": "sans-serif"},
    )

    @app.callback(
        [
            Output("plot", "figure"),
            Output("store-picks", "data"),
            Output("pick-table", "children"),
        ],
        [
            Input("sta-sel", "value"),
            Input("zoom-t", "value"),
            Input("f-type", "value"),
            Input("f-low", "value"),
            Input("f-high", "value"),
            Input("proc-check", "value"),
            Input("view-type", "value"),
            Input("plot", "clickData"),
        ],
        [State("phase", "value"), State("store-picks", "data")],
    )
    def update_ui(sta_idx, zoom, ft, fl, fh, opts, view, click, phase, current_picks):
        ctx = callback_context
        # 1. Processing
        p_params = {
            "detrend": "detrend" in opts,
            "filter_type": ft,
            "low_f": fl,
            "high_f": fh,
            "taper": 0.05,
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
            pt = click["points"][0]
            net, sta, cha = pt["customdata"]
            rel_time = pt["x"]
            tr = picker.original_stream.select(network=net, station=sta, channel=cha)[0]
            abs_time = tr.stats.starttime + rel_time
            current_picks.append(
                {"station": sta, "phase": phase, "time": str(abs_time), "cha": cha}
            )

        # 3. Creazione Figura
        station = picker.stations[sta_idx]
        traces = picker.processed_stream.select(
            network=station["net"], station=station["sta"]
        )
        # Sort Z-N-E
        traces = sorted(traces, key=lambda x: x.stats.channel[-1], reverse=True)

        fig = make_subplots(rows=len(traces), cols=1, shared_xaxes=(view == "wave"))

        for i, tr in enumerate(traces, 1):
            if view == "wave":
                x, y = tr.times(), tr.data
                fig.add_trace(
                    go.Scatter(
                        x=x,
                        y=y,
                        mode="lines",
                        name=tr.stats.channel,
                        line=dict(color="black", width=1),
                        customdata=[
                            [tr.stats.network, tr.stats.station, tr.stats.channel]
                        ]
                        * len(x),
                    ),
                    row=i,
                    col=1,
                )
                # Disegna pick
                for p in current_picks:
                    if p["station"] == tr.stats.station:
                        p_rel = UTCDateTime(p["time"]) - tr.stats.starttime
                        fig.add_vline(
                            x=p_rel,
                            line=dict(
                                color="red" if p["phase"] == "P" else "blue",
                                dash="dash",
                            ),
                            row=i,
                            col=1,
                        )
            else:
                # Modalità Spettro
                freq, spec = utils.get_spectrum(tr)
                fig.add_trace(
                    go.Scatter(
                        x=freq, y=spec, mode="lines", name=f"Spec {tr.stats.channel}"
                    ),
                    row=i,
                    col=1,
                )
                fig.update_xaxes(title_text="Frequenza (Hz)", row=i, col=1)

        if view == "wave":
            dur = traces[0].stats.endtime - traces[0].stats.starttime
            fig.update_xaxes(range=[0, dur / zoom], title_text="Secondi")

        fig.update_layout(showlegend=False, margin=dict(l=40, r=40, t=40, b=40))

        # Tabella pick
        table = html.Table(
            [html.Tr([html.Th(h) for h in ["STA", "CHA", "FASE", "TEMPO"]])]
            + [
                html.Tr(
                    [
                        html.Td(p["station"]),
                        html.Td(p["cha"]),
                        html.Td(p["phase"]),
                        html.Td(p["time"][-12:]),
                    ]
                )
                for p in current_picks
            ],
            style={"width": "100%"},
        )

        return fig, current_picks, table

    return app
