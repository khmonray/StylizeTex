"""Output path resolution for saved stylized textures."""

from __future__ import annotations

import os
import re

_SAFE_NAME = re.compile(r"[^0-9A-Za-z._-]+")


def sanitize_name(name: str, fallback: str = "object") -> str:
    """Return a filesystem-safe version of ``name``."""

    cleaned = _SAFE_NAME.sub("_", str(name)).strip("_")
    return cleaned or fallback


def build_output_filename(object_name: str) -> str:
    return f"{sanitize_name(object_name)}_stylized_basecolor.png"


def resolve_output_dir(context, image, output_dir: str) -> str:
    """Resolve the directory used for saved PNG files.

    Falls back from the user setting, to the source image folder, to the blend
    file folder and finally to the system temporary directory.
    """

    import bpy

    if output_dir:
        return os.path.abspath(bpy.path.abspath(output_dir))

    if image is not None and getattr(image, "filepath", ""):
        source_path = bpy.path.abspath(image.filepath)
        source_dir = os.path.dirname(source_path)
        if source_dir and os.path.isdir(source_dir):
            return os.path.abspath(source_dir)

    blend_path = bpy.data.filepath
    if blend_path:
        blend_dir = os.path.dirname(os.path.abspath(blend_path))
        if os.path.isdir(blend_dir):
            return blend_dir

    return os.path.abspath(bpy.app.tempdir)


def resolve_output_filepath(context, obj, image, output_dir: str, explicit_filepath: str) -> str:
    """Resolve the final PNG file path for the operator."""

    import bpy

    if explicit_filepath:
        return os.path.abspath(bpy.path.abspath(explicit_filepath))

    directory = resolve_output_dir(context, image, output_dir)
    return os.path.join(directory, build_output_filename(obj.name))
