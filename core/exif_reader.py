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

import shutil
import subprocess
from pathlib import Path
from typing import Any

import exiftool


class ExifToolNotFoundError(RuntimeError):
    """Sollevata quando il binario exiftool non e' disponibile nel PATH."""


def check_exiftool_available() -> str:
    """
    Verifica che il binario exiftool sia installato e ne ritorna la versione.
    Solleva ExifToolNotFoundError se non e' presente.
    """
    path = shutil.which("exiftool")
    if path is None:
        raise ExifToolNotFoundError(
            "exiftool non trovato nel PATH.\n"
            "Installalo da https://exiftool.org (Windows/Mac) oppure, su "
            "Linux, con 'sudo apt install libimage-exiftool-perl'.\n"
            "IMPORTANTE: per una fotocamera recente come la R6 Mark III, "
            "usa la versione piu' aggiornata possibile, non quella dei "
            "repository di sistema (spesso datata)."
        )
    result = subprocess.run(
        [path, "-ver"], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def read_all_metadata(file_path: str | Path) -> dict[str, Any]:
    """
    Ritorna un dizionario con TUTTI i tag letti da ExifTool per il file
    indicato, con chiavi nel formato 'Gruppo:NomeTag' (es. 'Canon:AFAreaMode').

    Usiamo '-G1' internamente (tramite ExifToolHelper con i parametri
    corretti) per avere il gruppo specifico (Canon, ExifIFD, Composite...),
    utile per distinguere tag omonimi in gruppi diversi.
    """
    file_path = str(file_path)
    # IMPORTANTE: ExifToolHelper aggiunge di default common_args=['-G', '-n'],
    # che imporrebbero SEMPRE valori grezzi numerici anche alla chiamata
    # "formattata" qui sotto (bug scoperto durante il test con un file reale:
    # anche 'AFAreaMode' con descrizione testuale nota tornava come numero).
    # Passiamo common_args=[] per avere il pieno controllo sui parametri.
    with exiftool.ExifToolHelper(common_args=[]) as et:
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
    file_path = str(file_path)
    exe = shutil.which("exiftool")
    if exe is None:
        raise ExifToolNotFoundError("exiftool non trovato nel PATH.")

    result = subprocess.run(
        [exe, "-b", f"-{tag_name}", file_path],
        capture_output=True,
        check=True,
    )
    data = result.stdout
    return data if data else None
