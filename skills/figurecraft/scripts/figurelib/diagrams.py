from __future__ import annotations

import html
import hashlib
import math
import textwrap
import unicodedata
from dataclasses import dataclass
from copy import deepcopy
from pathlib import Path
from typing import Any

from .cnn import render_cnn_svg
from .drawio import export_drawio
from .framework import render_framework_svg
from .framework_matrix import render_framework_matrix_svg
from .icons import render_icon
from .media import apply_svg_media, prepare_media, raster_dpi
from .graph_layout import assign_layers, edge_ports, order_layers
from .provenance import append_provenance, provenance_description
from .revision import apply_placement
from .typography import DEFAULT_FONT, label_height, label_svg, measure_text, readable_color, wrap_text
from .routing import Geometry, label_leader, path_data, place_label, route_orthogonal, segment_intersects_rect


@dataclass
class Box:
    node_id: str
    label: str
    subtitle: str | None
    x: float
    y: float
    width: float
    height: float
    shape: str
    layer: int
    group: str | None
    lane: str | None
    fill: str | None
    accent: str | None
    role: str
    icon: str | None
    step: str | None

    @property
    def cx(self) -> float:
        return self.x + self.width / 2

    @property
    def cy(self) -> float:
        return self.y + self.height / 2


def render_diagram(
    spec: dict[str, Any],
    output_dir: Path,
    theme: dict[str, Any],
) -> tuple[list[Path], dict[str, Any], list[dict[str, Any]]]:
    spec, theme = prepare_media(spec, theme)
    spec, theme = _semantic_style(spec, theme)
    if spec.get("layout", {}).get("optimize") and (
        spec["kind"] in {"diagram.framework-matrix", "diagram.cnn-architecture"} or spec.get("framework_stages")
    ):
        raise ValueError("layout.optimize supports node diagrams and system landscapes, not specialized plates")
    if spec.get("layout", {}).get("placement") and (
        spec["kind"] in {"diagram.framework-matrix", "diagram.cnn-architecture"} or spec.get("framework_stages")
    ):
        raise ValueError("This specialized renderer does not support placement locks; use reflow")
    direction = spec.get("layout", {}).get("direction", "LR")
    if direction not in {"LR", "TB"}:
        raise ValueError("layout.direction must be LR or TB")
    geometry: list[dict[str, Any]] = []
    if spec["kind"] == "diagram.framework-matrix":
        svg, width, height, geometry = render_framework_matrix_svg(spec, theme)
        boxes = {}
        lane_geometry = []
    elif (
        spec["kind"] == "diagram.research-framework"
        and spec.get("framework_stages")
    ):
        svg, width, height, geometry = render_framework_svg(spec, theme)
        boxes = {}
        lane_geometry = []
    elif spec["kind"] == "diagram.cnn-architecture":
        svg, width, height, geometry = render_cnn_svg(spec, theme)
        boxes = {}
        lane_geometry = []
    elif spec["kind"] == "diagram.system-landscape":
        svg, width, height, geometry = _system_landscape_svg(spec, theme)
        boxes = {}
        lane_geometry = []
    elif spec["kind"] == "diagram.swimlane":
        boxes, width, height, lane_geometry = _layout_swimlane(spec, theme)
        height = _reserve_title(spec, boxes, lane_geometry, width, height, theme)
        width, height = apply_placement(spec, boxes, width, height)
        geometry = _route_geometry(spec, boxes, theme, width)
        width, height = _constrained_routing_canvas(spec, geometry, width, height)
        svg = _svg(spec, boxes, width, height, lane_geometry, theme, geometry)
    else:
        boxes, width, height = _layout_layered(spec, direction, theme)
        lane_geometry = []
        height = _reserve_title(spec, boxes, lane_geometry, width, height, theme)
        width, height = apply_placement(spec, boxes, width, height)
        geometry = _route_geometry(spec, boxes, theme, width)
        width, height = _constrained_routing_canvas(spec, geometry, width, height)
        svg = _svg(spec, boxes, width, height, lane_geometry, theme, geometry)
    content_height = height
    if spec.get("layout", {}).get("optimize"):
        key = "connections" if spec["kind"] == "diagram.system-landscape" else "edges"
        for edge, route in zip(spec.get(key, []), getattr(geometry, "edges", [])):
            edge.update(route.get("ports", {}))
    svg, footer_height = append_provenance(svg, spec, theme)
    if footer_height is not None:
        height = footer_height
    svg, media_metadata = apply_svg_media(svg, spec)
    svg_path = output_dir / "figure.svg"
    svg_path.write_text(svg, encoding="utf-8")
    primary_format = str(spec.get("output", {}).get("primary", "svg")).lower()
    requested = [primary_format]
    requested.extend(
        str(item).lower() for item in spec.get("output", {}).get("additional", [])
    )
    formats = list(dict.fromkeys(requested))
    unsupported = [
        item for item in formats if item not in {"svg", "png", "pdf", "drawio"}
    ]
    if unsupported:
        raise ValueError(f"Unsupported diagram output format: {unsupported[0]}")
    converted = {
        path.suffix.lstrip("."): path
        for path in _convert_svg(
            svg_path,
            [item for item in formats if item in {"png", "pdf"}],
            spec,
        )
    }
    editable = (
        export_drawio(
            spec,
            output_dir,
            theme,
            boxes,
            (width, height),
            geometry=geometry,
        )
        if "drawio" in formats
        else None
    )
    if editable and footer_height is not None:
        from .provenance import append_drawio_provenance
        append_drawio_provenance(editable, spec, theme, width, content_height, height - content_height)
    by_format = {"svg": svg_path, **converted}
    if editable:
        by_format["drawio"] = editable
    outputs = [by_format[item] for item in formats]
    if "svg" not in formats:
        outputs.append(svg_path)
    if not geometry:
        geometry = [
            {
                "id": box.node_id,
                "x": box.x,
                "y": box.y,
                "width": box.width,
                "height": box.height,
            }
            for box in boxes.values()
        ]
    return (
        outputs,
        {
            "renderer": "builtin-svg",
            "version": "1.0",
            "canvas": {"width": width, "height": height},
            "edges": getattr(geometry, "edges", []),
            "labels": getattr(geometry, "labels", []),
            "routing_nodes": getattr(geometry, "routing_nodes", list(geometry)),
            "semantic_counts": _semantic_counts(spec),
            "provenance": provenance_description(spec),
            "media": media_metadata,
            "layout_quality": _layout_quality(spec, geometry),
        },
        geometry,
    )


