"""
af_parser.py
------------
Interpreta i metadati grezzi restituiti da ExifTool per ricavare:
  1. i "dati di scatto" (camera, obiettivo, esposizione...)
  2. i dati di autofocus (modalita' AF, punto/i usati, coordinate)

ATTENZIONE - LEGGERE PRIMA DELL'USO
------------------------------------
Canon NON pubblica la struttura dei MakerNotes. Il mapping dei tag usato
qui e' quello noto per le EOS R piu' recenti (R5, R6 II, R3), reverse-
engineered dalla community ExifTool. La EOS R6 Mark III e' uscita a
novembre 2025 ed e' MOLTO recente: e' possibile che alcuni tag abbiano
nomi diversi o non siano ancora mappati nella tua versione di ExifTool.

Per questo il modulo e' costruito in due livelli:
  - get_af_data_raw(): ritorna semplicemente TUTTI i tag il cui nome
    contiene "AF" o "Focus", senza alcuna assunzione. Usa questo se i
    campi strutturati sotto risultano vuoti sui tuoi file.
  - get_af_data_structured(): prova a interpretare i tag piu' comuni
    (vedi liste _AF_MODE_TAGS, _AF_AREA_TAGS, ecc.) in una struttura
    pulita. Se un tag non esiste, il campo corrispondente resta None
    invece di far fallire tutto.

Se dopo aver eseguito tools/inspect_tags.py sui tuoi CR3 scopri nomi di
tag diversi, aggiungili semplicemente alle liste qui sotto: il resto del
programma continuera' a funzionare.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Liste di possibili nomi di tag, in ordine di priorita' (dal piu' recente/
# specifico al piu' generico). Modificale liberamente dopo la calibrazione.
# ---------------------------------------------------------------------------

_AF_AREA_MODE_TAGS = ["Canon:AFAreaMode", "Canon:AFAreaModeSetting"]
_AF_NUM_POINTS_TAGS = ["Canon:NumAFPoints", "Canon:AFNumPoints"]
# ValidAFPoints indica QUANTI elementi delle liste sottostanti sono dati
# reali: il resto dell'array e' padding a zero. Scoperto essere ESSENZIALE
# testando su un file reale (R6 III): NumAFPoints puo' valere 1053 (l'intera
# griglia AF possibile) mentre ValidAFPoints=1 indica che solo il primo
# elemento della lista e' la zona di messa a fuoco effettiva.
_VALID_AF_POINTS_TAGS = ["Canon:ValidAFPoints"]
_AF_IMAGE_SIZE_TAGS = [("Canon:AFImageWidth", "Canon:AFImageHeight")]
_AF_POINTS_USED_TAGS = ["Canon:AFPointsSelected", "Canon:AFPointsUsed", "Canon:AFPointsUsed20"]
_AF_POINTS_IN_FOCUS_TAGS = ["Canon:AFPointsInFocus", "Canon:AFPointsInFocus20"]
_AF_X_POS_TAGS = ["Canon:AFAreaXPositions", "Canon:AFAreaXPositions1"]
_AF_Y_POS_TAGS = ["Canon:AFAreaYPositions", "Canon:AFAreaYPositions1"]
_AF_WIDTHS_TAGS = ["Canon:AFAreaWidths"]
_AF_HEIGHTS_TAGS = ["Canon:AFAreaHeights"]
_PRIMARY_AF_POINT_TAGS = ["Canon:PrimaryAFPoint"]
_FOCUS_MODE_TAGS = ["ExifIFD:FocusMode", "Canon:FocusMode", "MakerNotes:FocusMode"]
_SUBJECT_DETECTED_TAGS = ["Canon:SubjectToDetect", "Canon:EyeDetection", "Canon:SubjectArea", "Canon:DetectedFace"]


@dataclass
class ShootingData:
    """Dati di scatto principali, leggibili dall'utente."""

    camera_model: str | None = None
    lens: str | None = None
    date_time: str | None = None
    shutter_speed: str | None = None
    aperture: str | None = None
    iso: str | None = None
    focal_length: str | None = None
    exposure_mode: str | None = None
    metering_mode: str | None = None
    white_balance: str | None = None
    image_width: int | None = None
    image_height: int | None = None


@dataclass
class AFPoint:
    """Un singolo punto/area AF, in coordinate pixel gia' scalate."""

    x: float
    y: float
    width: float = 0.0
    height: float = 0.0
    in_focus: bool = False


