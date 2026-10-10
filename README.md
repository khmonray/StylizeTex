# Stylized Texture Processor

Blender add-on that reads the Base Color image from the active material of the active UV-mapped mesh, processes it, saves a new PNG, and by default connects the generated image to the material. The source image, source node, and unrelated material nodes and links are preserved. This documentation describes the implementation that exists in this repository; it does not promise a particular visual quality.

Author: github.com/khmonray

## Implemented scope: Phase 1 and Phase 2

The implemented pipeline is:

```text
Input image
    ↓
Scene-linear → sRGB conversion
    ↓
Micro Detail smoothing (Phase 2; skipped at 1.0)
    ↓
Color Simplification
    ↓
Hue Variation (Phase 2; skipped at 0.0)
    ↓
Painterly Variation (Phase 2; skipped at 0.0)
    ↓
Smooth low-frequency variation
    ↓
Contrast
    ↓
Saturation
    ↓
sRGB → scene-linear conversion
    ↓
New image + PNG
```

Phase 2 adds `Hue Variation`, `Brush Scale`, `Paint Variation`, and `Micro Detail`. Its neutral defaults preserve the Phase 1 result byte-for-byte: `hue_variation=0.0`, `paint_variation=0.0`, and `micro_detail=1.0`. `Brush Scale` is used by Painterly Variation and has no effect while `Paint Variation` is zero.

The operator creates a new Blender image data-block and always writes an external PNG. By default it immediately connects the generated image to the active material's Principled BSDF **Base Color** input. The original source image and source node remain available; only that Base Color link is redirected.

Not implemented: Phase 3 material features (roughness, AO, curvature, and material generation) or Phase 4 UX features (preview, presets, and batch processing). Masks, geometry-aware shading, and GLB export are also not implemented.

## Supported Blender versions

- The repository's tested Blender target is **5.2.1**.
- The current `bl_info` and `blender_manifest.toml` declare a minimum of **4.2.0**. Versions below 4.2 and versions other than the tested target are unverified.
- The extension manifest requires Blender 4.2 or newer. The classic legacy add-on path is separate.

## Installation

### Legacy add-on ZIP

Use `build/stylized_texture_addon-legacy.zip`. This archive contains a top-level `stylized_texture_addon/` folder and the literal `bl_info` metadata used by Blender's classic add-on system.

1. In Blender, open **Edit > Preferences > Add-ons**.
2. Choose **Install...** and select `stylized_texture_addon-legacy.zip`.
3. Enable **Stylized Texture Processor**.

### Blender extension ZIP

Use `build/stylized_texture_addon-extension.zip`. This archive has `blender_manifest.toml` at its root and is intended for Blender's extension workflow.

Install it through Blender's **Preferences > Get Extensions** interface using the install-from-disk option, or use the extension commands appropriate to the installed Blender version. Do not install the extension archive as a classic add-on if Blender expects an extension package.

The packaging script uses Blender's `extension build` command when a Blender executable is available; otherwise it writes a manual ZIP with the same package files.

## User interface and usage

After enabling the add-on, open the 3D Viewport sidebar with `N` and select the **Stylized Texture** tab. The panel is registered in `View3D > Sidebar > Stylized Texture`.

The panel is grouped as follows:

- **Source**: active object and detected Base Color image.
- **Output**: `Resolution`, `Output Folder`, `Apply to Material` (default `True`), and `Pack into .blend` (default `False`).
- **Style / Color**: color simplification, color steps, contrast, and saturation.
- **Style / Large Scale**: variation strength and variation scale.
- **Style / Painterly**: brush scale, paint variation, micro detail, and hue variation.
- **Style / Seed**: the shared seed.
- Actions: **Process Texture**, **Randomize Style**, and **Reset**. When available, the last saved output path is shown below the actions.

Required input for **Process Texture**:

1. Work in Object Mode.
2. Select a mesh object with an active UV map.
3. Ensure it has an active material.
4. In the active material, use a node-based Principled BSDF connected to the active Material Output.
5. Connect an **Image Texture** node directly to the Principled BSDF **Base Color** input.
6. Set the output settings and parameters in the panel.
7. Press **Process Texture**.

The validator accepts only that direct Image Texture → Principled BSDF Base Color link. It does not resolve a texture through color nodes, groups, mixes, or other shader networks. If a previous run's generated node is connected, processing unwraps it and reads the recorded original source instead of feeding the generated result back into the pipeline. The operator also validates the output directory and reports path or permission errors in the UI; unexpected exceptions are printed to the Blender Console.

### Randomize Style

