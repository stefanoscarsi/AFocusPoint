# Canon AF Point Viewer

App desktop (Windows/Mac/Linux) che legge un file CR3 e mostra:
- i dati di scatto (fotocamera, obiettivo, esposizione, ISO, focale...)
- il tipo di AF usato (modalità area AF, One-Shot/Servo, punti usati)
- il/i punto/i di messa a fuoco sovrapposti all'anteprima della foto

Pensata inizialmente per la **Canon EOS R6 Mark III**.

## ⚠️ Leggi prima di iniziare: perché serve una calibrazione

Canon **non pubblica** la struttura dei metadati proprietari (MakerNotes)
in cui sono salvati i dati AF. Tutto ciò che sappiamo su questi tag viene
da reverse engineering fatto dalla community ExifTool nel tempo. La R6
Mark III è uscita a **novembre 2025**: è recentissima, quindi il mapping
dei tag usato in questo progetto (preso dai modelli EOS R precedenti:
R5, R6 II, R3) potrebbe non essere identico o non essere ancora presente
nella tua versione di ExifTool.

Per questo il progetto è diviso in due fasi:

1. **Calibrazione** (`tools/inspect_tags.py`) — analizza un tuo file CR3
   reale e ti mostra ESATTAMENTE quali tag Canon/AF esistono nel file.
2. **Interpretazione** (`core/af_parser.py`) — usa quei nomi di tag per
   costruire i dati strutturati mostrati nella GUI. Se la calibrazione
   rivela nomi diversi da quelli già previsti, basta aggiornare le liste
   in cima al file (`_AF_AREA_MODE_TAGS`, `_AF_X_POS_TAGS`, ecc.):
   il resto del programma continua a funzionare senza altre modifiche.

## 1. Installazione

### ExifTool (obbligatorio, motore di lettura dei metadati)

