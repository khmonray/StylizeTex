"""Pure NumPy tests for the deterministic style randomizer."""

from __future__ import annotations

import os
import sys
import unittest
from dataclasses import fields

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from stylized_texture_addon.processing import (  # noqa: E402
    RANDOM_RANGES,
    STYLE_FIELDS,
    StylizationSettings,
    pick_new_seed,
    randomized_style,
)


class RandomizedStyleTests(unittest.TestCase):
    def test_deterministic(self):
        first = randomized_style(1234)
        second = randomized_style(1234)
        self.assertEqual(first.as_dict(), second.as_dict())

    def test_different_seeds_differ(self):
        first = randomized_style(1).as_dict()
        second = randomized_style(2).as_dict()
        self.assertNotEqual(first, second)

    def test_seed_is_stored(self):
        for seed in (0, 7, 12345):
            with self.subTest(seed=seed):
                self.assertEqual(randomized_style(seed).seed, seed)

    def test_whitelist_matches_style_fields(self):
        expected = {
            field.name for field in fields(StylizationSettings) if field.name != "output_resolution"
        }
        self.assertEqual(set(STYLE_FIELDS), expected)

    def test_output_resolution_is_untouched(self):
        settings = randomized_style(9)
        self.assertEqual(settings.output_resolution, StylizationSettings().output_resolution)

    def test_values_are_within_restrained_ranges(self):
        for seed in range(64):
            with self.subTest(seed=seed):
                settings = randomized_style(seed)
                self.assertGreaterEqual(settings.color_steps, 5)
                self.assertLessEqual(settings.color_steps, 12)
                for name, (low, high) in RANDOM_RANGES.items():
                    if name == "color_steps":
                        continue
                    value = getattr(settings, name)
                    self.assertGreaterEqual(value, low - 1e-9, name)
                    self.assertLessEqual(value, high + 1e-9, name)

    def test_ranges_require_effects_to_be_active(self):
        # The randomizer should always enable painterly detail rather than
        # returning the neutral (Phase 1) settings.
        for seed in range(8):
            settings = randomized_style(seed)
            self.assertGreater(settings.paint_variation, 0.0)
            self.assertLess(settings.micro_detail, 1.0)


class PickNewSeedTests(unittest.TestCase):
    def test_seed_differs_from_current(self):
        for current in (0, 1, 12345, 2**31 - 1):
            with self.subTest(current=current):
                candidate = pick_new_seed(current)
                self.assertNotEqual(candidate, current)
                self.assertGreaterEqual(candidate, 0)
                self.assertLess(candidate, 2**31)

    def test_seeds_are_not_constant(self):
        values = {pick_new_seed(0) for _ in range(64)}
        self.assertGreater(len(values), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