**Randomize Style** chooses a new operating-system-random seed that differs from the current seed, then samples a restrained style from that seed. It changes only the style whitelist: `Color Steps`, `Color Simplification`, `Variation Strength`, `Variation Scale`, `Contrast`, `Saturation`, `Seed`, `Hue Variation`, `Brush Scale`, `Paint Variation`, and `Micro Detail`. `Resolution`, `Output Folder`, and the scene's last-output path are preserved.

The action performs no image processing, creates no Blender images or materials, does no file I/O, and does not require a selected mesh. It only changes the settings; press **Process Texture** separately to produce output. The pure randomizer is deterministic for a supplied seed, while the button obtains a new seed on each invocation.

### Applying and packing the result

With **Apply to Material** enabled (the default), processing immediately connects the generated image through one marked **Image Texture** node to the active material's Principled BSDF **Base Color**. The existing source Image Texture node and image are kept, and only the Base Color link is changed. Other nodes and links are not changed.

Repeated processing reuses the same marked generated node and replaces its generated image, while continuing to read the original source. It does not accumulate generated nodes or feed a previous result back into processing.

Disable **Apply to Material** to preserve the active material exactly as-is. The new Blender image and external PNG are still created, but the generated image is not connected.

Enable **Pack into .blend** to pack the generated image in addition to writing the external PNG; the external file is always created. Packing does not save the `.blend` automatically. Save the `.blend` manually to persist the material link and packed image. Packing also works for an unsaved blend and the status reports the save reminder.

## Output behavior

The output is a new image and an external PNG. The default filename is `<object>_stylized_basecolor.png`; object names are sanitized for filesystem use. An explicit operator file path overrides the output-folder setting.

If **Output Folder** is empty, the add-on falls back in order to the source image folder, the `.blend` file folder, and Blender's temporary directory. This last fallback is used for an unsaved blend when no usable source-image folder exists. Existing files may be overwritten when the resolved filename is the same; the implementation does not add a unique suffix to disk filenames. An invalid, inaccessible, or unwritable output path cancels processing and reports an error. Each processing run creates a new image data-block; with apply enabled it replaces the previous generated result in the material, while the input source image and unrelated material data remain preserved.

### Resolution and aspect ratio

The UI offers `512`, `1024`, `2048`, and `4096`. The selected value is the target length of the **longest side**, not a forced square output. The other side is scaled proportionally and rounded to at least one pixel using bilinear resampling. For example, a 1024×512 source at target 2048 becomes 2048×1024; a square source becomes square.

## Parameters

| Parameter | Default | Range / choices | Effect |
| --- | ---: | --- | --- |
| Resolution | 2048 | 512, 1024, 2048, 4096 | Longest output side; aspect ratio is preserved. |
| Output Folder | empty | Directory path | Folder for the saved PNG; empty uses the fallback chain above. |
| Apply to Material | True | Boolean | Immediately connect the generated image to Base Color; when false, preserve the material. |
| Pack into .blend | False | Boolean | Pack the generated image in addition to the external PNG; does not auto-save the blend. |
| Color Steps | 8 | 2–32 | Number of tonal groups used by color simplification. |
| Color Simplification | 0.70 | 0.0–1.0 | Blend strength of color simplification. |
| Variation Strength | 0.25 | 0.0–1.0 | Strength of smooth low-frequency color variation. |
| Variation Scale | 0.15 | 0.01–1.0 | Relative size of low-frequency color blobs. |
| Contrast | 1.05 | 0.0–3.0 | Contrast multiplier around mid-grey. |
| Saturation | 0.90 | 0.0–3.0 | Saturation multiplier. |
| Seed | 12345 | 0–2147483647 | Shared master seed for deterministic procedural variation. |
| Hue Variation | 0.0 | 0.0–1.0 | Bounded hue shift applied to colored areas; neutral at 0.0. |
| Brush Scale | 0.15 | 0.01–1.0 | Relative size of painterly strokes; used by Painterly Variation. |
| Paint Variation | 0.0 | 0.0–1.0 | Painterly brightness, saturation, and hue variation; neutral at 0.0. |
| Micro Detail | 1.0 | 0.0–1.0 | Amount of fine original detail retained; 1.0 is neutral/full detail, 0.0 is strongest smoothing. |

Phase 2 neutral defaults are deliberately compatible with Phase 1. Values supplied through old or partial settings objects are synchronized tolerantly: missing recognized fields use defaults (or a supplied base), unknown fields are ignored, and malformed individual values fall back to that field's default before clamping.

## Color management and reproducibility

The processing pipeline expects Blender image pixels as scene-linear float RGB/RGBA. It converts RGB to sRGB, applies the operations in the order shown above, then converts RGB back to scene-linear. Alpha, when present, is preserved untouched. Output values are clipped to `[0, 1]` and saved as an sRGB PNG by the Blender image API.

