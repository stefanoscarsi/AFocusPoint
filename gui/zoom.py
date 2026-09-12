"""Pure zoom math for the image viewer -- no Qt here, so it can be tested
without a running application. The Qt-side wiring (wheel events, scrollbar
positioning) lives in main_window.py.

Zoom is relative to "fit the whole photo in the viewport" (MIN_ZOOM): at
MIN_ZOOM the photo is shown scaled to fit, matching the original behaviour.
MAX_ZOOM lets the user get well past native 100% for pixel-level peeping,
which is the whole point of judging a real focus mistake.
"""

MIN_ZOOM = 1.0
MAX_ZOOM = 8.0
ZOOM_STEP = 1.25


def compute_fit_scale(image_size: tuple[int, int], viewport_size: tuple[int, int]) -> float:
    """The scale factor that fits `image_size` inside `viewport_size` while
    preserving aspect ratio. Returns 1.0 for degenerate (zero/negative) sizes
    rather than dividing by zero."""
    img_w, img_h = image_size
    view_w, view_h = viewport_size
    if img_w <= 0 or img_h <= 0 or view_w <= 0 or view_h <= 0:
        return 1.0
    return min(view_w / img_w, view_h / img_h)


def clamp_zoom(zoom: float) -> float:
    return min(max(zoom, MIN_ZOOM), MAX_ZOOM)
