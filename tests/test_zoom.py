from gui import zoom


def test_compute_fit_scale_binding_axis():
    # 6960x4640 photo into a 2304x1440 viewport: height is the binding
    # constraint (1440/4640 < 2304/6960).
    scale = zoom.compute_fit_scale((6960, 4640), (2304, 1440))
    assert abs(scale - 1440 / 4640) < 1e-9


def test_compute_fit_scale_degenerate_sizes_return_one():
    assert zoom.compute_fit_scale((0, 0), (100, 100)) == 1.0
    assert zoom.compute_fit_scale((100, 100), (0, 0)) == 1.0


def test_clamp_zoom_within_range_is_unchanged():
    assert zoom.clamp_zoom(2.5) == 2.5


def test_clamp_zoom_below_min_clamps_to_min():
    assert zoom.clamp_zoom(0.1) == zoom.MIN_ZOOM


def test_clamp_zoom_above_max_clamps_to_max():
    assert zoom.clamp_zoom(100.0) == zoom.MAX_ZOOM
