from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .routing import segment_intersects_rect
from .typography import contrast_ratio


def lint_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    failures: list[str] = []
    warnings: list[str] = []
    base = path.parent
    for item in manifest.get("outputs", []):
        output = base / item["path"]
        if not output.is_file():
            failures.append(f"Missing output: {item['path']}")
        elif output.stat().st_size == 0:
            failures.append(f"Empty output: {item['path']}")
        elif output.suffix.lower() == ".svg":
            svg_failures, svg_warnings = lint_svg(output)
            failures.extend(svg_failures)
            warnings.extend(svg_warnings)
        elif output.suffix.lower() == ".drawio":
            failures.extend(lint_drawio(output, manifest.get("engine", {}).get("semantic_counts")))
    geometry = manifest.get("geometry", [])
    if (
        manifest.get("kind", "").startswith("diagram.")
        and manifest.get("kind") != "diagram.system-landscape"
        and len(geometry) > 15
    ):
        warnings.append(
            "Diagram has more than 15 elements; consider overview and detail views"
        )
    canvas = manifest.get("engine", {}).get("canvas")
    if canvas:
        for item in geometry:
            if (
                item["x"] < 0
                or item["y"] < 0
                or item["x"] + item["width"] > canvas["width"]
                or item["y"] + item["height"] > canvas["height"]
            ):
                failures.append(f"Node outside canvas: {item['id']}")
    for index, left in enumerate(geometry):
        for right in geometry[index + 1 :]:
            if left.get("container") or right.get("container"):
                continue
            if _overlap(left, right):
                failures.append(f"Node overlap: {left['id']} and {right['id']}")
    engine = manifest.get("engine", {})
    routing_nodes = engine.get("routing_nodes", geometry)
    edges = engine.get("edges", [])
    labels = engine.get("labels", [])
    for edge in edges:
        points = edge.get("points", [])
        if len(points) < 2:
            failures.append(f"Edge has no route: {edge['id']}")
            continue
        if canvas and any(x < 0 or y < 0 or x > canvas["width"] or y > canvas["height"] for x, y in points):
            failures.append(f"Edge outside canvas: {edge['id']}")
        for node in routing_nodes:
            if node.get("container") or node["id"] in {edge.get("from"), edge.get("to")}:
                continue
            if any(segment_intersects_rect(a, b, node) for a, b in zip(points, points[1:])):
                failures.append(f"Edge crosses unrelated node: {edge['id']} and {node['id']}")
    for index, label in enumerate(labels):
        if canvas and (label["x"] < 0 or label["y"] < 0 or label["x"] + label["width"] > canvas["width"] or label["y"] + label["height"] > canvas["height"]):
            failures.append(f"Label outside canvas: {label['id']}")
        for node in routing_nodes:
            if not node.get("container") and _overlap(label, node, tolerance=0.1):
                failures.append(f"Label overlaps node: {label['id']} and {node['id']}")
            leader = label.get("leader", [])
            if not node.get("container") and any(segment_intersects_rect(a, b, node) for a, b in zip(leader, leader[1:])):
                failures.append(f"Label leader crosses node: {label['id']} and {node['id']}")
        for other in labels[index + 1:]:
            if _overlap(label, other, tolerance=0.1):
                failures.append(f"Label overlap: {label['id']} and {other['id']}")
    return {
        "passed": not failures,
        "failures": failures,
        "warnings": warnings,
    }


