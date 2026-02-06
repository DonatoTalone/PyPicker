#!/usr/bin/env python3
"""
Test script aggiornato con funzionalità di preprocessing e visualizzazione spettrale
"""

import numpy as np
from obspy import Stream, Trace, UTCDateTime
from seismic_picker import SeismicPicker, create_dash_app

def create_synthetic_seismogram_v2(station, channel, starttime, duration=60, 
                                   sampling_rate=100, p_arrival=10, s_arrival=20,
                                   add_noise_trend=True):
    """
    Create a synthetic seismogram with P and S wave arrivals
    Now includes trend and mean offset to test preprocessing
    
    Parameters:
    -----------
    station : str
        Station code
    channel : str
        Channel code (e.g., 'HHZ', 'HHN', 'HHE')
    starttime : UTCDateTime
        Start time of the trace
    duration : float
        Duration in seconds
    sampling_rate : float
        Sampling rate in Hz
    p_arrival : float
        P wave arrival time in seconds from start
    s_arrival : float
        S wave arrival time in seconds from start
    add_noise_trend : bool
        Add noise, mean offset, and trend (for testing preprocessing)
    """
    npts = int(duration * sampling_rate)
    
    # Create noise
    noise = np.random.normal(0, 0.5, npts)
    
    # Create P wave (higher frequency, smaller amplitude)
    p_signal = np.zeros(npts)
    p_idx = int(p_arrival * sampling_rate)
    p_duration = int(3 * sampling_rate)  # 3 seconds
    if p_idx < npts:
        p_end = min(p_idx + p_duration, npts)
        p_times = np.arange(p_end - p_idx) / sampling_rate
        # P wave: higher frequency (8 Hz) with harmonics
        p_signal[p_idx:p_end] = (
            5 * np.sin(2 * np.pi * 8 * p_times) * np.exp(-p_times / 0.5) +
            2 * np.sin(2 * np.pi * 16 * p_times) * np.exp(-p_times / 0.3)
        )
    
    # Create S wave (lower frequency, larger amplitude)
    s_signal = np.zeros(npts)
    s_idx = int(s_arrival * sampling_rate)
    s_duration = int(5 * sampling_rate)  # 5 seconds
    if s_idx < npts:
        s_end = min(s_idx + s_duration, npts)
        s_times = np.arange(s_end - s_idx) / sampling_rate
        # S wave: lower frequency (3-4 Hz) with harmonics
        amplitude = 10 if 'Z' in channel else 12  # Stronger on horizontal components
        s_signal[s_idx:s_end] = (
            amplitude * np.sin(2 * np.pi * 3 * s_times) * np.exp(-s_times / 1.2) +
            4 * np.sin(2 * np.pi * 6 * s_times) * np.exp(-s_times / 0.8)
        )
    
    # Add some surface waves (low frequency)
    surface_wave = 0
    if s_idx < npts:
        surface_start = s_idx + int(2 * sampling_rate)
        surface_duration = npts - surface_start
        if surface_duration > 0:
            surface_times = np.arange(surface_duration) / sampling_rate
            surface_wave = np.zeros(npts)
            surface_wave[surface_start:] = (
                3 * np.sin(2 * np.pi * 1.5 * surface_times) * np.exp(-surface_times / 3.0)
            )
    
    # Combine all components
    data = noise + p_signal + s_signal + surface_wave
    
    # Add trend and mean offset if requested (to test preprocessing)
    if add_noise_trend:
        # Add linear trend
        trend = np.linspace(-2, 3, npts)
        # Add mean offset
        mean_offset = 5.0
        data = data + trend + mean_offset
    
    # Add some variability based on component
    if 'N' in channel or '1' in channel:
        data *= 0.8
        data += np.random.normal(0, 0.2, npts)
    elif 'E' in channel or '2' in channel:
        data *= 0.7
        data += np.random.normal(0, 0.3, npts)
    
    # Create trace
    trace = Trace(data=data)
    trace.stats.network = 'SY'  # Synthetic network
    trace.stats.station = station
    trace.stats.channel = channel
    trace.stats.starttime = starttime
    trace.stats.sampling_rate = sampling_rate
    
    return trace

def create_test_stream_v2(n_stations=3, add_preprocessing_issues=True):
    """
    Create a test stream with multiple stations and components
    Now includes issues that can be fixed with preprocessing
    
    Parameters:
    -----------
    n_stations : int
        Number of stations to create
    add_preprocessing_issues : bool
        Add mean offset and trends to test preprocessing
    """
    stream = Stream()
    starttime = UTCDateTime('2024-01-15T10:30:00')
    
    # Different P and S arrival times for each station (simulating distance)
    arrivals = [
        (8, 15),   # Station 1: close
        (12, 22),  # Station 2: medium distance
        (16, 30),  # Station 3: far
    ]
    
    station_names = ['STA1', 'STA2', 'STA3', 'STA4', 'STA5']
    
    for i in range(min(n_stations, len(station_names))):
        station = station_names[i]
        p_time, s_time = arrivals[min(i, len(arrivals)-1)]
        
        # Create 3-component data (Z, N, E)
        for channel in ['HHZ', 'HHN', 'HHE']:
            trace = create_synthetic_seismogram_v2(
                station=station,
                channel=channel,
                starttime=starttime,
                duration=60,
                sampling_rate=100,
                p_arrival=p_time,
                s_arrival=s_time,
                add_noise_trend=add_preprocessing_issues
            )
            stream.append(trace)
    
    return stream

