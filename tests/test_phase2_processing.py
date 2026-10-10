"""Pure NumPy tests for the Phase 2 effects (hue, painterly, micro detail)."""

from __future__ import annotations

import os
import sys
import unittest

import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from stylizetex.processing import (  # noqa: E402
    StylizationSettings,
    adapt_settings,
    apply_hue_variation,
    apply_micro_detail,
    apply_painterly_variation,
    effect_rng,
    hsv_to_rgb,
    painterly_field,
    process_texture,
    rgb_to_hsv,
    stroke_cells,
)


def _random(h=48, w=40, c=3, seed=0):
    return np.random.default_rng(seed).random((h, w, c), dtype=np.float32)


class HSVTests(unittest.TestCase):
    def test_roundtrip_is_close(self):
        source = _random()
        roundtrip = hsv_to_rgb(rgb_to_hsv(source))
        np.testing.assert_allclose(roundtrip, source, atol=1e-5)

    def test_greys_convert_to_zero_saturation(self):
        grey = np.full((4, 4, 3), 0.42, dtype=np.float32)
        hsv = rgb_to_hsv(grey)
        np.testing.assert_allclose(hsv[..., 1], 0.0, atol=1e-6)
        np.testing.assert_allclose(hsv[..., 2], 0.42, atol=1e-6)


class MicroDetailTests(unittest.TestCase):
    def test_one_is_exact_identity(self):
        source = _random(seed=1)
        result = apply_micro_detail(source, 1.0)
        np.testing.assert_array_equal(result, source)

    def test_high_frequency_noise_is_reduced(self):
        source = np.full((64, 64, 3), 0.5, dtype=np.float32)
        noise = (np.random.default_rng(2).random((64, 64, 3), dtype=np.float32) - 0.5) * 0.06
        noisy = np.clip(source + noise, 0.0, 1.0)
        smoothed = apply_micro_detail(noisy, 0.0)
        self.assertLess(float(smoothed.std()), float(noisy.std()) * 0.5)

    def test_large_color_boundaries_are_preserved(self):
        image = np.zeros((48, 48, 3), dtype=np.float32)
        image[:, :24] = np.array([0.9, 0.1, 0.1], dtype=np.float32)
        image[:, 24:] = np.array([0.1, 0.1, 0.9], dtype=np.float32)
        noise = (np.random.default_rng(3).random((48, 48, 3), dtype=np.float32) - 0.5) * 0.03
        smoothed = apply_micro_detail(np.clip(image + noise, 0, 1), 0.0)
        left = smoothed[:, :20, 0].mean()
        right = smoothed[:, -20:, 0].mean()
        self.assertGreater(float(left - right), 0.5)

    def test_alpha_is_preserved_with_rgba(self):
        source = _random(c=4, seed=4)
        result = apply_micro_detail(source, 0.0)
        np.testing.assert_array_equal(result[..., 3], source[..., 3])

    def test_alpha_weight_is_used_for_rgb_input(self):
        rgb = np.zeros((8, 8, 3), dtype=np.float32)
        rgb[:, :4] = 0.9
        alpha = np.zeros((8, 8, 1), dtype=np.float32)
        alpha[:, :4] = 1.0
        result = apply_micro_detail(rgb, 0.0, alpha=alpha)
        self.assertEqual(result.shape, rgb.shape)

    def test_alpha_influences_smoothing(self):
        # Two regions with a subtle colour ramp; an alpha edge between them must
        # change the smoothing result (proving alpha participates in weights).
        yy, xx = np.mgrid[0:16, 0:16].astype(np.float32)
        rgb = np.clip(0.4 + 0.2 * (xx / 15.0), 0.0, 1.0)[..., None].repeat(3, axis=-1)
        alpha = np.ones((16, 16, 1), dtype=np.float32)
        alpha[:, 8:] = 0.0
        with_alpha = apply_micro_detail(rgb, 0.0, alpha=alpha)
        without_alpha = apply_micro_detail(rgb, 0.0)
        self.assertFalse(np.array_equal(with_alpha, without_alpha))

    def test_rgba_uses_internal_alpha(self):
        rgb = np.clip(0.4 + 0.2 * (np.mgrid[0:16, 0:16][1].astype(np.float32) / 15.0), 0, 1)
        rgb = rgb[..., None].repeat(3, axis=-1)
        alpha = np.ones((16, 16, 1), dtype=np.float32)
        alpha[:, 8:] = 0.0
        rgba = np.concatenate([rgb, alpha], axis=-1)
        rgba_result = apply_micro_detail(rgba, 0.0)
        rgb_result = apply_micro_detail(rgb, 0.0)
        self.assertFalse(np.array_equal(rgba_result[..., :3], rgb_result))


