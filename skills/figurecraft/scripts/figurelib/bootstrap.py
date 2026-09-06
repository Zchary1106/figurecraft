"""Select an installer-managed interpreter before importing renderer dependencies."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


_DLL_HANDLES = []


def load_runtime(config: Path) -> dict | None:
    if not config.exists():
        return None
    runtime = json.loads(config.read_text(encoding="utf-8"))
    if not isinstance(runtime, dict) or runtime.get("schema") != "figurecraft.runtime/1":
        raise ValueError("Unsupported FigureCraft runtime configuration; reinstall the skill")
    python = runtime.get("python")
    libraries = runtime.get("library_dirs", [])
    if not isinstance(python, str) or not Path(python).is_absolute() or not Path(python).is_file():
        raise ValueError("Configured FigureCraft Python is missing; rerun the one-command installer")
    if (not isinstance(libraries, list)
            or any(not isinstance(path, str) or not Path(path).is_absolute()
                   or not Path(path).is_dir() for path in libraries)):
        raise ValueError("Configured Cairo directory is missing or invalid; reinstall the skill")
    return runtime


def configure_libraries(libraries: list[str]) -> None:
    if not libraries:
        return
    key = {"darwin": "DYLD_FALLBACK_LIBRARY_PATH", "win32": "PATH"}.get(sys.platform, "LD_LIBRARY_PATH")
    existing = os.environ.get(key)
    os.environ[key] = os.pathsep.join([*libraries, *([existing] if existing else [])])
    if sys.platform == "win32":
        for path in libraries:
            _DLL_HANDLES.append(os.add_dll_directory(path))


def run(config: str | Path) -> int:
    runtime = load_runtime(Path(config))
    if runtime is not None:
        configure_libraries(runtime.get("library_dirs", []))
        # Do not resolve symlinks: POSIX venv executables often point at base Python.
        current = os.path.normcase(os.path.abspath(sys.executable))
        target = os.path.normcase(os.path.abspath(runtime["python"]))
        if current != target:
            return subprocess.run([runtime["python"], *sys.argv], check=False).returncode
    from .cli import main

    return main()
