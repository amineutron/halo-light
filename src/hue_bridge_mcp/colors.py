"""Color helpers: names, hex, sRGB to CIE xy, Kelvin to mirek."""

from __future__ import annotations

import re

from .errors import InvalidInputError
from .matching import normalize

WHITE_POINT_XY = (0.3127, 0.3290)  # D65
MIREK_MIN = 153  # about 6500 K
MIREK_MAX = 500  # 2000 K

_NAMED_RGB: dict[str, tuple[int, int, int]] = {
    "rouge": (255, 0, 0),
    "red": (255, 0, 0),
    "vert": (0, 200, 0),
    "green": (0, 200, 0),
    "bleu": (0, 0, 255),
    "blue": (0, 0, 255),
    "jaune": (255, 220, 0),
    "yellow": (255, 220, 0),
    "orange": (255, 120, 0),
    "rose": (255, 105, 180),
    "pink": (255, 105, 180),
    "violet": (140, 0, 255),
    "purple": (140, 0, 255),
    "magenta": (255, 0, 255),
    "cyan": (0, 255, 255),
    "turquoise": (64, 224, 208),
    "blanc": (255, 255, 255),
    "white": (255, 255, 255),
}

_HEX = re.compile(r"^#?([0-9a-fA-F]{6})$")


def rgb_to_xy(red: int, green: int, blue: int) -> tuple[float, float]:
    """Convert sRGB (0-255) to CIE 1931 xy using the formula from the Hue documentation."""
    for value in (red, green, blue):
        if not 0 <= value <= 255:
            raise InvalidInputError("RGB components must be between 0 and 255.")

    def linear(channel: int) -> float:
        c = channel / 255
        return ((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92

    r, g, b = linear(red), linear(green), linear(blue)
    x = r * 0.664511 + g * 0.154324 + b * 0.162028
    y = r * 0.283881 + g * 0.668433 + b * 0.047685
    z = r * 0.000088 + g * 0.072310 + b * 0.986039
    total = x + y + z
    if total == 0:
        return WHITE_POINT_XY
    return round(x / total, 4), round(y / total, 4)


def color_to_xy(color: str) -> tuple[float, float]:
    """Resolve a color name (French or English, accents ignored) or ``#rrggbb`` to xy."""
    text = color.strip()
    hex_match = _HEX.match(text)
    if hex_match:
        digits = hex_match.group(1)
        return rgb_to_xy(int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16))
    rgb = _NAMED_RGB.get(normalize(text))
    if rgb is None:
        known = ", ".join(sorted(_NAMED_RGB))
        raise InvalidInputError(f"Unknown color '{color}'. Use #rrggbb or one of: {known}.")
    return rgb_to_xy(*rgb)


def check_xy(x: float, y: float) -> tuple[float, float]:
    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
        raise InvalidInputError("xy coordinates must be between 0 and 1.")
    return x, y


def kelvin_to_mirek(kelvin: int) -> int:
    """Convert a color temperature in Kelvin to the mirek unit used by the bridge."""
    if kelvin <= 0:
        raise InvalidInputError("The temperature must be a positive number of Kelvin.")
    mirek = round(1_000_000 / kelvin)
    if not MIREK_MIN <= mirek <= MIREK_MAX:
        low, high = round(1_000_000 / MIREK_MAX), round(1_000_000 / MIREK_MIN)
        raise InvalidInputError(f"Temperature out of range: use {low} to {high} Kelvin.")
    return mirek


def mirek_to_kelvin(mirek: int) -> int:
    return round(1_000_000 / mirek)
