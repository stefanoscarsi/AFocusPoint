"""Blur/focus-quality scoring via variance of the Laplacian.

A higher score means more high-frequency detail (sharp edges); a flat or
blurred region scores near zero. This is a relative measure for comparing
regions of the *same* photo, not an absolute "in focus" threshold.

IMPORTANT LIMITATION (confirmed on real photos): this metric conflates edge
sharpness with local contrast/exposure. On backlit or high-contrast wildlife
scenes, a blurry but sunlit twig can outscore a correctly-focused, confirmed
AF subject in flatter light by an order of magnitude. Two mitigations
(normalizing by local contrast, and restricting comparisons to similarly-lit
tiles) were tried and both failed in new ways -- comparing absolute sharpness
across differently-lit regions of one frame appears to be a fundamental
limitation of single-frame spatial metrics. Callers must present this as
indicative only, not proof of a focus mistake.

SECOND, SEPARATE BUG FOUND AND FIXED (confirmed on ~20 real photos): the
original "elsewhere" search compared the AVERAGE sharpness over the whole AF
box against the single SHARPEST small tile anywhere in the entire photo.
That is not a fair comparison -- "best of many small samples" beats "one
big average" almost by construction, regardless of actual focus, and
searching the whole frame kept surfacing subjects unrelated to what the
camera focused on. That combination produced a "mismatch" on 19 of 20 real
photos, most of them confirmed AF hits. Fixed by comparing the same
granularity on both sides (best_tile_score vs. find_sharpest_nearby_tile,
both using DEFAULT_TILE_SIZE tiles) within a neighbourhood around the AF
point rather than the whole frame -- this alone cut the mismatch rate from
19/20 to 9/20 on the same sample, and the remaining mismatches were
visually sensible (e.g. a sharp insect on a branch next to a slightly
soft, backlit subject), not unrelated background clutter.
"""
from PIL import Image

import numpy as np

from . import geometry

# Below this, a crop is too small for the Laplacian response to mean
# anything (mostly border effects from the edge-padding).
MIN_REGION_SIZE = 8

DEFAULT_TILE_SIZE = 100

# The "elsewhere" search is restricted to a square neighbourhood around the
# AF box, side = the box's longer edge * this factor. Searching the WHOLE
# photo (the original approach) tends to surface an unrelated area far from
# the subject -- confirmed on real photos, a distant sunlit twig or a patch
# of shadow noise consistently outscored a correctly-focused subject in
# flatter light. A local neighbourhood keeps the comparison relevant to the
# actual subject instead.
NEIGHBORHOOD_RADIUS_FACTOR = 6

# Only report a mismatch if the alternate area beats the AF point by more
# than this margin -- otherwise near-identical scores (normal measurement
# noise) get flagged as a false alarm.
MISMATCH_TOLERANCE = 1.15


def _laplacian_variance(gray: np.ndarray) -> float:
    # Manual 4-neighbour Laplacian via edge-padded slicing, avoiding a scipy
    # dependency just for one small convolution.
    padded = np.pad(gray, 1, mode="edge")
    response = (
        padded[:-2, 1:-1] + padded[2:, 1:-1] + padded[1:-1, :-2] + padded[1:-1, 2:]
        - 4 * padded[1:-1, 1:-1]
    )
    return float(response.var())


def region_sharpness(image: Image.Image, box: geometry.Box) -> float | None:
    """Sharpness score for one arbitrary region (e.g. the AF box), clamped to
    the image bounds. Returns None if the (clamped) region is too small to
    score meaningfully."""
    left = max(0, int(box.left))
    top = max(0, int(box.top))
    right = min(image.width, int(box.right))
    bottom = min(image.height, int(box.bottom))
    if right - left < MIN_REGION_SIZE or bottom - top < MIN_REGION_SIZE:
        return None

    tile = image.crop((left, top, right, bottom)).convert("L")
    return _laplacian_variance(np.asarray(tile, dtype=np.float64))


def find_sharpest_tile(
    image: Image.Image, tile_size: int = DEFAULT_TILE_SIZE
) -> tuple[geometry.Box, float]:
    """Scans the whole image in a grid of tile_size x tile_size tiles (edge
    tiles may be smaller) and returns the box and score of the sharpest one.
    Used to show the user where the photo's actual sharpest area is, as a
    check against the (possibly unconfirmed) AF point."""
    gray = np.asarray(image.convert("L"), dtype=np.float64)
    height, width = gray.shape

    best_box = geometry.Box(0, 0, min(tile_size, width), min(tile_size, height))
    best_score = 0.0
    for top in range(0, height, tile_size):
        bottom = min(top + tile_size, height)
        if bottom - top < MIN_REGION_SIZE:
            continue
        for left in range(0, width, tile_size):
            right = min(left + tile_size, width)
            if right - left < MIN_REGION_SIZE:
                continue
            score = _laplacian_variance(gray[top:bottom, left:right])
            if score > best_score:
                best_score = score
                best_box = geometry.Box(left, top, right, bottom)

    return best_box, best_score


def best_tile_score(
    image: Image.Image, box: geometry.Box, tile_size: int = DEFAULT_TILE_SIZE
) -> float | None:
    """Sharpness of the single sharpest tile_size x tile_size patch within
    `box` (clamped to image bounds) -- NOT the average over the whole box,
    so it's comparable on equal terms with find_sharpest_tile's/
    find_sharpest_nearby_tile's own patches elsewhere. Falls back to scoring
    the whole (clamped) box via region_sharpness when it's too small to
    subdivide into even one tile. Returns None if the (clamped) box is too
    small to score meaningfully at all."""
    left = max(0, int(box.left))
    top = max(0, int(box.top))
    right = min(image.width, int(box.right))
    bottom = min(image.height, int(box.bottom))
    if right - left < MIN_REGION_SIZE or bottom - top < MIN_REGION_SIZE:
        return None
    if right - left < tile_size or bottom - top < tile_size:
        return region_sharpness(image, box)

    region = image.crop((left, top, right, bottom))
    _, score = find_sharpest_tile(region, tile_size=tile_size)
    return score


def find_sharpest_nearby_tile(
    image: Image.Image,
    reference_box: geometry.Box,
    radius_factor: float = NEIGHBORHOOD_RADIUS_FACTOR,
    tile_size: int = DEFAULT_TILE_SIZE,
) -> tuple[geometry.Box, float]:
    """Like find_sharpest_tile, but restricted to a square neighbourhood
    around reference_box instead of the whole photo -- see the module
    docstring for why searching the whole frame gives misleading results."""
    cx = (reference_box.left + reference_box.right) / 2
    cy = (reference_box.top + reference_box.bottom) / 2
    side = max(reference_box.right - reference_box.left, reference_box.bottom - reference_box.top)
    half = side * radius_factor / 2

    left = max(0, int(cx - half))
    top = max(0, int(cy - half))
    right = min(image.width, int(cx + half))
    bottom = min(image.height, int(cy + half))

    region = image.crop((left, top, right, bottom))
    box, score = find_sharpest_tile(region, tile_size=tile_size)
    return geometry.Box(box.left + left, box.top + top, box.right + left, box.bottom + top), score
