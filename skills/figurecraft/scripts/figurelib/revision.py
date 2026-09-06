from __future__ import annotations

import copy
import math
from pathlib import Path
from typing import Any

from .io import load_spec, sha256
from .routing import segment_intersects_rect
from .styles import load_theme
from .typography import DEFAULT_FONT, label_height


_RECT = ("x", "y", "width", "height")
_TEXT = {"label", "title", "subtitle", "caption", "note", "technology"}
_EPSILON = 1e-6


def _theme(spec: dict[str, Any]) -> dict[str, Any]:
    return load_theme(spec, Path(__file__).resolve().parents[2])


def _footer_height(spec: dict[str, Any], theme: dict[str, Any], width: float) -> float:
    if "provenance" not in spec:
        return 0.0
    from .provenance import append_provenance

    _, height = append_provenance(
        f'<svg viewBox="0 0 {width:.0f} 1" width="{width:.0f}" height="1"></svg>', spec, theme,
    )
    return float(height) - 1 if height is not None else 0.0


def _supported(spec: dict[str, Any]) -> bool:
    return (
        str(spec.get("kind", "")).startswith("diagram.")
        and spec["kind"] not in {"diagram.framework-matrix", "diagram.cnn-architecture", "diagram.swimlane"}
        and not spec.get("framework_stages")
    )


def _entities(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    field = "zones" if spec.get("kind") == "diagram.system-landscape" else "nodes"
    values = spec.get(field, [])
    if not isinstance(values, list) or not values:
        raise ValueError(f"Revision requires nonempty {field} with stable IDs")
    result = {}
    for item in values:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
            raise ValueError(f"Revision requires stable {field} IDs")
        if item["id"] in result:
            raise ValueError(f"Duplicate revision ID: {item['id']}")
        result[item["id"]] = item
    return result


def _edges(spec: dict[str, Any], ids: set[str]) -> dict[str, dict[str, Any]]:
    values = spec.get("connections" if spec.get("kind") == "diagram.system-landscape" else "edges", [])
    result = {}
    for item in values:
        if not isinstance(item, dict) or item.get("from") not in ids or item.get("to") not in ids:
            raise ValueError("Revision edge refers to a missing node or zone ID")
        edge_id = str(item.get("id", f"{item['from']}--{item['to']}"))
        if edge_id in result:
            raise ValueError(f"Ambiguous revision edge ID: {edge_id}; assign unique edge IDs")
        result[edge_id] = item
    return result


def _rectangle(value: Any, identifier: str) -> dict[str, float]:
    if not isinstance(value, dict):
        raise ValueError(f"Invalid revision geometry for {identifier}")
    result = {}
    for key in _RECT:
        number = value.get(key)
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number):
            raise ValueError(f"Revision geometry {identifier}.{key} must be finite")
        if number < 0 or (key in {"width", "height"} and number == 0):
            raise ValueError(f"Invalid revision geometry {identifier}.{key}")
        result[key] = float(number)
    return result


