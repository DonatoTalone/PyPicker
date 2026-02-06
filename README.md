# PyPicker

Applicazione interattiva per la visualizzazione e il picking di forme d'onda sismiche, sviluppata con ObsPy e Plotly Dash.

## Caratteristiche

### Visualizzazione
- **Modalità Stazione Singola**: visualizza le 3 componenti (Z, N, E) di una stazione simultaneamente
- **Modalità Tutte le Stazioni**: panoramica di tutte le stazioni per confronto rapido
- **Switch dinamico** tra le modalità di visualizzazione

### Controlli Interattivi
- **Zoom Temporale**: comprime/espande l'asse del tempo (0.5x - 10x)
- **Controllo Ampiezza**: scala l'ampiezza delle tracce indipendentemente dall'asse temporale (0.1x - 10x)
- **Navigazione**: selezione della stazione tramite menu a tendina

### Picking delle Fasi
- **Click interattivo** sulla forma d'onda per marcare gli arrivi
- **Selezione tipo di fase**: P, S, o Altro
- **Marker visuali**: linee verticali colorate (rosso=P, blu=S)
- **Annotazioni**: etichette delle fasi sui grafici

### Salvataggio
- **Formato QuakeML**: compatibile con ObsPy e software sismologici standard
- **Formato JSON**: per facile lettura e post-processing
- **Metadati completi**: rete, stazione, canale, tempo di arrivo, fase

## Installazione

### Requisiti
```bash
pip install obspy dash plotly numpy
```

### Versioni testate
- Python >= 3.8
- ObsPy >= 1.4.0
- Dash >= 2.14.0
- Plotly >= 5.17.0

## Utilizzo

### Con i tuoi dati
```python
from obspy import read
from seismic_picker import SeismicPicker, create_dash_app

# Carica i dati sismici (formati supportati: miniSEED, SAC, etc.)
stream = read('path/to/your/seismic/data.mseed')

# Crea il picker e l'applicazione
picker = SeismicPicker(stream)
app = create_dash_app(picker)

# Avvia il server
app.run_server(debug=True, port=8050)
```

### Con dati sintetici di test
```bash
python test_seismic_picker.py
```

Questo script crea automaticamente dati sismici sintetici con arrivi P e S realistici.

## Interfaccia Utente

### Pannello di Controllo Superiore
1. **Modalità visualizzazione**: Radio button per switchare tra single/all
2. **Selettore stazione**: Dropdown (visibile solo in modalità singola)
3. **Zoom Temporale**: Slider per controllare la compressione temporale
4. **Ampiezza**: Slider per scalare le ampiezze

### Pannello Picking
1. **Tipo di fase**: Seleziona P, S, o Altro prima di cliccare
2. **Pulsante Salva**: Esporta in formato QuakeML (.xml)
3. **Pulsante Esporta**: Esporta in formato JSON (.json)

### Area Grafica
- **Click sulla traccia**: Aggiunge un picking al tempo cliccato
- **Hover**: Mostra tempo e ampiezza precisi
- **Marker**: Linee verticali indicano i picking esistenti

### Lista Picks
Mostra tutti i picking registrati con:
- Numero progressivo
- Rete.Stazione.Canale
- Tipo di fase
- Tempo di arrivo (UTC)

## Struttura dei File di Output

### QuakeML (.xml)
Formato standard ObsPy compatibile con:
- SeisComP
- SEISAN
- Antelope
- Altri software sismologici

```xml
<?xml version='1.0' encoding='utf-8'?>
<q:quakeml>
  <eventParameters>
    <event>
      <pick>
        <time><value>2024-01-15T10:30:08.000000Z</value></time>
        <phaseHint>P</phaseHint>
        <waveformID networkCode="SY" stationCode="STA1" channelCode="HHZ"/>
      </pick>
    </event>
  </eventParameters>
</q:quakeml>
```

### JSON (.json)
```json
[
  {
    "time": "2024-01-15T10:30:08.000000Z",
    "phase": "P",
    "network": "SY",
    "station": "STA1",
    "channel": "HHZ",
    "timestamp": "2024-02-04T15:30:45.123456"
  }
]
```

