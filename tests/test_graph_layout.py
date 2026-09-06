from __future__ import annotations

import copy
import itertools
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/figurecraft/scripts"))

from figurelib.graph_layout import assign_layers, count_crossings, edge_ports, order_layers
from figurelib.routing import path_congestion, port_point, route_orthogonal, segment_intersects_rect


def nodes(ids: str) -> list[dict]:
    return [{"id": node_id} for node_id in ids]


def edge(source: str, target: str, **extra) -> dict:
    return {"from": source, "to": target, **extra}


def rect(node_id: str, x: float, y: float) -> dict:
    return {"id": node_id, "x": x, "y": y, "width": 100, "height": 60}


class GraphLayerTests(unittest.TestCase):
    def test_crossed_layers_improve_without_changing_inputs(self) -> None:
        layers = {0: nodes("abc"), 1: nodes("xyz")}
        edges = [edge("a", "z"), edge("b", "y"), edge("c", "x")]
        before = copy.deepcopy((layers, edges))
        ordered = order_layers(layers, edges)
        self.assertEqual(3, count_crossings(layers, edges))
        self.assertEqual(0, count_crossings(ordered, edges))
        self.assertEqual(before, (layers, edges))
        self.assertIsNot(ordered[0], layers[0])
        for layer, items in ordered.items():
            self.assertEqual({id(node) for node in layers[layer]}, {id(node) for node in items})

    def test_order_is_deterministic_for_permuted_edges(self) -> None:
        layers = {0: nodes("abc"), 1: nodes("xyz"), 3: nodes("uvw")}
        edges = [edge("a", "z"), edge("b", "y"), edge("c", "x"), edge("y", "u"), edge("z", "w")]
        expected = order_layers(layers, edges)
        for permutation in itertools.permutations(edges):
            self.assertEqual(expected, order_layers(layers, list(permutation)))

    def test_group_blocks_and_member_order_are_optimized(self) -> None:
        layers = {0: nodes("abcd"), 1: [
            {"id": "w", "group": "one"}, {"id": "x", "group": "two"},
            {"id": "y", "group": "one"}, {"id": "z", "group": "two"}]}
        edges = [edge("a", "z"), edge("b", "x"), edge("c", "y"), edge("d", "w")]
        ordered = order_layers(layers, edges)
        self.assertLess(count_crossings(ordered, edges), count_crossings(layers, edges))
        for group in ("one", "two"):
            indexes = [index for index, node in enumerate(ordered[1]) if node["group"] == group]
            self.assertEqual(list(range(min(indexes), max(indexes) + 1)), indexes)

    def test_long_reverse_parallel_and_self_edges_in_metric(self) -> None:
        layers = {0: nodes("ab"), 2: nodes("xy")}
        edges = [edge("a", "y"), edge("x", "b")]
        self.assertEqual(1, count_crossings(layers, edges))
        self.assertEqual(0, count_crossings(order_layers(layers, edges), edges))
        self.assertEqual(0, count_crossings(layers, [edge("a", "a"), edge("a", "b"),
                                                   edge("a", "y"), edge("a", "y"), edge("y", "a")]))
        self.assertEqual(2, count_crossings(layers, edges + [edge("a", "y")]))

    def test_metric_includes_partially_overlapping_spans(self) -> None:
        layers = {0: nodes("ab"), 1: nodes("cd"), 2: nodes("ef"), 3: nodes("gh")}
        self.assertEqual(1, count_crossings(layers, [edge("a", "f"), edge("d", "g")]))

    def test_empty_disconnected_and_bounded_passes(self) -> None:
        self.assertEqual({}, order_layers({}, []))
        layers = {3: nodes("abc"), 8: []}
        self.assertEqual(layers, order_layers(layers, []))
        self.assertEqual(layers, order_layers(layers, [], max_passes=0))
        for value in (-1, 9, 1.5, True):
            with self.assertRaises(ValueError):
                order_layers(layers, [], max_passes=value)

    def test_cycles_are_condensed_before_ranking_successors(self) -> None:
        graph = nodes("abcdef")
        edges = [edge("a", "b"), edge("b", "c"), edge("c", "b"), edge("c", "d"),
                 edge("e", "e"), edge("c", "d")]
        expected = {"a": 0, "b": 1, "c": 1, "d": 2, "e": 0, "f": 0}
        self.assertEqual(expected, assign_layers(graph, edges))
        self.assertEqual(expected, assign_layers(list(reversed(graph)), list(reversed(edges))))

    def test_partial_pins_are_exact_even_with_feedback(self) -> None:
        graph = [{"id": "a", "layer": 4}, {"id": "b"}, {"id": "c", "layer": 1}, {"id": "d"}]
        edges = [edge("a", "b"), edge("b", "c"), edge("c", "d")]
        self.assertEqual({"a": 4, "b": 5, "c": 1, "d": 2}, assign_layers(graph, edges))

    def test_pins_inside_cycle_and_successor_constraints(self) -> None:
        graph = [{"id": "a", "layer": 2.0}, {"id": "b"}, {"id": "c", "layer": 7}, {"id": "d"}]
        edges = [edge("a", "b"), edge("b", "c"), edge("c", "a"), edge("b", "d")]
        self.assertEqual({"a": 2, "b": 2, "c": 7, "d": 8}, assign_layers(graph, edges))

    def test_large_chain_and_cycle_do_not_recurse(self) -> None:
        graph = [{"id": str(index)} for index in range(1200)]
        edges = [edge(str(index), str(index + 1)) for index in range(1199)]
        self.assertEqual(1199, assign_layers(graph, edges)["1199"])
        self.assertEqual({0}, set(assign_layers(graph, edges + [edge("1199", "0")]).values()))

    def test_huge_sparse_layers_preserve_pins_without_float_conversion(self) -> None:
        huge = 10 ** 400
        graph = [{"id": "a", "layer": huge}, {"id": "b"}]
        self.assertEqual({"a": huge, "b": huge + 1}, assign_layers(graph, [edge("a", "b")]))
        layers = {0: nodes("ab"), huge: nodes("cd"), huge + 1: nodes("ef")}
        edges = [edge("a", "d"), edge("b", "c"), edge("c", "f")]
        self.assertEqual(1, count_crossings(layers, edges))
        self.assertEqual(0, count_crossings(order_layers(layers, edges), edges))

    def test_invalid_layers_and_endpoints_fail_clearly(self) -> None:
        for value in (-1, 1.5, True, "1", float("inf")):
            with self.assertRaises(ValueError):
                assign_layers([{"id": "a", "layer": value}], [])
        with self.assertRaises(ValueError):
            assign_layers(nodes("aa"), [])
        with self.assertRaises(ValueError):
            assign_layers(nodes("a"), [edge("a", "b")])
        self.assertEqual({}, assign_layers([], []))