@dataclass
class AFData:
    """Dati di autofocus strutturati."""

    af_area_mode: str | None = None
    af_area_mode_raw: int | None = None
    focus_mode: str | None = None
    num_points_used: int | None = None
    primary_point_index: int | None = None
    af_reference_width: int | None = None
    af_reference_height: int | None = None
    points: list[AFPoint] = field(default_factory=list)
    # Numero totale di aree AF candidate valutate dalla fotocamera in questa
    # modalita' (es. 189 in una Zone AF ampia): quasi sempre MOLTO maggiore
    # del numero di punti effettivamente confermati a fuoco in 'points'.
    # Utile da mostrare come contesto ("189 aree valutate, 1 confermata").
    candidate_area_count: int | None = None
    # (min_x, min_y, max_x, max_y) in pixel, area complessiva coperta da
    # TUTTE le zone candidate valutate (utile solo se sono piu' di una,
    # per dare contesto visivo sulla zona di ricerca/tracking).
    search_zone_bbox: tuple[float, float, float, float] | None = None
    subject_detection: str | None = None
    unresolved_tags: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Funzioni di supporto
# ---------------------------------------------------------------------------

def _first_present(d: dict, candidates: list[str]):
    """Ritorna il valore del primo tag tra 'candidates' presente in d."""
    for key in candidates:
        if key in d and d[key] not in (None, ""):
            return d[key]
    return None


