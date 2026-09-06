from __future__ import annotations

import html
import math
from typing import Any

from .icons import render_icon
from .typography import label_height, label_svg, readable_color


def framework_layout(spec: dict[str, Any], theme: dict[str, Any]) -> dict[str, Any]:
    layout = spec.get("layout", {})
    width = float(layout.get("width", 1160))
    margin = float(layout.get("margin", 58))
    panel_width = width - 2 * margin
    if panel_width < 260:
        raise ValueError("Research framework needs at least 260px of panel width")
    font = theme.get("svg_font_family", theme["font_family"])
    title_height = label_height(
        spec.get("title", "Research framework"), spec.get("caption", ""),
        panel_width - 18, font, 19, 10.5,
    )
    cursor = max(float(layout.get("start_y", 88)), title_height + 42)
    gap = float(layout.get("stage_gap", 54))
    stages: list[dict[str, Any]] = []
    for stage in spec["framework_stages"]:
        items = stage["items"]
        columns = min(len(items), max(1, int((panel_width - 22) // 178)))
        card_width = (panel_width - 40 - 18 * (columns - 1)) / columns
        header = max(59.0, label_height(
            stage["title"], stage.get("subtitle", ""), panel_width - 64, font, 13, 9.2,
        ) + 22)
        row_heights: list[float] = []
        for row in range(math.ceil(len(items) / columns)):
            heights = []
            for item in items[row * columns:(row + 1) * columns]:
                diamond = item.get("shape") == "diamond" or item.get("role", stage.get("role")) == "risk"
                inset = 0.5 if diamond else 1
                text_width = card_width * inset - (57 if item.get("icon") and not diamond else 28)
                needed = label_height(item["label"], item.get("subtitle", ""), text_width, font)
                heights.append((needed + 22) / inset + (14 if item.get("shape") == "database" else 0))
            row_heights.append(max(66.0, *heights))
        minimum = float(layout.get("stage_height", 142))
        stage_height = max(minimum, header + sum(row_heights) + 22 * (len(row_heights) - 1) + 17)
        if len(row_heights) == 1:
            row_heights[0] = stage_height - header - 17
        item_boxes = []
        row_y = cursor + header
        for index, item in enumerate(items):
            row, column = divmod(index, columns)
            if column == 0 and row:
                row_y += row_heights[row - 1] + 22
            item_boxes.append({
                "id": str(item.get("id", f"{stage['id']}-item-{index}")),
                "x": margin + 20 + column * (card_width + 18),
                "y": row_y, "width": card_width, "height": row_heights[row],
            })
        stages.append({
            "id": stage["id"], "x": margin, "y": cursor, "width": panel_width,
            "height": stage_height, "header_height": header, "items": item_boxes,
        })
        cursor += stage_height + gap
    outcome = spec.get("outcome", {})
    outcome_width = min(float(outcome.get("width", 390)), panel_width)
    outcome_height = max(78.0, label_height(
        outcome.get("label", "Research outcome"), outcome.get("subtitle", ""),
        outcome_width - (88 if outcome.get("icon") else 48), font, 12.5, 9.2,
    ) + 30)
    outcome_box = {
        "id": "outcome", "x": (width - outcome_width) / 2,
        "y": cursor - gap + 62, "width": outcome_width, "height": outcome_height,
    }
    height = max(float(layout.get("height", 0)), outcome_box["y"] + outcome_height + 70)
    return {"width": width, "height": height, "stages": stages, "outcome": outcome_box,
            "title_height": title_height, "margin": margin}


def render_framework_svg(
    spec: dict[str, Any],
    theme: dict[str, Any],
) -> tuple[str, float, float, list[dict[str, Any]]]:
    stages = spec["framework_stages"]
    layout = spec.get("layout", {})
    positions = framework_layout(spec, theme)
    width, height, margin = positions["width"], positions["height"], positions["margin"]
    font = theme.get("svg_font_family", theme["font_family"])
    foreground = theme["foreground"]
    muted = theme["muted"]
    edge = theme.get("edge", foreground)
    surface = theme.get("surface", theme["background"])
    canvas = theme.get("canvas_background", theme["background"])
    fills = theme["node_fills"]
    accents = theme["accents"]
    panel_width = width - 2 * margin
    outcome = spec.get("outcome", {})
    outcome_y = positions["outcome"]["y"]
    outcome_height = positions["outcome"]["height"]
    description = spec.get("caption") or f"Research framework with {len(stages)} stages"

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}" role="img" aria-labelledby="figure-title figure-desc">',
        f'<title id="figure-title">{html.escape(spec.get("title", "Research framework"))}</title>',
        f'<desc id="figure-desc">{html.escape(description)}</desc>',
        "<defs>",
        f'<marker id="framework-arrow" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="{edge}"/></marker>',
        f'<filter id="framework-panel-shadow" x="-10%" y="-12%" width="120%" height="130%"><feDropShadow dx="0" dy="3" stdDeviation="4" flood-color="{foreground}" flood-opacity="0.09"/></filter>',
        f'<filter id="framework-card-shadow" x="-12%" y="-15%" width="124%" height="135%"><feDropShadow dx="0" dy="1.5" stdDeviation="2.2" flood-color="{foreground}" flood-opacity="0.07"/></filter>',
        f'<linearGradient id="framework-canvas" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="{canvas}"/><stop offset="100%" stop-color="{theme["background"]}"/></linearGradient>',
        f'<linearGradient id="framework-outcome" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="{fills[5 % len(fills)]}"/><stop offset="100%" stop-color="{surface}"/></linearGradient>',
        "</defs>",
        f'<rect x="0" y="0" width="{width:.0f}" height="{height:.0f}" fill="url(#framework-canvas)"/>',
    ]
    parts.extend(_title_svg(spec, theme, font, margin))

    stage_boxes = positions["stages"]

    spine_x = width / 2
    for index in range(len(stage_boxes) - 1):
        current = stage_boxes[index]
        following = stage_boxes[index + 1]
        y1 = current["y"] + current["height"]
        y2 = following["y"]
        parts.append(
            f'<path d="M {spine_x:.1f} {y1:.1f} V {y2-2:.1f}" fill="none" stroke="{edge}" stroke-width="1.8" marker-end="url(#framework-arrow)"/>'
        )
        transition = stages[index + 1].get("transition")
        if transition:
            label_y = (y1 + y2) / 2
            label_width = max(74, len(str(transition)) * 7 + 22)
            parts.extend(
                [
                    f'<rect x="{spine_x-label_width/2:.1f}" y="{label_y-11:.1f}" width="{label_width:.1f}" height="22" rx="11" fill="{surface}" stroke="{theme["grid"]}" stroke-width="0.9"/>',
                    f'<text x="{spine_x:.1f}" y="{label_y+1:.1f}" dominant-baseline="middle" text-anchor="middle" fill="{muted}" font-family="{font}" font-size="9.5" font-weight="700">{html.escape(str(transition))}</text>',
                ]
            )

    feedback = spec.get("feedback")
    if isinstance(feedback, dict):
        source_index = _stage_index(stages, feedback.get("from"))
        target_index = _stage_index(stages, feedback.get("to"))
        if source_index is not None and target_index is not None:
            source = stage_boxes[source_index]
            target = stage_boxes[target_index]
            route_x = width - 26
            y1 = source["y"] + source["height"] / 2
            y2 = target["y"] + target["height"] / 2
            parts.append(
                f'<path d="M {source["x"]+source["width"]:.1f} {y1:.1f} H {route_x:.1f} V {y2:.1f} H {target["x"]+target["width"]:.1f}" fill="none" stroke="{accents[4 % len(accents)]}" stroke-width="1.4" stroke-dasharray="7 5" marker-end="url(#framework-arrow)"/>'
            )
            parts.append(
                f'<text x="{route_x-7:.1f}" y="{(y1+y2)/2:.1f}" transform="rotate(-90 {route_x-7:.1f} {(y1+y2)/2:.1f})" text-anchor="middle" fill="{accents[4 % len(accents)]}" font-family="{font}" font-size="9" font-weight="700">{html.escape(str(feedback.get("label", "feedback")))}</text>'
            )

    for index, (stage, box) in enumerate(zip(stages, stage_boxes)):
        parts.extend(
            _stage_svg(
                stage,
                box,
                index,
                theme,
                font,
            )
        )

    last = stage_boxes[-1]
    outcome_width = positions["outcome"]["width"]
    outcome_x = width / 2 - outcome_width / 2
    parts.append(
        f'<path d="M {spine_x:.1f} {last["y"]+last["height"]:.1f} V {outcome_y-3:.1f}" fill="none" stroke="{edge}" stroke-width="1.8" marker-end="url(#framework-arrow)"/>'
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

    geometry = [{key: value for key, value in box.items() if key not in {"items", "header_height"}} for box in stage_boxes] + [
        {
            "id": "outcome",
            "x": outcome_x,
            "y": outcome_y,
            "width": outcome_width,
            "height": outcome_height,
        }
    ]
    parts.append("</svg>")
    return "\n".join(parts) + "\n", width, height, geometry


def _title_svg(
    spec: dict[str, Any],
    theme: dict[str, Any],
    font: str,
    margin: float,
) -> list[str]:
    accent = theme.get("title_accent", theme["accents"][0])
    width = float(spec.get("layout", {}).get("width", 1160)) - 2 * margin - 18
    title, caption = spec.get("title", "Research framework"), spec.get("caption", "")
    height = label_height(title, caption, width, font, 19, 10.5)
    result = [f'<rect x="{margin:.1f}" y="18" width="5" height="{height:.1f}" rx="2.5" fill="{accent}"/>']
    result.extend(label_svg(title, caption, margin + 18, 18, width, height, font, 19, 10.5,
                            theme["foreground"], theme["muted"], theme["background"], "start"))
    return result


def _stage_svg(
    stage: dict[str, Any],
    box: dict[str, Any],
    index: int,
    theme: dict[str, Any],
    font: str,
) -> list[str]:
    fill = stage.get("fill", theme["node_fills"][index % len(theme["node_fills"])])
    accent = stage.get("accent", theme["accents"][index % len(theme["accents"])])
    foreground = theme["foreground"]
    muted = theme["muted"]
    surface = theme.get("surface", theme["background"])
    x, y = box["x"], box["y"]
    width, height = box["width"], box["height"]
    parts = [
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" rx="20" fill="{fill}" fill-opacity="0.30" stroke="{accent}" stroke-opacity="0.50" stroke-width="1.3" filter="url(#framework-panel-shadow)"/>',
        f'<circle cx="{x+23:.1f}" cy="{y+24:.1f}" r="12" fill="{accent}"/>',
        f'<text x="{x+23:.1f}" y="{y+24.5:.1f}" dominant-baseline="middle" text-anchor="middle" fill="{readable_color("#FFFFFF", accent)}" font-family="{font}" font-size="9" font-weight="700">{index+1:02d}</text>',
    ]
    parts.extend(label_svg(stage["title"], stage.get("subtitle", ""), x + 44, y + 10,
                           width - 64, box["header_height"] - 20, font, 13, 9.2,
                           accent, muted, surface, "start"))
    items = stage.get("items", [])
    item_boxes = box["items"]
    if stage.get("connect_items") and len(item_boxes) > 1:
        for left, right in zip(item_boxes, item_boxes[1:]):
            if left["y"] != right["y"]:
                raise ValueError("Connected framework items require a wider panel to remain on one row")
            cy = left["y"] + left["height"] / 2
            parts.append(
                f'<path d="M {left["x"]+left["width"]:.1f} {cy:.1f} H {right["x"]-2:.1f}" fill="none" stroke="{theme.get("edge", foreground)}" stroke-width="1.4" marker-end="url(#framework-arrow)"/>'
            )
    for item_index, (item, item_box) in enumerate(zip(items, item_boxes)):
        parts.extend(
            _item_svg(
                item,
                item_box,
                stage.get("role", "default"),
                item_index,
                accent,
                fill,
                surface,
                theme,
                font,
            )
        )
    return parts


def _item_svg(
    item: dict[str, Any],
    box: dict[str, float],
    stage_role: str,
    index: int,
    accent: str,
    fill: str,
    surface: str,
    theme: dict[str, Any],
    font: str,
) -> list[str]:
    role = str(item.get("role", stage_role))
    shape = str(item.get("shape", "rounded"))
    x, y, width, height = box["x"], box["y"], box["width"], box["height"]
    card_fill = item.get("fill", surface if role in {"input", "analysis"} else fill)
    parts: list[str] = []
    if shape == "database":
        parts.extend(
            [
                f'<path d="M {x:.1f} {y+10:.1f} C {x:.1f} {y-1:.1f}, {x+width:.1f} {y-1:.1f}, {x+width:.1f} {y+10:.1f} L {x+width:.1f} {y+height-10:.1f} C {x+width:.1f} {y+height+1:.1f}, {x:.1f} {y+height+1:.1f}, {x:.1f} {y+height-10:.1f} Z" fill="{card_fill}" stroke="{accent}" stroke-width="1.3" filter="url(#framework-card-shadow)"/>',
                f'<ellipse cx="{x+width/2:.1f}" cy="{y+10:.1f}" rx="{width/2:.1f}" ry="10" fill="{card_fill}" stroke="{accent}" stroke-width="1.3"/>',
            ]
        )
    elif shape == "diamond" or role == "risk":
        points = (
            f"{x+width/2:.1f},{y:.1f} {x+width:.1f},{y+height/2:.1f} "
            f"{x+width/2:.1f},{y+height:.1f} {x:.1f},{y+height/2:.1f}"
        )
        parts.append(
            f'<polygon points="{points}" fill="{card_fill}" stroke="{accent}" stroke-width="1.4" filter="url(#framework-card-shadow)"/>'
        )
    else:
        radius = height / 2 if shape == "pill" else 13
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" rx="{radius:.1f}" fill="{card_fill}" stroke="{accent}" stroke-width="1.3" filter="url(#framework-card-shadow)"/>'
        )
    step = item.get("step")
    if step:
        parts.extend(
            [
                f'<circle cx="{x+15:.1f}" cy="{y-6:.1f}" r="11" fill="{surface}" stroke="{accent}" stroke-width="1.2"/>',
                f'<text x="{x+15:.1f}" y="{y-5.5:.1f}" dominant-baseline="middle" text-anchor="middle" fill="{accent}" font-family="{font}" font-size="8.5" font-weight="700">{html.escape(str(step))}</text>',
            ]
        )
    icon = item.get("icon")
    diamond = shape == "diamond" or role == "risk"
    icon_allowed = bool(icon) and shape != "database" and not diamond
    if icon_allowed:
        icon_size = 22.0
        badge_x = x + 17
        badge_y = y + height / 2
        parts.append(
            f'<circle cx="{badge_x:.1f}" cy="{badge_y:.1f}" r="15" fill="{accent}" opacity="0.11"/>'
        )
        parts.append(
            render_icon(
                str(icon),
                badge_x - icon_size / 2,
                badge_y - icon_size / 2,
                icon_size,
                accent,
            )
        )
        text_x = x + 43
        anchor = "start"
    else:
        text_x = x + width / 2
        anchor = "middle"
    inset_x = width / 4 + 14 if diamond else (43 if icon_allowed else 14)
    inset_y = height / 4 + 8 if diamond else (21 if shape == "database" else 10)
    text_width = width / 2 - 28 if diamond else width - inset_x - 14
    text_height = height / 2 - 16 if diamond else height - inset_y - 10
    parts.extend(label_svg(item["label"], item.get("subtitle", ""), x + inset_x, y + inset_y,
                           text_width, text_height, font, 11, 8.8, theme["foreground"],
                           theme["muted"], card_fill, anchor))
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
    accent = outcome.get("accent", theme["accents"][5 % len(theme["accents"])])
    label = str(outcome.get("label", "Research outcome"))
    subtitle = str(outcome.get("subtitle", ""))
    parts = [
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" rx="{height/2:.1f}" fill="url(#framework-outcome)" stroke="{accent}" stroke-width="2" filter="url(#framework-panel-shadow)"/>',
        f'<rect x="{x+5:.1f}" y="{y+5:.1f}" width="{width-10:.1f}" height="{height-10:.1f}" rx="{height/2-5:.1f}" fill="none" stroke="{accent}" stroke-opacity="0.34" stroke-width="1"/>',
    ]
    if outcome.get("icon"):
        parts.append(
            render_icon(
                str(outcome["icon"]),
                x + 24,
                y + height / 2 - 13,
                26,
                accent,
            )
        )
        text_x = x + 64
        anchor = "start"
    else:
        text_x = x + width / 2
        anchor = "middle"
    left = 64 if outcome.get("icon") else 24
    parts.extend(label_svg(label, subtitle, x + left, y + 15, width - left - 24, height - 30,
                           font, 12.5, 9.2, theme["foreground"], theme["muted"],
                           theme.get("surface", theme["background"]), anchor))
    return parts


def _stage_index(
    stages: list[dict[str, Any]],
    stage_id: Any,
) -> int | None:
    for index, stage in enumerate(stages):
        if stage.get("id") == stage_id:
            return index
    return None
