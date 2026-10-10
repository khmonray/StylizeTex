"""Headless test: metadata-stripped import under an extension-like namespace.

The add-on must register correctly when ``bl_info`` has been stripped from
``__init__.py`` (Blender extension loading may remove it) and when the package
is imported under a nested namespace such as ``bl_ext.<repo>.<id>``.

This test creates a temporary copy of the package with ``bl_info`` removed,
places it under a ``bl_ext_sim/user_default/`` namespace and imports it, then
verifies register/unregister work without any ``bl_info`` access.

Run with::

    blender --background --factory-startup --python tests/blender_namespace_test.py
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile

import bpy

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE_DIR = os.path.join(PROJECT_ROOT, "stylized_texture_addon")

_NAMESPACE = "bl_ext_sim"
_REPO = "user_default"
_PACKAGE = "stylized_texture_addon"
_RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    _RESULTS.append((name, bool(condition), detail))
    print(f"[{'PASS' if condition else 'FAIL'}] {name} {detail}")


def strip_bl_info(text: str) -> str:
    """Remove the literal ``bl_info = {...}`` block from an __init__ source."""

    pattern = re.compile(r"(?ms)^bl_info\s*=\s*\{.*?^\}\s*$")
    return pattern.sub("", text, count=1)


def build_namespace_copy(root: str) -> str:
    namespace_root = os.path.join(root, _NAMESPACE)
    repo_root = os.path.join(namespace_root, _REPO)
    os.makedirs(repo_root, exist_ok=True)

    for init_path in (
        os.path.join(namespace_root, "__init__.py"),
        os.path.join(repo_root, "__init__.py"),
    ):
        with open(init_path, "w", encoding="utf-8") as handle:
            handle.write("")

    destination = os.path.join(repo_root, _PACKAGE)
    shutil.copytree(
        PACKAGE_DIR,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )

    init_path = os.path.join(destination, "__init__.py")
    with open(init_path, "r", encoding="utf-8") as handle:
        source = handle.read()
    stripped = strip_bl_info(source)
    if re.search(r"(?m)^bl_info\s*=", stripped):
        raise AssertionError("Failed to strip bl_info from the packaged __init__.py.")
    with open(init_path, "w", encoding="utf-8") as handle:
        handle.write(stripped)

    return root


def main() -> int:
    temp_root = tempfile.mkdtemp(prefix="stylized_ns_")
    build_namespace_copy(temp_root)
    sys.path.insert(0, temp_root)

    import importlib

    module_name = f"{_NAMESPACE}.{_REPO}.{_PACKAGE}"
    addon = importlib.import_module(module_name)
    check("namespace_import_ok", addon is not None)
    check("bl_info_stripped", not hasattr(addon, "bl_info"))

    addon.register()
    check(
        "operator_registered",
        hasattr(bpy.types, "STYLIZED_TEXTURE_OT_process_texture")
        and hasattr(bpy.types, "STYLIZED_TEXTURE_OT_randomize_style"),
    )
    check("panel_registered", hasattr(bpy.types, "STYLIZED_PT_main"))
    addon.unregister()
    check(
        "operator_unregistered",
        not hasattr(bpy.types, "STYLIZED_TEXTURE_OT_process_texture")
        and not hasattr(bpy.types, "STYLIZED_TEXTURE_OT_randomize_style"),
    )

    failures = [name for name, ok, _ in _RESULTS if not ok]
    print(f"RESULT: {'PASS' if not failures else 'FAIL'} ({len(_RESULTS) - len(failures)}/{len(_RESULTS)} checks)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
