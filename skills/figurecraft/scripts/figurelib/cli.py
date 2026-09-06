from __future__ import annotations

import argparse
import json
import platform
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .io import copy_source, load_columns, load_spec, sha256, source_inputs, write_json
from .lint import lint_manifest
from .styles import load_theme
from .validate import validate_chart_data, validate_spec


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    env_parser = subparsers.add_parser("check-env", help="Report required and optional tools")
    env_parser.add_argument("--format", action="append", dest="formats", choices=["svg", "png", "pdf", "drawio"])
    env_parser.add_argument("--formats", nargs="+", action="extend", dest="formats", choices=["svg", "png", "pdf", "drawio"])
    env_parser.add_argument("--kind")
    env_parser.add_argument("--cjk", "--check-cjk", action="store_true", dest="cjk")
    env_parser.add_argument("--json", action="store_true", dest="as_json")

    validate_parser = subparsers.add_parser("validate", help="Validate a FigureSpec")
    validate_parser.add_argument("spec", type=Path)

    render_parser = subparsers.add_parser("render", help="Render a FigureSpec")
    render_parser.add_argument("spec", type=Path)
    render_parser.add_argument("--output", type=Path, required=True)
    render_parser.add_argument("--no-lint", action="store_true")

    set_parser = subparsers.add_parser("render-set", help="Render source-linked overview and detail views")
    set_parser.add_argument("spec", type=Path)
    set_parser.add_argument("--output", type=Path, required=True)

    gallery_parser = subparsers.add_parser("gallery", help="Build a local SVG preview library of bundled examples")
    gallery_parser.add_argument("--output", type=Path, required=True)

    revise_parser = subparsers.add_parser("revise", help="Render a controlled revision into a fresh directory")
    revise_parser.add_argument("base_manifest", type=Path)
    revise_parser.add_argument("updated_spec", type=Path)
    revise_parser.add_argument("--mode", choices=["content-only", "local", "reflow"], default="content-only")
    revise_parser.add_argument("--unlock", nargs="+", action="extend", default=[])
    revise_parser.add_argument("--output", type=Path, required=True)

    lint_parser = subparsers.add_parser("lint", help="Lint a rendered manifest")
    lint_parser.add_argument("manifest", type=Path)

    args = parser.parse_args(argv)
    try:
        if args.command == "check-env":
            return _check_env(args.formats, args.kind, args.cjk, args.as_json)
        if args.command == "validate":
            spec_path = args.spec.resolve()
            spec = load_spec(spec_path)
            return _print_validation(spec, _skill_root())
        if args.command == "render":
            return _render(args.spec.absolute(), args.output.absolute(), args.no_lint)
        if args.command == "render-set":
            from .delivery import render_set

            spec_path = args.spec.resolve()
            errors = validate_spec(load_spec(spec_path), _skill_root())
            if errors:
                raise ValueError("\n".join(errors))
            print(render_set(spec_path, args.output.resolve(), _render))
            return 0
        if args.command == "gallery":
            from .delivery import render_gallery

            result = render_gallery(_skill_root() / "assets/examples", args.output.resolve(), _render)
            print(args.output.resolve() / "index.html")
            return 1 if result["failed"] else 0
        if args.command == "revise":
            return _revise(args.base_manifest.resolve(), args.updated_spec.resolve(),
                           args.output.resolve(), args.mode, args.unlock)
        if args.command == "lint":
            return _print_lint(args.manifest.resolve())
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


def _skill_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _print_validation(spec: dict[str, Any], skill_root: Path) -> int:
    errors = validate_spec(spec, skill_root)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    print("FigureSpec is valid")
    return 0


def _render(spec_path: Path, output_dir: Path, no_lint: bool) -> int:
    from .transactions import reject_symlinks, render_transaction

    spec_path, output_dir = spec_path.absolute(), output_dir.absolute()
    reject_symlinks(spec_path)
    reject_symlinks(output_dir)
    spec_path, output_dir = spec_path.resolve(), output_dir.resolve()
    spec = load_spec(spec_path)
    errors = validate_spec(spec, _skill_root())
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    manifest_path = output_dir / "figure-manifest.json"
    data = spec.get("data", {})
    inputs = [spec_path]
    reference = data.get("source") if data.get("columns") is None else None
    if reference:
        external = (spec_path.parent / reference).absolute()
        reject_symlinks(external)
        inputs.append(external.resolve())
    if spec["kind"].startswith("chart.") and data.get("source") and data.get("columns") is None:
        data_errors = validate_chart_data(spec, load_columns(spec, spec_path))
        if data_errors:
            raise ValueError("\n".join(data_errors))
    output = spec.get("output", {})
    formats = {"svg", str(output.get("primary", "svg")).lower(),
               *(str(extension).lower() for extension in output.get("additional", []))}
    generated = {"figure-manifest.json", "index.html", *(f"figure.{extension}" for extension in formats)}
    if any(path.resolve() == (output_dir / name).resolve() for path in inputs for name in generated):
        raise ValueError("Output would overwrite an input; choose a separate output directory")
    source_name = f"figure-source{spec_path.suffix.lower()}"
    bundled_name = f"figure-input-{sha256(inputs[1])}{inputs[1].suffix.lower()}" if reference else None
    if spec_path.parent == output_dir:
        if spec_path.name == f"figure-source-bundled{spec_path.suffix.lower()}":
            source_name = spec_path.name
        elif spec_path.name == source_name and reference and reference != bundled_name:
            source_name = f"figure-source-bundled{spec_path.suffix.lower()}"
    generated.add(source_name)
    if bundled_name:
        generated.add(bundled_name)
    with render_transaction(output_dir, generated, inputs) as transaction:
        source = copy_source(spec_path, transaction.stage)
        if source.name != source_name:
            source = source.rename(transaction.stage / source_name)
        if reference and reference == bundled_name:
            # Already-bundled inputs must retain their exact bytes on in-place rerenders.
            shutil.copy2(spec_path, source)
        result = _render_staged(source, transaction.stage, no_lint)
        if result:
            return result
        transaction.publish()
    print(manifest_path)
    return 0


