"""Headless Blender smoke test: register/unregister + operator + non-mutation.

Run with::

    blender --background --factory-startup --python tests/blender_smoke_test.py

The script prints a ``RESULT: PASS`` / ``RESULT: FAIL`` summary and exits with a
non-zero status on failure.
"""

from __future__ import annotations

import os
import sys
import tempfile

import bpy
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

_RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    _RESULTS.append((name, bool(condition), detail))
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name} {detail}")


def is_operator_registered(idname: str) -> bool:
    """Blender derives the ``bpy.types`` attribute from ``bl_idname``."""

    prefix, _, operator = idname.partition(".")
    rna_name = f"{prefix.upper()}_OT_{operator}"
    return hasattr(bpy.types, rna_name)


def call_expect_cancelled(*args, **kwargs) -> set:
    """Blender raises RuntimeError for operator ERROR reports; treat as cancel."""

    try:
        return bpy.ops.stylizetex.process_texture(*args, **kwargs)
    except RuntimeError:
        return {"CANCELLED"}


def make_source_image(name: str, size: int = 64):
    image = bpy.data.images.new(name, size, size, alpha=True, float_buffer=False)
    image.colorspace_settings.name = "sRGB"
    yy, xx = np.mgrid[0:size, 0:size]
    pixels = np.zeros((size, size, 4), dtype=np.float32)
    pixels[..., 0] = xx / float(size)
    pixels[..., 1] = yy / float(size)
    pixels[..., 2] = 0.5
    pixels[..., 3] = 0.2 + 0.8 * (xx / float(size))
    image.pixels.foreach_set(pixels.reshape(-1))
    return image


def make_material(name: str, image):
    material = bpy.data.materials.new(name)
    if material.node_tree is None:
        material.use_nodes = True
    node_tree = material.node_tree
    bsdf = node_tree.nodes.get("Principled BSDF")
    texture = node_tree.nodes.new("ShaderNodeTexImage")
    texture.image = image
    node_tree.links.new(texture.outputs["Color"], bsdf.inputs["Base Color"])
    return material


def test_register_cycle():
    import stylizetex as addon

    addon.register()
    check(
        "operator_registered",
        is_operator_registered("stylizetex.process_texture")
        and is_operator_registered("stylizetex.reset_settings")
        and is_operator_registered("stylizetex.randomize_style"),
    )
    check("panel_registered", hasattr(bpy.types, "STYLIZETEX_PT_main"))
    check("scene_settings_registered", hasattr(bpy.types.Scene, "stylizetex_settings"))
    addon.unregister()
    check(
        "operator_unregistered",
        not is_operator_registered("stylizetex.process_texture")
        and not is_operator_registered("stylizetex.randomize_style"),
    )
    check("panel_unregistered", not hasattr(bpy.types, "STYLIZETEX_PT_main"))
    check(
        "scene_settings_unregistered",
        not hasattr(bpy.types.Scene, "stylizetex_settings"),
    )
    # Register again for the operator tests.
    addon.register()


def test_metadata():
    import stylizetex as addon

    info = getattr(addon, "bl_info", {})
    check("bl_info_version_001", info.get("version") == (0, 0, 1), str(info.get("version")))
    group = bpy.context.scene.stylizetex_settings
    for name in ("hue_variation", "brush_scale", "paint_variation", "micro_detail"):
        check(f"property_{name}", hasattr(group, name))
    check("property_apply_to_material", group.apply_to_material is True, str(group.apply_to_material))
    check("property_pack_output", group.pack_output is False, str(group.pack_output))


def test_operator_undo_options():
    """Static assertion: the process operator registers an undo step.

    The operator now mutates the active material (Base Color retarget), so its
    ``bl_options`` must contain both ``REGISTER`` and ``UNDO``.
    """

    operator = bpy.types.STYLIZETEX_OT_process_texture
    options = set(operator.bl_options)
    check("process_operator_register_option", "REGISTER" in options, str(options))
    check("process_operator_undo_option", "UNDO" in options, str(options))


def build_scene():
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=4, y_subdivisions=4, size=2.0)
    obj = bpy.context.active_object
    obj.name = "SmokeObject"

    image = make_source_image("SmokeSource")
    material = make_material("SmokeMaterial", image)
    obj.data.materials.append(material)

    settings = bpy.context.scene.stylizetex_settings
    settings.output_resolution = "512"
    settings.color_steps = 6
    settings.seed = 4242

    return obj, image, material


