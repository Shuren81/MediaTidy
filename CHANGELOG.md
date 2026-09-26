# Changelog

Tutte le modifiche rilevanti di MediaTidy sono documentate in questo file.

Il progetto usa una numerazione di versione nel formato `MAJOR.MINOR.PATCH`.

## [0.7.1] - 2026-09-26

### Aggiunto

- Il codice TMDB già scritto nel nome di un file o di una cartella (formato
  `{tmdb-ID}`, quello che MediaTidy stesso usa) viene ora riconosciuto in
  automatico non appena il file viene aggiunto alla lista: il Test salta
  direttamente al recupero dei dettagli, senza rifare una ricerca e senza
  chiedere conferma. Per i film cerca nel file e nella cartella che lo
  contiene; per le serie anche nella cartella "nonna" (la cartella della
  serie, sopra Season NN), dove MediaTidy scrive il codice.

### Corretto

- La checkbox "Applica anche agli altri episodi di questa release" (v0.6.0)
  ora richiede anche che il nome di serie indovinato sia simile, non solo che
  la cartella di origine sia la stessa: se in un'unica cartella trascinata
  convivono più serie diverse non ancora organizzate, confermarne una non
  scrive più per errore lo stesso codice TMDB sugli episodi delle altre.

## [0.7.0] - 2026-09-26

### Aggiunto

- Il nome di ciascuna scheda mostra ora anche quanti file sono pronti, es.
  "Film (12, 8 pronti)".
- Etichetta con la dimensione totale da spostare/copiare (somma dei file
  "pronti") e lo spazio libero sul disco di destinazione, accanto ai bottoni
  Esegui — non disponibile per destinazioni remote (SSH).
- Il bottone **Test** mostra ora anche lui il conteggio, come i bottoni
  Esegui: "Test tutto (N)" senza selezione, "Test N sel." con una selezione
  attiva — ed è disabilitato quando quel conteggio è zero.
- Bottone/scorciatoia **"Inverti selezione"** (Ctrl+I) accanto a Ctrl+A.
- **Copia percorso di origine** e **Copia percorso di destinazione previsto**
  nel menu contestuale (quest'ultimo solo se il nome/cartella di destinazione
  sono già stati calcolati).
- Il tooltip sulla colonna "Cartella di destinazione" mostra ora il percorso
  assoluto completo (destinazione + cartella), non solo il testo già
  visibile in cella.

## [0.6.2] - 2026-09-25

### Corretto

- **Bug di sicurezza**: se un file video si trovava direttamente nella "radice"
  di una cartella trascinata (non in una sottocartella), la pulizia della
  cartella di origine proponeva di cancellare l'INTERA cartella radice — che
  poteva contenere qualunque altro contenuto non correlato (altre
  sottocartelle, documenti, foto...). Una prima correzione troppo prudente
  impediva la pulizia di QUALSIASI cartella con sottocartelle residue, ma
  questo bloccava anche un caso legittimo e comune: release con una
  sottocartella "Screens" (o Sample, Subs, Proof...) accanto al file video.
  La regola definitiva: una cartella con sottocartelle residue viene ancora
  proposta per la cancellazione (con conferma) solo se TUTTE quelle
  sottocartelle hanno un nome riconosciuto come "di scarto" di una release
  scene (sample, screens, screenshots, proof, subs, subtitles, extras,
  featurettes, artwork, covers, scans — corrispondenza esatta,
  case-insensitive); se anche una sola sottocartella ha un nome diverso, la
  cartella non viene mai più proposta, nemmeno con conferma. Il caso
  legittimo delle stagioni (Season 01, Season 02...) resta invariato.

## [0.6.0] - 2026-09-25

### Aggiunto

- **Evidenziazione tab all'import**: dopo ogni rilascio (ovunque avvenga —
  tabella giusta, sbagliata, o area neutra della finestra), MediaTidy passa
  automaticamente alla scheda che ha ricevuto più file in quel singolo
  trascinamento. In caso di parità (incluso nessun file importato) la scheda
  attiva non cambia.
- Nel dialogo di conferma serie TV, una nuova checkbox **"Applica anche agli
  altri episodi di questa release"**: se confermata, scrive lo stesso codice
  TMDB su tutti gli altri episodi ancora da testare che condividono la stessa
  cartella di origine, evitando un popup identico per ogni file di una
  release già organizzata Serie/Stagione/Episodio.
- Bottone **"Apri cartella"** nel dialogo "cartella di origine non vuota" e
  in quello dei duplicati (quest'ultimo solo per destinazioni locali), per
  vedere il contenuto prima di decidere.
- **Icona personalizzata dell'applicazione** (`MT_Icon.png`) al posto
  dell'icona di default nella barra del titolo/applicazioni.
- **Paese di produzione anche per le serie TV**, nel formato
  `Titolo (Paese, Anno)` — diverso dal formato film, che resta invariato per
  ora. Attivabile/disattivabile con una nuova checkbox indipendente nella
  scheda Serie TV di Formato Nomi.

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
- L'etichetta ora resta verde/rossa fissa anche dopo un rilascio avvenuto
  sopra una tabella (prima questo accadeva solo per i rilasci sull'area
  neutra della finestra).
- Il testo dell'etichetta usa `font-weight: bold` invece del valore numerico
  `800`, più affidabile su diversi temi/font di sistema.

## [0.5.0] - 2026-09-25

### Aggiunto

- **Feedback visivo sul trascinamento**: le tabelle Film/Serie mostrano un
  contorno giallo mentre si trascina sopra, e un lampeggio verde/rosso di circa
  mezzo secondo dopo il rilascio a seconda che sia stato importato qualcosa o no.
- **Tutta la finestra è ora area di rilascio** (non solo un riquadro dedicato):
  le tabelle mantengono la precedenza quando il drop avviene sopra di loro.
- Il riquadro di drop in alto è stato sostituito da un'etichetta col nome del
  programma ("MediaTidy v{VERSION} by Shuren", poi ingrandita in stile banner
  con bordo colorato) che segnala anch'essa lo stato del trascinamento, ma con
  esito **fisso** (verde o rosso) finché non si ricomincia a trascinare, a
  differenza del lampeggio breve delle tabelle.

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
- **Feedback visivo sul trascinamento**: le tabelle Film/Serie mostrano un
  contorno giallo mentre si trascina sopra, e un lampeggio verde/rosso di circa
  mezzo secondo dopo il rilascio a seconda che sia stato importato qualcosa o no.
- **Tutta la finestra è ora area di rilascio** (non solo un riquadro dedicato):
  le tabelle mantengono la precedenza quando il drop avviene sopra di loro.
- Il riquadro di drop in alto è stato sostituito da un'etichetta col nome del
  programma ("MediaTidy v{VERSION} by Shuren") che segnala anch'essa lo stato
  del trascinamento, ma con esito **fisso** (verde o rosso) finché non si
  ricomincia a trascinare, a differenza del lampeggio breve delle tabelle.

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
- Rimosso il controllo Sposta/Copia dal dialogo Formato Nomi: era duplicato
  rispetto al radio button di ciascuna scheda (unico punto rimasto per
  impostare l'azione, più comodo da raggiungere durante il lavoro quotidiano).
- Rimossa l'area di drop dedicata (`DropZone`, non più usata) in favore
  dell'intera finestra come area di rilascio.

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