def _without_placement(spec: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(spec)
    if isinstance(result.get("layout"), dict):
        result["layout"].pop("placement", None)
        if not result["layout"]:
            result.pop("layout")
    return result


def _text_only(before: Any, after: Any, path: str = "") -> None:
    if before == after:
        return
    if isinstance(before, dict) and isinstance(after, dict):
        for key in before.keys() | after.keys():
            previous, current = before.get(key), after.get(key)
            location = f"{path}.{key}" if path else key
            if key in _TEXT and all(value is None or isinstance(value, str) for value in (previous, current)):
                continue
            if key not in before or key not in after:
                raise ValueError(f"content-only revision cannot change nontext field {location}")
            _text_only(previous, current, location)
        return
    if isinstance(before, list) and isinstance(after, list) and len(before) == len(after):
        for index, (previous, current) in enumerate(zip(before, after)):
            _text_only(previous, current, f"{path}[{index}]")
        return
    raise ValueError(f"content-only revision cannot change nontext field {path}")


def _snapshot(spec: dict[str, Any]) -> tuple[float, float, list[dict[str, Any]]]:
    # Recompute in memory: revisions must not trust edited manifest coordinates.
    from . import diagrams

    spec, theme = diagrams.prepare_media(spec, _theme(spec))
    spec, theme = diagrams._semantic_style(spec, theme)
    kind = spec["kind"]
    if kind == "diagram.system-landscape":
        _, width, height, geometry = diagrams._system_landscape_svg(spec, theme)
    elif kind == "diagram.framework-matrix":
        _, width, height, geometry = diagrams.render_framework_matrix_svg(spec, theme)
    elif kind == "diagram.cnn-architecture":
        _, width, height, geometry = diagrams.render_cnn_svg(spec, theme)
    elif spec.get("framework_stages"):
        _, width, height, geometry = diagrams.render_framework_svg(spec, theme)
    else:
        if kind == "diagram.swimlane":
            boxes, width, height, lanes = diagrams._layout_swimlane(spec, theme)
        else:
            boxes, width, height = diagrams._layout_layered(spec, spec.get("layout", {}).get("direction", "LR"), theme)
            lanes = []
        height = diagrams._reserve_title(spec, boxes, lanes, width, height, theme)
        width, height = apply_placement(spec, boxes, width, height)
        geometry = diagrams._route_geometry(spec, boxes, theme, width)
        width, height = diagrams._constrained_routing_canvas(spec, geometry, width, height)
    if "provenance" in spec:
        height = float(f"{height:.0f}") + _footer_height(spec, theme, width)
    return width, height, geometry


def _equivalent(first: Any, second: Any) -> bool:
    if isinstance(first, dict) and isinstance(second, dict):
        return first.keys() == second.keys() and all(_equivalent(first[key], second[key]) for key in first)
    if isinstance(first, (list, tuple)) and isinstance(second, (list, tuple)):
        return len(first) == len(second) and all(_equivalent(a, b) for a, b in zip(first, second))
    if isinstance(first, (int, float)) and isinstance(second, (int, float)):
        return math.isfinite(first) and math.isfinite(second) and abs(first - second) <= _EPSILON
    return first == second


def _landscape_nested(zone: dict[str, Any], width: float, theme: dict[str, Any]) -> dict[str, Any]:
    from .diagrams import landscape_section_layout, landscape_zone_layout

    layout = landscape_zone_layout(zone, width, theme)
    sections = []
    for rect in layout["sections"]:
        section = zone["sections"][rect["index"]]
        inner = landscape_section_layout(section, rect["width"], theme)
        sections.append({
            **rect, "header_height": inner["header_height"],
            "items": inner["items"], "note": inner["note"],
        })
    return {"header_height": layout["header_height"], "sections": sections}


def _bundle_file(manifest_path: Path, reference: Any) -> Path:
    if not isinstance(reference, str) or not reference:
        raise ValueError("Base manifest is missing its bundled source path")
    root = manifest_path.resolve().parent
    path = (root / reference).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Base manifest source must be an existing file inside its bundle")
    return path


def prepare_revision(
    base_manifest: Path,
    updated_spec_path: Path,
    mode: str,
    unlocked_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Return a new constrained spec, without modifying either input or bundle."""
    if mode not in {"content-only", "local", "reflow"}:
        raise ValueError("Revision mode must be content-only, local, or reflow")
    unlocked = list(unlocked_ids or [])
    if any(not isinstance(identifier, str) or not identifier for identifier in unlocked) or len(set(unlocked)) != len(unlocked):
        raise ValueError("unlocked_ids must contain unique nonempty IDs")
    if mode == "local" and not unlocked:
        raise ValueError("local revision requires explicit nonempty unlocked_ids")
    if mode != "local" and unlocked:
        raise ValueError("unlocked_ids are only valid for local revision")
    base_manifest = Path(base_manifest)
    manifest = load_spec(base_manifest)
    reference = manifest.get("spec", {})
    if not isinstance(reference, dict):
        raise ValueError("Base manifest is missing its bundled source")
    source = _bundle_file(base_manifest, reference.get("path"))
    if reference.get("sha256") != sha256(source):
        raise ValueError("Base source hash mismatch: bundled source was modified")
    for entry in manifest.get("inputs", []):
        path = _bundle_file(base_manifest, entry.get("path"))
        if entry.get("sha256") != sha256(path):
            raise ValueError("Base input hash mismatch")
    before, updated = load_spec(source), load_spec(Path(updated_spec_path))
    if before.get("kind") != updated.get("kind") or manifest.get("kind") != before.get("kind"):
        raise ValueError("Revision cannot change figure kind")
    if not str(before.get("kind", "")).startswith("diagram."):
        raise ValueError("Constrained revision supports diagrams only")
    if mode != "reflow" and (not _supported(before) or not _supported(updated)):
        raise ValueError("This specialized renderer does not support placement locks; use reflow")
    engine = manifest.get("engine", {})
    if not isinstance(engine, dict) or engine.get("renderer") != "builtin-svg":
        raise ValueError("Revision requires a builtin-svg base engine")
    width, height, actual_geometry = _snapshot(before)
    recorded_geometry = manifest.get("geometry")
    if not isinstance(recorded_geometry, list) or not recorded_geometry:
        raise ValueError("Base manifest is missing geometry")
    recorded = {}
    for item in recorded_geometry:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or item["id"] in recorded:
            raise ValueError("Base geometry has missing or duplicate IDs")
        recorded[item["id"]] = _rectangle(item, item["id"])
    actual = {item["id"]: _rectangle(item, item["id"]) for item in actual_geometry}
    if not _equivalent(recorded, actual) or not _equivalent(engine.get("canvas"), {"width": width, "height": height}):
        raise ValueError("Base geometry or canvas does not match the bundled source renderer")
    if not _equivalent(engine.get("edges", []), getattr(actual_geometry, "edges", [])):
        raise ValueError("Base edge routes do not match the bundled source renderer")
    result = _without_placement(updated)
    if mode == "reflow":
        return result
    old_nodes, new_nodes = _entities(before), _entities(updated)
    old_edges, new_edges = _edges(before, set(old_nodes)), _edges(updated, set(new_nodes))
    if set(recorded) != set(old_nodes):
        raise ValueError("Base geometry IDs do not match primary nodes or zones")
    unknown = set(unlocked) - (old_nodes.keys() | new_nodes.keys())
    if unknown:
        raise ValueError(f"Unknown unlocked IDs: {', '.join(sorted(unknown))}")
    if (old_nodes.keys() ^ new_nodes.keys()) - set(unlocked):
        raise ValueError("Added or removed nodes must be explicitly unlocked")
    if mode == "content-only":
        _text_only(_without_placement(before), result)
    locked = {identifier: recorded[identifier] for identifier in old_nodes if identifier not in unlocked}
    routes = []
    for route in engine.get("edges", []):
        identifier = route["id"]
        if route["from"] not in locked or route["to"] not in locked or identifier not in new_edges:
            continue
        old_edge = {key: value for key, value in old_edges[identifier].items() if key not in _TEXT}
        new_edge = {key: value for key, value in new_edges[identifier].items() if key not in _TEXT}
        if old_edge == new_edge:
            routes.append(copy.deepcopy(route))
    result.setdefault("layout", {})["placement"] = {
        "mode": mode, "boxes": locked, "canvas": {"width": width, "height": height},
        "unlocked_ids": unlocked, "routes": routes, "source_sha256": reference["sha256"],
    }
    # Fail before returning an unusable plan, including text overflow at locked widths.
    from .diagrams import _semantic_style

    resolved, theme = _semantic_style(result, _theme(result))
    resolved_nodes = _entities(resolved)
    for identifier, rect in locked.items():
        _check_content(resolved_nodes[identifier], rect, resolved, theme)
        if result["kind"] == "diagram.system-landscape":
            old_nested = _landscape_nested(old_nodes[identifier], rect["width"], _theme(before))
            new_nested = _landscape_nested(new_nodes[identifier], rect["width"], theme)
            if not _equivalent(old_nested, new_nested):
                raise ValueError(
                    f"Locked landscape internal geometry changed for {identifier}; "
                    "unlock this zone or use reflow"
                )
    revised_width, revised_height, revised_geometry = _snapshot(result)
    revised_rects = {item["id"]: _rectangle(item, item["id"]) for item in revised_geometry}
    if any(not _equivalent(rect, revised_rects.get(identifier)) for identifier, rect in locked.items()):
        raise ValueError("Renderer did not preserve locked geometry; use reflow")
    if not _equivalent((width, height), (revised_width, revised_height)):
        raise ValueError("Revision content or routing overflow changes the locked canvas; use reflow")
    revised_routes = {item["id"]: item for item in getattr(revised_geometry, "edges", [])}
    if any(not _equivalent(route, revised_routes.get(route["id"])) for route in routes):
        raise ValueError("Revision cannot preserve unrelated edge paths with these constraints; use reflow")
    return result


def apply_placement(
    spec: dict[str, Any], boxes: dict[str, Any], width: float, height: float,
) -> tuple[float, float]:
    """Apply locked rectangles to generic Boxes or landscape zone dictionaries."""
    placement = spec.get("layout", {}).get("placement")
    if placement is None:
        return width, height
    if not _supported(spec):
        raise ValueError("This renderer does not support placement locks; use reflow")
    if not isinstance(placement, dict) or placement.get("mode") not in {"content-only", "local"}:
        raise ValueError("Invalid placement mode")
    locks = placement.get("boxes")
    unlocked = placement.get("unlocked_ids", [])
    if not isinstance(locks, dict) or not isinstance(unlocked, list) or any(not isinstance(item, str) for item in unlocked):
        raise ValueError("Invalid placement boxes or unlocked_ids")
    if len(set(unlocked)) != len(unlocked) or set(locks) & set(unlocked):
        raise ValueError("Placement locked and unlocked IDs must be disjoint and unique")
    if placement["mode"] == "content-only" and (unlocked or set(locks) != set(boxes)):
        raise ValueError("content-only placement must lock every primary node or zone")
    if placement["mode"] == "local" and not unlocked:
        raise ValueError("local placement requires explicit nonempty unlocked_ids")
    if set(locks) - set(boxes) or set(boxes) - set(locks) - set(unlocked):
        raise ValueError("Placement IDs do not match renderer nodes or zones")
    canvas = placement.get("canvas", {})
    if not isinstance(canvas, dict):
        raise ValueError("Invalid placement canvas")
    canvas_rect = _rectangle({"x": 0, "y": 0, **canvas}, "canvas")
    width, height = canvas_rect["width"], canvas_rect["height"]
    theme = _theme(spec)
    # The manifest canvas includes the footer; the renderer appends it after layout.
    height = round(height - _footer_height(spec, theme, width), 6)
    if height <= 0:
        raise ValueError("Revision footer overflow exceeds the locked canvas")
    candidates = {}
    for identifier, box in boxes.items():
        value = box if isinstance(box, dict) else {key: getattr(box, key) for key in _RECT}
        candidates[identifier] = _rectangle(locks.get(identifier, value), identifier)
    for identifier, rect in candidates.items():
        if rect["x"] + rect["width"] > width + _EPSILON or rect["y"] + rect["height"] > height + _EPSILON:
            raise ValueError(f"Revision node {identifier} is out of canvas; unlock or use reflow")
    values = list(candidates.items())
    for index, (first_id, first) in enumerate(values):
        for second_id, second in values[index + 1:]:
            if (min(first["x"] + first["width"], second["x"] + second["width"]) > max(first["x"], second["x"]) + _EPSILON
                    and min(first["y"] + first["height"], second["y"] + second["height"]) > max(first["y"], second["y"]) + _EPSILON):
                raise ValueError(f"Revision overlap between {first_id} and {second_id}; unlock or use reflow")
    routes = placement.get("routes", [])
    if not isinstance(routes, list):
        raise ValueError("Invalid placement routes")
    for route in routes:
        if not isinstance(route, dict) or route.get("from") not in locks or route.get("to") not in locks:
            raise ValueError("Preserved route endpoints must both be locked")
        points = route.get("points", [])
        if not isinstance(points, list) or len(points) < 2:
            raise ValueError("Preserved route requires at least two points")
        for point in points:
            if (not isinstance(point, (list, tuple)) or len(point) != 2
                    or any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in point)):
                raise ValueError("Preserved route points must be finite coordinate pairs")
            if not (0 <= point[0] <= width and 0 <= point[1] <= height):
                raise ValueError("Preserved route is out of canvas")
        for start, end in zip(points, points[1:]):
            if any(segment_intersects_rect(start, end, rect) for rect in candidates.values()):
                raise ValueError(f"Preserved route {route.get('id', '')} overlaps a revision node; use reflow")
    nodes = _entities(spec)
    for identifier in locks:
        _check_content(nodes[identifier], candidates[identifier], spec, theme)
    if spec["kind"] == "diagram.system-landscape" and (spec.get("title") or spec.get("caption")):
        margin = float(spec.get("layout", {}).get("margin", 24))
        font = theme.get("svg_font_family", theme["font_family"])
        needed = label_height(spec.get("title", ""), spec.get("caption", ""), width - margin * 2 - 16,
                              font, theme["font_size"] + 6, max(8, theme["font_size"] - 1)) + 26
        if needed > min(rect["y"] for rect in candidates.values()) + _EPSILON:
            raise ValueError("Revision title overflow would overlap locked zones; use reflow")
    elif spec.get("title"):
        from .diagrams import _generic_title_height

        if _generic_title_height(spec, width, theme) + 36 > min(rect["y"] for rect in candidates.values()) + _EPSILON:
            raise ValueError("Revision title overflow would overlap locked content; use reflow")
    for identifier in locks:
        box = boxes[identifier]
        if isinstance(box, dict):
            box.update(candidates[identifier])
        else:
            for key, value in candidates[identifier].items():
                setattr(box, key, value)
    return width, height


def _check_content(
    node: dict[str, Any], rect: dict[str, float], spec: dict[str, Any], theme: dict[str, Any],
) -> None:
    if spec["kind"] == "diagram.system-landscape":
        from .diagrams import _landscape_zone_height

        needed = _landscape_zone_height(node, rect["width"], theme)
        available = rect["height"]
    else:
        shape = node.get("shape", "rounded")
        shaped = shape in {"diamond", "ellipse", "operation"}
        icon = bool(node.get("icon")) and shape not in {"database", "tensor", "diamond", "operation", "ellipse", "document"}
        fraction = .7 if shape in {"ellipse", "operation"} and spec.get("style", {}).get("visual_grammar") == "semantic" else .5
        text_width = rect["width"] * fraction - 14 if shaped else rect["width"] - (59 if icon else 28)
        available = rect["height"] * fraction - 20 if shaped else rect["height"] - (38 if shape in {"database", "document"} else 24)
        font = theme.get("svg_font_family", theme.get("font_family", DEFAULT_FONT))
        size = theme.get("font_size", 12)
        needed = label_height(str(node.get("label", node["id"])), str(node.get("subtitle", node.get("technology", ""))),
                              text_width, font, size, max(8, size - 2))
    if needed > available + 0.1:
        raise ValueError(f"Locked content overflow for {node['id']}: needs {needed:.1f}px, has {available:.1f}px; unlock or use reflow")
