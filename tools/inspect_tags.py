#!/usr/bin/env python3
"""
inspect_tags.py — strumento di CALIBRAZIONE, da eseguire per primo.
=====================================================================

Uso:
    python3 tools/inspect_tags.py /percorso/a/una/foto.CR3

Cosa fa:
  1. Stampa a schermo TUTTI i tag Canon/AF/Focus trovati nel file
     (raggruppati e ordinati), cosi' puoi verificare quali esistono
     davvero per la tua R6 Mark III con la tua versione di ExifTool.
  2. Salva lo stesso output in un file .txt accanto alla foto, per
     confrontarlo facilmente tra scatti con modalita' AF diverse
     (punto singolo, zona, tracking soggetto...).

Perche' serve: Canon non documenta ufficialmente questi tag, e la R6
Mark III (nov. 2025) e' troppo recente perche' esista una mappatura
certa e stabile. Questo script sostituisce le ipotesi con dati reali:
usa il suo output per correggere le liste in core/af_parser.py se i
campi mostrati dall'app risultano vuoti o sbagliati.

Suggerimento: scatta la STESSA inquadratura con almeno 3 modalita' AF
diverse (1 punto, zona, tracking soggetto/occhio) e confronta gli
output: i tag che CAMBIANO tra uno scatto e l'altro sono quelli che
contengono davvero la posizione del fuoco.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.exif_reader import check_exiftool_available, read_all_metadata  # noqa: E402


def _print_and_collect(title: str, items: dict, lines: list[str]) -> None:
    lines.append(f"\n=== {title} ({len(items)} tag) ===")
    print(f"\n=== {title} ({len(items)} tag) ===")
    for key in sorted(items):
        line = f"{key} = {items[key]}"
        lines.append(line)
        print(line)


def inspect(file_path: str) -> None:
    path = Path(file_path)
    if not path.exists():
        print(f"File non trovato: {path}")
        sys.exit(1)

    version = check_exiftool_available()
    print(f"ExifTool versione: {version}")
    if tuple(int(p) for p in version.split(".")[:2]) < (13, 0):
        print(
            "⚠ ATTENZIONE: stai usando una versione di ExifTool piuttosto "
            "datata. Per un corpo macchina uscito a novembre 2025 come la "
            "R6 Mark III, scarica l'ultima versione da https://exiftool.org "
            "per avere il mapping dei tag Canon piu' aggiornato possibile."
        )

    metadata = read_all_metadata(path)
    raw = metadata["raw"]
    formatted = metadata["formatted"]

    output_lines = [f"File analizzato: {path}", f"ExifTool versione: {version}"]

    # Tutti i tag del gruppo Canon (MakerNotes)
    canon_tags = {k: v for k, v in formatted.items() if k.startswith("Canon:")}
    _print_and_collect("Tutti i tag Canon (MakerNotes)", canon_tags, output_lines)

    # Solo quelli che contengono "AF" o "Focus" nel nome, valori grezzi (-n)
    af_tags_raw = {
        k: v for k, v in raw.items() if "AF" in k.split(":")[-1] or "Focus" in k.split(":")[-1]
    }
    _print_and_collect("Tag AF/Focus — valori GREZZI (-n)", af_tags_raw, output_lines)

    # Stessi tag ma con valori formattati/leggibili
    af_tags_formatted = {
        k: v for k, v in formatted.items() if "AF" in k.split(":")[-1] or "Focus" in k.split(":")[-1]
    }
    _print_and_collect("Tag AF/Focus — valori FORMATTATI", af_tags_formatted, output_lines)

    out_path = path.with_suffix(".tags.txt")
    try:
        out_path.write_text("\n".join(output_lines), encoding="utf-8")
        print(f"\n✅ Output salvato anche in: {out_path}")
    except OSError:
        # La cartella del file potrebbe essere di sola lettura (es. cartelle
        # di upload/condivisione): scriviamo nella cartella corrente invece
        # di far fallire l'intera analisi gia' stampata sopra.
        fallback_path = Path.cwd() / f"{path.stem}.tags.txt"
        fallback_path.write_text("\n".join(output_lines), encoding="utf-8")
        print(
            f"\n⚠ La cartella del file è di sola lettura: salvato invece in "
            f"{fallback_path}"
        )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python3 tools/inspect_tags.py /percorso/a/foto.CR3")
        sys.exit(1)
    inspect(sys.argv[1])
