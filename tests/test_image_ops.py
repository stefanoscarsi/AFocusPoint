from PIL import Image

from core import image_ops


def test_apply_orientation_identity_returns_same_size():
    img = Image.new("RGB", (100, 60), "black")
    result = image_ops.apply_orientation(img, 1)
    assert result.size == (100, 60)


def test_apply_orientation_90_swaps_dimensions():
    img = Image.new("RGB", (100, 60), "black")
    result = image_ops.apply_orientation(img, 6)
    assert result.size == (60, 100)


def test_apply_orientation_180_keeps_dimensions():
    img = Image.new("RGB", (100, 60), "black")
    result = image_ops.apply_orientation(img, 3)
    assert result.size == (100, 60)


def test_apply_crop_produces_expected_size():
    img = Image.new("RGB", (200, 100), "black")
    cropped = image_ops.apply_crop(img, (0.5, 0.0, 1.0, 1.0))
    assert cropped.size == (100, 100)
