#!/usr/bin/env python3
"""
Interactive Seismic Waveform Viewer and Picker
Uses ObsPy for seismic data handling and Plotly Dash for interactive visualization
"""

import dash
from dash import dcc, html, Input, Output, State, callback_context
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from obspy import read, UTCDateTime, Stream
from obspy.core.event import Pick, WaveformStreamID, Catalog, Event, Origin
from datetime import datetime
import json

class SeismicPicker:
    def __init__(self, stream):
        """
        Initialize the seismic picker with an ObsPy Stream object
        
        Parameters:
        -----------
        stream : obspy.Stream
            Stream object containing waveform data
        """
        self.stream = stream.copy()
        self.picks = []
        self.current_station_idx = 0
        self.stations = self._get_stations()
        self.view_mode = 'single'  # 'single' or 'all'
        self.time_zoom = 1.0
        self.amplitude_factor = 1.0
        
    def _get_stations(self):
        """Extract unique stations from the stream"""
        stations = []
        for tr in self.stream:
            station_id = f"{tr.stats.network}.{tr.stats.station}"
            if station_id not in [s['id'] for s in stations]:
                stations.append({
                    'id': station_id,
                    'network': tr.stats.network,
                    'station': tr.stats.station
                })
        return stations
    
    def get_station_traces(self, station_id):
        """Get all traces for a specific station"""
        network, station = station_id.split('.')
        return self.stream.select(network=network, station=station)
    
    def create_figure(self):
        """Create the main plotly figure based on current view mode"""
        if self.view_mode == 'single':
            return self._create_single_station_figure()
        else:
            return self._create_all_stations_figure()
    
    def _create_single_station_figure(self):
        """Create figure showing 3 components of a single station"""
        if not self.stations:
            return go.Figure()
        
        station_id = self.stations[self.current_station_idx]['id']
        traces = self.get_station_traces(station_id)
        
        # Sort traces by channel (Z, N, E order preferred)
        channel_order = {'Z': 0, 'N': 1, 'E': 2, '1': 1, '2': 2}
        traces_sorted = sorted(traces, 
                              key=lambda x: channel_order.get(x.stats.channel[-1], 3))
        
        n_traces = len(traces_sorted)
        fig = make_subplots(
            rows=n_traces, 
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.02,
            subplot_titles=[f"{tr.stats.channel}" for tr in traces_sorted]
        )
        
        for idx, tr in enumerate(traces_sorted, 1):
            times = tr.times(type='matplotlib')
            times_relative = (times - times[0]) * 86400  # Convert to seconds
            data = tr.data * self.amplitude_factor
            
            fig.add_trace(
                go.Scatter(
                    x=times_relative,
                    y=data,
                    mode='lines',
                    name=tr.stats.channel,
                    line=dict(width=0.5, color='black'),
                    hovertemplate='Tempo: %{x:.3f}s<br>Ampiezza: %{y:.2e}<extra></extra>'
                ),
                row=idx,
                col=1
            )
            
            # Add picks for this trace
            trace_picks = [p for p in self.picks 
                          if p['station'] == tr.stats.station 
                          and p['channel'] == tr.stats.channel]
            
            for pick in trace_picks:
                pick_time = (pick['time'] - tr.stats.starttime)
                if 0 <= pick_time <= tr.stats.endtime - tr.stats.starttime:
                    fig.add_vline(
                        x=pick_time,
                        line=dict(color='red' if pick['phase'] == 'P' else 'blue', 
                                 width=2, dash='dash'),
                        row=idx,
                        col=1
                    )
                    fig.add_annotation(
                        x=pick_time,
                        y=0.95,
                        yref=f'y{idx} domain',
                        text=pick['phase'],
                        showarrow=False,
                        font=dict(color='red' if pick['phase'] == 'P' else 'blue', size=12),
                        row=idx,
                        col=1
                    )
        
        # Calculate time window based on zoom
        if traces_sorted:
            total_duration = traces_sorted[0].stats.endtime - traces_sorted[0].stats.starttime
            visible_duration = total_duration / self.time_zoom
            
            fig.update_xaxes(
                title_text="Tempo (s)",
                row=n_traces,
                col=1,
                range=[0, visible_duration]
            )
        
        fig.update_yaxes(title_text="Ampiezza")
        fig.update_layout(
            height=200 * n_traces,
            title_text=f"Stazione: {station_id}",
            showlegend=False,
            hovermode='x unified'
        )
        
        return fig
    
    def _create_all_stations_figure(self):
        """Create figure showing all stations"""
        if not self.stream:
            return go.Figure()
        
        # Group traces by station
        station_traces = {}
        for station in self.stations:
            traces = self.get_station_traces(station['id'])
            if traces:
                station_traces[station['id']] = traces
        
        n_stations = len(station_traces)
        fig = make_subplots(
            rows=n_stations,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.01,
            subplot_titles=list(station_traces.keys())
        )
        
        for idx, (station_id, traces) in enumerate(station_traces.items(), 1):
            # Use first trace (typically Z component) for overview
            tr = traces[0]
            times = tr.times(type='matplotlib')
            times_relative = (times - times[0]) * 86400
            data = tr.data * self.amplitude_factor
            
            fig.add_trace(
                go.Scatter(
                    x=times_relative,
                    y=data,
                    mode='lines',
                    name=station_id,
                    line=dict(width=0.5, color='black'),
                    hovertemplate=f'{station_id}<br>Tempo: %{{x:.3f}}s<br>Ampiezza: %{{y:.2e}}<extra></extra>'
                ),
                row=idx,
                col=1
            )
            
            # Add picks
            station_picks = [p for p in self.picks if f"{p['network']}.{p['station']}" == station_id]
            for pick in station_picks:
                pick_time = (pick['time'] - tr.stats.starttime)
                if 0 <= pick_time <= tr.stats.endtime - tr.stats.starttime:
                    fig.add_vline(
                        x=pick_time,
                        line=dict(color='red' if pick['phase'] == 'P' else 'blue', 
                                 width=1.5, dash='dash'),
                        row=idx,
                        col=1
                    )
        
        if station_traces:
            first_trace = list(station_traces.values())[0][0]
            total_duration = first_trace.stats.endtime - first_trace.stats.starttime
            visible_duration = total_duration / self.time_zoom
            
            fig.update_xaxes(
                title_text="Tempo (s)",
                row=n_stations,
                col=1,
                range=[0, visible_duration]
            )
        
        fig.update_yaxes(title_text="Amp")
        fig.update_layout(
            height=150 * n_stations,
            title_text="Tutte le stazioni",
            showlegend=False,
            hovermode='closest'
        )
        
        return fig
    
    def add_pick(self, time, phase, station=None, channel=None):
        """Add a pick to the list"""
        if self.view_mode == 'single' and station is None:
            station_id = self.stations[self.current_station_idx]['id']
            network, station = station_id.split('.')
        
        pick_dict = {
            'time': time,
            'phase': phase,
            'network': network,
            'station': station,
            'channel': channel if channel else '',
            'timestamp': datetime.now().isoformat()
        }
        self.picks.append(pick_dict)
        
    def save_picks(self, filename):
        """Save picks in ObsPy Catalog format"""
        if not self.picks:
            print("Nessun picking da salvare")
            return
        
        catalog = Catalog()
        event = Event()
        
        # Add origin (dummy for now)
        origin = Origin()
        origin.time = UTCDateTime(self.picks[0]['time'])
        event.origins.append(origin)
        
        # Add picks
        for pick_dict in self.picks:
            pick = Pick()
            pick.time = UTCDateTime(pick_dict['time'])
            pick.phase_hint = pick_dict['phase']
            pick.waveform_id = WaveformStreamID(
                network_code=pick_dict['network'],
                station_code=pick_dict['station'],
                channel_code=pick_dict['channel']
            )
            event.picks.append(pick)
        
        catalog.events.append(event)
        catalog.write(filename, format='QUAKEML')
        print(f"Picks salvati in {filename}")
    
    def export_picks_json(self, filename):
        """Export picks as JSON for easy reading"""
        with open(filename, 'w') as f:
            json.dump(self.picks, f, indent=2, default=str)
        print(f"Picks esportati in {filename}")


