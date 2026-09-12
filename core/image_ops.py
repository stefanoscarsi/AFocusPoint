"""PIL-side image transforms: orientation and crop, applied to the preview
before any AF box is drawn on it.

Orientation handling here must stay consistent with geometry.rotate_point:
EXIF orientation 6 means "rotate 90 CW to display correctly", which in
PIL's (counter-clockwise) rotate convention is ROTATE_270; orientation 8
("90 CCW to display correctly") is ROTATE_90.
"""
from PIL import Image


def apply_orientation(image: Image.Image, orientation: int) -> Image.Image:
    if orientation == 1:
        return image
    if orientation == 3:
        return image.transpose(Image.ROTATE_180)
    if orientation == 6:
        return image.transpose(Image.ROTATE_270)
    if orientation == 8:
        return image.transpose(Image.ROTATE_90)
    raise ValueError(f"Unsupported orientation value: {orientation}")


def apply_crop(image: Image.Image, crop_rect) -> Image.Image:
    x0, y0, x1, y1 = crop_rect
    w, h = image.size
    return image.crop((x0 * w, y0 * h, x1 * w, y1 * h))
