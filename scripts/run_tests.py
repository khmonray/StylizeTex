"""Repeatable test + packaging runner for the stylized texture add-on.

Runs, in order:

1. packaging (legacy ZIP + extension ZIP);
2. pure NumPy unit tests (any Python with NumPy);
3. Blender headless smoke test (register/unregister, operator, non-mutation);
4. Blender material application/packing/rollback test;
5. Blender metadata-stripped namespace import test;
6. Blender legacy add-on install/enable test;
7. Blender real extension install/enable test.

Usage::

    python scripts/run_tests.py
    python scripts/run_tests.py --python python --blender /path/to/blender
    python scripts/run_tests.py --skip-pure --skip-blender
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
TESTS_DIR = os.path.join(PROJECT_ROOT, "tests")
BUILD_DIR = os.path.join(PROJECT_ROOT, "build")
DEFAULT_BLENDER = os.environ.get("BLENDER_EXE", "blender")
LEGACY_ZIP = os.path.join(BUILD_DIR, "stylizetex-legacy.zip")
EXTENSION_ZIP = os.path.join(BUILD_DIR, "stylizetex-extension.zip")


def run(command: list[str], *, env=None, cwd: str = PROJECT_ROOT):
    print("\n$ " + " ".join(command))
    completed = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True)
    output = (completed.stdout or "") + (completed.stderr or "")
    print(output)
    return completed.returncode, output


def isolated_env(root: str) -> dict:
    env = os.environ.copy()
    for key, subdir in (
        ("BLENDER_USER_CONFIG", "config"),
        ("BLENDER_USER_SCRIPTS", "scripts"),
        ("BLENDER_USER_EXTENSIONS", "extensions"),
        ("BLENDER_USER_DATAFILES", "datafiles"),
    ):
        path = os.path.join(root, subdir)
        os.makedirs(path, exist_ok=True)
        env[key] = path
    return env


def summarize(name: str, returncode: int, output: str) -> tuple[str, str]:
    if "RESULT: SKIP" in output:
        status = "SKIP"
    elif "RESULT: FAIL" in output:
        status = "FAIL"
    elif returncode != 0:
        status = "FAIL"
    else:
        status = "PASS"
    return name, status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the add-on test suite.")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--blender", default=DEFAULT_BLENDER)
    parser.add_argument("--skip-pure", action="store_true")
    parser.add_argument("--skip-blender", action="store_true")
    args = parser.parse_args(argv)

    python = args.python
    blender = args.blender
    if not os.path.exists(blender):
        blender = shutil.which(blender) or shutil.which("blender") or blender

    results: list[tuple[str, str]] = []
    workdir = tempfile.mkdtemp(prefix="stylizetex_tests_")

    try:
        # 1. Packaging.
        python_executable = python if os.path.exists(python) else (shutil.which(python) or python)
        if os.path.exists(python_executable):
            code, output = run([python_executable, os.path.join(SCRIPT_DIR, "package.py"), "--blender", blender])
            results.append(summarize("package", code, output))
        else:
            code, output = 0, ""
            results.append(("package", "SKIP"))

        # 2. Pure NumPy tests.
        if not args.skip_pure:
            code, output = run(
                [python_executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"]
            )
            results.append(summarize("pure-unittest", code, output))

        if args.skip_blender:
            return _report(results)

        if not os.path.exists(blender):
            print(f"WARNING: Blender executable not found ({blender}); skipping Blender tests.")
            results.append(("blender", "SKIP"))
            return _report(results)

        # 3. Smoke test.
        code, output = run(
            [blender, "--background", "--factory-startup", "--python", os.path.join(TESTS_DIR, "blender_smoke_test.py")]
        )
        results.append(summarize("blender-smoke", code, output))

        # 4. Material application / packing / rollback test.
        code, output = run(
            [blender, "--background", "--factory-startup", "--python", os.path.join(TESTS_DIR, "blender_materials_test.py")]
        )
        results.append(summarize("blender-materials", code, output))

        # 5. Metadata-stripped namespace test.
        code, output = run(
            [blender, "--background", "--factory-startup", "--python", os.path.join(TESTS_DIR, "blender_namespace_test.py")]
        )
        results.append(summarize("blender-namespace", code, output))

        # 6. Legacy install/enable.
        legacy_profile = os.path.join(workdir, "legacy_profile")
        legacy_env = isolated_env(legacy_profile)
        legacy_env["STYLIZETEX_LEGACY_ZIP"] = LEGACY_ZIP
        code, output = run(
            [blender, "--background", "--python", os.path.join(TESTS_DIR, "blender_install_test.py")],
            env=legacy_env,
        )
        results.append(summarize("blender-legacy-install", code, output))

        # 7. Real extension install/enable.
        extension_profile = os.path.join(workdir, "extension_profile")
        extension_env = isolated_env(extension_profile)
        if os.path.isfile(EXTENSION_ZIP):
            run(
                [
                    blender,
                    "--background",
                    "--command",
                    "extension",
                    "validate",
                    EXTENSION_ZIP,
                ],
                env=extension_env,
            )
            run(
                [
                    blender,
                    "--background",
                    "--command",
                    "extension",
                    "install-file",
                    "-r",
                    "user_default",
                    "-e",
                    EXTENSION_ZIP,
                ],
                env=extension_env,
            )
            extension_env["STYLIZETEX_EXTENSION_INSTALLED"] = "1"
        code, output = run(
            [blender, "--background", "--python", os.path.join(TESTS_DIR, "blender_extension_test.py")],
            env=extension_env,
        )
        results.append(summarize("blender-extension-install", code, output))

        # 8. Synthetic A/B/C visual artifacts (test-only).
        code, output = run(
            [blender, "--background", "--factory-startup", "--python", os.path.join(TESTS_DIR, "blender_artifacts_test.py")]
        )
        results.append(summarize("blender-artifacts", code, output))

        return _report(results)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _report(results: list[tuple[str, str]]) -> int:
    print("\n" + "=" * 48)
    print("SUMMARY")
    print("=" * 48)
    failed = False
    for name, status in results:
        print(f"  {status:4}  {name}")
        if status == "FAIL":
            failed = True
    print("=" * 48)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
