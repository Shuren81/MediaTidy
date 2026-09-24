# Changelog

Tutte le modifiche rilevanti di MediaTidy sono documentate in questo file.

Il progetto usa una numerazione di versione nel formato `MAJOR.MINOR.PATCH`.

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