class HueVariationTests(unittest.TestCase):
    def test_zero_amount_is_identity(self):
        source = _random(seed=5)
        result = apply_hue_variation(source, 0.0, 1)
        np.testing.assert_array_equal(result, source)

    def test_neutral_greys_are_preserved(self):
        grey = np.full((16, 16, 3), 0.5, dtype=np.float32)
        result = apply_hue_variation(grey, 0.12, 7)
        np.testing.assert_allclose(result, grey, atol=1e-6)

    def test_deterministic_for_same_seed(self):
        source = _random(seed=6)
        first = apply_hue_variation(source, 0.1, 11)
        second = apply_hue_variation(source, 0.1, 11)
        np.testing.assert_array_equal(first, second)

    def test_changes_with_seed(self):
        source = _random(seed=7)
        first = apply_hue_variation(source, 0.1, 11)
        second = apply_hue_variation(source, 0.1, 12)
        self.assertFalse(np.array_equal(first, second))

    def test_changes_colored_input(self):
        source = _random(seed=8)
        result = apply_hue_variation(source, 0.12, 3)
        self.assertFalse(np.array_equal(result, source))

    def test_output_is_finite_and_bounded(self):
        source = _random(seed=9)
        result = apply_hue_variation(source, 1.0, 3)
        self.assertTrue(np.isfinite(result).all())
        self.assertGreaterEqual(float(result.min()), 0.0)
        self.assertLessEqual(float(result.max()), 1.0)


class PainterlyTests(unittest.TestCase):
    def test_zero_variation_is_identity(self):
        source = _random(seed=10)
        result = apply_painterly_variation(source, 0.0, 0.15, 1)
        np.testing.assert_array_equal(result, source)

    def test_deterministic_for_same_seed(self):
        source = _random(seed=11)
        first = apply_painterly_variation(source, 0.3, 0.2, 5)
        second = apply_painterly_variation(source, 0.3, 0.2, 5)
        np.testing.assert_array_equal(first, second)

    def test_changes_with_seed(self):
        source = _random(seed=12)
        first = apply_painterly_variation(source, 0.3, 0.2, 5)
        second = apply_painterly_variation(source, 0.3, 0.2, 6)
        self.assertFalse(np.array_equal(first, second))

    def test_larger_brush_produces_larger_strokes(self):
        small = painterly_field(96, 96, 0.08, 5)
        large = painterly_field(96, 96, 0.30, 5)

        def adjacent_difference(field):
            return float(np.abs(field[:, 1:] - field[:, :-1]).mean())

        self.assertLess(adjacent_difference(large), adjacent_difference(small))

    def test_stroke_cells_decrease_with_brush(self):
        small_cells = stroke_cells(0.08)
        large_cells = stroke_cells(0.30)
        self.assertGreater(small_cells[0], large_cells[0])

    def test_stroke_cells_upper_range_has_no_plateau(self):
        # Regression: ``round(1 / safe)`` combined with a floor of 2 cells made
        # the entire upper half of the range (0.5..1.0) collapse to the same
        # 2x1 lattice. Every step must now map to a strictly larger stroke.
        values = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        cells = [stroke_cells(value)[0] for value in values]
        self.assertEqual(cells, sorted(cells, reverse=True))
        self.assertEqual(len(set(cells)), len(cells))
        self.assertNotEqual(stroke_cells(0.5), stroke_cells(1.0))
        self.assertNotEqual(stroke_cells(0.6), stroke_cells(1.0))

    def test_stroke_cells_are_continuous_and_bounded(self):
        # A continuous mapping stays within a sane cell budget (no huge lattice)
        # and never drops below a single cell on either axis.
        for value in np.linspace(0.01, 1.0, 200):
            cells_x, cells_y = stroke_cells(float(value))
            self.assertGreaterEqual(cells_x, 1.0)
            self.assertGreaterEqual(cells_y, 1.0)
            self.assertLessEqual(cells_x, 100.0)

    def test_upper_brush_range_changes_field(self):
        # The whole point of the fix: 0.5, 0.6 and 1.0 must produce visibly
        # different strokes rather than identical fields.
        for seed in range(6):
            with self.subTest(seed=seed):
                half = painterly_field(96, 96, 0.5, seed)
                mid = painterly_field(96, 96, 0.6, seed)
                full = painterly_field(96, 96, 1.0, seed)
                self.assertFalse(np.array_equal(half, full))
                self.assertFalse(np.array_equal(mid, full))
                self.assertGreater(float(np.abs(mid - full).mean()), 0.1)

    def test_upper_brush_range_correlation_is_not_identity(self):
        # Distinct brush sizes must not share (almost) the same field.
        for seed in range(6):
            with self.subTest(seed=seed):
                mid = painterly_field(96, 96, 0.6, seed)
                full = painterly_field(96, 96, 1.0, seed)
                correlation = abs(float(np.corrcoef(mid.ravel(), full.ravel())[0, 1]))
                self.assertLess(correlation, 0.9)

    def test_upper_brush_range_larger_brush_is_smoother(self):
        # Averaged over seeds, a larger brush (1.0) yields larger, smoother
        # strokes than a smaller one (0.6).
        def mean_adjacent_difference(brush_scale):
            values = [
                float(np.abs(field[:, 1:] - field[:, :-1]).mean())
                for field in (
                    painterly_field(96, 96, brush_scale, seed) for seed in range(8)
                )
            ]
            return float(np.mean(values))

        self.assertLess(
            mean_adjacent_difference(1.0), mean_adjacent_difference(0.6)
        )

    def test_upper_brush_range_no_per_pixel_grain(self):
        for brush_scale in (0.6, 1.0):
            with self.subTest(brush_scale=brush_scale):
                field = painterly_field(96, 96, brush_scale, 5)
                adjacent = float(np.abs(field[:, 1:] - field[:, :-1]).mean())
                self.assertLess(adjacent, 0.15)

    def test_no_per_pixel_grain(self):
        # A smooth field must not explode into per-pixel noise: the average
        # neighbour difference stays far below the field's own range.
        field = painterly_field(96, 96, 0.15, 5)
        adjacent = float(np.abs(field[:, 1:] - field[:, :-1]).mean())
        self.assertLess(adjacent, 0.15)

    def test_output_is_finite_and_bounded(self):
        source = _random(seed=13)
        result = apply_painterly_variation(source, 1.0, 0.5, 9)
        self.assertTrue(np.isfinite(result).all())
        self.assertGreaterEqual(float(result.min()), 0.0)
        self.assertLessEqual(float(result.max()), 1.0)