def create_dash_app(picker):
    """Create and configure the Dash application"""
    app = dash.Dash(__name__)
    
    app.layout = html.Div([
        html.H1("Seismic Waveform Picker", style={'textAlign': 'center'}),
        
        # Control panel
        html.Div([
            html.Div([
                html.Label("Modalità visualizzazione:"),
                dcc.RadioItems(
                    id='view-mode',
                    options=[
                        {'label': ' Stazione Singola', 'value': 'single'},
                        {'label': ' Tutte le Stazioni', 'value': 'all'}
                    ],
                    value='single',
                    inline=True,
                    style={'marginLeft': '10px'}
                )
            ], style={'display': 'inline-block', 'marginRight': '30px'}),
            
            html.Div([
                html.Label("Stazione:"),
                dcc.Dropdown(
                    id='station-selector',
                    options=[{'label': s['id'], 'value': i} 
                            for i, s in enumerate(picker.stations)],
                    value=0,
                    style={'width': '200px', 'marginLeft': '10px'}
                )
            ], id='station-selector-div', style={'display': 'inline-block', 'marginRight': '30px'}),
            
            html.Div([
                html.Label("Zoom Temporale:"),
                dcc.Slider(
                    id='time-zoom',
                    min=0.5,
                    max=10,
                    step=0.5,
                    value=1,
                    marks={i: f'{i}x' for i in [1, 2, 5, 10]},
                    tooltip={"placement": "bottom", "always_visible": True}
                )
            ], style={'display': 'inline-block', 'width': '300px', 'marginRight': '30px'}),
            
            html.Div([
                html.Label("Ampiezza:"),
                dcc.Slider(
                    id='amplitude-factor',
                    min=0.1,
                    max=10,
                    step=0.1,
                    value=1,
                    marks={i: f'{i}x' for i in [0.1, 1, 5, 10]},
                    tooltip={"placement": "bottom", "always_visible": True}
                )
            ], style={'display': 'inline-block', 'width': '300px'})
        ], style={'padding': '20px', 'backgroundColor': '#f0f0f0', 'marginBottom': '20px'}),
        
        # Picking controls
        html.Div([
            html.Label("Tipo di fase:"),
            dcc.RadioItems(
                id='phase-type',
                options=[
                    {'label': ' P', 'value': 'P'},
                    {'label': ' S', 'value': 'S'},
                    {'label': ' Altro', 'value': 'Other'}
                ],
                value='P',
                inline=True,
                style={'marginLeft': '10px', 'marginRight': '20px'}
            ),
            html.Button('Salva Picks (QuakeML)', id='save-button', n_clicks=0,
                       style={'marginRight': '10px'}),
            html.Button('Esporta Picks (JSON)', id='export-button', n_clicks=0),
            html.Div(id='save-status', style={'display': 'inline-block', 'marginLeft': '20px'})
        ], style={'padding': '10px', 'backgroundColor': '#e0e0e0', 'marginBottom': '10px'}),
        
        # Waveform plot
        dcc.Graph(id='waveform-plot', config={'modeBarButtonsToAdd': ['drawline']}),
        
        # Pick list
        html.Div([
            html.H3("Picks registrati:"),
            html.Div(id='pick-list')
        ], style={'padding': '20px'}),
        
        # Hidden div to store picker state
        dcc.Store(id='picker-state', data={'picks': []})
    ])
    
    @app.callback(
        Output('station-selector-div', 'style'),
        Input('view-mode', 'value')
    )
    def toggle_station_selector(view_mode):
        if view_mode == 'single':
            return {'display': 'inline-block', 'marginRight': '30px'}
        return {'display': 'none'}
    
    @app.callback(
        [Output('waveform-plot', 'figure'),
         Output('picker-state', 'data'),
         Output('pick-list', 'children')],
        [Input('view-mode', 'value'),
         Input('station-selector', 'value'),
         Input('time-zoom', 'value'),
         Input('amplitude-factor', 'value'),
         Input('waveform-plot', 'clickData'),
         Input('phase-type', 'value')],
        [State('picker-state', 'data')]
    )
    def update_plot(view_mode, station_idx, time_zoom, amp_factor, 
                   click_data, phase_type, picker_state):
        picker.view_mode = view_mode
        picker.current_station_idx = station_idx if station_idx is not None else 0
        picker.time_zoom = time_zoom
        picker.amplitude_factor = amp_factor
        picker.picks = picker_state.get('picks', [])
        
        # Handle click for picking
        ctx = callback_context
        if ctx.triggered and 'clickData' in ctx.triggered[0]['prop_id'] and click_data:
            click_time = click_data['points'][0]['x']
            
            if view_mode == 'single':
                station_id = picker.stations[picker.current_station_idx]['id']
                network, station = station_id.split('.')
                
                # Determine which trace was clicked
                curve_num = click_data['points'][0]['curveNumber']
                traces = picker.get_station_traces(station_id)
                channel_order = {'Z': 0, 'N': 1, 'E': 2, '1': 1, '2': 2}
                traces_sorted = sorted(traces, 
                                      key=lambda x: channel_order.get(x.stats.channel[-1], 3))
                
                if curve_num < len(traces_sorted):
                    channel = traces_sorted[curve_num].stats.channel
                    pick_time = traces_sorted[curve_num].stats.starttime + click_time
                    picker.add_pick(pick_time, phase_type, station, channel)
        
        fig = picker.create_figure()
        
        # Create pick list
        pick_items = []
        for i, pick in enumerate(picker.picks):
            pick_text = f"{i+1}. {pick['network']}.{pick['station']}.{pick['channel']} - " \
                       f"{pick['phase']} - {UTCDateTime(pick['time']).strftime('%Y-%m-%d %H:%M:%S.%f')[:-4]}"
            pick_items.append(html.Div(pick_text, style={'padding': '5px'}))
        
        return fig, {'picks': picker.picks}, pick_items
    
    @app.callback(
        Output('save-status', 'children'),
        [Input('save-button', 'n_clicks'),
         Input('export-button', 'n_clicks')],
        [State('picker-state', 'data')]
    )
    def save_picks(save_clicks, export_clicks, picker_state):
        ctx = callback_context
        if not ctx.triggered:
            return ""
        
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        picker.picks = picker_state.get('picks', [])
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if button_id == 'save-button' and save_clicks > 0:
            filename = f'picks_{timestamp}.xml'
            picker.save_picks(filename)
            return f"✓ Salvato: {filename}"
        elif button_id == 'export-button' and export_clicks > 0:
            filename = f'picks_{timestamp}.json'
            picker.export_picks_json(filename)
            return f"✓ Esportato: {filename}"
        
        return ""
    
    return app


