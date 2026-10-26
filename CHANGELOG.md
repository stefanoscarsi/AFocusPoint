# Cronologia delle versioni

Il numero di versione vive in `version.py` (unico punto). Ogni release ha
un tag git `vX.Y.Z`. Schema: MAJOR.MINOR.PATCH (vedi `version.py`).

## 1.0.0 — 2026-10-26

Prima versione con numero. Raccoglie il lavoro che ha reso l'app funzionante
e verificata su macOS oltre che su Windows.

### Aggiunto
- **Supporto completo a macOS**, senza cambiare il comportamento su Windows:
  - ExifTool trovato anche quando l'app è avviata dal Finder o dal Dock
    (cartelle di Homebrew), non solo dal Terminale;
  - file aperti da "Apri con…" e dal trascinamento sul Dock;
  - trackpad: due dita per spostarsi, pizzico o Cmd+scorrimento per lo zoom,
    doppio tocco per adattare; nuovo menu "Vista" con zoom da tastiera;
  - build dedicata (`build_mac.sh` + `AFocusPoint-mac.spec`) che produce
    `.app` e `.dmg`, dichiara i CR3 per "Apri con…" e genera un pacchetto
    firmabile (~115 MB invece di 643 MB);
  - avvio comodo con `avvia.command`.
- **Numero di versione** mostrato nel titolo della finestra e nella voce
  "Informazioni su AFocusPoint".
- File per riprendere lo sviluppo su qualsiasi computer: `requirements-dev.txt`,
  `CLAUDE.md`, istruzioni nel README.

### Modificato
- Il riquadro del punto AF è disegnato sopra la foto con spessore fisso sullo
  schermo: resta visibile a ogni zoom, anche con la foto adattata alla finestra
  (prima quasi spariva).
- Quando la fotocamera ha confermato a fuoco molte aree insieme, i riquadri
  sono disegnati con linea sottile e senza crocetta, così la foto resta
  visibile sotto. Gli stessi punti, nelle stesse posizioni: nessuno aggiunto,
  tolto, spostato o unito.

### Sicurezza
- I percorsi passati a ExifTool sono validati (niente caratteri di controllo,
  sempre percorso assoluto).
- Su Windows ExifTool non è più cercato nella cartella corrente.
- Valori EXIF e messaggi di errore mostrati come testo semplice, mai come HTML.

### Verificato
- Metadati corretti su tutte le 4.485 foto di prova (confronto con ExifTool,
  nessuna differenza).
- Punto AF controllato a video su 62 foto: corrisponde sempre al dato
  registrato dalla fotocamera.
