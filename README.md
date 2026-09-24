# MediaTidy

Rinomina e organizza film e serie TV usando i metadati di TMDB, con GUI a due schede: Film e Serie TV.

### Versione 0.2.0 - Settembre 2026

### Struttura del progetto


```
MediaTidy/
├── media_tidy.py # entry point
├── config.py # configurazione
├── localization.py # traduzioni
├── text_utils.py # formattazione titoli
├── media_operations.py # operazioni file
├── tmdb_client.py # chiamate TMDB
├── core/
│ ├── movie_handler.py # gestione film
│ ├── series_handler.py # gestione serie
│ └── series_classifier.py # classificazione episodi
├── ui/
│ ├── main_window.py # finestra principale
│ ├── movie_tab.py # scheda Film
│ ├── series_tab.py # scheda Serie TV
│ ├── widgets.py # widget comuni
│ └── settings_dialog.py # dialogo opzioni
└── logs/ # log operazioni
```

## Avvio

Crea ambiente virtuale (consigliato):

```bash
python3 -m venv venv
source venv/bin/activate
```

### Installa dipendenze:

```bash
pip install -r requirements.txt
```

***Avvia il programma:***

```bash
python media_tidy.py
```

## Configurazione

**Al primo avvio:**

  -  Clicca su Opzioni

   - Inserisci la chiave API TMDB

   - Imposta Destinazione Film

   - Imposta Destinazione Serie TV

   - Scegli lingua TMDB

   - Clicca OK

## Funzionalità
- **Film**

    Riconoscimento automatico titolo e anno dal nome file

    Ricerca e conferma manuale su TMDB

    Rinomina con metadati: Titolo (Anno) {tmdb-ID} [Paese, Regista]

    Download poster del film

    Spostamento o copia con gestione duplicati

    Pulizia cartelle di origine

- **Serie TV**

    Riconoscimento automatico episodi SxxEyy

    Classificazione episodi, sample, clip

    Ricerca serie su TMDB

    Struttura: Serie (Anno)/Season NN/Serie - SxxEyy - Titolo.ext

    Download poster della serie (cartella principale)

    Download poster di ogni stagione (Season NN/)

    Mai decisioni automatiche su episodi non riconosciuti

### Generale

  - Destinazioni separate per film e serie TV

  - Supporto destinazioni remote SSH/rsync

  - Mount/unmount automatico condivisioni

  - Log dettagliati e CSV

  - Traduzioni italiano/inglese

## Changelog
**0.2.0 - 2026-09-24**

Aggiunto:

    Destinazioni separate per film e serie TV

    Download poster delle stagioni

    Download poster della serie

    Tasto CANC per rimuovere file

    Dialogo Opzioni con due destinazioni

Corretto:

    Pulizia directory sorgenti per serie TV

    Gestione percorsi spostamento/copia

**0.1.0 - 2026-09-24**

Prima versione funzionante con:

    Scheda Film (da MovieTidy)

    Scheda Serie TV

    Integrazione TMDB

    Log separati


## Esempi

***Film:***

Input: `Inception.2010.1080p.mkv`

Output: `Inception (2010) {tmdb-27205}/Inception (2010).mkv`

***Serie TV:***

Input: `Breaking.Bad.S01E01.1080p.x265-ELiTE.mkv`

Output: `Breaking Bad (2008)/Season 01/Breaking Bad - S01E01 - Pilot.mkv`

## Privacy

MediaTidy è un'applicazione desktop eseguita localmente sul computer dell'utente. Non include account utente, telemetria, analytics, pubblicità, tracciamento dell'utilizzo o servizi cloud propri.

### Dati elaborati localmente

Durante il normale utilizzo, MediaTidy elabora localmente:

- I percorsi e i nomi dei file e delle cartelle selezionati dall'utente
- I metadati ricavati dai nomi dei file, come titolo, anno, stagione ed episodio
- Le impostazioni dell'applicazione, inclusi percorsi di destinazione, lingua, preferenze di rinomina e modalità copia/spostamento
- I log delle operazioni e i file CSV generati nella cartella `logs/`

Le impostazioni vengono salvate localmente tramite QSettings. I log rimangono sul computer dell'utente e vengono conservati per un periodo limitato configurato dal programma.

### Comunicazioni di rete

Quando l'utente esegue una ricerca o un test, MediaTidy invia richieste alle API di TMDB (The Movie Database) per ottenere metadati di film, serie TV, stagioni, episodi e poster.

Le richieste a TMDB possono includere:

- La chiave API TMDB inserita dall'utente
- Il titolo o la query di ricerca
- L'anno, se disponibile
- La lingua selezionata
- L'identificativo TMDB del contenuto, quando già noto
- Il numero di stagione e di episodio per le serie TV

I poster vengono scaricati dal servizio immagini di TMDB solo quando la relativa funzione viene utilizzata.

MediaTidy non invia a TMDB i file video dell'utente. In generale, i percorsi completi locali dei file non vengono inviati come parametri alle API TMDB.

### Chiave API TMDB

La chiave API TMDB viene inserita dall'utente nelle Opzioni e viene utilizzata solo per autenticare le richieste verso TMDB.

Il programma tenta di nascondere la chiave API nei messaggi di errore, nei log e nei file CSV. L'utente non deve comunque inserire la propria chiave API in file da pubblicare, repository GitHub, screenshot o segnalazioni di bug.

### Destinazioni remote

Se l'utente configura una destinazione remota, MediaTidy utilizza SSH e rsync per trasferire i file verso l'host indicato. In questo caso, dati quali file video, nomi, percorsi di destinazione e poster vengono trasmessi al server remoto scelto dall'utente.

La configurazione, la sicurezza e la privacy del server remoto sono responsabilità dell'utente.

### Controllo dell'utente

L'utente mantiene il controllo delle operazioni sui file:

- Può scegliere tra copia e spostamento
- Può verificare i risultati prima dell'esecuzione
- Può correggere manualmente titoli, identificativi TMDB, stagioni ed episodi
- Può scegliere come gestire i duplicati
- Può scegliere se rimuovere le cartelle sorgenti dopo lo spostamento
- Può eliminare manualmente impostazioni e log locali

### Servizi di terze parti

I metadati e le immagini sono forniti da TMDB. L'utilizzo di tali servizi è soggetto ai termini e all'informativa sulla privacy di TMDB.

MediaTidy non è approvato, certificato o ufficialmente associato a TMDB.

## Autore

Michele *Shuren* Bancheri

### Licenza

MIT License
