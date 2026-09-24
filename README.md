# MediaTidy

MediaTidy è un’applicazione desktop per Linux che rinomina e organizza film e serie TV usando i metadati di [TMDB](https://www.themoviedb.org/).

L’interfaccia grafica include due schede dedicate:

- **Film**
- **Serie TV**

L’applicazione consente di analizzare i file video, cercare i metadati corrispondenti, verificare i risultati proposti e quindi copiare, spostare o rinominare i file secondo una struttura ordinata.

## Funzionalità

- Ricerca di film e serie TV tramite API TMDB.
- Riconoscimento di titolo e anno dai nomi dei file.
- Riconoscimento di stagioni ed episodi per le serie TV.
- Recupero del titolo del singolo episodio.
- Rinomina dei file video secondo regole configurabili.
- Scelta tra modalità **Copia** e **Sposta**.
- Rinomina direttamente nella cartella sorgente, quando appropriato.
- Gestione dei duplicati: sovrascrittura, suffisso automatico, modifica manuale o salto.
- Pulizia opzionale delle cartelle sorgenti vuote dopo uno spostamento.
- Supporto per destinazioni locali e remote tramite SSH/rsync.
- Download opzionale di poster da TMDB.
- Interfaccia in italiano e inglese.
- Log giornalieri e file CSV per le operazioni relative a film e serie TV.
- Cartelle di destinazione separate per Film e Serie TV.
- Percorso dei log personalizzabile dalla finestra **Opzioni**.

## Installazione

### AppImage

La versione consigliata per Linux è disponibile nella pagina [Releases](../../releases).

1. Scarica il file AppImage più recente.
2. Rendilo eseguibile:

   ```bash
   chmod +x MediaTidy-*.AppImage
   ```

3. Avvialo:

   ```bash
   ./MediaTidy-*.AppImage
   ```

In alternativa, dal file manager di Linux Mint, fai clic destro sul file, apri **Proprietà → Permessi**, abilita l’esecuzione come programma e apri il file.

### Da sorgente

Clona il repository ed esegui:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 media_tidy.py
```

## Configurazione

Alla prima esecuzione, apri **Opzioni** e configura almeno:

- La tua chiave API TMDB.
- La cartella di destinazione per i film.
- La cartella di destinazione per le serie TV.
- La lingua usata per le ricerche TMDB.
- La modalità operativa: copia o spostamento.

Facoltativamente, puoi configurare:

- Regola di capitalizzazione dei titoli.
- Smontaggio automatico del disco dopo l’elaborazione.
- Rimozione delle cartelle sorgenti rimaste vuote.
- Lingua dell’interfaccia.
- Cartella personalizzata per log e CSV.

## Log e CSV

Per impostazione predefinita, MediaTidy salva log e file CSV in:

```text
~/.local/share/MediaTidy/logs/
```

Dalla finestra **Opzioni** puoi selezionare un’altra cartella. Il programma crea la directory automaticamente quando deve scrivere un log o un CSV.

I file generati includono normalmente:

```text
MediaTidy_YYYY-MM-DD.log
MediaTidy_movies_YYYY-MM-DD.csv
MediaTidy_series_YYYY-MM-DD.csv
```

I log e i CSV possono contenere nomi di file e percorsi locali: non pubblicarli se contengono dati personali.

## Struttura del progetto

```text
MediaTidy/
├── media_tidy.py            # Avvio dell’applicazione
├── config.py                 # Configurazione condivisa e QSettings
├── localization.py           # Traduzioni italiano/inglese
├── text_utils.py             # Sanificazione e capitalizzazione dei titoli
├── media_operations.py       # Log, CSV, file, mount, SSH e rsync
├── tmdb_client.py            # Client API TMDB
├── MT_Icon.png               # Icona dell’applicazione
├── requirements.txt          # Dipendenze Python
├── CHANGELOG.md              # Cronologia delle versioni
├── core/
│   ├── movie_handler.py      # Logica film
│   ├── series_handler.py     # Logica serie TV
│   └── series_classifier.py  # Riconoscimento episodi, sample e clip
├── ui/
│   ├── main_window.py        # Finestra principale
│   ├── movie_tab.py          # Scheda Film
│   ├── series_tab.py         # Scheda Serie TV
│   ├── settings_dialog.py    # Finestra Opzioni
│   └── widgets.py            # Widget e dialoghi condivisi
└── AppImage/
    ├── build_appimage.sh     # Script di build locale
    └── MediaTidy.desktop     # Desktop entry dell’AppImage
```

Le directory `venv/`, `build/`, `dist/`, `tools/` e `logs/` sono generate localmente e non devono essere incluse nel repository.

## Privacy

MediaTidy viene eseguito localmente sul computer dell’utente. Non richiede un account, non include pubblicità, telemetria o analytics.

### Dati elaborati localmente

MediaTidy può elaborare localmente:

- Nomi e percorsi dei file e delle cartelle selezionati.
- Metadati ricavati dai nomi dei file, come titolo, anno, stagione ed episodio.
- Impostazioni dell’applicazione, inclusi percorsi di destinazione, lingua e preferenze di rinomina.
- Log e CSV delle operazioni.

Le preferenze, inclusa la chiave API TMDB, sono memorizzate localmente tramite QSettings.

### Connessioni di rete

Quando l’utente cerca o verifica un contenuto, MediaTidy contatta le API TMDB per ottenere metadati di film, serie TV, stagioni, episodi e poster.

Le richieste possono includere:

- Chiave API TMDB.
- Titolo della ricerca.
- Anno, se disponibile.
- Lingua selezionata.
- Identificativi TMDB.
- Numero di stagione ed episodio.

I file video dell’utente non vengono caricati su TMDB.

Se viene configurata una destinazione remota, MediaTidy usa SSH e rsync per trasferire file e poster verso il server scelto dall’utente. La sicurezza e la privacy del server remoto sono responsabilità dell’utente.

### Chiave API TMDB

La chiave API TMDB viene usata esclusivamente per autenticare le richieste a TMDB. Il programma tenta di mascherarla nei messaggi di errore, nei log e nei CSV.

Non pubblicare mai la chiave API in repository, screenshot, log o segnalazioni di bug.

## Licenza

Da definire.

## Crediti

Programma realizzato da Michele *Shuren* Bancheri, con l'ausilio di Claude.ai per la struttura base e Perplexity.ai per tutto il resto

MediaTidy usa le API e le immagini di [TMDB](https://www.themoviedb.org/).

Questo prodotto usa le API TMDB ma non è approvato né certificato da TMDB.
