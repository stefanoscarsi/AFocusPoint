from gui import zoom


def test_clamp_zoom_within_range_is_unchanged():
    assert zoom.clamp_zoom(2.5) == 2.5


def test_clamp_zoom_below_min_clamps_to_min():
    assert zoom.clamp_zoom(0.1) == zoom.MIN_ZOOM


def test_clamp_zoom_above_max_clamps_to_max():
    assert zoom.clamp_zoom(100.0) == zoom.MAX_ZOOM


def test_clamp_zoom_respects_a_custom_upper_bound():
    assert zoom.clamp_zoom(10.0, upper=3.0) == 3.0


def test_max_zoom_for_base_scale_caps_at_native_resolution():
    # base_scale 1.0 (photo already shown at 100% to fit) -> the ceiling is
    # exactly MAX_NATIVE_SCALE (400% of native pixel size), well under the
    # flat MAX_ZOOM ceiling so it's the binding constraint here.
    result = zoom.max_zoom_for_base_scale(1.0)
    assert abs(result - zoom.MAX_NATIVE_SCALE) < 1e-9


def test_max_zoom_for_base_scale_never_exceeds_the_flat_ceiling():
    # A tiny base_scale would otherwise imply a huge native-resolution cap;
    # MAX_ZOOM still wins as the hard ceiling.
    assert zoom.max_zoom_for_base_scale(0.001) == zoom.MAX_ZOOM


def test_max_zoom_for_base_scale_never_below_min_zoom():
    # A base_scale already above MAX_NATIVE_SCALE would otherwise compute a
    # ceiling below MIN_ZOOM -- must still allow at least the fit view.
    assert zoom.max_zoom_for_base_scale(10.0) == zoom.MIN_ZOOM


def test_max_zoom_for_base_scale_falls_back_to_flat_ceiling_when_degenerate():
    assert zoom.max_zoom_for_base_scale(0.0) == zoom.MAX_ZOOM
    assert zoom.max_zoom_for_base_scale(-1.0) == zoom.MAX_ZOOM
