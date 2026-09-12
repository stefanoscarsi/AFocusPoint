from PIL import Image, ImageDraw

from core import geometry, sharpness


def _flat_image(size=(100, 100), color=128):
    return Image.new("L", size, color).convert("RGB")


def _image_with_sharp_patch(size=(200, 200), patch_box=(80, 80, 120, 120)):
    """A flat grey image with a black/white checkerboard patch in one spot --
    that patch should score far higher than the rest of the (textureless)
    image."""
    img = Image.new("RGB", size, (128, 128, 128))
    draw = ImageDraw.Draw(img)
    left, top, right, bottom = patch_box
    step = 4
    for y in range(top, bottom, step):
        for x in range(left, right, step):
            if ((x - left) // step + (y - top) // step) % 2 == 0:
                draw.rectangle([x, y, x + step, y + step], fill=(255, 255, 255))
            else:
                draw.rectangle([x, y, x + step, y + step], fill=(0, 0, 0))
    return img


def test_region_sharpness_is_zero_on_a_flat_region():
    img = _flat_image()
    box = geometry.Box(10, 10, 90, 90)
    assert sharpness.region_sharpness(img, box) == 0.0


def test_region_sharpness_is_positive_on_a_textured_region():
    img = _image_with_sharp_patch()
    box = geometry.Box(80, 80, 120, 120)
    score = sharpness.region_sharpness(img, box)
    assert score is not None
    assert score > 0.0


def test_region_sharpness_returns_none_for_a_tiny_box():
    img = _flat_image()
    box = geometry.Box(10, 10, 12, 12)
    assert sharpness.region_sharpness(img, box) is None


def test_region_sharpness_clamps_a_box_that_overflows_image_bounds():
    img = _flat_image((100, 100))
    box = geometry.Box(-50, -50, 150, 150)
    # Should not raise, and a clamped flat region still scores zero.
    assert sharpness.region_sharpness(img, box) == 0.0


def test_find_sharpest_tile_locates_the_textured_patch():
    img = _image_with_sharp_patch(size=(200, 200), patch_box=(80, 80, 120, 120))
    box, score = sharpness.find_sharpest_tile(img, tile_size=40)
    assert score > 0.0
    # The winning tile must at least overlap the planted textured patch.
    assert box.left < 120 and box.right > 80
    assert box.top < 120 and box.bottom > 80


def test_find_sharpest_tile_on_a_fully_flat_image_scores_zero():
    img = _flat_image((120, 120))
    box, score = sharpness.find_sharpest_tile(img, tile_size=40)
    assert score == 0.0
    assert box.right > box.left and box.bottom > box.top