- **Windows**: scarica la build più recente da https://exiftool.org (il file
  "Windows Executable"). Viene scaricato come `exiftool(-k).exe`:
  **rinominalo in `exiftool.exe`** e spostalo in una cartella presente nel
  PATH di sistema (es. `C:\Windows\` o una cartella dedicata aggiunta al
  PATH) — senza questo passaggio il programma non lo trova.
- **Mac**: piu' comodo via Homebrew: `brew install exiftool`. In alternativa,
  scarica il pacchetto `.dmg` da https://exiftool.org.
- **Linux (Ubuntu/Debian)**: `sudo apt install libimage-exiftool-perl`
  — ma attenzione: i repository di sistema spesso hanno una versione
  datata. Per una fotocamera così recente conviene scaricare l'ultima
  versione direttamente dal sito ufficiale.

Verifica con (Prompt dei comandi su Windows, Terminale su Mac):
```bash
exiftool -ver
```

### Dipendenze Python

```bash
python3 -m venv venv
source venv/bin/activate        # su Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Calibrazione (fai questo PRIMA di usare la GUI)

Scatta 3-4 foto di test con la tua R6 III cambiando modalità AF ogni
volta (es. 1 punto, zona, tracking occhio/soggetto), poi lancia:

```bash
python3 tools/inspect_tags.py /percorso/a/foto1.CR3
```

Lo script stampa a schermo (e salva in un file `.tags.txt` accanto alla
foto) tutti i tag Canon e tutti quelli con "AF" o "Focus" nel nome.
Confronta l'output tra i vari scatti: i valori che **cambiano** in base
a dove hai messo a fuoco sono quelli che ti servono.

Se i nomi non corrispondono a quelli già previsti in
`core/af_parser.py`, aggiorna le liste `_AF_*_TAGS` in cima al file con
i nomi corretti trovati nel tuo output.

## 3. Avvio dell'app

**Opzione comoda (Windows): doppio click su `avvia.bat`**
Nella cartella del progetto trovi `avvia.bat`: fai doppio click e si apre da
solo (usa automaticamente l'ambiente virtuale `venv` se presente). Se
qualcosa va storto, la finestra nera resta aperta con il messaggio di
errore invece di chiudersi subito.

**Opzione manuale (da riga di comando):**
```bash
python3 main.py
```

Poi `File → Apri CR3...` e seleziona uno scatto.

## 4. (Opzionale) Creare un vero eseguibile standalone

Se vuoi un vero file `.exe` (Windows) o `.app` (Mac) da poter spostare
liberamente — anche fuori da questa cartella, o su un altro PC senza
Python installato — usa gli script di build inclusi. Vanno eseguiti **sulla
stessa piattaforma per cui vuoi generare il file** (non si può creare un
.exe Windows da un Mac o viceversa: va fatto sul sistema di destinazione).

**Windows:** doppio click su `build_windows.bat`.
Al termine trovi l'eseguibile in `dist\CanonAFPointViewer.exe`, con l'icona
personalizzata inclusa in `assets/icon.ico`.

**Mac:** apri il Terminale, vai nella cartella del progetto ed esegui:
```bash
chmod +x build_mac.sh   # solo la prima volta, da' il permesso di esecuzione
./build_mac.sh
```
Al termine trovi l'app in `dist/Canon AF Point Viewer.app`, con l'icona
personalizzata inclusa in `assets/icon.icns`, trascinabile in Applicazioni. Al primo avvio macOS potrebbe segnalarla come "app di
sviluppatore non identificato" (Gatekeeper): tasto destro sull'app → Apri
→ Apri comunque.

**Da sapere:**
- Il file generato è grande (200-350 MB circa): include l'intero framework
  grafico Qt, è normale per un'app PySide6 standalone.
- **ExifTool resta comunque necessario a parte**, installato nel PATH di
  sistema come descritto sopra: non è incluso dentro l'exe/app. Se in
  futuro vuoi condividere l'app con altre persone senza fargli installare
  ExifTool separatamente, fammelo sapere: si può impacchettare anche
  quello, ma richiede un passaggio in più in fase di build.
- Rilanciare lo script di build rigenera l'exe/app da zero (utile dopo
  aver modificato il codice, es. calibrato `core/af_parser.py`).

## 5. Aprire i file CR3 direttamente da Esplora File o da DxO PhotoLab

Per far sì che Windows (tasto destro → **Apri con...**) o DxO PhotoLab
(impostazione "editor esterno") sappiano aprire i CR3 con questo programma,
devi indicare loro **quale eseguibile lanciare**. Il file da indicare
dipende da come usi il programma:

- **Hai generato `CanonAFPointViewer.exe`** (vedi punto 4 sopra): indica
  direttamente quel file, sia in Explorer che in DxO PhotoLab. Basta
  questo, nessun altro passaggio.
- **Esegui invece dai sorgenti** (con `venv`, senza aver generato l'exe):
  NON indicare `python.exe` direttamente — Explorer/DxO non saprebbero
  dirgli anche di eseguire `main.py`. Indica invece il file `apri_con.bat`
  incluso nel progetto: fa lui da tramite.

**Su Windows, per impostare "Apri con...":**
1. Tasto destro su un file `.CR3` → **Apri con** → **Scegli un'altra app**
2. Sfoglia fino a `CanonAFPointViewer.exe` (o `apri_con.bat` se usi i sorgenti)
3. Se vuoi che diventi il programma predefinito per i CR3, spunta l'opzione
   corrispondente; altrimenti resterà disponibile nel menu "Apri con" ogni volta

**Su DxO PhotoLab**, cerca nelle preferenze/impostazioni la voce per
configurare un "editor esterno" (external editor) e punta anche lì allo
stesso file.

## Struttura del progetto

```
canon_af_point_viewer/
├── main.py                    # avvio dell'app (gestisce anche "Apri con...")
├── avvia.bat                  # avvio comodo Windows (doppio click)
├── apri_con.bat                # wrapper per "Apri con..."/DxO se usi i sorgenti
├── build_windows.bat          # genera CanonAFPointViewer.exe
├── build_mac.sh                # genera Canon AF Point Viewer.app
├── core/
│   ├── exif_reader.py         # wrapper attorno a ExifTool
│   ├── af_parser.py           # interpreta i tag in dati strutturati
│   ├── preview_extractor.py   # estrae l'anteprima JPEG dal CR3
│   └── overlay_renderer.py    # disegna i punti AF sull'anteprima
├── gui/
│   ├── main_window.py         # finestra principale
│   └── info_panel.py          # pannello con dati di scatto e AF
└── tools/
    └── inspect_tags.py        # script di calibrazione (vedi sopra)
```

## Limiti noti di questa prima versione

- Se `AFData.points` risulta vuoto dopo il caricamento, la GUI te lo
  segnala esplicitamente e ti invita a rilanciare `inspect_tags.py`:
  non troverai mai un overlay "inventato" o impreciso senza avviso.
- Il tracking soggetto/occhio in scatti in raffica potrebbe salvare i
  dati in modo diverso dal singolo scatto: se non funziona subito,
  confrontane l'output di calibrazione con quello di un 1-punto AF.
- Nessun supporto per l'apertura di intere cartelle/raffiche in sequenza:
  è previsto come estensione naturale del progetto, non incluso qui.
