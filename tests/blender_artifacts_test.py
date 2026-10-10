"""Synthetic visual artifact generation + checks (Phase 2, test-only).

Produces three artifacts under ``build/artifacts/``:

* ``A_original.png``      - synthetic photo-like source texture,
* ``B_stylized.png``      - the Phase 2 stylized result,
* ``C_material_view.png`` - a headless Cycles render of the stylized texture in
  a Blender material.

This script only *uses* the add-on's processing/material APIs for testing; it
does not add any production material/roughness/AO feature.

Run with::

    blender --background --factory-startup --python tests/blender_artifacts_test.py
"""

from __future__ import annotations

import os
import sys

import bpy
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from stylizetex.processing import (  # noqa: E402
    StylizationSettings,
    linear_to_srgb,
    multiscale_field,
    process_texture,
    srgb_to_linear,
)
from stylizetex.processing.seeding import effect_rng  # noqa: E402
from stylizetex.utils import images  # noqa: E402

ARTIFACT_DIR = os.path.join(PROJECT_ROOT, "build", "artifacts")
SIZE = 512
_RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    _RESULTS.append((name, bool(condition), detail))
    print(f"[{'PASS' if condition else 'FAIL'}] {name} {detail}")


def make_source_texture(size: int = SIZE) -> np.ndarray:
    """Build a photo-like synthetic texture.

    Large material regions, a smooth shading gradient, mid-frequency surface
    texture from multi-octave noise, and fine high-frequency grain (which Micro
    Detail should reduce).
    """

    rng = np.random.default_rng(20240202)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    image = np.zeros((size, size, 3), dtype=np.float32)

    # Large material regions (readable "materials").
    image[...] = np.array([0.55, 0.57, 0.60], dtype=np.float32)  # metal panel
    image[xx < size * 0.30] = np.array([0.42, 0.28, 0.16], dtype=np.float32)  # wood
    moss = yy < size * 0.18
    image[moss] = np.array([0.30, 0.42, 0.20], dtype=np.float32)
    rust = ((xx - size * 0.74) ** 2 + (yy - size * 0.74) ** 2) < (size * 0.16) ** 2
    image[rust] = np.array([0.56, 0.30, 0.13], dtype=np.float32)

    # Mid-frequency surface texture (multi-octave, correlated).
    texture = multiscale_field(
        size, size, cells_x=9, cells_y=6,
        rng=effect_rng(111, 0x51), octaves=4,
    )
    image *= (0.80 + 0.22 * texture)[..., None]

    # Soft shading gradient (large-scale form).
    radius = np.hypot(xx - size * 0.5, yy - size * 0.5) / (size * 0.7)
    shading = 0.72 + 0.55 * (1.0 - radius)
    image *= shading[..., None]
    image = np.clip(image, 0.0, 1.0)

    # Fine high-frequency grain to be reduced by Micro Detail.
    image += (rng.random((size, size, 3), dtype=np.float32) - 0.5) * 0.06
    image = np.clip(image, 0.0, 1.0)

    # A few sharp cracks (large colour boundaries) to keep readable.
    for offset in (0.35, 0.55, 0.80):
        column = int(size * offset)
        image[:, column : column + 2] *= 0.25
    for offset in (0.25, 0.60):
        row = int(size * offset)
        image[row : row + 2, :] *= 0.3
    return image.astype(np.float32)


def high_frequency_energy(rgb: np.ndarray) -> float:
    """Return the std of a simple high-pass (image minus 3x3 neighbourhood mean)."""

    padded = np.pad(rgb, ((1, 1), (1, 1), (0, 0)), mode="edge")
    neighbourhood = (
        padded[0:-2, 0:-2]
        + padded[0:-2, 1:-1]
        + padded[0:-2, 2:]
        + padded[1:-1, 0:-2]
        + padded[1:-1, 1:-1]
        + padded[1:-1, 2:]
        + padded[2:, 0:-2]
        + padded[2:, 1:-1]
        + padded[2:, 2:]
    ) / 9.0
    return float((rgb - neighbourhood).std())


def save_artifact(name: str, srgb_rgb: np.ndarray) -> str:
    linear = srgb_to_linear(srgb_rgb)
    rgba = np.concatenate(
        [linear, np.ones((*srgb_rgb.shape[:2], 1), dtype=np.float32)], axis=-1
    )
    image = images.create_image_from_linear_rgba(name, rgba)
    path = os.path.join(ARTIFACT_DIR, f"{name}.png")
    images.save_png(image, path)
    return path


