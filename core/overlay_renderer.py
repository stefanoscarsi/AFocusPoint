"""Draws pre-computed boxes on top of the (already oriented/cropped) preview.

Coordinate computation lives in frame_builder.py / geometry.py -- this module
only knows how to paint geometry.Box rectangles in given colors. Keeping it
this "dumb" makes it trivial to test without needing real AF metadata.

Colors:
  - verde  = punto/area effettivamente a fuoco
  - rosso  = punto primario (primary_point_index), se identificabile
  - blu (tratteggio sottile) = zona di ricerca complessiva (contesto)
  - blu (bordo pieno) = area della foto risultata piu' nitida nel confronto
"""
from __future__ import annotations

from PIL import Image, ImageDraw

from . import geometry

COLOR_IN_FOCUS = (0, 230, 0)
COLOR_PRIMARY = (255, 40, 40)
COLOR_SEARCH_ZONE = (0, 160, 255)
COLOR_SHARPEST = (0, 140, 255)
LINE_WIDTH = 3


def draw_af_points(
    image: Image.Image,
    boxes: list[tuple[geometry.Box, tuple[int, int, int]]],
    search_zone_box: geometry.Box | None = None,
) -> Image.Image:
    """Returns a COPY of `image` with the given (box, color) pairs drawn as
    rectangles with a center cross, plus an optional search-zone rectangle
    (drawn first/underneath, thin outline, shown as context when the camera
    evaluated multiple candidate areas)."""
    result = image.convert("RGB").copy()
    draw = ImageDraw.Draw(result)

    if search_zone_box is not None:
        draw.rectangle(
            [search_zone_box.left, search_zone_box.top, search_zone_box.right, search_zone_box.bottom],
            outline=COLOR_SEARCH_ZONE,
            width=1,
        )

    for box, color in boxes:
        draw.rectangle([box.left, box.top, box.right, box.bottom], outline=color, width=LINE_WIDTH)
        cx = (box.left + box.right) / 2
        cy = (box.top + box.bottom) / 2
        draw.line([cx - 6, cy, cx + 6, cy], fill=color, width=LINE_WIDTH)
        draw.line([cx, cy - 6, cx, cy + 6], fill=color, width=LINE_WIDTH)

    return result


def draw_sharp_box(image: Image.Image, box: geometry.Box) -> Image.Image:
    """Marks the photo's actual sharpest region (per sharpness.find_sharpest_tile)
    in a color distinct from the AF box colors, so the user can compare them."""
    annotated = image.copy()
    draw = ImageDraw.Draw(annotated)
    draw.rectangle([box.left, box.top, box.right, box.bottom], outline=COLOR_SHARPEST, width=LINE_WIDTH)
    return annotated
