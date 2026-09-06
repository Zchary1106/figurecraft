from __future__ import annotations

import html
import math
from copy import deepcopy
from typing import Any

from .typography import label_height, label_svg, measure_text, readable_color


def cnn_layout_spec(spec: dict[str, Any], theme: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(spec)
    layout = result.setdefault("layout", {})
    font = theme.get("svg_font_family", theme["font_family"])
    margin = float(layout.get("margin", 48))
    slot_minimum = max(180.0, max(float(s.get("width", 126)) + 60 for s in result["stages"]))
    transition_width = max((_transition_width(s["transition"], font)
                            for s in result["stages"][1:] if s.get("transition")), default=0)
    if transition_width:
        slot_minimum = max(slot_minimum, max(float(s.get("width", 126))
                           for s in result["stages"]) + transition_width + 24)
    width = max(float(layout.get("width", 1680)), slot_minimum * len(result["stages"]) + 2 * margin)
    layout["width"] = width
    title_height = label_height(result.get("title", "CNN architecture"), result.get("caption", ""),
                                width - 2 * margin - 18, font, 21, 11)
    band_y = max(88.0, title_height + 42)
    slot = (width - 2 * margin) / len(result["stages"])
    stage_title_height = max(label_height(s["title"], "", slot - 24, font, 13) for s in result["stages"])
    layout["band_y"] = band_y
    layout["main_y"] = max(float(layout.get("main_y", 235)), band_y + stage_title_height + 110)
    band_bottom = layout["main_y"] + 110
    for stage in result["stages"]:
        if stage.get("type", "tensor") != "tensor":
            stage["width"] = max(126.0, float(stage.get("width", 126)))
            stage["height"] = max(float(stage.get("height", 66)), label_height(
                stage.get("label", stage["title"]), stage.get("subtitle", ""),
                stage["width"] - 24, font, 12, 9,
            ) + 24)
        annotation_height = label_height(stage.get("operation", ""), _dimension_label(stage),
                                         slot - 24, font, 10.5, 9.5)
        face_height = float(stage.get("height", 126))
        band_bottom = max(band_bottom, layout["main_y"] + face_height / 2 + 27 + annotation_height + 18)
    layout["band_bottom"] = band_bottom
    height = max(float(layout.get("height", 420)), band_bottom + 28)
    detail = result.get("block_detail")
    if detail:
        steps = detail.get("steps", [])
        inset_x = float(layout.get("inset_x", 180))
        inset_width = max(float(layout.get("inset_width", 1040)), len(steps) * 150 + 334)
        layout["inset_x"], layout["inset_width"] = inset_x, inset_width
        layout["inset_y"] = max(float(layout.get("inset_y", 430)), band_bottom + 42)
        geometry = block_layout(detail, inset_x, layout["inset_y"], inset_width, font)
        inset_height = max(float(layout.get("inset_height", 210)), geometry["required_height"])
        legend_width = max(320.0, width - inset_x - inset_width - 34 - margin)
        inset_height = max(inset_height, legend_layout(result, legend_width, font)["height"])
        layout["inset_height"] = inset_height
        layout["width"] = max(width, inset_x + inset_width + 34 + legend_width + margin)
        height = max(height, layout["inset_y"] + inset_height + 35)
    layout["height"] = height
    return result


def legend_layout(spec: dict[str, Any], width: float, font: str) -> dict[str, Any]:
    columns = [(20.0, width * 0.28 - 30), (width * 0.28, width * 0.28 - 10),
               (width * 0.56, width * 0.44 - 56), (width - 44, 24.0)]
    rows = []
    for row in spec.get("stage_table", []):
        row_height = max(27.0, max(label_height(str(row.get(key, "")), "", span, font, 9.2)
                                  for key, (_, span) in zip(("stage", "output", "block", "repeat"), columns)) + 12)
        rows.append(row_height)
    note = spec.get("note", "Tensor face area encodes spatial scale; prism depth encodes channels.")
    note_height = label_height(note, "", width - 40, font, 8.2)
    height = (76 + sum(rows) if rows else 190) + note_height + 26
    return {"height": height, "columns": columns, "rows": rows, "note": note, "note_height": note_height}


def block_layout(detail: dict[str, Any], x: float, y: float, width: float, font: str) -> dict[str, float]:
    count = len(detail.get("steps", []))
    start_x, end_x = x + 72, x + width - 122
    card_width = min(150.0, (end_x - start_x - 140) / max(1, count))
    card_height = max([70.0] + [label_height(step["label"], step.get("subtitle", ""),
        card_width - 20, font, 10.5, 8.8) + 24 for step in detail.get("steps", [])])
    header_height = label_height(detail.get("title", "Block detail"), detail.get("subtitle", "Representative repeated block"),
                                  width - 40, font, 14, 9.5)
    shortcut = detail.get("shortcut")
    shortcut_height = 34.0
    if isinstance(shortcut, dict):
        shortcut_height = max(34.0, label_height(shortcut.get("label", "Projection"),
            shortcut.get("subtitle", ""), 118, font, 9.2, 8) + 16)
    residual_y = max(y + 78, y + header_height + 24 + shortcut_height / 2)
    path_y = max(y + 142, residual_y + shortcut_height / 2 + card_height / 2 + 20)
    return {"start_x": start_x, "end_x": end_x, "card_width": card_width, "card_height": card_height,
            "header_height": header_height, "shortcut_height": shortcut_height, "residual_y": residual_y,
            "path_y": path_y, "required_height": path_y - y + card_height / 2 + 24}


def render_cnn_svg(
    spec: dict[str, Any],
    theme: dict[str, Any],
) -> tuple[str, float, float, list[dict[str, Any]]]:
    spec = cnn_layout_spec(spec, theme)
    stages = spec["stages"]
    layout = spec.get("layout", {})
    width = float(layout.get("width", 1680))
    height = float(layout.get("height", 700 if spec.get("block_detail") else 420))
    margin = float(layout.get("margin", 48))
    main_y = float(layout.get("main_y", 235))
    font = theme.get("svg_font_family", theme["font_family"])
    foreground = theme["foreground"]
    muted = theme["muted"]
    edge = theme.get("edge", foreground)
    background = theme["background"]
    canvas = theme.get("canvas_background", background)
    palette = theme.get("palette", ["#3569E8"])
    fills = theme.get("node_fills", ["#EEF4FF"])
    slot = (width - 2 * margin) / len(stages)
    geometry: list[dict[str, Any]] = []
    stage_layout: list[dict[str, Any]] = []

    for index, stage in enumerate(stages):
        center_x = margin + slot * (index + 0.5)
        stage_type = stage.get("type", "tensor")
        if stage_type == "tensor":
            spatial = _spatial(stage)
            channels = int(stage.get("channels", 1))
            face_height = _log_scale(spatial, 7, 224, 58, 126)
            face_width = max(68.0, face_height * 0.72)
            depth = _log_scale(channels, 3, 2048, 10, 30)
            total_width = face_width + depth * 0.72
            total_height = face_height + depth * 0.45
        else:
            face_width = float(stage.get("width", 126))
            face_height = float(stage.get("height", 66))
            depth = 0.0
            total_width = face_width
            total_height = face_height
        x = center_x - total_width / 2
        y = main_y - face_height / 2
        stage_layout.append(
            {
                "stage": stage,
                "index": index,
                "center_x": center_x,
                "x": x,
                "y": y,
                "face_width": face_width,
                "face_height": face_height,
                "depth": depth,
                "total_width": total_width,
                "total_height": total_height,
            }
        )
        geometry.append(
            {
                "id": stage["id"],
                "x": x,
                "y": y - depth * 0.45,
                "width": total_width,
                "height": total_height,
            }
        )

    description = spec.get("caption") or (
        f"CNN architecture with {len(stages)} stages and a residual block detail"
    )
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}" role="img" aria-labelledby="figure-title figure-desc">',
        f'<title id="figure-title">{html.escape(spec.get("title", "CNN architecture"))}</title>',
        f'<desc id="figure-desc">{html.escape(description)}</desc>',
        "<defs>",
        f'<marker id="cnn-arrow" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="{edge}"/></marker>',
        f'<filter id="cnn-shadow" x="-20%" y="-20%" width="145%" height="155%"><feDropShadow dx="0" dy="3" stdDeviation="4" flood-color="{foreground}" flood-opacity="0.11"/></filter>',
        f'<linearGradient id="cnn-canvas" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="{canvas}"/><stop offset="100%" stop-color="{background}"/></linearGradient>',
        "</defs>",
        f'<rect x="0" y="0" width="{width:.0f}" height="{height:.0f}" fill="url(#cnn-canvas)"/>',
    ]
    parts.extend(_title_svg(spec, theme, font))

    for item in stage_layout:
        index = item["index"]
        stage = item["stage"]
        color = stage.get("color", palette[index % len(palette)])
        fill = stage.get("fill", fills[index % len(fills)])
        band_x = margin + slot * index + 7
        parts.append(
            f'<rect x="{band_x:.1f}" y="{layout["band_y"]:.1f}" width="{slot - 14:.1f}" height="{layout["band_bottom"]-layout["band_y"]:.1f}" rx="16" fill="{fill}" opacity="0.20"/>'
        )
        heading_height = label_height(stage["title"], "", slot - 24, font, 13)
        parts.extend(label_svg(stage["title"], "", band_x + 5, layout["band_y"] + 10, slot - 24,
                               heading_height, font, 13, 9, foreground, muted, background))
        if stage.get("type", "tensor") == "tensor":
            parts.extend(_tensor_svg(item, fill, color, foreground, font))
        else:
            parts.extend(_operator_stage_svg(item, fill, color, foreground, muted, font))
        operation_y = main_y + item["face_height"] / 2 + 34
        dimension = _dimension_label(stage)
        if stage.get("operation") or dimension:
            parts.extend(label_svg(stage.get("operation", ""), dimension, band_x + 5, operation_y - 7,
                                   slot - 24, layout["band_bottom"] - operation_y, font, 10.5, 9.5,
                                   foreground, muted, background))
        repeat = int(stage.get("repeat", 1))
        if repeat > 1:
            badge_x = item["x"] + item["total_width"] - 16
            badge_y = item["y"] - item["depth"] * 0.45 - 11
            parts.extend(
                [
                    f'<rect x="{badge_x - 20:.1f}" y="{badge_y - 11:.1f}" width="40" height="22" rx="11" fill="{background}" stroke="{color}" stroke-width="1.1"/>',
                    f'<text x="{badge_x:.1f}" y="{badge_y + 0.5:.1f}" dominant-baseline="middle" text-anchor="middle" fill="{color}" font-family="{font}" font-size="10" font-weight="700">×{repeat}</text>',
                ]
            )

    for left, right in zip(stage_layout, stage_layout[1:]):
        x1 = left["x"] + left["total_width"]
        x2 = right["x"]
        parts.append(
            f'<path d="M {x1:.1f} {main_y:.1f} H {x2:.1f}" fill="none" stroke="{edge}" stroke-width="1.6" marker-end="url(#cnn-arrow)"/>'
        )
        transition = right["stage"].get("transition")
        if transition:
            label_x = (x1 + x2) / 2
            label_width = _transition_width(transition, font)
            parts.extend(
                [
                    f'<rect x="{label_x - label_width / 2:.1f}" y="{main_y - 31:.1f}" width="{label_width:.1f}" height="20" rx="10" fill="{background}" stroke="{theme["grid"]}" stroke-width="0.8"/>',
                ]
            )
            parts.extend(label_svg(str(transition), "", label_x - label_width / 2 + 8,
                                   main_y - 31, label_width - 16, 20, font, 9.5, 9,
                                   muted, muted, background))

    block_detail = spec.get("block_detail")
    if block_detail:
        inset_x = float(layout.get("inset_x", 180))
        inset_y = float(layout.get("inset_y", 430))
        inset_width = float(layout.get("inset_width", 1040))
        inset_height = float(layout.get("inset_height", 210))
        parts.extend(
            _block_detail_svg(
                block_detail,
                inset_x,
                inset_y,
                inset_width,
                inset_height,
                theme,
                font,
            )
        )
        geometry.append(
            {
                "id": "block-detail",
                "x": inset_x,
                "y": inset_y,
                "width": inset_width,
                "height": inset_height,
            }
        )
        legend_x = inset_x + inset_width + 34
        legend_width = width - legend_x - margin
        parts.extend(
            _legend_svg(
                spec,
                legend_x,
                inset_y,
                legend_width,
                inset_height,
                theme,
                font,
            )
        )
        geometry.append(
            {
                "id": "legend",
                "x": legend_x,
                "y": inset_y,
                "width": legend_width,
                "height": inset_height,
            }
        )

    parts.append("</svg>")
    return "\n".join(parts) + "\n", width, height, geometry


