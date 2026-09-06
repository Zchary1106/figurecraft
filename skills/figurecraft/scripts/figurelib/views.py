"""Source-preserving, bounded diagram views; relationships always carry evidence."""
from __future__ import annotations

from copy import deepcopy
from typing import Any


MAX_NODES = 6


def _chunks(items: list[Any], limit: int = MAX_NODES) -> list[list[Any]]:
    count = max(1, (len(items) + limit - 1) // limit)
    size = max(1, (len(items) + count - 1) // count)
    return [items[i:i + size] for i in range(0, len(items), size)]


def _node(item: dict, path: str, *, label: str | None = None) -> dict:
    result = {key: deepcopy(item[key]) for key in
              ("id", "label", "subtitle", "shape", "group", "lane", "role", "icon", "technology", "step",
               "color", "accent", "fill",
               "input_shape", "output_shape", "in_features", "out_features", "in_channels", "out_channels")
              if key in item}
    result["id"] = str(item.get("id", path))
    result["label"] = str(label if label is not None else item.get("label", item.get("title", result["id"])))
    dimensions = [f"{key}: " + ("×".join(map(str, item[key])) if isinstance(item[key], list) else str(item[key]))
                  for key in ("input_shape", "output_shape", "in_features", "out_features", "in_channels", "out_channels")
                  if key in item]
    if dimensions:
        result["subtitle"] = "\n".join(filter(None, [result.get("subtitle", result.get("technology", "")), *dimensions]))
    return result


def _relation(edge: dict, path: str, basis: str = "explicit") -> dict:
    return {**deepcopy(edge), "source_ref": path, "basis": basis}


def _ordered_edges(nodes: list[dict], path: str, basis: str) -> list[dict]:
    return [_relation({"from": a["id"], "to": b["id"]}, f"{path}/{i}", basis)
            for i, (a, b) in enumerate(zip(nodes, nodes[1:]))]


def plan_views(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Return reference, overview(s), and detail plans without mutating ``spec``.

    Each plan includes a renderable ``spec``, exact ``full_source``, source object
    references, visible-edge evidence, boundary edges, and explicit omissions.
    Anonymous objects use JSON pointers; grammar-only endpoints are explicitly
    tagged as derivations rather than being presented as original source IDs.
    """
    source = deepcopy(spec)
    kind = spec.get("kind", "")
    nodes: list[dict] = []
    relations: list[dict] = []
    records: dict[str, dict] = {}
    groups: list[tuple[str, list[dict]]] = []
    overview: list[dict] = []
    overview_relations: list[dict] | None = None
    notes: list[str] = []
    narrow_medium = spec.get("layout", {}).get("medium") in {"paper-single", "slide"}
    node_limit = 3 if narrow_medium else MAX_NODES

    def register(item: dict, path: str, *, label: str | None = None) -> dict:
        node = _node(item, path, label=label)
        if node["id"] in records:
            raise ValueError(f"Cannot partition duplicate source identifier: {node['id']}")
        records[node["id"]] = {"source_id": item.get("id"), "source_ref": path,
                               "source": deepcopy(item)}
        return node

    def contents(items: list, path: str, group: str) -> list[dict]:
        result = []
        for index, value in enumerate(items):
            item = value if isinstance(value, dict) else {"label": str(value)}
            node = register(item, f"{path}/{index}")
            node["group"] = group
            result.append(node)
        return result

    if kind == "diagram.system-landscape":
        for zi, zone in enumerate(spec["zones"]):
            zone_node = register(zone, f"/zones/{zi}")
            overview.append(zone_node)
            nodes.append(zone_node)
            for si, section in enumerate(zone.get("sections", [])):
                path = f"/zones/{zi}/sections/{si}"
                section_node = register(section, path)
                section_node["group"] = zone["id"]
                nodes.append(section_node)
                items = contents(section.get("items", []), f"{path}/items", section["title"])
                nodes.extend(items)
                groups.append((f"{zone['title']} / {section['title']}", items or [section_node]))
            if not zone.get("sections"):
                groups.append((zone["title"], [zone_node]))
        relations = [_relation(edge, f"/connections/{i}") for i, edge in enumerate(spec.get("connections", []))]
        notes.append("Zone connections are source macro connections. Section membership is not an item-to-item dependency.")
    elif kind == "diagram.research-framework" and spec.get("framework_stages"):
        for i, stage in enumerate(spec["framework_stages"]):
            node = register(stage, f"/framework_stages/{i}")
            overview.append(node)
            nodes.append(node)
            items = contents(stage["items"], f"/framework_stages/{i}/items", stage["title"])
            nodes.extend(items)
            groups.append((stage["title"], items))
        relations = _ordered_edges(overview, "/framework_stages", "ordered framework stages")
        if spec.get("outcome"):
            outcome = register(spec["outcome"], "/outcome")
            relations.append(_relation({"from": overview[-1]["id"], "to": outcome["id"]},
                                       "/outcome", "framework outcome"))
            overview.append(outcome)
            nodes.append(outcome)
        if spec.get("feedback"):
            relations.append(_relation(spec["feedback"], "/feedback"))
        notes.append("Stage order is the framework grammar; items within a stage have no inferred dependency edges.")
    elif kind == "diagram.framework-matrix":
        phases = {phase["id"]: i for i, phase in enumerate(spec["phases"])}
        terminals = []
        track_for = {}
        for i, track in enumerate(spec["tracks"]):
            track_node = register(track, f"/tracks/{i}")
            overview.append(track_node)
            nodes.append(track_node)
            cells = contents(track.get("cells", []), f"/tracks/{i}/cells", track["title"])
            cells.sort(key=lambda n: phases[records[n["id"]]["source"]["phase"]])
            nodes.extend(cells)
            for cell in cells:
                track_for[cell["id"]] = track["id"]
            relations.extend(_ordered_edges(cells, f"/tracks/{i}/cells", "phase-ordered track progression"))
            groups.append((track["title"], cells))
            if cells:
                terminals.append(cells[-1])
        integration = register(spec.get("integration", {"label": "Evidence integration"}), "/integration")
        outcome = register(spec.get("outcome", {"label": "Research outcome"}), "/outcome")
        for field, node in (("integration", integration), ("outcome", outcome)):
            if field not in spec:
                records[node["id"]].update(source_ref="", source=deepcopy(source),
                                           derivation=f"source renderer's default matrix {field}")
        nodes.extend([integration, outcome])
        overview.extend([integration, outcome])
        for terminal in terminals:
            relations.append(_relation({"from": terminal["id"], "to": integration["id"]},
                                       records[terminal["id"]]["source_ref"], "matrix terminal through evidence bus"))
        relations.append(_relation({"from": integration["id"], "to": outcome["id"]},
                                   "/outcome", "matrix integration to outcome"))
        relations.extend(_relation(edge, f"/cross_links/{i}") for i, edge in enumerate(spec.get("cross_links", [])))
        overview_relations = []
        for edge in relations:
            a, b = track_for.get(edge["from"], edge["from"]), track_for.get(edge["to"], edge["to"])
            if a != b:
                overview_relations.append({**deepcopy(edge), "from": a, "to": b,
                                           "original_endpoints": [edge["from"], edge["to"]]})
        notes.append("Overview track connections aggregate actual cell paths; original endpoints remain in edge evidence.")
        if "integration" not in spec or "outcome" not in spec:
            notes.append("Missing integration/outcome labels use the source renderer's matrix grammar defaults.")
    elif kind == "diagram.cnn-architecture":
        for i, stage in enumerate(spec["stages"]):
            node = register(stage, f"/stages/{i}", label=stage["title"])
            if "fill" in stage:
                node["color"] = stage["fill"]
            if "color" in stage:
                node["accent"] = stage["color"]
            facts = [str(stage.get("label", "")), str(stage.get("operation", ""))]
            if stage.get("spatial") is not None:
                spatial = stage["spatial"]
                dimensions = "×".join(map(str, spatial)) if isinstance(spatial, list) else str(spatial)
                facts.append(f"{dimensions} · C={stage.get('channels')}")
            if "repeat" in stage:
                facts.append(f"×{stage['repeat']}")
            if stage.get("subtitle"):
                facts.append(stage["subtitle"])
            node["subtitle"] = "\n".join(dict.fromkeys(f for f in facts if f))
            overview.append(node)
            nodes.append(node)
        relations = _ordered_edges(overview, "/stages", "ordered CNN stages")
        for i, edge in enumerate(relations):
            if spec["stages"][i + 1].get("transition"):
                edge["label"] = spec["stages"][i + 1]["transition"]
        detail = spec.get("block_detail")
        if detail:
            block_nodes = [register({"label": "Input"}, "/block_detail/input")]
            steps = contents(detail["steps"], "/block_detail/steps", detail.get("title", "Block detail"))
            block_nodes.extend(steps)
            block_edges = _ordered_edges(block_nodes, "/block_detail/steps", "ordered block steps")
            residual = detail.get("residual", True)
            if residual:
                add = register({"label": "Add"}, "/block_detail/add")
                block_nodes.append(add)
                block_edges.append(_relation({"from": steps[-1]["id"], "to": add["id"]},
                                             "/block_detail/residual", "residual addition"))
                shortcut = detail.get("shortcut")
                if isinstance(shortcut, dict):
                    projection = register(shortcut, "/block_detail/shortcut",
                                          label=shortcut.get("label", "Projection"))
                    block_nodes.append(projection)
                    block_edges.extend([
                        _relation({"from": block_nodes[0]["id"], "to": projection["id"]},
                                  "/block_detail/shortcut", "projection shortcut"),
                        _relation({"from": projection["id"], "to": add["id"]},
                                  "/block_detail/residual", "residual addition"),
                    ])
                else:
                    block_edges.append(_relation({"from": block_nodes[0]["id"], "to": add["id"],
                                                   "label": "identity", "style": "dashed"},
                                                  "/block_detail/residual", "identity residual"))
                last = add
            else:
                last = steps[-1]
            output = register({"label": detail.get("output", "ReLU")}, "/block_detail/output")
            block_nodes.append(output)
            block_edges.append(_relation({"from": last["id"], "to": output["id"]},
                                         "/block_detail/output", "block output"))
            for role in ("input", "add", "output"):
                identifier = f"/block_detail/{role}"
                if identifier in records:
                    records[identifier].update(source_ref="/block_detail", source=deepcopy(detail),
                                               derivation=f"block grammar {role}; not an original source ID")
            nodes.extend(block_nodes)
            relations.extend(block_edges)
            groups.append((detail.get("title", "Block detail"), block_nodes))
            notes.append("The block detail is representative only; no block internals are inferred for individual stages.")
            if "residual" not in detail or "output" not in detail:
                notes.append("Unspecified residual/output use the existing block grammar defaults: residual=true, output=ReLU.")
    elif kind.startswith("diagram.") and spec.get("nodes"):
        nodes = [register(item, f"/nodes/{i}") for i, item in enumerate(spec["nodes"])]
        relations = [_relation(edge, f"/edges/{i}") for i, edge in enumerate(spec.get("edges", []))]
        by_group: dict[str, list] = {}
        for node in nodes:
            group = str(node.get("group", node.get("lane", "Nodes")))
            by_group.setdefault(group, []).append(node)
        groups = list(by_group.items())
        overview = nodes if len(nodes) <= MAX_NODES else [items[0] for items in by_group.values()][:MAX_NODES]
        if len(overview) < 3 and len(nodes) > MAX_NODES:
            overview = nodes[:MAX_NODES]
        notes.append("The overview is a source-node subset, not a complete dependency graph; omitted crossings are listed explicitly.")
    else:
        raise ValueError(f"Automatic view partitioning is unsupported for {kind}; use render for a single figure.")

    known = {n["id"] for n in nodes}
    for edge in relations:
        if edge["from"] not in known or edge["to"] not in known:
            raise ValueError(f"Cannot partition unknown relation endpoint: {edge['from']} → {edge['to']}")
    plans: list[dict] = []
    all_ids = list(records)

    def plan(role: str, title: str, selected: list[dict], available: list[dict] | None = None) -> None:
        ids = {node["id"] for node in selected}
        pool = relations if available is None else available
        internal = [e for e in pool if e["from"] in ids and e["to"] in ids]
        boundary = [e for e in relations if (e["from"] in ids) != (e["to"] in ids)]
        ancestors = {parent for parent, record in records.items() if parent not in ids and not record.get("derivation") and any(
            records[node_id]["source_ref"].startswith(record["source_ref"] + "/") for node_id in ids)}
        context_boundary = [e for e in relations if e not in boundary and
                            (e["from"] in ancestors or e["to"] in ancestors)]
        # A single visible crossing can have multiple source witnesses.
        visible: dict[tuple, dict] = {}
        for edge in internal:
            key = (edge["from"], edge["to"], edge.get("label", ""), edge.get("direction", "forward"),
                   edge.get("style", ""), edge.get("technology", ""), edge.get("status", ""),
                   edge.get("kind", ""), edge.get("color", ""))
            if key not in visible:
                allowed = ("from", "to", "label", "style", "direction", "technology", "status", "kind", "color")
                visible[key] = {k: deepcopy(edge[k]) for k in allowed if k in edge}
                visible[key]["id"] = f"view-edge-{len(visible) + 1}"
                visible[key]["source_relations"] = []
            visible[key]["source_relations"].append(deepcopy(edge))
        style = deepcopy(spec.get("style", {"preset": "paper-light"}))
        overrides = style.setdefault("overrides", {})
        target_font = 16 if narrow_medium else 12
        overrides["font_size"] = max(overrides.get("font_size", target_font), target_font)
        compact = {
            "version": spec.get("version", "1.0"), "kind": "diagram.architecture",
            "title": title, "nodes": deepcopy(selected),
            "edges": [{k: v for k, v in e.items() if k != "source_relations"} for e in visible.values()],
            "style": style,
            "layout": {"direction": "TB", "density": "compact", "margin": 24,
                       "medium": deepcopy(spec.get("layout", {}).get("medium", "web"))},
            "output": deepcopy(spec.get("output", {"primary": "svg"})),
            "assumptions": deepcopy(spec.get("assumptions", [])) + notes,
        }
        for key in ("language", "provenance"):
            if key in spec:
                compact[key] = deepcopy(spec[key])
        for key in ("width_mm", "height_mm", "min_font_pt", "min_font_px"):
            if key in spec.get("layout", {}):
                compact["layout"][key] = spec["layout"][key]
        # A narrow, ordered reading layout does not assert new graph edges.
        for index, node in enumerate(compact["nodes"]):
            node["layer"] = index if internal or narrow_medium else index // 2
            group = node.pop("group", None)
            group_title = title.split(" · part ")[0]
            if group and group != group_title and not group_title.endswith(" / " + group):
                node["subtitle"] = "\n".join(filter(None, [f"Group: {group}", node.get("subtitle", "")]))
            if narrow_medium:
                if node.get("step"):
                    node["label"] = f'{node.pop("step")} · {node["label"]}'
        omitted = [node_id for node_id in all_ids if node_id not in ids]
        omissions = ["Native positions, tensor geometry, and decorative containers are replaced by a compact reading layout; source palette and semantic colors are retained."]
        omissions.append("Source grouping is retained in titles/annotations instead of numbered decorative containers.")
        if omitted:
            omissions.append("Other source objects are omitted from this view; see omitted_source_ids and the full-source reference.")
        omissions.append("Fields not displayed in this view are listed in omitted_source_fields and retained in source_objects/full_source.")
        omissions.append("The original caption, notes, and tables remain in the full-source reference. Source font size is never reduced.")
        displayed = {"id", "label", "title", "subtitle", "group", "lane", "shape", "role", "icon",
                     "technology", "color", "accent", "fill", "input_shape", "output_shape",
                     "in_features", "out_features", "in_channels", "out_channels"}
        planned = {
            "id": f"{role}-{sum(p['role'] == role for p in plans) + 1:02d}", "role": role,
            "title": title, "spec": compact, "source_ids": [n["id"] for n in selected],
            "original_source_ids": [records[n["id"]]["source_id"] for n in selected
                                    if records[n["id"]]["source_id"] is not None],
            "source_objects": {n["id"]: deepcopy(records[n["id"]]) for n in selected},
            "source_edges": deepcopy(internal), "rendered_edges": list(visible.values()),
            "boundary_edges": deepcopy(boundary), "omitted_source_ids": omitted,
            "context_boundary_edges": deepcopy(context_boundary),
            "omitted_source_fields": {n["id"]: sorted(set(records[n["id"]]["source"]) - displayed)
                                      for n in selected},
            "omitted_root_fields": [key for key in ("caption", "note", "stage_table", "layout", "view")
                                    if key in spec],
            "omitted_relations": [deepcopy(e) for e in relations if e not in internal],
            "view_omissions": omissions, "full_source": deepcopy(source),
        }
        compact["view"] = {
            "type": role, "source_kind": kind,
            **{key: deepcopy(planned[key]) for key in
               ("source_ids", "original_source_ids", "source_objects", "boundary_edges",
                "context_boundary_edges", "view_omissions", "omitted_source_ids",
                "omitted_source_fields", "omitted_root_fields", "omitted_relations", "full_source")},
        }
        plans.append(planned)

    for i, chunk in enumerate(_chunks(overview, node_limit)):
        plan("overview", "Overview" + (f" · part {i + 1}" if len(overview) > node_limit else ""),
             chunk, overview_relations)
    for title, items in groups:
        for i, chunk in enumerate(_chunks(items, node_limit)):
            plan("detail", title + (f" · part {i + 1}" if len(items) > node_limit else ""), chunk)
    reference = deepcopy(source)
    reference.setdefault("layout", {})["medium"] = "web"
    for key in ("width_mm", "height_mm", "min_font_pt", "min_font_px"):
        reference["layout"].pop(key, None)
    plans.append({
        "id": "reference", "role": "reference", "title": "Full source · web reference",
        "spec": reference, "source_ids": all_ids, "source_objects": records,
        "original_source_ids": [r["source_id"] for r in records.values() if r["source_id"] is not None],
        "source_edges": deepcopy(relations), "rendered_edges": [],
        "boundary_edges": [], "context_boundary_edges": [], "omitted_source_ids": [], "omitted_relations": [],
        "view_omissions": ["Medium is web for reference viewing, not a print-publication claim."],
        "full_source": source,
    })
    return plans
