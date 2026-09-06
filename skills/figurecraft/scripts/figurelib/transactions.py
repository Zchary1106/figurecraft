"""Stage a single figure bundle and publish only its declared artifacts."""
from __future__ import annotations

import os
import shutil
import sys
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from .io import load_spec, sha256


def reject_symlinks(path: Path) -> None:
    system_aliases = {Path("/var"): Path("/private/var"), Path("/tmp"): Path("/private/tmp")}
    for part in (path, *path.parents):
        if part.is_symlink():
            expected = system_aliases.get(part) if sys.platform == "darwin" else None
            if expected is not None:
                destination = part.parent / part.readlink()
                if destination == expected and expected.resolve() == expected and expected.is_dir():
                    continue
            raise ValueError(f"Refusing to follow symlink: {part}")


def fingerprint(path: Path) -> tuple | None:
    reject_symlinks(path)
    if not path.exists():
        return None
    if not path.is_file():
        raise ValueError(f"Output artifact is not a regular file: {path}")
    info = path.stat()
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, sha256(path))


class RenderTransaction:
    def __init__(self, output: Path, stage: Path, names: set[str], inputs: list[Path]):
        self.output = output
        self.stage = stage
        self.retain_stage = False
        self.directory_identity = self._directory_identity()
        self.before = {name: fingerprint(output / name) for name in names}
        self.inputs = {path: fingerprint(path) for path in inputs}
        manifest_path = output / "figure-manifest.json"
        self.owned: dict[str, str] = {}
        self.removals: set[str] = set()
        self.previous = None
        if self.before["figure-manifest.json"] is not None:
            self.previous = load_spec(manifest_path)
            skill = self.previous.get("skill")
            source = self.previous.get("spec")
            if (not isinstance(skill, dict) or skill.get("name") not in ("figurecraft", "vizweaver")
                    or not isinstance(source, dict) or not isinstance(source.get("path"), str)
                    or Path(source["path"]).name != source["path"]
                    or not isinstance(self.previous.get("outputs"), list)
                    or not isinstance(self.previous.get("inputs", []), list)
                    or not isinstance(self.previous.get("generated_files", []), list)):
                raise ValueError(f"Refusing to overwrite untracked manifest: {manifest_path}")
            for item in [self.previous.get("spec", {}), *self.previous.get("inputs", []),
                         *self.previous["outputs"], *self.previous.get("generated_files", [])]:
                if isinstance(item, dict) and isinstance(item.get("path"), str) and item.get("sha256"):
                    self.owned[item["path"]] = item["sha256"]
            for item in self.previous["outputs"]:
                if not isinstance(item, dict):
                    continue
                name = item.get("path")
                if not isinstance(name, str) or name not in {"figure.svg", "figure.png", "figure.pdf", "figure.drawio"}:
                    continue
                destination = output / name
                if name in names or destination in self.inputs or destination.is_symlink() or not destination.is_file():
                    continue
                before = fingerprint(destination)
                if before is not None and before[-1] == item.get("sha256"):
                    self.before[name] = before
                    self.removals.add(name)

    def _directory_identity(self) -> tuple[int, int]:
        reject_symlinks(self.output)
        info = self.output.stat()
        return info.st_dev, info.st_ino

    def _check(self, name: str, expected: tuple | None) -> None:
        if self._directory_identity() != self.directory_identity:
            raise ValueError("Output directory changed during render; retry")
        if fingerprint(self.output / name) != expected:
            raise ValueError(f"Output changed during render: {self.output / name}")

    def publish(self) -> None:
        files = sorted(self.stage.iterdir(), key=lambda p: (p.name == "figure-manifest.json", p.name))
        replacements = []
        for path in files:
            name = path.name
            if name not in self.before or not path.is_file() or path.is_symlink():
                raise ValueError(f"Unexpected staged artifact: {name}")
            self._check(name, self.before[name])
            destination = self.output / name
            digest = sha256(path)
            if destination in self.inputs:
                if digest != self.inputs[destination][-1]:
                    raise ValueError(f"Output would overwrite an input: {destination}")
                continue
            previous = self.before[name]
            if previous is not None:
                if name == "figure-manifest.json":
                    pass
                elif self.owned.get(name) == previous[-1]:
                    pass
                elif previous[-1] == digest:
                    # Identical pre-existing inputs can be reused without writing them.
                    continue
                elif name == "index.html" and self.previous and "generated_files" not in self.previous:
                    # Legacy manifests did not hash their generated delivery page.
                    from .delivery import write_single_delivery
                    legacy = self.stage / ".legacy"
                    legacy.mkdir()
                    try:
                        source = self.output / self.previous["spec"]["path"]
                        reject_symlinks(source)
                        write_single_delivery(legacy, self.previous, load_spec(source))
                        if sha256(legacy / "index.html") != previous[-1]:
                            raise ValueError(f"Refusing to overwrite modified delivery: {destination}")
                    finally:
                        shutil.rmtree(legacy)
                else:
                    raise ValueError(f"Refusing to overwrite untracked or modified artifact: {destination}")
            replacements.append(path)
        for path, before in self.inputs.items():
            if fingerprint(path) != before:
                raise ValueError(f"Input changed during render: {path}")
        for name in self.removals:
            self._check(name, self.before[name])
        backup = self.stage / ".backup"
        backup.mkdir()
        moved: list[tuple[Path, bool, tuple | None]] = []
        operations = [(path, False) for path in replacements]
        operations.extend((self.stage / name, True) for name in self.removals)
        operations.sort(key=lambda item: (item[0].name == "figure-manifest.json", item[0].name))
        try:
            for path, remove in operations:
                destination = self.output / path.name
                self._check(path.name, self.before[path.name])
                had_previous = self.before[path.name] is not None
                if had_previous:
                    os.replace(destination, backup / path.name)
                moved.append((destination, had_previous, None))
                self._check(path.name, None)
                if not remove:
                    os.replace(path, destination)
                    moved[-1] = (destination, had_previous, fingerprint(destination))
        except (OSError, ValueError, RuntimeError):
            try:
                for destination, had_previous, installed in reversed(moved):
                    self._check(destination.name, installed)
                    if had_previous:
                        os.replace(backup / destination.name, destination)
                    elif installed is not None:
                        destination.unlink()
            except (OSError, ValueError, RuntimeError) as exc:
                self.retain_stage = True
                raise RuntimeError(f"Publication rollback blocked; original files retained in {backup}: {exc}") from exc
            raise


@contextmanager
def render_transaction(output: Path, names: set[str], inputs: list[Path]):
    reject_symlinks(output)
    output.mkdir(parents=True, exist_ok=True)
    lock = output / ".figure-render.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValueError("Figure is already rendering or has a retained .figure-render.lock; retry after checking the lock") from exc
    stage = output / f".figure-stage-{uuid4().hex}"
    transaction = None
    try:
        stage.mkdir()
        transaction = RenderTransaction(output, stage, names, inputs)
        yield transaction
    finally:
        try:
            if stage.exists() and not (transaction and transaction.retain_stage):
                shutil.rmtree(stage)
        finally:
            os.close(descriptor)
            lock.unlink()
