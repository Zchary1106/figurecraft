"""Opt-in, deterministic graph ranking, crossing reduction, and endpoint spacing."""
from __future__ import annotations

import heapq
import json
import math
from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from .routing import default_ports

MAX_ORDERING_PASSES = 8
Node = dict[str, Any]
Layers = dict[int, list[Node]]


def assign_layers(nodes: list[Node], edges: list[Node]) -> dict[str, int]:
    """Rank the SCC condensation DAG, keeping every explicit layer unchanged.

    Unpinned SCCs occupy one rank after their latest predecessor. A pinned SCC
    places its unpinned members at its earliest pin; successors follow its latest
    actual rank. Pins override forward-edge preferences, including contradictory
    pins and feedback edges, rather than being silently shifted or discarded.
    """
    ids = sorted(node["id"] for node in nodes)
    if len(set(ids)) != len(ids):
        raise ValueError("Node IDs must be unique")
    successors = {node_id: set() for node_id in ids}
    predecessors = {node_id: set() for node_id in ids}
    explicit = {}
    for node in nodes:
        value = node.get("layer")
        if value is not None:
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or isinstance(value, float) and not math.isfinite(value)
                    or value < 0 or int(value) != value):
                raise ValueError("Explicit layers must be nonnegative integers")
            explicit[node["id"]] = int(value)
    for edge in edges:
        source, target = edge["from"], edge["to"]
        if source not in successors or target not in successors:
            raise ValueError("Edge endpoint is not a known node")
        successors[source].add(target)
        predecessors[target].add(source)

    # Iterative Kosaraju avoids recursion limits on long chains and large cycles.
    seen, finish = set(), []
    for root in ids:
        if root in seen:
            continue
        seen.add(root)
        stack = [(root, iter(sorted(successors[root])))]
        while stack:
            node_id, children = stack[-1]
            child = next(children, None)
            if child is None:
                finish.append(node_id)
                stack.pop()
            elif child not in seen:
                seen.add(child)
                stack.append((child, iter(sorted(successors[child]))))
    components, owner = [], {}
    for root in reversed(finish):
        if root in owner:
            continue
        component = []
        owner[root] = len(components)
        stack = [root]
        while stack:
            node_id = stack.pop()
            component.append(node_id)
            for parent in sorted(predecessors[node_id], reverse=True):
                if parent not in owner:
                    owner[parent] = len(components)
                    stack.append(parent)
        components.append(sorted(component))
    outgoing = [set() for _ in components]
    incoming = [set() for _ in components]
    for source in ids:
        for target in successors[source]:
            a, b = owner[source], owner[target]
            if a != b:
                outgoing[a].add(b)
                incoming[b].add(a)
    indegree = [len(parents) for parents in incoming]
    queue = [index for index, degree in enumerate(indegree) if not degree]
    heapq.heapify(queue)
    result, latest = {}, {}
    while queue:
        index = heapq.heappop(queue)
        members = components[index]
        pins = [explicit[node_id] for node_id in members if node_id in explicit]
        rank = min(pins) if pins else max((latest[parent] + 1 for parent in incoming[index]), default=0)
        for node_id in members:
            result[node_id] = explicit.get(node_id, rank)
        latest[index] = max(result[node_id] for node_id in members)
        for child in sorted(outgoing[index]):
            indegree[child] -= 1
            if not indegree[child]:
                heapq.heappush(queue, child)
    return {node_id: result[node_id] for node_id in ids}


def _positions(by_layer: Layers) -> dict[str, tuple[int, float]]:
    return {node["id"]: (layer, index - (len(items) - 1) / 2)
            for layer, items in by_layer.items() for index, node in enumerate(items)}


def count_crossings(by_layer: Layers, edges: list[Node]) -> int:
    """Count proper crossings of ideal straight rank-to-rank segments.

    Ranks are centered in each layer, matching equal-sized layered nodes. Sparse
    layer numbers are compressed to consecutive positions without changing their
    order. Long and reverse edges participate; same-layer edges, endpoint touches,
    and coincident parallel edges do not. This is a layout metric, not a claim
    about crossings in the final obstacle-routed geometry.
    """
    positions = _positions(by_layer)
    layer_positions = {layer: index for index, layer in enumerate(sorted(by_layer))}
    segments = []
    for edge in edges:
        start, end = positions[edge["from"]], positions[edge["to"]]
        if start[0] == end[0]:
            continue
        if start[0] > end[0]:
            start, end = end, start
        start, end = (layer_positions[start[0]], start[1]), (layer_positions[end[0]], end[1])
        segments.append((start, end))
    count = 0
    for index, (a, b) in enumerate(segments):
        for c, d in segments[index + 1:]:
            left, right = max(a[0], c[0]), min(b[0], d[0])
            if left >= right:
                continue
            a_slope = (b[1] - a[1]) / (b[0] - a[0])
            c_slope = (d[1] - c[1]) / (d[0] - c[0])
            first = a[1] + (left - a[0]) * a_slope - c[1] - (left - c[0]) * c_slope
            last = a[1] + (right - a[0]) * a_slope - c[1] - (right - c[0]) * c_slope
            if first * last < -1e-12:
                count += 1
    return count


def _blocks(items: list[Node]) -> list[list[Node]]:
    blocks, groups = [], {}
    for node in items:
        group = node.get("group")
        if not group:
            blocks.append([node])
        elif group in groups:
            groups[group].append(node)
        else:
            block = [node]
            groups[group] = block
            blocks.append(block)
    return blocks


