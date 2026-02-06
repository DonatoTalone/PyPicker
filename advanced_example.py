#!/usr/bin/env python3
"""
Advanced example: Load real seismic data with preprocessing
This script shows how to load, filter, and prepare data for the picker
"""

from obspy import read, UTCDateTime
from obspy.clients.fdsn import Client
from seismic_picker import SeismicPicker, create_dash_app
import sys

def load_and_preprocess_local_data(filepath, starttime=None, endtime=None,
                                   apply_filter=True, freqmin=1.0, freqmax=10.0):
    """
    Load and preprocess seismic data from a local file
    
    Parameters:
    -----------
    filepath : str
        Path to seismic data file (miniSEED, SAC, etc.)
    starttime : UTCDateTime or None
        Start time for trimming
    endtime : UTCDateTime or None
        End time for trimming
    apply_filter : bool
        Whether to apply bandpass filter
    freqmin : float
        Low corner frequency for bandpass filter
    freqmax : float
        High corner frequency for bandpass filter
    
    Returns:
    --------
    stream : obspy.Stream
        Preprocessed stream
    """
    print(f"Caricamento dati da {filepath}...")
    stream = read(filepath)
    
    print(f"Tracce caricate: {len(stream)}")
    print(stream)
    
    # Remove instrument response (if available)
    # Uncomment if you have response information
    # try:
    #     stream.remove_response(output='VEL')
    #     print("Risposta strumentale rimossa")
    # except:
    #     print("Attenzione: impossibile rimuovere risposta strumentale")
    
    # Detrend
    print("Rimozione trend...")
    stream.detrend('linear')
    stream.detrend('demean')
    
    # Taper
    print("Applicazione taper...")
    stream.taper(max_percentage=0.05, type='hann')
    
    # Filter
    if apply_filter:
        print(f"Applicazione filtro bandpass {freqmin}-{freqmax} Hz...")
        stream.filter('bandpass', freqmin=freqmin, freqmax=freqmax, corners=4, zerophase=True)
    
    # Trim
    if starttime and endtime:
        print(f"Taglio da {starttime} a {endtime}...")
        stream.trim(starttime=starttime, endtime=endtime)
    
    # Resample to common rate if needed
    sample_rates = [tr.stats.sampling_rate for tr in stream]
    if len(set(sample_rates)) > 1:
        target_rate = min(sample_rates)
        print(f"Resampling a {target_rate} Hz...")
        stream.resample(target_rate)
    
    print("\nDati preprocessati:")
    print(stream)
    
    return stream


def download_data_from_server(network, station, location, channel,
                              starttime, endtime, server='IRIS'):
    """
    Download seismic data from FDSN server
    
    Parameters:
    -----------
    network : str
        Network code (e.g., 'IU')
    station : str
        Station code (e.g., 'ANMO')
    location : str
        Location code (e.g., '00')
    channel : str
        Channel code with wildcards (e.g., 'BH?')
    starttime : UTCDateTime
        Start time
    endtime : UTCDateTime
        End time
    server : str
        FDSN server name (e.g., 'IRIS', 'INGV', 'GEOFON')
    
    Returns:
    --------
    stream : obspy.Stream
        Downloaded stream
    """
    print(f"Connessione a {server}...")
    client = Client(server)
    
    print(f"Download dati per {network}.{station}.{location}.{channel}")
    print(f"Periodo: {starttime} - {endtime}")
    
    stream = client.get_waveforms(
        network=network,
        station=station,
        location=location,
        channel=channel,
        starttime=starttime,
        endtime=endtime
    )
    
    print(f"\nDati scaricati: {len(stream)} tracce")
    print(stream)
    
    return stream


def example_local_file():
    """Example using a local file"""
    print("="*60)
    print("ESEMPIO 1: Caricamento da file locale")
    print("="*60 + "\n")
    
    # Specify your file path
    filepath = '/path/to/your/seismic/data.mseed'
    
    # Optional: specify time window
    # starttime = UTCDateTime('2024-01-15T10:00:00')
    # endtime = UTCDateTime('2024-01-15T10:10:00')
    
    try:
        stream = load_and_preprocess_local_data(
            filepath,
            # starttime=starttime,
            # endtime=endtime,
            apply_filter=True,
            freqmin=1.0,
            freqmax=10.0
        )
        
        # Create picker and run
        picker = SeismicPicker(stream)
        app = create_dash_app(picker)
        
        print("\n" + "="*60)
        print("Avvio applicazione su http://127.0.0.1:8050/")
        print("Premi Ctrl+C per terminare")
        print("="*60 + "\n")
        
        app.run_server(debug=True, port=8050)
        
    except FileNotFoundError:
        print(f"\nErrore: File {filepath} non trovato")
        print("Modifica la variabile 'filepath' con il percorso del tuo file")
        print("Formati supportati: miniSEED, SAC, GSE2, SEISAN, Q, etc.")
        return False
    
    return True


