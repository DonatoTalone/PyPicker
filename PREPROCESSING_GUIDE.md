# Guida al Preprocessing e Analisi Spettrale

## Indice
- [Introduzione](#introduzione)
- [Rimozione Media e Trend](#rimozione-media-e-trend)
- [Filtri Digitali](#filtri-digitali)
- [Analisi Spettrale](#analisi-spettrale)
- [Esempi Pratici](#esempi-pratici)

## Introduzione

Il preprocessing è essenziale per preparare i dati sismici all'analisi e al picking. Questa guida spiega come utilizzare le funzionalità di preprocessing del Seismic Picker.

## Rimozione Media e Trend

### Rimozione Media (Demean)

**Cosa fa**: Rimuove l'offset DC (valore medio) dal segnale, centrando i dati sullo zero.

**Quando usarla**:
- I dati hanno un offset costante diverso da zero
- Prima di applicare filtri
- Prima di calcolare FFT o altri analisi

**Come usarla**:
1. Spunta "Rimuovi Media" nel pannello Preprocessing
2. Clicca "Applica"

**Esempio pratico**:
```
Prima:  Segnale oscilla tra 95 e 105
Dopo:   Segnale oscilla tra -5 e +5
```

### Rimozione Trend (Detrend)

**Cosa fa**: Rimuove il trend lineare dal segnale (deriva graduale nel tempo).

**Quando usarla**:
- I dati mostrano una deriva lineare nel tempo
- Presenza di componente a frequenza molto bassa
- Prima di filtri passa-banda

**Come usarla**:
1. Spunta "Rimuovi Trend" nel pannello Preprocessing
2. Clicca "Applica"

**Esempio pratico**:
```
Prima:  Baseline sale da 0 a 10 durante la registrazione
Dopo:   Baseline rimane intorno a 0
```

### Best Practice

È comune applicare entrambe le operazioni in sequenza:
1. Prima rimuovi il trend (componente lenta)
2. Poi rimuovi la media (offset residuo)

Nel Seismic Picker puoi attivarle entrambe e cliccare "Applica" una volta sola.

## Filtri Digitali

### Tipi di Filtri

#### 1. Passa-Basso (Lowpass)

**Cosa fa**: Rimuove frequenze superiori a una soglia, mantenendo solo le basse frequenze.

**Quando usarlo**:
- Ridurre rumore ad alta frequenza
- Estrarre onde di superficie o segnali lenti
- Rimuovere aliasing

**Parametri**:
- **Frequenza di taglio**: frequenza sopra la quale il segnale viene attenuato (es. 5 Hz)

**Esempio**:
```
Filtro passa-basso a 5 Hz
→ Mantiene: 0-5 Hz (onde superficiali, trend)
→ Rimuove: >5 Hz (onde P/S ad alta frequenza, rumore)
```

**Applicazioni tipiche**:
- Studio onde di superficie: 0.5-2 Hz
- Rimozione rumore strumentale: 10-20 Hz

#### 2. Passa-Alto (Highpass)

**Cosa fa**: Rimuove frequenze inferiori a una soglia, mantenendo solo le alte frequenze.

**Quando usarlo**:
- Rimuovere trend a bassa frequenza
- Evidenziare onde P (alta frequenza)
- Eliminare derive strumentali

**Parametri**:
- **Frequenza di taglio**: frequenza sotto la quale il segnale viene attenuato (es. 1 Hz)

**Esempio**:
```
Filtro passa-alto a 1 Hz
→ Rimuove: 0-1 Hz (trend, drift, maree terrestri)
→ Mantiene: >1 Hz (onde sismiche)
```

**Applicazioni tipiche**:
- Rimozione drift: 0.01-0.1 Hz
- Enfatizzare P waves: 1-2 Hz

#### 3. Passa-Banda (Bandpass)

**Cosa fa**: Mantiene solo le frequenze in un intervallo specificato, rimuovendo tutto il resto.

**Quando usarlo**:
- Isolare una specifica fase (P, S)
- Rimuovere rumore sia alto che basso
- Standard per analisi sismica

**Parametri**:
- **Frequenza minima**: limite inferiore della banda (es. 1 Hz)
- **Frequenza massima**: limite superiore della banda (es. 10 Hz)

**Esempio**:
```
Filtro passa-banda 2-8 Hz
→ Rimuove: <2 Hz (trend, onde superficiali lente)
→ Mantiene: 2-8 Hz (onde P e S tipiche)
→ Rimuove: >8 Hz (rumore ad alta frequenza)
```

**Applicazioni tipiche**:
- Terremoti locali: 1-10 Hz
- Terremoti regionali: 0.5-5 Hz
- Terremoti telesismici: 0.01-1 Hz

### Parametri Filtro

**Corners**: Il Seismic Picker usa 4 corners (4-poli Butterworth) che offrono un buon compromesso tra:
- Ripidità della transizione
- Assenza di oscillazioni (ringing)

**Zerophase**: Tutti i filtri sono zero-phase, quindi:
- Non introducono ritardi temporali
- I picks rimangono accurati
- Il segnale è leggermente "smussato"

### Come Scegliere le Frequenze

1. **Guarda lo spettro** (attiva "Mostra Spettro")
2. **Identifica i picchi**: corrispondono al contenuto in frequenza del segnale
3. **Identifica il rumore**: zone piatte o basse ampiezze
4. **Scegli il filtro**:
   - Include i picchi di interesse
   - Esclude le zone di rumore

## Analisi Spettrale

### Visualizzazione Spettro

**Accesso**:
1. Seleziona "Stazione Singola"
2. Attiva "Mostra Spettro"

**Cosa mostra**:
- Asse X: Frequenza (Hz)
- Asse Y: Ampiezza (dB)
- Linea rossa tratteggiata: Frequenza di Nyquist (f_sampling/2)

### Interpretazione

**Picchi nello spettro**:
- Indicano contenuto energetico a quella frequenza
- Più alto il picco, più energia a quella frequenza

**Esempi tipici**:
```
Picco a 1-2 Hz:    Onde di superficie (Rayleigh, Love)
Picco a 3-5 Hz:    Onde S
Picco a 7-10 Hz:   Onde P
Picco a 15-20 Hz:  Possibile rumore strumentale
Picco a 50/60 Hz:  Rumore elettrico (rete elettrica)
```

**Rumore**:
- Spettro piatto = rumore bianco
- Aumento continuo verso basse frequenze = drift/trend
- Aumento continuo verso alte frequenze = rumore digitale

### Uso dello Spettro per Ottimizzare Filtri

**Workflow**:

1. **Osserva spettro RAW**
   ```
   Identifica dove si concentra il segnale sismico
   Identifica dove si concentra il rumore
   ```

2. **Applica preprocessing**
   ```
   Rimuovi media/trend se c'è energia a ~0 Hz
   ```

3. **Progetta filtro**
   ```
   Se segnale a 2-8 Hz e rumore a >10 Hz:
   → Passa-banda 1-10 Hz
   ```

4. **Verifica risultato**
   ```
   Guarda lo spettro dopo il filtro
   Il segnale dovrebbe essere preservato
   Il rumore dovrebbe essere ridotto
   ```

5. **Raffina**
   ```
   Aggiusta le frequenze se necessario
   ```

### Frequenza di Nyquist

**Cos'è**: La massima frequenza che può essere rappresentata con un dato campionamento.

**Formula**: f_Nyquist = f_sampling / 2

**Esempi**:
```
100 Hz sampling → Nyquist = 50 Hz
50 Hz sampling  → Nyquist = 25 Hz
20 Hz sampling  → Nyquist = 10 Hz
```

**Importante**: 
- Frequenze sopra Nyquist NON esistono realmente
- Sono artefatti (aliasing)
- Mai filtrare vicino o sopra Nyquist

## Esempi Pratici

### Esempio 1: Terremoto Locale

**Scenario**: Evento locale a 50 km, dati campionati a 100 Hz

**Problema**: Rumore ad alta frequenza maschera P waves

**Soluzione**:
```
1. Rimuovi Media e Trend
2. Guarda spettro:
   - Segnale: picchi a 5-15 Hz
   - Rumore: energia >20 Hz
3. Applica Passa-Banda 2-20 Hz
4. Verifica spettro: rumore ridotto
5. Fai picking su forma d'onda pulita
```

### Esempio 2: Terremoto Regionale

**Scenario**: Evento a 500 km, dati campionati a 40 Hz

**Problema**: Trend a bassa frequenza disturba il segnale

**Soluzione**:
```
1. Rimuovi Trend (essenziale!)
2. Guarda spettro:
   - Onde di superficie: 0.5-2 Hz
   - Onde S: 2-5 Hz
   - Onde P: 5-10 Hz
3. Per picking P: Passa-Alto 3 Hz
4. Per picking S: Passa-Banda 1-8 Hz
5. Per onde superficiali: Passa-Basso 3 Hz
```

### Esempio 3: Microsismica

**Scenario**: Eventi molto piccoli, alto rumore

**Problema**: Signal-to-noise ratio molto basso

**Soluzione**:
```
1. Rimuovi Media e Trend
2. Guarda spettro:
   - Microterremoti spesso a 10-30 Hz
   - Rumore ambientale a 1-5 Hz
3. Applica Passa-Alto 8 Hz
4. Aumenta ampiezza (slider) per visualizzare meglio
5. Usa zoom temporale per dettagli
```

### Esempio 4: Dati con Drift Strumentale

**Scenario**: Deriva lenta nel tempo

**Problema**: Baseline non stabile

**Soluzione**:
```
1. Rimuovi Trend (ESSENZIALE)
2. Rimuovi Media
3. Guarda spettro:
   - Se ancora energia a <0.1 Hz: usa Passa-Alto 0.1 Hz
4. Poi applica filtro standard (es. 1-10 Hz)
```

## Tips e Best Practices

### Ordine delle Operazioni

**Sequenza raccomandata**:
```
1. Rimuovi Trend
2. Rimuovi Media
3. Applica Filtro (se necessario)
4. Visualizza Spettro (per verifica)
5. Aggiusta Filtro (se necessario)
6. Torna a Forma d'Onda per picking
```

### Quando NON Filtrare

- Se il segnale è già pulito
- Se non sai quali frequenze mantenere
- Prima di aver guardato lo spettro

### Errori Comuni

❌ **Filtrare troppo aggressivamente**
```
Passa-Banda 5-6 Hz su segnale con energia 2-10 Hz
→ Perdi informazione!
```

✅ **Soluzione**:
```
Passa-Banda 1-15 Hz (più ampio)
```

❌ **Non rimuovere trend prima di filtrare**
```
→ Filtri passa-alto possono amplificare artefatti
```

✅ **Soluzione**:
```
Sempre detrend prima di filtrare
```

❌ **Filtrare vicino a Nyquist**
```
100 Hz sampling, filtro passa-basso a 45 Hz
→ Possibile distorsione
```

✅ **Soluzione**:
```
Non filtrare oltre 0.8 * Nyquist (es. 40 Hz per 100 Hz sampling)
```

### Shortcuts Mentali

**Per picking P**:
- Passa-Alto 2-5 Hz (rimuove onde lente)

**Per picking S**:
- Passa-Banda 1-10 Hz (mantiene onde intermedie)

**Per onde superficiali**:
- Passa-Basso 2-3 Hz (rimuove P e S)

**Per rimozione rumore elettrico (50/60 Hz)**:
- Passa-Basso 30 Hz (o notch filter se disponibile)

## Riferimenti

- Ampiezza in dB: `dB = 20 * log10(amplitude)`
- Filtro Butterworth: risposta piatta in banda passante
- Zero-phase filtering: no time shift, ma smoothing bidirezionale

## Note Tecniche

**Implementazione nel Seismic Picker**:
- Libreria: ObsPy (basata su SciPy)
- Tipo filtro: Butterworth 4-poli
- Zero-phase: True (default)
- Taper: 5% Hann (automatico prima del filtro)

**Limiti**:
- Filtri molto stretti (<0.5 Hz bandwidth) possono causare ringing
- Filtri vicino a Nyquist possono dare risultati inaspettati
- Dati troppo corti (<10 cicli della frequenza minima) possono avere edge effects
