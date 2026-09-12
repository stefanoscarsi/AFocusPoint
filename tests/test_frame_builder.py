from PIL import Image

from core import frame_builder, overlay_renderer


def _af_tags(x=0, y=0, w=100, h=100, ref=(400, 300), valid=1):
    ref_w, ref_h = ref
    return {
        "Canon:AFImageWidth": ref_w,
        "Canon:AFImageHeight": ref_h,
        "Canon:AFAreaXPositions": str(x),
        "Canon:AFAreaYPositions": str(y),
        "Canon:AFAreaWidths": str(w),
        "Canon:AFAreaHeights": str(h),
        "Canon:ValidAFPoints": valid,
    }


def _stub(monkeypatch, raw_extra=None, formatted_extra=None, preview_size=(400, 300)):
    raw = {**(raw_extra or {})}
    formatted = {**(formatted_extra or {})}
    monkeypatch.setattr(
        frame_builder.exif_reader,
        "read_all_metadata",
        lambda path: {"raw": raw, "formatted": formatted},
    )
    monkeypatch.setattr(
        frame_builder.preview_extractor,
        "extract_preview_image",
        lambda path: Image.new("RGB", preview_size, "black"),
    )


def test_no_sidecar_rotates_preview_using_exif_orientation(monkeypatch, tmp_path):
    """A portrait shot straight off the card has no .dop, but the RAW's own
    IFD0:Orientation still says it must be rotated."""
    _stub(monkeypatch, raw_extra={"IFD0:Orientation": 6}, preview_size=(400, 300))
    raw_path = tmp_path / "IMG_0001.CR3"
    raw_path.touch()
    assert frame_builder.dop_parser.find_sidecar(raw_path) is None

    result = frame_builder.build_frame(raw_path)

    assert result.image.size == (300, 400)


def test_no_sidecar_and_no_orientation_tag_leaves_preview_unrotated(monkeypatch, tmp_path):
    _stub(monkeypatch, preview_size=(400, 300))
    raw_path = tmp_path / "IMG_0001.CR3"
    raw_path.touch()

    result = frame_builder.build_frame(raw_path)

    assert result.image.size == (400, 300)


def test_sidecar_orientation_wins_over_exif_orientation(monkeypatch, tmp_path):
    """Once a .dop exists it is authoritative -- it reflects what PhotoLab
    actually did, including any rotation the user undid."""
    _stub(monkeypatch, raw_extra={"IFD0:Orientation": 6}, preview_size=(400, 300))
    raw_path = tmp_path / "IMG_0001.CR3"
    raw_path.touch()
    (tmp_path / "IMG_0001.CR3.dop").write_text(
        "Sidecar = {\nOrientation = 1,\nCropActive = false,\n}\n", encoding="utf-8"
    )

    result = frame_builder.build_frame(raw_path)

    assert result.image.size == (400, 300)


def test_unsupported_correction_returns_warning_and_no_boxes(monkeypatch, tmp_path):
    _stub(monkeypatch, raw_extra=_af_tags(), formatted_extra={"Canon:AFPointsInFocus": "0"})
    raw_path = tmp_path / "IMG_0001.CR3"
    raw_path.touch()
    (tmp_path / "IMG_0001.CR3.dop").write_text(
        "Sidecar = {\nOrientation = 1,\nCropActive = false,\nKeystoningActive = true,\n}\n",
        encoding="utf-8",
    )

    result = frame_builder.build_frame(raw_path)

    assert result.geometry_warning == frame_builder._UNSUPPORTED_CORRECTION_WARNING
    # No box color anywhere on the (otherwise flat black) image.
    pixels = result.image.load()
    w, h = result.image.size
    assert not any(
        pixels[x, y] == overlay_renderer.COLOR_IN_FOCUS for y in range(0, h, 5) for x in range(0, w, 5)
    )


def test_confirmed_single_af_point_draws_box(monkeypatch, tmp_path):
    _stub(
        monkeypatch,
        raw_extra=_af_tags(x=0, y=0, w=100, h=100, ref=(400, 300)),
        formatted_extra={"Canon:AFPointsInFocus": "0"},
    )
    raw_path = tmp_path / "IMG_0001.CR3"
    raw_path.touch()

    result = frame_builder.build_frame(raw_path)

    assert result.geometry_warning is None
    pixels = result.image.load()
    w, h = result.image.size
    assert any(
        pixels[x, y] == overlay_renderer.COLOR_IN_FOCUS for y in range(0, h, 2) for x in range(0, w, 2)
    )


def test_ambiguous_af_with_no_confirmed_point_draws_only_search_zone(monkeypatch, tmp_path):
    """Two candidate areas, neither confirmed via AFPointsInFocus/Selected --
    af_parser deliberately leaves points empty rather than guessing, but the
    search-zone rectangle (context) should still be drawn."""
    raw = _af_tags(x="-50 50", y="0 0", w="20 20", h="20 20", ref=(400, 300))
    raw["Canon:AFAreaXPositions"] = "-50 50"
    raw["Canon:AFAreaYPositions"] = "0 0"
    raw["Canon:AFAreaWidths"] = "20 20"
    raw["Canon:AFAreaHeights"] = "20 20"
    raw["Canon:ValidAFPoints"] = 2
    _stub(monkeypatch, raw_extra=raw, formatted_extra={})
    raw_path = tmp_path / "IMG_0001.CR3"
    raw_path.touch()

    result = frame_builder.build_frame(raw_path)

    assert result.af_data.points == []
    pixels = result.image.load()
    w, h = result.image.size
    assert any(
        pixels[x, y] == overlay_renderer.COLOR_SEARCH_ZONE for y in range(0, h, 2) for x in range(0, w, 2)
    )


def test_af_point_outside_crop_sets_clipped_warning(monkeypatch, tmp_path):
    _stub(
        monkeypatch,
        raw_extra=_af_tags(x=-190, y=0, w=10, h=10, ref=(400, 300)),
        formatted_extra={"Canon:AFPointsInFocus": "0"},
        preview_size=(400, 300),
    )
    raw_path = tmp_path / "IMG_0001.CR3"
    raw_path.touch()
    # Crop to the right half -- the AF point (near the far left edge) falls
    # entirely outside it.
    (tmp_path / "IMG_0001.CR3.dop").write_text(
        "Sidecar = {\nOrientation = 1,\nCropActive = true,\nCropRect = {\n0.5,\n0,\n1,\n1,\n}\n,\n}\n",
        encoding="utf-8",
    )

    result = frame_builder.build_frame(raw_path)

    assert result.geometry_warning == frame_builder._CLIPPED_BY_CROP_WARNING
