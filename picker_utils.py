#!/usr/bin/env python3
"""
Utility functions for the Seismic Picker
Additional features and helpers
"""
import numpy as np
from obspy import UTCDateTime, read_events
import json


def apply_preprocessing(stream, params):
    """Applica filtri e correzioni a una copia dello stream"""
    st = stream.copy()

    if params.get("detrend"):
        st.detrend("linear")

    if params.get("taper", 0) > 0:
        st.taper(max_percentage=params["taper"], type="cosine")

    f_type = params.get("filter_type")
    low = params.get("low_f", 1.0)
    high = params.get("high_f", 20.0)

    try:
        if f_type == "bandpass" and low < high:
            st.filter("bandpass", freqmin=low, freqmax=high)
        elif f_type == "highpass":
            st.filter("highpass", freqmin=low)
        elif f_type == "lowpass":
            st.filter("lowpass", freqmax=high)
    except Exception as e:
        print(f"Errore filtro: {e}")

    return st


def get_spectrum(trace):
    """Calcola lo spettro di frequenza di una traccia"""
    data = trace.data - np.mean(trace.data)
    n = len(data)
    delta = trace.stats.delta

    # Calcolo FFT
    freq = np.fft.rfftfreq(n, d=delta)
    spec = np.abs(np.fft.rfft(data))

    return freq, spec

def load_picks_from_quakeml(filename):
    """
    Load picks from a QuakeML file
    
    Parameters:
    -----------
    filename : str
        Path to QuakeML file
    
    Returns:
    --------
    picks : list
        List of pick dictionaries
    """
    catalog = read_events(filename)
    picks = []
    
    for event in catalog:
        for pick in event.picks:
            pick_dict = {
                'time': pick.time,
                'phase': pick.phase_hint if pick.phase_hint else 'Unknown',
                'network': pick.waveform_id.network_code,
                'station': pick.waveform_id.station_code,
                'channel': pick.waveform_id.channel_code,
            }
            picks.append(pick_dict)
    
    return picks


def load_picks_from_json(filename):
    """
    Load picks from a JSON file
    
    Parameters:
    -----------
    filename : str
        Path to JSON file
    
    Returns:
    --------
    picks : list
        List of pick dictionaries
    """
    with open(filename, 'r') as f:
        picks = json.load(f)
    
    # Convert time strings back to UTCDateTime
    for pick in picks:
        if isinstance(pick['time'], str):
            pick['time'] = UTCDateTime(pick['time'])
    
    return picks


def merge_picks(picks_list):
    """
    Merge multiple pick lists, removing duplicates
    
    Parameters:
    -----------
    picks_list : list of lists
        List containing multiple pick lists
    
    Returns:
    --------
    merged_picks : list
        Merged and deduplicated picks
    """
    merged = []
    seen = set()
    
    for picks in picks_list:
        for pick in picks:
            # Create unique identifier
            key = (
                pick['station'],
                pick['channel'],
                pick['phase'],
                round(float(pick['time']), 2)  # Round to 0.01s
            )
            
            if key not in seen:
                merged.append(pick)
                seen.add(key)
    
    # Sort by time
    merged.sort(key=lambda x: x['time'])
    
    return merged


def calculate_pick_statistics(picks, stream):
    """
    Calculate statistics about picks
    
    Parameters:
    -----------
    picks : list
        List of pick dictionaries
    stream : obspy.Stream
        Stream object
    
    Returns:
    --------
    stats : dict
        Dictionary with statistics
    """
    stats = {
        'total_picks': len(picks),
        'p_picks': sum(1 for p in picks if p['phase'] == 'P'),
        's_picks': sum(1 for p in picks if p['phase'] == 'S'),
        'stations_with_picks': len(set(p['station'] for p in picks)),
        'total_stations': len(set(tr.stats.station for tr in stream)),
    }
    
    # Calculate P-S times if both exist
    ps_times = []
    stations = set(p['station'] for p in picks)
    
    for station in stations:
        station_picks = [p for p in picks if p['station'] == station]
        p_picks = [p for p in station_picks if p['phase'] == 'P']
        s_picks = [p for p in station_picks if p['phase'] == 'S']
        
        if p_picks and s_picks:
            p_time = min(p['time'] for p in p_picks)
            s_time = min(s['time'] for s in s_picks)
            ps_times.append(float(s_time - p_time))
    
    if ps_times:
        stats['mean_ps_time'] = np.mean(ps_times)
        stats['std_ps_time'] = np.std(ps_times)
        stats['min_ps_time'] = np.min(ps_times)
        stats['max_ps_time'] = np.max(ps_times)
    
    return stats


def print_pick_summary(picks, stream):
    """
    Print a nice summary of picks
    
    Parameters:
    -----------
    picks : list
        List of pick dictionaries
    stream : obspy.Stream
        Stream object
    """
    stats = calculate_pick_statistics(picks, stream)
    
    print("\n" + "="*60)
    print("RIEPILOGO PICKS")
    print("="*60)
    print(f"Totale picks: {stats['total_picks']}")
    print(f"  - Fase P: {stats['p_picks']}")
    print(f"  - Fase S: {stats['s_picks']}")
    print(f"Stazioni con picks: {stats['stations_with_picks']}/{stats['total_stations']}")
    
    if 'mean_ps_time' in stats:
        print(f"\nTempi P-S:")
        print(f"  - Media: {stats['mean_ps_time']:.2f} s")
        print(f"  - Dev. Std.: {stats['std_ps_time']:.2f} s")
        print(f"  - Min-Max: {stats['min_ps_time']:.2f} - {stats['max_ps_time']:.2f} s")
    
    print("\nDettaglio per stazione:")
    stations = sorted(set(p['station'] for p in picks))
    for station in stations:
        station_picks = [p for p in picks if p['station'] == station]
        p_count = sum(1 for p in station_picks if p['phase'] == 'P')
        s_count = sum(1 for p in station_picks if p['phase'] == 'S')
        print(f"  {station}: {len(station_picks)} picks (P:{p_count}, S:{s_count})")
    
    print("="*60 + "\n")