class EdgePortTests(unittest.TestCase):
    def test_fanout_is_spaced_in_opposite_cross_axis_order(self) -> None:
        boxes = [rect("a", 0, 100), rect("b", 240, 0), rect("c", 240, 100), rect("d", 240, 200)]
        edges = [edge("a", node_id, id=node_id) for node_id in "dcb"]
        original = copy.deepcopy(edges)
        result = edge_ports(edges, boxes, "LR")
        self.assertEqual([.75, .5, .25], [item["from_anchor"] for item in result])
        self.assertEqual([.5] * 3, [item["to_anchor"] for item in result])
        self.assertTrue(all(item["source_port"] == "E" and item["target_port"] == "W" for item in result))
        self.assertEqual(original, edges)
        starts = {port_point(boxes[0], item["source_port"], item["from_anchor"]) for item in result}
        self.assertEqual(3, len(starts))

    def test_vertical_fanin_and_reverse_direction(self) -> None:
        boxes = {item["id"]: item for item in [rect("a", 0, 0), rect("b", 150, 0), rect("c", 70, 200)]}
        result = edge_ports([edge("b", "c"), edge("a", "c")], boxes, "TB")
        self.assertEqual([2 / 3, 1 / 3], [item["to_anchor"] for item in result])
        self.assertTrue(all(item["source_port"] == "S" and item["target_port"] == "N" for item in result))
        reverse = edge_ports([edge("c", "a")], boxes, "BT")[0]
        self.assertEqual(("N", "S"), (reverse["source_port"], reverse["target_port"]))

    def test_explicit_anchors_ports_and_incoming_outgoing_share_slots(self) -> None:
        boxes = [rect("a", 0, 100), rect("b", 240, 0), rect("c", 240, 100), rect("d", 240, 200)]
        edges = [edge("a", "c", source_port="E", from_anchor=.5, target_port="N", to_anchor=0),
                 edge("a", "b"), edge("d", "a", target_port="E")]
        result = edge_ports(edges, boxes)
        self.assertEqual(edges[0], result[0])
        self.assertEqual(.25, result[1]["from_anchor"])
        self.assertEqual(.75, result[2]["to_anchor"])

    def test_parallel_edges_are_deterministic_and_have_distinct_clear_routes(self) -> None:
        boxes = [rect("a", 0, 100), rect("b", 240, 100)]
        edges = [edge("a", "b", id=str(index)) for index in range(4)]
        result = edge_ports(edges, boxes)
        self.assertEqual(result, list(reversed(edge_ports(list(reversed(edges)), boxes))))
        paths = []
        for item in result:
            points = route_orthogonal(boxes[0], boxes[1], boxes,
                                      source_port=item["source_port"], target_port=item["target_port"],
                                      source_anchor=item["from_anchor"], target_anchor=item["to_anchor"])
            paths.append(tuple(points))
            for start, end in zip(points, points[1:]):
                self.assertFalse(any(segment_intersects_rect(start, end, box) for box in boxes))
        self.assertEqual(4, len(set(paths)))
        self.assertEqual([2] * 4, [len(path) for path in paths])

    def test_idless_parallel_and_self_loop_ports(self) -> None:
        boxes = [rect("a", 50, 50)]
        edges = [edge("a", "a", source_port="E", target_port="E")] * 2
        result = edge_ports(edges, boxes)
        anchors = [item[key] for item in result for key in ("from_anchor", "to_anchor")]
        self.assertEqual(4, len(set(anchors)))
        for item in result:
            points = route_orthogonal(boxes[0], boxes[0], boxes, source_port="E", target_port="E",
                                      source_anchor=item["from_anchor"], target_anchor=item["to_anchor"])
            self.assertNotEqual(points[0], points[-1])

    def test_explicit_duplicate_anchors_remain_explicit(self) -> None:
        boxes = [rect("a", 0, 0), rect("b", 240, 0)]
        result = edge_ports([edge("a", "b", from_anchor=.5), edge("a", "b", from_anchor=.5),
                             edge("a", "b")], boxes)
        self.assertEqual([.5, .5], [item["from_anchor"] for item in result[:2]])
        self.assertNotEqual(.5, result[2]["from_anchor"])

    def test_nonrectangular_boundaries_keep_inferred_anchors_at_center(self) -> None:
        for shape in ("ellipse", "diamond", "operation", "database", "document"):
            for side in ("N", "E", "S", "W"):
                with self.subTest(shape=shape, side=side):
                    boxes = [{**rect("a", 100, 100), "shape": shape}, rect("b", 300, 100)]
                    edges = [edge("a", "b", source_port=side), edge("b", "a", target_port=side)]
                    result = edge_ports(edges, boxes)
                    anchors = [result[0]["from_anchor"], result[1]["to_anchor"]]
                    if shape in {"ellipse", "diamond", "operation"} or side in {"N", "S"}:
                        self.assertEqual([.5, .5], anchors)
                    else:
                        self.assertEqual({1 / 3, 2 / 3}, set(anchors))
                    explicit = edge_ports([edge("a", "b", source_port=side, from_anchor=.2),
                                           edge("b", "a", target_port=side, to_anchor=.8)], boxes)
                    self.assertEqual(.2, explicit[0]["from_anchor"])
                    self.assertEqual(.8, explicit[1]["to_anchor"])

    def test_box_objects_supply_shape_for_endpoint_precision(self) -> None:
        boxes = {"a": SimpleNamespace(**rect("a", 0, 0), shape="diamond"),
                 "b": SimpleNamespace(**rect("b", 240, 0), shape="rounded")}
        result = edge_ports([edge("a", "b", id="one"), edge("a", "b", id="two")], boxes)
        self.assertEqual([.5, .5], [item["from_anchor"] for item in result])
        self.assertEqual([1 / 3, 2 / 3], [item["to_anchor"] for item in result])

    def test_invalid_ports_anchors_and_direction(self) -> None:
        boxes = [rect("a", 0, 0)]
        for extra in ({"source_port": "bad"}, {"from_anchor": -1}, {"to_anchor": float("nan")}):
            with self.assertRaises(ValueError):
                edge_ports([edge("a", "a", **extra)], boxes)
        with self.assertRaises(ValueError):
            edge_ports([], boxes, "bad")
        self.assertEqual([], edge_ports([], []))


