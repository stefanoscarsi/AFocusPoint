from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem

from core import af_parser, geometry
from core.frame_builder import AFBox, FrameResult
from gui import af_overlay


def _result(af_boxes=(), search_zone_box=None):
    return FrameResult(
        image=None,
        shooting=af_parser.ShootingData(),
        af_data=af_parser.AFData(),
        af_boxes=list(af_boxes),
        search_zone_box=search_zone_box,
    )


def _colored_rects(items):
    return [i for i in items if isinstance(i, QGraphicsRectItem) and i.zValue() == af_overlay._Z_LINE]


def test_af_box_is_drawn_at_its_photo_coordinates():
    items = af_overlay.build_items(_result([AFBox(geometry.Box(100, 200, 300, 500), is_primary=False)]))
    (rect,) = _colored_rects(items)
    r = rect.rect()
    assert (r.left(), r.top(), r.right(), r.bottom()) == (100, 200, 300, 500)
    assert rect.pen().color() == af_overlay.COLOR_IN_FOCUS


def test_every_line_keeps_a_fixed_on_screen_width_at_any_zoom():
    items = af_overlay.build_items(
        _result([AFBox(geometry.Box(0, 0, 10, 10), is_primary=True)], search_zone_box=geometry.Box(0, 0, 50, 50))
    )
    assert items
    assert all(item.pen().isCosmetic() for item in items)


def test_center_cross_keeps_a_fixed_on_screen_size():
    items = af_overlay.build_items(_result([AFBox(geometry.Box(0, 0, 10, 10), is_primary=False)]))
    crosses = [i for i in items if i.flags() & QGraphicsItem.ItemIgnoresTransformations]
    assert crosses
    assert all((c.pos().x(), c.pos().y()) == (5, 5) for c in crosses)


def test_primary_point_is_red_and_search_zone_is_blue():
    items = af_overlay.build_items(
        _result([AFBox(geometry.Box(0, 0, 10, 10), is_primary=True)], search_zone_box=geometry.Box(0, 0, 50, 50))
    )
    colors = {rect.pen().color().name() for rect in _colored_rects(items)}
    assert colors == {af_overlay.COLOR_PRIMARY.name(), af_overlay.COLOR_SEARCH_ZONE.name()}


def test_no_af_data_means_no_overlay():
    assert af_overlay.build_items(_result()) == []