def _semantic_style(spec: dict[str, Any], theme: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    style = spec.get("style", {})
    semantic = style.get("visual_grammar") == "semantic"
    theme = {**theme, "card_accent": style.get("card_accent", "none" if semantic else "legacy"),
             "visual_grammar": style.get("visual_grammar", "legacy")}
    if not style.get("semantic_shapes") and not semantic:
        return spec, theme
    spec = deepcopy(spec)
    shapes = {"actor": "ellipse", "input": "pill", "outcome": "pill", "output": "pill",
              "data": "database", "storage": "database", "memory": "database",
              "decision": "diamond", "risk": "diamond", "method": "rounded", "tool": "rect"}
    if semantic:
        shapes.update({"process": "rounded", "agent": "rounded", "compute": "rounded",
                       "artifact": "document", "evidence": "document", "report": "document",
                       "operation": "operation"})
    roles = {
        "actor": 0, "input": 0, "data": 0,
        "method": 1, "process": 1, "agent": 1, "compute": 1, "tool": 1, "operation": 1,
        "decision": 2, "risk": 2,
        "storage": 3, "memory": 3,
        "outcome": 4, "output": 4, "artifact": 4, "evidence": 4, "report": 4,
    }
    for node in spec.get("nodes", []):
        if node.get("role") in shapes:
            node.setdefault("shape", shapes[node["role"]])
        if semantic:
            role = roles.get(node.get("role"))
            fills = theme.get("node_fills", [theme["node_fill"]])
            accents = theme.get("accents", [theme["node_stroke"]])
            node.setdefault("color", fills[role % len(fills)] if role is not None else theme["node_fill"])
            node.setdefault("accent", accents[role % len(accents)] if role is not None else theme["node_stroke"])
    return spec, theme


def _semantic_counts(spec: dict[str, Any]) -> dict[str, int]:
    kind = spec["kind"]
    if kind == "diagram.system-landscape":
        zones = spec["zones"]
        sections = [s for z in zones for s in z.get("sections", [])]
        return {"vertices": len(zones) + len(sections) + sum(len(s.get("items", [])) for s in sections),
                "edges": len(spec.get("connections", []))}
    if kind == "diagram.framework-matrix":
        tracks = spec["tracks"]
        cells = [c for t in tracks for c in t.get("cells", [])]
        return {"vertices": len(spec["phases"]) + len(tracks) + len(cells) + 2,
                "edges": sum(max(0, len(t.get("cells", [])) - 1) for t in tracks)
                + len(spec.get("cross_links", [])) + sum(bool(t.get("cells")) for t in tracks) + 1}
    if kind == "diagram.research-framework" and spec.get("framework_stages"):
        stages = spec["framework_stages"]
        return {"vertices": len(stages) + sum(len(s["items"]) for s in stages) + 1,
                "edges": len(stages) + bool(spec.get("feedback"))
                + sum(max(0, len(s["items"]) - 1) for s in stages if s.get("connect_items"))}
    if kind == "diagram.cnn-architecture":
        return {"vertices": len(spec["stages"]), "edges": len(spec["stages"]) - 1}
    return {"vertices": len(spec["nodes"]), "edges": len(spec.get("edges", []))}


def _system_landscape_svg(
    spec: dict[str, Any],
    theme: dict[str, Any],
) -> tuple[str, float, float, list[dict[str, Any]]]:
    zones = spec["zones"]
    layout = spec.get("layout", {})
    width = float(layout.get("width", 1600))
    margin = float(layout.get("margin", 24))
    gap = float(layout.get("gap", 24))
    column_gap = float(layout.get("column_gap", gap))
    row_gap = float(layout.get("row_gap", gap))
    available = width - margin * 2
    font = theme.get("svg_font_family", theme["font_family"])
    header_height = label_height(spec.get("title", ""), spec.get("caption", ""),
                                 width - margin * 2 - 16, font, theme["font_size"] + 6,
                                 max(8, theme["font_size"] - 1))
    start_y = max(72.0, header_height + 26) if spec.get("title") or spec.get("caption") else 28.0
    rows: dict[int, list[dict[str, Any]]] = {}
    for zone in zones:
        rows.setdefault(int(zone.get("row", 0)), []).append(zone)

    zone_boxes: dict[str, dict[str, Any]] = {}
    cursor_y = start_y
    for row in sorted(rows):
        row_zones = rows[row]
        provisional: list[tuple[dict[str, Any], float, float]] = []
        for zone in row_zones:
            column = int(zone.get("column", 0))
            span = int(zone.get("span", 12))
            x = margin + available * column / 12
            zone_width = available * span / 12
            if column > 0:
                x += column_gap / 2
                zone_width -= column_gap / 2
            if column + span < 12:
                zone_width -= column_gap / 2
            provisional.append(
                (zone, x, _landscape_zone_height(zone, zone_width, theme))
            )
        row_height = max((height for _, _, height in provisional), default=100.0)
        for zone, x, _ in provisional:
            column = int(zone.get("column", 0))
            span = int(zone.get("span", 12))
            zone_width = available * span / 12
            if column > 0:
                zone_width -= column_gap / 2
            if column + span < 12:
                zone_width -= column_gap / 2
            zone_boxes[zone["id"]] = {
                "id": zone["id"],
                "x": x,
                "y": cursor_y,
                "width": zone_width,
                "height": row_height,
            }
        cursor_y += row_height + row_gap
    height = cursor_y - row_gap + margin
    width, height = apply_placement(spec, zone_boxes, width, height)
    geometry = Geometry(zone_boxes.values())
    geometry.routing_nodes = list(geometry)
    obstacles = list(geometry)
    if spec.get("title") or spec.get("caption"):
        obstacles.append({"id": "_title", "x": 0, "y": 0, "width": width, "height": start_y - 10})
    connections = spec.get("connections", [])
    geometry.edges = _route_edges(spec, connections, zone_boxes, obstacles)
    for index, connection in enumerate(connections):
        points = geometry.edges[index]["points"]
        edge_id = geometry.edges[index]["id"]
        if connection.get("label") or connection.get("status"):
            pill_width, pill_height = _landscape_label_size(connection, theme)
            label_obstacles = obstacles + (_other_routes(geometry.edges, index) if layout.get("optimize") else [])
            rect = place_label(points, pill_width, pill_height, label_obstacles, geometry.labels)
            geometry.labels.append({"id": edge_id, "edge_index": index, **rect,
                                    "leader": label_leader(points, rect, geometry)})
    width, height = _constrained_routing_canvas(spec, geometry, width, height)
    font = theme.get("svg_font_family", theme["font_family"])
    edge_color = theme.get("edge", theme["foreground"])
    accent_markers = [
        f'<marker id="landscape-arrow-{index}" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{color}"/></marker>'
        for index, color in enumerate(theme.get("accents", []))
    ]
    description = spec.get("caption") or f"{spec['kind']} with {len(zones)} zones"
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}" role="img" aria-labelledby="figure-title figure-desc">',
        f'<title id="figure-title">{html.escape(spec.get("title", spec["kind"]))}</title>',
        f'<desc id="figure-desc">{html.escape(description)}</desc>',
        "<defs>",
        f'<marker id="arrow" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{edge_color}"/></marker>',
        *accent_markers,
        f'<filter id="shadow-zone" x="-12%" y="-12%" width="124%" height="130%"><feDropShadow dx="0" dy="3" stdDeviation="4" flood-color="{theme["foreground"]}" flood-opacity="{theme.get("zone_shadow_opacity", 0.06)}"/></filter>',
        f'<filter id="shadow-card" x="-12%" y="-14%" width="124%" height="132%"><feDropShadow dx="0" dy="1.5" stdDeviation="2" flood-color="{theme["foreground"]}" flood-opacity="{theme.get("card_shadow_opacity", 0.04)}"/></filter>',
        f'<linearGradient id="canvas-gradient" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="{theme.get("canvas_background", theme["background"])}"/><stop offset="100%" stop-color="{theme.get("canvas_background_end", theme.get("canvas_background", theme["background"]))}"/></linearGradient>',
        "</defs>",
        f'<rect x="0" y="0" width="{width:.0f}" height="{height:.0f}" fill="url(#canvas-gradient)"/>',
    ]
    if spec.get("title") and theme.get("card_accent") != "none":
        title_accent = theme.get("title_accent", theme.get("accents", ["#3569E8"])[0])
        parts.append(
            f'<rect x="{margin:.1f}" y="12" width="4" height="37" rx="2" fill="{title_accent}"/>'
        )
    if spec.get("title") or spec.get("caption"):
        parts.extend(label_svg(spec.get("title", ""), spec.get("caption", ""), margin + 16, 10,
                               width - margin * 2 - 16, header_height, font, theme["font_size"] + 6,
                               max(8, theme["font_size"] - 1), theme["foreground"], theme["muted"],
                               theme.get("canvas_background", theme["background"]), "start"))
    label_lookup = {label["edge_index"]: label for label in geometry.labels}
    connection_layers = [
        _landscape_connection_svg(
            zone_boxes[connection["from"]],
            zone_boxes[connection["to"]],
            connection,
            theme,
            font,
            geometry.edges[index]["points"],
            label_lookup.get(index),
            geometry.routing_nodes,
        )
        for index, connection in enumerate(spec.get("connections", []))
    ]
    for connection_parts in connection_layers:
        parts.append(connection_parts[0])
    for zone in zones:
        parts.extend(
            _landscape_zone_svg(zone, zone_boxes[zone["id"]], theme, font)
        )
    for connection_parts in connection_layers:
        parts.extend(connection_parts[1:])
    parts.append("</svg>")
    return "\n".join(parts) + "\n", width, height, geometry


def _landscape_header_layout(
    title: str, subtitle: str, width: float, font: str, size: float, subtitle_size: float,
) -> dict[str, Any]:
    title_width = measure_text(title, size, font, "bold")
    inline = title_width <= width and (not subtitle or title_width + 18 + measure_text(subtitle, subtitle_size, font, "bold") <= width)
    height = max(size, subtitle_size) * 1.4 if inline else label_height(title, subtitle, width, font, size, subtitle_size)
    return {"inline": inline, "title_width": title_width, "height": height}


def landscape_zone_layout(zone: dict[str, Any], width: float, theme: dict[str, Any]) -> dict[str, Any]:
    columns = max(1, int(zone.get("section_columns", 1)))
    sections = zone.get("sections", [])
    inner_width = width - 32
    section_width = (inner_width - 14 * (columns - 1)) / columns
    font = theme.get("svg_font_family", theme.get("font_family", DEFAULT_FONT))
    size = theme.get("font_size", 12)
    header = _landscape_header_layout(zone["title"], zone.get("subtitle", ""), width - 36, font, size + 3, size)
    header_height = max(44.0, header["height"] + 20)
    cursor = header_height
    positions = []
    for offset in range(0, len(sections), columns):
        row = sections[offset : offset + columns]
        row_height = max((_landscape_section_height(s, section_width, theme) for s in row), default=0.0)
        for column, section in enumerate(row):
            positions.append({"index": offset + column, "x": 16 + column * (section_width + 14),
                              "y": cursor, "width": section_width, "height": row_height})
        cursor += row_height + 14
    return {"height": cursor + 2, "header_height": header_height, "header": header, "sections": positions}


