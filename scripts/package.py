"""Package the stylized texture add-on for legacy and extension layouts.

Usage::

    python scripts/package.py                 # build both archives
    python scripts/package.py --legacy-only
    python scripts/package.py --extension-only
    python scripts/package.py --blender "E:\\Blender 5\\blender.exe"

Outputs (in ``build/`` by default):

* ``stylized_texture_addon-legacy.zip`` - classic add-on layout with a
  ``stylized_texture_addon/`` root folder and ``bl_info`` metadata.
* ``stylized_texture_addon-extension.zip`` - Blender extension layout with
  ``blender_manifest.toml`` at the archive root.

The extension archive is produced with Blender's official ``extension build``
command when a Blender executable is available, and falls back to a manual ZIP
of the package contents otherwise.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import zipfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
PACKAGE_NAME = "stylized_texture_addon"
PACKAGE_DIR = os.path.join(PROJECT_ROOT, PACKAGE_NAME)
BUILD_DIR = os.path.join(PROJECT_ROOT, "build")

EXCLUDED_DIRS = {"__pycache__", ".git", ".mypy_cache", ".pytest_cache"}
EXCLUDED_SUFFIXES = (".pyc", ".pyo")


def iter_package_files(package_dir: str = PACKAGE_DIR):
    """Yield package-relative file paths, skipping caches and compiled files."""

    for current_dir, dirnames, filenames in os.walk(package_dir):
        dirnames[:] = [name for name in dirnames if name not in EXCLUDED_DIRS]
        for filename in sorted(filenames):
            if filename.endswith(EXCLUDED_SUFFIXES):
                continue
            absolute = os.path.join(current_dir, filename)
            yield os.path.relpath(absolute, package_dir)


def build_legacy_zip(output_path: str, package_dir: str = PACKAGE_DIR) -> str:
    """Create the classic add-on archive with a top-level package folder."""

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for relative in iter_package_files(package_dir):
            archive.write(
                os.path.join(package_dir, relative),
                os.path.join(PACKAGE_NAME, relative).replace("\\", "/"),
            )
    return output_path


def _find_blender(explicit: str | None) -> str | None:
    if explicit:
        return explicit if os.path.exists(explicit) else None
    candidates = [os.environ.get("BLENDER_EXE", ""), shutil.which("blender") or ""]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return None


def build_extension_zip(
    output_path: str,
    package_dir: str = PACKAGE_DIR,
    blender: str | None = None,
) -> tuple[str, str]:
    """Create the extension archive.

    Returns ``(method, log)`` where ``method`` is ``"blender"`` or ``"manual"``.
    """

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    executable = _find_blender(blender)

    if executable:
        command = [
            executable,
            "--background",
            "--factory-startup",
            "--command",
            "extension",
            "build",
            "--source-dir",
            package_dir,
            "--output-filepath",
            os.path.abspath(output_path),
            "--valid-tags",
            "",
        ]
        completed = subprocess.run(command, capture_output=True, text=True)
        log = (completed.stdout or "") + (completed.stderr or "")
        if completed.returncode == 0 and os.path.exists(output_path):
            return "blender", log

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for relative in iter_package_files(package_dir):
            archive.write(
                os.path.join(package_dir, relative),
                relative.replace("\\", "/"),
            )
    return "manual", "Blender executable not available; wrote manual extension ZIP."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Package the stylized texture add-on.")
    parser.add_argument("--output-dir", default=BUILD_DIR)
    parser.add_argument("--blender", default=None)
    parser.add_argument("--legacy-only", action="store_true")
    parser.add_argument("--extension-only", action="store_true")
    args = parser.parse_args(argv)

    os.makedirs(args.output_dir, exist_ok=True)
    build_legacy = not args.extension_only
    build_extension = not args.legacy_only

    if build_legacy:
        path = build_legacy_zip(
            os.path.join(args.output_dir, f"{PACKAGE_NAME}-legacy.zip")
        )
        print(f"legacy:    {path}")

    if build_extension:
        path = os.path.join(args.output_dir, f"{PACKAGE_NAME}-extension.zip")
        method, log = build_extension_zip(path, blender=args.blender)
        print(f"extension: {path} ({method})")
        if method == "manual" and log:
            print(f"note: {log.strip()}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
