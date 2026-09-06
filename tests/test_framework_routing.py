from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/figurecraft"
sys.path.insert(0, str(SKILL / "scripts"))

from figurelib.framework_matrix import matrix_layout, render_framework_matrix_svg
from figurelib.lint import lint_manifest, lint_svg
from figurelib.routing import overlaps, segment_intersects_rect
from figurelib.styles import load_theme


def matrix_spec(tracks: int = 3) -> dict:
    return {
        "version": "1.0", "kind": "diagram.framework-matrix", "title": "Complex framework",
        "phases": [{"id": "design", "title": "Design"}, {"id": "evaluate", "title": "Evaluate"}],
        "tracks": [{
            "id": f"track-{index}", "title": f"Research track {index + 1}",
            "cells": [{"id": f"{index}-design", "phase": "design", "label": "Hypothesis"},
                      {"id": f"{index}-evaluate", "phase": "evaluate", "label": "Evidence"}],
        } for index in range(tracks)],
        "cross_links": [{"from": "0-evaluate", "to": f"{tracks - 1}-evaluate", "label": "evidence"}],
        "integration": {"label": "Integrate", "chips": ["Validity"]},
        "outcome": {"label": "Outcome"},
        "style": {"preset": "editorial-contrast"}, "output": {"primary": "svg"},
    }


class FrameworkRoutingTests(unittest.TestCase):
    def render(self, spec: dict) -> tuple[str, list, dict]:
        theme = load_theme(spec, SKILL)
        svg, width, height, geometry = render_framework_matrix_svg(spec, theme)
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".matrix-routing-test-") as directory:
            path = Path(directory)
            (path / "figure.svg").write_text(svg)
            engine = {"canvas": {"width": width, "height": height}, "edges": geometry.edges,
                      "labels": geometry.labels, "routing_nodes": geometry.routing_nodes}
            manifest = {"kind": spec["kind"], "geometry": geometry, "engine": engine,
                        "outputs": [{"path": "figure.svg"}]}
            (path / "manifest.json").write_text(json.dumps(manifest))
            checks = lint_manifest(path / "manifest.json")
            self.assertTrue(checks["passed"], checks)
            self.assertEqual([], lint_svg(path / "figure.svg")[0])
        return svg, geometry, engine

    def test_skips_middle_track_without_crossing_cells(self) -> None:
        spec = matrix_spec()
        original = copy.deepcopy(spec)
        _, geometry, _ = self.render(spec)
        self.assertEqual(original, spec)
        self.assertEqual(5, len(geometry))
        route = next(edge for edge in geometry.edges if edge["id"] == "matrix-cross-0")
        middle = next(box for box in geometry.routing_nodes if box["id"] == "1-evaluate")
        self.assertTrue(any(x != route["points"][0][0] for x, _ in route["points"]))
        self.assertFalse(any(segment_intersects_rect(a, b, middle) for a, b in zip(route["points"], route["points"][1:])))

    def test_repeated_labels_are_measured_wrapped_and_disjoint(self) -> None:
        spec = matrix_spec(4)
        spec["cross_links"] = [
            {"from": "0-evaluate", "to": "3-evaluate",
             "label": "Long methodological relationship including uncertainty and evidence"}
            for _ in range(4)
        ]
        svg, geometry, _ = self.render(spec)
        self.assertEqual(4, len(geometry.labels))
        self.assertTrue(all(label["width"] <= 200 for label in geometry.labels))
        self.assertTrue(all(label["height"] > 20 for label in geometry.labels))
        for index, label in enumerate(geometry.labels):
            self.assertFalse(any(overlaps(label, other) for other in geometry.labels[index + 1:]))
        self.assertIn("data-text-box", svg)

    def test_reverse_self_and_horizontal_cross_links(self) -> None:
        spec = matrix_spec()
        spec["cross_links"] = [
            {"from": "2-design", "to": "0-design", "label": "feedback"},
            {"from": "1-design", "to": "1-design", "label": "iterate"},
            {"from": "0-evaluate", "to": "0-design", "label": "refine"},
        ]
        self.render(spec)

    def test_bus_metadata_is_compact_and_has_no_hidden_obstacles(self) -> None:
        spec = matrix_spec()
        _, geometry, _ = self.render(spec)
        layout = matrix_layout(spec, load_theme(spec, SKILL))
        bus = next(edge for edge in geometry.edges if edge["id"] == "matrix-evidence-bus")
        self.assertEqual(4, len(bus["points"]))
        self.assertEqual(layout["grid_x"] + layout["grid_width"] + layout["convergence_gutter"] / 2, bus["points"][0][0])
        self.assertEqual(3, len([edge for edge in geometry.edges if edge["id"].startswith("matrix-branch-")]))
        self.assertEqual(3, len([edge for edge in geometry.edges if edge["id"].startswith("matrix-progression-")]))
        self.assertFalse(any("junction" in box["id"] for box in geometry.routing_nodes))
        self.assertEqual(geometry.edges[-1]["to"], "outcome")
        self.assertTrue(any(box["id"] == "matrix-track-label-0" for box in geometry.routing_nodes))
        self.assertTrue(any(box["id"] == "matrix-phase-0" for box in geometry.routing_nodes))

    def test_original_complex_example_across_shipped_themes(self) -> None:
        for theme in sorted((SKILL / "assets/themes").glob("*.json")):
            with self.subTest(theme=theme.stem):
                spec = matrix_spec(2)
                spec["style"]["preset"] = theme.stem
                self.render(spec)

    def test_unknown_cross_link_endpoint_is_not_silently_dropped(self) -> None:
        spec = matrix_spec()
        spec["cross_links"][0]["to"] = "missing"
        with self.assertRaisesRegex(ValueError, "unknown endpoint"):
            render_framework_matrix_svg(spec, load_theme(spec, SKILL))

    def test_svg_routes_match_manifest_points(self) -> None:
        svg, geometry, _ = self.render(matrix_spec())
        paths = {element.get("data-edge-id"): element for element in ET.fromstring(svg).iter()
                 if element.get("data-edge-id")}
        self.assertEqual({edge["id"] for edge in geometry.edges}, set(paths))


if __name__ == "__main__":
    unittest.main()
