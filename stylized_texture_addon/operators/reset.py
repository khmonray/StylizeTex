"""Operator that resets stylization settings to their defaults."""

from __future__ import annotations

import bpy

from ..properties.settings import reset_settings


class STYLIZED_OT_reset_settings(bpy.types.Operator):
    bl_idname = "stylized_texture.reset_settings"
    bl_label = "Reset Settings"
    bl_description = "Reset all stylization settings to their default values"
    bl_options = {"REGISTER"}

    def execute(self, context):
        group = getattr(context.scene, "stylized_texture_settings", None)
        if group is None:
            self.report({"ERROR"}, "Stylization settings are unavailable.")
            return {"CANCELLED"}
        reset_settings(group)
        self.report({"INFO"}, "Stylization settings reset to defaults.")
        return {"FINISHED"}
