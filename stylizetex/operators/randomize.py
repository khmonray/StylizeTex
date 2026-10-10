"""Operator that randomizes the style settings and the seed.

The operator only touches the whitelisted style fields (it never changes the
output resolution, output directory or the last-output path) and performs no
image processing or file I/O, so it works with or without a selected mesh.
"""

from __future__ import annotations

import bpy

from ..processing.randomize import STYLE_FIELDS, pick_new_seed, randomized_style


class STYLIZETEX_OT_randomize_style(bpy.types.Operator):
    bl_idname = "stylizetex.randomize_style"
    bl_label = "Randomize Style"
    bl_description = (
        "Pick a new seed and sample restrained style settings. Output resolution, "
        "output folder and the last output are left unchanged"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        group = getattr(context.scene, "stylizetex_settings", None)
        if group is None:
            self.report({"ERROR"}, "Stylization settings are unavailable.")
            return {"CANCELLED"}

        current_seed = int(getattr(group, "seed", 0))
        new_seed = pick_new_seed(current_seed)
        style = randomized_style(new_seed)

        for name in STYLE_FIELDS:
            if hasattr(group, name):
                setattr(group, name, getattr(style, name))

        self.report({"INFO"}, f"Randomized style with seed {new_seed}.")
        return {"FINISHED"}
