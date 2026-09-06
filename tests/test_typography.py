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

from figurelib.cnn import block_layout, cnn_layout_spec, render_cnn_svg
from figurelib.diagrams import _node_size, render_diagram
from figurelib.framework import framework_layout, render_framework_svg
from figurelib.framework_matrix import matrix_layout, render_framework_matrix_svg
from figurelib.io import load_spec
from figurelib.styles import load_theme
from figurelib.lint import lint_drawio, lint_svg
from figurelib.typography import contrast_ratio, label_svg, measure_text, readable_color, wrap_text


class TypographyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.theme = load_theme({}, SKILL)

    def assert_text_bounds(self, svg: str) -> None:
        for element in ET.fromstring(svg).iter():
            if "data-text-box" not in element.attrib:
                continue
            x, y, width, height = map(float, element.get("data-text-box").split(","))
            cx, cy, cw, ch = map(float, element.get("data-text-container").split(","))
            self.assertGreaterEqual(x + 0.05, cx, element.text)
            self.assertGreaterEqual(y + 0.05, cy, element.text)
            self.assertLessEqual(x + width, cx + cw + 0.05, element.text)
            self.assertLessEqual(y + height, cy + ch + 0.05, element.text)
            self.assertGreaterEqual(contrast_ratio(element.get("fill"), element.get("data-text-background")), 4.5)

    def test_uses_font_metrics_not_character_count(self) -> None:
        self.assertGreater(measure_text("WWW", 12), measure_text("iii", 12) * 2)
        lines = wrap_text("Wide WWW tokens andaverylongidentifierthatmustwrap", 70, 12)
        self.assertGreater(len(lines), 2)
        self.assertTrue(all(measure_text(line, 12) <= 70 for line in lines))
        text = "Measured exact width"
        self.assertEqual(wrap_text(text, measure_text(text, 12) - 1e-12, 12), [text])

    def test_label_fails_instead_of_silently_clipping(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not fit"):
            label_svg("A long label that cannot fit", "", 0, 0, 40, 10)

    def test_label_contrast_follows_custom_background(self) -> None:
        svg = "<svg>" + "".join(label_svg("Visible", "", 0, 0, 100, 40,
            foreground="#FFFFFF", background="#FFFFFF")) + "</svg>"
        self.assert_text_bounds(svg)

    def test_midgray_contrast_fallback_meets_threshold(self) -> None:
        for channel in range(256):
            background = "#" + f"{channel:02x}" * 3
            color = readable_color("#FFFFFF", background)
            self.assertGreaterEqual(contrast_ratio(color, background), 4.5)
        self.assertEqual(readable_color("#FFFFFF", "#777777"), "#000000")

    def test_technology_and_large_font_are_included_in_node_size(self) -> None:
        plain = {"id": "n", "label": "Processor"}
        detailed = {**plain, "technology": "First line\nSecond line\nThird line\nFourth line"}
        self.assertGreater(_node_size(detailed, self.theme)[1], _node_size(plain, self.theme)[1])
        larger = {**self.theme, "font_size": 28}
        self.assertGreater(_node_size(detailed, larger)[1], _node_size(detailed, self.theme)[1])
        with tempfile.TemporaryDirectory() as tmp:
            render_diagram({"kind": "diagram.architecture", "nodes": [detailed]}, Path(tmp), larger)
            self.assert_text_bounds((Path(tmp) / "figure.svg").read_text())

    def test_lint_rejects_measured_text_overlap(self) -> None:
        elements = label_svg("First", "", 0, 0, 100, 40) + label_svg("Second", "", 0, 0, 100, 40)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "figure.svg"
            path.write_text('<svg viewBox="0 0 100 40">' + "".join(elements) + "</svg>")
            self.assertTrue(any("Text overlap" in error for error in lint_svg(path)[0]))

    def test_lint_rejects_title_only_editable_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "figure.drawio"
            path.write_text('<mxfile compressed="false"><diagram><mxGraphModel><root>'
                            '<mxCell id="title" vertex="1" value="Title"/>'
                            '</root></mxGraphModel></diagram></mxfile>')
            self.assertTrue(any("missing semantic vertices" in error for error in
                                lint_drawio(path, {"vertices": 4, "edges": 2})))

    def test_framework_wraps_cards_into_rows_and_grows(self) -> None:
        spec = {
            "kind": "diagram.research-framework", "layout": {"width": 700},
            "framework_stages": [{"id": "stage", "title": "Method",
                "items": [{"id": str(i), "label": "A sufficiently detailed methodological step",
                           "subtitle": "Inputs and outputs remain fully readable"} for i in range(9)]}],
        }
        layout = framework_layout(spec, self.theme)
        self.assertGreater(layout["stages"][0]["height"], 142)
        self.assertGreater(len({item["y"] for item in layout["stages"][0]["items"]}), 1)
        self.assert_text_bounds(render_framework_svg(spec, self.theme)[0])

    def test_matrix_adapts_long_content_and_dense_columns(self) -> None:
        spec = {
            "kind": "diagram.framework-matrix", "layout": {"width": 700},
            "phases": [{"id": str(i), "title": "A very detailed phase title"} for i in range(6)],
            "tracks": [{"id": f"t{j}", "title": "Scientific evidence and rigorous methods",
                "cells": [{"id": f"{j}-{i}", "phase": str(i),
                           "label": "Long compound label with several technical concepts",
                           "subtitle": "Details remain readable without shrinking the entire figure"}
                          for i in range(6)]} for j in range(2)],
            "integration": {"label": "Integrate all workstreams", "chips": ["Evidence quality and reproducibility"] * 5},
        }
        layout = matrix_layout(spec, self.theme)
        self.assertGreater(layout["width"], 700)
        self.assertGreater(layout["tracks"][0]["height"], 138)
        self.assert_text_bounds(render_framework_matrix_svg(spec, self.theme)[0])

    def test_dark_cnn_merge_and_overridden_tensor_fill_are_readable(self) -> None:
        spec = load_spec(SKILL / "assets/examples/cnn-architecture.json")
        theme = load_theme({"style": {"preset": "presentation-dark"}}, SKILL)
        svg = render_cnn_svg(spec, theme)[0]
        self.assert_text_bounds(svg)
        plus = next(e for e in ET.fromstring(svg).iter() if e.text == "+")
        self.assertGreaterEqual(contrast_ratio(plus.get("fill"), plus.get("data-text-background")), 4.5)

    def test_dense_cnn_expands_without_mutating_source(self) -> None:
        spec = load_spec(SKILL / "assets/examples/cnn-architecture.json")
        for i in range(8):
            stage = copy.deepcopy(spec["stages"][1])
            stage["id"] = f"extra-{i}"
            spec["stages"].append(stage)
        before = copy.deepcopy(spec)
        normalized = cnn_layout_spec(spec, self.theme)
        self.assertGreater(normalized["layout"]["width"], spec["layout"]["width"])
        svg, _, _, geometry = render_cnn_svg(spec, self.theme)
        self.assertEqual(before, spec)
        stages = geometry[:len(spec["stages"])]
        for left, right in zip(stages, stages[1:]):
            self.assertLess(left["x"] + left["width"], right["x"])
        self.assert_text_bounds(svg)

    def test_non_residual_cnn_does_not_invent_an_addition(self) -> None:
        spec = load_spec(SKILL / "assets/examples/cnn-architecture.json")
        spec["block_detail"]["residual"] = False
        svg = render_cnn_svg(spec, self.theme)[0]
        self.assertFalse(any(element.text == "+" for element in ET.fromstring(svg).iter()))
        self.assertNotIn("identity shortcut", svg)
        self.assert_text_bounds(svg)

    def test_cnn_block_output_stays_inside_inset(self) -> None:
        spec = load_spec(SKILL / "assets/examples/cnn-architecture.json")
        normalized = cnn_layout_spec(spec, self.theme)
        layout = normalized["layout"]
        positions = block_layout(spec["block_detail"], layout["inset_x"], layout["inset_y"],
                                 layout["inset_width"], self.theme["font_family"])
        self.assertLessEqual(positions["end_x"] + 70 + 27,
                             layout["inset_x"] + layout["inset_width"] - 18)

    def test_cnn_transition_uses_resolved_font_and_measured_bounds(self) -> None:
        spec = load_spec(SKILL / "assets/examples/cnn-architecture.json")
        svg = render_cnn_svg(spec, self.theme)[0]
        transitions = {str(stage["transition"]) for stage in spec["stages"] if stage.get("transition")}
        labels = [element for element in ET.fromstring(svg).iter()
                  if "".join(element.itertext()) in transitions and element.tag.endswith("text")]
        self.assertTrue(labels)
        self.assertTrue(all("data-text-box" in label.attrib for label in labels))
        self.assert_text_bounds(svg)


if __name__ == "__main__":
    unittest.main()