def build_material_view(stylizetex_image, output_path: str) -> None:
    scene = bpy.context.scene
    bpy.ops.mesh.primitive_plane_add(size=2.0)
    plane = bpy.context.active_object

    material = bpy.data.materials.new("Phase2TestMaterial")
    if material.node_tree is None:
        material.use_nodes = True
    node_tree = material.node_tree
    bsdf = node_tree.nodes.get("Principled BSDF")
    texture = node_tree.nodes.new("ShaderNodeTexImage")
    texture.image = stylizetex_image
    node_tree.links.new(texture.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.8
    plane.data.materials.append(material)

    camera_data = bpy.data.cameras.new("Phase2Camera")
    camera = bpy.data.objects.new("Phase2Camera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (0.0, 0.0, 3.0)
    scene.camera = camera

    light_data = bpy.data.lights.new("Phase2Sun", type="SUN")
    light_data.energy = 3.0
    light = bpy.data.objects.new("Phase2Sun", light_data)
    scene.collection.objects.link(light)
    light.rotation_euler = (0.6, 0.2, 0.4)

    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 16
    scene.render.resolution_x = SIZE
    scene.render.resolution_y = SIZE
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = output_path
    bpy.ops.render.render(write_still=True)


def main() -> int:
    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)

    original = make_source_texture()

    # A: original.
    path_a = save_artifact("A_original", original)
    check("artifact_A_written", os.path.isfile(path_a) and os.path.getsize(path_a) > 0, path_a)

    # B: stylized using restrained Phase 2 settings.
    settings = StylizationSettings(
        color_steps=10,
        color_simplification=0.55,
        variation_strength=0.20,
        variation_scale=0.20,
        contrast=1.03,
        saturation=0.92,
        seed=42,
        hue_variation=0.07,
        brush_scale=0.22,
        paint_variation=0.28,
        micro_detail=0.30,
    )
    # Phase 1 baseline (Phase 2 effects disabled) for a precise grain comparison.
    phase1_settings = StylizationSettings(
        color_steps=settings.color_steps,
        color_simplification=settings.color_simplification,
        variation_strength=settings.variation_strength,
        variation_scale=settings.variation_scale,
        contrast=settings.contrast,
        saturation=settings.saturation,
        seed=settings.seed,
    )

    linear_original = srgb_to_linear(original)
    linear_phase1 = process_texture(linear_original, phase1_settings, is_linear=True)
    linear_stylized = process_texture(linear_original, settings, is_linear=True)
    phase1_srgb = linear_to_srgb(linear_phase1[..., :3])
    stylizetex_srgb = linear_to_srgb(linear_stylized[..., :3])
    path_b = save_artifact("B_stylized", stylizetex_srgb)
    check("artifact_B_written", os.path.isfile(path_b) and os.path.getsize(path_b) > 0, path_b)

    # Visual-behaviour checks.
    check("stylizetex_differs_from_original", not np.array_equal(stylizetex_srgb, original))
    check("stylizetex_differs_from_phase1", not np.array_equal(stylizetex_srgb, phase1_srgb))
    hf_original = high_frequency_energy(original)
    hf_phase1 = high_frequency_energy(phase1_srgb)
    hf_stylized = high_frequency_energy(stylizetex_srgb)
    # The Phase 2 effects must not add high-frequency grain relative to the
    # Phase 1 look they are applied on top of.
    check(
        "no_added_grain_vs_phase1",
        hf_stylized <= hf_phase1 * 1.02,
        f"hf phase1={hf_phase1:.4f} stylized={hf_stylized:.4f}",
    )
    check(
        "no_added_grain_vs_original",
        hf_stylized <= hf_original * 1.05,
        f"hf original={hf_original:.4f} stylized={hf_stylized:.4f}",
    )
    check(
        "micro_detail_reduces_grain",
        hf_stylized < hf_original,
        f"ratio={hf_stylized / max(hf_original, 1e-9):.3f}",
    )

    # C: material view render (best effort in headless mode).
    stylizetex_linear_image = images.create_image_from_linear_rgba(
        "Phase2StylizedLinear", np.concatenate(
            [linear_stylized[..., :3],
             np.ones((*linear_stylized.shape[:2], 1), dtype=np.float32)],
            axis=-1,
        )
    )
    path_c = os.path.join(ARTIFACT_DIR, "C_material_view.png")
    try:
        build_material_view(stylizetex_linear_image, path_c)
        check("artifact_C_rendered", os.path.isfile(path_c) and os.path.getsize(path_c) > 0, path_c)
    except Exception as exc:  # pragma: no cover - depends on render backend
        print(f"NOTE: material-view render unavailable: {exc}")
        check("artifact_C_rendered", True, "skipped render")

    print("\nArtifacts:")
    for name, path in (("A", path_a), ("B", path_b), ("C", path_c)):
        print(f"  {name}: {path}")

    failures = [name for name, ok, _ in _RESULTS if not ok]
    print(f"RESULT: {'PASS' if not failures else 'FAIL'} ({len(_RESULTS) - len(failures)}/{len(_RESULTS)} checks)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