def landscape_section_layout(section: dict[str, Any], width: float, theme: dict[str, Any]) -> dict[str, Any]:
    columns = max(1, int(section.get("columns", 1)))
    items = section.get("items", [])
    font = theme.get("svg_font_family", theme.get("font_family", DEFAULT_FONT))
    size = theme.get("font_size", 12)
    title_left = 34 if section.get("icon") else 24
    header = _landscape_header_layout(section["title"], section.get("subtitle", ""), width - title_left - 12,
                                       font, size + 1, max(7, size - 2))
    header_height = max(34.0, header["height"] + 16)
    card_width = (width - 28 - 10 * (columns - 1)) / columns
    if card_width < 52:
        raise ValueError(f"Landscape section {section['title']!r} is too narrow; increase width or reduce columns")
    positions = []
    cursor = header_height
    for offset in range(0, len(items), columns):
        row = items[offset:offset + columns]
        card_height = max([54.0] + [
            label_height(item["label"], item.get("subtitle", ""), card_width - (50 if item.get("icon") else 24),
                         font, size, max(7, size - 2)) + 18 for item in row
        ])
        for column, item in enumerate(row):
            positions.append({"index": offset + column, "x": 14 + column * (card_width + 10),
                              "y": cursor, "width": card_width, "height": card_height})
        cursor += card_height + 10
    note_height = max(28.0, label_height(section["note"], "", width - 28, font, max(7, size - 2)) + 12) if section.get("note") else 0
    note_box = {"x": 14, "y": cursor, "width": width - 28, "height": note_height}
    return {"height": cursor + note_height + 6, "header_height": header_height, "header": header,
            "card_width": card_width, "items": positions, "note": note_box}


def _landscape_zone_height(zone: dict[str, Any], width: float, theme: dict[str, Any] | None = None) -> float:
    return landscape_zone_layout(zone, width, theme or {})["height"]


def _landscape_section_height(section: dict[str, Any], width: float, theme: dict[str, Any] | None = None) -> float:
    return landscape_section_layout(section, width, theme or {})["height"]


def _landscape_header_svg(title: str, subtitle: str, x: float, y: float, width: float,
                          geometry: dict[str, Any], font: str, size: float, subtitle_size: float,
                          foreground: str, muted: str, background: str) -> list[str]:
    height = geometry["height"]
    if not geometry["inline"]:
        return label_svg(title, subtitle, x, y, width, height, font, size, subtitle_size, foreground, muted, background, "start")
    title_width = min(width, geometry["title_width"] + 1)
    parts = label_svg(title, "", x, y, title_width, height, font, size, subtitle_size, foreground, muted, background, "start")
    if subtitle:
        left = title_width + 14
        parts.extend(label_svg(subtitle, "", x + left, y, width - left, height, font, subtitle_size, subtitle_size,
                               muted, muted, background, "start"))
    return parts