def order_layers(
    by_layer: Layers, edges: list[Node], *, max_passes: int = MAX_ORDERING_PASSES,
) -> Layers:
    """Use at most eight bidirectional barycenter sweeps to reduce crossings.

    Nodes never change layers. Groups form indivisible contiguous blocks, with
    member order optimized within each block. Only strictly improving moves are
    retained after initial group compaction (that required compaction can itself
    increase crossings). Input dictionaries and node objects are never mutated.
    """
    if isinstance(max_passes, bool) or not isinstance(max_passes, int) or not 0 <= max_passes <= MAX_ORDERING_PASSES:
        raise ValueError(f"max_passes must be an integer between 0 and {MAX_ORDERING_PASSES}")
    current = {layer: [node for block in _blocks(items) for node in block]
               for layer, items in sorted(by_layer.items())}
    neighbors = defaultdict(list)
    for edge in edges:
        source, target = edge["from"], edge["to"]
        if source != target:
            neighbors[source].append(target)
            neighbors[target].append(source)
    neighbors = {node_id: sorted(items) for node_id, items in neighbors.items()}
    score = count_crossings(current, edges)
    for _ in range(max_passes):
        improved = False
        for forward in (True, False):
            for layer in sorted(current, reverse=not forward):
                positions = _positions(current)

                def barycenter(node: Node) -> float:
                    related = [positions[node_id][1] for node_id in neighbors.get(node["id"], [])
                               if (positions[node_id][0] < layer if forward else positions[node_id][0] > layer)]
                    return sum(related) / len(related) if related else positions[node["id"]][1]

                blocks = [sorted(block, key=barycenter) for block in _blocks(current[layer])]
                blocks.sort(key=lambda block: sum(barycenter(node) for node in block) / len(block))
                candidate = [node for block in blocks for node in block]
                if candidate == current[layer]:
                    continue
                previous = current[layer]
                current[layer] = candidate
                candidate_score = count_crossings(current, edges)
                if candidate_score < score:
                    score, improved = candidate_score, True
                else:
                    current[layer] = previous
        if not improved or not score:
            break
    return current


def edge_ports(edges: list[Node], boxes: Any, direction: str = "LR") -> list[Node]:
    """Return edge copies with resolved ports and spaced fractional anchors.

    Accept either an ID-to-rectangle/Box mapping or an iterable of rectangles.
    Each node side allocates incoming and outgoing endpoints together. Automatic
    anchors follow the opposite endpoint's cross-axis position; explicit anchors
    reserve the nearest slot and are never changed. Existing explicit ports also
    remain unchanged. Nonrectangular boundaries retain center anchors where
    fractional rectangle anchors would not touch the rendered shape. Identical
    ID-less parallel edges are interchangeable.
    """
    if direction not in {"LR", "RL", "TB", "BT"}:
        raise ValueError("direction must be LR, RL, TB, or BT")
    rects = {}
    values = boxes.items() if isinstance(boxes, Mapping) else ((box["id"], box) for box in boxes)
    for node_id, box in values:
        rects[node_id] = {"id": node_id,
                         "shape": box.get("shape") if isinstance(box, Mapping) else getattr(box, "shape", None), **{
            key: box[key] if isinstance(box, Mapping) else getattr(box, key)
            for key in ("x", "y", "width", "height")}}
    result = [dict(edge) for edge in edges]
    endpoints = defaultdict(list)
    for index, edge in enumerate(result):
        source, target = rects[edge["from"]], rects[edge["to"]]
        dx = target["x"] + target["width"] / 2 - source["x"] - source["width"] / 2
        dy = target["y"] + target["height"] / 2 - source["y"] - source["height"] / 2
        ports = default_ports(source, target)
        if source["id"] != target["id"]:
            if direction in {"LR", "RL"} and abs(dx) > 1e-9:
                ports = ("E", "W") if dx > 0 else ("W", "E")
            elif direction in {"TB", "BT"} and abs(dy) > 1e-9:
                ports = ("S", "N") if dy > 0 else ("N", "S")
        identity = json.dumps(edges[index], sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        for node, opposite, port_key, anchor_key, port in (
            (source, target, "source_port", "from_anchor", ports[0]),
            (target, source, "target_port", "to_anchor", ports[1]),
        ):
            if edge.get(port_key) is None:
                edge[port_key] = port
            side = edge[port_key]
            if side not in {"N", "E", "S", "W"}:
                raise ValueError(f"Unknown port: {side}")
            center_only = (node["shape"] in {"ellipse", "diamond", "operation"}
                           or node["shape"] in {"database", "document"} and side in {"N", "S"})
            if center_only and anchor_key not in edge:
                edge[anchor_key] = .5
            if anchor_key in edge:
                anchor = edge[anchor_key]
                if (isinstance(anchor, bool) or not isinstance(anchor, (int, float))
                        or not math.isfinite(anchor) or not 0 <= anchor <= 1):
                    raise ValueError("Port anchor must be between 0 and 1")
            cross = (opposite["y"] + opposite["height"] / 2 if side in {"E", "W"}
                     else opposite["x"] + opposite["width"] / 2)
            endpoints[node["id"], side].append((cross, identity, anchor_key, index))
    for attached in endpoints.values():
        attached.sort()
        slots = [(index + 1) / (len(attached) + 1) for index in range(len(attached))]
        explicit = [endpoint for endpoint in attached if endpoint[2] in result[endpoint[3]]]
        for _, _, anchor_key, index in explicit:
            anchor = result[index][anchor_key]
            slots.remove(min(slots, key=lambda slot: (abs(slot - anchor), slot)))
        automatic = [endpoint for endpoint in attached if endpoint[2] not in result[endpoint[3]]]
        for (_, _, anchor_key, index), anchor in zip(automatic, slots, strict=True):
            result[index][anchor_key] = anchor
    return result
