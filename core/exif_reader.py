"""
exif_reader.py
---------------
Wrapper attorno a ExifTool (via PyExifTool) per estrarre metadati da file
Canon CR3. ExifTool e' l'unico strumento con un mapping (reverse-engineered
dalla community, dato che Canon non pubblica specifiche ufficiali) dei tag
proprietari Canon contenuti nei MakerNotes, dove risiedono i dati di
messa a fuoco.

Non ipotizziamo QUALI tag esistano per la R6 Mark III: recuperiamo tutto
cio' che e' disponibile e lasciamo che sia af_parser.py a interpretarlo,
in modo che il sistema resti robusto anche se il set di tag di questo
corpo macchina (uscito a novembre 2025) differisce da quello dei modelli
precedenti.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import exiftool


class ExifToolNotFoundError(RuntimeError):
    """Sollevata quando il binario exiftool non e' disponibile nel PATH."""


# Su macOS un'app avviata dal Finder/Dock (il .app generato da build_mac.sh,
# o "Apri con...") NON eredita il PATH del Terminale, ma solo quello minimo
# di sistema (/usr/bin:/bin:/usr/sbin:/sbin): le cartelle di Homebrew e
# dell'installer ufficiale di exiftool.org non ci sono, quindi
# shutil.which() fallisce anche con ExifTool installato correttamente.
# Per questo, se la ricerca nel PATH fallisce, proviamo anche i percorsi di
# installazione standard.
_MACOS_FALLBACK_DIRS = (
    "/opt/homebrew/bin",  # Homebrew su Apple Silicon
    "/usr/local/bin",     # Homebrew su Intel e installer .pkg di exiftool.org
)


def find_exiftool() -> str:
    """
    Ritorna il percorso completo dell'eseguibile exiftool.
    Solleva ExifToolNotFoundError se non e' presente.
    """
    if sys.platform == "win32":
        # Su Windows shutil.which (e CreateProcess) cercano l'eseguibile
        # PRIMA nella cartella corrente e solo dopo nel PATH: un
        # exiftool.exe estraneo nella cartella da cui l'app viene avviata
        # (ad es. quella delle foto) verrebbe eseguito al posto di quello
        # vero. Questa variabile, documentata da Microsoft, disattiva la
        # ricerca nella cartella corrente.
        os.environ["NoDefaultCurrentDirectoryInExePath"] = "1"
    path = shutil.which("exiftool")
    if path is None and sys.platform == "darwin":
        for directory in _MACOS_FALLBACK_DIRS:
            candidate = Path(directory) / "exiftool"
            if candidate.is_file():
                path = str(candidate)
                break
    if path is None:
        raise ExifToolNotFoundError(
            "exiftool non trovato nel PATH.\n"
            "Installalo da https://exiftool.org (Windows/Mac), su Mac anche "
            "con 'brew install exiftool', oppure, su Linux, con "
            "'sudo apt install libimage-exiftool-perl'.\n"
            "IMPORTANTE: per una fotocamera recente come la R6 Mark III, "
            "usa la versione piu' aggiornata possibile, non quella dei "
            "repository di sistema (spesso datata)."
        )
    return path


def check_exiftool_available() -> str:
    """
    Verifica che il binario exiftool sia installato e ne ritorna la versione.
    Solleva ExifToolNotFoundError se non e' presente.
    """
    result = subprocess.run(
        [find_exiftool(), "-ver"], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _safe_path(file_path: str | Path) -> str:
    """
    Percorso da passare a ExifTool, validato.

    PyExifTool invia gli argomenti a ExifTool una riga per volta: un nome
    di file con caratteri di controllo (un a-capo e' lecito nei nomi di
    file su macOS e Linux) verrebbe spezzato in piu' argomenti e letto come
    opzioni di ExifTool. Rifiutiamo quindi questi nomi, e passiamo sempre il
    percorso assoluto, che non puo' mai cominciare con '-' (che ExifTool
    interpreterebbe anch'esso come un'opzione).
    """
    path = str(Path(file_path).resolve())
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in path):
        raise ValueError(
            "Il nome del file o della cartella contiene caratteri non "
            "ammessi (es. un a-capo): rinominalo e riprova."
        )
    return path


def read_all_metadata(file_path: str | Path) -> dict[str, Any]:
    """
    Ritorna un dizionario con TUTTI i tag letti da ExifTool per il file
    indicato, con chiavi nel formato 'Gruppo:NomeTag' (es. 'Canon:AFAreaMode').

    Usiamo '-G1' internamente (tramite ExifToolHelper con i parametri
    corretti) per avere il gruppo specifico (Canon, ExifIFD, Composite...),
    utile per distinguere tag omonimi in gruppi diversi.
    """
    file_path = _safe_path(file_path)
    # IMPORTANTE: ExifToolHelper aggiunge di default common_args=['-G', '-n'],
    # che imporrebbero SEMPRE valori grezzi numerici anche alla chiamata
    # "formattata" qui sotto (bug scoperto durante il test con un file reale:
    # anche 'AFAreaMode' con descrizione testuale nota tornava come numero).
    # Passiamo common_args=[] per avere il pieno controllo sui parametri.
    # executable= esplicito: altrimenti PyExifTool cerca "exiftool" nel PATH
    # per conto suo, e dal Finder su Mac non lo troverebbe (vedi sopra).
    with exiftool.ExifToolHelper(executable=find_exiftool(), common_args=[]) as et:
        # -G1 = usa i nomi di gruppo "family 1" (es. Canon, ExifIFD), che e'
        #       lo schema di raggruppamento assunto in af_parser.py.
        # -n  = valori numerici "grezzi" invece che stringhe formattate,
        #       fondamentale per fare calcoli sulle coordinate AF.
        # Manteniamo pero' anche una copia "formattata" (senza -n) per i
        # dati di scatto e le descrizioni leggibili (es. "Flexible Zone AF 1").
        raw = et.get_metadata(file_path, params=["-G1", "-n"])
        formatted = et.get_metadata(file_path, params=["-G1"])

    raw_dict = raw[0] if raw else {}
    formatted_dict = formatted[0] if formatted else {}

    return {"raw": raw_dict, "formatted": formatted_dict}


def extract_binary_tag(file_path: str | Path, tag_name: str) -> bytes | None:
    """
    Estrae il contenuto binario di un tag (es. PreviewImage, JpgFromRaw)
    usando 'exiftool -b -TAG file'. Ritorna None se il tag non esiste o
    e' vuoto.
    """
    file_path = _safe_path(file_path)
    exe = find_exiftool()

    result = subprocess.run(
        [exe, "-b", f"-{tag_name}", file_path],
        capture_output=True,
        check=True,
    )
    data = result.stdout
    return data if data else None
