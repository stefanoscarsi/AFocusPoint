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
"""
from PIL import Image

import numpy as np

from . import geometry

# Below this, a crop is too small for the Laplacian response to mean
# anything (mostly border effects from the edge-padding).
MIN_REGION_SIZE = 8

DEFAULT_TILE_SIZE = 200


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
