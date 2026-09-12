"""
info_panel.py
-------------
Pannello laterale con due sezioni:
  - Dati di scatto (camera, esposizione, obiettivo...)
  - Dati di autofocus (modalita', punti usati, punto primario...)
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QLabel, QVBoxLayout, QWidget

from core.af_parser import AFData, ShootingData


def _row(label: str, value) -> str:
    value_str = "—" if value in (None, "") else str(value)
    return f"<b>{label}:</b> {value_str}"


class InfoPanel(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)

        self.shooting_box = QGroupBox("Dati di scatto")
        self.shooting_label = QLabel("Apri un file CR3 per vedere i dati.")
        self.shooting_label.setTextFormat(Qt.RichText)
        self.shooting_label.setWordWrap(True)
        shooting_layout = QVBoxLayout()
        shooting_layout.addWidget(self.shooting_label)
        self.shooting_box.setLayout(shooting_layout)

        self.af_box = QGroupBox("Autofocus")
        self.af_label = QLabel("—")
        self.af_label.setTextFormat(Qt.RichText)
        self.af_label.setWordWrap(True)
        af_layout = QVBoxLayout()
        af_layout.addWidget(self.af_label)
        self.af_box.setLayout(af_layout)

        self.warning_label = QLabel("")
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet("color: #b35c00;")

        layout.addWidget(self.shooting_box)
        layout.addWidget(self.af_box)
        layout.addWidget(self.warning_label)
        layout.addStretch(1)

    def update_data(self, shooting: ShootingData, af: AFData) -> None:
        shooting_lines = [
            _row("Fotocamera", shooting.camera_model),
            _row("Obiettivo", shooting.lens),
            _row("Data/ora", shooting.date_time),
            _row("Otturatore", shooting.shutter_speed),
            _row("Apertura", shooting.aperture),
            _row("ISO", shooting.iso),
            _row("Focale", shooting.focal_length),
            _row("Esposizione", shooting.exposure_mode),
            _row("Misurazione", shooting.metering_mode),
            _row("Bilanciamento del bianco", shooting.white_balance),
            _row("Risoluzione", f"{shooting.image_width} x {shooting.image_height}"
                 if shooting.image_width else None),
        ]
        self.shooting_label.setText("<br>".join(shooting_lines))

        af_lines = [
            _row("Modalita' area AF", af.af_area_mode),
            _row("Modalita' focus (One-Shot/Servo)", af.focus_mode),
            _row("Aree candidate valutate", af.candidate_area_count),
            _row("Punti confermati a fuoco", af.num_points_used),
            _row("Rilevamento soggetto", af.subject_detection),
        ]
        self.af_label.setText("<br>".join(af_lines))

        if not af.points:
            if af.candidate_area_count and af.candidate_area_count > 1:
                self.warning_label.setText(
                    "⚠ La fotocamera ha valutato piu' aree candidate ma questo "
                    "file non specifica quale abbia raggiunto la conferma di "
                    "fuoco. Mostrata solo la zona di ricerca complessiva "
                    "(rettangolo blu), non un punto preciso."
                )
            else:
                self.warning_label.setText(
                    "⚠ Nessuna coordinata AF interpretata con il mapping attuale.\n"
                    "Esegui tools/inspect_tags.py su questo file per vedere i tag "
                    "grezzi disponibili e aggiornare core/af_parser.py di conseguenza."
                )
        else:
            self.warning_label.setText("")
