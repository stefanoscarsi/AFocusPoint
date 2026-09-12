from PIL import Image

from core import geometry, overlay_renderer


def test_draw_af_points_colors_the_outline():
    img = Image.new("RGB", (100, 100), "black")
    box = geometry.Box(left=20, top=20, right=80, bottom=80)
    annotated = overlay_renderer.draw_af_points(img, [(box, overlay_renderer.COLOR_IN_FOCUS)])
    assert annotated.getpixel((50, 20)) == overlay_renderer.COLOR_IN_FOCUS
    # a pixel well inside the box (away from the center cross) is untouched
    assert annotated.getpixel((30, 30)) == (0, 0, 0)


def test_draw_af_points_uses_the_given_color_per_box():
    img = Image.new("RGB", (100, 100), "black")
    green_box = geometry.Box(10, 10, 30, 30)
    red_box = geometry.Box(60, 60, 80, 80)
    annotated = overlay_renderer.draw_af_points(
        img, [(green_box, overlay_renderer.COLOR_IN_FOCUS), (red_box, overlay_renderer.COLOR_PRIMARY)]
    )
    assert annotated.getpixel((20, 10)) == overlay_renderer.COLOR_IN_FOCUS
    assert annotated.getpixel((70, 60)) == overlay_renderer.COLOR_PRIMARY


def test_draw_af_points_draws_the_search_zone_underneath():
    img = Image.new("RGB", (100, 100), "black")
    search_zone = geometry.Box(0, 0, 100, 100)
    annotated = overlay_renderer.draw_af_points(img, [], search_zone_box=search_zone)
    assert annotated.getpixel((50, 0)) == overlay_renderer.COLOR_SEARCH_ZONE


def test_draw_af_points_with_no_boxes_and_no_search_zone_is_a_noop_copy():
    img = Image.new("RGB", (100, 100), "black")
    annotated = overlay_renderer.draw_af_points(img, [])
    assert annotated.getpixel((50, 50)) == (0, 0, 0)
    assert annotated is not img
