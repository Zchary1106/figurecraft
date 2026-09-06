from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def validate_spec(spec: dict[str, Any], skill_root: Path) -> list[str]:
    schema_path = skill_root / "assets/schema/figure-spec.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        from jsonschema import Draft202012Validator, FormatChecker
    except ImportError as exc:
        raise RuntimeError("Validation requires jsonschema") from exc

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = [
        f"{_path(error.absolute_path)}: {error.message}"
        for error in sorted(validator.iter_errors(spec), key=lambda item: _path(item.path))
    ]
    errors.extend(_finite_errors(spec))
    if errors:
        return errors
    errors.extend(_semantic_errors(spec))
    return errors


def _semantic_errors(spec: dict[str, Any]) -> list[str]:
    kind = spec.get("kind", "")
    errors: list[str] = []
    if kind.startswith("chart."):
        data = spec.get("data", {})
        if "columns" in data:
            errors.extend(validate_chart_data(spec, data["columns"]))
        if kind == "chart.heatmap" and "matrix" in data:
            errors.extend(_matrix_errors(data["matrix"], data))
        bins = spec.get("layout", {}).get("bins")
        if isinstance(bins, list) and any(a >= b for a, b in zip(bins, bins[1:])):
            errors.append("$.layout.bins: edges must be strictly increasing")
        if kind == "chart.errorbar":
            uncertainty = spec.get("semantics", {}).get("uncertainty")
            if not uncertainty:
                errors.append("$.semantics.uncertainty: required for error bars")
            if not spec.get("series"):
                errors.append("$.series: error bars require explicit series with error fields")
            for index, series in enumerate(spec.get("series", [])):
                if "error" not in series:
                    errors.append(f"$.series[{index}].error: required for error bars")
        for index, series in enumerate(spec.get("series", [])):
            has_lower = "lower" in series
            has_upper = "upper" in series
            if has_lower != has_upper:
                errors.append(
                    f"$.series[{index}]: uncertainty bands require both lower and upper"
                )
            if has_lower and has_upper and not spec.get("semantics", {}).get("uncertainty"):
                errors.append("$.semantics.uncertainty: required for uncertainty bands")

    if kind.startswith("diagram."):
        nodes = spec.get("nodes", [])
        node_ids = [node.get("id") for node in nodes]
        if any(not value for value in node_ids):
            errors.append("$.nodes: every node requires a non-empty id")
        duplicates = sorted({value for value in node_ids if node_ids.count(value) > 1})
        if duplicates:
            errors.append(f"$.nodes: duplicate ids: {', '.join(duplicates)}")
        known = set(node_ids)
        for index, edge in enumerate(spec.get("edges", [])):
            for endpoint in ("from", "to"):
                if edge.get(endpoint) not in known:
                    errors.append(
                        f"$.edges[{index}].{endpoint}: unknown node {edge.get(endpoint)!r}"
                    )
            for port_name in ("source_port", "target_port"):
                if edge.get(port_name) not in {None, "N", "E", "S", "W"}:
                    errors.append(
                        f"$.edges[{index}].{port_name}: must be N, E, S, or W"
                    )
        if kind == "diagram.swimlane":
            lane_ids = {lane.get("id") for lane in spec.get("lanes", [])}
            if not lane_ids:
                errors.append("$.lanes: swimlane diagrams require lanes")
            for index, node in enumerate(nodes):
                if node.get("lane") not in lane_ids:
                    errors.append(
                        f"$.nodes[{index}].lane: must reference an existing lane"
                    )
        if kind == "diagram.neural-network":
            lookup = {node["id"]: node for node in nodes}
            for index, edge in enumerate(spec.get("edges", [])):
                if edge["from"] in lookup and edge["to"] in lookup:
                    errors.extend(_dimension_errors(
                        lookup[edge["from"]], lookup[edge["to"]], f"$.edges[{index}]"
                    ))
    if kind == "diagram.system-landscape":
        zones = spec.get("zones", [])
        zone_ids = [zone.get("id") for zone in zones]
        if any(not value for value in zone_ids):
            errors.append("$.zones: every zone requires a non-empty id")
        duplicates = sorted({value for value in zone_ids if zone_ids.count(value) > 1})
        if duplicates:
            errors.append(f"$.zones: duplicate ids: {', '.join(duplicates)}")
        known_zones = set(zone_ids)
        for zone_index, zone in enumerate(zones):
            if not zone.get("title"):
                errors.append(f"$.zones[{zone_index}].title: required")
            for section_index, section in enumerate(zone.get("sections", [])):
                if not section.get("title"):
                    errors.append(
                        f"$.zones[{zone_index}].sections[{section_index}].title: required"
                    )
                if int(section.get("columns", 1)) < 1:
                    errors.append(
                        f"$.zones[{zone_index}].sections[{section_index}].columns: must be positive"
                    )
        for index, connection in enumerate(spec.get("connections", [])):
            for endpoint in ("from", "to"):
                if connection.get(endpoint) not in known_zones:
                    errors.append(
                        f"$.connections[{index}].{endpoint}: unknown zone "
                        f"{connection.get(endpoint)!r}"
                    )
    if kind == "diagram.cnn-architecture":
        stages = spec.get("stages", [])
        stage_ids = [stage.get("id") for stage in stages]
        if len(stages) < 2:
            errors.append("$.stages: CNN architecture requires at least two stages")
        if any(not value for value in stage_ids):
            errors.append("$.stages: every stage requires a non-empty id")
        duplicates = sorted(
            {value for value in stage_ids if stage_ids.count(value) > 1}
        )
        if duplicates:
            errors.append(f"$.stages: duplicate ids: {', '.join(duplicates)}")
        for index, stage in enumerate(stages):
            if not stage.get("title"):
                errors.append(f"$.stages[{index}].title: required")
            if int(stage.get("repeat", 1)) < 1:
                errors.append(f"$.stages[{index}].repeat: must be positive")
            if stage.get("type", "tensor") == "tensor":
                spatial = stage.get("spatial")
                channels = stage.get("channels")
                values = spatial if isinstance(spatial, list) else [spatial]
                if not values or any(
                    not isinstance(value, (int, float)) or value <= 0
                    for value in values
                ):
                    errors.append(
                        f"$.stages[{index}].spatial: must contain positive dimensions"
                    )
                if not isinstance(channels, (int, float)) or channels <= 0:
                    errors.append(
                        f"$.stages[{index}].channels: must be positive"
                    )
        for index in range(1, len(stages)):
            errors.extend(_dimension_errors(stages[index - 1], stages[index], f"$.stages[{index}]"))
    if kind == "diagram.research-framework":
        framework_stages = spec.get("framework_stages")
        if framework_stages is None and not spec.get("nodes"):
            errors.append(
                "$: research framework requires nodes or framework_stages"
            )
        if framework_stages is not None:
            if not framework_stages:
                errors.append("$.framework_stages: must not be empty")
            stage_ids = [stage.get("id") for stage in framework_stages]
            if any(not value for value in stage_ids):
                errors.append(
                    "$.framework_stages: every stage requires a non-empty id"
                )
            duplicates = sorted(
                {value for value in stage_ids if stage_ids.count(value) > 1}
            )
            if duplicates:
                errors.append(
                    f"$.framework_stages: duplicate ids: {', '.join(duplicates)}"
                )
            for index, stage in enumerate(framework_stages):
                if not stage.get("title"):
                    errors.append(
                        f"$.framework_stages[{index}].title: required"
                    )
                if not stage.get("items"):
                    errors.append(
                        f"$.framework_stages[{index}].items: must not be empty"
                    )
            feedback = spec.get("feedback", {})
            for endpoint in ("from", "to"):
                if endpoint in feedback and feedback[endpoint] not in stage_ids:
                    errors.append(f"$.feedback.{endpoint}: unknown framework stage {feedback[endpoint]!r}")
    if kind == "diagram.framework-matrix":
        phases = spec.get("phases", [])
        tracks = spec.get("tracks", [])
        phase_ids = [phase.get("id") for phase in phases]
        track_ids = [track.get("id") for track in tracks]
        if len(phases) < 2:
            errors.append("$.phases: matrix requires at least two phases")
        if len(tracks) < 2:
            errors.append("$.tracks: matrix requires at least two tracks")
        if any(not value for value in phase_ids):
            errors.append("$.phases: every phase requires a non-empty id")
        if any(not value for value in track_ids):
            errors.append("$.tracks: every track requires a non-empty id")
        known_phases = set(phase_ids)
        for name, values in (("phases", phase_ids), ("tracks", track_ids)):
            if len(values) != len(set(values)):
                errors.append(f"$.{name}: duplicate ids")
        cell_ids: list[str] = []
        for track_index, track in enumerate(tracks):
            if not track.get("title"):
                errors.append(f"$.tracks[{track_index}].title: required")
            occupied: set[str] = set()
            for cell_index, cell in enumerate(track.get("cells", [])):
                if cell["phase"] in occupied:
                    errors.append(f"$.tracks[{track_index}].cells[{cell_index}].phase: duplicate phase in track")
                occupied.add(cell["phase"])
                cell_id = cell.get("id")
                if not cell_id:
                    errors.append(
                        f"$.tracks[{track_index}].cells[{cell_index}].id: required"
                    )
                else:
                    cell_ids.append(cell_id)
                if cell.get("phase") not in known_phases:
                    errors.append(
                        f"$.tracks[{track_index}].cells[{cell_index}].phase: "
                        "must reference an existing phase"
                    )
        duplicates = sorted(
            {value for value in cell_ids if cell_ids.count(value) > 1}
        )
        if duplicates:
            errors.append(f"$.tracks: duplicate cell ids: {', '.join(duplicates)}")
        known_cells = set(cell_ids)
        for index, link in enumerate(spec.get("cross_links", [])):
            for endpoint in ("from", "to"):
                if link.get(endpoint) not in known_cells:
                    errors.append(
                        f"$.cross_links[{index}].{endpoint}: unknown cell "
                        f"{link.get(endpoint)!r}"
                    )

    if kind == "project.gantt":
        import datetime as dt

        task_ids = {task.get("id") for task in spec.get("tasks", []) if task.get("id")}
        ids = [task["id"] for task in spec["tasks"] if "id" in task]
        if len(ids) != len(task_ids):
            errors.append("$.tasks: duplicate ids")
        graph: dict[str, list[str]] = {}
        for index, task in enumerate(spec.get("tasks", [])):
            try:
                start = dt.date.fromisoformat(task["start"])
                end = dt.date.fromisoformat(task["end"])
                if end < start:
                    errors.append(f"$.tasks[{index}]: end precedes start")
            except (KeyError, TypeError, ValueError):
                errors.append(f"$.tasks[{index}]: start and end must be ISO dates")
            dependency = task.get("depends_on")
            dependencies = [dependency] if isinstance(dependency, str) else dependency or []
            if task.get("id"):
                graph[task["id"]] = dependencies
            for item in dependencies:
                if item not in task_ids:
                    errors.append(
                        f"$.tasks[{index}].depends_on: unknown task {item!r}"
                    )
        pending = {key: set(values) & task_ids for key, values in graph.items()}
        while pending:
            ready = {key for key, values in pending.items() if not values}
            if not ready:
                errors.append("$.tasks: dependency cycle")
                break
            pending = {key: values - ready for key, values in pending.items() if key not in ready}
    return errors


