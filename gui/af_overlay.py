"""Draws the AF boxes on top of the photo in the QGraphicsScene.

The boxes are scene items rather than pixels painted into the photo, and
their pens are "cosmetic": the line width is in screen pixels, not photo
pixels, so the square stays equally visible at every zoom level. Painted
into a several-thousand-pixel-wide preview, a thin line all but disappears
once the photo is scaled down to fit the window.

Colors:
  - verde = punto/area effettivamente a fuoco
  - rosso = punto primario (primary_point_index), se identificabile
  - blu (sottile) = zona di ricerca complessiva (contesto)
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPathItem, QGraphicsRectItem

from core import geometry
from core.frame_builder import FrameResult

COLOR_IN_FOCUS = QColor(0, 230, 0)
COLOR_PRIMARY = QColor(255, 40, 40)
COLOR_SEARCH_ZONE = QColor(0, 160, 255)

# All widths are in screen pixels (cosmetic pens).
LINE_WIDTH = 2
SEARCH_ZONE_LINE_WIDTH = 1
# A dark outline (2 px wider) under each colored line, so a green square
# stays readable over green vegetation or a bright sky.
HALO_COLOR = QColor(0, 0, 0, 140)
# Half-length of the arms of the center cross, in screen pixels.
CROSS_ARM = 6

# Above the photo (z = 0); halos under their colored lines.
_Z_HALO = 1
_Z_LINE = 2


def _pen(color: QColor, width: float) -> QPen:
    pen = QPen(color, width)
    pen.setCosmetic(True)
    pen.setJoinStyle(Qt.MiterJoin)
    return pen


def _rect(box: geometry.Box) -> QRectF:
    return QRectF(box.left, box.top, box.right - box.left, box.bottom - box.top)


def _rect_items(box: geometry.Box, color: QColor, width: float) -> list[QGraphicsItem]:
    items: list[QGraphicsItem] = []
    for pen, z in ((_pen(HALO_COLOR, width + 2), _Z_HALO), (_pen(color, width), _Z_LINE)):
        item = QGraphicsRectItem(_rect(box))
        item.setPen(pen)
        item.setZValue(z)
        items.append(item)
    return items


def _cross_items(box: geometry.Box, color: QColor) -> list[QGraphicsItem]:
    # ItemIgnoresTransformations keeps the cross a fixed size on screen
    # (its path is in screen pixels around pos), like the line widths.
    path = QPainterPath()
    path.moveTo(-CROSS_ARM, 0)
    path.lineTo(CROSS_ARM, 0)
    path.moveTo(0, -CROSS_ARM)
    path.lineTo(0, CROSS_ARM)
    center_x = (box.left + box.right) / 2
    center_y = (box.top + box.bottom) / 2

    items: list[QGraphicsItem] = []
    for pen, z in ((_pen(HALO_COLOR, LINE_WIDTH + 2), _Z_HALO), (_pen(color, LINE_WIDTH), _Z_LINE)):
        item = QGraphicsPathItem(path)
        item.setPen(pen)
        item.setPos(center_x, center_y)
        item.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        item.setZValue(z)
        items.append(item)
    return items


def build_items(result: FrameResult) -> list[QGraphicsItem]:
    """All the overlay items for one photo, in scene (= photo pixel)
    coordinates, ready to be added to the scene holding that photo."""
    items: list[QGraphicsItem] = []
    if result.search_zone_box is not None:
        items += _rect_items(result.search_zone_box, COLOR_SEARCH_ZONE, SEARCH_ZONE_LINE_WIDTH)
    for af_box in result.af_boxes:
        color = COLOR_PRIMARY if af_box.is_primary else COLOR_IN_FOCUS
        items += _rect_items(af_box.box, color, LINE_WIDTH)
        items += _cross_items(af_box.box, color)
    return items
