from __future__ import annotations

import xml.etree.ElementTree as ET
import re
from pathlib import Path
from typing import Any

from .typography import label_height, label_svg


def provenance_description(spec: dict[str, Any]) -> dict[str, Any]:
    value = spec.get("provenance", {})
    kind = value.get("type", "unspecified")
    chinese = spec.get("language") == "zh-CN"
    labels = {
        "conceptual": ("Conceptual illustration", "概念示意"),
        "code-derived": ("Derived from declared code", "基于声明的代码来源"),
        "data-derived": ("Derived from declared data", "基于声明的数据来源"),
        "unspecified": ("Source basis unspecified", "来源依据未声明"),
    }
    label = labels[kind][int(chinese)]
    if kind in {"code-derived", "data-derived"}:
        label += (
            (" · 作者声明已核验" if chinese else " · Verification declared by author")
            if value.get("verified") else
            (" · 未声明独立核验" if chinese else " · Independent verification not declared")
        )
    return {"type": kind, "label": label, "summary": value.get("summary", ""),
            "sources": list(value.get("sources", [])),
            "verification_declared": bool(value.get("verified", False))}


def append_provenance(
    svg: str, spec: dict[str, Any], theme: dict[str, Any],
) -> tuple[str, float | None]:
    if "provenance" not in spec:
        return svg, None
    root = ET.fromstring(svg)
    x, y, width, height = map(float, root.attrib["viewBox"].split())
    information = provenance_description(spec)
    title = information["label"]
    subtitle = information["summary"]
    font = theme.get("svg_font_family", theme["font_family"])
    size = max(10.0, float(theme.get("font_size", 12)) - 1)
    margin = min(24.0, width / 10)
    content_height = label_height(title, subtitle, width - 2 * margin, font, size, size)
    footer_height = content_height + 28
    fill = theme.get("background", "#FFFFFF")
    elements = [
        f'<g id="figure-provenance"><rect x="{x:g}" y="{y + height:g}" '
        f'width="{width:g}" height="{footer_height:g}" fill="{fill}"/>',
        *label_svg(title, subtitle, x + margin, y + height + 12, width - 2 * margin,
                   content_height, font, size, size, theme["foreground"], theme["muted"], fill, "start"),
        "</g>",
    ]
    # Preserve renderer markup and editable font runs instead of reserializing the whole SVG.
    opening_end = svg.index(">", svg.index("<svg"))
    opening = svg[svg.index("<svg"):opening_end + 1]
    changed = re.sub(r'\bheight="[^"]*"', f'height="{height + footer_height:g}"', opening, count=1)
    changed = re.sub(r'\bviewBox="[^"]*"', f'viewBox="{x:g} {y:g} {width:g} {height + footer_height:g}"', changed)
    svg = svg.replace(opening, changed, 1)
    return svg.replace("</svg>", "\n".join(elements) + "\n</svg>", 1), height + footer_height


def append_drawio_provenance(
    path: Path, spec: dict[str, Any], theme: dict[str, Any],
    width: float, y: float, height: float,
) -> None:
    from .drawio import _html_text, _style, _vertex, _write
    from .typography import readable_color

    document = ET.parse(path).getroot()
    root = document.find(".//root")
    if root is None:
        raise ValueError("Draw.io output is missing its editable root")
    used = {cell.get("id") for cell in root}
    cell_id = "figure-provenance"
    while cell_id in used:
        cell_id += "-footer"
    information = provenance_description(spec)
    fill = theme["background"]
    _vertex(root, cell_id, _html_text(information["label"], information["summary"]),
            _style(html=1, whiteSpace="wrap", align="left", verticalAlign="middle",
                   fillColor=fill, strokeColor="none", fontSize=max(10, theme["font_size"] - 1),
                   fontColor=readable_color(theme["foreground"], fill)),
            1, 24, y, width - 48, height)
    _write(path, document)