def _landscape_zone_svg(
    zone: dict[str, Any],
    box: dict[str, Any],
    theme: dict[str, Any],
    font: str,
) -> list[str]:
    x, y = box["x"], box["y"]
    width, height = box["width"], box["height"]
    zone_radius = float(theme.get("zone_radius", 20))
    zone_border = float(theme.get("zone_border_width", 1.6))
    zone_border_color = theme.get("zone_border", theme["foreground"])
    surface = theme.get("surface", theme["background"])
    text_shift = float(theme.get("text_optical_shift", 0))
    header_y = y + 24 + text_shift
    positions = landscape_zone_layout(zone, width, theme)
    result = [
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" rx="{zone_radius:.1f}" fill="{surface}" stroke="{zone_border_color}" stroke-width="{zone_border:.2f}" filter="url(#shadow-zone)"/>',
        f'<line x1="{x + 16:.1f}" y1="{y + positions["header_height"] - 2:.1f}" x2="{x + width - 16:.1f}" y2="{y + positions["header_height"] - 2:.1f}" stroke="{theme.get("zone_divider", theme["grid"])}" stroke-width="1"/>',
    ]
    result.extend(_landscape_header_svg(zone["title"], zone.get("subtitle", ""), x + 18, y + 10,
                                       width - 36, positions["header"], font, theme["font_size"] + 3,
                                       theme["font_size"], theme["foreground"], theme["muted"], surface))
    sections = zone.get("sections", [])
    for section_box in positions["sections"]:
        result.extend(_landscape_section_svg(sections[section_box["index"]], x + section_box["x"], y + section_box["y"],
                                             section_box["width"], section_box["height"], theme, font))
    return result


def _landscape_section_svg(
    section: dict[str, Any],
    x: float,
    y: float,
    width: float,
    height: float,
    theme: dict[str, Any],
    font: str,
) -> list[str]:
    tone_index = {
        "blue": 0,
        "green": 1,
        "orange": 2,
        "purple": 3,
        "rose": 4,
        "teal": 5,
    }.get(str(section.get("tone", "neutral")), 0)
    fills = theme.get("node_fills", [theme["group_fill"]])
    accents = theme.get("accents", [theme["group_stroke"]])
    fill = (
        theme["group_fill"]
        if section.get("tone", "neutral") == "neutral"
        else fills[tone_index % len(fills)]
    )
    accent = (
        theme["muted"]
        if section.get("tone", "neutral") == "neutral"
        else accents[tone_index % len(accents)]
    )
    section_radius = float(theme.get("section_radius", 7))
    section_border = float(theme.get("section_border_width", 1.0))
    text_shift = float(theme.get("text_optical_shift", 0))
    section_header_y = y + 19 + text_shift
    positions = landscape_section_layout(section, width, theme)
    result = [
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" rx="{section_radius:.1f}" fill="{fill}" fill-opacity="0.52" stroke="{accent}" stroke-width="{section_border:.2f}"/>',
    ]
    if section.get("icon"):
        result.append(
            render_icon(
                str(section["icon"]),
                x + 10,
                y + 10,
                17,
                accent,
            )
        )
        title_x = x + 34
    else:
        result.append(
            f'<circle cx="{x + 14:.1f}" cy="{section_header_y - text_shift:.1f}" r="3.2" fill="{accent}"/>'
        )
        title_x = x + 24
    result.extend(_landscape_header_svg(section["title"], section.get("subtitle", ""), title_x, y + 8,
                                       x + width - 12 - title_x, positions["header"], font, theme["font_size"] + 1,
                                       max(7, theme["font_size"] - 2), accent, theme["muted"],
                                       theme.get("surface", theme["background"])))
    items = section.get("items", [])
    card_radius = float(theme.get("card_radius", 7))
    card_border = float(theme.get("card_border_width", 1.1))
    text_shift = float(theme.get("text_optical_shift", 0))
    for item_box in positions["items"]:
        item = items[item_box["index"]]
        card_x, card_y = x + item_box["x"], y + item_box["y"]
        card_width, card_height = item_box["width"], item_box["height"]
        card_fill = (
            theme.get("neutral_surface", theme["background"])
            if section.get("tone") == "neutral"
            else fill
        )
        result.append(
            f'<rect x="{card_x:.1f}" y="{card_y:.1f}" width="{card_width:.1f}" height="{card_height:.1f}" rx="{card_radius:.1f}" fill="{card_fill}" stroke="{accent}" stroke-width="{card_border:.2f}" filter="url(#shadow-card)"/>'
        )
        if theme.get("card_accent", "legacy") == "legacy" or (
            theme.get("card_accent") == "role" and item.get("role") in {"risk", "outcome"}
        ):
            result.append(
                f'<rect x="{card_x + 1.5:.1f}" y="{card_y + 9:.1f}" width="3" height="{card_height - 18:.1f}" rx="1.5" fill="{accent}" opacity="0.72"/>'
            )
        has_subtitle = bool(item.get("subtitle"))
        has_icon = bool(item.get("icon"))
        label_y = (
            card_y
            + (20.5 if has_subtitle else card_height / 2)
            + text_shift
        )
        if has_icon:
            icon_size = min(18.0, card_height * 0.32)
            result.append(
                render_icon(
                    str(item["icon"]),
                    card_x + 13,
                    card_y + (card_height - icon_size) / 2,
                    icon_size,
                    accent,
                )
            )
            text_x = card_x + 38
            text_anchor = "start"
        else:
            text_x = card_x + card_width / 2
            text_anchor = "middle"
        left = 38 if has_icon else 12
        result.extend(label_svg(item["label"], item.get("subtitle", ""), card_x + left, card_y + 9,
                                card_width - left - 12, card_height - 18, font, max(8, theme["font_size"] - 1),
                                max(7, theme["font_size"] - 3), theme["foreground"], theme["muted"],
                                card_fill, text_anchor))
    if section.get("note"):
        note = positions["note"]
        note_y = y + note["y"]
        result.extend(
            [
                f'<rect x="{x + 14:.1f}" y="{note_y:.1f}" width="{width - 28:.1f}" height="{note["height"]:.1f}" rx="5" fill="{accent}" fill-opacity="0.10" stroke="none"/>',
            ]
        )
        result.extend(label_svg(section["note"], "", x + 14, note_y + 6, width - 28, note["height"] - 12,
                                font, max(7, theme["font_size"] - 2), 8, accent, theme["muted"],
                                theme.get("surface", theme["background"]), "start"))
    return result


def _landscape_connection_svg(
    source: dict[str, Any],
    target: dict[str, Any],
    connection: dict[str, Any],
    theme: dict[str, Any],
    font: str,
    points: list[tuple[float, float]] | None = None,
    label_box: dict[str, Any] | None = None,
    obstacles: list[dict[str, Any]] | None = None,
) -> list[str]:
    kind = str(connection.get("kind", "default"))
    kind_index = {
        "control": 0,
        "runtime": 1,
        "evidence": 2,
        "state": 3,
        "feedback": 4,
    }.get(kind)
    accents = theme.get("accents", [])
    edge_color = (
        str(connection.get("color"))
        if connection.get("color")
        else (
            accents[kind_index % len(accents)]
            if kind_index is not None and accents
            else theme.get("edge", theme["foreground"])
        )
    )
    marker_key = str(connection.get("id", connection["from"] + "--" + connection["to"])) + edge_color
    marker_id = "edge-arrow-" + hashlib.sha256(marker_key.encode("utf-8")).hexdigest()[:12]
    if points is None:
        points = route_orthogonal(
            source, target, [source, target],
            source_port=connection.get("source_port"), target_port=connection.get("target_port"),
            source_anchor=float(connection.get("from_anchor", .5)),
            target_anchor=float(connection.get("to_anchor", .5)),
        )
    path = path_data(points, radius=8 if connection.get("style") == "curved" else 0,
                     obstacles=obstacles if obstacles is not None else [source, target])
    dash = ' stroke-dasharray="6 5"' if connection.get("style") == "dashed" else ""
    connection_id = str(
        connection.get("id", f"{connection['from']}--{connection['to']}")
    )
    direction = str(connection.get("direction", "forward"))
    marker_start = (
        f' marker-start="url(#{marker_id})"'
        if direction == "bidirectional"
        else ""
    )
    marker_end = (
        f' marker-end="url(#{marker_id})"'
        if direction in {"forward", "bidirectional"}
        else ""
    )
    result = [
        f'<path data-edge-id="{html.escape(connection_id)}" d="{path}" fill="none" stroke="{edge_color}" stroke-width="{theme["line_width"]}" stroke-linecap="round" stroke-linejoin="round"{marker_start}{marker_end}{dash}/>'
    ]
    result.append(f'<defs><marker id="{marker_id}" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{edge_color}"/></marker></defs>')
    label = str(connection.get("label", "")).strip()
    status = str(connection.get("status", "")).strip()
    if label or status:
        status_width, label_width = _landscape_label_widths(connection, theme)
        pill_width, pill_height = _landscape_label_size(connection, theme)
        if label_box is None:
            label_box = place_label(points, pill_width, pill_height, [source, target], [])
        label_x = label_box["x"] + pill_width / 2
        label_y = label_box["y"] + pill_height / 2
        if label_box.get("leader"):
            result.append(
                f'<path d="{path_data(label_box["leader"])}" fill="none" stroke="{edge_color}" stroke-opacity="0.65" stroke-width="0.8" stroke-dasharray="3 3"/>'
            )
        text_shift = float(theme.get("text_optical_shift", 0))
        left = label_x - pill_width / 2
        result.append(
            f'<rect x="{left:.1f}" y="{label_box["y"]:.1f}" width="{pill_width:.1f}" height="{pill_height:.1f}" rx="10" fill="{theme.get("surface", theme["background"])}" stroke="{edge_color}" stroke-opacity="0.42" stroke-width="0.9"/>'
        )
        if status:
            direction_glyph = {
                "bidirectional": "↔",
                "forward": "→",
                "none": "•",
            }.get(direction, "→")
            glyph_x = left + 13
            status_x = left + 26
            result.extend(label_svg(direction_glyph, "", left + 5, label_box["y"] + 3, 17, pill_height - 6,
                                    font, max(8, theme["font_size"] - 2), 9, edge_color, edge_color,
                                    theme.get("surface", theme["background"])))
            result.extend(label_svg(status, "", status_x, label_box["y"] + 3, status_width, pill_height - 6,
                                    font, max(7, theme["font_size"] - 3), 9, edge_color, edge_color,
                                    theme.get("surface", theme["background"]), "start"))
        if label:
            if status:
                label_text_x = left + 36 + status_width
                anchor = "start"
            else:
                label_text_x = left + 10
                anchor = "middle"
            result.extend(label_svg(label, "", label_text_x, label_box["y"] + 3,
                                    label_width if status else pill_width - 20, pill_height - 6, font,
                                    max(7, theme["font_size"] - 2), 9, theme["muted"], theme["muted"],
                                    theme.get("surface", theme["background"]), anchor))
    return result


def _landscape_label_widths(connection: dict[str, Any], theme: dict[str, Any]) -> tuple[float, float]:
    status, label = str(connection.get("status", "")).strip(), str(connection.get("label", "")).strip()
    font = theme.get("svg_font_family", theme["font_family"])
    return (min(100, max(1, measure_text(status, max(7, theme["font_size"] - 3), font, "bold") + 1)),
            min(180, max(1, measure_text(label, max(7, theme["font_size"] - 2), font, "bold") + 1)))


def _landscape_label_size(connection: dict[str, Any], theme: dict[str, Any]) -> tuple[float, float]:
    status, label = str(connection.get("status", "")).strip(), str(connection.get("label", "")).strip()
    status_width, label_width = _landscape_label_widths(connection, theme)
    font = theme.get("svg_font_family", theme["font_family"])
    heights = [20.0]
    if status:
        heights.append(label_height(status, "", status_width, font, max(7, theme["font_size"] - 3)) + 6)
    if label:
        heights.append(label_height(label, "", label_width, font, max(7, theme["font_size"] - 2)) + 6)
    width = (26 + status_width if status else 0) + (10 + label_width if label else 0) + 10
    return max(52, width), max(heights)


def _layout_layered(
    spec: dict[str, Any], direction: str, theme: dict[str, Any] | None = None,
) -> tuple[dict[str, Box], float, float]:
    nodes = spec["nodes"]
    edges = spec.get("edges", [])
    optimize = spec.get("layout", {}).get("optimize", False)
    layers = assign_layers(nodes, edges) if optimize else _layers(nodes, edges)
    by_layer: dict[int, list[dict[str, Any]]] = {}
    for node in nodes:
        by_layer.setdefault(layers[node["id"]], []).append(node)
    if optimize:
        by_layer = order_layers(by_layer, edges)
    density = str(spec.get("layout", {}).get("density", "normal"))
    density_spacing = {
        "compact": (44.0, 20.0),
        "normal": (60.0, 30.0),
        "comfortable": (84.0, 44.0),
    }
    if density not in density_spacing:
        raise ValueError("layout.density must be compact, normal, or comfortable")
    primary_gap, cross_gap = density_spacing[density]
    layout = spec.get("layout", {})
    primary_gap = float(layout.get("column_gap" if direction == "LR" else "row_gap",
                                   layout.get("gap", primary_gap)))
    cross_gap = float(layout.get("row_gap" if direction == "LR" else "column_gap", cross_gap))
    if any(node.get("group") for node in nodes):
        primary_gap += 20.0
    margin = float(layout.get("margin", 104.0 if spec.get("title") else 56.0))
    max_layer = max(by_layer, default=0)
    boxes: dict[str, Box] = {}
    layer_sizes: dict[int, tuple[float, float]] = {}
    for layer, items in by_layer.items():
        item_boxes = [_node_size(item, theme) for item in items]
        if direction == "LR":
            primary_size = max((size[0] for size in item_boxes), default=150.0)
            cross_size = sum(size[1] for size in item_boxes)
        else:
            primary_size = max((size[1] for size in item_boxes), default=54.0)
            cross_size = sum(size[0] for size in item_boxes)
        cross_size += cross_gap * max(0, len(items) - 1)
        layer_sizes[layer] = (primary_size, cross_size)
    max_cross = max((cross for _, cross in layer_sizes.values()), default=100.0)
    primary_cursor = margin
    for layer in (sorted(by_layer) if optimize else range(max_layer + 1)):
        items = by_layer.get(layer, [])
        primary_size, cross_size = layer_sizes.get(layer, (150.0, 0.0))
        cross_cursor = margin + (max_cross - cross_size) / 2
        for node in items:
            node_width, node_height = _node_size(node, theme)
            if direction == "LR":
                x = primary_cursor + (primary_size - node_width) / 2
                y = cross_cursor
                cross_cursor += node_height + cross_gap
            else:
                x = cross_cursor
                y = primary_cursor + (primary_size - node_height) / 2
                cross_cursor += node_width + cross_gap
            boxes[node["id"]] = Box(
                node_id=node["id"],
                label=str(node.get("label", node["id"])),
                subtitle=_optional_text(
                    node.get("subtitle", node.get("technology"))
                ),
                x=x,
                y=y,
                width=node_width,
                height=node_height,
                shape=node.get("shape", "rounded"),
                layer=layers[node["id"]],
                group=node.get("group"),
                lane=node.get("lane"),
                fill=node.get("color"),
                accent=node.get("accent"),
                role=str(node.get("role", "default")),
                icon=_optional_text(node.get("icon")),
                step=_optional_text(node.get("step")),
            )
        primary_cursor += primary_size + primary_gap
    if direction == "LR":
        width = primary_cursor - primary_gap + margin
        height = max_cross + margin * 2
    else:
        width = max_cross + margin * 2
        height = primary_cursor - primary_gap + margin
    return boxes, max(width, 360), height if "margin" in layout else max(height, 220)


def _layout_swimlane(
    spec: dict[str, Any], theme: dict[str, Any] | None = None,
) -> tuple[dict[str, Box], float, float, list[dict[str, Any]]]:
    lanes = spec["lanes"]
    nodes = spec["nodes"]
    edges = spec.get("edges", [])
    layers = _layers(nodes, edges)
    cell_nodes: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for node in nodes:
        cell_nodes.setdefault((node["lane"], layers[node["id"]]), []).append(node)
    max_cell_height = max(
        (
            sum(_node_size(node, theme)[1] for node in items)
            + 8 * max(0, len(items) - 1)
            for items in cell_nodes.values()
        ),
        default=60.0,
    )
    lane_height = max(132.0, max_cell_height + 28)
    header_width, margin = 132.0, 32.0
    max_layer = max(layers.values(), default=0)
    column_widths = {
        layer: max((_node_size(node, theme)[0] for node in nodes if layers[node["id"]] == layer), default=132.0)
        for layer in range(max_layer + 1)
    }
    column_x: dict[int, float] = {}
    cursor_x = header_width + margin
    for layer, column_width in column_widths.items():
        column_x[layer] = cursor_x
        cursor_x += column_width + 44
    width = cursor_x - 44 + margin
    height = margin * 2 + len(lanes) * lane_height
    lane_index = {lane["id"]: index for index, lane in enumerate(lanes)}
    boxes: dict[str, Box] = {}
    lane_geometry: list[dict[str, Any]] = []
    for index, lane in enumerate(lanes):
        y = margin + index * lane_height
        lane_geometry.append(
            {"id": lane["id"], "label": lane.get("label", lane["id"]), "y": y, "height": lane_height}
        )
    for (lane, layer), items in cell_nodes.items():
        sizes = [_node_size(node, theme) for node in items]
        total_height = sum(size[1] for size in sizes) + 8 * max(0, len(items) - 1)
        cursor = margin + lane_index[lane] * lane_height + (lane_height - total_height) / 2
        for node, (node_width, node_height) in zip(items, sizes, strict=True):
            x = column_x[layer] + (column_widths[layer] - node_width) / 2
            boxes[node["id"]] = Box(
                node_id=node["id"],
                label=str(node.get("label", node["id"])),
                subtitle=_optional_text(
                    node.get("subtitle", node.get("technology"))
                ),
                x=x,
                y=cursor,
                width=node_width,
                height=node_height,
                shape=node.get("shape", "rounded"),
                layer=layers[node["id"]],
                group=node.get("group"),
                lane=lane,
                fill=node.get("color"),
                accent=node.get("accent"),
                role=str(node.get("role", "default")),
                icon=_optional_text(node.get("icon")),
                step=_optional_text(node.get("step")),
            )
            cursor += node_height + 8
    return boxes, max(width, 520), max(height, 260), lane_geometry


def _layers(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, int]:
    explicit = {
        node["id"]: int(node["layer"])
        for node in nodes
        if node.get("layer") is not None
    }
    ids = [node["id"] for node in nodes]
    predecessors: dict[str, set[str]] = {node_id: set() for node_id in ids}
    successors: dict[str, set[str]] = {node_id: set() for node_id in ids}
    for edge in edges:
        predecessors[edge["to"]].add(edge["from"])
        successors[edge["from"]].add(edge["to"])
    indegree = {node_id: len(predecessors[node_id]) for node_id in ids}
    queue = [node_id for node_id in ids if indegree[node_id] == 0]
    result = {node_id: explicit.get(node_id, 0) for node_id in ids}
    visited: set[str] = set()
    while queue:
        node_id = queue.pop(0)
        visited.add(node_id)
        if node_id not in explicit and predecessors[node_id]:
            result[node_id] = max(result[item] + 1 for item in predecessors[node_id])
        for successor in successors[node_id]:
            indegree[successor] -= 1
            if indegree[successor] == 0:
                queue.append(successor)
    cycle_layer = max(result.values(), default=0)
    for node_id in ids:
        if node_id not in visited and node_id not in explicit:
            cycle_layer += 1
            result[node_id] = cycle_layer
    return result


def _node_size(node: dict[str, Any], theme: dict[str, Any] | None = None) -> tuple[float, float]:
    theme = theme or {}
    font = theme.get("svg_font_family", theme.get("font_family", DEFAULT_FONT))
    size = float(theme.get("font_size", 12))
    label = str(node.get("label", node["id"]))
    subtitle = str(node.get("subtitle", node.get("technology", "")))
    shape = node.get("shape", "rounded")
    icon = bool(node.get("icon")) and shape not in {"database", "tensor", "diamond", "operation", "ellipse", "document"}
    inset = 59 if icon else 28
    natural_width = max(measure_text(line, size, font, "bold") for line in label.splitlines() or [""])
    if subtitle:
        natural_width = max(natural_width, max(measure_text(line, max(8, size - 2), font) for line in subtitle.splitlines()))
    width = max(min(264.0, max(132.0, natural_width + inset)), float(node.get("visual_width", 0)))
    shaped = shape in {"diamond", "ellipse", "operation"}
    if shaped:
        width = max(width, 180)
    fraction = .7 if shape in {"ellipse", "operation"} and theme.get("visual_grammar") == "semantic" else .5
    text_width = width * fraction - 14 if shaped else width - inset
    needed = label_height(label, subtitle, text_width, font, size, max(8, size - 2))
    height = max(60.0, (needed + 20) / fraction if shaped else needed + (40 if shape in {"database", "document"} else 24))
    height = max(height, float(node.get("visual_height", 0)))
    if shape == "operation":
        width = height = max(width, height)
    return width, height


def _optional_text(value: Any) -> str | None:
    return str(value) if value is not None and str(value).strip() else None


def _wrap(label: str) -> list[str]:
    lines: list[str] = []
    for paragraph in label.splitlines() or [label]:
        if _display_width(paragraph) <= 24:
            lines.append(paragraph)
        elif any(character.isspace() for character in paragraph):
            lines.extend(
                textwrap.wrap(paragraph, width=24, break_long_words=False) or [""]
            )
        else:
            current = ""
            current_width = 0
            for character in paragraph:
                character_width = _display_width(character)
                if current and current_width + character_width > 24:
                    lines.append(current)
                    current = ""
                    current_width = 0
                current += character
                current_width += character_width
            lines.append(current)
    return lines


def _display_width(value: str) -> int:
    return sum(
        2 if unicodedata.east_asian_width(character) in {"W", "F"} else 1
        for character in value
    )


def _svg(
    spec: dict[str, Any],
    boxes: dict[str, Box],
    width: float,
    height: float,
    lanes: list[dict[str, Any]],
    theme: dict[str, Any],
    geometry: Geometry | None = None,
) -> str:
    font = theme.get("svg_font_family", theme["font_family"])
    edge_color = theme.get("edge", theme["foreground"])
    description = spec.get("caption") or f"{spec['kind']} with {len(boxes)} nodes"
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}" role="img" aria-labelledby="figure-title figure-desc">',
        f'<title id="figure-title">{html.escape(spec.get("title", spec["kind"]))}</title>',
        f'<desc id="figure-desc">{html.escape(description)}</desc>',
        "<defs>",
        f'<marker id="arrow" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{edge_color}"/></marker>',
        f'<filter id="generic-card-shadow" x="-14%" y="-16%" width="128%" height="138%"><feDropShadow dx="0" dy="2" stdDeviation="2.8" flood-color="{theme["foreground"]}" flood-opacity="{theme.get("card_shadow_opacity", 0.06)}"/></filter>',
        f'<filter id="generic-group-shadow" x="-10%" y="-10%" width="120%" height="125%"><feDropShadow dx="0" dy="2.5" stdDeviation="3.5" flood-color="{theme["foreground"]}" flood-opacity="{theme.get("zone_shadow_opacity", 0.05)}"/></filter>',
        "</defs>",
        f'<rect x="0" y="0" width="{width:.0f}" height="{height:.0f}" fill="{theme.get("canvas_background", theme["background"])}"/>',
    ]
    for index, lane in enumerate(lanes):
        fill = theme["lane_even"] if index % 2 == 0 else theme["lane_odd"]
        parts.append(
            f'<rect x="24" y="{lane["y"]:.1f}" width="{width - 48:.1f}" height="{lane["height"]:.1f}" fill="{fill}" stroke="none"/>'
        )
        parts.append(
            f'<line x1="24" y1="{lane["y"] + lane["height"]:.1f}" x2="{width - 24:.1f}" y2="{lane["y"] + lane["height"]:.1f}" stroke="{theme["grid"]}" stroke-width="1"/>'
        )
        parts.append(
            f'<rect x="24" y="{lane["y"]:.1f}" width="126" height="{lane["height"]:.1f}" fill="{theme["group_fill"]}" stroke="none"/>'
        )
        parts.extend(label_svg(lane["label"], "", 36, lane["y"] + 12, 102, lane["height"] - 24,
                               font, theme["font_size"], 9, theme["foreground"], theme["muted"],
                               theme["group_fill"], "start"))
    parts.extend(_groups(boxes, theme))
    geometry = geometry if geometry is not None else _route_geometry(spec, boxes, theme)
    label_lookup = {label["edge_index"]: label for label in geometry.labels}
    leaders: list[str] = []
    labels: list[str] = []
    for edge_index, edge in enumerate(spec.get("edges", [])):
        path = path_data(geometry.edges[edge_index]["points"],
                         radius=8 if edge.get("style") == "curved" else 0,
                         obstacles=geometry.routing_nodes)
        edge_id = str(edge.get("id", f"{edge['from']}--{edge['to']}"))
        dash = ' stroke-dasharray="7 5"' if edge.get("style") == "dashed" else ""
        kind_index = {"control": 0, "runtime": 1, "evidence": 2, "state": 3, "feedback": 4}.get(edge.get("kind"))
        accents = theme.get("accents", [])
        color = edge.get("color") or (accents[kind_index % len(accents)] if kind_index is not None and accents else edge_color)
        marker_id = f"generic-edge-{edge_index}"
        parts.append(f'<defs><marker id="{marker_id}" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{color}"/></marker></defs>')
        direction = edge.get("direction", "forward")
        arrows = f' marker-end="url(#{marker_id})"' if direction in {"forward", "bidirectional"} else ""
        arrows += f' marker-start="url(#{marker_id})"' if direction == "bidirectional" else ""
        parts.append(
            f'<path data-edge-id="{html.escape(edge_id)}" d="{path}" fill="none" stroke="{color}" stroke-width="{theme["line_width"]}" stroke-linecap="round" stroke-linejoin="round"{arrows}{dash}/>'
        )
        edge_text = _edge_text(edge)
        if edge_text:
            label = edge_text
            label_box = label_lookup[edge_index]
            pill_width = label_box["width"]
            label_x = label_box["x"] + pill_width / 2
            label_y = label_box["y"] + label_box["height"] / 2
            if label_box.get("leader"):
                leaders.append(
                    f'<path d="{path_data(label_box["leader"])}" fill="none" stroke="{edge_color}" stroke-opacity="0.65" stroke-width="0.8" stroke-dasharray="3 3"/>'
                )
            labels.append(
                f'<rect x="{label_box["x"]:.1f}" y="{label_box["y"]:.1f}" width="{pill_width:.1f}" height="{label_box["height"]:.1f}" rx="10" fill="{theme["background"]}" stroke="{theme["grid"]}" stroke-width="0.8"/>'
            )
            labels.extend(label_svg(label, "", label_box["x"] + 9, label_box["y"] + 3,
                                   pill_width - 18, label_box["height"] - 6, font,
                                   max(8, theme["font_size"] - 1), 9, theme["muted"],
                                   theme["muted"], theme["background"]))
    parts.extend(leaders)
    parts.extend(labels)
    for box in boxes.values():
        parts.extend(_node_svg(box, theme))
    if spec.get("title"):
        title_accent = theme.get(
            "title_accent",
            theme.get("accents", [theme["node_stroke"]])[0],
        )
        if theme.get("card_accent") != "none":
            parts.append(
                f'<rect x="28" y="11" width="4" height="38" rx="2" fill="{title_accent}"/>'
            )
        title_height = _generic_title_height(spec, width, theme)
        parts.extend(label_svg(spec["title"], spec.get("caption", ""), 44, 11, width - 88, title_height,
                               font, theme["font_size"] + 4, max(8, theme["font_size"] - 1),
                               theme["foreground"], theme["muted"], theme["background"], "start"))
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _group_layout(boxes: dict[str, Box], theme: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Box]] = {}
    for box in boxes.values():
        if box.group:
            grouped.setdefault(box.group, []).append(box)
    font = theme.get("svg_font_family", theme["font_family"])
    font_size = max(9, theme["font_size"])
    groups = []
    for index, (name, members) in enumerate(grouped.items(), start=1):
        left = min(item.x for item in members) - 18
        right = max(item.x + item.width for item in members) + 18
        badge_font_size = max(8.5, theme["font_size"] - 4)
        badge_size = max(20, measure_text(f"{index:02d}", badge_font_size, font, "bold") + 8,
                         badge_font_size * 1.4)
        heading_x = left + 16 + badge_size
        text_width = right - heading_x - 12
        lines = wrap_text(name, text_width, font_size, font, "bold")
        text_height = len(lines) * font_size * 1.4
        header_height = max(30.0, text_height, badge_size + 10)
        top = min(item.y for item in members) - header_height - 16
        heading_y = top + 5 + (header_height - text_height) / 2
        headings = [
            {"id": f"_group-heading-{index}-{line_index}", "x": heading_x,
             "y": heading_y + line_index * font_size * 1.4,
             "width": measure_text(line, font_size, font, "bold"), "height": font_size * 1.4}
            for line_index, line in enumerate(lines)
        ]
        badge = {"id": f"_group-badge-{index}", "x": left + 8, "y": top + 11,
                 "width": badge_size, "height": badge_size}
        headings.append(badge)
        groups.append({"name": name, "members": members, "index": index, "left": left, "right": right,
                       "top": top, "bottom": max(item.y + item.height for item in members) + 20,
                       "header_height": header_height, "headings": headings, "badge": badge,
                       "badge_font_size": badge_font_size, "heading_x": heading_x})
    return groups