def _title_svg(spec: dict[str, Any], theme: dict[str, Any], font: str) -> list[str]:
    accent = theme.get("title_accent", theme.get("palette", ["#3569E8"])[0])
    title = spec.get("title", "CNN architecture")
    caption = spec.get("caption", "")
    margin = float(spec.get("layout", {}).get("margin", 48))
    width = float(spec.get("layout", {}).get("width", 1680)) - 2 * margin - 18
    height = label_height(title, caption, width, font, 21, 11)
    result = [f'<rect x="{margin:.1f}" y="18" width="5" height="{height:.1f}" rx="2.5" fill="{accent}"/>']
    result.extend(label_svg(title, caption, margin + 18, 18, width, height, font, 21, 11,
                           theme["foreground"], theme["muted"], theme["background"], "start"))
    return result


def _transition_width(text: str, font: str) -> float:
    return max(48.0, measure_text(str(text), 9.5, font, "bold") + 16)


def _tensor_svg(
    item: dict[str, Any],
    fill: str,
    color: str,
    foreground: str,
    font: str,
) -> list[str]:
    x = item["x"]
    y = item["y"]
    width = item["face_width"]
    height = item["face_height"]
    depth = item["depth"]
    dx = depth * 0.72
    dy = -depth * 0.45
    top = f"{x:.1f},{y:.1f} {x+dx:.1f},{y+dy:.1f} {x+width+dx:.1f},{y+dy:.1f} {x+width:.1f},{y:.1f}"
    side = f"{x+width:.1f},{y:.1f} {x+width+dx:.1f},{y+dy:.1f} {x+width+dx:.1f},{y+height+dy:.1f} {x+width:.1f},{y+height:.1f}"
    center_x = x + width / 2
    center_y = y + height / 2
    parts = [
        f'<g data-stage-id="{html.escape(str(item["stage"]["id"]))}" filter="url(#cnn-shadow)">',
        f'<polygon points="{top}" fill="{fill}" stroke="{color}" stroke-width="1.2" opacity="0.82"/>',
        f'<polygon points="{side}" fill="{color}" stroke="{color}" stroke-width="1.2" opacity="0.28"/>',
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" rx="5" fill="{fill}" stroke="{color}" stroke-width="1.5"/>',
        f'<path d="M {x+6:.1f} {y+8:.1f} H {x+width-6:.1f}" stroke="{color}" stroke-width="2.4" opacity="0.75"/>',
    ]
    parts.extend(label_svg(item["stage"].get("label", item["stage"]["title"]), "", x + 8, y + 14,
                           width - 16, height - 24, font, 11, 9, foreground, foreground, fill))
    parts.append("</g>")
    return parts


