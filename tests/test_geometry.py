from core import geometry


def test_rotate_point_identity():
    assert geometry.rotate_point(10, 20, 100, 200, 1) == (10, 20, 100, 200)


def test_rotate_point_180():
    assert geometry.rotate_point(10, 20, 100, 200, 3) == (90, 180, 100, 200)


def test_rotate_point_90_cw():
    # width=100, height=200 -> after 90 CW, frame becomes 200x100
    assert geometry.rotate_point(10, 20, 100, 200, 6) == (180, 10, 200, 100)


def test_rotate_point_90_ccw():
    assert geometry.rotate_point(10, 20, 100, 200, 8) == (20, 90, 200, 100)


def test_af_box_to_pixels_centers_correctly():
    box = geometry.af_box_to_pixels(center_x=50, center_y=50, box_w=20, box_h=10)
    assert box == geometry.Box(left=40, top=45, right=60, bottom=55)


def test_boxes_overlap_true_when_boxes_intersect():
    a = geometry.Box(0, 0, 50, 50)
    b = geometry.Box(25, 25, 75, 75)
    assert geometry.boxes_overlap(a, b) is True


def test_boxes_overlap_false_when_boxes_are_disjoint():
    a = geometry.Box(0, 0, 50, 50)
    b = geometry.Box(60, 60, 100, 100)
    assert geometry.boxes_overlap(a, b) is False


def test_boxes_overlap_false_when_boxes_only_touch_at_an_edge():
    a = geometry.Box(0, 0, 50, 50)
    b = geometry.Box(50, 0, 100, 50)
    assert geometry.boxes_overlap(a, b) is False


def test_apply_crop_shifts_into_crop_relative_coords():
    box = geometry.Box(left=40, top=45, right=60, bottom=55)
    # crop_rect selects the right half of a 100x100 frame
    shifted = geometry.apply_crop(box, (0.5, 0.0, 1.0, 1.0), frame_width=100, frame_height=100)
    assert shifted == geometry.Box(left=-10, top=45, right=10, bottom=55)


def test_apply_crop_returns_none_when_box_entirely_outside():
    box = geometry.Box(left=5, top=5, right=15, bottom=15)
    shifted = geometry.apply_crop(box, (0.5, 0.5, 1.0, 1.0), frame_width=100, frame_height=100)
    assert shifted is None


def test_scale_box_applies_independent_x_y_ratios():
    box = geometry.Box(left=10, top=20, right=30, bottom=40)
    scaled = geometry.scale_box(box, from_width=100, from_height=200, to_width=50, to_height=100)
    assert scaled == geometry.Box(left=5, top=10, right=15, bottom=20)


def test_compute_display_box_no_crop_no_rotation():
    box = geometry.compute_display_box(
        af_point=(50, 50), box_w=20, box_h=20,
        ref_width=100, ref_height=100, orientation=1,
        crop_rect=None, crop_active=False,
        target_width=100, target_height=100,
    )
    assert box == geometry.Box(left=40, top=40, right=60, bottom=60)


def test_compute_display_box_with_crop_and_downscale():
    box = geometry.compute_display_box(
        af_point=(75, 50), box_w=20, box_h=20,
        ref_width=100, ref_height=100, orientation=1,
        crop_rect=(0.5, 0.0, 1.0, 1.0), crop_active=True,
        target_width=50, target_height=100,
    )
    # crop-relative center: (75-50, 50) = (25, 50) in a 50x100 crop frame,
    # target is already 50x100 so no further scaling
    assert box == geometry.Box(left=15, top=40, right=35, bottom=60)


def test_compute_display_box_returns_none_outside_crop():
    box = geometry.compute_display_box(
        af_point=(10, 10), box_w=5, box_h=5,
        ref_width=100, ref_height=100, orientation=1,
        crop_rect=(0.5, 0.5, 1.0, 1.0), crop_active=True,
        target_width=50, target_height=50,
    )
    assert box is None


def test_compute_display_box_returns_none_on_degenerate_crop_width():
    """A .dop CropRect with x1 == x0 leaves a zero-width frame; dividing by it
    would raise ZeroDivisionError. Reuse the existing "box is None" contract
    instead (the caller renders that as a warning)."""
    box = geometry.compute_display_box(
        af_point=(50, 50), box_w=10, box_h=10,
        ref_width=100, ref_height=100, orientation=1,
        crop_rect=(0.5, 0.5, 0.5, 1.0), crop_active=True,
        target_width=50, target_height=50,
    )
    assert box is None


def test_compute_display_box_returns_none_on_degenerate_crop_height():
    box = geometry.compute_display_box(
        af_point=(50, 50), box_w=10, box_h=10,
        ref_width=100, ref_height=100, orientation=1,
        crop_rect=(0.0, 0.5, 1.0, 0.5), crop_active=True,
        target_width=50, target_height=50,
    )
    assert box is None


def test_compute_display_box_returns_none_on_zero_reference_frame():
    box = geometry.compute_display_box(
        af_point=(0, 0), box_w=10, box_h=10,
        ref_width=0, ref_height=0, orientation=1,
        crop_rect=None, crop_active=False,
        target_width=50, target_height=50,
    )
    assert box is None