def test_operator_success():
    from stylizetex.utils import materials

    obj, image, material = build_scene()
    node_tree = material.node_tree
    link_source_before = (
        node_tree.nodes.get("Principled BSDF").inputs["Base Color"].links[0].from_node.name
    )
    source_pixels_before = np.array(image.pixels[:], dtype=np.float32)

    check("mesh_has_uv", obj.data.uv_layers.active is not None)

    output_dir = tempfile.mkdtemp(prefix="stylizetex_smoke_")
    output_png = os.path.join(output_dir, "smoke_output.png")

    result = bpy.ops.stylizetex.process_texture(filepath=output_png)
    check("operator_finished", result == {"FINISHED"}, str(result))

    # Source image is never modified.
    source_pixels_after = np.array(image.pixels[:], dtype=np.float32)
    check(
        "source_image_unchanged",
        np.array_equal(source_pixels_before, source_pixels_after),
    )

    # Apply-to-material defaults to True: the source node stays in the tree and
    # only the Base Color link is redirected to the marked generated node.
    check(
        "material_source_node_preserved",
        node_tree.nodes.get(link_source_before) is not None,
    )
    link_source_after = (
        node_tree.nodes.get("Principled BSDF").inputs["Base Color"].links[0].from_node.name
    )
    check("material_base_color_retargeted", link_source_after != link_source_before)
    generated_node = node_tree.nodes.get(link_source_after)
    check("material_generated_node_marked", materials.is_generated_node(generated_node))

    # Output file.
    check("png_exists", os.path.isfile(output_png) and os.path.getsize(output_png) > 0)

    loaded = bpy.data.images.load(output_png)
    check("png_resolution", tuple(loaded.size) == (512, 512), str(tuple(loaded.size)))
    check(
        "png_colorspace_srgb",
        loaded.colorspace_settings.name.startswith("sRGB"),
        loaded.colorspace_settings.name,
    )

    # NEW image data-block created, source not reused.
    created = [
        candidate
        for candidate in bpy.data.images
        if candidate.name.startswith("SmokeObject_stylizetex_basecolor")
    ]
    check("new_image_created", len(created) >= 1)

    if created:
        out_pixels = np.array(created[0].pixels[:], dtype=np.float32).reshape(512, 512, 4)
        # Alpha must vary like the source gradient (not flattened to 0/1 only).
        check(
            "output_alpha_variation",
            float(out_pixels[..., 3].max() - out_pixels[..., 3].min()) > 0.1,
            f"range={float(out_pixels[..., 3].max() - out_pixels[..., 3].min()):.3f}",
        )

    loaded_pixels = np.array(loaded.pixels[:], dtype=np.float32).reshape(512, 512, 4)
    check("output_nonempty", float(loaded_pixels[..., :3].std()) > 1e-3)
    # Stylization should keep the overall brightness close to the source.
    source_srgb = np.array(image.pixels[:], dtype=np.float32).reshape(64, 64, 4)[..., :3]
    brightness_delta = abs(float(loaded_pixels[..., :3].mean()) - float(source_srgb.mean()))
    check("output_brightness_sane", brightness_delta < 0.25, f"delta={brightness_delta:.3f}")

    # Cleanup the loaded copy so names stay tidy.
    bpy.data.images.remove(loaded)


def test_reset_operator():
    settings = bpy.context.scene.stylizetex_settings
    settings.color_steps = 3
    settings.contrast = 1.9
    settings.hue_variation = 0.4
    settings.paint_variation = 0.5
    settings.micro_detail = 0.1
    settings.brush_scale = 0.6
    settings.apply_to_material = False
    settings.pack_output = True
    result = bpy.ops.stylizetex.reset_settings()
    check("reset_finished", result == {"FINISHED"}, str(result))
    check("reset_color_steps", settings.color_steps == 8, str(settings.color_steps))
    check("reset_contrast", abs(settings.contrast - 1.05) < 1e-5, str(settings.contrast))
    check("reset_resolution", settings.output_resolution == "2048")
    check("reset_hue_variation", abs(settings.hue_variation - 0.0) < 1e-6, str(settings.hue_variation))
    check("reset_brush_scale", abs(settings.brush_scale - 0.15) < 1e-6, str(settings.brush_scale))
    check("reset_paint_variation", abs(settings.paint_variation - 0.0) < 1e-6, str(settings.paint_variation))
    check("reset_micro_detail", abs(settings.micro_detail - 1.0) < 1e-6, str(settings.micro_detail))
    check("reset_apply_to_material", settings.apply_to_material is True, str(settings.apply_to_material))
    check("reset_pack_output", settings.pack_output is False, str(settings.pack_output))


