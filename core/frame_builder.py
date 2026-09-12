"""Orchestrates the full pipeline for one CR3: read metadata, extract the
preview, apply PhotoLab's crop/rotation (if any), and work out where the AF
point(s) land on the final image before drawing them. Pulled out of
gui/main_window.py so it can be tested without Qt.

A sharpness-based "is this really the sharpest area?" cross-check used to
live here too. It was removed: even after fixing a real measurement bias
(comparing the AF box's average against the single sharpest tile in the
whole photo -- an unfair comparison that flagged ~95% of confirmed-AF real
photos as a mismatch) and restricting it to a local neighbourhood (which
brought that down to ~70%), it still pointed at areas the user could see
weren't actually the sharpest. Comparing sharpness across a single frame
this way just isn't reliable enough to show as a feature -- see git history
(core/sharpness.py) if picking this up again.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from . import af_parser, dop_parser, exif_reader, geometry, image_ops, overlay_renderer, preview_extractor

# Orientations image_ops.apply_orientation / geometry.rotate_point can handle.
# Mirrored EXIF values (2/4/5/7) are effectively never produced by Canon RAWs;
# treating them as "no rotation" shows the photo unrotated rather than failing
# the whole load with an error dialog.
_SUPPORTED_ORIENTATIONS = (1, 3, 6, 8)

_UNSUPPORTED_CORRECTION_WARNING = "Posizione non garantita — correzione prospettica non gestita"
_CLIPPED_BY_CROP_WARNING = "Il punto AF cade fuori dall'area ritagliata"


@dataclass
class FrameResult:
    image: Image.Image
    shooting: af_parser.ShootingData
    af_data: af_parser.AFData
    # Set only when geometry (crop/rotation/perspective) prevented placing a
    # box confidently -- independent of af_parser's own "ambiguous AF" case,
    # which info_panel already reports from af_data.points being empty.
    geometry_warning: str | None = None


def _geometry_without_sidecar(raw_metadata: dict) -> dop_parser.Geometry:
    """No .dop means nothing was cropped or rotated in PhotoLab -- but the
    camera may still have recorded a portrait orientation in the RAW itself,
    so honour IFD0:Orientation rather than assuming 1."""
    try:
        orientation = int(raw_metadata.get("IFD0:Orientation", 1))
    except (TypeError, ValueError):
        orientation = 1
    if orientation not in _SUPPORTED_ORIENTATIONS:
        orientation = 1
    return dop_parser.Geometry(
        orientation=orientation, crop_active=False, crop_rect=None, has_unsupported_correction=False
    )


def _resolve_geometry(raw_path: Path, raw_metadata: dict) -> dop_parser.Geometry:
    sidecar_path = dop_parser.find_sidecar(raw_path)
    if sidecar_path is None:
        return _geometry_without_sidecar(raw_metadata)
    # Once a .dop exists it is authoritative: it reflects what PhotoLab
    # actually did, including its own Orientation field.
    return dop_parser.parse_dop(sidecar_path.read_text(encoding="utf-8", errors="replace"))


def _display_box_for_point(
    point: af_parser.AFPoint, af_data: af_parser.AFData, geom: dop_parser.Geometry, target_size: tuple[int, int]
) -> geometry.Box | None:
    if not af_data.af_reference_width or not af_data.af_reference_height:
        return None
    return geometry.compute_display_box(
        af_point=(point.x, point.y),
        box_w=point.width,
        box_h=point.height,
        ref_width=af_data.af_reference_width,
        ref_height=af_data.af_reference_height,
        orientation=geom.orientation,
        crop_rect=geom.crop_rect,
        crop_active=geom.crop_active,
        target_width=target_size[0],
        target_height=target_size[1],
    )


def _display_box_for_search_zone(
    af_data: af_parser.AFData, geom: dop_parser.Geometry, target_size: tuple[int, int]
) -> geometry.Box | None:
    if not af_data.search_zone_bbox or not af_data.af_reference_width or not af_data.af_reference_height:
        return None
    min_x, min_y, max_x, max_y = af_data.search_zone_bbox
    center = ((min_x + max_x) / 2, (min_y + max_y) / 2)
    return geometry.compute_display_box(
        af_point=center,
        box_w=max_x - min_x,
        box_h=max_y - min_y,
        ref_width=af_data.af_reference_width,
        ref_height=af_data.af_reference_height,
        orientation=geom.orientation,
        crop_rect=geom.crop_rect,
        crop_active=geom.crop_active,
        target_width=target_size[0],
        target_height=target_size[1],
    )


def build_frame(raw_path: str | Path) -> FrameResult:
    raw_path = Path(raw_path)
    metadata = exif_reader.read_all_metadata(raw_path)
    shooting = af_parser.get_shooting_data(metadata["raw"], metadata["formatted"])
    af_data = af_parser.get_af_data_structured(metadata["raw"], metadata["formatted"])

    preview = preview_extractor.extract_preview_image(raw_path)
    geom = _resolve_geometry(raw_path, metadata["raw"])

    oriented = image_ops.apply_orientation(preview, geom.orientation)
    cropped = image_ops.apply_crop(oriented, geom.crop_rect) if (geom.crop_active and geom.crop_rect) else oriented
    target_size = (cropped.width, cropped.height)

    if geom.has_unsupported_correction:
        return FrameResult(
            image=cropped.convert("RGB"),
            shooting=shooting,
            af_data=af_data,
            geometry_warning=_UNSUPPORTED_CORRECTION_WARNING,
        )

    display_boxes: list[tuple[geometry.Box, tuple[int, int, int]]] = []
    for idx, point in enumerate(af_data.points):
        box = _display_box_for_point(point, af_data, geom, target_size)
        if box is None:
            continue
        color = overlay_renderer.COLOR_PRIMARY if idx == af_data.primary_point_index else overlay_renderer.COLOR_IN_FOCUS
        display_boxes.append((box, color))

    geometry_warning = None
    if af_data.points and not display_boxes:
        geometry_warning = _CLIPPED_BY_CROP_WARNING

    search_zone_box = _display_box_for_search_zone(af_data, geom, target_size)

    annotated = overlay_renderer.draw_af_points(cropped, display_boxes, search_zone_box)

    return FrameResult(
        image=annotated,
        shooting=shooting,
        af_data=af_data,
        geometry_warning=geometry_warning,
    )
