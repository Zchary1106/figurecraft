from __future__ import annotations

import html
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from . import __version__


def export_drawio(
    spec: dict[str, Any],
    output_dir: Path,
    theme: dict[str, Any],
    boxes: dict[str, Any],
    canvas: tuple[float, float],
    geometry: list[dict[str, Any]] | None = None,
) -> Path:
    width, height = canvas
    model, root = _document(width, height, theme)
    if spec["kind"] == "diagram.cnn-architecture":
        _cnn_diagram(root, spec, theme, width)
    elif spec["kind"] == "diagram.system-landscape":
        _system_landscape(root, spec, theme, width, geometry)
    elif spec["kind"] == "diagram.framework-matrix":
        _framework_matrix(root, spec, theme, geometry)
    elif spec["kind"] == "diagram.research-framework" and spec.get("framework_stages"):
        _framework(root, spec, theme)
    else:
        _generic_diagram(root, spec, theme, boxes, geometry)
    path = output_dir / "figure.drawio"
    _write(path, model)
    return path


def _document(
    width: float,
    height: float,
    theme: dict[str, Any],
) -> tuple[ET.Element, ET.Element]:
    mxfile = ET.Element(
        "mxfile",
        {
            "host": "app.diagrams.net",
            "agent": "figurecraft",
            "version": __version__,
            "compressed": "false",
        },
    )
    diagram = ET.SubElement(mxfile, "diagram", {"id": "page-1", "name": "Page-1"})
    graph = ET.SubElement(
        diagram,
        "mxGraphModel",
        {
            "dx": str(int(width)),
            "dy": str(int(height)),
            "grid": "1",
            "gridSize": "10",
            "guides": "1",
            "tooltips": "1",
            "connect": "1",
            "arrows": "1",
            "fold": "1",
            "page": "1",
            "pageScale": "1",
            "pageWidth": str(int(width)),
            "pageHeight": str(int(height)),
            "background": theme.get(
                "canvas_background", theme.get("background", "#FFFFFF")
            ),
            "math": "0",
            "shadow": "0",
        },
    )
    root = ET.SubElement(graph, "root")
    ET.SubElement(root, "mxCell", {"id": "0"})
    ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})
    return mxfile, root


def _framework_vertex(
    root: ET.Element,
    cell_id: str,
    item: dict[str, Any],
    box: dict[str, Any],
    theme: dict[str, Any],
    fill: str,
    accent: str,
    parent: str = "1",
    parent_box: dict[str, Any] | None = None,
    container: bool = False,
) -> None:
    from .typography import readable_color

    shape = item.get("shape", "rounded")
    shape_style = {
        "database": "shape=cylinder3;boundedLbl=1;backgroundOutline=1",
        "diamond": "rhombus",
        "pill": "rounded=1;arcSize=50",
    }.get(shape, "rounded=1;arcSize=16")
    primary = item.get("label", item.get("title", ""))
    if item.get("step"):
        primary = f"{item['step']} · {primary}"
    background = item.get("fill", fill)
    foreground = readable_color(theme["foreground"], background)
    secondary = readable_color(theme["muted"], background)
    _vertex(
        root, cell_id, _html_text(primary, _secondary(item), secondary),
        _style(
            html=1, whiteSpace="wrap", container=int(container),
            recursiveResize=0, collapsible=0,
            align="left" if container else "center",
            verticalAlign="top" if container else "middle",
            spacingTop=12 if container else 4, spacingLeft=16 if container else 4,
            fontColor=foreground, fontSize=12 if container else 11,
            fontFamily=theme["font_family"], fontStyle=1,
            fillColor=background, strokeColor=item.get("accent", accent),
            strokeWidth=1.3, raw=shape_style,
        ),
        parent,
        box["x"] - (parent_box["x"] if parent_box else 0),
        box["y"] - (parent_box["y"] if parent_box else 0),
        box["width"], box["height"],
    )
    cell = root[-1]
    for key in ("status", "state", "role", "phase"):
        if key in item:
            cell.set(key, str(item[key]))


def _framework_heading(root: ET.Element, spec: dict[str, Any], theme: dict[str, Any], positions: dict[str, Any]) -> None:
    if not spec.get("title"):
        return
    margin = positions["margin"]
    _vertex(
        root, "figure-title", _html_text(spec["title"], spec.get("caption")),
        _style(html=1, whiteSpace="wrap", strokeColor="none", fillColor="none",
               align="left", verticalAlign="middle", fontColor=theme["foreground"],
               fontSize=19, fontStyle=1, fontFamily=theme["font_family"]),
        1, margin + 18, 18, positions["width"] - 2 * margin - 18,
        positions.get("title_height", max(48, positions.get("phase_y", 90) - 42)),
    )