# Example usage
if __name__ == '__main__':
    # Example: Load seismic data
    # Replace this with your actual data file
    try:
        # Try to load example data (you'll need to provide your own file)
        stream = read()  # This reads example data from ObsPy
        
        # Or load your own data:
        # stream = read('/path/to/your/seismic/data.mseed')
        
        print(f"Loaded {len(stream)} traces")
        print(stream)
        
        # Create picker and app
        picker = SeismicPicker(stream)
        app = create_dash_app(picker)
        
        print("\n=== ISTRUZIONI D'USO ===")
        print("1. L'applicazione si aprirà nel browser")
        print("2. Usa i controlli in alto per cambiare modalità di visualizzazione")
        print("3. Clicca sulla forma d'onda per aggiungere un picking")
        print("4. Seleziona il tipo di fase (P/S) prima di cliccare")
        print("5. Usa gli slider per zoomare e modificare l'ampiezza")
        print("6. Salva i picks con i pulsanti 'Salva' o 'Esporta'")
        print("\nAvvio dell'applicazione su http://127.0.0.1:8050/")
        print("Premi Ctrl+C per terminare\n")
        
        app.run_server(debug=True, port=8050)
        
    except Exception as e:
        print(f"Errore nel caricamento dei dati: {e}")
        print("\nPer usare questo script, fornisci un file di dati sismici:")
        print("  stream = read('path/to/your/data.mseed')")
        print("\nOppure usa i dati di esempio di ObsPy modificando il codice.")