def _groups(boxes: dict[str, Box], theme: dict[str, Any]) -> list[str]:
    result: list[str] = []
    font = theme.get("svg_font_family", theme["font_family"])
    fills = theme.get("node_fills", [theme["group_fill"]])
    accents = theme.get("accents", [theme["group_stroke"]])
    for group in _group_layout(boxes, theme):
        name, members, group_index = group["name"], group["members"], group["index"]
        layer = min(item.layer for item in members)
        fill = fills[layer % len(fills)]
        accent = accents[layer % len(accents)]
        left, top, right, bottom = group["left"], group["top"], group["right"], group["bottom"]
        badge = group["badge"]
        radius = badge["width"] / 2
        badge_x, badge_y = badge["x"] + radius, badge["y"] + radius
        result.append(
            f'<rect x="{left:.1f}" y="{top:.1f}" width="{right-left:.1f}" height="{bottom-top:.1f}" rx="18" fill="{fill}" fill-opacity="0.20" stroke="{accent}" stroke-opacity="0.42" stroke-width="1.2" filter="url(#generic-group-shadow)"/>'
        )
        result.append(
            f'<circle cx="{badge_x:.1f}" cy="{badge_y:.1f}" r="{radius:.1f}" fill="{accent}"/>'
        )
        result.append(
            f'<text x="{badge_x:.1f}" y="{badge_y + 0.5:.1f}" dominant-baseline="middle" text-anchor="middle" fill="{readable_color("#FFFFFF", accent)}" font-family="{font}" font-size="{group["badge_font_size"]}" font-weight="700">{group_index:02d}</text>'
        )
        result.extend(label_svg(name, "", group["heading_x"], top + 5,
                                right - group["heading_x"] - 12, group["header_height"], font,
                                max(9, theme["font_size"]), 9, accent, theme["muted"],
                                theme["background"], "start"))
        result.append(
            f'<line x1="{left + 12:.1f}" y1="{top + group["header_height"] + 8:.1f}" x2="{right - 12:.1f}" y2="{top + group["header_height"] + 8:.1f}" stroke="{accent}" stroke-opacity="0.24" stroke-width="1"/>'
        )
    return result