def _framework(root: ET.Element, spec: dict[str, Any], theme: dict[str, Any]) -> None:
    from .framework import framework_layout

    positions = framework_layout(spec, theme)
    _framework_heading(root, spec, theme, positions)
    fills, accents = theme["node_fills"], theme["accents"]
    surface = theme.get("surface", theme["background"])
    stages = spec["framework_stages"]
    stage_boxes = positions["stages"]
    by_id = {box["id"]: box for box in stage_boxes}
    for index, (stage, box) in enumerate(zip(stages, stage_boxes)):
        fill = stage.get("fill", fills[index % len(fills)])
        accent = stage.get("accent", accents[index % len(accents)])
        stage_id = f"framework-stage-{stage['id']}"
        _framework_vertex(root, stage_id, stage, box, theme, fill, accent, container=True)
        item_ids = []
        for item_index, (item, item_box) in enumerate(zip(stage.get("items", []), box["items"])):
            item_id = f"{stage_id}-item-{item_index}"
            role = item.get("role", stage.get("role", "default"))
            item_fill = surface if role in {"input", "analysis"} else fill
            shape_item = {**item, "shape": "diamond"} if role == "risk" else item
            _framework_vertex(root, item_id, shape_item, item_box, theme, item_fill, accent, stage_id, box)
            item_ids.append(item_id)
        if stage.get("connect_items"):
            for item_index, (left, right) in enumerate(zip(item_ids, item_ids[1:])):
                _edge(root, f"{stage_id}-edge-{item_index}", "", left, right, theme, False,
                      source_box=box["items"][item_index], target_box=box["items"][item_index + 1])
    for index, (left, right) in enumerate(zip(stages, stages[1:])):
        _edge(root, f"framework-transition-{index}", html.escape(str(right.get("transition", ""))),
              f"framework-stage-{left['id']}", f"framework-stage-{right['id']}", theme, False,
              source_box=by_id[left["id"]], target_box=by_id[right["id"]])
    outcome = {"label": "Research outcome", "shape": "pill", **spec.get("outcome", {})}
    _framework_vertex(root, "framework-outcome", outcome, positions["outcome"], theme,
                      fills[5 % len(fills)], accents[5 % len(accents)])
    _edge(root, "framework-outcome-edge", "", f"framework-stage-{stages[-1]['id']}",
          "framework-outcome", theme, False, source_box=stage_boxes[-1], target_box=positions["outcome"])
    if isinstance(spec.get("feedback"), dict):
        feedback = {"kind": "feedback", "style": "dashed", **spec["feedback"]}
        _edge(root, "framework-feedback", _relationship_label(feedback),
              f"framework-stage-{feedback['from']}", f"framework-stage-{feedback['to']}",
              theme, feedback["style"] == "dashed",
              relationship={"source_port": "E", "target_port": "E", **feedback},
              source_box=by_id[feedback["from"]], target_box=by_id[feedback["to"]])


