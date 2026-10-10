"""Operator-invokable Blender properties for the stylized texture add-on."""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty

RESOLUTION_ITEMS = (
    ("512", "512 x 512", "512 px output"),
    ("1024", "1024 x 1024", "1024 px output"),
    ("2048", "2048 x 2048", "2048 px output"),
    ("4096", "4096 x 4096", "4096 px output"),
)

# Defaults are the single source of truth for the Reset operator. They mirror
# ``processing.settings.StylizationSettings`` but are kept local so this module
# never depends on the processing package at import time.
DEFAULTS = {
    "output_resolution": "2048",
    "output_dir": "",
    "apply_to_material": True,
    "pack_output": False,
    "color_steps": 8,
    "color_simplification": 0.70,
    "variation_strength": 0.25,
    "variation_scale": 0.15,
    "contrast": 1.05,
    "saturation": 0.90,
    "seed": 12345,
    # Phase 2 (neutral defaults preserve the Phase 1 look).
    "hue_variation": 0.0,
    "brush_scale": 0.15,
    "paint_variation": 0.0,
    "micro_detail": 1.0,
}


class StylizeTexSettings(bpy.types.PropertyGroup):
    output_resolution: EnumProperty(
        name="Resolution",
        description="Output texture resolution (longest side)",
        items=RESOLUTION_ITEMS,
        default="2048",
    )
    output_dir: StringProperty(
        name="Output Folder",
        description="Folder for saved PNG files. Empty = next to the source texture",
        subtype="DIR_PATH",
        default="",
    )
    color_steps: IntProperty(
        name="Color Steps",
        description="Number of tonal groups used for color simplification",
        min=2,
        max=32,
        default=8,
    )
    color_simplification: FloatProperty(
        name="Color Simplification",
        description="Blend strength of the color simplification step",
        min=0.0,
        max=1.0,
        default=0.70,
    )
    variation_strength: FloatProperty(
        name="Variation Strength",
        description="Strength of the smooth low-frequency color variation",
        min=0.0,
        max=1.0,
        default=0.25,
    )
    variation_scale: FloatProperty(
        name="Variation Scale",
        description="Relative size of the low-frequency color blobs",
        min=0.01,
        max=1.0,
        default=0.15,
    )
    contrast: FloatProperty(
        name="Contrast",
        description="Contrast multiplier around mid grey",
        min=0.0,
        max=3.0,
        default=1.05,
    )
    saturation: FloatProperty(
        name="Saturation",
        description="Saturation multiplier",
        min=0.0,
        max=3.0,
        default=0.90,
    )
    seed: IntProperty(
        name="Seed",
        description="Random seed for all procedural variation",
        min=0,
        max=2147483647,
        default=12345,
    )
    hue_variation: FloatProperty(
        name="Hue Variation",
        description="Bounded, wrapped hue shift applied to coloured areas",
        min=0.0,
        max=1.0,
        default=0.0,
    )
    brush_scale: FloatProperty(
        name="Brush Scale",
        description="Painterly stroke size. Larger values produce larger strokes",
        min=0.01,
        max=1.0,
        default=0.15,
    )
    paint_variation: FloatProperty(
        name="Paint Variation",
        description="Strength of the painterly brightness/saturation/hue variation",
        min=0.0,
        max=1.0,
        default=0.0,
    )
    micro_detail: FloatProperty(
        name="Micro Detail",
        description="Amount of fine original detail to keep (1 = full detail, 0 = smooth)",
        min=0.0,
        max=1.0,
        default=1.0,
    )
    apply_to_material: BoolProperty(
        name="Apply to Material",
        description=(
            "Redirect the active material's Base Color link to the generated "
            "texture. The original source node is kept and only the Base Color "
            "link is changed"
        ),
        default=True,
    )
    pack_output: BoolProperty(
        name="Pack into .blend",
        description=(
            "Pack the generated texture into the .blend file as well as saving "
            "the external PNG. Save the .blend to keep the packed data"
        ),
        default=False,
    )


classes = (StylizeTexSettings,)


def register_scene_properties() -> None:
    bpy.types.Scene.stylizetex_settings = bpy.props.PointerProperty(
        type=StylizeTexSettings
    )
    bpy.types.Scene.stylizetex_last_output = StringProperty(
        name="Last Stylized Output",
        description="Path of the most recently saved stylized texture",
        subtype="FILE_PATH",
        default="",
    )
    bpy.types.Scene.stylizetex_last_status = StringProperty(
        name="Last Stylized Status",
        description="Short status of the most recent processing run",
        default="",
    )


def unregister_scene_properties() -> None:
    if hasattr(bpy.types.Scene, "stylizetex_settings"):
        del bpy.types.Scene.stylizetex_settings
    if hasattr(bpy.types.Scene, "stylizetex_last_output"):
        del bpy.types.Scene.stylizetex_last_output
    if hasattr(bpy.types.Scene, "stylizetex_last_status"):
        del bpy.types.Scene.stylizetex_last_status


def reset_settings(settings: StylizeTexSettings) -> None:
    """Reset recognized settings to their defaults (tolerant to missing fields)."""

    for name, value in DEFAULTS.items():
        if hasattr(settings, name):
            setattr(settings, name, value)