def _node_svg(box: Box, theme: dict[str, Any]) -> list[str]:
    fills = theme.get("node_fills", [theme["node_fill"]])
    accents = theme.get("accents", [theme["node_stroke"]])
    fill = box.fill or fills[box.layer % len(fills)]
    accent = box.accent or accents[box.layer % len(accents)]
    font = theme.get("svg_font_family", theme["font_family"])
    attrs = (
        f'data-node-id="{html.escape(box.node_id)}" fill="{fill}" '
        f'stroke="{accent}" stroke-width="1.25" filter="url(#generic-card-shadow)"'
    )
    if box.shape == "ellipse":
        shapes = [
            f'<ellipse cx="{box.cx:.1f}" cy="{box.cy:.1f}" rx="{box.width/2:.1f}" ry="{box.height/2:.1f}" {attrs}/>'
        ]
    elif box.shape == "diamond":
        points = f"{box.cx:.1f},{box.y:.1f} {box.x+box.width:.1f},{box.cy:.1f} {box.cx:.1f},{box.y+box.height:.1f} {box.x:.1f},{box.cy:.1f}"
        shapes = [f'<polygon points="{points}" {attrs}/>']
    elif box.shape == "database":
        shapes = [
            f'<path d="M {box.x:.1f} {box.y + 10:.1f} C {box.x:.1f} {box.y - 2:.1f}, {box.x + box.width:.1f} {box.y - 2:.1f}, {box.x + box.width:.1f} {box.y + 10:.1f} L {box.x + box.width:.1f} {box.y + box.height - 10:.1f} C {box.x + box.width:.1f} {box.y + box.height + 2:.1f}, {box.x:.1f} {box.y + box.height + 2:.1f}, {box.x:.1f} {box.y + box.height - 10:.1f} Z" {attrs}/>',
            f'<ellipse cx="{box.cx:.1f}" cy="{box.y + 10:.1f}" rx="{box.width / 2:.1f}" ry="10" fill="{fill}" stroke="{accent}" stroke-width="1.25"/>',
        ]
    elif box.shape == "document":
        fold = 16
        right, bottom = box.x + box.width, box.y + box.height
        shapes = [
            f'<path d="M {box.x:.1f} {box.y:.1f} H {right-fold:.1f} L {right:.1f} {box.y+fold:.1f} V {bottom:.1f} H {box.x:.1f} Z" {attrs}/>',
            f'<path d="M {right-fold:.1f} {box.y:.1f} V {box.y+fold:.1f} H {right:.1f}" fill="none" stroke="{accent}" stroke-width="1.25"/>',
        ]
    elif box.shape == "tensor":
        shapes = [
            f'<rect x="{box.x + offset:.1f}" y="{box.y - offset:.1f}" width="{box.width - 12:.1f}" height="{box.height:.1f}" rx="8" fill="{fill}" stroke="{accent}" stroke-width="1.1" opacity="{opacity}" filter="url(#generic-card-shadow)"/>'
            for offset, opacity in ((0, "0.50"), (6, "0.72"), (12, "1"))
        ]
    elif box.shape == "operation":
        radius = min(box.width, box.height) / 2
        shapes = [
            f'<circle cx="{box.cx:.1f}" cy="{box.cy:.1f}" r="{radius:.1f}" fill="{fill}" stroke="{accent}" stroke-width="1.6" data-node-id="{html.escape(box.node_id)}"/>'
        ]
    else:
        radius = box.height / 2 if box.shape == "pill" else (12 if box.shape == "rounded" else 4)
        shapes = [
            f'<rect x="{box.x:.1f}" y="{box.y:.1f}" width="{box.width:.1f}" height="{box.height:.1f}" rx="{radius:.1f}" {attrs}/>',
        ]
        if box.role == "outcome" and theme.get("visual_grammar") != "semantic":
            shapes.append(
                f'<rect x="{box.x + 4:.1f}" y="{box.y + 4:.1f}" width="{box.width - 8:.1f}" height="{box.height - 8:.1f}" rx="{max(4, radius - 4):.1f}" fill="none" stroke="{accent}" stroke-opacity="0.35" stroke-width="1"/>'
            )
    result = shapes
    icon_enabled = (
        box.icon is not None
        and box.shape not in {"database", "tensor", "diamond", "operation", "ellipse", "document"}
    )
    if icon_enabled:
        icon_size = 20.0
        result.append(
            render_icon(
                box.icon or "diagram",
                box.x + 14,
                box.cy - icon_size / 2,
                icon_size,
                accent,
            )
        )
        text_x = box.x + 45
        text_anchor = "start"
    else:
        text_x = box.cx
        text_anchor = "middle"
    if box.step:
        result.extend(
            [
                f'<circle cx="{box.x + 12:.1f}" cy="{box.y - 7:.1f}" r="11" fill="{theme["background"]}" stroke="{accent}" stroke-width="1.2"/>',
                f'<text x="{box.x + 12:.1f}" y="{box.y - 6.5:.1f}" dominant-baseline="middle" text-anchor="middle" fill="{accent}" font-family="{font}" font-size="8.5" font-weight="700">{html.escape(box.step)}</text>',
            ]
        )
    shaped = box.shape in {"diamond", "ellipse", "operation"}
    fraction = .7 if box.shape in {"ellipse", "operation"} and theme.get("visual_grammar") == "semantic" else .5
    left = box.width * (1 - fraction) / 2 + 7 if shaped else (45 if icon_enabled else 14)
    top = box.height * (1 - fraction) / 2 + 10 if shaped else (26 if box.shape in {"database", "document"} else 12)
    text_width = box.width * fraction - 14 if shaped else box.width - left - 14
    text_height = box.height * fraction - 20 if shaped else box.height - top - 12
    result.extend(label_svg(box.label, box.subtitle or "", box.x + left, box.y + top, text_width, text_height,
                            font, theme["font_size"], max(8, theme["font_size"] - 2),
                            theme["foreground"], theme["muted"], fill, text_anchor))
    return result


