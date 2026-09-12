"""Orchestrates the full pipeline for one CR3: read metadata, extract the
preview, apply PhotoLab's crop/rotation (if any), work out where the AF
point(s) land on the final image, draw them, and score sharpness as a
cross-check. Pulled out of gui/main_window.py so it can be tested without Qt.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from . import af_parser, dop_parser, exif_reader, geometry, image_ops, overlay_renderer, preview_extractor, sharpness

# Orientations image_ops.apply_orientation / geometry.rotate_point can handle.
# Mirrored EXIF values (2/4/5/7) are effectively never produced by Canon RAWs;
# treating them as "no rotation" shows the photo unrotated rather than failing
# the whole load with an error dialog.
_SUPPORTED_ORIENTATIONS = (1, 3, 6, 8)

_UNSUPPORTED_CORRECTION_WARNING = "Posizione non garantita — correzione prospettica non gestita"
_CLIPPED_BY_CROP_WARNING = "Il punto AF cade fuori dall'area ritagliata"

SHARPNESS_CAVEAT = (
    "Indicativo, non prova di un errore di messa a fuoco — il confronto "
    "diventa inaffidabile in controluce o su scene ad alto contrasto "
    "(confermato su una foto reale: un soggetto correttamente a fuoco in "
    "luce piatta ha ottenuto un punteggio molto piu' basso di un ramoscello "
    "sfocato ma illuminato dal sole). Verifica visivamente ingrandendo."
)


@dataclass
class FrameResult:
    image: Image.Image
    shooting: af_parser.ShootingData
    af_data: af_parser.AFData
    # Set only when geometry (crop/rotation/perspective) prevented placing a
    # box confidently -- independent of af_parser's own "ambiguous AF" case,
    # which info_panel already reports from af_data.points being empty.
    geometry_warning: str | None = None
    # Populated only when at least one AF box was actually drawn -- with
    # nothing "identified" to compare against, a sharpness readout has no
    # meaningful baseline.
    af_sharpness: float | None = None
    best_sharpness: float | None = None
    sharpness_matches: bool | None = None


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
    shooting = af_parser.get_shooting_data(metadata["formatted"])
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

    af_sharpness = None
    best_sharpness = None
    sharpness_matches = None
    if display_boxes:
        primary_box = next(
            (box for box, color in display_boxes if color == overlay_renderer.COLOR_PRIMARY),
            display_boxes[0][0],
        )
        af_sharpness = sharpness.region_sharpness(cropped, primary_box)
        best_box, best_sharpness = sharpness.find_sharpest_tile(cropped)
        sharpness_matches = geometry.boxes_overlap(primary_box, best_box)
        if not sharpness_matches:
            annotated = overlay_renderer.draw_sharp_box(annotated, best_box)

    return FrameResult(
        image=annotated,
        shooting=shooting,
        af_data=af_data,
        geometry_warning=geometry_warning,
        af_sharpness=af_sharpness,
        best_sharpness=best_sharpness,
        sharpness_matches=sharpness_matches,
    )