class SeedingTests(unittest.TestCase):
    def test_effect_rng_is_deterministic(self):
        first = effect_rng(42, 100).random(8, dtype=np.float32)
        second = effect_rng(42, 100).random(8, dtype=np.float32)
        np.testing.assert_array_equal(first, second)

    def test_effect_ids_are_independent(self):
        first = effect_rng(42, 100).random(8, dtype=np.float32)
        second = effect_rng(42, 101).random(8, dtype=np.float32)
        self.assertFalse(np.array_equal(first, second))

    def test_old_variation_stream_is_untouched(self):
        # ``variation.low_frequency_field`` still uses ``default_rng(seed)``
        # directly; the Phase 2 helper must not share that stream.
        from stylizetex.processing import low_frequency_field

        legacy_a = low_frequency_field(16, 16, 0.25, seed=3)
        legacy_b = low_frequency_field(16, 16, 0.25, seed=3)
        np.testing.assert_array_equal(legacy_a, legacy_b)
        new_stream = effect_rng(3, 0x5E1).random(16 * 16, dtype=np.float32).reshape(16, 16)
        self.assertFalse(np.array_equal(legacy_a, new_stream))


class PipelinePhase2Tests(unittest.TestCase):
    def _sample(self, seed=0):
        return _random(32, 24, 4, seed=seed)

    def test_full_effects_deterministic(self):
        settings = StylizationSettings(
            seed=21, hue_variation=0.1, brush_scale=0.2, paint_variation=0.3, micro_detail=0.3
        )
        first = process_texture(self._sample(), settings)
        second = process_texture(self._sample(), settings)
        np.testing.assert_array_equal(first, second)

    def test_effects_change_with_seed(self):
        first = process_texture(
            self._sample(),
            StylizationSettings(seed=1, paint_variation=0.3, hue_variation=0.1),
        )
        second = process_texture(
            self._sample(),
            StylizationSettings(seed=2, paint_variation=0.3, hue_variation=0.1),
        )
        self.assertFalse(np.array_equal(first, second))

    def test_effects_change_output_when_enabled(self):
        neutral = process_texture(self._sample(), StylizationSettings(seed=5))
        effect = process_texture(
            self._sample(),
            StylizationSettings(seed=5, paint_variation=0.3, micro_detail=0.3, hue_variation=0.1),
        )
        self.assertFalse(np.array_equal(neutral, effect))

    def test_alpha_identity_and_input_not_mutated(self):
        source = self._sample(seed=6)
        original = source.copy()
        settings = StylizationSettings(
            seed=6, hue_variation=0.1, paint_variation=0.3, micro_detail=0.3
        )
        result = process_texture(source, settings)
        np.testing.assert_array_equal(source, original)
        np.testing.assert_array_equal(result[..., 3], source[..., 3])

    def test_non_contiguous_input(self):
        big = _random(48, 48, 4, seed=7)
        view = big[::2, ::2, :]
        self.assertFalse(view.flags["C_CONTIGUOUS"])
        result = process_texture(view, StylizationSettings(seed=7, paint_variation=0.2))
        self.assertEqual(result.shape, view.shape)
        self.assertTrue(np.isfinite(result).all())

    def test_non_square_shapes(self):
        for shape in ((3, 17), (17, 3), (1, 12), (12, 1)):
            with self.subTest(shape=shape):
                source = np.random.default_rng(8).random((*shape, 3), dtype=np.float32)
                result = process_texture(
                    source,
                    StylizationSettings(seed=8, hue_variation=0.1, paint_variation=0.2, micro_detail=0.2),
                )
                self.assertEqual(result.shape, source.shape)

    def test_tiny_images(self):
        for shape in ((1, 1, 3), (2, 1, 3), (1, 2, 3)):
            with self.subTest(shape=shape):
                source = np.full(shape, 0.4, dtype=np.float32)
                result = process_texture(
                    source,
                    StylizationSettings(seed=1, hue_variation=0.1, paint_variation=0.2, micro_detail=0.2),
                )
                self.assertEqual(result.shape, source.shape)
                self.assertTrue(np.isfinite(result).all())

    def test_constant_input_stays_constant_without_phase2(self):
        source = np.full((8, 8, 3), 0.42, dtype=np.float32)
        result = process_texture(
            source,
            StylizationSettings(
                color_simplification=0.0,
                variation_strength=0.0,
                contrast=1.0,
                saturation=1.0,
            ),
            is_linear=True,
        )
        np.testing.assert_allclose(result, source, atol=2e-2)

    def test_greys_stay_grey_with_hue_variation(self):
        source = np.full((16, 16, 3), 0.5, dtype=np.float32)
        result = process_texture(
            source,
            StylizationSettings(
                color_simplification=0.0,
                variation_strength=0.0,
                contrast=1.0,
                saturation=1.0,
                hue_variation=0.12,
            ),
            is_linear=True,
        )
        np.testing.assert_allclose(result[..., 0], result[..., 1], atol=2e-3)
        np.testing.assert_allclose(result[..., 1], result[..., 2], atol=2e-3)

    def test_extremes_are_finite_and_bounded(self):
        for value in (0.0, 1.0):
            with self.subTest(value=value):
                source = np.full((6, 6, 3), value, dtype=np.float32)
                result = process_texture(
                    source,
                    StylizationSettings(seed=1, hue_variation=0.12, paint_variation=0.35, micro_detail=0.15),
                )
                self.assertTrue(np.isfinite(result).all())
                self.assertGreaterEqual(float(result.min()), 0.0)
                self.assertLessEqual(float(result.max()), 1.0)

    def test_micro_detail_blending_endpoint_matches_manual_smooth(self):
        source = _random(24, 24, 3, seed=14)
        smooth = apply_micro_detail(source, 0.0)
        blended = apply_micro_detail(source, 0.5)
        np.testing.assert_allclose(blended, smooth + (source - smooth) * 0.5, atol=1e-6)


