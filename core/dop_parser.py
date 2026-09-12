"""Parses the fields this app needs out of a DxO .dop sidecar file.

The .dop format is NOT XML -- it's DxO's own undocumented text notation
(`Key = value,` pairs and `{ }` blocks). Rather than writing a full parser
for an undocumented, deeply-nested grammar, this module does targeted
regex extraction of the handful of scalar/array fields we actually need.

Known gap: no free-angle "straighten" rotation field has been identified
yet -- only crop and the 90-degree-multiple Orientation value are handled.
"""
import re
from dataclasses import dataclass
from pathlib import Path


# Corrections that change the frame CropRect is expressed in. None of them can
# be inverted (they need a projective/lens transform we don't model), so if any
# is active the AF box position can't be reconstructed and the caller shows a
# "position not guaranteed" warning instead of a falsely precise box. All four
# names were confirmed present in a real PhotoLab 9 sidecar.
_GEOMETRY_CORRECTION_FLAGS = (
    "KeystoningActive",
    "KeystoningHorizonActive",
    "FramingActive",
    "AnamorphosisActive",
)


@dataclass(frozen=True)
class Geometry:
    orientation: int
    crop_active: bool
    crop_rect: tuple[float, float, float, float] | None
    has_unsupported_correction: bool


def find_sidecar(raw_path: Path) -> Path | None:
    candidate = raw_path.with_name(raw_path.name + ".dop")
    return candidate if candidate.is_file() else None


def _find_scalar(text: str, key: str) -> str | None:
    match = re.search(rf"\b{re.escape(key)}\s*=\s*([^\n,]+),?", text)
    return match.group(1).strip() if match else None


def parse_dop(dop_text: str) -> Geometry:
    orientation_raw = _find_scalar(dop_text, "Orientation")
    orientation = int(orientation_raw) if orientation_raw else 1

    crop_active = _find_scalar(dop_text, "CropActive") == "true"

    crop_rect = None
    crop_rect_match = re.search(r"CropRect\s*=\s*\{([^}]*)\}", dop_text)
    if crop_rect_match:
        values = [float(v) for v in crop_rect_match.group(1).replace(",", " ").split()]
        if len(values) == 4:
            crop_rect = (values[0], values[1], values[2], values[3])

    has_unsupported_correction = any(
        _find_scalar(dop_text, flag) == "true" for flag in _GEOMETRY_CORRECTION_FLAGS
    )

    return Geometry(orientation, crop_active, crop_rect, has_unsupported_correction)
