#!/usr/bin/env python3
"""
Punto di ingresso dell'app: AFocusPoint.
Avvio: python3 main.py
Avvio con un file gia' aperto: python3 main.py "percorso/foto.CR3"
(e' questo il meccanismo usato da Windows/DxO PhotoLab quando l'app viene
aperta tramite "Apri con..." o come editor esterno: il sistema operativo
passa il percorso del file come argomento da riga di comando).
"""

import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow


def resource_path(relative_path: str) -> Path:
    """
    Risolve il percorso di una risorsa (es. l'icona) sia quando il
    programma gira dai sorgenti, sia quando e' impacchettato con
    PyInstaller: in quel caso i file aggiunti con --add-data vengono
    estratti in una cartella temporanea indicata da sys._MEIPASS, diversa
    dalla cartella del progetto.
    """
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative_path


def main() -> None:
    app = QApplication(sys.argv)

    # Icona dell'applicazione: usata nella barra del titolo, nella barra
    # delle applicazioni (taskbar) e nel dock (Mac) MENTRE il programma e'
    # in esecuzione. E' una cosa diversa dall'icona del file .exe stesso
    # (quella impostata con --icon in PyInstaller, visibile in Esplora
    # File): senza questa riga, la finestra mostrava l'icona generica di
    # Python/Qt anche a build riuscita.
    icon_path = resource_path("assets/icon.png")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow()
    window.show()

    # Se l'app e' stata avviata da "Apri con..." (Esplora File, DxO
    # PhotoLab come editor esterno, ecc.), il sistema operativo passa il
    # percorso del file come primo argomento: PRIMA questo veniva ignorato
    # del tutto, motivo per cui l'app si apriva ma la foto non compariva
    # mai. QTimer.singleShot(0, ...) rimanda il caricamento al primo giro
    # del ciclo eventi, cosi' la finestra appare subito e poi la foto si
    # carica, invece di bloccare l'avvio.
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        QTimer.singleShot(0, lambda: window.load_file(file_path))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
