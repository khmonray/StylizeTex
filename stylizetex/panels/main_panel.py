"""Minimal View3D sidebar panel for the stylized texture add-on."""

from __future__ import annotations

import bpy

from ..utils.validation import get_base_color_source_image


class STYLIZETEX_PT_main(bpy.types.Panel):
    bl_label = "StylizeTex"
    bl_idname = "STYLIZETEX_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "StylizeTex"

    def draw(self, context):
        layout = self.layout
        group = getattr(context.scene, "stylizetex_settings", None)

        if group is None:
            layout.label(text="Settings unavailable.", icon="ERROR")
            return

        source_box = layout.box()
        source_box.label(text="Source", icon="IMAGE_DATA")
        obj = context.active_object
        if obj is not None and obj.type == "MESH":
            source_box.label(text=f"Object: {obj.name}")
            image = get_base_color_source_image(obj.active_material)
            source_box.label(text=f"Base Color: {image.name if image else 'None'}")
        else:
            source_box.label(text="Select a mesh object.", icon="INFO")

        output_box = layout.box()
        output_box.label(text="Output", icon="FILE_IMAGE")
        output_box.prop(group, "output_resolution")
        output_box.prop(group, "output_dir")
        output_box.prop(group, "apply_to_material")
        output_box.prop(group, "pack_output")

        style_box = layout.box()
        style_box.label(text="Style", icon="COLOR")

        color_group = style_box.column(align=True)
        color_group.label(text="Color")
        color_group.prop(group, "color_simplification")
        color_group.prop(group, "color_steps")
        color_group.prop(group, "contrast")
        color_group.prop(group, "saturation")

        variation_group = style_box.column(align=True)
        variation_group.label(text="Large Scale")
        variation_group.prop(group, "variation_strength")
        variation_group.prop(group, "variation_scale")

        painterly_group = style_box.column(align=True)
        painterly_group.label(text="Painterly")
        painterly_group.prop(group, "brush_scale")
        painterly_group.prop(group, "paint_variation")
        painterly_group.prop(group, "micro_detail")
        painterly_group.prop(group, "hue_variation")

        seed_group = style_box.column(align=True)
        seed_group.label(text="Seed")
        seed_group.prop(group, "seed")

        layout.separator()
        layout.operator("stylizetex.process_texture", icon="SHADERFX")
        layout.operator("stylizetex.randomize_style", icon="FILE_REFRESH")
        layout.operator("stylizetex.reset_settings", icon="LOOP_BACK")

        last_output = getattr(context.scene, "stylizetex_last_output", "")
        if last_output:
            layout.label(text="Last: " + last_output, icon="CHECKMARK")

        last_status = getattr(context.scene, "stylizetex_last_status", "")
        if last_status:
            layout.label(text=last_status, icon="INFO")


classes = (STYLIZETEX_PT_main,)

__all__ = ["STYLIZETEX_PT_main", "classes"]
