"""Pure zoom math for the image viewer -- no Qt here, so it can be tested
without a running application. The Qt-side wiring (QGraphicsView transforms,
drag mode) lives in main_window.py.

Zoom is relative to "fit the whole photo in the view" (MIN_ZOOM): at
MIN_ZOOM the photo is shown scaled to fit, matching the original behaviour.
"""

MIN_ZOOM = 1.0
MAX_ZOOM = 8.0
# Cap how far past the photo's own pixel resolution zooming can go: beyond
# this you're just enlarging blur, not seeing more real detail. Needed
# because MAX_ZOOM alone isn't enough -- it's relative to the fit-to-view
# scale, which for a several-thousand-pixel-wide RAW preview on a modest
# window can be small, so a flat "8x fit scale" ceiling could mean
# rendering many times the photo's actual pixel count (slow, no benefit).
MAX_NATIVE_SCALE = 4.0
ZOOM_STEP = 1.25


def clamp_zoom(zoom: float, upper: float = MAX_ZOOM) -> float:
    return min(max(zoom, MIN_ZOOM), upper)


def max_zoom_for_base_scale(base_scale: float) -> float:
    """The zoom-multiplier ceiling for one photo's fit-to-view scale, so
    that base_scale * zoom never exceeds MAX_NATIVE_SCALE. Falls back to the
    flat MAX_ZOOM when base_scale is degenerate (e.g. no image loaded yet)."""
    if base_scale <= 0:
        return MAX_ZOOM
    return clamp_zoom(MAX_NATIVE_SCALE / base_scale)


# One notch of a classic mouse wheel reports an angle delta of 120 (1/8 of a
# degree per unit, 15 degrees per notch -- a Qt convention).
WHEEL_NOTCH = 120


def wheel_zoom_factor(angle_delta_y: int) -> float:
    """Zoom multiplier for one wheel event, proportional to how far it
    scrolled: exactly ZOOM_STEP per notch of a classic mouse wheel, as
    before, but only a fraction of it for the many small events that a
    trackpad or high-resolution wheel sends -- a flat ZOOM_STEP per event
    made Cmd+scroll on a Mac trackpad jump straight to the zoom limit."""
    return ZOOM_STEP ** (angle_delta_y / WHEEL_NOTCH)


def pinch_zoom_factor(gesture_value: float) -> float:
    """Zoom multiplier for one step of a trackpad pinch (macOS native zoom
    gesture), whose value is the relative change in size, e.g. +0.02 for
    "2% bigger". Guarded so a large negative value can't flip the image."""
    return max(1.0 + gesture_value, 0.1)
