"""Deterministic independent RNG streams for the Phase 2 effects.

The legacy Phase 1 low-frequency variation keeps using ``default_rng(seed)``
directly and is never touched. Every Phase 2 effect instead derives its own
stream from the shared master seed and a fixed effect id using
:class:`numpy.random.SeedSequence`, so streams are independent and stable.
"""

from __future__ import annotations

import numpy as np

# Fixed, arbitrary effect ids. Changing these changes the look of an effect for
# a given seed, so they are treated as part of the format.
HUE_EFFECT_ID = 0x5E1
PAINTERLY_BRIGHTNESS_EFFECT_ID = 0x5E2
PAINTERLY_CHROMA_EFFECT_ID = 0x5E3
PAINTERLY_HUE_EFFECT_ID = 0x5E4

_MASK = 0x7FFFFFFF


def effect_rng(seed: int, effect_id: int) -> np.random.Generator:
    """Return a deterministic generator for ``(seed, effect_id)``.

    The same inputs always yield the same stream; different effect ids yield
    independent streams even for the same seed.
    """

    master = np.random.SeedSequence([int(seed) & _MASK, int(effect_id) & _MASK])
    return np.random.default_rng(master)
