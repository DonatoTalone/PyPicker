import dash
from dash import dcc, html, Input, Output, State, callback_context
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from obspy import UTCDateTime
import picker_utils as utils
import numpy as np


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

    # Colori Componenti
    comp_colors = {"Z": "#e74c3c", "N": "#2ecc71", "E": "#3498db", "default": "#9b59b6"}
    # Colori Fasi
    phase_colors = {"P": "#f1c40f", "S": "#e67e22", "default": "#1abc9c"}

    themes = {
        "light": {
            "bg": "#ffffff",
            "sidebar": "#f1f2f6",
            "text": "#2f3542",
            "template": "plotly_white",
            "grid": "#dcdde1",
            "input_bg": "#ffffff",
        },
        "dark": {
            "bg": "#1e272e",
            "sidebar": "#2f3542",
            "text": "#E759F4FF",
            "template": "plotly_dark",
            "grid": "#57606f",
            "input_bg": "#a5d4ff",
        },
    }

    app.layout = html.Div(
        id="main-container",
        children=[
            # Contenitore per il CSS dinamico (risolve il problema dei Dropdown bianchi)
            html.Div(id="css-container"),
            # Header
            html.Div(
                [
                    html.H3(
                        "Seismic Picker v2.5",
                        style={"margin": "0", "padding": "10px 20px"},
                    )
                ],
                id="header",
            ),
            # Layout Principale
            html.Div(
                [
                    # SIDEBAR
                    html.Div(
                        [
                            html.Label("Tema:"),
                            dcc.Dropdown(
                                id="theme-sel",
                                options=[
                                    {"label": "Light Mode", "value": "light"},
                                    {"label": "Dark Mode", "value": "dark"},
                                ],
                                value="light",
                                clearable=False,
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
                                labelStyle={"display": "block"},
                            ),
                            html.Br(),
                            html.Label("Colori Tracce:"),
                            dcc.RadioItems(
                                id="color-mode",
                                options=[
                                    {
                                        "label": " Unico (Bianco/Nero)",
                                        "value": "single",
                                    },
                                    {"label": " Per Componente (ZNE)", "value": "comp"},
                                ],
                                value="comp",
                                labelStyle={"display": "block"},
                            ),
                            html.Hr(),
                            html.Label("Preprocessing:"),
                            dcc.Checklist(
                                id="p-demean",
                                options=[{"label": " Demean", "value": "y"}],
                                value=["y"],
                            ),
                            dcc.Checklist(
                                id="p-detrend",
                                options=[{"label": " Detrend", "value": "y"}],
                                value=["y"],
                            ),
                            html.Label(
                                "Filtro:",
                                style={"marginTop": "10px", "display": "block"},
                            ),
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
                                        style={"width": "45%", "marginLeft": "5%"},
                                    ),
                                ],
                                style={"marginTop": "5px"},
                            ),
                            html.Hr(),
                            html.Label("Guadagno (Vertical Zoom):"),
                            dcc.Slider(
                                id="v-zoom",
                                min=0.5,
                                max=100,
                                value=1,
                                step=0.5,
                                marks={1: "1x", 50: "50x", 100: "100x"},
                            ),
                            html.Hr(),
                            html.Label("Fase:"),
                            dcc.RadioItems(
                                id="ph-sel",
                                options=[
                                    {"label": " P", "value": "P"},
                                    {"label": " S", "value": "S"},
                                    {"label": " Custom", "value": "custom"},
                                ],
                                value="P",
                                inline=True,
                            ),
                            dcc.Input(
                                id="ph-custom",
                                type="text",
                                placeholder="es. Pn",
                                style={"width": "100%", "marginTop": "5px"},
                            ),
                            html.Br(),
                            html.Br(),
                            html.Button(
                                "Esporta JSON", id="btn-exp", className="custom-button"
                            ),
                        ],
                        id="sidebar",
                        style={
                            "width": "260px",
                            "padding": "20px",
                            "flexShrink": "0",
                            "height": "calc(100vh - 50px)",
                            "overflowY": "auto",
                        },
                    ),
                    # AREA GRAFICA
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
                                                style={"width": "250px"},
                                            ),
                                        ],
                                        style={"marginRight": "30px"},
                                    ),
                                    html.Div(
                                        [
                                            html.Label("Zoom Orizzontale:"),
                                            dcc.Slider(
                                                id="h-zoom",
                                                min=1,
                                                max=20,
                                                value=1,
                                                step=1,
                                                marks={1: "1x", 10: "10x", 20: "20x"},
                                            ),
                                        ],
                                        style={"flexGrow": "1"},
                                    ),
                                ],
                                style={
                                    "display": "flex",
                                    "padding": "10px",
                                    "alignItems": "center",
                                },
                            ),
                            dcc.Graph(
                                id="plot",
                                style={"flexGrow": "1"},
                                config={"displaylogo": False},
                            ),
                            html.Div(
                                id="table-out",
                                style={
                                    "padding": "10px",
                                    "overflowY": "auto",
                                    "maxHeight": "150px",
                                },
                            ),
                        ],
                        id="main-content",
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
        style={"height": "100vh", "margin": "0", "overflow": "hidden"},
    )

    @app.callback(
        [
            Output("plot", "figure"),
            Output("pick-store", "data"),
            Output("table-out", "children"),
            Output("main-container", "style"),
            Output("sidebar", "style"),
            Output("header", "style"),
            Output("css-container", "children"),
        ],
        [
            Input("theme-sel", "value"),
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
        theme_name,
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
        ctx = callback_context
        t = themes[theme_name]
        active_ph = p_cust if p_sel == "custom" and p_cust else p_sel

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
                if c_mode == "comp"
                else ("#ffffff" if theme_name == "dark" else "#000000")
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
                        customdata=[
                            [tr.stats.network, tr.stats.station, tr.stats.channel]
                        ]
                        * len(x),
                    ),
                    row=i,
                    col=1,
                )

                max_amp = np.max(np.abs(y)) if len(y) > 0 else 1
                fig.update_yaxes(
                    range=[-max_amp / v_zoom, max_amp / v_zoom],
                    row=i,
                    col=1,
                    gridcolor=t["grid"],
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
                            bgcolor=t["bg"],
                            row=i,
                            col=1,
                        )
            else:
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
                    gridcolor=t["grid"],
                )
                fig.update_xaxes(
                    title_text="Freq (Hz)", row=i, col=1, gridcolor=t["grid"]
                )

        if view == "wave":
            dur = traces[0].stats.endtime - traces[0].stats.starttime
            fig.update_xaxes(
                range=[0, dur / h_zoom], title_text="Secondi", gridcolor=t["grid"]
            )

        fig.update_layout(
            template=t["template"],
            showlegend=False,
            margin=dict(l=60, r=20, t=30, b=50),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )

        # FIX dei colori Dropdown e Input tramite CSS iniettato
        dropdown_css = f"""
        <style>
            .Select-control, .Select-menu-outer, .VirtualizedSelectFocusedOption {{ 
                background-color: {t["input_bg"]} !important; color: {t["text"]} !important; 
            }}
            .Select-value-label, .Select-placeholder {{ color: {t["text"]} !important; }}
            input {{ background-color: {t["input_bg"]} !important; color: {t["text"]} !important; border: 1px solid {t["grid"]}; }}
            .custom-button {{ background-color: #3498db; color: white; border: none; padding: 10px; cursor: pointer; border-radius: 4px; width: 100%; }}
            .custom-button:hover {{ background-color: #2980b9; }}
        </style>
        """

        container_style = {
            "backgroundColor": t["bg"],
            "color": t["text"],
            "transition": "0.3s",
        }
        sidebar_style = {
            "backgroundColor": t["sidebar"],
            "borderRight": f"1px solid {t['grid']}",
        }
        header_style = {
            "borderBottom": f"1px solid {t['grid']}",
            "backgroundColor": t["sidebar"],
        }

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
                "color": t["text"],
                "borderCollapse": "collapse",
                "fontSize": "12px",
            },
        )

        return (
            fig,
            picks,
            table,
            container_style,
            sidebar_style,
            header_style,
            dcc.Markdown(dropdown_css, dangerously_allow_html=True),
        )

    return app