class OccupiedRoutingTests(unittest.TestCase):
    def assert_clear(self, path: list, boxes: list) -> None:
        for first, second in zip(path, path[1:]):
            self.assertTrue(first[0] == second[0] or first[1] == second[1])
            self.assertFalse(any(segment_intersects_rect(first, second, box) for box in boxes))

    def test_real_crossing_is_reduced_by_a_clear_deterministic_detour(self) -> None:
        boxes = [rect("a", 0, 100), rect("b", 240, 100)]
        occupied = [[(180, 100), (180, 160)]]
        baseline = route_orthogonal(boxes[0], boxes[1], boxes)
        optimized = route_orthogonal(boxes[0], boxes[1], boxes, occupied_paths=occupied)
        self.assertEqual(1, path_congestion([baseline, *occupied])["crossings"])
        self.assertEqual(0, path_congestion([optimized, *occupied])["crossings"])
        self.assertEqual(baseline[0], optimized[0])
        self.assertEqual(baseline[-1], optimized[-1])
        self.assertEqual(optimized, route_orthogonal(boxes[0], boxes[1], boxes, occupied_paths=occupied))
        self.assert_clear(optimized, boxes)

    def test_shared_trunk_is_reduced_in_real_paths(self) -> None:
        boxes = [rect("a", 0, 100), rect("b", 240, 100)]
        occupied = [[(140, 130), (210, 130)]]
        baseline = route_orthogonal(boxes[0], boxes[1], boxes)
        optimized = route_orthogonal(boxes[0], boxes[1], boxes, occupied_paths=occupied)
        self.assertEqual(70, path_congestion([baseline, *occupied])["overlap_length"])
        self.assertEqual({"crossings": 0, "overlap_length": 0.0}, path_congestion([optimized, *occupied]))
        self.assert_clear(optimized, boxes)

    def test_fanout_ports_and_occupied_paths_remove_shared_departure(self) -> None:
        boxes = {box["id"]: box for box in [rect("a", 0, 100), rect("b", 240, 0), rect("c", 240, 200)]}
        edges = [edge("a", "b"), edge("a", "c")]
        baseline = [route_orthogonal(boxes[item["from"]], boxes[item["to"]], boxes.values(),
                                    source_port="E", target_port="W") for item in edges]
        optimized = []
        for item in edge_ports(edges, boxes, "LR"):
            optimized.append(route_orthogonal(
                boxes[item["from"]], boxes[item["to"]], boxes.values(),
                source_port=item["source_port"], target_port=item["target_port"],
                source_anchor=item["from_anchor"], target_anchor=item["to_anchor"],
                occupied_paths=optimized))
        self.assertGreater(path_congestion(baseline)["overlap_length"], 0)
        self.assertEqual({"crossings": 0, "overlap_length": 0.0}, path_congestion(optimized))
        for path in optimized:
            self.assert_clear(path, list(boxes.values()))

    def test_empty_occupied_paths_preserve_default_routes(self) -> None:
        boxes = [rect("a", 0, 100), rect("b", 180, 100), rect("c", 360, 100)]
        for source, target in ((boxes[0], boxes[2]), (boxes[2], boxes[0]), (boxes[0], boxes[0])):
            baseline = route_orthogonal(source, target, boxes)
            self.assertEqual(baseline, route_orthogonal(source, target, boxes, occupied_paths=[]))
            self.assertEqual(baseline, route_orthogonal(source, target, boxes, occupied_paths=iter(())))

    def test_real_metrics_deduplicate_bend_contacts_and_handle_json_points(self) -> None:
        self.assertEqual({"crossings": 0, "overlap_length": 0.0}, path_congestion([]))
        paths = [[[0, 10], [10, 10], [10, 20]], [[10, 0], [10, 10], [20, 10]]]
        self.assertEqual(1, path_congestion(paths)["crossings"])
        self.assertEqual(0, path_congestion([[(0, 0), (10, 0)], [(10, 0), (10, 10)]])["crossings"])
        self.assertEqual(30, path_congestion([[(-5, 0), (5, 0)]] * 3)["overlap_length"])

    def test_evidence_examples_reduce_actual_route_congestion(self) -> None:
        from figurelib.diagrams import _box_rect, _layout_layered, _semantic_style

        assets = ROOT / "skills/figurecraft/assets"
        theme = json.loads((assets / "themes/paper-light.json").read_text())
        for name in ("agent-evidence-workflow", "research-evidence-flow"):
            with self.subTest(example=name):
                original = json.loads((assets / f"examples/{name}.json").read_text())
                qualities = []
                for optimize in (False, True):
                    spec, style = _semantic_style(copy.deepcopy(original), theme)
                    spec["layout"]["optimize"] = False
                    if optimize:
                        assigned = assign_layers(spec["nodes"], spec["edges"])
                        layers = {}
                        for node in spec["nodes"]:
                            layers.setdefault(assigned[node["id"]], []).append(node)
                        spec["nodes"] = [node for items in order_layers(layers, spec["edges"]).values() for node in items]
                    boxes, _, _ = _layout_layered(spec, "LR", style)
                    obstacles = [_box_rect(box) for box in boxes.values()]
                    edges = edge_ports(spec["edges"], boxes, "LR") if optimize else spec["edges"]
                    paths = []
                    for item in edges:
                        points = route_orthogonal(
                            _box_rect(boxes[item["from"]]), _box_rect(boxes[item["to"]]), obstacles,
                            source_port=item.get("source_port"), target_port=item.get("target_port"),
                            source_anchor=item.get("from_anchor", .5), target_anchor=item.get("to_anchor", .5),
                            occupied_paths=paths if optimize else None)
                        self.assert_clear(points, obstacles)
                        paths.append(points)
                    qualities.append(path_congestion(paths))
                self.assertLess(qualities[1]["crossings"], qualities[0]["crossings"])
                self.assertLess(qualities[1]["overlap_length"], qualities[0]["overlap_length"])


if __name__ == "__main__":
    unittest.main()