class AdapterPhase2Tests(unittest.TestCase):
    def test_phase2_fields_roundtrip(self):
        settings = adapt_settings(
            {
                "hue_variation": 0.1,
                "brush_scale": 0.2,
                "paint_variation": 0.3,
                "micro_detail": 0.4,
            }
        )
        self.assertAlmostEqual(settings.hue_variation, 0.1, places=5)
        self.assertAlmostEqual(settings.brush_scale, 0.2, places=5)
        self.assertAlmostEqual(settings.paint_variation, 0.3, places=5)
        self.assertAlmostEqual(settings.micro_detail, 0.4, places=5)

    def test_phase2_fields_clamped(self):
        settings = adapt_settings(
            {
                "hue_variation": 5.0,
                "brush_scale": -1.0,
                "paint_variation": 9.0,
                "micro_detail": -2.0,
            }
        )
        self.assertEqual(settings.hue_variation, 1.0)
        self.assertEqual(settings.brush_scale, 0.01)
        self.assertEqual(settings.paint_variation, 1.0)
        self.assertEqual(settings.micro_detail, 0.0)

    def test_phase2_non_finite_falls_back(self):
        defaults = StylizationSettings()
        for name in ("hue_variation", "brush_scale", "paint_variation", "micro_detail"):
            for value in (float("inf"), float("-inf"), float("nan")):
                with self.subTest(field=name, value=value):
                    settings = adapt_settings({name: value})
                    self.assertEqual(getattr(settings, name), getattr(defaults, name))

    def test_missing_phase2_fields_use_base(self):
        base = StylizationSettings(hue_variation=0.3, brush_scale=0.25, paint_variation=0.4, micro_detail=0.2)
        settings = adapt_settings({}, base=base)
        self.assertEqual(settings.hue_variation, 0.3)
        self.assertEqual(settings.brush_scale, 0.25)
        self.assertEqual(settings.paint_variation, 0.4)
        self.assertEqual(settings.micro_detail, 0.2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
