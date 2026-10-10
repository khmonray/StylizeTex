"""Headless Blender tests: material application, packing and rollback.

Covers the apply-to-material and pack-into-.blend behavior of
``stylized_texture.process_texture``:

* ``Apply to Material`` defaults to ``True`` and retargets only the Base Color
  link while keeping the original source node and image intact;
* disabling apply preserves the legacy behavior (material untouched);
* repeated runs reuse a single marked generated node and never accumulate
  generated images;
* unrelated nodes and links are never modified;
* packing verifies ``packed_file`` while the external PNG is still written;
* pack/apply failures roll back the new image and leave the material intact;
* an unsaved ``.blend`` still packs and reports that the user must save.

Run with::

    blender --background --factory-startup --python tests/blender_materials_test.py
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

from stylized_texture_addon.utils import images as images_mod  # noqa: E402
from stylized_texture_addon.utils import materials as materials_mod  # noqa: E402
from stylized_texture_addon.utils import validation  # noqa: E402

_RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    _RESULTS.append((name, bool(condition), detail))
    print(f"[{'PASS' if condition else 'FAIL'}] {name} {detail}")


def reset_output_flags(*, apply_to_material: bool = True, pack_output: bool = False) -> None:
    """Reset the two output flags so tests never leak state into each other."""

    settings = bpy.context.scene.stylized_texture_settings
    settings.apply_to_material = apply_to_material
    settings.pack_output = pack_output


def call_expect_cancelled(*args, **kwargs) -> set:
    """Blender raises ``RuntimeError`` for operator ERROR reports."""

    try:
        return bpy.ops.stylized_texture.process_texture(*args, **kwargs)
    except RuntimeError:
        return {"CANCELLED"}


def reset_datablocks() -> None:
    """Remove test data-blocks so global counts are meaningful per test."""

    for obj in list(bpy.data.objects):
        try:
            bpy.data.objects.remove(obj, do_unlink=True)
        except Exception:
            pass
    for material in list(bpy.data.materials):
        try:
            bpy.data.materials.remove(material, do_unlink=True)
        except Exception:
            pass
    for image in list(bpy.data.images):
        try:
            bpy.data.images.remove(image)
        except Exception:
            pass
    for mesh in list(bpy.data.meshes):
        try:
            bpy.data.meshes.remove(mesh)
        except Exception:
            pass


def make_source_image(name: str, size: int = 32):
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


def get_bsdf(material):
    return material.node_tree.nodes.get("Principled BSDF")


def base_color_link(material):
    return get_bsdf(material).inputs["Base Color"].links[0].from_node


def link_signature(node_tree):
    return {
        (link.from_node.name, link.from_socket.name, link.to_node.name, link.to_socket.name)
        for link in node_tree.links
    }


def marked_node_count(node_tree):
    return sum(1 for node in node_tree.nodes if materials_mod.is_generated_node(node))


def marked_image_count():
    return sum(1 for image in bpy.data.images if materials_mod.is_generated_image(image))


def build_scene(name: str, with_extra_nodes: bool = False):
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=4, y_subdivisions=4, size=2.0)
    obj = bpy.context.active_object
    obj.name = name

    image = make_source_image(f"{name}Source")
    material = bpy.data.materials.new(f"{name}Material")
    if material.node_tree is None:
        material.use_nodes = True
    node_tree = material.node_tree
    bsdf = get_bsdf(material)
    texture = node_tree.nodes.new("ShaderNodeTexImage")
    texture.name = f"{name}SourceNode"
    texture.image = image
    node_tree.links.new(texture.outputs["Color"], bsdf.inputs["Base Color"])
    obj.data.materials.append(material)

    if with_extra_nodes:
        extra_image = make_source_image(f"{name}ExtraImage", 16)
        extra_tex = node_tree.nodes.new("ShaderNodeTexImage")
        extra_tex.name = f"{name}ExtraRoughnessNode"
        extra_tex.image = extra_image
        node_tree.links.new(extra_tex.outputs["Color"], bsdf.inputs["Roughness"])
        node_tree.nodes.new("ShaderNodeRGB").name = f"{name}UnrelatedNode"

    settings = bpy.context.scene.stylized_texture_settings
    settings.output_resolution = "512"
    return obj, image, material


def process_to_temp(obj, prefix: str) -> str:
    output_dir = tempfile.mkdtemp(prefix=prefix)
    return os.path.join(output_dir, "output.png")


def test_apply_default_enabled():
    reset_datablocks()
    reset_output_flags(apply_to_material=True, pack_output=False)
    obj, image, material = build_scene("ApplyDefault")
    settings = bpy.context.scene.stylized_texture_settings
    check("apply_default_true", settings.apply_to_material is True, str(settings.apply_to_material))

    node_tree = material.node_tree
    source_node = base_color_link(material)
    source_node_name = source_node.name
    source_pixels_before = np.array(image.pixels[:], dtype=np.float32)

    output_png = process_to_temp(obj, "stylized_materials_default_")
    result = bpy.ops.stylized_texture.process_texture(filepath=output_png)
    check("apply_default_finished", result == {"FINISHED"}, str(result))

    new_source = base_color_link(material)
    check("apply_default_retargeted", new_source.name != source_node_name, new_source.name)
    check("apply_default_marked", materials_mod.is_generated_node(new_source))
    check("apply_default_source_node_kept", node_tree.nodes.get(source_node_name) is not None)
    check("apply_default_one_generated_node", marked_node_count(node_tree) == 1)

    source_pixels_after = np.array(image.pixels[:], dtype=np.float32)
    check("apply_default_source_pixels_unchanged", np.array_equal(source_pixels_before, source_pixels_after))
    check("apply_default_png_exists", os.path.isfile(output_png) and os.path.getsize(output_png) > 0)

    resolved, error = validation.validate_base_color(obj)
    check("apply_default_validation_resolves_source", error is None and resolved == image, str(error))
    resolved_node, resolved_image = materials_mod.get_source_node(material)
    check(
        "apply_default_source_node_resolves",
        resolved_node is not None and resolved_node.name == source_node_name and resolved_image == image,
    )
    # The UI helper must also keep reporting the original source, not the
    # generated output that now feeds Base Color.
    display_image = validation.get_base_color_source_image(material)
    check("apply_default_display_resolves_source", display_image == image, str(display_image))


def test_apply_disabled():
    reset_datablocks()
    reset_output_flags(apply_to_material=False, pack_output=False)
    obj, image, material = build_scene("ApplyDisabled")
    settings = bpy.context.scene.stylized_texture_settings
    settings.apply_to_material = False

    node_tree = material.node_tree
    source_node_name = base_color_link(material).name
    source_pixels_before = np.array(image.pixels[:], dtype=np.float32)

    output_png = process_to_temp(obj, "stylized_materials_disabled_")
    result = bpy.ops.stylized_texture.process_texture(filepath=output_png)
    check("apply_disabled_finished", result == {"FINISHED"}, str(result))

    check("apply_disabled_link_unchanged", base_color_link(material).name == source_node_name)
    check("apply_disabled_no_generated_node", materials_mod.find_generated_node(node_tree) is None)
    # The generated image data-block is still created for the PNG, but it is not
    # connected to the material.
    check("apply_disabled_generated_image_unlinked", base_color_link(material).image == image)
    source_pixels_after = np.array(image.pixels[:], dtype=np.float32)
    check("apply_disabled_source_unchanged", np.array_equal(source_pixels_before, source_pixels_after))
    check("apply_disabled_png_exists", os.path.isfile(output_png))
    check("apply_disabled_one_generated_image", marked_image_count() == 1, str(marked_image_count()))
    display_image = validation.get_base_color_source_image(material)
    check("apply_disabled_display_resolves_source", display_image == image, str(display_image))

    # Repeated runs with apply disabled must not accumulate unused data-blocks:
    # the previous unused generated image is cleaned up and only the latest
    # output is kept.
    for _ in range(3):
        repeated_png = process_to_temp(obj, "stylized_materials_disabled_repeat_")
        repeated = bpy.ops.stylized_texture.process_texture(filepath=repeated_png)
        check("apply_disabled_repeat_finished", repeated == {"FINISHED"}, str(repeated))
    check("apply_disabled_no_accumulation", marked_image_count() == 1, str(marked_image_count()))
    check(
        "apply_disabled_latest_kept",
        base_color_link(material).image == image
        and any(materials_mod.is_generated_image(img) for img in bpy.data.images),
    )


def test_repeated_runs_single_generated_node():
    reset_datablocks()
    reset_output_flags(apply_to_material=True, pack_output=False)
    obj, image, material = build_scene("Repeat")
    settings = bpy.context.scene.stylized_texture_settings
    settings.apply_to_material = True

    node_tree = material.node_tree
    source_node_name = base_color_link(material).name

    first_png = os.path.join(tempfile.mkdtemp(prefix="stylized_materials_repeat_"), "output.png")
    result1 = bpy.ops.stylized_texture.process_texture(filepath=first_png)
    check("repeat_first_finished", result1 == {"FINISHED"}, str(result1))
    first_generated_name = base_color_link(material).name

    second_png = os.path.join(tempfile.mkdtemp(prefix="stylized_materials_repeat_"), "output.png")
    result2 = bpy.ops.stylized_texture.process_texture(filepath=second_png)
    check("repeat_second_finished", result2 == {"FINISHED"}, str(result2))
    second_generated_name = base_color_link(material).name

    check("repeat_same_node_reused", first_generated_name == second_generated_name)
    check("repeat_one_generated_node", marked_node_count(node_tree) == 1)
    check("repeat_one_generated_image", marked_image_count() == 1, str(marked_image_count()))
    check("repeat_source_node_kept", node_tree.nodes.get(source_node_name) is not None)
    check("repeat_generated_image_is_latest", materials_mod.is_generated_image(base_color_link(material).image))


def test_source_and_unrelated_preserved():
    reset_datablocks()
    reset_output_flags(apply_to_material=True, pack_output=False)
    obj, image, material = build_scene("Preserve", with_extra_nodes=True)
    settings = bpy.context.scene.stylized_texture_settings
    settings.apply_to_material = True

    node_tree = material.node_tree
    nodes_before = {node.name for node in node_tree.nodes}
    links_before = link_signature(node_tree)
    source_node_name = base_color_link(material).name
    source_pixels_before = np.array(image.pixels[:], dtype=np.float32)
    extra_node = node_tree.nodes.get("PreserveExtraRoughnessNode")
    extra_pixels_before = np.array(extra_node.image.pixels[:], dtype=np.float32)

    output_png = process_to_temp(obj, "stylized_materials_preserve_")
    result = bpy.ops.stylized_texture.process_texture(filepath=output_png)
    check("preserve_finished", result == {"FINISHED"}, str(result))

    nodes_after = {node.name for node in node_tree.nodes}
    links_after = link_signature(node_tree)
    added_nodes = nodes_after - nodes_before
    removed_nodes = nodes_before - nodes_after
    added_links = links_after - links_before
    removed_links = links_before - links_after

    check("preserve_all_original_nodes_kept", nodes_before <= nodes_after and not removed_nodes, str(removed_nodes))
    check("preserve_exactly_one_node_added", len(added_nodes) == 1, str(added_nodes))
    check("preserve_one_link_added", len(added_links) == 1, str(added_links))
    check("preserve_one_link_removed", len(removed_links) == 1, str(removed_links))
    check(
        "preserve_only_base_color_link_changed",
        all(to_node == "Principled BSDF" and to_socket == "Base Color" for _, _, to_node, to_socket in added_links)
        and all(
            to_node == "Principled BSDF" and to_socket == "Base Color"
            for _, _, to_node, to_socket in removed_links
        ),
    )
    check("preserve_source_node_kept", node_tree.nodes.get(source_node_name) is not None)
    check("preserve_source_pixels_unchanged", np.array_equal(source_pixels_before, np.array(image.pixels[:], dtype=np.float32)))
    check(
        "preserve_extra_image_unchanged",
        np.array_equal(extra_pixels_before, np.array(extra_node.image.pixels[:], dtype=np.float32)),
    )


def test_pack_and_external_png():
    reset_datablocks()
    reset_output_flags(apply_to_material=True, pack_output=True)
    obj, image, material = build_scene("Pack")
    settings = bpy.context.scene.stylized_texture_settings
    settings.apply_to_material = True
    settings.pack_output = True

    output_png = process_to_temp(obj, "stylized_materials_pack_")
    result = bpy.ops.stylized_texture.process_texture(filepath=output_png)
    check("pack_finished", result == {"FINISHED"}, str(result))

    generated_image = base_color_link(material).image
    check("pack_image_is_generated", materials_mod.is_generated_image(generated_image))
    check("pack_packed_file_present", generated_image.packed_file is not None)
    check("pack_external_png_kept", os.path.isfile(output_png) and os.path.getsize(output_png) > 0)

    status = bpy.context.scene.stylized_texture_last_status.lower()
    check("pack_status_mentions_packed", "packed" in status, status)
    check("pack_status_mentions_blend", ".blend" in status, status)


def test_unsaved_blend_and_rollbacks():
    reset_datablocks()
    reset_output_flags(apply_to_material=True, pack_output=True)
    check("unsaved_blend_empty_filepath", bpy.data.filepath == "", repr(bpy.data.filepath))

    # Packing succeeds in an unsaved .blend and reports the save reminder.
    obj, image, material = build_scene("Unsaved")
    settings = bpy.context.scene.stylized_texture_settings
    settings.apply_to_material = True
    settings.pack_output = True
    output_png = process_to_temp(obj, "stylized_materials_unsaved_")
    result = bpy.ops.stylized_texture.process_texture(filepath=output_png)
    check("unsaved_pack_finished", result == {"FINISHED"}, str(result))
    check("unsaved_pack_packed_file", base_color_link(material).image.packed_file is not None)
    check(
        "unsaved_pack_save_reminder",
        "save the .blend" in bpy.context.scene.stylized_texture_last_status.lower(),
        bpy.context.scene.stylized_texture_last_status,
    )

    # Pack failure: roll back the new image, leave the material untouched.
    reset_datablocks()
    obj, image, material = build_scene("PackFail")
    settings = bpy.context.scene.stylized_texture_settings
    settings.apply_to_material = True
    settings.pack_output = True
    node_tree = material.node_tree
    source_node_name = base_color_link(material).name
    nodes_before = len(node_tree.nodes)
    marked_images_before = marked_image_count()

    original_pack = images_mod.pack_image

    def failing_pack(_image):
        raise OSError("simulated pack failure")

    images_mod.pack_image = failing_pack
    try:
        output_png = process_to_temp(obj, "stylized_materials_packfail_")
        result = call_expect_cancelled(filepath=output_png)
    finally:
        images_mod.pack_image = original_pack

    check("pack_failure_cancelled", result == {"CANCELLED"}, str(result))
    check("pack_failure_link_unchanged", base_color_link(material).name == source_node_name)
    check("pack_failure_node_count_unchanged", len(node_tree.nodes) == nodes_before)
    check("pack_failure_no_generated_node", materials_mod.find_generated_node(node_tree) is None)
    check("pack_failure_image_rolled_back", marked_image_count() == marked_images_before)

    # Apply failure: roll back the new image, leave the material untouched.
    reset_datablocks()
    obj, image, material = build_scene("ApplyFail")
    settings = bpy.context.scene.stylized_texture_settings
    settings.apply_to_material = True
    settings.pack_output = False
    node_tree = material.node_tree
    source_node_name = base_color_link(material).name
    nodes_before = len(node_tree.nodes)
    marked_images_before = marked_image_count()

    original_apply = materials_mod.apply_generated_image

    def failing_apply(*_args, **_kwargs):
        raise RuntimeError("simulated apply failure")

    materials_mod.apply_generated_image = failing_apply
    try:
        output_png = process_to_temp(obj, "stylized_materials_applyfail_")
        result = call_expect_cancelled(filepath=output_png)
    finally:
        materials_mod.apply_generated_image = original_apply

    check("apply_failure_cancelled", result == {"CANCELLED"}, str(result))
    check("apply_failure_link_unchanged", base_color_link(material).name == source_node_name)
    check("apply_failure_node_count_unchanged", len(node_tree.nodes) == nodes_before)
    check("apply_failure_no_generated_node", materials_mod.find_generated_node(node_tree) is None)
    check("apply_failure_image_rolled_back", marked_image_count() == marked_images_before)


class _FailingLinks:
    """Delegate to real node links but fail the first ``new`` call."""

    def __init__(self, real_links):
        self._real = real_links
        self._remaining_failures = 1

    def new(self, *args, **kwargs):
        if self._remaining_failures > 0:
            self._remaining_failures -= 1
            raise RuntimeError("simulated node_tree.links.new failure")
        return self._real.new(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._real, name)


class _NodeTreeProxy:
    """Wrap a real node tree so ``links.new`` can be made to fail."""

    def __init__(self, real_tree, links):
        self._real = real_tree
        self.links = links

    def __getattr__(self, name):
        return getattr(self._real, name)


class _MaterialProxy:
    """Wrap a material with a proxied node tree for rollback injection."""

    def __init__(self, real_material, node_tree):
        self._real = real_material
        self.node_tree = node_tree

    def __getattr__(self, name):
        return getattr(self._real, name)


def _make_generated_image(name: str, size: int = 8):
    array = np.zeros((size, size, 4), dtype=np.float32)
    array[..., 3] = 1.0
    return images_mod.create_image_from_linear_rgba(name, array)


def _proxy_apply(material, generated_image, source_node, source_image) -> bool:
    """Call ``apply_generated_image`` through a proxy whose first link fails.

    Returns ``True`` when the internal rollback re-raised (as it should).
    """

    links = _FailingLinks(material.node_tree.links)
    proxy = _MaterialProxy(material, _NodeTreeProxy(material.node_tree, links))
    try:
        materials_mod.apply_generated_image(proxy, generated_image, source_node, source_image)
    except RuntimeError:
        return True
    return False


def test_internal_rollback_fresh_material():
    """A failed ``node_tree.links.new`` must restore a freshly mutated material."""

    reset_datablocks()
    reset_output_flags(apply_to_material=True, pack_output=False)
    obj, image, material = build_scene("InternalRollbackFresh")
    node_tree = material.node_tree
    source_node = base_color_link(material)
    source_node_name = source_node.name
    nodes_before = len(node_tree.nodes)
    marked_images_before = marked_image_count()

    generated = _make_generated_image("InternalRollbackFreshGenerated")
    materials_mod.mark_generated_image(generated, image)

    raised = _proxy_apply(material, generated, source_node, image)

    check("internal_rollback_fresh_raised", raised)
    check("internal_rollback_fresh_link_restored", base_color_link(material).name == source_node_name)
    check("internal_rollback_fresh_node_count", len(node_tree.nodes) == nodes_before)
    check("internal_rollback_fresh_no_generated_node", materials_mod.find_generated_node(node_tree) is None)
    check(
        "internal_rollback_fresh_source_untouched",
        node_tree.nodes.get(source_node_name) is not None and source_node.image == image,
    )

    materials_mod.remove_generated_image_if_unused(generated)
    check("internal_rollback_fresh_images_balanced", marked_image_count() == marked_images_before)


def test_internal_rollback_reused_node_restores_props():
    """A failed retarget must restore the reused node's image and custom props."""

    reset_datablocks()
    reset_output_flags(apply_to_material=True, pack_output=False)
    obj, image, material = build_scene("InternalRollbackReuse")
    node_tree = material.node_tree
    source_node_name = base_color_link(material).name

    # First real run creates and applies the marked generated node.
    first_png = process_to_temp(obj, "stylized_materials_internal_reuse_")
    result = bpy.ops.stylized_texture.process_texture(filepath=first_png)
    check("internal_reuse_first_finished", result == {"FINISHED"}, str(result))

    generated_node = base_color_link(material)
    check("internal_reuse_node_marked", materials_mod.is_generated_node(generated_node))
    node_name = generated_node.name
    previous_image = generated_node.image
    props_before = {
        materials_mod.GENERATED_NODE_MARKER: generated_node.get(materials_mod.GENERATED_NODE_MARKER),
        materials_mod.SOURCE_NODE_MARKER: generated_node.get(materials_mod.SOURCE_NODE_MARKER),
        materials_mod.SOURCE_IMAGE_MARKER: generated_node.get(materials_mod.SOURCE_IMAGE_MARKER),
        materials_mod.GENERATED_IMAGE_MARKER: generated_node.get(materials_mod.GENERATED_IMAGE_MARKER),
    }
    marked_before = marked_image_count()

    new_generated = _make_generated_image("InternalRollbackReuseGenerated")
    materials_mod.mark_generated_image(new_generated, image)

    raised = _proxy_apply(material, new_generated, generated_node, image)

    check("internal_reuse_raised", raised)
    reused = node_tree.nodes.get(node_name)
    check("internal_reuse_node_kept", reused is not None)
    check("internal_reuse_link_restored", base_color_link(material).name == node_name)
    check("internal_reuse_image_restored", reused is not None and reused.image == previous_image)
    restored_props = {
        materials_mod.GENERATED_NODE_MARKER: reused.get(materials_mod.GENERATED_NODE_MARKER),
        materials_mod.SOURCE_NODE_MARKER: reused.get(materials_mod.SOURCE_NODE_MARKER),
        materials_mod.SOURCE_IMAGE_MARKER: reused.get(materials_mod.SOURCE_IMAGE_MARKER),
        materials_mod.GENERATED_IMAGE_MARKER: reused.get(materials_mod.GENERATED_IMAGE_MARKER),
    }
    check("internal_reuse_props_restored", restored_props == props_before, str(restored_props))
    check(
        "internal_reuse_previous_image_kept",
        previous_image is not None and bpy.data.images.get(previous_image.name) is not None,
    )
    check("internal_reuse_source_node_kept", node_tree.nodes.get(source_node_name) is not None)

    materials_mod.remove_generated_image_if_unused(new_generated)
    check("internal_reuse_images_balanced", marked_image_count() == marked_before)


def main() -> int:
    import stylized_texture_addon as addon

    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon.register()

    test_apply_default_enabled()
    test_apply_disabled()
    test_repeated_runs_single_generated_node()
    test_source_and_unrelated_preserved()
    test_pack_and_external_png()
    test_unsaved_blend_and_rollbacks()
    test_internal_rollback_fresh_material()
    test_internal_rollback_reused_node_restores_props()

    addon.unregister()

    failures = [name for name, ok, _ in _RESULTS if not ok]
    for name, ok, detail in _RESULTS:
        if not ok:
            print(f"  FAILED: {name} {detail}")
    print(f"RESULT: {'PASS' if not failures else 'FAIL'} ({len(_RESULTS) - len(failures)}/{len(_RESULTS)} checks)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