def _framework_matrix(
    root: ET.Element, spec: dict[str, Any], theme: dict[str, Any],
    geometry: list[dict[str, Any]] | None = None,
) -> None:
    from .framework_matrix import _matrix_routes, matrix_layout

    positions = matrix_layout(spec, theme)
    if geometry is None or not hasattr(geometry, "edges"):
        geometry = _matrix_routes(spec, positions, theme)
    routes = {edge["id"]: edge["points"] for edge in getattr(geometry, "edges", [])}
    _framework_heading(root, spec, theme, positions)
    fills, accents = theme["node_fills"], theme["accents"]
    surface = theme.get("surface", theme["background"])
    for index, phase in enumerate(spec["phases"]):
        box = {
            "x": positions["grid_x"] + index * positions["column_width"] + 8,
            "y": positions["phase_y"],
            "width": positions["column_width"] - 16,
            "height": positions["phase_height"],
        }
        _framework_vertex(root, f"matrix-phase-{phase['id']}", phase, box, theme,
                          accents[index % len(accents)] if theme.get("phase_header_mode") == "solid" else fills[index % len(fills)],
                          accents[index % len(accents)])
    cell_boxes = positions["cells"]
    for index, (track, box) in enumerate(zip(spec["tracks"], positions["tracks"])):
        track_id = f"matrix-track-{track['id']}"
        accent = track.get("accent", accents[index % len(accents)])
        fill = track.get("fill", fills[index % len(fills)])
        _framework_vertex(root, track_id, {}, box, theme, fill, accent, container=True)
        label_box = {**box, "width": positions["label_width"] - 14}
        _framework_vertex(root, f"{track_id}-label", track, label_box, theme,
                          accent if theme.get("track_label_mode") == "solid" else fill,
                          accent, track_id, box)
        cells = sorted(track.get("cells", []), key=lambda cell: cell_boxes[cell["id"]]["phase"])
        for cell in cells:
            _framework_vertex(root, f"matrix-cell-{cell['id']}", cell, cell_boxes[cell["id"]], theme,
                              fill if theme.get("framework_card_mode") == "tinted" else surface,
                              accent, track_id, box)
        for edge_index, (left, right) in enumerate(zip(cells, cells[1:])):
            _edge(root, f"{track_id}-edge-{edge_index}", "", f"matrix-cell-{left['id']}",
                  f"matrix-cell-{right['id']}", theme, False,
                  source_box=cell_boxes[left["id"]], target_box=cell_boxes[right["id"]],
                  points=routes.get(f"matrix-progression-{index}-{edge_index}"))
        if cells:
            last = cells[-1]
            _edge(root, f"{track_id}-integration", "", f"matrix-cell-{last['id']}",
                  "matrix-integration", theme, False,
                  relationship={"color": accent, "source_port": "E", "target_port": "N"},
                  source_box=cell_boxes[last["id"]], target_box=positions["integration"],
                  points=routes[f"matrix-branch-{index}"] + routes["matrix-evidence-bus"][1:])
    for index, link in enumerate(spec.get("cross_links", [])):
        relationship = {"kind": "feedback", "style": "dashed", **link}
        _edge(root, f"matrix-cross-link-{index}", _relationship_label(relationship),
              f"matrix-cell-{link['from']}", f"matrix-cell-{link['to']}", theme,
              relationship["style"] == "dashed", relationship=relationship,
              source_box=cell_boxes[link["from"]], target_box=cell_boxes[link["to"]],
              points=routes.get(f"matrix-cross-{index}"))
    integration = {"label": "Evidence integration", **spec.get("integration", {})}
    chips = integration.get("chips", [])
    _framework_vertex(root, "matrix-integration", integration, positions["integration"], theme,
                      theme.get("integration_fill", fills[5 % len(fills)]),
                      theme.get("integration_accent", accents[5 % len(accents)]),
                      container=bool(positions.get("chips")))
    if chips:
        cell = root[-1]
        cell.set("style", cell.get("style") + f"labelWidth={positions['integration']['width'] * 0.45 - 44};")
    for index, (chip, box) in enumerate(zip(chips, positions.get("chips", []))):
        _framework_vertex(root, f"matrix-integration-chip-{index}", {"label": str(chip)}, box,
                          theme, surface, accents[5 % len(accents)],
                          "matrix-integration", positions["integration"])
    outcome = {"label": "Research outcome", "shape": "pill", **spec.get("outcome", {})}
    _framework_vertex(root, "matrix-outcome", outcome, positions["outcome"], theme,
                      theme.get("outcome_start", fills[5 % len(fills)]), accents[4 % len(accents)])
    _edge(root, "matrix-outcome-edge", "", "matrix-integration", "matrix-outcome", theme, False,
          source_box=positions["integration"], target_box=positions["outcome"],
          points=routes.get("matrix-outcome"))


def _system_landscape(
    root: ET.Element,
    spec: dict[str, Any],
    theme: dict[str, Any],
    width: float,
    geometry: list[dict[str, Any]] | None = None,
) -> None:
    from .diagrams import landscape_zone_layout

    if geometry is None:
        from .diagrams import _system_landscape_svg

        _, _, _, geometry = _system_landscape_svg(spec, theme)
    layout = spec.get("layout", {})
    margin = float(layout.get("margin", 24))
    zone_boxes: dict[str, dict[str, float]] = {box["id"]: box for box in geometry}

    if spec.get("title"):
        _vertex(
            root,
            "figure-title",
            _html_text(spec["title"], spec.get("caption")),
            _style(
                html=1,
                whiteSpace="wrap",
                strokeColor="none",
                fillColor="none",
                align="left",
                verticalAlign="middle",
                fontColor=theme["foreground"],
                fontSize=18,
                fontStyle=1,
            ),
            1,
            margin + 16,
            8,
            width - margin * 2,
            48,
        )

    fills = theme.get("node_fills", [theme["group_fill"]])
    accents = theme.get("accents", [theme["group_stroke"]])
    for zone in spec["zones"]:
        box = zone_boxes[zone["id"]]
        positions = landscape_zone_layout(zone, box["width"], theme)
        zone_id = f"zone-{zone['id']}"
        _vertex(
            root,
            zone_id,
            _html_text(zone["title"], _secondary(zone), theme["muted"],
                       inline=positions["header"]["inline"], secondary_size=theme["font_size"]),
            _style(
                html=1,
                whiteSpace="wrap",
                rounded=1,
                arcSize=8,
                container=1,
                recursiveResize=0,
                collapsible=0,
                align="left",
                verticalAlign="top",
                spacingTop=10,
                spacingLeft=18,
                spacingRight=18,
                fontColor=theme["foreground"],
                fontSize=theme["font_size"] + 3,
                fontFamily=theme.get("svg_font_family", theme["font_family"]),
                fontStyle=1,
                fillColor=theme.get("surface", theme["background"]),
                strokeColor=theme.get("zone_border", theme["foreground"]),
                strokeWidth=1.8,
                shadow=1,
            ),
            1,
            box["x"],
            box["y"],
            box["width"],
            box["height"],
        )
        _drawio_sections(
            root,
            zone,
            zone_id,
            box["width"],
            theme,
            fills,
            accents,
        )

    for index, connection in enumerate(spec.get("connections", [])):
        _edge(
            root,
            f"connection-{connection.get('id', index)}",
            _relationship_label(connection),
            f"zone-{connection['from']}",
            f"zone-{connection['to']}",
            theme,
            dashed=connection.get("style") == "dashed",
            relationship=connection,
            source_box=zone_boxes[connection["from"]],
            target_box=zone_boxes[connection["to"]],
            points=_route_points(geometry, index),
        )