if __name__ == '__main__':
    print("="*70)
    print("SEISMIC PICKER v2 - Con Preprocessing e Visualizzazione Spettrale")
    print("="*70 + "\n")
    
    print("Creazione dati sismici sintetici con caratteristiche realistiche...")
    print("  - Onde P (alta frequenza ~8 Hz)")
    print("  - Onde S (frequenza media ~3-4 Hz)")
    print("  - Onde di superficie (bassa frequenza ~1.5 Hz)")
    print("  - Trend lineare e offset medio (da rimuovere con preprocessing)")
    print("  - Rumore casuale\n")
    
    # Create synthetic stream with 3 stations
    stream = create_test_stream_v2(n_stations=3, add_preprocessing_issues=True)
    
    print(f"Stream creato con {len(stream)} tracce:")
    print(stream)
    print("\n" + "="*70)
    
    # Create picker and app
    picker = SeismicPicker(stream)
    app = create_dash_app(picker)
    
    print("\n" + "="*70)
    print("ISTRUZIONI D'USO")
    print("="*70)
    print("\n1. VISUALIZZAZIONE:")
    print("   - 'Stazione Singola': mostra 3 componenti (Z, N, E)")
    print("   - 'Tutte le Stazioni': panoramica generale")
    print("   - 'Mostra Spettro': visualizza lo spettro di frequenza (solo stazione singola)")
    
    print("\n2. PREPROCESSING (pannello blu):")
    print("   ✓ Rimuovi Media: elimina l'offset medio del segnale")
    print("   ✓ Rimuovi Trend: elimina il trend lineare")
    print("   ✓ Filtri:")
    print("     - Passa-Basso: rimuove frequenze alte (utile per rumore)")
    print("     - Passa-Alto: rimuove frequenze basse (utile per trend)")
    print("     - Passa-Banda: mantiene solo un intervallo di frequenze")
    print("   ⚠ Clicca 'Applica' dopo aver modificato i parametri")
    
    print("\n3. VISUALIZZAZIONE SPETTRO:")
    print("   - Mostra l'ampiezza vs frequenza per ogni componente")
    print("   - Utile per identificare contenuto in frequenza del segnale")
    print("   - Frequenza di Nyquist indicata con linea rossa tratteggiata")
    print("   - Verifica l'effetto dei filtri sullo spettro")
    
    print("\n4. SUGGERIMENTI PER IL TEST:")
    print("   a) Prima guarda i dati RAW (senza preprocessing)")
    print("      → Noterai trend e offset medio")
    print("   b) Attiva 'Rimuovi Media' e 'Rimuovi Trend', poi 'Applica'")
    print("      → Il segnale sarà centrato sullo zero")
    print("   c) Guarda lo spettro")
    print("      → Vedrai picchi a ~1.5, 3-4, 8 Hz (onde superficiali, S, P)")
    print("   d) Applica filtro Passa-Banda 2-15 Hz")
    print("      → Rimuove rumore a bassa frequenza")
    print("   e) Prova filtro Passa-Basso 5 Hz")
    print("      → Vedrai principalmente onde S e superficiali")
    print("   f) Prova filtro Passa-Alto 5 Hz")
    print("      → Vedrai principalmente onde P")
    
    print("\n5. PICKING:")
    print("   - Seleziona fase (P/S)")
    print("   - Clicca sulla forma d'onda nel punto di arrivo")
    print("   - I picks funzionano solo in vista forma d'onda (non spettro)")
    
    print("\n6. CONTROLLI:")
    print("   - Zoom Temporale: comprime/espande asse tempo")
    print("   - Ampiezza: scala verticalmente le tracce")
    
    print("\n7. SALVATAGGIO:")
    print("   - QuakeML: formato standard ObsPy")
    print("   - JSON: formato leggibile")
    
    print("\n" + "="*70)
    print("DATI SINTETICI:")
    print("  - 3 stazioni (STA1, STA2, STA3)")
    print("  - Arrivi P: ~8, 12, 16 secondi")
    print("  - Arrivi S: ~15, 22, 30 secondi")
    print("  - Campionamento: 100 Hz")
    print("  - Con trend e offset per testare preprocessing")
    print("="*70)
    
    print("\nAvvio applicazione su http://127.0.0.1:8050/")
    print("Premi Ctrl+C per terminare\n")
    
    # Run the app
    app.run(debug=True, port=8050)
