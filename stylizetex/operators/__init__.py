"""Operators for the stylized texture add-on."""

from .process import STYLIZETEX_OT_process_texture
from .randomize import STYLIZETEX_OT_randomize_style
from .reset import STYLIZETEX_OT_reset_settings

classes = (STYLIZETEX_OT_process_texture, STYLIZETEX_OT_reset_settings, STYLIZETEX_OT_randomize_style)

__all__ = [
    "STYLIZETEX_OT_process_texture",
    "STYLIZETEX_OT_randomize_style",
    "STYLIZETEX_OT_reset_settings",
    "classes",
]