def _render_staged(source: Path, output_dir: Path, no_lint: bool) -> int:
    from .charts import render_chart, render_gantt
    from .diagrams import render_diagram
    from .delivery import write_single_delivery

    spec = load_spec(source)
    manifest_path = output_dir / "figure-manifest.json"
    theme = load_theme(spec, _skill_root())
    kind = spec["kind"]
    geometry: list[dict[str, Any]] = []
    if kind.startswith("chart."):
        outputs, engine = render_chart(spec, source, output_dir, theme)
    elif kind == "project.gantt":
        outputs, engine = render_gantt(spec, output_dir, theme)
    elif kind.startswith("diagram."):
        outputs, engine, geometry = render_diagram(spec, output_dir, theme)
    else:
        raise ValueError(f"Unsupported kind: {kind}")
    manifest = {
        "schema_version": "1.0",
        "skill": {"name": "figurecraft", "version": __version__},
        "kind": kind,
        "view": spec.get("view"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "engine": engine,
        "theme": theme["name"],
        "spec": {"path": source.name, "sha256": sha256(source)},
        "inputs": source_inputs(source),
        "outputs": [
            {"path": path.name, "format": path.suffix.lstrip("."), "sha256": sha256(path)}
            for path in outputs
        ],
        "geometry": geometry,
        "assumptions": spec.get("assumptions", []),
        "provenance": spec.get("provenance", {"type": "unspecified", "verified": False}),
        "language": spec.get("language", "en"),
        "medium": spec.get("layout", {}).get("medium"),
        "checks": None,
    }
    write_json(manifest_path, manifest)
    if not no_lint:
        checks = lint_manifest(manifest_path)
        manifest["checks"] = checks
        write_json(manifest_path, manifest)
        if not checks["passed"]:
            for failure in checks["failures"]:
                print(f"error: {failure}", file=sys.stderr)
            return 1
    write_single_delivery(output_dir, manifest, spec)
    manifest["generated_files"] = [
        {"path": path.name, "sha256": sha256(path)}
        for path in sorted(output_dir.iterdir()) if path.name != manifest_path.name
    ]
    write_json(manifest_path, manifest)
    return 0


def _print_lint(path: Path) -> int:
    result = lint_manifest(path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


def _check_env(formats=None, kind=None, cjk=False, as_json=False) -> int:
    from .environment import environment_report, format_environment_report

    report = environment_report(formats=formats, kind=kind or "diagram.architecture", check_cjk=cjk)
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_environment_report(report))
    return 0 if report.get("ready", False) else 1


def _revise(base_manifest: Path, updated_spec: Path, output: Path, mode: str, unlocked: list[str]) -> int:
    from .delivery import write_single_delivery
    from .revision import prepare_revision

    if output == base_manifest.parent or output.is_relative_to(base_manifest.parent):
        raise ValueError("Revision output must be outside the base bundle; choose a fresh sibling directory")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("Revision output must be a fresh, empty directory")
    errors = validate_spec(load_spec(updated_spec), _skill_root())
    if errors:
        raise ValueError("\n".join(errors))
    prepared = prepare_revision(base_manifest, updated_spec, mode, unlocked_ids=unlocked)
    errors = validate_spec(prepared, _skill_root())
    if errors:
        raise ValueError("\n".join(errors))
    output.mkdir(parents=True, exist_ok=True)
    prepared_path = output / "revision-input.json"
    write_json(prepared_path, prepared)
    result = _render(prepared_path, output, False)
    manifest_path = output / "figure-manifest.json"
    if manifest_path.is_file():
        manifest = load_spec(manifest_path)
        manifest["revision"] = {
            "base_manifest": str(base_manifest), "base_manifest_sha256": sha256(base_manifest),
            "updated_source_sha256": sha256(updated_spec), "mode": mode, "unlocked_ids": unlocked,
        }
        write_json(manifest_path, manifest)
        write_single_delivery(output, manifest, prepared)
    return result
