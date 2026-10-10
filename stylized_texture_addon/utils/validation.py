"""Blender scene validation helpers for the stylized texture operator."""

from __future__ import annotations


def get_principled_bsdf(material):
    """Return the active Principled BSDF node of a material, or ``None``.

    We intentionally avoid reading ``Material.use_nodes`` (deprecated in Blender
    5.x, removed in 6.0). A non-``None`` ``node_tree`` is sufficient.
    """

    if material is None:
        return None
    node_tree = material.node_tree
    if node_tree is None:
        return None

    nodes = material.node_tree.nodes
    output = next(
        (node for node in nodes if node.type == "OUTPUT_MATERIAL" and node.is_active_output),
        None,
    )
    if output is None:
        output = next((node for node in nodes if node.type == "OUTPUT_MATERIAL"), None)
    if output is None:
        return None

    surface_input = output.inputs.get("Surface")
    if surface_input is None or not surface_input.is_linked:
        return None

    node = surface_input.links[0].from_node
    if node.type != "BSDF_PRINCIPLED":
        return None
    return node


def get_base_color_image(material):
    """Return the Image directly linked to Base Color, or ``None``.

    Only a direct link from an Image Texture node is accepted for Phase 1.
    """

    bsdf = get_principled_bsdf(material)
    if bsdf is None:
        return None

    base_color = bsdf.inputs.get("Base Color")
    if base_color is None or not base_color.is_linked:
        return None

    source = base_color.links[0].from_node
    if source.type != "TEX_IMAGE":
        return None
    return source.image


def get_base_color_source_image(material):
    """Return the original source image for display, never the generated one.

    The UI must keep showing the texture the user started from. Once the
    ``Apply to Material`` option redirects Base Color to our marked generated
    node, :func:`get_base_color_image` would return the generated result, so the
    recorded source image is resolved instead. This helper never raises; it
    returns ``None`` when no usable source can be resolved.
    """

    if material is None:
        return None
    try:
        # Local import avoids a circular import at module load time.
        from .materials import get_source_image

        return get_source_image(material)
    except Exception:
        return None


def validate_selected_mesh(context):
    """Return ``(object, None)`` or ``(None, error_message)``."""

    obj = context.active_object
    if obj is None or obj.type != "MESH":
        return None, "Please select a mesh object."
    return obj, None


def validate_base_color(obj):
    """Return ``(source_image, None)`` or ``(None, error_message)``.

    Validation still requires a direct Image Texture link to Base Color. When
    that link points at our marked generated node, the recorded original source
    image is returned instead so repeated processing never feeds the generated
    result back into the pipeline.
    """

    material = obj.active_material
    if material is None:
        return None, "Selected object has no material."

    image = get_base_color_image(material)
    if image is None:
        return None, (
            "No Base Color texture found. Link an Image Texture directly to the "
            "Principled BSDF Base Color input."
        )

    # Local import avoids a circular import at module load time.
    from .materials import get_base_color_node, get_source_node, is_generated_node

    if is_generated_node(get_base_color_node(material)):
        _source_node, source_image = get_source_node(material)
        if source_image is None:
            return None, (
                "The original Base Color source texture is unavailable. Restore "
                "the source Image Texture node or re-link it to Base Color."
            )
        image = source_image

    if image.size[0] <= 0 or image.size[1] <= 0:
        return None, "Base Color texture has no pixel data."

    return image, None


def validate_uv(obj):
    """Return ``None`` when a UV map exists, otherwise an error message."""

    mesh = obj.data
    if mesh is None or mesh.uv_layers is None or mesh.uv_layers.active is None:
        return "Selected object has no UV map."
    return None


def validate_output_directory(directory: str) -> str | None:
    """Return ``None`` when the directory exists and is writable."""

    import os

    if not directory:
        return "No output folder selected."

    expanded = os.path.abspath(directory)
    if not os.path.isdir(expanded):
        return "Output folder does not exist."
    if not os.access(expanded, os.W_OK):
        return "Output folder is not writable."
    return None