For the same input pixels, settings, and seed, the processing result is deterministic. Phase 2 uses independent deterministic random streams derived from the master seed for hue and painterly effects; the existing Phase 1 low-frequency variation stream remains unchanged. Changing the seed can produce a different procedural result. This is an implementation description, not a claim that every source color-management setup will look identical in every Blender display transform.

## Recommended workflow

```text
Install the add-on
    ↓
Select a UV-mapped mesh
    ↓
Check its active material and direct Base Color image link
    ↓
Choose output resolution and folder
    ↓
Adjust Phase 1/Phase 2 parameters
    ↓
Optionally press Randomize Style
    ↓
Press Process Texture
    ↓
Inspect the new PNG
    ↓
Confirm the generated image is connected (or leave Apply to Material disabled)
    ↓
Optionally enable Pack into .blend
    ↓
Save the .blend manually if the packed data or material link must persist
```

The planned workflow in `document.txt` mentions material generation, AO, roughness, preview, presets, bake, and GLB export. Those steps are not implemented by this repository version.

## Known limitations

- Only the active object, active material, active output, Principled BSDF, and direct Base Color image are considered.
- A UV map is required for validation, although the processing itself operates on the image rather than baking mesh coordinates.
- Phase 3 material features—roughness, AO, curvature, and material generation—are not implemented.
- Phase 4 preview, presets, and batch processing are not implemented.
- The material target is limited to a direct Image Texture → Principled BSDF Base Color link; textures routed through other shader networks are rejected.
- Packing does not auto-save the `.blend`; the user must save it manually.
- The add-on processes one image per **Process Texture** invocation.
- Disk output uses a deterministic filename and can overwrite an existing file with that name.
- The declared Blender minimum is 4.2.0; compatibility outside tested Blender 5.2.1 is unverified.
- No visual-quality guarantee is made; image suitability and the result must be evaluated in the target material.

## Architecture

```text
stylized_texture_addon/
├── __init__.py                 registration, legacy metadata, safe extension loading
├── operators/
│   ├── process.py              validation, resize, pipeline, image creation, PNG save
│   ├── randomize.py            Randomize Style operator
│   └── reset.py                restore UI defaults
├── panels/main_panel.py        View3D sidebar panel and UI grouping
├── properties/settings.py      Blender RNA properties and defaults
├── processing/
│   ├── settings.py             Blender-independent settings and tolerant adapter
│   ├── pipeline.py             Phase 1/Phase 2 pipeline and color-space handling
│   ├── randomize.py             deterministic style sampling and whitelist
│   ├── seeding.py              independent Phase 2 RNG streams
│   ├── resize.py               bilinear resize and aspect-preserving fit
│   ├── color.py                color conversions and color operations
│   ├── hue.py                  hue variation
│   ├── painterly.py            painterly variation
│   ├── micro_detail.py         detail smoothing
│   ├── variation.py            deterministic low-frequency field
│   └── validate.py              NumPy array validation
├── utils/
│   ├── materials.py           marker-based generated-image material assignment and cleanup
│   ├── validation.py           Blender scene/input validation
│   ├── images.py               Blender image pixel conversion and PNG I/O
│   └── paths.py                output path and filename resolution
└── blender_manifest.toml       Blender extension metadata
```

## Tests, commands, and artifacts

Build both archives:

```text
python scripts/package.py
```

Build one archive:

```text
python scripts/package.py --legacy-only
python scripts/package.py --extension-only
python scripts/package.py --blender /path/to/blender
```

Run the combined runner (packaging, pure Python tests, and Blender tests when Blender is available):

```text
python scripts/run_tests.py
python scripts/run_tests.py --python python --blender /path/to/blender
python scripts/run_tests.py --skip-pure --skip-blender
```

Run pure tests directly:

```text
python -m unittest discover -s tests -p "test_*.py" -v
```

The pure tests cover Phase 1 regression, Phase 2 HSV/hue, micro-detail and painterly processing, deterministic seeding, settings adaptation, and Randomize Style sampling. Blender tests include the `blender-materials` suite for material application, packing, and rollback, as well as registration cycles, processing, non-mutation of source/material data, Randomize Style preservation and no-processing behavior, metadata-stripped loading, legacy installation, extension installation/validation, and synthetic A/B/C artifacts.

The generated packaging artifacts are `build/stylized_texture_addon-legacy.zip` and `build/stylized_texture_addon-extension.zip`. The test-only visual artifacts are `build/artifacts/A_original.png`, `build/artifacts/B_stylized.png`, and `build/artifacts/C_material_view.png`.

Actual Blender-version compatibility remains subject to running these tests with that Blender executable; the repository test target is Blender 5.2.1.

## Changelog

See [`CHANGELOG.md`](CHANGELOG.md) for the implementation record and [`CHANGELOG.ru.md`](CHANGELOG.ru.md) for the Russian translation.