## Funzionalità Avanzate

### Classe SeismicPicker

```python
# Inizializzazione
picker = SeismicPicker(stream)

# Proprietà
picker.stations          # Lista di stazioni
picker.picks             # Lista di picks
picker.view_mode         # 'single' o 'all'
picker.time_zoom         # Fattore di zoom temporale
picker.amplitude_factor  # Fattore di scala ampiezza

# Metodi
picker.get_station_traces(station_id)  # Ottiene tracce di una stazione
picker.create_figure()                 # Genera il grafico Plotly
picker.add_pick(time, phase, ...)      # Aggiunge un pick
picker.save_picks(filename)            # Salva in QuakeML
picker.export_picks_json(filename)     # Esporta in JSON
```

### Pre-processamento dei Dati

Prima di caricare nel picker, puoi pre-processare con ObsPy:

```python
from obspy import read

# Carica dati
stream = read('data.mseed')

# Rimuovi trend e media
stream.detrend('linear')
stream.detrend('demean')

# Filtra
stream.filter('bandpass', freqmin=1.0, freqmax=10.0)

# Resample (opzionale)
stream.resample(100.0)

# Taglia a finestra temporale
stream.trim(starttime=start, endtime=end)

# Carica nel picker
picker = SeismicPicker(stream)
```

## Workflow Consigliato

1. **Carica i dati** in ObsPy Stream
2. **Pre-processa** (filtro, decimazione, etc.)
3. **Avvia il picker** con i dati preparati
4. **Visualizza in modalità "Tutte le Stazioni"** per overview
5. **Switcha a "Stazione Singola"** per picking dettagliato
6. **Seleziona la fase** (P o S)
7. **Clicca sugli arrivi** per marcarli
8. **Regola zoom e ampiezza** per migliore visibilità
9. **Ripeti per tutte le stazioni**
10. **Salva i picks** in formato QuakeML

## Limitazioni e Note

- Il picking si basa su click: la precisione dipende dalla risoluzione dello schermo e dal livello di zoom
- I picks sono salvati con la precisione del campionamento dei dati originali
- In modalità "Tutte le Stazioni" viene visualizzata solo la prima componente di ogni stazione
- I file QuakeML contengono un evento dummy con origine fittizia (necessario per la struttura del formato)

## Estensioni Possibili

### Aggiungi filtri in tempo reale
```python
# Nel callback, aggiungi:
stream_filtered = stream.copy()
stream_filtered.filter('bandpass', freqmin=1, freqmax=10)
picker = SeismicPicker(stream_filtered)
```

### Aggiungi rimozione picks
```python
# Aggiungi pulsante e callback per rimuovere l'ultimo pick
picker.picks.pop()
```

### Integra con localizzazione
```python
from obspy.taup import TauPyModel

# Dopo aver raccolto i picks, calcola la localizzazione
# usando tempi di arrivo e modello di velocità
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'dash'"
```bash
pip install dash plotly
```

### "No module named 'obspy'"
```bash
pip install obspy
```

### Il grafico non si aggiorna
- Controlla la console del browser per errori JavaScript
- Verifica che tutti i callback siano configurati correttamente
- Riavvia l'applicazione

### I picks non vengono salvati
- Verifica i permessi di scrittura nella directory corrente
- Controlla che ci siano picks nella lista prima di salvare
- Guarda i messaggi nella console

## Licenza

Questo codice è fornito come esempio educativo. Modificalo liberamente per le tue esigenze.

## Autore

Sviluppato come strumento interattivo per analisi sismica con ObsPy e Plotly Dash.

## Contributi

Suggerimenti per miglioramenti:
- Aggiungere undo/redo per i picks
- Implementare tastiera shortcuts (P, S per selezionare fase)
- Aggiungere filtri interattivi
- Integrazione con database sismologici
- Export in altri formati (Nordic, CSS, etc.)
- Visualizzazione spettrogrammi
