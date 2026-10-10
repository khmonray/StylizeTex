# Changelog

## 0.3.0 — Immediate material application and optional embedding

### Implemented

- Added `Apply to Material`, enabled by default (`True`). After a successful run, the generated image is immediately connected through one marked Image Texture node to the active material's Principled BSDF `Base Color` input.
- Added `Pack into .blend`, disabled by default (`False`). Packing is optional and occurs in addition to writing the external PNG; it never replaces external output.
- Preserved the original source image and source Image Texture node. Only the direct `Base Color` link is redirected; unrelated nodes and links are preserved.
- Repeated processing reuses one marked generated node and result slot, reads the original source instead of the previous generated result, and removes an obsolete generated image when it is unused.
- Disabling `Apply to Material` preserves the material while still creating the generated Blender image and external PNG.
- Packing works for an unsaved `.blend`, but the operator does not auto-save. The user must save the `.blend` manually to persist the packed data and material link; the status reports this reminder.
- External PNG output is always written, including when packing is enabled. Explicit file paths take precedence; otherwise output uses `Output Folder`, the source-image folder, the `.blend` folder, and finally Blender's temporary directory. Invalid or unwritable paths are reported as errors.
- Documented the direct Image Texture → Principled BSDF `Base Color` limitation; indirect shader networks are not resolved.
- `Randomize Style` continues to change only style fields and the seed; `Apply to Material` and `Pack into .blend` behavior flags are preserved.

### Verification

Headless Blender coverage checks default flags, immediate application, disabled-apply behavior, source/unrelated-node preservation, repeated-run reuse, external PNG creation while packed, unsaved-blend packing, rollback on failures, and preservation of the behavior flags during randomization.

## 0.2.0 — Phase 2 and Randomize Style

### Implemented

- Added Phase 2 settings: `Hue Variation`, `Brush Scale`, `Paint Variation`, and `Micro Detail`.
- Added neutral Phase 2 defaults (`hue_variation=0.0`, `paint_variation=0.0`, `micro_detail=1.0`) that preserve the Phase 1 output byte-for-byte.
- Added the exact Phase 2 processing order: scene-linear to sRGB, micro-detail smoothing, color simplification, hue variation, painterly variation, low-frequency variation, contrast, saturation, and sRGB back to scene-linear.
- Added deterministic Phase 2 effect streams derived from the shared `Seed`; alpha remains unchanged.
- Added the `Randomize Style` operator and button. It chooses a new seed, samples restrained style ranges, changes only the style whitelist, preserves resolution/output folder/last-output path, and performs no processing or file I/O.
- Grouped the UI into Source, Output, Color, Large Scale, Painterly, and Seed sections, with Process Texture, Randomize Style, and Reset actions.
- Added Phase 2 and randomizer pure Python tests, Blender operator coverage, and test-only A/B/C visual artifacts.
- Updated packaging/test documentation and retained the legacy and extension ZIP outputs.

### Not implemented

- Phase 3 material features: roughness, AO, curvature, and material generation.
- Phase 4 UX features: preview, presets, and batch processing.
- Masks, geometry-aware processing, and GLB export.
- No visual-quality claim is made by this release.

### Compatibility and verification

The repository's tested Blender target is **5.2.1**. `bl_info` and `blender_manifest.toml` declare **4.2.0** as the minimum. Versions outside the tested target are unverified.

Pure tests can be run with `python -m unittest discover -s tests -p "test_*.py" -v`; the combined runner is `python scripts/run_tests.py`. Packaging uses `python scripts/package.py`. Outputs are `build/stylized_texture_addon-legacy.zip` and `build/stylized_texture_addon-extension.zip`; test-only images are under `build/artifacts/`.

## 0.1.0 — Phase 1

### Implemented

- Added the `Stylized Texture` View3D sidebar panel.
- Added validation for Object Mode, an active mesh, an active UV map, an active material, an active Principled BSDF output, and a direct Image Texture link to Base Color.
- Added the Phase 1 pipeline: color simplification, smooth low-frequency variation, contrast, and saturation.
- Added scene-linear/sRGB conversion with untouched alpha handling.
- Added bilinear resizing that fits the requested longest-side resolution while preserving aspect ratio.
- Added settings defaults, range clamping, resolution normalization, deterministic seed handling, and tolerant synchronization of partial settings.
- Added creation of a new Blender image data-block and PNG output without modifying the source image or unrelated material nodes and links.
- Added output-folder fallback resolution and sanitized `<object>_stylized_basecolor.png` filenames.
- Added a reset-settings operator.
- Added classic legacy ZIP and Blender extension ZIP packaging.
- Kept registration safe when Blender extension loading strips `bl_info`.
- Added pure NumPy tests and headless Blender tests for registration, processing, non-mutation, namespace loading, and installation paths.

### Compatibility note

The repository's test target is Blender 5.2.1. The current metadata declares Blender 4.2.0 as the minimum; versions outside the tested target are unverified.
