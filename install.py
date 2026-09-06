#!/usr/bin/env python3
"""Install the FigureCraft core and specialist skills for supported agents."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import uuid
import venv
from pathlib import Path


SKILL_NAMES = (
    "figurecraft",
    "figurecraft-charts",
    "figurecraft-architecture",
    "figurecraft-neural-networks",
    "figurecraft-research-frameworks",
    "figurecraft-process-diagrams",
    "figurecraft-visual-critic",
)
PROJECT_LOCATIONS = {
    "claude": Path(".claude/skills"),
    "copilot": Path(".github/skills"),
    "codex": Path(".agents/skills"),
}
USER_LOCATIONS = {
    "claude": Path.home() / ".claude/skills",
    "copilot": Path.home() / ".copilot/skills",
    "codex": Path.home() / ".agents/skills",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--agent",
        choices=("claude", "copilot", "codex", "all"),
        default="all",
    )
    parser.add_argument("--scope", choices=("project", "user"), default="project")
    parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Project root for project-scoped installs.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace existing copies, preserving them under the target's .figurecraft-backups/.",
    )
    parser.add_argument("--setup", action="store_true",
                        help="Create a shared isolated Python runtime, install dependencies, and check readiness.")
    parser.add_argument("--require-export", action="store_true",
                        help="With --setup, require diagram PNG/PDF support before installing skills.")
    parser.add_argument("--runtime-root", type=Path,
                        help="With --setup, override the directory containing versioned runtimes.")
    parser.add_argument("--cairo-dir", type=Path, action="append", default=[],
                        help="With --setup, add a native Cairo library directory for this runtime only.")
    args = parser.parse_args()
    if not args.setup and (args.require_export or args.runtime_root or args.cairo_dir):
        parser.error("--require-export, --runtime-root and --cairo-dir require --setup")
    return args


def install_plan(agent: str, scope: str, project: Path, force: bool) -> tuple[tuple[Path, Path], ...]:
    if agent not in PROJECT_LOCATIONS or scope not in {"project", "user"}:
        raise ValueError("Choose a supported agent and project or user scope")
    source_root = Path(__file__).resolve().parent / "skills"
    base = (
        project.resolve() / PROJECT_LOCATIONS[agent]
        if scope == "project"
        else USER_LOCATIONS[agent]
    )
    pairs = tuple(
        (source_root / skill_name, base / skill_name)
        for skill_name in SKILL_NAMES
    )
    if base.is_relative_to(source_root) or source_root.is_relative_to(base):
        raise ValueError("Install target must not overlap the source skills directory")
    for path in (base, *base.parents):
        if path.is_symlink():
            raise ValueError(f"Install target must not traverse a symlink: {path}")
    for source, _ in pairs:
        if not (source / "SKILL.md").is_file():
            raise FileNotFoundError(f"Skill not found: {source}")
        if source.is_symlink() or any(path.is_symlink() for path in source.rglob("*")):
            raise ValueError(f"Source skill must not contain symlinks: {source}")
    for _, destination in pairs:
        if destination.is_symlink():
            raise ValueError(f"Installed skill must not be a symlink: {destination}")
    existing = [destination for _, destination in pairs if destination.exists()]
    if existing and not force:
        paths = ", ".join(str(path) for path in existing)
        raise FileExistsError(
            f"Installed skill paths already exist: {paths}; pass --force to replace them"
        )
    return pairs


def install(
    agent: str, scope: str, project: Path, force: bool, runtime: dict | None = None,
) -> tuple[Path, ...]:
    pairs = install_plan(agent, scope, project, force)
    base = pairs[0][1].parent
    existing = [destination for _, destination in pairs if destination.exists()]
    base.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    staging = base / f".figurecraft-stage-{token}"
    backup_root = base / ".figurecraft-backups"
    backup = backup_root / token
    if backup_root.is_symlink():
        raise ValueError(f"Backup directory must not be a symlink: {backup_root}")
    staging.mkdir()
    replaced: list[tuple[Path, Path]] = []
    installed: list[Path] = []
    try:
        for source, destination in pairs:
            shutil.copytree(
                source,
                staging / destination.name,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store", ".figurecraft-runtime.json"),
            )
        config = staging / "figurecraft/scripts/.figurecraft-runtime.json"
        if runtime is not None:
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(json.dumps(runtime, indent=2) + "\n", encoding="utf-8")
        else:
            previous_config = base / "figurecraft/scripts/.figurecraft-runtime.json"
            if previous_config.is_symlink():
                raise ValueError(f"Runtime configuration must not be a symlink: {previous_config}")
            if previous_config.exists():
                config.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(previous_config, config)
        if existing:
            backup.mkdir(parents=True)
        for _, destination in pairs:
            if destination.exists():
                # Recheck after staging: never replace a concurrently created copy without force.
                if not force or destination.is_symlink():
                    raise FileExistsError(f"Install target changed during staging: {destination}")
                saved = backup / destination.name
                saved.parent.mkdir(parents=True, exist_ok=True)
                destination.rename(saved)
                replaced.append((destination, saved))
            (staging / destination.name).rename(destination)
            installed.append(destination)
    except Exception:
        for destination in reversed(installed):
            shutil.rmtree(destination)
        for destination, saved in reversed(replaced):
            saved.rename(destination)
        if backup.exists() and not any(backup.iterdir()):
            backup.rmdir()
        raise
    finally:
        shutil.rmtree(staging)
    return tuple(destination for _, destination in pairs)


def runtime_python(directory: Path, platform: str | None = None) -> Path:
    return directory / ("Scripts/python.exe" if (platform or sys.platform) == "win32" else "bin/python")


def prepare_runtime(
    root: Path, require_export: bool = False, cairo_dirs: list[Path] | None = None,
) -> dict:
    if sys.version_info < (3, 11):
        raise ValueError("Python 3.11 or newer is required; install it from python.org and retry")
    root = root.absolute()
    source = Path(__file__).resolve().parent
    for path in (root, *root.parents):
        if path.is_symlink():
            raise ValueError(f"Runtime directory must not traverse a symlink: {path}")
    if root.is_relative_to(source / "skills"):
        raise ValueError("Runtime directory must be outside the source skills directory")
    libraries = [path.absolute() for path in cairo_dirs or []]
    if not libraries and sys.platform == "darwin":
        libraries = [path for path in (Path("/opt/homebrew/opt/cairo/lib"),
                                      Path("/usr/local/opt/cairo/lib")) if path.is_dir()]
    for path in libraries:
        if not path.is_dir():
            raise ValueError(f"Cairo library directory not found: {path}")
    root.mkdir(parents=True, exist_ok=True)
    directory = root / uuid.uuid4().hex
    directory.mkdir()
    try:
        venv.EnvBuilder(with_pip=True).create(directory)
        python = runtime_python(directory)
        subprocess.run([str(python), "-m", "pip", "install", f"{source}[export]"], check=True)
        runtime = {"schema": "figurecraft.runtime/1", "python": str(python),
                   "library_dirs": [str(path) for path in libraries]}
        config = directory / "runtime.json"
        config.write_text(json.dumps(runtime, indent=2) + "\n", encoding="utf-8")
        # Probe through the same bootstrap used by all installed hosts.
        probe = directory / "probe.py"
        probe.write_text(
            "import sys\n"
            f"sys.path.insert(0, {str(source / 'skills/figurecraft/scripts')!r})\n"
            "from figurelib.bootstrap import run\n"
            f"raise SystemExit(run({str(config)!r}))\n", encoding="utf-8")
        formats = ["svg", "drawio", *(["png", "pdf"] if require_export else [])]
        subprocess.run([str(python), str(probe), "check-env", "--formats", *formats], check=True)
        probe.unlink()
        return runtime
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError):
        shutil.rmtree(directory)
        raise


def main() -> int:
    args = parse_args()
    agents = PROJECT_LOCATIONS if args.agent == "all" else (args.agent,)
    for agent in agents:
        install_plan(agent, args.scope, args.project, args.force)
    runtime = None
    if args.setup:
        base = args.project.resolve() if args.scope == "project" else Path.home()
        runtime = prepare_runtime(args.runtime_root or base / ".figurecraft/runtimes",
                                  args.require_export, args.cairo_dir)
        print(f"Shared runtime: {runtime['python']}")
    for agent in agents:
        destinations = install(agent, args.scope, args.project, args.force, runtime)
        for destination in destinations:
            print(f"Installed {agent}: {destination}")
        if args.force:
            print(f"Previous copies, if any, preserved in: {destinations[0].parent / '.figurecraft-backups'}")
    print("Installation complete. Restart or reload your agent to discover FigureCraft.")
    if runtime:
        print("Installed figure.py commands select the shared runtime automatically.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Installation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