def lint_svg(path: Path) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        return [f"Invalid SVG XML: {exc}"], warnings
    view_box = root.attrib.get("viewBox")
    canvas_box = None
    if not view_box:
        failures.append("SVG is missing viewBox")
    else:
        try:
            values = [float(value) for value in view_box.split()]
            if len(values) != 4 or not all(math.isfinite(value) for value in values) or values[2] <= 0 or values[3] <= 0:
                failures.append("SVG viewBox must contain positive width and height")
            else:
                canvas_box = values
        except ValueError:
            failures.append("SVG viewBox is not numeric")
    texts = [
        "".join(element.itertext()).strip()
        for element in root.iter()
        if element.tag.endswith("text")
    ]
    if any(not text for text in texts):
        warnings.append("SVG contains an empty text element")
    has_title = any(element.tag.endswith("title") for element in root.iter())
    has_desc = any(element.tag.endswith("desc") for element in root.iter())
    if not has_title:
        warnings.append("SVG is missing an accessible title")
    if not has_desc:
        warnings.append("SVG is missing an accessible description")
    measured_texts: list[tuple[str, dict[str, float]]] = []
    for element in root.iter():
        if not element.tag.endswith("text"):
            continue
        if "data-text-box" in element.attrib:
            text = "".join(element.itertext()).strip()
            try:
                bounds = _text_bounds(element.attrib["data-text-box"])
                container = _text_bounds(element.attrib.get("data-text-container", ""))
            except ValueError as exc:
                failures.append(f"Invalid text geometry for {text!r}: {exc}")
            else:
                if not _contains_bounds(container, bounds):
                    failures.append(f"Text outside container: {text!r}")
                if canvas_box is not None and not _contains_bounds(canvas_box, bounds):
                    failures.append(f"Text outside SVG canvas: {text!r}")
                if text and bounds[2] > 0:
                    measured_texts.append((text, dict(zip(("x", "y", "width", "height"), bounds, strict=True))))
            background = element.attrib.get("data-text-background")
            foreground = element.attrib.get("fill")
            if not background or not foreground:
                failures.append(f"Missing text contrast metadata: {text!r}")
            else:
                try:
                    contrast = contrast_ratio(foreground, background)
                except ValueError as exc:
                    failures.append(f"Invalid text contrast colors for {text!r}: {exc}")
                else:
                    if not math.isfinite(contrast) or contrast < 4.5:
                        failures.append(f"Insufficient text contrast: {text!r} ({contrast:.2f}:1; requires 4.5:1)")
        font_size = element.attrib.get("font-size")
        if font_size:
            try:
                if float(font_size.removesuffix("px")) < 7:
                    warnings.append("SVG contains text smaller than 7 px")
            except ValueError:
                warnings.append(f"SVG has an unrecognized font size: {font_size}")
    for index, (text, bounds) in enumerate(measured_texts):
        for other, other_bounds in measured_texts[index + 1:]:
            if _overlap(bounds, other_bounds, tolerance=0.5):
                failures.append(f"Text overlap: {text!r} and {other!r}")
    return failures, list(dict.fromkeys(warnings))


def _text_bounds(value: str) -> list[float]:
    bounds = [float(item) for item in value.split(",")]
    if len(bounds) != 4 or not all(math.isfinite(item) for item in bounds):
        raise ValueError("expected four finite rectangle coordinates")
    if bounds[2] < 0 or bounds[3] < 0:
        raise ValueError("rectangle dimensions must be nonnegative")
    return bounds


def _contains_bounds(container: list[float], bounds: list[float], tolerance: float = .1) -> bool:
    x, y, width, height = bounds
    cx, cy, cw, ch = container
    return (
        x >= cx - tolerance and y >= cy - tolerance
        and x + width <= cx + cw + tolerance
        and y + height <= cy + ch + tolerance
    )


def lint_drawio(path: Path, expected: dict[str, int] | None = None) -> list[str]:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        return [f"Invalid Draw.io XML: {exc}"]
    failures: list[str] = []
    if root.tag != "mxfile":
        failures.append("Draw.io root must be mxfile")
    cells = root.findall(".//mxCell")
    ids = [cell.get("id") for cell in cells]
    if len(ids) != len(set(ids)):
        failures.append("Draw.io contains duplicate cell IDs")
    known = set(ids)
    for cell in cells:
        if cell.get("edge") == "1":
            for endpoint in ("source", "target"):
                if cell.get(endpoint) not in known:
                    failures.append(f"Draw.io edge {cell.get('id')} has an unknown {endpoint}")
    if not any(cell.get("vertex") == "1" for cell in cells):
        failures.append("Draw.io file has no editable vertices")
    if root.get("compressed") != "false":
        failures.append("Draw.io file must use readable uncompressed XML")
    if expected:
        for flag, field in (("vertex", "vertices"), ("edge", "edges")):
            count = sum(cell.get(flag) == "1" for cell in cells)
            if count < expected.get(field, 0):
                failures.append(f"Draw.io is missing semantic {field}: expected at least {expected[field]}, found {count}")
    return failures


def _overlap(left: dict[str, Any], right: dict[str, Any], tolerance: float = 1.0) -> bool:
    return not (
        left["x"] + left["width"] <= right["x"] + tolerance
        or right["x"] + right["width"] <= left["x"] + tolerance
        or left["y"] + left["height"] <= right["y"] + tolerance
        or right["y"] + right["height"] <= left["y"] + tolerance
    )
