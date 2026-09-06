from __future__ import annotations

import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/figurecraft"
sys.path.insert(0, str(SKILL / "scripts"))

from figurelib.diagrams import _layout_swimlane, render_diagram
from figurelib.lint import lint_manifest, lint_svg
from figurelib.routing import label_leader, overlaps, path_data, place_label, route_orthogonal, segment_intersects_rect


def rect(node_id: str, x: float, y: float = 70, width: float = 100, height: float = 60) -> dict:
    return {"id": node_id, "x": x, "y": y, "width": width, "height": height}


def sample_path(path: str) -> list[tuple[float, float]]:
    tokens = iter(path.split())
    samples = []
    for command in tokens:
        point = (float(next(tokens)), float(next(tokens)))
        if command == "M":
            samples.append(point)
            continue
        start = samples[-1]
        if command == "Q":
            end = (float(next(tokens)), float(next(tokens)))
            for step in range(1, 101):
                t = step / 100
                samples.append(tuple((1 - t) ** 2 * start[axis] + 2 * t * (1 - t) * point[axis] + t * t * end[axis] for axis in (0, 1)))
        elif command == "L":
            samples.extend(tuple(start[axis] + (point[axis] - start[axis]) * step / 100 for axis in (0, 1)) for step in range(1, 101))
        else:
            raise AssertionError(f"Unexpected SVG command: {command}")
    return samples


class RoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.theme = json.loads((SKILL / "assets/themes/paper-light.json").read_text())

    def lint(self, geometry: list, engine: dict) -> dict:
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".routing-test-") as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps({"kind": "diagram.architecture", "geometry": geometry, "engine": engine}))
            return lint_manifest(path)

    def assert_clear(self, points: list, boxes: list) -> None:
        self.assertGreaterEqual(len(points), 2)
        for a, b in zip(points, points[1:]):
            self.assertTrue(a[0] == b[0] or a[1] == b[1])
            for box in boxes:
                self.assertFalse(segment_intersects_rect(a, b, box), (a, b, box))

    def test_skip_layer_obstacle_and_quality_gate(self) -> None:
        boxes = [rect("a", 50), rect("b", 220), rect("c", 390)]
        old_route = [(150, 100), (390, 100)]
        self.assertFalse(self.lint(boxes, {"edges": [{"id": "ac", "from": "a", "to": "c", "points": old_route}]})["passed"])
        route = route_orthogonal(boxes[0], boxes[2], boxes)
        self.assert_clear(route, boxes)
        self.assertTrue(self.lint(boxes, {"edges": [{"id": "ac", "from": "a", "to": "c", "points": route}]})["passed"])
        self.assertEqual(route, route_orthogonal(boxes[0], boxes[2], boxes))

    def test_adjacent_stays_straight(self) -> None:
        a, b = rect("a", 50), rect("b", 220)
        self.assertEqual([(150, 100), (220, 100)], route_orthogonal(a, b, [a, b]))

    def test_curved_path_uses_safe_quadratic_corners(self) -> None:
        boxes = [rect("a", 50), rect("b", 220), rect("c", 390)]
        points = route_orthogonal(boxes[0], boxes[2], boxes)
        curved = path_data(points, radius=8, obstacles=boxes)
        self.assertIn("Q ", curved)
        samples = sample_path(curved)
        self.assertEqual(points[0], samples[0])
        self.assertEqual(points[-1], samples[-1])
        for box in boxes:
            self.assertFalse(any(segment_intersects_rect(a, b, box) for a, b in zip(samples, samples[1:])), box)

    def test_curved_corner_rejects_intersecting_control_hull(self) -> None:
        points = [(0, 20), (20, 20), (20, 0)]
        blocker = rect("corner-obstacle", 14, 14, 4, 4)
        self.assertEqual(path_data(points), path_data(points, radius=8, obstacles=[blocker]))
        self.assertIn("Q ", path_data(points, radius=8, obstacles=[{**blocker, "container": True}]))

    def test_curve_radius_is_bounded_and_straight_paths_are_unchanged(self) -> None:
        points = [(0, 0), (10, 0), (10, 6)]
        self.assertEqual("M 0.000 0.000 L 7.000 0.000 Q 10.000 0.000 10.000 3.000 L 10.000 6.000",
                         path_data(points, radius=100))
        straight = [(0, 0), (10, 0), (20, 0)]
        self.assertEqual(path_data(straight), path_data(straight, radius=8))
        self.assertEqual("M 0.000 0.000 L 10.000 0.000 L 10.000 6.000", path_data(points))
        for invalid in (-1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                path_data(points, radius=invalid)

    def test_generic_and_landscape_curved_edges_preserve_route_metadata(self) -> None:
        specs = [
            {"kind": "diagram.architecture",
             "nodes": [{"id": node, "layer": index} for index, node in enumerate("abc")],
             "edges": [{"from": "a", "to": "c", "style": "curved"}]},
            {"kind": "diagram.system-landscape",
             "zones": [{"id": node, "title": node, "row": 0, "column": index * 4, "span": 4, "sections": []}
                       for index, node in enumerate("abc")],
             "connections": [{"from": "a", "to": "c", "style": "curved"}]},
        ]
        for spec in specs:
            with self.subTest(kind=spec["kind"]), tempfile.TemporaryDirectory(dir=ROOT, prefix=".routing-test-") as directory:
                path = Path(directory)
                _, engine, _ = render_diagram(spec, path, self.theme)
                edge = next(element for element in ET.parse(path / "figure.svg").iter()
                            if element.get("data-edge-id") == "a--c")
                self.assertIn("Q ", edge.get("d"))
                samples = sample_path(edge.get("d"))
                for box in engine["routing_nodes"]:
                    # SVG endpoints are serialized to 0.001 px; ignore only that boundary rounding.
                    interior = {**box, "x": box["x"] + .001, "y": box["y"] + .001,
                                "width": box["width"] - .002, "height": box["height"] - .002}
                    self.assertFalse(any(segment_intersects_rect(a, b, interior) for a, b in zip(samples, samples[1:])), box)
                points = engine["edges"][0]["points"]
                key = "connections" if "connections" in spec else "edges"
                spec[key][0]["style"] = "orthogonal"
                _, straight_engine, _ = render_diagram(spec, path, self.theme)
                straight = next(element for element in ET.parse(path / "figure.svg").iter()
                                if element.get("data-edge-id") == "a--c")
                self.assertEqual(points, straight_engine["edges"][0]["points"])
                self.assertEqual(path_data(points), straight.get("d"))

    def test_vertical_skip_and_fractional_anchors(self) -> None:
        a, b, c = rect("a", 80, 50), rect("b", 80, 190), rect("c", 80, 330)
        route = route_orthogonal(a, c, [a, b, c], source_port="S", target_port="N",
                                 source_anchor=.2, target_anchor=.8)
        self.assertEqual((100, 110), route[0])
        self.assertEqual((160, 330), route[-1])
        self.assert_clear(route, [a, b, c])

    def test_reverse_self_and_all_explicit_port_pairs(self) -> None:
        a, b, c = rect("a", 50), rect("b", 220), rect("c", 390)
        self.assert_clear(route_orthogonal(c, a, [a, b, c]), [a, b, c])
        for source_port in ("N", "E", "S", "W"):
            for target_port in ("N", "E", "S", "W"):
                with self.subTest(source=source_port, target=target_port):
                    for target in (a, c):
                        route = route_orthogonal(a, target, [a, b, c], source_port=source_port, target_port=target_port)
                        self.assert_clear(route, [a, b, c])
                        vectors = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}
                        for first, second, port in ((route[0], route[1], source_port), (route[-1], route[-2], target_port)):
                            dx, dy = vectors[port]
                            self.assertGreater((second[0] - first[0]) * dx + (second[1] - first[1]) * dy, 0)

    def test_label_placement_and_quality_gates(self) -> None:
        a, b = rect("a", 50), rect("b", 220)
        points = route_orthogonal(a, b, [a, b])
        labels = []
        for index in range(5):
            label = {"id": str(index), **place_label(points, 160, 22, [a, b], labels)}
            self.assertFalse(any(overlaps(label, box) for box in [a, b, *labels]))
            labels.append(label)
        self.assertTrue(self.lint([a, b], {"labels": labels})["passed"])
        self.assertFalse(self.lint([a, b], {"labels": [{"id": "bad", **a}]})["passed"])
        self.assertFalse(self.lint([], {"labels": labels + [labels[0]]})["passed"])

    def test_containers_are_not_unrelated_obstacles(self) -> None:
        a, b = rect("a", 50), rect("b", 220)
        container = {**rect("group", 20, 20, 350, 200), "container": True}
        route = route_orthogonal(a, b, [a, b, container])
        result = self.lint([a, b, container], {"edges": [{"id": "ab", "from": "a", "to": "b", "points": route}]})
        self.assertTrue(result["passed"], result)

    def test_wide_swimlane_columns(self) -> None:
        spec = {"lanes": [{"id": "lane"}], "nodes": [
            {"id": "a", "lane": "lane", "layer": 0, "visual_width": 450},
            {"id": "b", "lane": "lane", "layer": 1, "visual_width": 360},
        ]}
        boxes, width, _, _ = _layout_swimlane(spec)
        self.assertGreaterEqual(boxes["b"].x - boxes["a"].x - boxes["a"].width, 44)
        self.assertGreater(width, boxes["b"].x + boxes["b"].width)

    def test_group_headings_are_measured_routing_obstacles(self) -> None:
        spec = {"kind": "diagram.architecture", "layout": {"direction": "TB"},
                "nodes": [{"id": "a", "layer": 0, "group": "Group Alpha"},
                          {"id": "b", "layer": 1.0, "group": "Group Beta"}],
                "edges": [{"from": "a", "to": "b", "source_port": "S", "target_port": "N"}]}
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".routing-test-") as directory:
            _, engine, geometry = render_diagram(spec, Path(directory), self.theme)
            self.assertEqual(2, len(geometry))
            route = engine["edges"][0]["points"]
            headings = [box for box in engine["routing_nodes"] if box["id"].startswith("_group-heading-")]
            self.assertEqual(2, len(headings))
            for box in headings:
                self.assertFalse(any(segment_intersects_rect(a, b, box) for a, b in zip(route, route[1:])))
            self.assertTrue(any(segment_intersects_rect(route[0], route[-1], box) for box in headings))
            self.assertGreater(route[1][1], route[0][1])
            self.assertLess(route[-2][1], route[-1][1])
            self.assertFalse(any(box.get("container") for box in engine["routing_nodes"]))
            self.assertTrue(self.lint(geometry, engine)["passed"])
            texts = {element.text: element for element in ET.parse(Path(directory) / "figure.svg").iter()
                     if element.get("data-text-box") and element.text in {"Group Alpha", "Group Beta"}}
            for name, box in zip(("Group Alpha", "Group Beta"), headings):
                bounds = [float(value) for value in texts[name].get("data-text-box").split(",")]
                for key, value in zip(("x", "y", "width", "height"), bounds):
                    self.assertAlmostEqual(box[key], value, delta=.01)

    def test_renderer_exports_routes_and_label_bounds(self) -> None:
        spec = {"kind": "diagram.architecture", "nodes": [
            {"id": node, "layer": layer} for layer, node in enumerate("abc")
        ], "edges": [{"from": "a", "to": "c", "label": "Skip middle"},
                     {"from": "a", "to": "c", "label": "Another relationship"},
                     {"from": "c", "to": "a"}, {"from": "a", "to": "a"}]}
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".routing-test-") as directory:
            _, engine, geometry = render_diagram(spec, Path(directory), self.theme)
            self.assertEqual(3, len(geometry))
            self.assertEqual(4, len(engine["edges"]))
            self.assertEqual(2, len(engine["labels"]))
            result = self.lint(geometry, engine)
            self.assertTrue(result["passed"], result)

    def test_displaced_label_has_obstacle_free_leader(self) -> None:
        a, b = rect("a", 50), rect("b", 220)
        route = route_orthogonal(a, b, [a, b])
        label = rect("label", 170, 220, 100, 22)
        leader = label_leader(route, label, [a, b])
        self.assertGreaterEqual(len(leader), 2)
        self.assert_clear(leader, [a, b])

    def test_landscape_skip_zone_routes(self) -> None:
        spec = {"kind": "diagram.system-landscape", "zones": [
            {"id": node, "title": node, "row": 0, "column": i * 4, "span": 4, "sections": []}
            for i, node in enumerate("abc")
        ], "connections": [{"from": "a", "to": "c", "label": "skip"},
                           {"from": "c", "to": "a", "label": "return"},
                           {"from": "a", "to": "a", "label": "self"}]}
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".routing-test-") as directory:
            _, engine, geometry = render_diagram(spec, Path(directory), self.theme)
            result = self.lint(geometry, engine)
            self.assertTrue(result["passed"], result)
            self.assertEqual(3, len(engine["edges"]))

    def test_blocked_port_is_explicit_error(self) -> None:
        a, b = rect("a", 50), rect("b", 120)
        with self.assertRaisesRegex(ValueError, "Blocked routing port|No obstacle-free"):
            route_orthogonal(a, b, [a, b], source_port="E")

    def test_text_metadata_quality_gate(self) -> None:
        def check(bounds: str, container: str, color: str = "#111111") -> list[str]:
            with tempfile.TemporaryDirectory(dir=ROOT, prefix=".routing-test-") as directory:
                path = Path(directory) / "figure.svg"
                path.write_text(
                    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100">'
                    '<title>Test</title><desc>Text checks</desc>'
                    f'<text data-text-box="{bounds}" data-text-container="{container}" '
                    f'fill="{color}" data-text-background="#FFFFFF">Label</text></svg>'
                )
                return lint_svg(path)[0]
        self.assertEqual([], check("10,10,80,20", "5,5,100,40"))
        self.assertTrue(any("outside container" in error for error in check("10,10,120,20", "5,5,100,40")))
        self.assertTrue(any("outside SVG canvas" in error for error in check("190,10,80,20", "180,5,100,40")))
        self.assertTrue(any("Insufficient text contrast" in error for error in check("10,10,80,20", "5,5,100,40", "#EEEEEE")))
        self.assertTrue(any("Invalid text geometry" in error for error in check("nan,10,80,20", "5,5,100,40")))
        self.assertTrue(any("Invalid text contrast colors" in error for error in check("10,10,80,20", "5,5,100,40", "invalid")))


if __name__ == "__main__":
    unittest.main()
