# Changelog

Tutte le modifiche rilevanti di MediaTidy sono documentate in questo file.

Il progetto usa una numerazione di versione nel formato `MAJOR.MINOR.PATCH`.

## [0.5.3] - 2026-09-25

### Corretto

- Nella pulizia delle cartelle di origine (Serie TV), la cartella "genitore"
  trascinata dall'utente (es. la cartella della serie, sopra le sottocartelle
  Season NN) non veniva mai presa in considerazione: solo la cartella
  immediata di ciascun file (la singola stagione) veniva controllata e,
  se vuota, proposta per la cancellazione. Questo lasciava la cartella
  principale della serie — e qualunque file non video al suo interno — non
  calcolata, senza prompt e mai cancellata, anche dopo aver svuotato tutte
  le sue sottocartelle. Ora viene registrata anche lei (tramite `release_dir`,
  già presente su ogni item ma non ancora usato per la pulizia) e controllata
  con le stesse regole di sicurezza già esistenti.

## [0.5.2] - 2026-09-25

### Corretto

- Risolti gli avvisi ripetuti in console (`QWidget::paintEngine: Should no
  longer be called`, `QPainter::begin: Paint device returned engine == 0`, e
  gli errori a cascata che ne conseguivano) generati dal bordo colorato delle
  tabelle Film/Serie durante il trascinamento. La causa era disegnare il
  bordo con un `QPainter` direttamente sulla tabella (`QTableWidget`), che
  però eredita da `QAbstractScrollArea` ed espone come vera superficie di
  disegno solo il proprio `viewport()`, non sé stessa. Il bordo ora viene
  applicato via foglio di stile invece che disegnato a mano, eliminando il
  problema alla radice — non bloccante, ma comparivano ad ogni trascinamento.

## [0.5.1] - 2026-09-25

### Modificato

- L'etichetta col nome del programma diventa gialla anche mentre si trascina
  sopra le tabelle Film/Serie (prima lo faceva solo trascinando su un'area
  neutra della finestra, perché le tabelle intercettano il trascinamento con
  la precedenza voluta e la finestra non se ne accorgeva più).

## [0.5.0] - 2026-09-25

### Aggiunto

- **Feedback visivo sul trascinamento**: le tabelle Film/Serie mostrano un
  contorno giallo mentre si trascina sopra, e un lampeggio verde/rosso di circa
  mezzo secondo dopo il rilascio a seconda che sia stato importato qualcosa o no.
- **Tutta la finestra è ora area di rilascio** (non solo un riquadro dedicato):
  le tabelle mantengono la precedenza quando il drop avviene sopra di loro.
- Il riquadro di drop in alto è stato sostituito da un'etichetta col nome del
  programma ("MediaTidy v{VERSION} by Shuren") che segnala anch'essa lo stato
  del trascinamento, ma con esito **fisso** (verde o rosso) finché non si
  ricomincia a trascinare, a differenza del lampeggio breve delle tabelle.

### Rimosso

- Il controllo Sposta/Copia dal dialogo Formato Nomi: era duplicato rispetto
  al radio button di ciascuna scheda (che resta l'unico punto per impostare
  l'azione, più comodo da raggiungere durante il lavoro quotidiano).
- L'area di drop dedicata (`DropZone`), non più usata in favore dell'intera
  finestra come area di rilascio.

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