def _cnn_diagram(
    root: ET.Element,
    spec: dict[str, Any],
    theme: dict[str, Any],
    width: float,
) -> None:
    from .cnn import block_layout, cnn_layout_spec

    spec = cnn_layout_spec(spec, theme)
    layout = spec.get("layout", {})
    width = float(layout.get("width", width))
    margin = float(layout.get("margin", 48))
    main_y = float(layout.get("main_y", 235))
    stages = spec["stages"]
    slot = (width - 2 * margin) / len(stages)
    palette = theme["palette"]
    fills = theme["node_fills"]
    if spec.get("title"):
        _vertex(
            root,
            "figure-title",
            _html_text(spec["title"], spec.get("caption")),
            _style(
                html=1,
                whiteSpace="wrap",
                strokeColor="none",
                fillColor="none",
                align="left",
                verticalAlign="middle",
                fontColor=theme["foreground"],
                fontSize=18,
                fontStyle=1,
            ),
            1,
            margin,
            8,
            width - margin * 2,
            52,
        )
    for index, stage in enumerate(stages):
        center_x = margin + slot * (index + 0.5)
        stage_type = stage.get("type", "tensor")
        cell_width = float(stage.get("width", 132 if stage_type == "operator" else 116))
        cell_height = float(stage.get("height", 72 if stage_type == "operator" else 108))
        repeat = int(stage.get("repeat", 1))
        dimension = _drawio_dimension(stage)
        secondary = " · ".join(
            item
            for item in (
                str(stage.get("operation", "")).strip(),
                dimension,
                f"×{repeat}" if repeat > 1 else "",
            )
            if item
        )
        shape = "shape=process" if stage_type == "tensor" else "rounded=1;arcSize=16"
        _vertex(
            root,
            f"cnn-stage-{stage['id']}",
            _html_text(stage.get("label", stage["title"]), secondary),
            _style(
                html=1,
                whiteSpace="wrap",
                align="center",
                verticalAlign="middle",
                fontColor=theme["foreground"],
                fontSize=11,
                fontStyle=1,
                fillColor=stage.get("fill", fills[index % len(fills)]),
                strokeColor=stage.get("color", palette[index % len(palette)]),
                strokeWidth=1.4,
                shadow=1,
                raw=shape,
            ),
            1,
            center_x - cell_width / 2,
            main_y - cell_height / 2,
            cell_width,
            cell_height,
        )
        _vertex(
            root,
            f"cnn-stage-label-{stage['id']}",
            f"<b>{html.escape(str(stage['title']))}</b>",
            _style(
                html=1,
                whiteSpace="wrap",
                strokeColor="none",
                fillColor="none",
                align="center",
                verticalAlign="middle",
                fontColor=theme["foreground"],
                fontSize=12,
                fontStyle=1,
            ),
            1,
            center_x - slot / 2 + 8,
            float(layout.get("band_y", 88)),
            slot - 16,
            30,
        )
    for index, (left, right) in enumerate(zip(stages, stages[1:])):
        _edge(
            root,
            f"cnn-stage-edge-{index}",
            str(right.get("transition", "")),
            f"cnn-stage-{left['id']}",
            f"cnn-stage-{right['id']}",
            theme,
            dashed=False,
        )
    detail = spec.get("block_detail")
    if not detail:
        return
    inset_x = float(layout.get("inset_x", 180))
    inset_y = float(layout.get("inset_y", 430))
    inset_width = float(layout.get("inset_width", 1040))
    inset_height = float(layout.get("inset_height", 210))
    positions = block_layout(
        detail, inset_x, inset_y, inset_width,
        theme.get("svg_font_family", theme["font_family"]),
    )
    start_x = positions["start_x"] - inset_x
    end_x = positions["end_x"] - inset_x
    path_y = positions["path_y"] - inset_y
    _vertex(
        root,
        "cnn-block-detail",
        _html_text(detail.get("title", "Block detail"), detail.get("subtitle")),
        _style(
            html=1,
            whiteSpace="wrap",
            rounded=1,
            arcSize=10,
            container=1,
            recursiveResize=0,
            collapsible=0,
            align="left",
            verticalAlign="top",
            spacingTop=10,
            spacingLeft=12,
            fontColor=theme["foreground"],
            fontSize=14,
            fontStyle=1,
            fillColor=theme.get("surface", theme["background"]),
            strokeColor=theme["group_stroke"],
            strokeWidth=1.3,
            shadow=1,
        ),
        1,
        inset_x,
        inset_y,
        inset_width,
        inset_height,
    )
    input_id = "cnn-detail-input"
    _vertex(
        root,
        input_id,
        "<b>x</b>",
        _style(
            html=1,
            ellipse=1,
            align="center",
            verticalAlign="middle",
            fillColor=fills[0],
            strokeColor=palette[0],
            fontSize=11,
            fontStyle=1,
        ),
        "cnn-block-detail",
        start_x - 18,
        path_y - 18,
        36,
        36,
    )
    steps = detail.get("steps", [])
    available = end_x - start_x
    step_width = positions["card_width"]
    step_height = positions["card_height"]
    gap = (available - step_width * len(steps)) / max(1, len(steps) + 1)
    previous = input_id
    for index, step in enumerate(steps):
        step_id = f"cnn-detail-step-{index}"
        step_x = start_x + gap * (index + 1) + step_width * index
        _vertex(
            root,
            step_id,
            _html_text(step["label"], step.get("subtitle")),
            _style(
                html=1,
                whiteSpace="wrap",
                rounded=1,
                arcSize=12,
                align="center",
                verticalAlign="middle",
                fillColor=fills[index % len(fills)],
                strokeColor=palette[index % len(palette)],
                strokeWidth=1.2,
                fontSize=10,
                fontStyle=1,
            ),
            "cnn-block-detail",
            step_x,
            path_y - step_height / 2,
            step_width,
            step_height,
        )
        _edge(
            root,
            f"cnn-detail-edge-{index}",
            "",
            previous,
            step_id,
            theme,
            dashed=False,
        )
        previous = step_id
    output_source = previous
    if detail.get("residual", True):
        merge_id = "cnn-detail-merge"
        _vertex(
            root, merge_id, "<b>+</b>",
            _style(html=1, ellipse=1, align="center", verticalAlign="middle",
                   fillColor=theme.get("surface", theme["background"]), strokeColor=palette[0],
                   fontSize=18, fontStyle=1),
            "cnn-block-detail", end_x - 19, path_y - 19, 38, 38,
        )
        _edge(root, "cnn-detail-main-merge", "", previous, merge_id, theme, False)
        output_source = merge_id
        residual_y = positions["residual_y"]
        input_x, merge_x = positions["start_x"], positions["end_x"]
        main_y = positions["path_y"]
        shortcut = detail.get("shortcut")
        if isinstance(shortcut, dict):
            shortcut_box = {
                "x": (input_x + merge_x) / 2 - 69,
                "y": residual_y - positions["shortcut_height"] / 2,
                "width": 138, "height": positions["shortcut_height"],
            }
            _framework_vertex(
                root, "cnn-detail-shortcut", {"label": "Projection", **shortcut},
                shortcut_box, theme, fills[4 % len(fills)], palette[4 % len(palette)],
                "cnn-block-detail", {"x": inset_x, "y": inset_y},
            )
            _edge(root, "cnn-detail-residual-input", "", input_id, "cnn-detail-shortcut", theme, False,
                  relationship={"source_port": "N", "target_port": "W"},
                  points=[(input_x, main_y - 18), (input_x, residual_y), (shortcut_box["x"], residual_y)])
            _edge(root, "cnn-detail-residual", "", "cnn-detail-shortcut", merge_id, theme, False,
                  relationship={"source_port": "E", "target_port": "N"},
                  points=[(shortcut_box["x"] + 138, residual_y), (merge_x, residual_y), (merge_x, main_y - 19)])
        else:
            _edge(root, "cnn-detail-residual", "identity shortcut", input_id, merge_id, theme, False,
                  relationship={"source_port": "N", "target_port": "N"},
                  points=[(input_x, main_y - 18), (input_x, residual_y),
                          (merge_x, residual_y), (merge_x, main_y - 19)])
    _framework_vertex(
        root, "cnn-detail-output", {"label": detail.get("output", "ReLU"), "shape": "pill"},
        {"x": positions["end_x"] + 43, "y": positions["path_y"] - 18, "width": 54, "height": 36},
        theme, fills[1 % len(fills)], palette[2 % len(palette)],
        "cnn-block-detail", {"x": inset_x, "y": inset_y},
    )
    _edge(root, "cnn-detail-output-edge", "", output_source, "cnn-detail-output", theme, False)
    _cnn_legend(root, spec, theme, layout, width)