def _finite_errors(value: Any, path: str = "$") -> list[str]:
    if isinstance(value, float) and not math.isfinite(value):
        return [f"{path}: must be finite"]
    if isinstance(value, dict):
        return [error for key, item in value.items() for error in _finite_errors(item, f"{path}.{key}")]
    if isinstance(value, list):
        return [error for index, item in enumerate(value) for error in _finite_errors(item, f"{path}[{index}]")]
    return []


def _numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and (
        not isinstance(value, float) or math.isfinite(value)
    )


def validate_chart_data(spec: dict[str, Any], columns: dict[str, list[Any]]) -> list[str]:
    """Validate resolved columns as well as inline data, before plotting."""
    errors: list[str] = []
    if not columns or any(not isinstance(values, list) or not values for values in columns.values()):
        return ["$.data.columns: requires non-empty arrays"]
    kind = spec["kind"]
    if kind not in {"chart.histogram", "chart.box"} and len({len(values) for values in columns.values()}) > 1:
        errors.append("$.data.columns: all inline columns must have equal length")
    if kind == "chart.heatmap":
        return errors + _matrix_errors(list(columns.values()), spec.get("data", {}))
    items = spec.get("series")
    if not items:
        keys = list(columns)
        if kind in {"chart.histogram", "chart.box"}:
            items = [{"field": key} for key in (keys[:1] if kind == "chart.histogram" else keys)]
        elif len(keys) < 2:
            return errors + ["$.data.columns: chart requires at least two columns"]
        else:
            items = [{"x": keys[0], "y": key} for key in keys[1:]]
    for index, item in enumerate(items):
        for field in ("x", "y", "field", "lower", "upper", "error"):
            if field not in item:
                continue
            name = item[field]
            if name not in columns:
                errors.append(f"$.series[{index}].{field}: unknown data field {name!r}")
                continue
            values = columns[name]
            numeric = field != "x" or kind == "chart.scatter"
            if numeric and not all(_numeric(value) for value in values):
                errors.append(f"$.data.columns.{name}: must contain finite numeric values")
            elif field == "x" and not all(_numeric(value) or isinstance(value, str) for value in values):
                errors.append(f"$.data.columns.{name}: must contain numeric or categorical values")
            if field == "error" and all(_numeric(value) for value in values) and any(value < 0 for value in values):
                errors.append(f"$.data.columns.{name}: error magnitudes must be non-negative")
        lower, upper = columns.get(item.get("lower")), columns.get(item.get("upper"))
        if lower is not None and upper is not None and all(_numeric(value) for value in lower + upper):
            if any(low > high for low, high in zip(lower, upper)):
                errors.append(f"$.series[{index}]: lower uncertainty bounds must not exceed upper bounds")
        if kind == "chart.bar" and item.get("x") in columns and items[0].get("x") in columns:
            if columns[item["x"]] != columns[items[0]["x"]]:
                errors.append(f"$.series[{index}].x: grouped and stacked bars require matching categories")
    return errors


