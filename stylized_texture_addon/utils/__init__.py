"""Blender-side utility helpers for the stylized texture add-on."""

from .images import (
    create_image_from_linear_rgba,
    image_to_linear_rgba,
    is_srgb_colorspace,
    new_image_name,
    pack_image,
    read_image_pixels,
    save_png,
)
from .materials import (
    apply_generated_image,
    find_generated_node,
    get_source_image,
    get_source_node,
    is_generated_image,
    is_generated_node,
    mark_generated_image,
    remove_generated_image_if_unused,
    remove_other_generated_images,
)
from .paths import build_output_filename, resolve_output_dir, resolve_output_filepath, sanitize_name
from .validation import (
    get_base_color_image,
    get_base_color_source_image,
    get_principled_bsdf,
    validate_base_color,
    validate_output_directory,
    validate_selected_mesh,
    validate_uv,
)

__all__ = [
    "apply_generated_image",
    "build_output_filename",
    "create_image_from_linear_rgba",
    "find_generated_node",
    "get_base_color_image",
    "get_base_color_source_image",
    "get_principled_bsdf",
    "get_source_image",
    "get_source_node",
    "image_to_linear_rgba",
    "is_generated_image",
    "is_generated_node",
    "is_srgb_colorspace",
    "mark_generated_image",
    "new_image_name",
    "pack_image",
    "read_image_pixels",
    "remove_generated_image_if_unused",
    "remove_other_generated_images",
    "resolve_output_dir",
    "resolve_output_filepath",
    "sanitize_name",
    "save_png",
    "validate_base_color",
    "validate_output_directory",
    "validate_selected_mesh",
    "validate_uv",
]