def _cnn_legend(
    root: ET.Element,
    spec: dict[str, Any],
    theme: dict[str, Any],
    layout: dict[str, Any],
    canvas_width: float,
) -> None:
    from .cnn import legend_layout

    x = layout["inset_x"] + layout["inset_width"] + 34
    y = layout["inset_y"]
    width = canvas_width - x - float(layout.get("margin", 48))
    height = layout["inset_height"]
    font = theme.get("svg_font_family", theme["font_family"])
    positions = legend_layout(spec, width, font)
    table = spec.get("stage_table", [])
    _framework_vertex(
        root, "cnn-legend", {"title": "Stage schedule" if table else "Visual grammar"},
        {"x": x, "y": y, "width": width, "height": height}, theme,
        theme.get("surface", theme["background"]), theme["group_stroke"], container=True,
    )

    def text(cell_id: str, value: Any, left: float, top: float, span: float, size: float,
             text_height: float, align: str = "left") -> None:
        _vertex(
            root, cell_id, html.escape(str(value)),
            _style(html=1, whiteSpace="wrap", strokeColor="none", fillColor="none",
                   align=align, verticalAlign="middle", fontColor=theme["foreground"],
                   fontFamily=font, fontSize=size, spacing=0),
            "cnn-legend", left, top, span, text_height,
        )

    if table:
        for heading, (left, span) in zip(("Stage", "Output", "Block", "×"), positions["columns"]):
            text(f"cnn-legend-heading-{heading}", heading, left, 43, span, 8.8, 18,
                 "center" if heading == "×" else "left")
        row_y = 70.0
        for index, (row, row_height) in enumerate(zip(table, positions["rows"])):
            for key, (left, span) in zip(("stage", "output", "block", "repeat"), positions["columns"]):
                text(f"cnn-legend-row-{index}-{key}", row.get(key, ""), left, row_y + 6,
                     span, 9.2, row_height - 12, "center" if key == "repeat" else "left")
            row_y += row_height
    else:
        for index, value in enumerate(("Tensor / feature map", "Downsample transition",
                                       "Residual / identity", "Repeated block")):
            text(f"cnn-legend-entry-{index}", value, 20, 49 + 35 * index, width - 40, 10, 26)
    text("cnn-legend-note", positions["note"], 20, height - positions["note_height"] - 16,
         width - 40, 8.2, positions["note_height"])


