from __future__ import annotations

import copy
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/figurecraft"
sys.path.insert(0, str(SKILL / "scripts"))

from figurelib.diagrams import render_diagram
from figurelib.io import load_spec
from figurelib.lint import lint_svg
from figurelib.provenance import provenance_description
from figurelib.styles import load_theme
from figurelib.typography import measure_text, wrap_text
from figurelib.validate import validate_spec


class ProvenanceLanguageTests(unittest.TestCase):
    def test_undeclared_source_does_not_become_verified(self) -> None:
        result = provenance_description({})
        self.assertEqual(result["type"], "unspecified")
        self.assertFalse(result["verification_declared"])

    def test_derived_claim_requires_a_source(self) -> None:
        spec = {"version": "1.0", "kind": "diagram.architecture", "nodes": [{"id": "a", "label": "A"}],
                "provenance": {"type": "code-derived"}}
        self.assertTrue(any("sources" in error for error in validate_spec(spec, SKILL)))
        spec["provenance"]["sources"] = ["src/model.py"]
        self.assertEqual(validate_spec(spec, SKILL), [])
        self.assertIn("not declared", provenance_description(spec)["label"])

    def test_provenance_is_visible_and_editable_without_mutating_source(self) -> None:
        spec = {"version": "1.0", "kind": "diagram.architecture",
                "nodes": [{"id": "a", "label": "Processor"}],
                "provenance": {"type": "conceptual", "summary": "Not an implemented architecture."},
                "output": {"primary": "svg", "additional": ["drawio"]}}
        before = copy.deepcopy(spec)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            _, engine, _ = render_diagram(spec, out, load_theme(spec, SKILL))
            svg = out / "figure.svg"
            self.assertIn("Conceptual illustration", "".join(ET.parse(svg).getroot().itertext()))
            self.assertIn("Not an implemented architecture", (out / "figure.drawio").read_text())
            self.assertEqual(lint_svg(svg)[0], [])
            self.assertEqual(engine["provenance"]["type"], "conceptual")
        self.assertEqual(spec, before)

    def test_semantic_shapes_preserve_explicit_shapes_and_topology(self) -> None:
        spec = {"version": "1.0", "kind": "diagram.architecture",
                "nodes": [{"id": "db", "label": "Records", "role": "storage"},
                          {"id": "out", "label": "Report", "role": "outcome", "shape": "rect"}],
                "edges": [{"from": "db", "to": "out"}],
                "style": {"semantic_shapes": True},
                "output": {"primary": "svg", "additional": ["drawio"]}}
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            _, engine, geometry = render_diagram(spec, out, load_theme(spec, SKILL))
            xml = ET.parse(out / "figure.drawio")
            self.assertIn("cylinder", xml.find(".//mxCell[@id='node-db']").get("style"))
            self.assertEqual(len(geometry), 2)
            self.assertEqual(len(engine["edges"]), 1)
        self.assertNotIn("shape", spec["nodes"][0])

    def test_missing_glyph_is_an_explicit_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "Missing font glyph"):
            measure_text("\U0010ffff", 12)

    def test_edge_paths_cannot_paint_over_other_edge_labels(self) -> None:
        spec = {"version": "1.0", "kind": "diagram.architecture",
                "nodes": [{"id": "a", "label": "A", "layer": 0},
                          {"id": "b", "label": "B", "layer": 1},
                          {"id": "c", "label": "C", "layer": 1}],
                "edges": [{"from": "a", "to": "b", "label": "research"},
                          {"from": "a", "to": "c", "label": "execute"}],
                "layout": {"direction": "TB"}}
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            render_diagram(spec, out, load_theme(spec, SKILL))
            elements = list(ET.parse(out / "figure.svg").getroot())
            routes = [i for i, element in enumerate(elements) if element.get("data-edge-id")]
            labels = [i for i, element in enumerate(elements)
                      if "".join(element.itertext()) in {"research", "execute"}]
            self.assertEqual(len(labels), 2)
            self.assertGreater(min(labels), max(routes))

    def test_explicit_margin_and_gap_control_layered_layout(self) -> None:
        spec = {"version": "1.0", "kind": "diagram.architecture",
                "nodes": [{"id": "a", "label": "A", "layer": 0},
                          {"id": "b", "label": "B", "layer": 1}],
                "layout": {"direction": "LR", "margin": 24, "gap": 44}}
        with tempfile.TemporaryDirectory() as directory:
            _, engine, geometry = render_diagram(spec, Path(directory), load_theme(spec, SKILL))
            self.assertEqual(geometry[0]["x"], 24)
            self.assertEqual(geometry[1]["x"] - geometry[0]["x"] - geometry[0]["width"], 44)
            self.assertEqual(engine["canvas"]["height"], geometry[0]["height"] + 48)

    def test_chinese_punctuation_does_not_start_wrapped_line(self) -> None:
        text = "数据、方法、证据。结果（说明）"
        try:
            measure_text(text, 12)
        except ValueError as exc:
            self.skipTest(f"Optional CJK font unavailable: {exc}")
        lines = wrap_text(text, 48, 12)
        self.assertGreater(len(lines), 1)
        for line in lines:
            self.assertNotIn(line[0], "，。、：；！？）】》」』")
            self.assertNotIn(line[-1], "（【《「『")
            self.assertLessEqual(measure_text(line, 12), 48 + 1e-6)


if __name__ == "__main__":
    unittest.main()
