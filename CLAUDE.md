# AFocusPoint — note per Claude Code

App desktop PySide6 che legge un RAW Canon CR3 tramite ExifTool e mostra
dati di scatto, dati AF e il punto di messa a fuoco sopra l'anteprima.
L'utente scrive in italiano: rispondi in italiano.

## Vincoli

- **Deve funzionare sia su macOS sia su Windows.** Lo sviluppo avviene su
  entrambi: ogni modifica va pensata per tutti e due, e una correzione per
  un sistema non deve cambiare il comportamento dell'altro.
- Differenze di piattaforma già gestite (non romperle):
  - macOS: un'app avviata dal Finder non eredita il PATH del Terminale →
    `core/exif_reader.find_exiftool()` cerca anche nelle cartelle di
    Homebrew; i file aperti dal Finder arrivano come `QFileOpenEvent`
    (`AFocusPointApp` in `main.py`), non in `sys.argv`; il trackpad manda
    `pixelDelta` (scorrimento = spostamento, pizzico = zoom).
  - Windows: il file arriva in `sys.argv`; `find_exiftool()` disattiva la
    ricerca di eseguibili nella cartella corrente.
- Build separate: `build_windows.bat` (exe singolo, rigenera
  `AFocusPoint.spec`) e `build_mac.sh` (usa `AFocusPoint-mac.spec`, che
  dichiara i CR3 per "Apri con..." e NON usa `collect_all('PySide6')`).

## Regole del codice

- Ogni percorso passato a ExifTool passa da `exif_reader._safe_path()`:
  PyExifTool invia gli argomenti una riga per volta, quindi nomi con
  caratteri di controllo vanno rifiutati. Non aggirarlo.
- Testo che arriva dal file (valori EXIF, nomi file, errori) si mostra come
  testo semplice, mai come HTML (`html.escape`, `Qt.PlainText`).
- I riquadri AF non si disegnano nei pixel della foto: `frame_builder`
  restituisce le coordinate e `gui/af_overlay.py` li disegna sopra con
  penne "cosmetiche" (spessore fisso sullo schermo).
- La logica pura (`core/`, `gui/zoom.py`) resta senza Qt dove possibile,
  per poterla testare.
- Un confronto automatico di nitidezza è già stato provato e rimosso perché
  inaffidabile (vedi docstring di `core/frame_builder.py`).

## Comandi

- Setup: `python3 -m venv venv` e `venv/bin/pip install -r requirements-dev.txt`
  (Windows: `py -m venv venv`, `venv\Scripts\pip ...`). Serve anche ExifTool.
- Test: `venv/bin/python -m pytest` (non servono foto né ExifTool).
- App dai sorgenti: `venv/bin/python main.py [foto.CR3]`.
- Build: `./build_mac.sh` su Mac, `build_windows.bat` su Windows: ognuna
  va eseguita sul proprio sistema.