def _edge_route(
    source: Box,
    target: Box,
    edge: dict[str, Any],
    obstacles: list[dict[str, Any]] | None = None,
) -> tuple[str, float, float]:
    source_rect, target_rect = _box_rect(source), _box_rect(target)
    points = route_orthogonal(
        source_rect, target_rect, obstacles or [source_rect, target_rect],
        source_port=edge.get("source_port"), target_port=edge.get("target_port"),
        source_anchor=float(edge.get("from_anchor", .5)),
        target_anchor=float(edge.get("to_anchor", .5)),
    )
    label = place_label(points, 42, 20, obstacles or [source_rect, target_rect], [])
    return (path_data(points, radius=8 if edge.get("style") == "curved" else 0,
                      obstacles=obstacles if obstacles is not None else [source_rect, target_rect]),
            label["x"] + 21, label["y"] + 10)


def _box_rect(box: Box) -> dict[str, Any]:
    return {"id": box.node_id, "x": box.x, "y": box.y,
            "width": box.width, "height": box.height}


def _generic_title_height(spec: dict[str, Any], width: float, theme: dict[str, Any]) -> float:
    if not spec.get("title"):
        return 0.0
    font = theme.get("svg_font_family", theme["font_family"])
    return label_height(spec["title"], spec.get("caption", ""), width - 88, font,
                        theme["font_size"] + 4, max(8, theme["font_size"] - 1))


def _reserve_title(
    spec: dict[str, Any], boxes: dict[str, Box], lanes: list[dict[str, Any]],
    width: float, height: float, theme: dict[str, Any],
) -> float:
    groups = _group_layout(boxes, theme)
    top = min([box.y for box in boxes.values()] + [group["top"] for group in groups] +
              [lane["y"] for lane in lanes], default=104)
    required_top = _generic_title_height(spec, width, theme) + 36 if spec.get("title") else 10
    shift = max(0, required_top - top)
    for box in boxes.values():
        box.y += shift
    for lane in lanes:
        lane["y"] += shift
    return height + shift


def _route_geometry(
    spec: dict[str, Any], boxes: dict[str, Box], theme: dict[str, Any], canvas_width: float | None = None,
) -> Geometry:
    geometry = Geometry(_box_rect(box) for box in boxes.values())
    obstacles = list(geometry)
    for group in _group_layout(boxes, theme):
        obstacles.extend(group["headings"])
    if spec.get("title"):
        width = canvas_width or max((r["x"] + r["width"] for r in geometry), default=360) + 56
        obstacles.append({"id": "_title", "x": 0, "y": 0, "width": width,
                          "height": _generic_title_height(spec, width, theme) + 20})
    geometry.routing_nodes = obstacles
    geometry.edges = _route_edges(spec, spec.get("edges", []), boxes, obstacles)
    for index, edge in enumerate(spec.get("edges", [])):
        edge_id, points = geometry.edges[index]["id"], geometry.edges[index]["points"]
        text = _edge_text(edge)
        if text:
            font_size = max(8, theme["font_size"] - 1)
            font = theme.get("svg_font_family", theme["font_family"])
            width = min(260.0, max(42, measure_text(text, font_size, font, "bold") + 18))
            height = max(20, label_height(text, "", width - 18, font, font_size) + 6)
            label_obstacles = obstacles + (
                _other_routes(geometry.edges, index) if spec.get("layout", {}).get("optimize") else [])
            rect = place_label(points, width, height, label_obstacles, geometry.labels)
            geometry.labels.append({"id": edge_id, "edge_index": index, **rect,
                                    "leader": label_leader(points, rect, obstacles)})
    return geometry


