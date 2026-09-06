from __future__ import annotations

import html
import math
from typing import Any

from .icons import render_icon
from .routing import Geometry, label_leader, path_data, place_label, route_orthogonal, segment_intersects_rect
from .typography import label_height, label_svg, measure_text, readable_color


def matrix_layout(spec: dict[str, Any], theme: dict[str, Any]) -> dict[str, Any]:
    layout = spec.get("layout", {})
    phases, tracks = spec["phases"], spec["tracks"]
    margin = float(layout.get("margin", 48))
    label_width = max(160.0, float(layout.get("label_width", 190)))
    gutter = max(48.0, float(layout.get("convergence_gutter", 92)))
    width = max(float(layout.get("width", 1500)), 2 * margin + label_width + gutter + 180 * len(phases))
    grid_x = margin + label_width
    grid_width = width - grid_x - margin - gutter
    column_width = grid_width / len(phases)
    font = theme.get("svg_font_family", theme["font_family"])
    title_height = label_height(spec.get("title", "Complex research framework"), spec.get("caption", ""),
                                width - 2 * margin - 18, font, 20, 10.5)
    phase_y = max(float(layout.get("phase_y", 92)), title_height + 42)
    phase_height = max(float(layout.get("phase_height", 62)), max(
        label_height(p["title"], p.get("subtitle", ""), column_width - 74, font, 11.5, 8.5) + 22
        for p in phases
    ))
    grid_y = max(float(layout.get("grid_y", 174)), phase_y + phase_height + 20)
    phase_lookup = {p["id"]: i for i, p in enumerate(phases)}
    cells: dict[str, dict[str, Any]] = {}
    track_boxes = []
    cursor = grid_y
    for index, track in enumerate(tracks):
        card_height = max([76.0] + [
            label_height(c["label"], c.get("subtitle", ""), column_width - 28 - (58 if c.get("icon") else 28),
                         font, 10.5, 8.3) + 22 for c in track.get("cells", [])
        ])
        track_height = max(float(layout.get("track_height", 150)), card_height + 74,
                           label_height(track["title"], track.get("subtitle", ""), label_width - 48,
                                        font, 13, 8.8) + 86)
        track_boxes.append({"id": track["id"], "x": margin, "y": cursor,
                            "width": width - 2 * margin, "height": track_height - 12})
        for cell in track.get("cells", []):
            phase = phase_lookup[cell["phase"]]
            cells[cell["id"]] = {"x": grid_x + phase * column_width + 14, "y": cursor + 31,
                                  "width": column_width - 28, "height": track_height - 74,
                                  "track": index, "phase": phase}
        cursor += track_height
    integration = spec.get("integration", {})
    label_space = grid_width * 0.45 - 44 if integration.get("chips") else grid_width - 44
    integration_height = max(86.0, label_height(integration.get("label", "Evidence integration"),
        integration.get("subtitle", ""), label_space, font, 13, 8.8) + 30)
    chips = integration.get("chips", [])
    if chips:
        chip_columns = max(1, int((grid_width * 0.55 - 22) // 130))
        chip_width = (grid_width * 0.55 - 22) / chip_columns - 10
        chip_height = max(44.0, max(label_height(str(c), "", chip_width - 16, font, 9.2) + 16 for c in chips))
        integration_height = max(integration_height, math.ceil(len(chips) / chip_columns) * (chip_height + 10) + 20)
    outcome = spec.get("outcome", {})
    outcome_width = min(float(outcome.get("width", 430)), width - 2 * margin)
    outcome_height = max(72.0, label_height(outcome.get("label", "Research outcome"),
        outcome.get("subtitle", ""), outcome_width - (88 if outcome.get("icon") else 48), font, 12.5, 9.2) + 30)
    integration_box = {"id": "integration", "x": grid_x, "y": cursor + 50, "width": grid_width, "height": integration_height}
    outcome_box = {"id": "outcome", "x": (width - outcome_width) / 2,
                   "y": integration_box["y"] + integration_height + 58, "width": outcome_width, "height": outcome_height}
    chip_boxes = []
    if chips:
        for index, chip in enumerate(chips):
            row, column = divmod(index, chip_columns)
            chip_boxes.append({"id": f"integration-chip-{index}", "label": str(chip),
                               "x": grid_x + grid_width * 0.45 + column * (chip_width + 10),
                               "y": integration_box["y"] + 15 + row * (chip_height + 10),
                               "width": chip_width, "height": chip_height})
    return {"width": width, "height": max(float(layout.get("height", 0)), outcome_box["y"] + outcome_height + 54),
            "margin": margin, "label_width": label_width, "convergence_gutter": gutter,
            "grid_x": grid_x, "grid_y": grid_y, "grid_width": grid_width, "column_width": column_width,
            "phase_y": phase_y, "phase_height": phase_height, "tracks": track_boxes, "cells": cells,
            "integration": integration_box, "outcome": outcome_box, "chips": chip_boxes, "title_height": title_height}


def _matrix_routes(spec: dict[str, Any], positions: dict[str, Any], theme: dict[str, Any]) -> Geometry:
    geometry = Geometry([*positions["tracks"], positions["integration"], positions["outcome"]])
    font = theme.get("svg_font_family", theme["font_family"])
    cells = {node_id: {**box, "id": node_id} for node_id, box in positions["cells"].items()}
    geometry.routing_nodes = [*cells.values(), positions["integration"], positions["outcome"]]
    for index, phase in enumerate(spec["phases"]):
        geometry.routing_nodes.append({
            "id": f"matrix-phase-{index}", "x": positions["grid_x"] + index * positions["column_width"] + 8,
            "y": positions["phase_y"], "width": positions["column_width"] - 16, "height": positions["phase_height"],
        })
    for index, track in enumerate(positions["tracks"]):
        geometry.routing_nodes.append({
            "id": f"matrix-track-label-{index}", "x": positions["margin"] + 1, "y": track["y"] + 1,
            "width": positions["label_width"] - 14, "height": track["height"] - 2,
        })
    geometry.routing_nodes.append({
        "id": "matrix-title", "x": positions["margin"], "y": 18,
        "width": positions["width"] - 2 * positions["margin"], "height": positions["title_height"],
    })
    bus_x = positions["grid_x"] + positions["grid_width"] + positions["convergence_gutter"] / 2
    terminal_cells = []
    for index, track in enumerate(spec["tracks"]):
        ordered = sorted((cells[cell["id"]] for cell in track.get("cells", [])), key=lambda box: box["phase"])
        if ordered:
            terminal_cells.append((index, ordered[-1]))
    integration, outcome = positions["integration"], positions["outcome"]
    if terminal_cells:
        top_y = min(box["y"] + box["height"] / 2 for _, box in terminal_cells)
        caption_height = measure_text("Evidence bus", 8.5, font, "bold")
        geometry.routing_nodes.append({
            "id": "matrix-bus-label", "x": bus_x + 5, "y": (top_y + integration["y"] - 18) / 2 - caption_height / 2,
            "width": 13, "height": caption_height,
        })

    def add_route(edge_id: str, source: dict[str, Any], target: dict[str, Any], **ports: Any) -> list[tuple[float, float]]:
        points = route_orthogonal(source, target, geometry.routing_nodes, **ports)
        geometry.edges.append({"id": edge_id, "from": source["id"], "to": target["id"], "points": points})
        return points

    for track_index, track in enumerate(spec["tracks"]):
        ordered = sorted((cells[cell["id"]] for cell in track.get("cells", [])), key=lambda box: box["phase"])
        for index, (source, target) in enumerate(zip(ordered, ordered[1:])):
            add_route(f"matrix-progression-{track_index}-{index}", source, target, source_port="E", target_port="W")
    for index, link in enumerate(spec.get("cross_links", [])):
        if link["from"] not in cells or link["to"] not in cells:
            raise ValueError(f"Matrix cross-link has unknown endpoint: {link['from']} -> {link['to']}")
        source, target = cells[link["from"]], cells[link["to"]]
        if source["track"] != target["track"]:
            ports = ("S", "N") if source["track"] < target["track"] else ("N", "S")
        else:
            ports = (None, None)
        points = add_route(
            f"matrix-cross-{index}", source, target,
            source_port=link.get("source_port", ports[0]), target_port=link.get("target_port", ports[1]),
            source_anchor=float(link.get("from_anchor", .5)), target_anchor=float(link.get("to_anchor", .5)),
        )
        if link.get("label"):
            text = str(link["label"])
            text_width = max(40, min(182, measure_text(text, 8.5, font, "bold")))
            label_width = text_width + 18
            label_size = label_height(text, "", text_width, font, 8.5, 8.5) + 8
            label = place_label(points, label_width, label_size, geometry.routing_nodes, geometry.labels)
            geometry.labels.append({
                "id": f"matrix-cross-{index}", "edge_index": index, **label,
                "leader": label_leader(points, label, geometry.routing_nodes),
            })
    for index, box in terminal_cells:
        junction = {"id": f"matrix-bus-junction-{index}", "x": bus_x,
                    "y": box["y"] + box["height"] / 2, "width": 0, "height": 0}
        add_route(f"matrix-branch-{index}", box, junction, source_port="E", target_port="W")
    if terminal_cells:
        hub_x = integration["x"] + integration["width"] / 2
        points = [(bus_x, top_y), (bus_x, integration["y"] - 18),
                  (hub_x, integration["y"] - 18), (hub_x, integration["y"])]
        for box in geometry.routing_nodes:
            if box["id"] != integration["id"] and any(segment_intersects_rect(a, b, box) for a, b in zip(points, points[1:])):
                raise ValueError(f"Evidence bus crosses {box['id']}")
        geometry.edges.append({"id": "matrix-evidence-bus", "from": "matrix-bus", "to": integration["id"], "points": points})
    hub_x = integration["x"] + integration["width"] / 2
    target_anchor = (hub_x - outcome["x"]) / outcome["width"]
    add_route("matrix-outcome", integration, outcome, source_port="S", target_port="N",
              target_anchor=target_anchor if 0 < target_anchor < 1 else .5)
    return geometry


def render_framework_matrix_svg(
    spec: dict[str, Any],
    theme: dict[str, Any],
) -> tuple[str, float, float, list[dict[str, Any]]]:
    phases = spec["phases"]
    tracks = spec["tracks"]
    layout = spec.get("layout", {})
    positions = matrix_layout(spec, theme)
    geometry = _matrix_routes(spec, positions, theme)
    width, height = positions["width"], positions["height"]
    margin, label_width = positions["margin"], positions["label_width"]
    phase_y, phase_height = positions["phase_y"], positions["phase_height"]
    grid_y, grid_x = positions["grid_y"], positions["grid_x"]
    convergence_gutter = positions["convergence_gutter"]
    grid_width, column_width = positions["grid_width"], positions["column_width"]
    integration_y, integration_height = positions["integration"]["y"], positions["integration"]["height"]
    outcome_y, outcome_height = positions["outcome"]["y"], positions["outcome"]["height"]
    font = theme.get("svg_font_family", theme["font_family"])
    foreground = theme["foreground"]
    muted = theme["muted"]
    edge = theme.get("edge", foreground)
    surface = theme.get("surface", theme["background"])
    canvas = theme.get("canvas_background", theme["background"])
    fills = theme["node_fills"]
    accents = theme["accents"]
    outcome_start = theme.get("outcome_start", fills[5 % len(fills)])
    outcome_end = theme.get("outcome_end", surface)
    description = spec.get("caption") or (
        f"Complex research framework with {len(phases)} phases and {len(tracks)} tracks"
    )
    canvas_width, canvas_height = width, height
    for item in geometry.edges:
        for x, y in item["points"]:
            if x < 0 or y < 0:
                raise ValueError(f"Matrix relationship outside canvas: {item['id']}")
            canvas_width, canvas_height = max(canvas_width, x + 12), max(canvas_height, y + 12)
    for item in geometry.labels:
        canvas_width = max(canvas_width, item["x"] + item["width"] + 12)
        canvas_height = max(canvas_height, item["y"] + item["height"] + 12)
        for x, y in item.get("leader", []):
            canvas_width, canvas_height = max(canvas_width, x + 12), max(canvas_height, y + 12)
    canvas_width, canvas_height = math.ceil(canvas_width), math.ceil(canvas_height)
    routed = {item["id"]: item for item in geometry.edges}

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_width:.0f}" height="{canvas_height:.0f}" viewBox="0 0 {canvas_width:.0f} {canvas_height:.0f}" role="img" aria-labelledby="figure-title figure-desc">',
        f'<title id="figure-title">{html.escape(spec.get("title", "Complex research framework"))}</title>',
        f'<desc id="figure-desc">{html.escape(description)}</desc>',
        "<defs>",
        f'<marker id="matrix-arrow" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="{edge}"/></marker>',
        f'<filter id="matrix-panel-shadow" x="-12%" y="-15%" width="124%" height="135%"><feDropShadow dx="0" dy="2.5" stdDeviation="3.5" flood-color="{foreground}" flood-opacity="0.09"/></filter>',
        f'<filter id="matrix-card-shadow" x="-12%" y="-16%" width="124%" height="138%"><feDropShadow dx="0" dy="1.5" stdDeviation="2.2" flood-color="{foreground}" flood-opacity="0.07"/></filter>',
        f'<linearGradient id="matrix-canvas" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="{canvas}"/><stop offset="100%" stop-color="{theme["background"]}"/></linearGradient>',
        f'<linearGradient id="matrix-outcome" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="{outcome_start}"/><stop offset="100%" stop-color="{outcome_end}"/></linearGradient>',
        "</defs>",
        f'<rect x="0" y="0" width="{canvas_width:.0f}" height="{canvas_height:.0f}" fill="url(#matrix-canvas)"/>',
    ]
    parts.extend(_title_svg(spec, theme, font, margin, width))

    phase_lookup = {phase["id"]: index for index, phase in enumerate(phases)}
    for index, phase in enumerate(phases):
        x = grid_x + index * column_width + 8
        phase_fill = fills[index % len(fills)]
        phase_accent = accents[index % len(accents)]
        phase_solid = theme.get("phase_header_mode") == "solid"
        phase_background = phase_accent if phase_solid else phase_fill
        phase_opacity = 1 if phase_solid else 0.58
        phase_text = _contrast_text(phase_accent) if phase_solid else foreground
        phase_muted = phase_text if phase_solid else muted
        badge_fill = "#FFFFFF" if phase_solid else phase_accent
        badge_text = phase_accent if phase_solid else "#FFFFFF"
        parts.extend(
            [
                f'<rect x="{x:.1f}" y="{phase_y:.1f}" width="{column_width-16:.1f}" height="{phase_height:.1f}" rx="15" fill="{phase_background}" fill-opacity="{phase_opacity}" stroke="{phase_accent}" stroke-opacity="0.82" stroke-width="1.2" filter="url(#matrix-card-shadow)"/>',
                f'<circle cx="{x+22:.1f}" cy="{phase_y+phase_height/2:.1f}" r="13" fill="{badge_fill}" fill-opacity="0.94"/>',
                f'<text x="{x+22:.1f}" y="{phase_y+phase_height/2+0.5:.1f}" dominant-baseline="middle" text-anchor="middle" fill="{badge_text}" font-family="{font}" font-size="9" font-weight="700">{index+1:02d}</text>',
            ]
        )
        parts.extend(label_svg(phase["title"], phase.get("subtitle", ""), x + 44, phase_y + 10,
                               column_width - 74, phase_height - 20, font, 11.5, 8.5,
                               phase_text, phase_muted, phase_background, "start"))

    cell_boxes = positions["cells"]
    track_geometry = positions["tracks"]
    for track_index, track in enumerate(tracks):
        y = track_geometry[track_index]["y"]
        track_height = track_geometry[track_index]["height"] + 12
        accent = track.get("accent", accents[track_index % len(accents)])
        fill = track.get("fill", fills[track_index % len(fills)])
        track_opacity = float(theme.get("track_fill_opacity", 0.20))
        label_solid = theme.get("track_label_mode") == "solid"
        label_fill = accent if label_solid else fill
        label_text = _contrast_text(accent) if label_solid else accent
        label_muted = label_text if label_solid else muted
        parts.append(
            f'<rect x="{margin:.1f}" y="{y:.1f}" width="{width-2*margin:.1f}" height="{track_height-12:.1f}" rx="18" fill="{fill}" fill-opacity="{track_opacity:.2f}" stroke="{accent}" stroke-opacity="0.56" stroke-width="1.2"/>'
        )
        parts.append(
            f'<rect x="{margin+1:.1f}" y="{y+1:.1f}" width="{label_width-14:.1f}" height="{track_height-14:.1f}" rx="17" fill="{label_fill}" fill-opacity="{1 if label_solid else 0.46}" stroke="none"/>'
        )
        icon = str(track.get("icon", "workflow"))
        parts.append(
            render_icon(icon, margin + 22, y + 34, 28, label_text)
        )
        parts.extend(
            [
            ]
        )
        parts.extend(label_svg(track["title"], track.get("subtitle", ""), margin + 24, y + 70,
                               label_width - 48, track_height - 86, font, 13, 8.8,
                               label_text, label_muted, label_fill, "start"))

    for track_index, track in enumerate(tracks):
        ordered = sorted(
            (
                cell
                for cell in track.get("cells", [])
                if cell.get("id") in cell_boxes
            ),
            key=lambda cell: cell_boxes[cell["id"]]["phase"],
        )
        for index, (left_cell, right_cell) in enumerate(zip(ordered, ordered[1:])):
            route = routed[f"matrix-progression-{track_index}-{index}"]
            parts.append(
                f'<path data-edge-id="{route["id"]}" d="{path_data(route["points"])}" fill="none" stroke="{edge}" stroke-width="1.45" marker-end="url(#matrix-arrow)"/>'
            )

    labels = {item["edge_index"]: item for item in geometry.labels}
    for index, link in enumerate(spec.get("cross_links", [])):
        route = routed[f"matrix-cross-{index}"]
        link_color = accents[4 % len(accents)]
        dash = ' stroke-dasharray="6 5"' if link.get("style", "dashed") == "dashed" else ""
        parts.append(
            f'<path data-edge-id="{route["id"]}" d="{path_data(route["points"])}" fill="none" stroke="{link_color}" stroke-width="1.25" marker-end="url(#matrix-arrow)"{dash}/>'
        )
        if link.get("label"):
            label = labels[index]
            if label["leader"]:
                parts.append(f'<path d="{path_data(label["leader"])}" fill="none" stroke="{link_color}" stroke-width="0.8" stroke-dasharray="3 3"/>')
            parts.append(
                f'<rect x="{label["x"]:.2f}" y="{label["y"]:.2f}" width="{label["width"]:.2f}" height="{label["height"]:.2f}" rx="10" fill="{surface}" stroke="{theme["grid"]}" stroke-width="0.8"/>'
            )
            parts.extend(label_svg(str(link["label"]), "", label["x"] + 9, label["y"] + 4,
                                   label["width"] - 18, label["height"] - 8, font, 8.5, 8.5,
                                   link_color, link_color, surface))

    for track_index, track in enumerate(tracks):
        accent = track.get("accent", accents[track_index % len(accents)])
        fill = track.get("fill", fills[track_index % len(fills)])
        for cell in track.get("cells", []):
            box = cell_boxes.get(cell.get("id"))
            if box:
                parts.extend(
                    _cell_svg(
                        cell,
                        box,
                        accent,
                        fill,
                        surface,
                        theme,
                        font,
                    )
                )

    integration = spec.get("integration", {})
    integration_x = grid_x
    integration_width = grid_width
    bus_x = grid_x + grid_width + convergence_gutter / 2
    branch_points: list[tuple[float, str]] = []
    for track_index, track in enumerate(tracks):
        cells = [
            cell for cell in track.get("cells", []) if cell.get("id") in cell_boxes
        ]
        if not cells:
            continue
        last_cell = max(cells, key=lambda cell: cell_boxes[cell["id"]]["phase"])
        box = cell_boxes[last_cell["id"]]
        x1 = box["x"] + box["width"]
        y1 = box["y"] + box["height"] / 2
        branch_color = track.get(
            "accent",
            accents[track_index % len(accents)],
        )
        route = routed[f"matrix-branch-{track_index}"]
        parts.append(
            f'<path data-edge-id="{route["id"]}" d="{path_data(route["points"])}" fill="none" stroke="{branch_color}" stroke-width="1.4" stroke-linecap="round"/>'
        )
        parts.append(
            f'<circle cx="{bus_x:.1f}" cy="{y1:.1f}" r="4.2" fill="{surface}" stroke="{branch_color}" stroke-width="1.4"/>'
        )
        branch_points.append((y1, branch_color))
    if branch_points:
        top_y = min(point[0] for point in branch_points)
        hub_x = integration_x + integration_width / 2
        route = routed["matrix-evidence-bus"]
        parts.append(
            f'<path data-edge-id="{route["id"]}" d="{path_data(route["points"])}" fill="none" stroke="{edge}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" marker-end="url(#matrix-arrow)"/>'
        )
        parts.append(
            f'<text x="{bus_x+13:.1f}" y="{(top_y+integration_y-18)/2:.1f}" transform="rotate(-90 {bus_x+13:.1f} {(top_y+integration_y-18)/2:.1f})" text-anchor="middle" fill="{muted}" font-family="{font}" font-size="8.5" font-weight="700">Evidence bus</text>'
        )
    parts.extend(
        _integration_svg(
            integration,
            integration_x,
            integration_y,
            integration_width,
            integration_height,
            theme,
            font,
        )
    )
    outcome = spec.get("outcome", {})
    outcome_width = positions["outcome"]["width"]
    outcome_x = width / 2 - outcome_width / 2
    route = routed["matrix-outcome"]
    parts.append(
        f'<path data-edge-id="{route["id"]}" d="{path_data(route["points"])}" fill="none" stroke="{edge}" stroke-width="1.8" marker-end="url(#matrix-arrow)"/>'
    )
    parts.extend(
        _outcome_svg(
            outcome,
            outcome_x,
            outcome_y,
            outcome_width,
            outcome_height,
            theme,
            font,
        )
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n", canvas_width, canvas_height, geometry


def _title_svg(
    spec: dict[str, Any],
    theme: dict[str, Any],
    font: str,
    margin: float,
    width: float,
) -> list[str]:
    accent = theme.get("title_accent", theme["accents"][0])
    title, caption = spec.get("title", "Complex research framework"), spec.get("caption", "")
    area_width = width - 2 * margin - 18
    height = label_height(title, caption, area_width, font, 20, 10.5)
    result = [f'<rect x="{margin:.1f}" y="18" width="5" height="{height:.1f}" rx="2.5" fill="{accent}"/>']
    result.extend(label_svg(title, caption, margin + 18, 18, area_width, height,
                           font, 20, 10.5, theme["foreground"], theme["muted"], theme["background"], "start"))
    return result


def _cell_svg(
    cell: dict[str, Any],
    box: dict[str, float],
    accent: str,
    fill: str,
    surface: str,
    theme: dict[str, Any],
    font: str,
) -> list[str]:
    x, y, width, height = box["x"], box["y"], box["width"], box["height"]
    default_card_fill = (
        fill
        if theme.get("framework_card_mode") == "tinted"
        else surface
    )
    card_fill = cell.get("fill", default_card_fill)
    parts = [
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" rx="13" fill="{card_fill}" stroke="{accent}" stroke-width="1.25" filter="url(#matrix-card-shadow)"/>'
    ]
    if cell.get("icon"):
        icon_size = 22.0
        parts.append(
            f'<circle cx="{x+20:.1f}" cy="{y+height/2:.1f}" r="15" fill="{fill}" stroke="none"/>'
        )
        parts.append(
            render_icon(
                str(cell["icon"]),
                x + 9,
                y + height / 2 - 11,
                icon_size,
                accent,
            )
        )
        text_x = x + 44
        anchor = "start"
    else:
        text_x = x + width / 2
        anchor = "middle"
    left = 44 if cell.get("icon") else 14
    parts.extend(label_svg(cell["label"], cell.get("subtitle", ""), x + left, y + 11,
                           width - left - 14, height - 22, font, 10.5, 8.3,
                           theme["foreground"], theme["muted"], card_fill, anchor))
    return parts


def _integration_svg(
    integration: dict[str, Any],
    x: float,
    y: float,
    width: float,
    height: float,
    theme: dict[str, Any],
    font: str,
) -> list[str]:
    solid = theme.get("integration_mode") == "solid"
    accent = integration.get(
        "accent",
        theme.get(
            "integration_accent",
            theme["accents"][5 % len(theme["accents"])],
        ),
    )
    fill = integration.get(
        "fill",
        theme.get(
            "integration_fill",
            theme["node_fills"][5 % len(theme["node_fills"])],
        ),
    )
    title_color = theme.get("on_integration", "#FFFFFF") if solid else theme["foreground"]
    subtitle_color = theme.get("integration_muted", "#D5DAE1") if solid else theme["muted"]
    fill_opacity = 1 if solid else 0.58
    chips = integration.get("chips", [])
    parts = [
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" rx="18" fill="{fill}" fill-opacity="{fill_opacity}" stroke="{accent}" stroke-width="1.5" filter="url(#matrix-panel-shadow)"/>',
    ]
    label_width = width * 0.45 - 44 if chips else width - 44
    parts.extend(label_svg(integration.get("label", "Evidence integration"), integration.get("subtitle", ""),
                           x + 22, y + 15, label_width, height - 30, font, 13, 8.8,
                           title_color, subtitle_color, fill, "start"))
    if chips:
        columns = max(1, int((width * 0.55 - 22) // 130))
        chip_width = (width * 0.55 - 22) / columns - 10
        chip_height = max(44.0, max(label_height(str(c), "", chip_width - 16, font, 9.2) + 16 for c in chips))
        start_x = x + width * 0.45
        chip_fill = fill if solid else theme.get("surface", theme["background"])
        for index, chip in enumerate(chips):
            row, column = divmod(index, columns)
            chip_x = start_x + column * (chip_width + 10)
            chip_y = y + 15 + row * (chip_height + 10)
            parts.append(f'<rect x="{chip_x:.1f}" y="{chip_y:.1f}" width="{chip_width:.1f}" height="{chip_height:.1f}" rx="12" fill="{chip_fill}" stroke="{accent}" stroke-opacity="0.72" stroke-width="1"/>')
            parts.extend(label_svg(str(chip), "", chip_x + 8, chip_y + 8, chip_width - 16, chip_height - 16,
                                   font, 9.2, 8.8, title_color if solid else accent, subtitle_color, chip_fill))
    return parts


def _outcome_svg(
    outcome: dict[str, Any],
    x: float,
    y: float,
    width: float,
    height: float,
    theme: dict[str, Any],
    font: str,
) -> list[str]:
    solid = theme.get("outcome_mode") == "solid"
    accent = outcome.get("accent", theme["accents"][4 % len(theme["accents"])])
    outcome_text = theme.get("on_outcome", "#FFFFFF") if solid else theme["foreground"]
    outcome_muted = theme.get("on_outcome", "#FFFFFF") if solid else theme["muted"]
    parts = [
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" rx="{height/2:.1f}" fill="url(#matrix-outcome)" stroke="{accent}" stroke-width="2" filter="url(#matrix-panel-shadow)"/>',
        f'<rect x="{x+5:.1f}" y="{y+5:.1f}" width="{width-10:.1f}" height="{height-10:.1f}" rx="{height/2-5:.1f}" fill="none" stroke="{accent}" stroke-opacity="0.32" stroke-width="1"/>',
    ]
    if outcome.get("icon"):
        parts.append(
            render_icon(
                str(outcome["icon"]),
                x + 24,
                y + height / 2 - 13,
                26,
                outcome_text if solid else accent,
            )
        )
        text_x = x + 64
        anchor = "start"
    else:
        text_x = x + width / 2
        anchor = "middle"
    left = 64 if outcome.get("icon") else 24
    fill = theme.get("outcome_start", theme["node_fills"][5 % len(theme["node_fills"])])
    parts.extend(label_svg(outcome.get("label", "Research outcome"), outcome.get("subtitle", ""),
                           x + left, y + 15, width - left - 24, height - 30, font, 12.5, 9.2,
                           outcome_text, outcome_muted, fill, anchor))
    return parts


def _contrast_text(background: str) -> str:
    if not background.startswith("#") or len(background) != 7:
        return "#FFFFFF"
    red = int(background[1:3], 16) / 255
    green = int(background[3:5], 16) / 255
    blue = int(background[5:7], 16) / 255

    def linearize(channel: float) -> float:
        return (
            channel / 12.92
            if channel <= 0.04045
            else ((channel + 0.055) / 1.055) ** 2.4
        )

    luminance = (
        0.2126 * linearize(red)
        + 0.7152 * linearize(green)
        + 0.0722 * linearize(blue)
    )
    white_contrast = 1.05 / (luminance + 0.05)
    dark_luminance = 0.006
    dark_contrast = (luminance + 0.05) / (dark_luminance + 0.05)
    return "#FFFFFF" if white_contrast >= dark_contrast else "#101722"
