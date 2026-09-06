"""Deterministic orthogonal routing and collision-aware relationship labels."""
from __future__ import annotations

import heapq
import math
from typing import Any, Iterable

Point = tuple[float, float]
Rect = dict[str, Any]
VECTORS = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}


class Geometry(list):
    """A node list with optional rendering metadata (JSON list contract unchanged)."""

    def __init__(self, values: Iterable[Rect] = ()) -> None:
        super().__init__(values)
        self.edges: list[Rect] = []
        self.labels: list[Rect] = []
        self.routing_nodes: list[Rect] = []


def overlaps(a: Rect, b: Rect, padding: float = 0) -> bool:
    return (
        a["x"] < b["x"] + b["width"] + padding
        and b["x"] < a["x"] + a["width"] + padding
        and a["y"] < b["y"] + b["height"] + padding
        and b["y"] < a["y"] + a["height"] + padding
    )


def segment_intersects_rect(a: Point, b: Point, rect: Rect) -> bool:
    """Test the open rectangle interior, including non-axis-aligned lint inputs."""
    low, high = 0.0, 1.0
    for start, end, minimum, maximum in (
        (a[0], b[0], rect["x"], rect["x"] + rect["width"]),
        (a[1], b[1], rect["y"], rect["y"] + rect["height"]),
    ):
        delta = end - start
        if abs(delta) < 1e-9:
            if not minimum + 1e-7 < start < maximum - 1e-7:
                return False
        else:
            t0, t1 = sorted(((minimum - start) / delta, (maximum - start) / delta))
            low, high = max(low, t0), min(high, t1)
    return high - low > 1e-7


def default_ports(source: Rect, target: Rect) -> tuple[str, str]:
    if source["id"] == target["id"]:
        return "E", "N"
    dx = target["x"] + target["width"] / 2 - source["x"] - source["width"] / 2
    dy = target["y"] + target["height"] / 2 - source["y"] - source["height"] / 2
    if abs(dx) >= abs(dy):
        return ("E", "W") if dx >= 0 else ("W", "E")
    return ("S", "N") if dy >= 0 else ("N", "S")


def port_point(rect: Rect, port: str, anchor: float = .5) -> Point:
    if port not in VECTORS:
        raise ValueError(f"Unknown port: {port}")
    if not 0 <= anchor <= 1:
        raise ValueError("Port anchor must be between 0 and 1")
    x, y, w, h = (rect[key] for key in ("x", "y", "width", "height"))
    return {"N": (x + w * anchor, y), "E": (x + w, y + h * anchor),
            "S": (x + w * anchor, y + h), "W": (x, y + h * anchor)}[port]


def _simplify(points: list[Point]) -> list[Point]:
    result: list[Point] = []
    for point in points:
        if result and point == result[-1]:
            continue
        while len(result) > 1:
            a, b = result[-2:]
            if ((a[0] == b[0] == point[0] and (b[1] - a[1]) * (point[1] - b[1]) >= 0)
                    or (a[1] == b[1] == point[1] and (b[0] - a[0]) * (point[0] - b[0]) >= 0)):
                result.pop()
            else:
                break
        result.append(point)
    return result


def _segment_contact(a: Point, b: Point, c: Point, d: Point) -> tuple[float, Point | None]:
    if a == b or c == d:
        return 0.0, None
    horizontal, other_horizontal = a[1] == b[1], c[1] == d[1]
    if horizontal == other_horizontal:
        axis = 0 if horizontal else 1
        if abs(a[1 - axis] - c[1 - axis]) > 1e-7:
            return 0.0, None
        length = min(max(a[axis], b[axis]), max(c[axis], d[axis])) - max(
            min(a[axis], b[axis]), min(c[axis], d[axis]))
        return max(0.0, length), None
    if not horizontal:
        a, b, c, d = c, d, a, b
    point = (c[0], a[1])
    if (min(a[0], b[0]) - 1e-7 <= point[0] <= max(a[0], b[0]) + 1e-7
            and min(c[1], d[1]) - 1e-7 <= point[1] <= max(c[1], d[1]) + 1e-7):
        return 0.0, point
    return 0.0, None


