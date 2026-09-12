"""Pure coordinate math: no image I/O, no ExifTool, no filesystem access.

Orientation values follow the EXIF convention: 1=normal, 3=180 deg,
6=90 deg CW, 8=90 deg CCW. This must stay consistent with the rotation
PIL applies when orienting the preview -- if you change one, change the
other.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Box:
    left: float
    top: float
    right: float
    bottom: float


def rotate_point(x: float, y: float, width: int, height: int, orientation: int):
    if orientation == 1:
        return x, y, width, height
    if orientation == 3:
        return width - x, height - y, width, height
    if orientation == 6:
        return height - y, x, height, width
    if orientation == 8:
        return y, width - x, height, width
    raise ValueError(f"Unsupported orientation value: {orientation}")


def af_box_to_pixels(center_x: float, center_y: float, box_w: float, box_h: float) -> Box:
    return Box(
        left=center_x - box_w / 2,
        top=center_y - box_h / 2,
        right=center_x + box_w / 2,
        bottom=center_y + box_h / 2,
    )


def apply_crop(box: Box, crop_rect, frame_width: int, frame_height: int) -> Box | None:
    x0, y0, x1, y1 = crop_rect
    crop_left = x0 * frame_width
    crop_top = y0 * frame_height
    crop_right = x1 * frame_width
    crop_bottom = y1 * frame_height

    shifted = Box(
        left=box.left - crop_left,
        top=box.top - crop_top,
        right=box.right - crop_left,
        bottom=box.bottom - crop_top,
    )
    crop_w = crop_right - crop_left
    crop_h = crop_bottom - crop_top
    if shifted.right <= 0 or shifted.bottom <= 0 or shifted.left >= crop_w or shifted.top >= crop_h:
        return None
    return shifted


def boxes_overlap(a: Box, b: Box) -> bool:
    return a.left < b.right and b.left < a.right and a.top < b.bottom and b.top < a.bottom


def scale_box(box: Box, from_width: float, from_height: float, to_width: float, to_height: float) -> Box:
    sx = to_width / from_width
    sy = to_height / from_height
    return Box(box.left * sx, box.top * sy, box.right * sx, box.bottom * sy)


def compute_display_box(
    af_point: tuple[float, float],
    box_w: float,
    box_h: float,
    ref_width: int,
    ref_height: int,
    orientation: int,
    crop_rect,
    crop_active: bool,
    target_width: int,
    target_height: int,
) -> Box | None:
    x, y, frame_w, frame_h = rotate_point(af_point[0], af_point[1], ref_width, ref_height, orientation)
    box = af_box_to_pixels(x, y, box_w, box_h)

    if crop_active and crop_rect is not None:
        box = apply_crop(box, crop_rect, frame_w, frame_h)
        if box is None:
            return None
        x0, y0, x1, y1 = crop_rect
        frame_w = (x1 - x0) * frame_w
        frame_h = (y1 - y0) * frame_h

    # A degenerate frame (e.g. a .dop CropRect with x1 == x0, or a zero AF
    # reference size) would make scale_box divide by zero. Reuse the existing
    # "box is None" contract, which the caller already renders as a warning.
    if frame_w <= 0 or frame_h <= 0:
        return None

    return scale_box(box, frame_w, frame_h, target_width, target_height)
