"""Blender image I/O with explicit color space handling.

Blender's ``Image.pixels`` exposes the raw buffer values. For byte images tagged
``sRGB`` those values are sRGB-encoded, not scene-linear. To process them
correctly we convert to scene-linear on read and back to sRGB on write.
"""

from __future__ import annotations

import numpy as np

from ..processing.color import linear_to_srgb, srgb_to_linear


def is_srgb_colorspace(colorspace_name: str | None) -> bool:
    """Return ``True`` when the image color space needs sRGB decoding."""

    if not colorspace_name:
        return False
    return colorspace_name.startswith("sRGB")


def read_image_pixels(image) -> np.ndarray:
    """Return the raw ``(H, W, 4)`` float pixels of a Blender image."""

    width, height = int(image.size[0]), int(image.size[1])
    if width <= 0 or height <= 0:
        raise ValueError("Image has no pixel data.")

    buffer = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(buffer)
    return buffer.reshape(height, width, 4)


def image_to_linear_rgba(image) -> np.ndarray:
    """Read a Blender image as a scene-linear ``(H, W, 4)`` float array."""

    raw = read_image_pixels(image)
    rgb = raw[..., :3]
    if is_srgb_colorspace(image.colorspace_settings.name):
        rgb = srgb_to_linear(rgb)
    return np.concatenate([rgb, raw[..., 3:4]], axis=-1).astype(np.float32)


def create_image_from_linear_rgba(
    name: str,
    linear_rgba: np.ndarray,
    *,
    colorspace: str = "sRGB",
    float_buffer: bool = False,
):
    """Create a new Blender image from a scene-linear RGBA array.

    The array is encoded to the output color space (sRGB by default) and stored
    in a new image. The source image is never referenced or modified.
    """

    import bpy  # local import keeps this module importable in pure-python tests

    height, width = int(linear_rgba.shape[0]), int(linear_rgba.shape[1])
    if is_srgb_colorspace(colorspace):
        rgb = linear_to_srgb(linear_rgba[..., :3])
    else:
        rgb = np.clip(linear_rgba[..., :3], 0.0, 1.0)
    alpha = np.clip(linear_rgba[..., 3], 0.0, 1.0)[..., None]
    pixels = np.concatenate([rgb, alpha], axis=-1).astype(np.float32)

    image = bpy.data.images.new(name, width, height, alpha=True, float_buffer=float_buffer)
    image.colorspace_settings.name = colorspace
    image.pixels.foreach_set(pixels.reshape(-1))
    image.update()
    return image


def save_png(image, filepath: str) -> None:
    """Save a Blender image as PNG to ``filepath``."""

    image.filepath_raw = filepath
    image.file_format = "PNG"
    image.save()


def pack_image(image) -> None:
    """Pack the image data into the current ``.blend`` and verify success.

    Packing keeps the texture inside the ``.blend`` so it does not depend on the
    external PNG. The caller is responsible for reminding the user to save the
    file, since packing is only persisted once the ``.blend`` is written.
    """

    image.pack()
    if getattr(image, "packed_file", None) is None:
        raise RuntimeError("Image packing did not produce packed data.")


def new_image_name(object_name: str) -> str:
    return f"{object_name}_stylized_basecolor"