def _drawio_sections(
    root: ET.Element,
    zone: dict[str, Any],
    zone_id: str,
    zone_width: float,
    theme: dict[str, Any],
    fills: list[str],
    accents: list[str],
) -> None:
    from .diagrams import landscape_section_layout, landscape_zone_layout

    sections = zone.get("sections", [])
    positions = landscape_zone_layout(zone, zone_width, theme)
    for box in positions["sections"]:
        section = sections[box["index"]]
        section_id = f"{zone_id}-section-{box['index']}"
        section_layout = landscape_section_layout(section, box["width"], theme)
        tone_index = _tone_index(section.get("tone"))
        neutral = section.get("tone", "neutral") == "neutral"
        fill = theme["group_fill"] if neutral else fills[tone_index % len(fills)]
        accent = theme["muted"] if neutral else accents[tone_index % len(accents)]
        _vertex(
            root, section_id,
            _html_text(section["title"], _secondary(section), theme["muted"],
                       inline=section_layout["header"]["inline"],
                       secondary_size=max(7, theme["font_size"] - 2)),
            _style(
                html=1, whiteSpace="wrap", rounded=1, arcSize=8,
                container=1, recursiveResize=0, collapsible=0,
                align="left", verticalAlign="top", spacingTop=8,
                spacingLeft=34 if section.get("icon") else 24, spacingRight=12,
                fontColor=accent, fontSize=theme["font_size"] + 1,
                fontFamily=theme.get("svg_font_family", theme["font_family"]),
                fontStyle=1, fillColor=fill, fillOpacity=52,
                strokeColor=accent, strokeWidth=1.25,
            ),
            zone_id, box["x"], box["y"], box["width"], box["height"],
        )
        _drawio_cards(root, section, section_id, box["width"], theme, fill, accent)


def _drawio_cards(
    root: ET.Element,
    section: dict[str, Any],
    section_id: str,
    section_width: float,
    theme: dict[str, Any],
    fill: str,
    accent: str,
) -> None:
    from .diagrams import landscape_section_layout

    items = section.get("items", [])
    positions = landscape_section_layout(section, section_width, theme)
    for box in positions["items"]:
        index = box["index"]
        item = items[index]
        card_fill = (
            theme.get("neutral_surface", theme["background"])
            if section.get("tone", "neutral") == "neutral"
            else fill
        )
        _vertex(
            root,
            f"{section_id}-card-{index}",
            _html_text(
                _icon_prefix(item.get("icon")) + str(item["label"]),
                _secondary(item), theme["muted"],
                secondary_size=max(7, theme["font_size"] - 3),
            ),
            _style(
                html=1,
                whiteSpace="wrap",
                rounded=1,
                arcSize=12,
                align="center",
                verticalAlign="middle",
                fontColor=theme["foreground"],
                fontSize=max(8, theme["font_size"] - 1),
                fontFamily=theme.get("svg_font_family", theme["font_family"]),
                fontStyle=1,
                fillColor=card_fill,
                strokeColor=accent,
                strokeWidth=1.15,
                shadow=1,
            ),
            section_id,
            box["x"], box["y"], box["width"], box["height"],
        )
    if section.get("note"):
        box = positions["note"]
        _vertex(
            root, f"{section_id}-note", html.escape(str(section["note"])),
            _style(html=1, whiteSpace="wrap", rounded=1, arcSize=8,
                   align="left", verticalAlign="middle", spacingLeft=8, spacingRight=8,
                   fillColor=fill, strokeColor="none", fontColor=accent,
                   fontFamily=theme.get("svg_font_family", theme["font_family"]),
                   fontSize=max(7, theme["font_size"] - 2)),
            section_id, box["x"], box["y"], box["width"], box["height"],
        )


