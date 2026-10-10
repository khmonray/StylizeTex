"""Operator that processes the active material Base Color into a new image."""

from __future__ import annotations

import os
import traceback

import bpy
from bpy.props import StringProperty

from ..processing.pipeline import process_texture
from ..processing.resize import fit_resolution, resize_bilinear
from ..processing.settings import adapt_settings
from ..utils import images, materials, paths, validation


class STYLIZED_OT_process_texture(bpy.types.Operator):
    bl_idname = "stylized_texture.process_texture"
    bl_label = "Process Texture"
    bl_description = (
        "Process the Base Color image linked to the active material into a new "
        "stylized image, save it as a PNG and (optionally) apply it to the "
        "material and pack it into the .blend. The source image and every "
        "unrelated node/link are never modified"
    )
    bl_options = {"REGISTER", "UNDO"}

    filepath: StringProperty(
        name="Output File",
        description="Optional explicit PNG path. Overrides the output folder setting",
        subtype="FILE_PATH",
        default="",
    )

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT"

    def execute(self, context):
        try:
            return self._execute(context)
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        except Exception:  # unexpected: log for developers, no traceback in UI
            traceback.print_exc()
            self.report(
                {"ERROR"},
                "Unexpected error during stylization. See the Blender console for details.",
            )
            return {"CANCELLED"}

    def _execute(self, context):
        obj, error = validation.validate_selected_mesh(context)
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}

        image, error = validation.validate_base_color(obj)
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}

        uv_error = validation.validate_uv(obj)
        if uv_error:
            self.report({"ERROR"}, uv_error)
            return {"CANCELLED"}

        group = getattr(context.scene, "stylized_texture_settings", None)
        settings = adapt_settings(group)

        apply_to_material = bool(getattr(group, "apply_to_material", True))
        pack_output = bool(getattr(group, "pack_output", False))

        output_dir = group.output_dir if group is not None else ""
        output_filepath = paths.resolve_output_filepath(
            context, obj, image, output_dir, self.filepath
        )
        output_folder = os.path.dirname(output_filepath)
        directory_error = validation.validate_output_directory(output_folder)
        if directory_error:
            self.report({"ERROR"}, directory_error)
            return {"CANCELLED"}

        material = obj.active_material
        source_node, _resolved = materials.get_source_node(material)

        linear = images.image_to_linear_rgba(image)
        target = settings.output_resolution
        out_width, out_height = fit_resolution(linear.shape[1], linear.shape[0], target)
        if (out_height, out_width) != (linear.shape[0], linear.shape[1]):
            linear = resize_bilinear(linear, out_height, out_width)

        processed = process_texture(linear, settings, is_linear=True)

        output_image = images.create_image_from_linear_rgba(
            images.new_image_name(obj.name), processed
        )
        materials.mark_generated_image(output_image, image)

        # 1. External PNG is always written, even when packing.
        try:
            images.save_png(output_image, output_filepath)
        except (OSError, RuntimeError) as exc:
            bpy.data.images.remove(output_image)
            print(f"[stylized_texture] Failed to save PNG: {exc}")
            self.report({"ERROR"}, "Unable to save texture. Check output path and permissions.")
            return {"CANCELLED"}

        # 2. Optionally pack the image into the .blend (before applying).
        if pack_output:
            try:
                images.pack_image(output_image)
            except (OSError, RuntimeError) as exc:
                materials.remove_generated_image_if_unused(output_image)
                print(f"[stylized_texture] Failed to pack image: {exc}")
                self.report(
                    {"ERROR"},
                    "Unable to pack the texture into the .blend. The material was left unchanged.",
                )
                return {"CANCELLED"}

        # 3. Optionally apply the generated image to the material.
        applied = False
        if apply_to_material:
            try:
                materials.apply_generated_image(material, output_image, source_node, image)
                applied = True
            except Exception as exc:
                traceback.print_exc()
                materials.remove_generated_image_if_unused(output_image)
                print(f"[stylized_texture] Failed to apply texture: {exc}")
                self.report(
                    {"ERROR"},
                    "Unable to apply the texture to the material. The material was left unchanged.",
                )
                return {"CANCELLED"}

        # 4. Remove orphan generated images from earlier runs of this source.
        # Without applying, the freshly written output stays an unused data-block
        # and would otherwise accumulate on every run. This keeps the current
        # output (needed for the last-output/status report and any later apply)
        # while discarding only unused marked images. Source, foreign and in-use
        # images are never touched. Packing is unaffected.
        materials.remove_other_generated_images(image, keep_image=output_image)

        status = self._build_status(output_filepath, applied, pack_output)
        context.scene.stylized_texture_last_output = output_filepath
        context.scene.stylized_texture_last_status = status
        self.report({"INFO"}, status)
        return {"FINISHED"}

    @staticmethod
    def _build_status(output_filepath, applied, packed):
        parts = [f"Saved stylized texture: {output_filepath}"]
        if applied:
            parts.append("applied to material")
        if packed:
            parts.append("packed into .blend (save the .blend to keep the packed texture)")
        return " - ".join(parts)
