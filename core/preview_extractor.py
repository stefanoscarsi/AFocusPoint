"""
preview_extractor.py
---------------------
Estrae l'anteprima JPEG incorporata in un file CR3, evitando cosi' di
dover decodificare il RAW completo (molto piu' lento) solo per mostrare
l'immagine con il punto di messa a fuoco.

Un CR3 puo' contenere piu' anteprime a risoluzioni diverse. Proviamo in
ordine dalla piu' grande alla piu' piccola, cosi' l'overlay resta preciso
anche quando ingrandiamo l'immagine a schermo.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from .exif_reader import extract_binary_tag

# Ordine di priorita': dalla risoluzione piu' alta alla piu' bassa.
_PREVIEW_TAG_PRIORITY = ["JpgFromRaw", "PreviewImage", "ThumbnailImage"]


def extract_preview_image(file_path: str | Path) -> Image.Image:
    """
    Ritorna la migliore anteprima disponibile come oggetto PIL.Image.
    Solleva ValueError se nel file non e' presente nessuna anteprima
    (caso raro, ma possibile con impostazioni non standard).
    """
    last_error = None
    for tag in _PREVIEW_TAG_PRIORITY:
        try:
            data = extract_binary_tag(file_path, tag)
        except Exception as exc:  # noqa: BLE001 - vogliamo provare il tag successivo
            last_error = exc
            continue
        if data:
            try:
                return Image.open(io.BytesIO(data))
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                continue

    raise ValueError(
        f"Nessuna anteprima trovata in {file_path} "
        f"(provati i tag: {', '.join(_PREVIEW_TAG_PRIORITY)}). "
        f"Ultimo errore: {last_error}"
    )