def _generic_diagram(
    root: ET.Element,
    spec: dict[str, Any],
    theme: dict[str, Any],
    boxes: dict[str, Any],
    geometry: list[dict[str, Any]] | None = None,
) -> None:
    fills = theme.get("node_fills", [theme["node_fill"]])
    accents = theme.get("accents", [theme["node_stroke"]])
    if spec.get("title"):
        _vertex(
            root,
            "figure-title",
            _html_text(spec["title"], spec.get("caption")),
            _style(
                html=1,
                whiteSpace="wrap",
                strokeColor="none",
                fillColor="none",
                align="left",
                verticalAlign="middle",
                fontColor=theme["foreground"],
                fontSize=16,
                fontStyle=1,
            ),
            1,
            24,
            8,
            600,
            48,
        )
    for node in spec.get("nodes", []):
        box = boxes[node["id"]]
        layer = box.layer
        shape = node.get("shape", "rounded")
        shape_style = {
            "ellipse": "ellipse",
            "diamond": "rhombus",
            "database": "shape=cylinder3;boundedLbl=1;backgroundOutline=1",
            "tensor": "shape=process",
            "document": "shape=note;size=16",
            "pill": "rounded=1;arcSize=50",
            "operation": "ellipse",
        }.get(shape, "rounded=1;arcSize=12")
        _vertex(
            root,
            f"node-{node['id']}",
            _html_text(
                _icon_prefix(node.get("icon")) + str(node.get("label", node["id"])),
                _secondary(node),
            ),
            _style(
                html=1,
                whiteSpace="wrap",
                align="center",
                verticalAlign="middle",
                fontColor=theme["foreground"],
                fontSize=11,
                fontStyle=1,
                fillColor=node.get("color", fills[layer % len(fills)]),
                strokeColor=node.get("accent", accents[layer % len(accents)]),
                strokeWidth=1.2,
                shadow=1,
                raw=shape_style,
            ),
            1,
            box.x,
            box.y,
            box.width,
            box.height,
        )
    for index, edge in enumerate(spec.get("edges", [])):
        points = _route_points(geometry, index)
        if points is None:
            from .routing import route_orthogonal

            rectangles = {key: {"id": key, **vars(box)} for key, box in boxes.items()}
            points = route_orthogonal(
                rectangles[edge["from"]], rectangles[edge["to"]], rectangles.values(),
                source_port=edge.get("source_port"), target_port=edge.get("target_port"),
                source_anchor=float(edge.get("from_anchor", 0.5)),
                target_anchor=float(edge.get("to_anchor", 0.5)),
            )
        _edge(
            root,
            f"edge-{edge.get('id', index)}",
            _relationship_label(edge),
            f"node-{edge['from']}",
            f"node-{edge['to']}",
            theme,
            dashed=edge.get("style") == "dashed",
            relationship=edge,
            source_box=vars(boxes[edge["from"]]),
            target_box=vars(boxes[edge["to"]]),
            points=points,
        )


