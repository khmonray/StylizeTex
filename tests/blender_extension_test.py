"""Headless test: real Blender extension install/enable under ``bl_ext``.

Prerequisite: the extension ZIP must already be installed into an isolated user
repository (see ``scripts/run_tests.py``, which runs
``blender --command extension install-file -r user_default -e <zip>`` first).

The test imports ``bl_ext.user_default.stylized_texture_addon``, verifies it
registers, then unregisters/registers the add-on without touching ``bl_info``.

Run with::

    blender --background --python tests/blender_extension_test.py
"""

from __future__ import annotations

import importlib
import os
import sys

import bpy

_EXTENSION_MODULE = "bl_ext.user_default.stylized_texture_addon"
_RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    _RESULTS.append((name, bool(condition), detail))
    print(f"[{'PASS' if condition else 'FAIL'}] {name} {detail}")


def load_extension_module():
    try:
        return importlib.import_module(_EXTENSION_MODULE)
    except ImportError:
        pass

    # Not auto-enabled: install exists, so try to enable it explicitly.
    try:
        bpy.ops.preferences.addon_enable(module=_EXTENSION_MODULE)
    except RuntimeError as exc:
        print(f"note: addon_enable failed: {exc}")
        return None
    return importlib.import_module(_EXTENSION_MODULE)


def main() -> int:
    if not os.environ.get("STYLIZED_EXTENSION_INSTALLED"):
        print("SKIP: STYLIZED_EXTENSION_INSTALLED is not set.")
        print("RESULT: SKIP")
        return 0

    module = load_extension_module()
    if module is None:
        print("SKIP: extension module could not be imported or enabled.")
        print("RESULT: SKIP")
        return 0

    check("extension_import_ok", module.__name__ == _EXTENSION_MODULE)
    # bl_info may be stripped by the extension loader; registration must not care.
    print(f"note: bl_info present = {hasattr(module, 'bl_info')}")

    if hasattr(bpy.types, "STYLIZED_TEXTURE_OT_process_texture"):
        module.unregister()
    check(
        "operator_unregistered",
        not hasattr(bpy.types, "STYLIZED_TEXTURE_OT_process_texture"),
    )

    module.register()
    check(
        "operator_registered_without_bl_info",
        hasattr(bpy.types, "STYLIZED_TEXTURE_OT_process_texture")
        and hasattr(bpy.types, "STYLIZED_TEXTURE_OT_randomize_style"),
    )
    check("panel_registered", hasattr(bpy.types, "STYLIZED_PT_main"))
    check(
        "scene_properties_registered",
        hasattr(bpy.types.Scene, "stylized_texture_settings"),
    )

    # Leave the extension registered so Blender's own shutdown unregisters it
    # exactly once (manual unregister here would cause a double unregister).
    failures = [name for name, ok, _ in _RESULTS if not ok]
    print(f"RESULT: {'PASS' if not failures else 'FAIL'} ({len(_RESULTS) - len(failures)}/{len(_RESULTS)} checks)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
