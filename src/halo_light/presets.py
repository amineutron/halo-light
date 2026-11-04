"""Named presets (white tones, activities, colors) and light effects.

A preset is a small recipe: a color or a white temperature, optionally a brightness. It is turned
into a CLIP v2 body with the same builders as the individual color tools, so a preset behaves
exactly like the equivalent explicit commands.
"""

from __future__ import annotations

from typing import Any

from .colors import color_to_xy
from .errors import InvalidInputError
from .matching import normalize
from .service import brightness_body, temperature_body, xy_body

# name -> (kind, value, brightness percent or None)
PRESETS: dict[str, tuple[str, int | str, float | None]] = {
    # White tones
    "warm": ("kelvin", 2500, None),
    "cool": ("kelvin", 4500, None),
    "daylight": ("kelvin", 6500, None),
    # Activities
    "concentration": ("kelvin", 4600, 100.0),
    "relax": ("kelvin", 2700, 57.0),
    "reading": ("kelvin", 3200, 86.0),
    "energize": ("kelvin", 6000, 100.0),
    # Colors
    "red": ("color", "rouge", None),
    "green": ("color", "vert", None),
    "blue": ("color", "bleu", None),
    "purple": ("color", "violet", None),
    "orange": ("color", "orange", None),
}

# Effects advertised by the bridge for Hue lights (``effects.effect_values``).
EFFECTS: tuple[str, ...] = (
    "no_effect",
    "candle",
    "fire",
    "prism",
    "sparkle",
    "opal",
    "glisten",
    "underwater",
    "cosmos",
    "sunbeam",
    "enchant",
)
_EFFECT_ALIASES = {"none": "no_effect", "aucun": "no_effect", "off": "no_effect"}


def preset_body(name: str) -> dict[str, Any]:
    """Return the request body for a preset (turns the light on)."""
    key = normalize(name)
    if key not in PRESETS:
        raise InvalidInputError(f"Unknown preset '{name}'. Choose one of: {', '.join(PRESETS)}.")
    kind, value, brightness = PRESETS[key]
    if kind == "kelvin":
        body = temperature_body(int(value))
    else:
        body = xy_body(*color_to_xy(str(value)))
    if brightness is not None:
        body = {**body, "dimming": brightness_body(brightness)["dimming"]}
    return body


def effect_body(name: str) -> dict[str, Any]:
    """Return the request body for a light effect (``none`` stops the current effect)."""
    key = normalize(name).replace(" ", "_")
    key = _EFFECT_ALIASES.get(key, key)
    if key not in EFFECTS:
        raise InvalidInputError(
            f"Unknown effect '{name}'. Choose one of: none, {', '.join(EFFECTS[1:])}."
        )
    return {"effects": {"effect": key}}