def _vertex(
    root: ET.Element,
    cell_id: str,
    value: str,
    style: str,
    parent: str | int,
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    cell = ET.SubElement(
        root,
        "mxCell",
        {
            "id": cell_id,
            "value": value,
            "style": style,
            "vertex": "1",
            "parent": str(parent),
        },
    )
    ET.SubElement(
        cell,
        "mxGeometry",
        {
            "x": _number(x),
            "y": _number(y),
            "width": _number(width),
            "height": _number(height),
            "as": "geometry",
        },
    )


def _edge(
    root: ET.Element,
    cell_id: str,
    value: str,
    source: str,
    target: str,
    theme: dict[str, Any],
    dashed: bool,
    relationship: dict[str, Any] | None = None,
    source_box: dict[str, Any] | None = None,
    target_box: dict[str, Any] | None = None,
    points: list[tuple[float, float]] | None = None,
) -> None:
    relationship = relationship or {}
    direction = relationship.get("direction", "forward")
    color = _relationship_color(relationship, theme)
    ports = _connection_ports(relationship, source_box, target_box)
    if points and source_box and target_box:
        for prefix, point, box in (("exit", points[0], source_box), ("entry", points[-1], target_box)):
            ports[f"{prefix}X"] = round((point[0] - box["x"]) / box["width"], 12)
            ports[f"{prefix}Y"] = round((point[1] - box["y"]) / box["height"], 12)
    cell = ET.SubElement(
        root,
        "mxCell",
        {
            "id": cell_id,
            "value": value,
            "style": _style(
                html=1,
                edgeStyle="orthogonalEdgeStyle",
                rounded=1,
                orthogonalLoop=1,
                jettySize="auto",
                startArrow="block" if direction == "bidirectional" else "none",
                endArrow="none" if direction == "none" else "block",
                startFill=1,
                endFill=1,
                strokeColor=color,
                fontColor=color,
                fontSize=10,
                dashed=1 if dashed else 0,
                **ports,
            ),
            "edge": "1",
            "parent": "1",
            "source": source,
            "target": target,
        },
    )
    for key in ("kind", "status", "state", "direction", "source_port", "target_port", "from_anchor", "to_anchor"):
        if key in relationship:
            cell.set(key, str(relationship[key]))
    edge_geometry = ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
    if points and len(points) > 2:
        waypoints = ET.SubElement(edge_geometry, "Array", {"as": "points"})
        for x, y in points[1:-1]:
            ET.SubElement(waypoints, "mxPoint", {"x": _number(x), "y": _number(y)})


def _route_points(geometry: list[dict[str, Any]] | None, index: int) -> list[tuple[float, float]] | None:
    edges = getattr(geometry, "edges", [])
    return edges[index].get("points") if index < len(edges) else None


def _secondary(item: dict[str, Any]) -> str:
    return " · ".join(
        str(value) for value in (
            item.get("subtitle", item.get("technology")),
            item.get("status"),
            item.get("state"),
        ) if value is not None and str(value).strip()
    )


def _relationship_label(relationship: dict[str, Any]) -> str:
    label = str(relationship.get("label", "")).strip()
    return _html_text(label, _secondary(relationship))


def _relationship_color(relationship: dict[str, Any], theme: dict[str, Any]) -> str:
    if relationship.get("color"):
        return str(relationship["color"])
    index = {"control": 0, "runtime": 1, "evidence": 2, "state": 3, "feedback": 4}.get(
        relationship.get("kind")
    )
    accents = theme.get("accents", [])
    return accents[index % len(accents)] if index is not None and accents else theme.get("edge", theme["foreground"])


def _connection_ports(
    relationship: dict[str, Any],
    source: dict[str, Any] | None,
    target: dict[str, Any] | None,
) -> dict[str, Any]:
    source_port, target_port = None, None
    if source and target:
        from .routing import default_ports

        source_port, target_port = default_ports(
            {"id": source.get("id", source.get("node_id", "_source")), **source},
            {"id": target.get("id", target.get("node_id", "_target")), **target},
        )
    result: dict[str, Any] = {}
    for prefix, port, anchor in (
        ("exit", relationship.get("source_port", source_port), relationship.get("from_anchor", 0.5)),
        ("entry", relationship.get("target_port", target_port), relationship.get("to_anchor", 0.5)),
    ):
        if port:
            x, y = {"N": (anchor, 0), "S": (anchor, 1), "E": (1, anchor), "W": (0, anchor)}[port]
            result.update({f"{prefix}X": x, f"{prefix}Y": y, f"{prefix}Dx": 0, f"{prefix}Dy": 0})
    return result


def _style(**values: Any) -> str:
    raw = str(values.pop("raw", "")).strip(";")
    parts = [f"{key}={value}" for key, value in values.items()]
    if raw:
        parts.append(raw)
    return ";".join(parts) + ";"


def _html_text(
    primary: Any, secondary: Any | None, secondary_color: str = "#70798A",
    *, inline: bool = False, secondary_size: float = 9,
) -> str:
    safe_primary = html.escape(str(primary))
    if secondary is None or not str(secondary).strip():
        return f"<b>{safe_primary}</b>"
    safe_secondary = html.escape(str(secondary))
    separator = " &nbsp; " if inline else "<br>"
    return (
        f"<b>{safe_primary}</b>{separator}"
        f'<font color="{html.escape(secondary_color)}" style="font-size:{secondary_size}px">{safe_secondary}</font>'
    )


def _icon_prefix(icon: Any | None) -> str:
    return ""


def _tone_index(value: Any) -> int:
    return {
        "blue": 0,
        "green": 1,
        "orange": 2,
        "purple": 3,
        "rose": 4,
        "teal": 5,
    }.get(str(value or "neutral"), 0)


def _drawio_dimension(stage: dict[str, Any]) -> str:
    if stage.get("type", "tensor") != "tensor":
        return str(stage.get("dimension", stage.get("subtitle", "")))
    spatial = stage.get("spatial")
    channels = stage.get("channels")
    if isinstance(spatial, list) and len(spatial) == 2:
        return f"{spatial[0]}×{spatial[1]}×{channels}"
    if spatial is not None and channels is not None:
        return f"{spatial}×{spatial}×{channels}"
    return ""


def _number(value: float) -> str:
    return f"{float(value):.2f}".rstrip("0").rstrip(".")


def _write(path: Path, root: ET.Element) -> None:
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(
        path,
        encoding="utf-8",
        xml_declaration=True,
        short_empty_elements=True,
    )