def test_randomize_operator():
    # Works with no selected mesh at all.
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = None

    settings = bpy.context.scene.stylizetex_settings
    settings.output_resolution = "1024"
    settings.output_dir = "C:/somewhere"
    settings.apply_to_material = False
    settings.pack_output = True
    bpy.context.scene.stylizetex_last_output = "C:/somewhere/keep.png"

    images_before = len(bpy.data.images)
    materials_before = len(bpy.data.materials)

    seed_before = settings.seed
    result = bpy.ops.stylizetex.randomize_style()
    check("randomize_finished", result == {"FINISHED"}, str(result))
    seed_after = settings.seed
    check("randomize_seed_changed", seed_after != seed_before, f"{seed_before} -> {seed_after}")

    # Output-related settings must be preserved exactly.
    check("randomize_keeps_resolution", settings.output_resolution == "1024")
    check("randomize_keeps_output_dir", settings.output_dir == "C:/somewhere")
    check("randomize_keeps_apply_to_material", settings.apply_to_material is False)
    check("randomize_keeps_pack_output", settings.pack_output is True)
    check(
        "randomize_keeps_last_output",
        bpy.context.scene.stylizetex_last_output == "C:/somewhere/keep.png",
    )

    # No data-blocks were created and no files touched.
    check("randomize_no_images", len(bpy.data.images) == images_before)
    check("randomize_no_materials", len(bpy.data.materials) == materials_before)

    # Style values are inside the restrained ranges.
    check(
        "randomize_style_bounds",
        5 <= settings.color_steps <= 12
        and 0.45 <= settings.color_simplification <= 0.90
        and 0.08 <= settings.variation_strength <= 0.30
        and 0.02 <= settings.hue_variation <= 0.12
        and 0.08 <= settings.brush_scale <= 0.30
        and 0.10 <= settings.paint_variation <= 0.35
        and 0.15 <= settings.micro_detail <= 0.45,
        f"steps={settings.color_steps}",
    )

    # Two consecutive presses produce different seeds and different styles.
    first_style = (
        settings.color_steps,
        settings.color_simplification,
        settings.brush_scale,
        settings.seed,
    )
    bpy.ops.stylizetex.randomize_style()
    second_style = (
        settings.color_steps,
        settings.color_simplification,
        settings.brush_scale,
        settings.seed,
    )
    check("randomize_two_presses_differ", first_style != second_style, f"{first_style} vs {second_style}")

    # Manually editing the seed must not change the other sliders.
    snapshot = (
        settings.color_steps,
        settings.color_simplification,
        settings.contrast,
        settings.saturation,
        settings.hue_variation,
        settings.brush_scale,
        settings.paint_variation,
        settings.micro_detail,
    )
    settings.seed = (settings.seed + 7) % 2147483647
    after_manual = (
        settings.color_steps,
        settings.color_simplification,
        settings.contrast,
        settings.saturation,
        settings.hue_variation,
        settings.brush_scale,
        settings.paint_variation,
        settings.micro_detail,
    )
    check("manual_seed_does_not_change_sliders", snapshot == after_manual)


def test_error_paths():
    # No active mesh object.
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = None
    result = call_expect_cancelled()
    check("error_no_object_cancelled", result == {"CANCELLED"}, str(result))

    # Restore an object without a material.
    obj, image, material = build_scene()
    obj.data.materials.clear()
    result = call_expect_cancelled()
    check("error_no_material_cancelled", result == {"CANCELLED"}, str(result))

    # Material with no Base Color texture link.
    plain_material = bpy.data.materials.new("NoTexture")
    if plain_material.node_tree is None:
        plain_material.use_nodes = True
    obj.data.materials.append(plain_material)
    result = call_expect_cancelled()
    check("error_no_base_color_cancelled", result == {"CANCELLED"}, str(result))

    # Object with a valid material but no UV map.
    obj.data.materials.clear()
    textured_material = make_material("WithTexture", make_source_image("Source2"))
    obj.data.materials.append(textured_material)
    for layer in list(obj.data.uv_layers):
        obj.data.uv_layers.remove(layer)
    result = call_expect_cancelled()
    check("error_no_uv_cancelled", result == {"CANCELLED"}, str(result))


def main() -> int:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    test_register_cycle()
    test_metadata()
    test_operator_undo_options()
    test_operator_success()
    test_reset_operator()
    test_randomize_operator()
    test_error_paths()

    import stylizetex as addon

    addon.unregister()

    failures = [name for name, ok, _ in _RESULTS if not ok]
    for name, ok, detail in _RESULTS:
        if not ok:
            print(f"  FAILED: {name} {detail}")
    print(f"RESULT: {'PASS' if not failures else 'FAIL'} ({len(_RESULTS) - len(failures)}/{len(_RESULTS)} checks)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

