from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


def load_spec(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    if suffix == ".json":
        value = json.loads(text)
    elif suffix in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError("YAML input requires PyYAML") from exc
        value = yaml.safe_load(text)
    else:
        raise ValueError("FigureSpec must use .json, .yaml, or .yml")
    if not isinstance(value, dict):
        raise ValueError("FigureSpec root must be an object")
    return value


def load_columns(spec: dict[str, Any], spec_path: Path) -> dict[str, list[Any]]:
    data = spec.get("data", {})
    columns = data.get("columns")
    if columns is not None:
        if not isinstance(columns, dict):
            raise ValueError("data.columns must be an object")
        return {str(key): list(value) for key, value in columns.items()}

    source = data.get("source")
    if not source:
        raise ValueError("Chart data requires data.columns or data.source")
    source_path = (spec_path.parent / source).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"Data source not found: {source_path}")
    if source_path.suffix.lower() == ".csv":
        with source_path.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            raise ValueError(f"CSV data source is empty: {source_path}")
        result: dict[str, list[Any]] = {key: [] for key in rows[0]}
        for row in rows:
            for key, value in row.items():
                result[key].append(_coerce(value))
        return result
    if source_path.suffix.lower() == ".json":
        value = json.loads(source_path.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            return {str(key): list(items) for key, items in value.items()}
        if isinstance(value, list) and value and isinstance(value[0], dict):
            keys = value[0].keys()
            return {str(key): [row.get(key) for row in value] for key in keys}
        raise ValueError("JSON data must be a columns object or array of records")
    raise ValueError("data.source must be CSV or JSON")


def copy_source(spec_path: Path, output_dir: Path) -> Path:
    spec = load_spec(spec_path)
    data = spec.get("data", {})
    reference = data.get("source") if data.get("columns") is None else None
    original = (spec_path.parent / reference).resolve() if reference else None
    if original and not original.is_file():
        raise FileNotFoundError(f"Data source not found: {original}")
    digest = sha256(original) if original else None
    bundled_name = f"figure-input-{digest}{original.suffix.lower()}" if original else None
    destination = output_dir / f"figure-source{spec_path.suffix.lower()}"
    if (spec_path.parent.resolve() == output_dir.resolve() and reference == bundled_name
            and spec_path.name in {destination.name, f"figure-source-bundled{spec_path.suffix.lower()}"}):
        destination = spec_path
    if (destination.resolve() == spec_path.resolve() and reference
            and reference != bundled_name):
        destination = output_dir / f"figure-source-bundled{spec_path.suffix.lower()}"
    if destination.is_symlink():
        raise ValueError(f"Refusing to overwrite source symlink: {destination}")
    if destination.exists() and destination.resolve() != spec_path.resolve():
        if destination.read_bytes() != spec_path.read_bytes():
            manifest_path = output_dir / "figure-manifest.json"
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                manifest = {}
            previous = manifest.get("spec", {}) if isinstance(manifest, dict) else {}
            if (not isinstance(previous, dict) or previous.get("path") != destination.name
                    or previous.get("sha256") != sha256(destination)):
                raise ValueError(f"Refusing to overwrite untracked source: {destination}")

    if reference:
        bundled = output_dir / bundled_name
        if bundled.is_symlink():
            raise ValueError(f"Refusing to overwrite input symlink: {bundled}")
        if bundled.exists():
            if sha256(bundled) != digest:
                raise ValueError(f"Bundled input has conflicting contents: {bundled}")
        else:
            # Exclusive creation never overwrites an unrelated file, even on reruns.
            with bundled.open("xb") as target, original.open("rb") as source:
                shutil.copyfileobj(source, target)
            if sha256(bundled) != digest:
                bundled.unlink()
                raise ValueError("Data source changed while bundling; retry the render")
        if destination.resolve() == spec_path.resolve():
            return destination
        data["source"] = bundled.name
        if destination.suffix == ".json":
            write_json(destination, spec)
        else:
            import yaml

            destination.write_text(
                yaml.safe_dump(spec, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
    elif spec_path.resolve() != destination.resolve():
        shutil.copy2(spec_path, destination)
    return destination


def source_inputs(spec_path: Path) -> list[dict[str, str]]:
    data = load_spec(spec_path).get("data", {})
    reference = data.get("source") if data.get("columns") is None else None
    if not reference:
        return []
    source = spec_path.parent / reference
    return [{"path": str(reference), "sha256": sha256(source)}]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _coerce(value: str | None) -> Any:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return int(stripped)
    except ValueError:
        try:
            return float(stripped)
        except ValueError:
            return stripped
