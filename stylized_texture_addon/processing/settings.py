"""Blender-independent stylization settings and tolerant settings adapter.

This module intentionally has **no** dependency on ``bpy`` so it can be unit
tested with a plain Python + NumPy installation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, fields
from typing import Any, Mapping

SUPPORTED_RESOLUTIONS: tuple[int, ...] = (512, 1024, 2048, 4096)
DEFAULT_RESOLUTION: int = 2048

_MISSING = object()

_INT_FIELDS = ("color_steps", "seed")


def normalize_resolution(value: Any) -> int:
    """Normalize an arbitrary resolution value to a supported resolution.

    Handles plain integers/floats as well as Blender RNA enum strings such as
    ``"2048"`` or ``"Resolution.2048"``. Unsupported positive values are snapped
    to the nearest supported resolution so that old/partial settings keep
    working instead of failing. Non-finite numbers (``NaN``/``inf``) are
    rejected with :class:`ValueError` rather than triggering ``OverflowError``.
    """

    if isinstance(value, bool):
        raise ValueError(f"Unsupported resolution value: {value!r}.")

    if isinstance(value, int):
        number = value
    elif isinstance(value, float):
        if not math.isfinite(value):  # NaN or +/-inf
            raise ValueError("Resolution must be a finite number.")
        number = int(round(value))
    elif isinstance(value, str):
        digits = "".join(character for character in value if character.isdigit())
        if not digits:
            raise ValueError(f"Cannot parse a resolution from {value!r}.")
        number = int(digits)
    else:
        raise ValueError(f"Unsupported resolution value: {value!r}.")

    if number <= 0:
        raise ValueError(f"Resolution must be positive, got {number}.")

    if number in SUPPORTED_RESOLUTIONS:
        return number

    return min(SUPPORTED_RESOLUTIONS, key=lambda candidate: abs(candidate - number))


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _default_if_non_finite(value: Any, default: Any) -> Any:
    """Return *default* when *value* is a non-finite real number.

    Finite and non-numeric values are returned unchanged so that the existing
    conversion and clamp behavior is fully preserved.
    """

    if _is_non_finite(value):
        return default
    return value


@dataclass
class StylizationSettings:
    """Central, Blender-independent settings structure.

    Phase 1 fields come first for positional compatibility; Phase 2 fields
    (``hue_variation``, ``brush_scale``, ``paint_variation``, ``micro_detail``)
    are appended and default to neutral values.
    """

    color_steps: int = 8
    color_simplification: float = 0.70
    variation_strength: float = 0.25
    variation_scale: float = 0.15
    contrast: float = 1.05
    saturation: float = 0.90
    seed: int = 12345
    output_resolution: int = DEFAULT_RESOLUTION

    # --- Phase 2 fields ------------------------------------------------
    # Appended after the Phase 1 fields so positional construction stays
    # backward compatible. The defaults are deliberately *neutral*: with
    # ``hue_variation == 0``, ``paint_variation == 0`` and ``micro_detail == 1``
    # the Phase 2 effects are skipped entirely and the pipeline reproduces the
    # exact Phase 1 output.
    hue_variation: float = 0.0
    brush_scale: float = 0.15
    paint_variation: float = 0.0
    micro_detail: float = 1.0

    def __post_init__(self) -> None:
        defaults = type(self)
        self.color_steps = int(
            _clamp(int(_default_if_non_finite(self.color_steps, defaults.color_steps)), 2, 32)
        )
        self.color_simplification = float(
            _clamp(
                float(_default_if_non_finite(self.color_simplification, defaults.color_simplification)),
                0.0,
                1.0,
            )
        )
        self.variation_strength = float(
            _clamp(
                float(_default_if_non_finite(self.variation_strength, defaults.variation_strength)),
                0.0,
                1.0,
            )
        )
        self.variation_scale = float(
            _clamp(
                float(_default_if_non_finite(self.variation_scale, defaults.variation_scale)),
                0.01,
                1.0,
            )
        )
        self.contrast = float(
            _clamp(float(_default_if_non_finite(self.contrast, defaults.contrast)), 0.0, 3.0)
        )
        self.saturation = float(
            _clamp(float(_default_if_non_finite(self.saturation, defaults.saturation)), 0.0, 3.0)
        )
        # Phase 2 fields (neutral defaults preserve Phase 1 behavior).
        self.hue_variation = float(
            _clamp(
                float(_default_if_non_finite(self.hue_variation, defaults.hue_variation)),
                0.0,
                1.0,
            )
        )
        self.brush_scale = float(
            _clamp(
                float(_default_if_non_finite(self.brush_scale, defaults.brush_scale)),
                0.01,
                1.0,
            )
        )
        self.paint_variation = float(
            _clamp(
                float(_default_if_non_finite(self.paint_variation, defaults.paint_variation)),
                0.0,
                1.0,
            )
        )
        self.micro_detail = float(
            _clamp(
                float(_default_if_non_finite(self.micro_detail, defaults.micro_detail)),
                0.0,
                1.0,
            )
        )
        self.seed = int(_default_if_non_finite(self.seed, defaults.seed)) % (2**31)
        self.output_resolution = normalize_resolution(self.output_resolution)

    def as_dict(self) -> dict[str, Any]:
        return {field.name: getattr(self, field.name) for field in fields(self)}


def _read(source: Any, name: str) -> Any:
    if isinstance(source, Mapping):
        return source.get(name, _MISSING)
    try:
        return getattr(source, name)
    except AttributeError:
        return _MISSING


def _is_non_finite(value: Any) -> bool:
    """Return ``True`` when *value* is a real number that is not finite.

    Only numeric values are classified. Non-numeric values (strings, arbitrary
    objects) return ``False`` and are left to the normal conversion/fallback
    path so that existing tolerant behavior is preserved. Python ``int`` values
    are always finite and are skipped to avoid needless ``float`` conversion of
    arbitrarily large integers.
    """

    if isinstance(value, bool) or isinstance(value, (int, str, bytes)):
        return False
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return False
    return not math.isfinite(number)


def _coerce(name: str, value: Any) -> Any:
    if name == "output_resolution":
        return normalize_resolution(value)
    if _is_non_finite(value):
        raise ValueError(f"Expected a finite number, got {value!r}.")
    if name in _INT_FIELDS:
        return int(value)
    return float(value)


def adapt_settings(source: Any, base: StylizationSettings | None = None) -> StylizationSettings:
    """Build :class:`StylizationSettings` from a partial/foreign settings object.

    Tolerant synchronization rules:

    * recognized attributes that are present are copied (and coerced);
    * recognized attributes that are missing fall back to ``base``/defaults;
    * unknown attributes are ignored;
    * RNA enum resolutions (``"2048"`` etc.) are normalized;
    * individual malformed values (including ``NaN``/``inf`` numbers) fall
      back to the ``base``/default value for that field.

    Unknown attributes never raise. This is the intended behavior for syncing
    old or partial operator/property state, not a blanket exception handler.
    """

    if base is None:
        base = StylizationSettings()

    resolved: dict[str, Any] = {}
    for field in fields(StylizationSettings):
        name = field.name
        default = getattr(base, name)
        value = _read(source, name)
        if value is _MISSING:
            resolved[name] = default
            continue
        try:
            resolved[name] = _coerce(name, value)
        except (TypeError, ValueError, OverflowError):
            resolved[name] = default

    return StylizationSettings(**resolved)