def _path_pair_congestion(first: list[Point], second: list[Point]) -> tuple[int, float]:
    contacts, overlap = set(), 0.0
    if len(first) < 2 or len(second) < 2:
        return 0, overlap
    shared_endpoints = {first[0], first[-1]} & {second[0], second[-1]}
    for a, b in zip(first, first[1:]):
        for c, d in zip(second, second[1:]):
            length, point = _segment_contact(a, b, c, d)
            overlap += length
            if point is not None and point not in shared_endpoints:
                contacts.add(point)
    return len(contacts), overlap


def path_congestion(paths: Iterable[Iterable[Point]]) -> dict[str, int | float]:
    """Measure actual orthogonal routes, not ideal graph ranks.

    Crossings include bend contacts, counted once per point per pair of paths,
    but exclude shared whole-path endpoints. Overlap length is the sum of
    positive-length shared runs for each pair. Both metrics are intentionally
    pairwise: three coincident routes count as three overlapping pairs.
    """
    values = [[tuple(point) for point in path] for path in paths]
    crossings, overlap = 0, 0.0
    for index, first in enumerate(values):
        for second in values[index + 1:]:
            count, length = _path_pair_congestion(first, second)
            crossings += count
            overlap += length
    return {"crossings": crossings, "overlap_length": overlap}


