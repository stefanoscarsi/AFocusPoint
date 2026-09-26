#!/usr/bin/env python3
"""
Punto di ingresso dell'app: AFocusPoint.
Avvio: python3 main.py
Avvio con un file gia' aperto: python3 main.py "percorso/foto.CR3"
(e' questo il meccanismo usato da Windows/DxO PhotoLab quando l'app viene
aperta tramite "Apri con..." o come editor esterno: il sistema operativo
passa il percorso del file come argomento da riga di comando).

Su macOS invece il Finder ("Apri con...", doppio click, trascinamento sull'
icona nel Dock) NON passa il file come argomento: manda all'app un evento
di apertura file (QFileOpenEvent), gestito da AFocusPointApp qui sotto.
"""

import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QTimer
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


class AFocusPointApp(QApplication):
    """
    Riceve i file aperti dal Finder su macOS. L'evento puo' arrivare sia
    all'avvio (l'app e' stata lanciata PER aprire quel file) sia con l'app
    gia' aperta (in quel caso si carica la nuova foto nella stessa
    finestra). Su Windows questo evento non arriva mai: li' il file passa
    da sys.argv, gestito in main().
    """

    def __init__(self, argv: list[str]):
        super().__init__(argv)
        self._window: MainWindow | None = None
        self._pending_file: str | None = None

    def set_window(self, window: MainWindow) -> None:
        self._window = window
        if self._pending_file:
            self._open_file(self._pending_file)
            self._pending_file = None

    def event(self, event) -> bool:  # noqa: N802 - override Qt
        if event.type() == QEvent.FileOpen:
            if self._window is None:
                self._pending_file = event.file()
            else:
                self._open_file(event.file())
            return True
        return super().event(event)

    def _open_file(self, file_path: str) -> None:
        window = self._window
        window.raise_()
        window.activateWindow()
        # Rimandato al ciclo eventi, come per sys.argv in main(): load_file
        # puo' mostrare una finestra di errore, che non va aperta mentre Qt
        # sta ancora consegnando questo evento.
        QTimer.singleShot(0, lambda: window.load_file(file_path))


def main() -> None:
    app = AFocusPointApp(sys.argv)

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
    app.set_window(window)

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