def example_download_from_fdsn():
    """Example downloading data from FDSN server"""
    print("="*60)
    print("ESEMPIO 2: Download da server FDSN")
    print("="*60 + "\n")
    
    # Example: Download data from IRIS for a recent earthquake
    # Modify these parameters for your needs
    
    network = 'IU'          # Network code
    station = 'ANMO'        # Station code (Albuquerque, New Mexico)
    location = '00'         # Location code
    channel = 'BH?'         # Channel code (? = wildcard for Z,N,E)
    
    # Time window (example: 1 hour of data)
    starttime = UTCDateTime('2024-01-01T00:00:00')
    endtime = starttime + 3600  # +1 hour
    
    try:
        stream = download_data_from_server(
            network, station, location, channel,
            starttime, endtime,
            server='IRIS'
        )
        
        # Preprocess
        print("\nPreprocessamento...")
        stream.detrend('linear')
        stream.detrend('demean')
        stream.filter('bandpass', freqmin=0.5, freqmax=10.0)
        
        # Create picker and run
        picker = SeismicPicker(stream)
        app = create_dash_app(picker)
        
        print("\n" + "="*60)
        print("Avvio applicazione su http://127.0.0.1:8050/")
        print("Premi Ctrl+C per terminare")
        print("="*60 + "\n")
        
        app.run_server(debug=True, port=8050)
        
    except Exception as e:
        print(f"\nErrore durante il download: {e}")
        print("\nSuggerimenti:")
        print("- Verifica la connessione internet")
        print("- Controlla che network/station/channel siano corretti")
        print("- Prova un periodo temporale diverso")
        print("- Usa un server diverso (GEOFON, INGV, etc.)")
        return False
    
    return True


def example_multi_station_event():
    """Example downloading multiple stations for an event"""
    print("="*60)
    print("ESEMPIO 3: Multi-stazione per un evento")
    print("="*60 + "\n")
    
    # Example event parameters
    event_time = UTCDateTime('2024-01-01T12:00:00')
    duration = 600  # 10 minutes
    
    # List of stations to download
    stations_list = [
        ('IU', 'ANMO', '00', 'BH?'),  # Albuquerque
        ('IU', 'CCM', '00', 'BH?'),   # Cathedral Cave
        ('IU', 'HRV', '00', 'BH?'),   # Harvard
    ]
    
    try:
        client = Client('IRIS')
        stream = None
        
        for network, station, location, channel in stations_list:
            print(f"Download {network}.{station}...")
            try:
                st = client.get_waveforms(
                    network, station, location, channel,
                    event_time, event_time + duration
                )
                if stream is None:
                    stream = st
                else:
                    stream += st
            except Exception as e:
                print(f"  Attenzione: {e}")
        
        if stream is None or len(stream) == 0:
            print("Nessun dato scaricato!")
            return False
        
        print(f"\nTotale tracce scaricate: {len(stream)}")
        print(stream)
        
        # Preprocess
        print("\nPreprocessamento...")
        stream.detrend('linear')
        stream.detrend('demean')
        stream.filter('bandpass', freqmin=0.5, freqmax=5.0)
        
        # Create picker and run
        picker = SeismicPicker(stream)
        app = create_dash_app(picker)
        
        print("\n" + "="*60)
        print("Avvio applicazione su http://127.0.0.1:8050/")
        print("Premi Ctrl+C per terminare")
        print("="*60 + "\n")
        
        app.run_server(debug=True, port=8050)
        
    except Exception as e:
        print(f"\nErrore: {e}")
        return False
    
    return True


if __name__ == '__main__':
    print("\n" + "="*60)
    print("SEISMIC PICKER - Esempi Avanzati")
    print("="*60 + "\n")
    
    print("Scegli un esempio:")
    print("1. Carica da file locale (devi fornire il percorso)")
    print("2. Download da server FDSN (IRIS)")
    print("3. Download multi-stazione per un evento")
    print("4. Usa dati sintetici (test)")
    print()
    
    choice = input("Scelta (1-4): ").strip()
    
    if choice == '1':
        success = example_local_file()
    elif choice == '2':
        success = example_download_from_fdsn()
    elif choice == '3':
        success = example_multi_station_event()
    elif choice == '4':
        # Use synthetic data
        print("\nCaricamento script con dati sintetici...")
        import test_seismic_picker
        sys.exit(0)
    else:
        print("Scelta non valida")
        sys.exit(1)
    
    if not success:
        print("\nEsempio non completato. Controlla i parametri e riprova.")
        sys.exit(1)