def route_orthogonal(
    source: Rect, target: Rect, obstacles: Iterable[Rect], *,
    source_port: str | None = None, target_port: str | None = None,
    source_anchor: float = .5, target_anchor: float = .5,
    clearance: float = 10.0,
    occupied_paths: Iterable[Iterable[Point]] | None = None,
) -> list[Point]:
    """Find a shortest rectilinear route with outward-facing endpoint stubs.

    Containers belong in obstacles only when they are actual endpoint objects
    (e.g. landscape zones), not when they decorate a group of child nodes.
    An impossible port or overlapping layout raises ValueError, never a
    collision-shaped fallback. Optional occupied paths add soft crossing and
    shared-trunk penalties; absent/empty paths retain the legacy routing policy.
    Explicit endpoint positions remain hard constraints.
    """
    rects = {rect["id"]: rect for rect in obstacles if not rect.get("container")}
    rects.update({source["id"]: source, target["id"]: target})
    defaults = default_ports(source, target)
    sp, tp = source_port or defaults[0], target_port or defaults[1]
    if source["id"] == target["id"] and sp == tp and source_anchor == target_anchor:
        source_anchor, target_anchor = .35, .65
    start, end = port_point(source, sp, source_anchor), port_point(target, tp, target_anchor)
    if clearance <= 0 or not math.isfinite(clearance):
        raise ValueError("Routing clearance must be positive and finite")
    # Narrow but valid corridors still need room on both sides.
    gap = clearance
    for a in rects.values():
        for b in rects.values():
            if a["id"] == b["id"]:
                continue
            for axis, size in (("x", "width"), ("y", "height")):
                separation = b[axis] - a[axis] - a[size]
                if separation > 0:
                    gap = min(gap, separation / 3)
    padding = max(0.01, gap)
    padded = [{**r, "x": r["x"] - padding, "y": r["y"] - padding,
               "width": r["width"] + 2 * padding, "height": r["height"] + 2 * padding}
              for r in rects.values()]
    sv, tv = VECTORS[sp], VECTORS[tp]
    first = (start[0] + sv[0] * padding, start[1] + sv[1] * padding)
    last = (end[0] + tv[0] * padding, end[1] + tv[1] * padding)
    for a, b, owner in ((start, first, source["id"]), (last, end, target["id"])):
        if any(segment_intersects_rect(a, b, r) for r in padded if r["id"] != owner):
            raise ValueError(f"Blocked routing port on {owner}")

    def clear(points: list[Point]) -> bool:
        return all(not segment_intersects_rect(a, b, r)
                   for a, b in zip(points, points[1:]) for r in padded)

    occupied = [[tuple(point) for point in path] for path in occupied_paths or ()]
    occupied = [path for path in occupied if len(path) > 1]

    def congestion(points: list[Point]) -> float:
        return sum(192 * count + 4 * length
                   for count, length in (_path_pair_congestion(points, path) for path in occupied))

    def route_cost(points: list[Point]) -> float:
        points = _simplify(points)
        return (sum(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in zip(points, points[1:]))
                + 16 * max(0, len(points) - 2) + congestion(points))

    mx, my = (first[0] + last[0]) / 2, (first[1] + last[1]) / 2
    candidates = [
        [first, (mx, first[1]), (mx, last[1]), last],
        [first, (first[0], my), (last[0], my), last],
    ]
    if sp in {"N", "S"}:
        candidates.reverse()
    clear_candidates = []
    for candidate in candidates:
        if clear(candidate):
            candidate = _simplify([start, *candidate, end])
            if not occupied or not congestion(candidate):
                return candidate
            clear_candidates.append(candidate)
    xs = {first[0], last[0], mx}
    ys = {first[1], last[1], my}
    for r in padded:
        xs.update((r["x"], r["x"] + r["width"]))
        ys.update((r["y"], r["y"] + r["height"]))
    if occupied:
        # Bounded extra tracks allow moving around existing trunks and their tips.
        for axis, coordinates, midpoint in ((0, xs, mx), (1, ys, my)):
            tracks = {point[axis] + offset for path in occupied for point in path
                      for offset in (-padding, padding)}
            coordinates.update(sorted(tracks - coordinates, key=lambda value: (abs(value - midpoint), value))[:32])
    xs, ys = sorted(xs), sorted(ys)
    origin = (xs.index(first[0]), ys.index(first[1]), -1)
    costs = {origin: 0.0}
    previous: dict[tuple, tuple] = {}
    queue = [(0.0, origin)]
    finish = None
    segment_costs = {}
    while queue:
        cost, state = heapq.heappop(queue)
        if cost != costs[state]:
            continue
        ix, iy, direction = state
        point = (xs[ix], ys[iy])
        if point == last:
            finish = state
            break
        for dx, dy, axis in ((-1, 0, 0), (1, 0, 0), (0, -1, 1), (0, 1, 1)):
            nx, ny = ix + dx, iy + dy
            if not (0 <= nx < len(xs) and 0 <= ny < len(ys)):
                continue
            neighbor = (xs[nx], ys[ny])
            if not clear([point, neighbor]):
                continue
            next_state = (nx, ny, axis)
            next_cost = cost + abs(neighbor[0] - point[0]) + abs(neighbor[1] - point[1])
            next_cost += 16 if direction not in {-1, axis} else 0
            if occupied:
                key = tuple(sorted((point, neighbor)))
                if key not in segment_costs:
                    segment_costs[key] = congestion([point, neighbor])
                next_cost += segment_costs[key]
            if next_cost < costs.get(next_state, math.inf):
                costs[next_state] = next_cost
                previous[next_state] = state
                heapq.heappush(queue, (next_cost, next_state))
    if finish is None:
        raise ValueError(f"No obstacle-free route from {source['id']} to {target['id']}")
    route = []
    while finish != origin:
        route.append((xs[finish[0]], ys[finish[1]]))
        finish = previous[finish]
    result = _simplify([start, first, *reversed(route), end])
    if occupied and clear_candidates:
        return min([*clear_candidates, result], key=route_cost)
    return result


