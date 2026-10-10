"""Exact Phase 1 regression for the Phase 2 pipeline.

With the Phase 2 effects at their neutral defaults the pipeline must reproduce
the frozen Phase 1 outputs byte-for-byte. The fixture in ``tests/fixtures`` was
generated from the pre-Phase-2 implementation.
"""

from __future__ import annotations

import os
import sys
import unittest

import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from stylized_texture_addon.processing import StylizationSettings, process_texture  # noqa: E402

FIXTURE = os.path.join(PROJECT_ROOT, "tests", "fixtures", "phase1_reference.npz")


class Phase1ExactRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.isfile(FIXTURE):
            raise unittest.SkipTest(f"missing Phase 1 fixture: {FIXTURE}")
        cls.data = np.load(FIXTURE)
        cls.cases = sorted(
            key[: -len("__input")] for key in cls.data.files if key.endswith("__input")
        )

    def _settings_from_config(self, name: str) -> StylizationSettings:
        config = self.data[f"{name}__config"]
        return StylizationSettings(
            color_steps=int(config[0]),
            color_simplification=float(config[1]),
            variation_strength=float(config[2]),
            variation_scale=float(config[3]),
            contrast=float(config[4]),
            saturation=float(config[5]),
            seed=int(config[6]),
        )

    def test_all_cases_reproduce_exactly(self):
        self.assertGreater(len(self.cases), 0)
        for name in self.cases:
            with self.subTest(case=name):
                source = self.data[f"{name}__input"]
                expected = self.data[f"{name}__output"]
                is_linear = bool(self.data[f"{name}__is_linear"][0])
                result = process_texture(
                    source, self._settings_from_config(name), is_linear=is_linear
                )
                np.testing.assert_array_equal(result, expected)

    def test_neutral_defaults_match_phase1_defaults(self):
        settings = StylizationSettings()
        self.assertEqual(settings.hue_variation, 0.0)
        self.assertEqual(settings.paint_variation, 0.0)
        self.assertEqual(settings.micro_detail, 1.0)

    def test_positional_phase1_fields_preserved(self):
        settings = StylizationSettings(4, 0.5, 0.2, 0.3, 1.1, 0.8, 77, 1024)
        self.assertEqual(settings.color_steps, 4)
        self.assertEqual(settings.seed, 77)
        self.assertEqual(settings.output_resolution, 1024)
        self.assertEqual(settings.hue_variation, 0.0)
        self.assertEqual(settings.brush_scale, 0.15)
        self.assertEqual(settings.paint_variation, 0.0)
        self.assertEqual(settings.micro_detail, 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
