# Changelog

Tutte le modifiche rilevanti di MediaTidy sono documentate in questo file.

Il progetto usa una numerazione di versione nel formato `MAJOR.MINOR.PATCH`.

## [0.4.0] - 2026-09-25

### Aggiunto

- **Triage automatico Film/Serie TV**: un'area di drop comune sopra le due schede
  (`core/media_classifier.py`, nessuna chiamata di rete) smista da sola i file
  trascinati nella scheda giusta; anche le tabelle di ciascuna scheda restano
  ricettive a tutto e si "autocorreggono" spostando nell'altra scheda ciò che non
  è suo. Nei casi davvero ambigui (nessun anno, nessun codice episodio) chiede
  conferma, con il tipo della scheda/zona di drop come suggerimento predefinito.
- **Dialogo "Formato Nomi"**, a fianco di Opzioni: destinazione, azione
  Sposta/Copia, modalità titolo (solo originale / solo localizzato / entrambi in
  un ordine o nell'altro) e i toggle su cosa includere nel nome/cartella
  (ID TMDB, paese, regista, titolo episodio, poster) — indipendenti tra Film e
  Serie TV.
- Bottoni **Esegui selezionati** / **Esegui tutti** separati (con conteggio ed
  azione in etichetta, es. "Sposta 3 sel." / "Copia tutto (12)"), al posto di un
  unico "Esegui" che ereditava in modo implicito un'eventuale selezione residua.
- Doppio click sulle colonne di nome/cartella per aprire la modifica
  personalizzata (Film), e un unico dialogo "Modifica episodio e nome" per le
  Serie TV (stagione/episodio + nome/cartella insieme, con stagione/episodio
  non più bloccanti se il nome è stato impostato a mano).
- Pulsante **Ripristina nome automatico** nei dialoghi di modifica personalizzata.
- Selezione multipla da tastiera con **Ctrl+A**, oltre a Canc/Backspace.
- Layout della barra superiore rivisto: Opzioni e Formato Nomi a sinistra, Log e
  Crediti & Privacy a destra.

### Corretto

- Canc/Backspace sulla tabella disallineava le righe visualizzate dagli item
  interni, causando modifiche/esecuzioni sulla riga sbagliata dopo un'eliminazione.
- Cliccare su una riga già selezionata non la deselezionava più (il click veniva
  "annullato" al rilascio del tasto da alcuni stili grafici, incluso quello
  tipico di Linux Mint); ora un clic su una qualsiasi riga selezionata
  deseleziona tutto, anche a tabella piena.
- Il poster di stagione veniva richiesto a TMDB e riscaricato per ogni singolo
  episodio invece che una sola volta per stagione.
- Il poster di stagione veniva richiesto anche per episodi non riconosciuti
  (stagione ignota), sprecando una chiamata TMDB.
- Rimossa una classe `SettingsDialog` residua in `ui/widgets.py` che referenziava
  una chiave di configurazione (`dest`) non più esistente dalla v0.3.

## [0.3.0] - 2026-09-25

### Aggiunto

- Configurazione separata delle cartelle di destinazione per Film e Serie TV.
- Selettore della cartella dei log e dei file CSV nella finestra **Opzioni**.
- Percorso predefinito dei log in:
  ```text
  ~/.local/share/MediaTidy/logs/
  ```
- Salvataggio persistente del percorso dei log tramite QSettings.
- Pulsante **Log** nella barra superiore per aprire la cartella configurata dei log e dei file CSV.
- Supporto per la distribuzione locale tramite file AppImage.
- Icona dell’applicazione `MT_Icon.png`.
- Documentazione privacy nel repository e nelle informazioni dell’app.

### Modificato

- I log e i CSV non dipendono più dalla posizione dei file sorgente o dal bundle AppImage.
- La gestione della cartella dei log legge sempre la configurazione utente corrente.
- Aggiornata la documentazione di progetto e della distribuzione Linux.

### Sicurezza e privacy

- La chiave API TMDB continua a essere memorizzata localmente tramite QSettings.
- I messaggi di errore, i log e i CSV mascherano la chiave API TMDB quando possibile.
- I log e i CSV possono includere nomi e percorsi dei file elaborati: non devono essere pubblicati.

## [0.2.0] - 2026-09-24

### Aggiunto

- Prima release pacchettizzata per Linux in formato AppImage.
- Gestione dei metadati TMDB per film e serie TV.
- Operazioni di copia, spostamento, rinomina e organizzazione dei file.
- Supporto per destinazioni locali e remote mediante SSH/rsync.
- Download opzionale di poster da TMDB.
- Log giornalieri e CSV separati per film e serie TV.
- Interfaccia grafica in italiano e inglese.

## [0.1.0] - 2026-09-24

### Aggiunto

- Prima versione di MediaTidy.
- Interfaccia grafica con schede Film e Serie TV.
- Ricerca dei metadati tramite TMDB.
- Riconoscimento di titoli, anni, stagioni ed episodi.