def path_data(points: list[Point], *, radius: float = 0, obstacles: Iterable[Rect] = ()) -> str:
    """Round only corners whose complete quadratic control hull is obstacle-free."""
    if not math.isfinite(radius) or radius < 0:
        raise ValueError("Corner radius must be nonnegative and finite")
    if not radius or len(points) < 3:
        return " ".join(f"{'M' if i == 0 else 'L'} {x:.3f} {y:.3f}" for i, (x, y) in enumerate(points))
    blockers = [rect for rect in obstacles if not rect.get("container") and rect["width"] > 0 and rect["height"] > 0]
    result = [f"M {points[0][0]:.3f} {points[0][1]:.3f}"]
    for previous, corner, following in zip(points, points[1:], points[2:]):
        ax, ay = previous[0] - corner[0], previous[1] - corner[1]
        bx, by = following[0] - corner[0], following[1] - corner[1]
        before, after = math.hypot(ax, ay), math.hypot(bx, by)
        orthogonal = (ax == 0 or ay == 0) and (bx == 0 or by == 0) and ax * bx + ay * by == 0
        if not before or not after or not orthogonal:
            result.append(f"L {corner[0]:.3f} {corner[1]:.3f}")
            continue
        distance = min(radius, before / 2, after / 2)
        start = (round(corner[0] + ax / before * distance, 3), round(corner[1] + ay / before * distance, 3))
        end = (round(corner[0] + bx / after * distance, 3), round(corner[1] + by / after * distance, 3))
        control = (round(corner[0], 3), round(corner[1], 3))
        xs, ys = zip(start, control, end)
        hull = {"x": min(xs), "y": min(ys), "width": max(xs) - min(xs), "height": max(ys) - min(ys)}
        if start == control or end == control or any(overlaps(hull, rect, 1e-6) for rect in blockers):
            result.append(f"L {corner[0]:.3f} {corner[1]:.3f}")
            continue
        result.append(f"L {start[0]:.3f} {start[1]:.3f}")
        result.append(f"Q {control[0]:.3f} {control[1]:.3f} {end[0]:.3f} {end[1]:.3f}")
    result.append(f"L {points[-1][0]:.3f} {points[-1][1]:.3f}")
    return " ".join(result)


def place_label(
    points: list[Point], width: float, height: float,
    obstacles: Iterable[Rect], occupied: Iterable[Rect], *,
    preferred: Point | None = None,
) -> Rect:
    """Place a label near its route without covering nodes or earlier labels."""
    blockers = [r for r in obstacles if not r.get("container")] + list(occupied)
    segments = list(zip(points, points[1:]))
    if not segments:
        raise ValueError("A label needs a nonempty route")
    a, b = max(segments, key=lambda ab: abs(ab[1][0] - ab[0][0]) + abs(ab[1][1] - ab[0][1]))
    preferred = preferred or ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 - height / 2 - 3)
    candidates = [preferred]
    for a, b in segments:
        cx, cy = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        candidates.extend([(cx, cy - height / 2 - 3), (cx, cy + height / 2 + 3),
                           (cx - width / 2 - 3, cy), (cx + width / 2 + 3, cy)])
    xs, ys = {preferred[0], width / 2 + 4}, {preferred[1], height / 2 + 4}
    for r in blockers:
        xs.update((r["x"] - width / 2 - 4, r["x"] + r["width"] + width / 2 + 4))
        ys.update((r["y"] - height / 2 - 4, r["y"] + r["height"] + height / 2 + 4))
    candidates.extend((x, y) for x in sorted(xs) for y in sorted(ys))
    candidates.sort(key=lambda p: (abs(p[0] - preferred[0]) + abs(p[1] - preferred[1]), p[1], p[0]))
    for x, y in candidates:
        rect = {"x": x - width / 2, "y": y - height / 2, "width": width, "height": height}
        if rect["x"] >= 2 and rect["y"] >= 2 and not any(overlaps(rect, r, 3) for r in blockers):
            return rect
    raise ValueError("No collision-free relationship label position")


def label_leader(points: list[Point], label: Rect, obstacles: Iterable[Rect]) -> list[Point]:
    """Keep displaced labels visibly associated with their relationship."""
    cx, cy = label["x"] + label["width"] / 2, label["y"] + label["height"] / 2
    candidates = []
    for a, b in zip(points, points[1:]):
        inset_x = min(4, abs(b[0] - a[0]) / 2)
        inset_y = min(4, abs(b[1] - a[1]) / 2)
        x = min(max(cx, min(a[0], b[0]) + inset_x), max(a[0], b[0]) - inset_x)
        y = min(max(cy, min(a[1], b[1]) + inset_y), max(a[1], b[1]) - inset_y)
        target = (min(max(x, label["x"]), label["x"] + label["width"]),
                  min(max(y, label["y"]), label["y"] + label["height"]))
        candidates.append((abs(x - target[0]) + abs(y - target[1]), (x, y), target))
    distance, start, end = min(candidates)
    if distance <= 8:
        return []
    source = {"id": "_label_leader_start", "x": start[0], "y": start[1], "width": 0, "height": 0}
    target = {"id": "_label_leader_end", "x": end[0], "y": end[1], "width": 0, "height": 0}
    return route_orthogonal(source, target, obstacles, clearance=2)