def _other_routes(edges: list[dict[str, Any]], excluded: int) -> list[dict[str, Any]]:
    blockers = []
    for index, edge in enumerate(edges):
        if index == excluded:
            continue
        for segment, (a, b) in enumerate(zip(edge["points"], edge["points"][1:])):
            blockers.append({"id": f"_route-{index}-{segment}", "x": min(a[0], b[0]) - 2,
                             "y": min(a[1], b[1]) - 2, "width": abs(a[0] - b[0]) + 4,
                             "height": abs(a[1] - b[1]) + 4})
    return blockers


def _route_edges(
    spec: dict[str, Any], edges: list[dict[str, Any]], boxes: dict[str, Any],
    obstacles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    optimize = spec.get("layout", {}).get("optimize", False)
    resolved = edge_ports(edges, boxes, spec.get("layout", {}).get("direction", "LR")) if optimize else edges
    rectangles = {key: value if isinstance(value, dict) else _box_rect(value) for key, value in boxes.items()}
    previous = spec.get("layout", {}).get("placement", {}).get("routes", [])
    saved = {route["id"]: route for route in previous}
    routes = {}
    indices = sorted(range(len(edges)), key=lambda i: (
        edges[i]["from"], edges[i]["to"], str(edges[i].get("id", "")), i)) if optimize else range(len(edges))
    for index in indices:
        edge = dict(resolved[index])
        edge_id = str(edge.get("id", f"{edge['from']}--{edge['to']}"))
        source, target = rectangles[edge["from"]], rectangles[edge["to"]]
        saved_ports = saved.get(edge_id, {}).get("ports")
        if optimize and saved_ports is not None:
            if (not isinstance(saved_ports, dict)
                    or any(saved_ports.get(key) not in ("N", "S", "E", "W")
                           for key in ("source_port", "target_port"))
                    or any(not isinstance(saved_ports.get(key), (int, float))
                           or isinstance(saved_ports[key], bool)
                           or not 0 <= saved_ports[key] <= 1
                           for key in ("from_anchor", "to_anchor"))):
                raise ValueError(f"Preserved route {edge_id} has invalid ports; use reflow")
            edge.update({key: saved_ports[key] for key in ("source_port", "target_port", "from_anchor", "to_anchor")})
        elif optimize and edge_id in saved:
            for rect, point, port_key, anchor_key in (
                (source, saved[edge_id]["points"][0], "source_port", "from_anchor"),
                (target, saved[edge_id]["points"][-1], "target_port", "to_anchor"),
            ):
                candidates = {
                    "N": (rect["y"], point[1], (point[0] - rect["x"]) / rect["width"]),
                    "S": (rect["y"] + rect["height"], point[1], (point[0] - rect["x"]) / rect["width"]),
                    "W": (rect["x"], point[0], (point[1] - rect["y"]) / rect["height"]),
                    "E": (rect["x"] + rect["width"], point[0], (point[1] - rect["y"]) / rect["height"]),
                }
                for side in (edge[port_key], *candidates):
                    expected, actual, anchor = candidates[side]
                    if math.isclose(expected, actual, abs_tol=1e-6) and 0 <= anchor <= 1:
                        edge[port_key], edge[anchor_key] = side, anchor
                        break
        points = route_orthogonal(
            source, target, obstacles,
            source_port=edge.get("source_port"), target_port=edge.get("target_port"),
            source_anchor=float(edge.get("from_anchor", .5)), target_anchor=float(edge.get("to_anchor", .5)),
            occupied_paths=[route["points"] for route in routes.values()] if optimize else None,
        )
        points = _preserved_route(spec, edge, edge_id, points, obstacles)
        routes[index] = {"id": edge_id, "from": edge["from"], "to": edge["to"], "points": points}
        if optimize:
            routes[index]["ports"] = {key: edge[key] for key in ("source_port", "target_port", "from_anchor", "to_anchor")}
    return [routes[index] for index in range(len(edges))]


def _layout_quality(spec: dict[str, Any], geometry: list[dict[str, Any]]) -> dict[str, Any]:
    from .routing import path_congestion

    edges = getattr(geometry, "edges", [])
    return {"optimized": bool(spec.get("layout", {}).get("optimize")),
            "metric": "pairwise orthogonal routes; shared endpoints excluded",
            **path_congestion(edge["points"] for edge in edges)}


def _preserved_route(
    spec: dict[str, Any], edge: dict[str, Any], edge_id: str,
    calculated: list[tuple[float, float]], obstacles: list[dict[str, Any]],
) -> list[tuple[float, float]]:
    routes = spec.get("layout", {}).get("placement", {}).get("routes", [])
    matches = [route for route in routes if route.get("id") == edge_id]
    if not matches:
        return calculated
    if len(matches) != 1 or any(matches[0].get(key) != edge[key] for key in ("from", "to")):
        raise ValueError(f"Preserved route {edge_id} has inconsistent endpoints")
    points = [tuple(point) for point in matches[0]["points"]]
    for saved, expected in ((points[0], calculated[0]), (points[-1], calculated[-1])):
        if any(not math.isclose(a, b, abs_tol=1e-6) for a, b in zip(saved, expected)):
            raise ValueError(f"Preserved route {edge_id} no longer matches its ports; use reflow")
    for first, second in zip(points, points[1:]):
        if first[0] != second[0] and first[1] != second[1]:
            raise ValueError(f"Preserved route {edge_id} is not orthogonal")
        if any(segment_intersects_rect(first, second, node) for node in obstacles if not node.get("container")):
            raise ValueError(f"Preserved route {edge_id} crosses revised content; use reflow")
    return points


def _constrained_routing_canvas(
    spec: dict[str, Any], geometry: Geometry, width: float, height: float,
) -> tuple[float, float]:
    routed_width, routed_height = _routing_canvas(geometry, width, height)
    if spec.get("layout", {}).get("placement"):
        if routed_width > math.ceil(width) or routed_height > math.ceil(height):
            raise ValueError("Revision routing or label overflow exceeds the locked canvas; use reflow")
        return width, height
    return routed_width, routed_height


def _routing_canvas(geometry: Geometry, width: float, height: float) -> tuple[float, float]:
    for edge in geometry.edges:
        for x, y in edge["points"]:
            if x < 0 or y < 0:
                raise ValueError(f"Edge {edge['id']} routes outside the nonnegative canvas")
            width, height = max(width, x + 12), max(height, y + 12)
    for label in geometry.labels:
        for x, y in label.get("leader", []):
            if x < 0 or y < 0:
                raise ValueError(f"Label leader {label['id']} routes outside the nonnegative canvas")
            width, height = max(width, x + 12), max(height, y + 12)
        width = max(width, label["x"] + label["width"] + 12)
        height = max(height, label["y"] + label["height"] + 12)
    return math.ceil(width), math.ceil(height)


def _default_ports(dx: float, dy: float) -> tuple[str, str]:
    if abs(dx) >= abs(dy):
        return ("E", "W") if dx >= 0 else ("W", "E")
    return ("S", "N") if dy >= 0 else ("N", "S")


def _port_point(box: Box, port: str) -> tuple[float, float]:
    return {
        "N": (box.cx, box.y),
        "E": (box.x + box.width, box.cy),
        "S": (box.cx, box.y + box.height),
        "W": (box.x, box.cy),
    }[port]


def _edge_text(edge: dict[str, Any]) -> str:
    label = str(edge.get("label", "")).strip()
    technology = str(edge.get("technology", "")).strip()
    text = f"{label} · {technology}" if label and technology else label or technology
    status = str(edge.get("status", "")).strip()
    return f"{status} · {text}" if status and text else status or text


def _convert_svg(primary: Path, formats: list[str], spec: dict[str, Any]) -> list[Path]:
    if not formats:
        return []
    try:
        import cairosvg
    except ImportError as exc:
        raise RuntimeError(
            "Diagram PNG/PDF export requires the optional CairoSVG dependency"
        ) from exc
    except OSError as exc:
        raise RuntimeError(
            "CairoSVG could not load native Cairo. Install Cairo and configure its library path "
            "(on Apple Silicon Homebrew: DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib)."
        ) from exc
    outputs: list[Path] = []
    for extension in dict.fromkeys(formats):
        if extension not in {"png", "pdf"}:
            raise ValueError(f"Unsupported diagram output format: {extension}")
        path = primary.parent / f"figure.{extension}"
        if extension == "png":
            cairosvg.svg2png(
                url=str(primary),
                write_to=str(path),
                dpi=96,
                scale=float(raster_dpi(spec)) / 96,
            )
        else:
            cairosvg.svg2pdf(url=str(primary), write_to=str(path), dpi=96, scale=1)
        outputs.append(path)
    return outputs