def _operator_stage_svg(
    item: dict[str, Any],
    fill: str,
    color: str,
    foreground: str,
    muted: str,
    font: str,
) -> list[str]:
    x = item["x"]
    y = item["y"]
    width = item["face_width"]
    height = item["face_height"]
    stage = item["stage"]
    parts = [
        f'<rect data-stage-id="{html.escape(str(stage["id"]))}" x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" rx="14" fill="{fill}" stroke="{color}" stroke-width="1.5" filter="url(#cnn-shadow)"/>',
        f'<rect x="{x:.1f}" y="{y:.1f}" width="5" height="{height:.1f}" rx="2.5" fill="{color}"/>',
    ]
    parts.extend(label_svg(stage.get("label", stage["title"]), stage.get("subtitle", ""), x + 12, y + 12,
                           width - 24, height - 24, font, 12, 9, foreground, muted, fill))
    return parts


def _block_detail_svg(
    detail: dict[str, Any],
    x: float,
    y: float,
    width: float,
    height: float,
    theme: dict[str, Any],
    font: str,
) -> list[str]:
    foreground = theme["foreground"]
    muted = theme["muted"]
    edge = theme.get("edge", foreground)
    background = theme.get("surface", theme["background"])
    palette = theme.get("palette", ["#3569E8", "#E99525", "#169B78"])
    positions = block_layout(detail, x, y, width, font)
    parts = [
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" rx="18" fill="{background}" stroke="{theme["group_stroke"]}" stroke-width="1.3" filter="url(#cnn-shadow)"/>',
    ]
    parts.extend(label_svg(detail.get("title", "Block detail"), detail.get("subtitle", "Representative repeated block"),
                           x + 20, y + 12, width - 40, positions["header_height"], font, 14, 9.5,
                           foreground, muted, background, "start"))
    steps = detail.get("steps", [])
    path_y = positions["path_y"]
    start_x = positions["start_x"]
    end_x = positions["end_x"]
    card_width, card_height = positions["card_width"], positions["card_height"]
    gap = ((end_x - start_x) - card_width * len(steps)) / max(1, len(steps) + 1)
    input_x = start_x
    parts.extend(
        [
            f'<circle cx="{input_x:.1f}" cy="{path_y:.1f}" r="18" fill="{theme["node_fills"][0]}" stroke="{palette[0]}" stroke-width="1.4"/>',
            f'<text x="{input_x:.1f}" y="{path_y+1:.1f}" dominant-baseline="middle" text-anchor="middle" fill="{readable_color(foreground, theme["node_fills"][0])}" font-family="{font}" font-size="11" font-weight="700">x</text>',
        ]
    )
    previous_x = input_x + 18
    card_centers: list[float] = []
    for index, step in enumerate(steps):
        card_x = start_x + gap * (index + 1) + card_width * index
        card_centers.append(card_x + card_width / 2)
        color = palette[index % len(palette)]
        fill = theme["node_fills"][index % len(theme["node_fills"])]
        parts.append(
            f'<path d="M {previous_x:.1f} {path_y:.1f} H {card_x:.1f}" fill="none" stroke="{edge}" stroke-width="1.5" marker-end="url(#cnn-arrow)"/>'
        )
        parts.extend(
            [
                f'<rect x="{card_x:.1f}" y="{path_y-card_height/2:.1f}" width="{card_width:.1f}" height="{card_height:.1f}" rx="10" fill="{fill}" stroke="{color}" stroke-width="1.3"/>',
            ]
        )
        parts.extend(label_svg(step["label"], step.get("subtitle", ""), card_x + 10,
                               path_y - card_height / 2 + 12, card_width - 20, card_height - 24,
                               font, 10.5, 8.8, foreground, muted, fill))
        previous_x = card_x + card_width
    merge_x = end_x
    if detail.get("residual", True):
        parts.extend(
            [
                f'<path d="M {previous_x:.1f} {path_y:.1f} H {merge_x-19:.1f}" fill="none" stroke="{edge}" stroke-width="1.5" marker-end="url(#cnn-arrow)"/>',
                f'<circle cx="{merge_x:.1f}" cy="{path_y:.1f}" r="19" fill="{background}" stroke="{palette[0]}" stroke-width="1.5"/>',
                f'<text x="{merge_x:.1f}" y="{path_y+1:.1f}" dominant-baseline="middle" text-anchor="middle" fill="{readable_color(foreground, background)}" data-text-background="{background}" font-family="{font}" font-size="18" font-weight="700">+</text>',
            ]
        )
        residual_y = positions["residual_y"]
        shortcut = detail.get("shortcut")
        if isinstance(shortcut, dict):
            shortcut_width = 138.0
            shortcut_height = positions["shortcut_height"]
            shortcut_x = (input_x + merge_x) / 2 - shortcut_width / 2
            shortcut_y = residual_y - shortcut_height / 2
            parts.extend(
                [
                    f'<path d="M {input_x:.1f} {path_y-18:.1f} V {residual_y:.1f} H {shortcut_x:.1f}" fill="none" stroke="{theme["muted"]}" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" marker-end="url(#cnn-arrow)"/>',
                    f'<rect x="{shortcut_x:.1f}" y="{shortcut_y:.1f}" width="{shortcut_width:.1f}" height="{shortcut_height:.1f}" rx="9" fill="{theme["node_fills"][4]}" stroke="{palette[4 % len(palette)]}" stroke-width="1.2"/>',
                    f'<path d="M {shortcut_x+shortcut_width:.1f} {residual_y:.1f} H {merge_x:.1f} V {path_y-19:.1f}" fill="none" stroke="{theme["muted"]}" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" marker-end="url(#cnn-arrow)"/>',
                ]
            )
            parts.extend(label_svg(shortcut.get("label", "Projection"), shortcut.get("subtitle", ""),
                                   shortcut_x + 10, shortcut_y + 8, shortcut_width - 20, shortcut_height - 16,
                                   font, 9.2, 8, foreground, muted, theme["node_fills"][4]))
        else:
            parts.extend(
                [
                    f'<path d="M {input_x:.1f} {path_y-18:.1f} V {residual_y:.1f} H {merge_x:.1f} V {path_y-19:.1f}" fill="none" stroke="{theme["muted"]}" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" marker-end="url(#cnn-arrow)"/>',
                    f'<text x="{(input_x+merge_x)/2:.1f}" y="{residual_y-8:.1f}" text-anchor="middle" fill="{muted}" font-family="{font}" font-size="9" font-weight="600">identity shortcut</text>',
                ]
            )
    output_x = merge_x + 70
    output_start = merge_x + 19 if detail.get("residual", True) else previous_x
    parts.extend(
        [
            f'<path d="M {output_start:.1f} {path_y:.1f} H {output_x-27:.1f}" fill="none" stroke="{edge}" stroke-width="1.5" marker-end="url(#cnn-arrow)"/>',
            f'<rect x="{output_x-27:.1f}" y="{path_y-18:.1f}" width="54" height="36" rx="18" fill="{theme["node_fills"][1]}" stroke="{palette[2 % len(palette)]}" stroke-width="1.3"/>',
        ]
    )
    parts.extend(label_svg(detail.get("output", "ReLU"), "", output_x - 23, path_y - 14, 46, 28,
                           font, 9.5, 9, foreground, muted, theme["node_fills"][1]))
    return parts


def _legend_svg(
    spec: dict[str, Any],
    x: float,
    y: float,
    width: float,
    height: float,
    theme: dict[str, Any],
    font: str,
) -> list[str]:
    foreground = theme["foreground"]
    muted = theme["muted"]
    surface = theme.get("surface", theme["background"])
    palette = theme["palette"]
    fills = theme["node_fills"]
    positions = legend_layout(spec, width, font)
    parts = [
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" rx="18" fill="{surface}" stroke="{theme["group_stroke"]}" stroke-width="1.3" filter="url(#cnn-shadow)"/>',
    ]
    stage_table = spec.get("stage_table")
    if stage_table:
        parts.append(
            f'<text x="{x+20:.1f}" y="{y+28:.1f}" fill="{foreground}" font-family="{font}" font-size="14" font-weight="700">Stage schedule</text>'
        )
        columns = [
            ("Stage", x + 20),
            ("Output", x + width * 0.28),
            ("Block", x + width * 0.56),
            ("×", x + width - 34),
        ]
        for label, column_x in columns:
            anchor = "middle" if label == "×" else "start"
            parts.append(
                f'<text x="{column_x:.1f}" y="{y+55:.1f}" text-anchor="{anchor}" fill="{muted}" font-family="{font}" font-size="8.8" font-weight="700">{label}</text>'
            )
        parts.append(
            f'<line x1="{x+18:.1f}" y1="{y+64:.1f}" x2="{x+width-18:.1f}" y2="{y+64:.1f}" stroke="{theme["grid"]}" stroke-width="1"/>'
        )
        row_y = y + 70
        for index, row in enumerate(stage_table):
            row_height = positions["rows"][index]
            for key, (offset, span) in zip(("stage", "output", "block", "repeat"), positions["columns"]):
                parts.extend(label_svg(str(row.get(key, "")), "", x + offset, row_y + 6,
                                       span, row_height - 12, font, 9.2, 8.8, foreground, muted, surface,
                                       "middle" if key == "repeat" else "start"))
            row_y += row_height
            if index < len(stage_table) - 1:
                parts.append(
                    f'<line x1="{x+18:.1f}" y1="{row_y:.1f}" x2="{x+width-18:.1f}" y2="{row_y:.1f}" stroke="{theme["grid"]}" stroke-width="0.7"/>'
                )
        parts.extend(label_svg(positions["note"], "", x + 20, y + height - positions["note_height"] - 16,
                               width - 40, positions["note_height"], font, 8.2, 8, muted, muted, surface, "start"))
        return parts
    parts.append(
        f'<text x="{x+20:.1f}" y="{y+28:.1f}" fill="{foreground}" font-family="{font}" font-size="14" font-weight="700">Visual grammar</text>'
    )
    entries = [
        ("Tensor / feature map", fills[0], palette[0], "box"),
        ("Downsample transition", fills[2], palette[2], "diamond"),
        ("Residual / identity", surface, muted, "line"),
        ("Repeated block", surface, palette[3 % len(palette)], "badge"),
    ]
    for index, (label, fill, color, kind) in enumerate(entries):
        cy = y + 62 + index * 35
        if kind == "box":
            parts.append(
                f'<rect x="{x+22:.1f}" y="{cy-10:.1f}" width="30" height="20" rx="4" fill="{fill}" stroke="{color}" stroke-width="1.2"/>'
            )
        elif kind == "diamond":
            parts.append(
                f'<polygon points="{x+37:.1f},{cy-11:.1f} {x+50:.1f},{cy:.1f} {x+37:.1f},{cy+11:.1f} {x+24:.1f},{cy:.1f}" fill="{fill}" stroke="{color}" stroke-width="1.2"/>'
            )
        elif kind == "line":
            parts.append(
                f'<path d="M {x+23:.1f} {cy:.1f} H {x+52:.1f}" stroke="{color}" stroke-width="1.4" fill="none" marker-end="url(#cnn-arrow)"/>'
            )
        else:
            parts.extend(
                [
                    f'<rect x="{x+22:.1f}" y="{cy-10:.1f}" width="32" height="20" rx="10" fill="{surface}" stroke="{color}" stroke-width="1.1"/>',
                    f'<text x="{x+38:.1f}" y="{cy+1:.1f}" dominant-baseline="middle" text-anchor="middle" fill="{color}" font-family="{font}" font-size="8.5" font-weight="700">×N</text>',
                ]
            )
        parts.append(
            f'<text x="{x+68:.1f}" y="{cy+1:.1f}" dominant-baseline="middle" fill="{foreground}" font-family="{font}" font-size="10">{html.escape(label)}</text>'
        )
    parts.extend(label_svg(positions["note"], "", x + 20, y + height - positions["note_height"] - 16,
                           width - 40, positions["note_height"], font, 8.2, 8, muted, muted, surface, "start"))
    return parts


def _spatial(stage: dict[str, Any]) -> int:
    value = stage.get("spatial", 1)
    if isinstance(value, list):
        return int(max(value))
    return int(value)


def _dimension_label(stage: dict[str, Any]) -> str:
    if stage.get("type", "tensor") != "tensor":
        return str(stage.get("dimension", ""))
    spatial = stage.get("spatial")
    channels = stage.get("channels")
    if isinstance(spatial, list) and len(spatial) == 2:
        return f"{spatial[0]}×{spatial[1]}×{channels}"
    if spatial is not None and channels is not None:
        return f"{spatial}×{spatial}×{channels}"
    return ""


def _log_scale(
    value: float,
    minimum: float,
    maximum: float,
    output_minimum: float,
    output_maximum: float,
) -> float:
    value = max(minimum, min(maximum, float(value)))
    low = math.log2(minimum)
    high = math.log2(maximum)
    ratio = (math.log2(value) - low) / (high - low)
    return output_minimum + ratio * (output_maximum - output_minimum)
