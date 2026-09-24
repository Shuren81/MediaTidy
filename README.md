#MediaTidy

Rinomina e organizza film e serie TV usando i metadati di TMDB, con GUI a due schede: Film e Serie TV.
Versione

0.2.0 - Settembre 2026

###Struttura del progetto


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

##Avvio

Crea ambiente virtuale (consigliato):

```bash
python3 -m venv venv
source venv/bin/activate
```

###Installa dipendenze:

```bash
pip install -r requirements.txt
```

***Avvia il programma:***

```bash
python media_tidy.py
```

##Configurazione

**Al primo avvio:**

  -  Clicca su Opzioni

   - Inserisci la chiave API TMDB

   - Imposta Destinazione Film

  -  Imposta Destinazione Serie TV

   - Scegli lingua TMDB

   - Clicca OK

##Funzionalità
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

###Generale

   - Destinazioni separate per film e serie TV

  - Supporto destinazioni remote SSH/rsync

  - Mount/unmount automatico condivisioni

  - Log dettagliati e CSV

  - Traduzioni italiano/inglese

##Changelog
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





##Esempi

***Film:***

Input: `Inception.2010.1080p.mkv`

Output: `Inception (2010) {tmdb-27205}/Inception (2010).mkv`

***Serie TV:***

Input: `Breaking.Bad.S01E01.1080p.x265-ELiTE.mkv`

Output: `Breaking Bad (2008)/Season 01/Breaking Bad - S01E01 - Pilot.mkv`

##Autore

Michele *Shuren* Bancheri

###Licenza

MIT License