def export_picks_to_csv(picks, filename):
    """
    Export picks to CSV format
    
    Parameters:
    -----------
    picks : list
        List of pick dictionaries
    filename : str
        Output filename
    """
    import csv
    
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Network', 'Station', 'Channel', 'Phase', 'Time'])
        
        for pick in picks:
            writer.writerow([
                pick['network'],
                pick['station'],
                pick['channel'],
                pick['phase'],
                UTCDateTime(pick['time']).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]
            ])
    
    print(f"Picks esportati in {filename}")


def validate_picks(picks, stream, max_picks_per_channel=10, 
                   min_ps_time=0.1, max_ps_time=100):
    """
    Validate picks and return warnings
    
    Parameters:
    -----------
    picks : list
        List of pick dictionaries
    stream : obspy.Stream
        Stream object
    max_picks_per_channel : int
        Maximum expected picks per channel
    min_ps_time : float
        Minimum expected P-S time (seconds)
    max_ps_time : float
        Maximum expected P-S time (seconds)
    
    Returns:
    --------
    warnings : list
        List of warning messages
    """
    warnings = []
    
    # Check for too many picks on same channel
    for tr in stream:
        channel_picks = [p for p in picks 
                        if p['station'] == tr.stats.station 
                        and p['channel'] == tr.stats.channel]
        
        if len(channel_picks) > max_picks_per_channel:
            warnings.append(
                f"Attenzione: {len(channel_picks)} picks su {tr.stats.station}.{tr.stats.channel} "
                f"(massimo atteso: {max_picks_per_channel})"
            )
    
    # Check P-S times
    stations = set(p['station'] for p in picks)
    for station in stations:
        station_picks = [p for p in picks if p['station'] == station]
        p_picks = [p for p in station_picks if p['phase'] == 'P']
        s_picks = [p for p in station_picks if p['phase'] == 'S']
        
        if p_picks and s_picks:
            p_time = min(p['time'] for p in p_picks)
            s_time = min(s['time'] for s in s_picks)
            ps_time = float(s_time - p_time)
            
            if ps_time < min_ps_time:
                warnings.append(
                    f"Attenzione: P-S time molto breve per {station}: {ps_time:.2f} s"
                )
            elif ps_time > max_ps_time:
                warnings.append(
                    f"Attenzione: P-S time molto lungo per {station}: {ps_time:.2f} s"
                )
            elif ps_time < 0:
                warnings.append(
                    f"Errore: S arriva prima di P per {station}! P-S = {ps_time:.2f} s"
                )
    
    # Check for picks outside trace time range
    for pick in picks:
        matching_traces = stream.select(
            station=pick['station'],
            channel=pick['channel']
        )
        
        if matching_traces:
            tr = matching_traces[0]
            pick_time = UTCDateTime(pick['time'])
            
            if pick_time < tr.stats.starttime or pick_time > tr.stats.endtime:
                warnings.append(
                    f"Attenzione: Pick per {pick['station']}.{pick['channel']} "
                    f"fuori dal range della traccia"
                )
    
    return warnings


def compare_picks(picks1, picks2, time_tolerance=0.5):
    """
    Compare two sets of picks
    
    Parameters:
    -----------
    picks1 : list
        First pick list
    picks2 : list
        Second pick list
    time_tolerance : float
        Time tolerance in seconds for matching picks
    
    Returns:
    --------
    comparison : dict
        Dictionary with comparison results
    """
    matches = []
    only_in_1 = []
    only_in_2 = []
    
    for p1 in picks1:
        found = False
        for p2 in picks2:
            if (p1['station'] == p2['station'] and 
                p1['channel'] == p2['channel'] and
                p1['phase'] == p2['phase']):
                
                time_diff = abs(float(UTCDateTime(p1['time']) - UTCDateTime(p2['time'])))
                
                if time_diff <= time_tolerance:
                    matches.append({
                        'pick1': p1,
                        'pick2': p2,
                        'time_diff': time_diff
                    })
                    found = True
                    break
        
        if not found:
            only_in_1.append(p1)
    
    for p2 in picks2:
        found = False
        for match in matches:
            if match['pick2'] == p2:
                found = True
                break
        if not found:
            only_in_2.append(p2)
    
    time_diffs = [m['time_diff'] for m in matches]
    
    comparison = {
        'total_picks_1': len(picks1),
        'total_picks_2': len(picks2),
        'matches': len(matches),
        'only_in_1': len(only_in_1),
        'only_in_2': len(only_in_2),
        'mean_time_diff': np.mean(time_diffs) if time_diffs else None,
        'std_time_diff': np.std(time_diffs) if time_diffs else None,
        'max_time_diff': np.max(time_diffs) if time_diffs else None,
    }
    
    return comparison


if __name__ == '__main__':
    print("Utilities per Seismic Picker")
    print("\nQuesto modulo contiene funzioni di utilità:")
    print("  - load_picks_from_quakeml()")
    print("  - load_picks_from_json()")
    print("  - merge_picks()")
    print("  - calculate_pick_statistics()")
    print("  - print_pick_summary()")
    print("  - export_picks_to_csv()")
    print("  - validate_picks()")
    print("  - compare_picks()")
    print("\nImporta queste funzioni nel tuo script:")
    print("  from picker_utils import *")