def _as_list(value) -> list:
    """ExifTool a volte ritorna liste come stringa 'a b c' o come lista vera."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return value.replace(",", " ").split()
    return [value]


def _parse_index_list(value) -> set[int]:
    """
    Interpreta il valore GIA' FORMATTATO (leggibile) di tag come
    'AFPointsSelected' / 'AFPointsInFocus'. ExifTool decodifica da solo la
    bitmap binaria grezza (parole a 32 bit, non replicabile in modo
    affidabile a mano) in una stringa di indici separati da virgola, es.
    '0,1,2,...,188' oppure un singolo indice come '86', oppure '(none)'/'0'
    quando non c'e' nessun punto. Qui trasformiamo quella stringa in un
    insieme di interi, gli stessi indici usati per le liste di posizione.

    Scoperto testando su un file reale con Zone AF ampia (189 aree
    candidate): il tag grezzo (-n) di questi campi NON e' un array con un
    flag per posizione, ma un array di parole a 32 bit codificate a bit
    (es. '-1 -1 ... 8191 0 0...'): tentare di interpretarlo a mano avrebbe
    richiesto di replicare esattamente la logica interna di ExifTool.
    Molto piu' robusto usare l'interpretazione che ExifTool offre gia'.
    """
    if value is None:
        return set()
    text = str(value).strip()
    # NOTA: "0" e' un indice valido (il punto numero zero), NON significa
    # "nessuno" - solo "(none)"/stringa vuota lo significano. Verificato sul
    # file con singola area valida: 'AF Points Selected: 0' indica che
    # l'indice 0 e' quello selezionato, non l'assenza di selezione.
    if text in ("", "(none)", "None"):
        return set()
    result = set()
    for part in text.replace(";", ",").split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            result.add(int(part))
    return result


# Descrizioni leggibili delle modalita' AF (Canon AFAreaMode e' un codice
# numerico nel tag "raw"; questi valori sono quelli noti per le EOS R
# recenti - verificali con inspect_tags.py se qualcosa non torna).
_AF_AREA_MODE_DESCRIPTIONS = {
    0: "Punto singolo AF",
    1: "AF automatico (area intera)",
    2: "Spot AF",
    4: "AF area espansa",
    5: "Zona AF",
    6: "AF area grande (zona)",
    7: "Zona flessibile 1",
    8: "Zona flessibile 2",
    9: "Zona flessibile 3",
    10: "Area intera / tracking soggetto",
    11: "AF area espansa (attorno)",
}


# ---------------------------------------------------------------------------
# Estrazione dati di scatto
# ---------------------------------------------------------------------------

_COLOR_TEMPERATURE_TAGS = ["Canon:ColorTemperature"]
_WHITE_BALANCE_MODE_TAGS = ["Canon:WhiteBalance", "ExifIFD:WhiteBalance", "EXIF:WhiteBalance"]


def _white_balance_display(raw_metadata: dict, formatted_metadata: dict) -> str | None:
    """Prefers the actual Kelvin value used for the shot (Canon:ColorTemperature
    -- present regardless of WB mode: Auto, a preset like Daylight/Cloudy, or
    Manual Kelvin all populate it with whatever temperature was actually
    applied) over the WhiteBalance MODE name (e.g. "Auto", "Manual Temperature
    (Kelvin)"), which says how it was set but not what temperature resulted.
    Falls back to the mode name if no numeric temperature is available."""
    color_temp = _first_present(raw_metadata, _COLOR_TEMPERATURE_TAGS)
    if color_temp is not None:
        try:
            return f"{int(color_temp)} K"
        except (TypeError, ValueError):
            pass
    return _first_present(formatted_metadata, _WHITE_BALANCE_MODE_TAGS)


def get_shooting_data(raw_metadata: dict, formatted_metadata: dict) -> ShootingData:
    """
    Costruisce i dati di scatto a partire dai dizionari 'raw' (valori
    numerici grezzi) e 'formatted' (valori leggibili) restituiti da
    exif_reader.
    """
    # NOTA CALIBRAZIONE: verificato su un CR3 reale di R6 III che, con
    # raggruppamento -G1, ExifTool usa il gruppo "ExifIFD" (non "EXIF") per
    # i tag EXIF standard, e "IFD0"/"Composite" per altri. Le liste sotto
    # riflettono i nomi REALI confermati, con qualche alternativa di
    # fallback per robustezza su altri corpi macchina/versioni.
    d = formatted_metadata
    width = _first_present(
        d, ["ExifIFD:ExifImageWidth", "IFD0:ImageWidth", "File:ImageWidth", "Composite:ImageWidth"]
    )
    height = _first_present(
        d, ["ExifIFD:ExifImageHeight", "IFD0:ImageHeight", "File:ImageHeight", "Composite:ImageHeight"]
    )

    return ShootingData(
        camera_model=_first_present(d, ["IFD0:Model", "EXIF:Model", "Canon:Model"]),
        lens=_first_present(d, ["Composite:LensID", "ExifIFD:LensModel", "Canon:LensType"]),
        date_time=_first_present(d, ["ExifIFD:DateTimeOriginal", "EXIF:DateTimeOriginal"]),
        shutter_speed=_first_present(d, ["ExifIFD:ExposureTime", "Composite:ShutterSpeed", "EXIF:ExposureTime"]),
        aperture=_first_present(d, ["ExifIFD:FNumber", "Composite:Aperture", "EXIF:FNumber"]),
        iso=_first_present(d, ["ExifIFD:ISO", "EXIF:ISO"]),
        focal_length=_first_present(d, ["ExifIFD:FocalLength", "EXIF:FocalLength"]),
        exposure_mode=_first_present(d, ["ExifIFD:ExposureProgram", "Canon:CanonExposureMode", "EXIF:ExposureProgram"]),
        metering_mode=_first_present(d, ["ExifIFD:MeteringMode", "Canon:MeteringMode", "EXIF:MeteringMode"]),
        white_balance=_white_balance_display(raw_metadata, d),
        image_width=int(width) if width else None,
        image_height=int(height) if height else None,
    )


# ---------------------------------------------------------------------------
# Estrazione dati AF
# ---------------------------------------------------------------------------

def get_af_data_raw(raw_metadata: dict) -> dict:
    """
    Ritorna, senza alcuna interpretazione, tutti i tag il cui nome
    contiene 'AF' o 'Focus'. Utile per la calibrazione / debug quando la
    struttura di questa specifica fotocamera non e' ancora mappata sotto.
    """
    result = {}
    for key, value in raw_metadata.items():
        tag_name = key.split(":")[-1]
        if "AF" in tag_name or "Focus" in tag_name:
            result[key] = value
    return result


def get_af_data_structured(raw_metadata: dict, formatted_metadata: dict) -> AFData:
    """
    Tenta di interpretare i tag AF piu' comuni in una struttura pulita e
    pronta per essere disegnata sull'immagine. Ogni campo che non trova
    corrispondenza resta None/vuoto, senza sollevare eccezioni: in questo
    modo l'app resta utilizzabile anche a fronte di un mapping incompleto.
    """
    raw = raw_metadata
    fmt = formatted_metadata

    af_area_mode_raw = _first_present(raw, _AF_AREA_MODE_TAGS)
    af_area_mode_raw_int = int(af_area_mode_raw) if af_area_mode_raw is not None else None
    af_area_mode_desc = (
        _AF_AREA_MODE_DESCRIPTIONS.get(af_area_mode_raw_int)
        if af_area_mode_raw_int is not None
        else None
    )
    # Se ExifTool ha gia' una descrizione testuale nel dizionario 'formatted',
    # preferiamola (piu' affidabile della nostra tabella statica).
    af_area_mode_formatted = _first_present(fmt, _AF_AREA_MODE_TAGS)
    if af_area_mode_formatted and not str(af_area_mode_formatted).isdigit():
        af_area_mode_desc = str(af_area_mode_formatted)

    ref_w_h = None
    for w_key, h_key in _AF_IMAGE_SIZE_TAGS:
        if w_key in raw and h_key in raw:
            ref_w_h = (int(raw[w_key]), int(raw[h_key]))
            break

    x_positions = _as_list(_first_present(raw, _AF_X_POS_TAGS))
    y_positions = _as_list(_first_present(raw, _AF_Y_POS_TAGS))
    widths = _as_list(_first_present(raw, _AF_WIDTHS_TAGS))
    heights = _as_list(_first_present(raw, _AF_HEIGHTS_TAGS))

    # Tronchiamo alle sole voci REALI indicate da ValidAFPoints: il resto
    # dell'array e' padding a zero e andrebbe altrimenti disegnato come
    # decine/centinaia di punti fantasma tutti sovrapposti al centro.
    valid_count_raw = _first_present(raw, _VALID_AF_POINTS_TAGS)
    if valid_count_raw is not None:
        valid_count = int(valid_count_raw)
        x_positions = x_positions[:valid_count]
        y_positions = y_positions[:valid_count]

    # ATTENZIONE (bug scoperto testando su un file con Zone AF ampia):
    # 'AFAreaXPositions/YPositions/Widths/Heights' elencano TUTTE le aree
    # CANDIDATE valutate dalla fotocamera (es. 189 in una griglia estesa),
    # non solo quella a fuoco. Per sapere quale, tra queste, ha davvero
    # raggiunto il fuoco, serve incrociare con 'AFPointsInFocus' - ma la sua
    # rappresentazione grezza (-n) e' una bitmap binaria packed a 32 bit non
    # affidabilmente decodificabile a mano. Usiamo invece la stringa GIA'
    # decodificata da ExifTool (es. '86', o '0,1,2,...,188', o '(none)').
    selected_indices = _parse_index_list(_first_present(fmt, _AF_POINTS_USED_TAGS))
    focus_indices = _parse_index_list(_first_present(fmt, _AF_POINTS_IN_FOCUS_TAGS))

    if not focus_indices:
        if len(x_positions) == 1:
            # Caso semplice (visto su scatti one-shot/zona con 1 sola area
            # valida): nessun indice esplicito confermato, ma essendoci
            # un'unica area candidata e' inequivocabilmente quella usata.
            focus_indices = {0}
        elif len(selected_indices) == 1:
            focus_indices = selected_indices
        # Se restano piu' candidati senza una conferma esplicita (raro),
        # NON indoviniamo: points restera' vuoto e lo segnaliamo in UI
        # invece di disegnare un punto potenzialmente sbagliato.

    points: list[AFPoint] = []
    candidate_xy: list[tuple[float, float]] = []  # per il bbox della zona di ricerca
    if ref_w_h and x_positions and y_positions:
        ref_w, ref_h = ref_w_h

        for idx, (x_off, y_off) in enumerate(zip(x_positions, y_positions)):
            try:
                x_off_f, y_off_f = float(x_off), float(y_off)
            except (TypeError, ValueError):
                continue
            # Le coordinate Canon sono offset dal CENTRO dell'area AF di
            # riferimento (non dall'angolo in alto a sx), MA con convenzione
            # matematica: Y positivo = verso l'ALTO. Le immagini invece hanno
            # Y positivo verso il basso (origine in alto a sx) -> l'asse Y va
            # invertito. Bug reale scoperto testando su una foto vera: senza
            # questo meno, il marcatore cadeva sistematicamente nella parte
            # SOPRA il soggetto reale invece che sopra di esso.
            px = ref_w / 2 + x_off_f
            py = ref_h / 2 - y_off_f
            candidate_xy.append((px, py))

            if idx not in focus_indices:
                continue  # disegniamo solo le aree CONFERMATE a fuoco

            w = float(widths[idx]) if idx < len(widths) else ref_w * 0.03
            h = float(heights[idx]) if idx < len(heights) else ref_h * 0.03
            points.append(AFPoint(x=px, y=py, width=w, height=h, in_focus=True))

    search_zone_bbox = None
    if len(candidate_xy) > 1:
        xs = [p[0] for p in candidate_xy]
        ys = [p[1] for p in candidate_xy]
        search_zone_bbox = (min(xs), min(ys), max(xs), max(ys))

    primary_point = _first_present(raw, _PRIMARY_AF_POINT_TAGS)
    focus_mode = _first_present(fmt, _FOCUS_MODE_TAGS)
    subject_detection = _first_present(fmt, _SUBJECT_DETECTED_TAGS)

    return AFData(
        af_area_mode=af_area_mode_desc,
        af_area_mode_raw=af_area_mode_raw_int,
        focus_mode=focus_mode,
        num_points_used=len(points) or None,
        primary_point_index=int(primary_point) if primary_point is not None else None,
        af_reference_width=ref_w_h[0] if ref_w_h else None,
        af_reference_height=ref_w_h[1] if ref_w_h else None,
        points=points,
        candidate_area_count=len(candidate_xy) or None,
        search_zone_bbox=search_zone_bbox,
        subject_detection=subject_detection,
        unresolved_tags=get_af_data_raw(raw) if not points else {},
    )
