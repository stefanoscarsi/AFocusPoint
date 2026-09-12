from pathlib import Path

import pytest

from core import dop_parser

FIXTURE = Path(__file__).parent / "fixtures" / "sample.dop"

# Every .dop flag that means "the frame CropRect is expressed in has been
# changed by a geometry correction we can't invert". Confirmed present in a
# real PhotoLab 9 sidecar.
GEOMETRY_CORRECTION_FLAGS = [
    "KeystoningActive",
    "KeystoningHorizonActive",
    "FramingActive",
    "AnamorphosisActive",
]


def test_parses_orientation_crop_and_keystoning_from_real_shaped_fixture():
    geometry = dop_parser.parse_dop(FIXTURE.read_text(encoding="utf-8"))
    assert geometry.orientation == 1
    assert geometry.crop_active is False
    assert geometry.crop_rect == (0.0, 0.0, 1.0, 1.0)
    assert geometry.has_unsupported_correction is False


def test_parses_active_crop_and_keystoning():
    text = FIXTURE.read_text(encoding="utf-8")
    text = text.replace("CropActive = false", "CropActive = true")
    text = text.replace("0,\n0,\n1,\n1,", "0.1,\n0.05,\n0.9,\n0.95,")
    text = text.replace("KeystoningActive = false", "KeystoningActive = true")

    geometry = dop_parser.parse_dop(text)
    assert geometry.crop_active is True
    assert geometry.crop_rect == (0.1, 0.05, 0.9, 0.95)
    assert geometry.has_unsupported_correction is True


@pytest.mark.parametrize("flag", GEOMETRY_CORRECTION_FLAGS)
def test_each_geometry_correction_flag_independently_marks_unsupported(flag):
    """All four corrections change the frame CropRect is expressed in. If any
    one of them is on, the box position can't be reconstructed, so the warning
    must fire even when the other three are off."""
    text = FIXTURE.read_text(encoding="utf-8").replace(
        f"{flag} = false", f"{flag} = true"
    )
    assert f"{flag} = true" in text, f"fixture is missing {flag}"

    geometry = dop_parser.parse_dop(text)
    assert geometry.has_unsupported_correction is True


def test_all_geometry_corrections_off_means_supported():
    text = FIXTURE.read_text(encoding="utf-8")
    for flag in GEOMETRY_CORRECTION_FLAGS:
        assert f"{flag} = false" in text, f"fixture is missing {flag}"
    assert dop_parser.parse_dop(text).has_unsupported_correction is False


def test_find_sidecar_returns_none_when_absent(tmp_path):
    raw = tmp_path / "IMG_0001.CR3"
    raw.touch()
    assert dop_parser.find_sidecar(raw) is None


def test_find_sidecar_finds_matching_dop(tmp_path):
    raw = tmp_path / "IMG_0001.CR3"
    raw.touch()
    (tmp_path / "IMG_0001.CR3.dop").touch()
    assert dop_parser.find_sidecar(raw) == tmp_path / "IMG_0001.CR3.dop"
