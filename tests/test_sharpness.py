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


# --- best_tile_score: same-granularity scoring for a fixed box ------------


def test_best_tile_score_finds_the_sharpest_patch_within_a_large_box():
    """A box big enough to contain several tiles must be scored by its
    sharpest sub-tile, not by averaging the whole (mostly flat) box --
    otherwise it's not comparable to find_sharpest_nearby_tile's own
    per-tile scores."""
    img = _image_with_sharp_patch(size=(300, 300), patch_box=(200, 200, 240, 240))
    box = geometry.Box(0, 0, 300, 300)
    whole_box_avg = sharpness.region_sharpness(img, box)
    best_patch = sharpness.best_tile_score(img, box, tile_size=40)
    assert best_patch > whole_box_avg


def test_best_tile_score_falls_back_to_whole_region_when_too_small_to_tile():
    img = _image_with_sharp_patch(size=(60, 60), patch_box=(0, 0, 60, 60))
    box = geometry.Box(0, 0, 60, 60)
    # Smaller than tile_size -- can't subdivide, must still return a score.
    score = sharpness.best_tile_score(img, box, tile_size=100)
    assert score is not None
    assert score == sharpness.region_sharpness(img, box)


def test_best_tile_score_returns_none_for_a_tiny_box():
    img = _flat_image()
    box = geometry.Box(10, 10, 12, 12)
    assert sharpness.best_tile_score(img, box, tile_size=40) is None


# --- find_sharpest_nearby_tile: local, not whole-frame, search ------------


def test_find_sharpest_nearby_tile_ignores_a_distant_unrelated_patch():
    """A textured patch far from the reference box must NOT be picked up --
    this is the whole point of restricting the search to a neighbourhood
    (confirmed on real photos: a whole-frame search kept surfacing unrelated
    background clutter far from the actual subject)."""
    img = _image_with_sharp_patch(size=(1000, 1000), patch_box=(900, 900, 940, 940))
    reference_box = geometry.Box(90, 90, 110, 110)  # far from the patch

    box, score = sharpness.find_sharpest_nearby_tile(
        img, reference_box, radius_factor=6, tile_size=20
    )

    assert score == 0.0  # nothing but flat grey within the neighbourhood
    assert box.left < 300 and box.top < 300  # nowhere near the distant patch


def test_find_sharpest_nearby_tile_finds_a_nearby_patch():
    img = _image_with_sharp_patch(size=(1000, 1000), patch_box=(120, 120, 160, 160))
    reference_box = geometry.Box(90, 90, 110, 110)  # close to the patch

    box, score = sharpness.find_sharpest_nearby_tile(
        img, reference_box, radius_factor=6, tile_size=20
    )

    assert score > 0.0
    assert box.left < 160 and box.right > 120
    assert box.top < 160 and box.bottom > 120
