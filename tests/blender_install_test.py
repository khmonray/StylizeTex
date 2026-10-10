"""Headless test: install the packaged legacy ZIP and enable the add-on.

Run with::

    set STYLIZETEX_LEGACY_ZIP=...\\stylizetex-legacy.zip
    blender --background --factory-startup --python tests/blender_install_test.py

The test is skipped (without failing) when ``STYLIZETEX_LEGACY_ZIP`` is not set.
"""

from __future__ import annotations

import os
import sys

import bpy

_MODULE_NAME = "stylizetex"
_RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    _RESULTS.append((name, bool(condition), detail))
    print(f"[{'PASS' if condition else 'FAIL'}] {name} {detail}")


def main() -> int:
    zip_path = os.environ.get("STYLIZETEX_LEGACY_ZIP", "")
    if not zip_path or not os.path.isfile(zip_path):
        print(f"SKIP: STYLIZETEX_LEGACY_ZIP is not a file: {zip_path!r}")
        print("RESULT: SKIP")
        return 0

    installed = bpy.ops.preferences.addon_install(filepath=zip_path, overwrite=True)
    check("addon_install_finished", installed == {"FINISHED"}, str(installed))

    enabled = bpy.ops.preferences.addon_enable(module=_MODULE_NAME)
    check("addon_enable_finished", enabled == {"FINISHED"}, str(enabled))
    check("addon_listed", _MODULE_NAME in bpy.context.preferences.addons)
    check(
        "operator_registered",
        hasattr(bpy.types, "STYLIZETEX_OT_process_texture")
        and hasattr(bpy.types, "STYLIZETEX_OT_randomize_style"),
    )
    check("panel_registered", hasattr(bpy.types, "STYLIZETEX_PT_main"))
    check(
        "scene_properties_registered",
        hasattr(bpy.types.Scene, "stylizetex_settings"),
    )

    disabled = bpy.ops.preferences.addon_disable(module=_MODULE_NAME)
    check("addon_disable_finished", disabled == {"FINISHED"}, str(disabled))
    check(
        "operator_unregistered",
        not hasattr(bpy.types, "STYLIZETEX_OT_process_texture")
        and not hasattr(bpy.types, "STYLIZETEX_OT_randomize_style"),
    )

    failures = [name for name, ok, _ in _RESULTS if not ok]
    print(f"RESULT: {'PASS' if not failures else 'FAIL'} ({len(_RESULTS) - len(failures)}/{len(_RESULTS)} checks)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
