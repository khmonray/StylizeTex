# Blender add-on: StylizeTex
#
# ``bl_info`` is declared as a literal at the very start of this file, before any
# dependent imports, so the legacy add-on system can discover the package
# metadata. When the package is loaded as a Blender extension via
# ``blender_manifest.toml`` the loader may strip this metadata, therefore
# registration, UI and operators must NEVER depend on ``bl_info`` existing.

bl_info = {
    "name": "StylizeTex",
    "author": "github.com/khmonray",
    "version": (0, 0, 1),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > StylizeTex",
    "description": "Non-destructively turn a Base Color texture into a stylized version.",
    "category": "Object",
}

try:  # pragma: no cover - exercised in Blender
    import bpy  # noqa: F401
except ImportError:  # allows pure-python imports of the processing package
    bpy = None

if bpy is not None:
    from . import operators, panels, properties

    _classes = (*properties.classes, *operators.classes, *panels.classes)
else:  # pragma: no cover - only outside Blender
    _classes = ()


def register():
    if bpy is None:  # pragma: no cover - only outside Blender
        return
    for cls in _classes:
        bpy.utils.register_class(cls)
    properties.register_scene_properties()


def unregister():
    if bpy is None:  # pragma: no cover - only outside Blender
        return
    properties.unregister_scene_properties()
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