def _matrix_errors(matrix: list[list[Any]], data: dict[str, Any]) -> list[str]:
    errors = []
    if not matrix or not matrix[0] or len({len(row) for row in matrix}) > 1:
        return ["$.data.matrix: must be a non-empty rectangular matrix"]
    if not all(_numeric(value) for row in matrix for value in row):
        errors.append("$.data.matrix: must contain finite numeric values")
    for name, count in (("row_labels", len(matrix)), ("column_labels", len(matrix[0]))):
        if name in data and len(data[name]) != count:
            errors.append(f"$.data.{name}: label count must match matrix dimensions")
    return errors


def _dimension_errors(source: dict[str, Any], target: dict[str, Any], path: str) -> list[str]:
    errors = []
    for output, input_ in (("output_shape", "input_shape"), ("out_features", "in_features"), ("out_channels", "in_channels")):
        left, right = source.get(output), target.get(input_)
        if left is None or right is None:
            continue
        if isinstance(left, list) and isinstance(right, list):
            mismatch = len(left) != len(right) or any(
                _numeric(a) and _numeric(b) and a != b
                for a, b in zip(left, right)
            )
        else:
            mismatch = left != right
        if mismatch:
            errors.append(f"{path}: explicit {output} and {input_} dimensions do not match")
    return errors


def _path(parts: Any) -> str:
    result = "$"
    for part in parts:
        result += f"[{part}]" if isinstance(part, int) else f".{part}"
    return result
