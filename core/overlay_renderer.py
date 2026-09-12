"""
overlay_renderer.py
--------------------
Disegna i punti/le aree AF sopra l'immagine di anteprima.

Le coordinate in AFData.points sono espresse rispetto al sistema di
riferimento "AF" della fotocamera (af_reference_width/height), che quasi
sempre corrisponde alla risoluzione massima dell'immagine ma va comunque
riscalato sulla risoluzione reale dell'anteprima mostrata a schermo.

Colori:
  - verde  = punto/area effettivamente a fuoco (in_focus=True)
  - giallo = punto/area selezionato ma non necessariamente a fuoco
  - rosso  = punto primario (primary_point_index), se identificabile
"""

from __future__ import annotations

from PIL import Image, ImageDraw

from .af_parser import AFData

_COLOR_IN_FOCUS = (0, 230, 0)
_COLOR_SELECTED = (255, 210, 0)
_COLOR_PRIMARY = (255, 40, 40)
_COLOR_SEARCH_ZONE = (0, 160, 255)
_LINE_WIDTH = 3


def draw_af_overlay(preview: Image.Image, af_data: AFData) -> Image.Image:
    """
    Ritorna una COPIA dell'immagine 'preview' con sovrapposti i marcatori
    AF. L'immagine originale non viene modificata.
    """
    if not af_data.points and not af_data.search_zone_bbox:
        return preview.copy()

    result = preview.convert("RGB").copy()
    draw = ImageDraw.Draw(result)

    prev_w, prev_h = result.size
    ref_w = af_data.af_reference_width or prev_w
    ref_h = af_data.af_reference_height or prev_h
    scale_x = prev_w / ref_w
    scale_y = prev_h / ref_h

    # Zona di ricerca complessiva (contesto): disegnata SOTTO ai marcatori
    # di fuoco, con un tratteggio leggero, solo quando esistono piu' aree
    # candidate (es. Zone AF ampia con decine/centinaia di sotto-aree).
    if af_data.search_zone_bbox:
        min_x, min_y, max_x, max_y = af_data.search_zone_bbox
        box = [min_x * scale_x, min_y * scale_y, max_x * scale_x, max_y * scale_y]
        draw.rectangle(box, outline=_COLOR_SEARCH_ZONE, width=1)

    for idx, point in enumerate(af_data.points):
        cx = point.x * scale_x
        cy = point.y * scale_y
        half_w = max(point.width * scale_x / 2, 8)
        half_h = max(point.height * scale_y / 2, 8)

        color = _COLOR_SELECTED
        if point.in_focus:
            color = _COLOR_IN_FOCUS
        if af_data.primary_point_index is not None and idx == af_data.primary_point_index:
            color = _COLOR_PRIMARY

        box = [cx - half_w, cy - half_h, cx + half_w, cy + half_h]
        draw.rectangle(box, outline=color, width=_LINE_WIDTH)
        # Crocino centrale per individuare il punto anche su aree molto grandi
        draw.line([cx - 6, cy, cx + 6, cy], fill=color, width=_LINE_WIDTH)
        draw.line([cx, cy - 6, cx, cy + 6], fill=color, width=_LINE_WIDTH)

    return result
