from __future__ import annotations

import copy
import json
import shutil
import sys
import unittest
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/figurecraft"
sys.path.insert(0, str(SKILL / "scripts"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from figurelib.charts import _bar, _heatmap, _line, _place_direct_labels, _rc_params, _save, render_chart, render_gantt
from figurelib.validate import validate_chart_data, validate_spec

THEME = json.loads((SKILL / "assets/themes/paper-light.json").read_text())


class ScientificValidationTests(unittest.TestCase):
    def line(self):
        return {
            "version": "1.0", "kind": "chart.line",
            "data": {"columns": {"x": [1, 2], "y": [2, 3], "low": [1, 2], "high": [3, 4]}},
            "series": [{"x": "x", "y": "y", "lower": "low", "upper": "high"}],
            "semantics": {"uncertainty": "95% confidence interval"},
        }

    def errors(self, spec):
        return "\n".join(validate_spec(spec, SKILL))

    def test_nested_malformed_types_never_reach_semantics(self):
        for value in (None, [], "bad", 5, True):
            for field in ("data", "series", "semantics", "layout"):
                spec = self.line()
                spec[field] = value
                with self.subTest(field=field, value=value):
                    self.assertTrue(self.errors(spec))
        for spec in (
            {"version": "1.0", "kind": ["chart.line"]},
            {"version": "1.0", "kind": "diagram.architecture", "nodes": [{"id": []}]},
            {"version": "1.0", "kind": "diagram.cnn-architecture", "stages": [None, {}]},
            {"version": "1.0", "kind": "project.gantt", "tasks": [{"label": "A", "start": [], "end": "2026-01-01", "depends_on": 3}]},
        ):
            self.assertTrue(self.errors(spec))

    def test_missing_matrix_cell_label_is_schema_error(self):
        spec = {
            "version": "1.0", "kind": "diagram.framework-matrix",
            "phases": [{"id": "a", "title": "A"}, {"id": "b", "title": "B"}],
            "tracks": [
                {"id": "one", "title": "One", "cells": [{"id": "c", "phase": "a"}]},
                {"id": "two", "title": "Two", "cells": []},
            ],
        }
        self.assertIn("'label' is a required property", self.errors(spec))

    def test_node_layers_are_nonnegative_json_integers(self):
        spec = {
            "version": "1.0", "kind": "diagram.architecture",
            "nodes": [{"id": "n", "label": "IMPORTANT", "layer": -1}],
        }
        self.assertIn("$.nodes[0].layer", self.errors(spec))
        for layer in (0, 1, 1.0):
            with self.subTest(layer=layer):
                spec["nodes"][0]["layer"] = layer
                self.assertEqual("", self.errors(spec))
        spec["nodes"][0]["layer"] = 1.5
        self.assertIn("$.nodes[0].layer", self.errors(spec))

    def test_uncertainty_requires_description_and_ordered_bounds(self):
        spec = self.line()
        self.assertEqual("", self.errors(spec))
        del spec["semantics"]
        self.assertIn("uncertainty", self.errors(spec))
        spec["semantics"] = {"uncertainty": "95% CI"}
        spec["data"]["columns"]["low"] = [4, 5]
        self.assertIn("lower uncertainty bounds", self.errors(spec))
        del spec["series"][0]["upper"]
        self.assertIn("both lower and upper", self.errors(spec))

    def test_numeric_and_reference_validation(self):
        for value in (float("nan"), float("inf"), -float("inf"), "bad", None, True):
            spec = self.line()
            spec["data"]["columns"]["y"][0] = value
            with self.subTest(value=value):
                self.assertTrue(self.errors(spec))
        spec = self.line()
        spec["series"][0]["y"] = "missing"
        self.assertIn("unknown data field", self.errors(spec))
        spec = self.line()
        spec["data"]["columns"]["y"].append(3)
        self.assertIn("equal length", self.errors(spec))

    def test_error_magnitudes_cannot_be_negative(self):
        spec = self.line()
        spec["kind"] = "chart.errorbar"
        spec["series"] = [{"x": "x", "y": "y", "error": "low"}]
        spec["data"]["columns"]["low"][0] = -1
        self.assertIn("non-negative", self.errors(spec))

    def test_nested_ranges_and_permissive_extensions(self):
        spec = self.line()
        spec["series"][0]["alpha"] = 2
        spec["layout"] = {"width_mm": 0}
        self.assertIn("$.series[0].alpha", self.errors(spec))
        self.assertIn("$.layout.width_mm", self.errors(spec))
        spec["series"][0]["alpha"] = 0.5
        spec["layout"] = {"width_mm": 90, "custom_hint": "preserved"}
        spec["series"][0]["custom_metadata"] = {"anything": True}
        self.assertEqual("", self.errors(spec))

    def test_heatmap_matrix_shape_and_labels(self):
        spec = {"version": "1.0", "kind": "chart.heatmap", "data": {"matrix": [[1, 2], [3]]}}
        self.assertIn("rectangular", self.errors(spec))
        spec["data"] = {"matrix": [[1, 2]], "row_labels": ["a", "b"]}
        self.assertIn("label count", self.errors(spec))

    def test_explicit_neural_dimensions_only(self):
        spec = {
            "version": "1.0", "kind": "diagram.neural-network",
            "nodes": [
                {"id": "a", "output_shape": ["B", 32], "subtitle": "64 → 16"},
                {"id": "b", "input_shape": ["N", 16]},
            ],
            "edges": [{"from": "a", "to": "b"}],
        }
        self.assertIn("dimensions do not match", self.errors(spec))
        spec["nodes"][1]["input_shape"] = ["N", 32]
        self.assertEqual("", self.errors(spec))
        del spec["nodes"][1]["input_shape"]
        self.assertEqual("", self.errors(spec))

    def test_gantt_dates_references_and_cycles(self):
        spec = {
            "version": "1.0", "kind": "project.gantt",
            "tasks": [
                {"id": "a", "label": "A", "start": "2026-01-01", "end": "2026-01-02", "depends_on": "b"},
                {"id": "b", "label": "B", "start": "2026-01-03", "end": "2026-01-04", "depends_on": "a"},
            ],
        }
        self.assertIn("dependency cycle", self.errors(spec))
        spec["tasks"][0]["depends_on"] = "missing"
        self.assertIn("unknown task", self.errors(spec))
        spec["tasks"][0]["start"] = "not-a-date"
        self.assertIn("date", self.errors(spec))

    def test_integer_valued_float_dimensions_are_compared(self):
        for kind in ("diagram.neural-network", "diagram.cnn-architecture"):
            for source_size, target_size in ((32.0, 16.0), (32, 16.0), (32.0, 16)):
                spec = {
                    "version": "1.0", "kind": kind,
                    "nodes": [
                        {"id": "a", "output_shape": [source_size]},
                        {"id": "b", "input_shape": [target_size]},
                    ],
                    "edges": [{"from": "a", "to": "b"}],
                }
                if kind == "diagram.cnn-architecture":
                    spec["stages"] = [
                        {**node, "title": node["id"], "type": "operator"}
                        for node in spec.pop("nodes")
                    ]
                    del spec["edges"]
                with self.subTest(kind=kind, source=source_size, target=target_size):
                    self.assertIn("dimensions do not match", self.errors(spec))
                    entries = spec.get("nodes", spec.get("stages"))
                    entries[1]["input_shape"] = [32.0]
                    self.assertEqual("", self.errors(spec))

    def test_external_columns_receive_same_numeric_validation(self):
        spec = self.line()
        columns = copy.deepcopy(spec["data"]["columns"])
        columns["y"] = ["bad", 3]
        self.assertIn("finite numeric", "\n".join(validate_chart_data(spec, columns)))
        columns["y"] = [float("inf"), 3]
        with patch("figurelib.charts.load_columns", return_value=columns):
            with self.assertRaisesRegex(ValueError, "finite numeric"):
                render_chart(spec, ROOT / "unused.json", ROOT, THEME)

    def test_all_examples_still_validate(self):
        for path in (SKILL / "assets/examples").glob("*.json"):
            with self.subTest(example=path.name):
                self.assertEqual("", self.errors(json.loads(path.read_text())))


class ScientificRenderingTests(unittest.TestCase):
    def setUp(self):
        self.directory = ROOT / f".scientific-output-{uuid.uuid4().hex}"
        self.directory.mkdir()
        self.addCleanup(shutil.rmtree, self.directory)
        self.addCleanup(plt.close, "all")

    def test_delta_units(self):
        for unit, explicit, expected in (
            ("ms", None, "+2.0 ms"), ("%", None, "+2.0 pp"),
            ("fraction", None, "+2.0 fraction"), ("", None, "+2.0"),
            ("ms", "custom", "+2.0 custom"),
        ):
            spec = {"series": [{"x": "x", "y": "a"}, {"x": "x", "y": "b"}],
                    "style": {"annotate_delta": True}, "semantics": {"y_unit": unit}}
            if explicit:
                spec["semantics"]["delta_unit"] = explicit
            fig, ax = plt.subplots()
            _bar(ax, spec, {"x": ["A"], "a": [1], "b": [3]}, THEME)
            self.assertEqual(expected, ax.texts[0].get_text())
            plt.close(fig)

    def test_signed_stacks_keep_separate_baselines(self):
        fig, ax = plt.subplots()
        spec = {"series": [{"x": "x", "y": name} for name in ("a", "b", "c")], "layout": {"stacked": True}}
        _bar(ax, spec, {"x": ["X"], "a": [3], "b": [-2], "c": [4]}, THEME)
        self.assertEqual([0, 0, 3], [bar.get_y() for bar in ax.patches])

    def test_heatmap_contrast_uses_colormap_not_value(self):
        for cmap in ("gray", "gray_r", "viridis", "coolwarm"):
            fig, ax = plt.subplots()
            spec = {"data": {"matrix": [[0, 1]]}, "style": {"annotate": True, "colormap": cmap}}
            _heatmap(fig, ax, spec, {}, THEME, np)
            image = ax.images[0]
            for value, text in zip((0, 1), ax.texts):
                rgb = image.cmap(image.norm(value))[:3]
                linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
                luminance = sum(c * w for c, w in zip(linear, (0.2126, 0.7152, 0.0722)))
                contrast = 1.05 / (luminance + 0.05) if text.get_color() == "white" else (luminance + 0.05) / 0.05
                self.assertGreaterEqual(contrast, 4.5)
            plt.close(fig)

    def test_identical_endpoint_labels_are_measured_and_deterministic(self):
        with plt.rc_context(_rc_params(THEME)):
            fig, ax = plt.subplots(figsize=(7, 4), constrained_layout=True)
            columns = {"x": [1, 2], **{name: [index, 5] for index, name in enumerate(("alpha", "beta", "gamma", "delta"))}}
            spec = {"kind": "chart.line", "series": [{"x": "x", "y": name} for name in columns if name != "x"],
                    "style": {"direct_labels": True}}
            _line(ax, spec, columns, THEME, False)
            _save(fig, spec, self.directory)
            fig.canvas.draw()
            renderer = fig.canvas.get_renderer()
            boxes = [text.get_bbox_patch().get_window_extent(renderer) for text in ax.texts]
            for index, box in enumerate(boxes):
                for other in boxes[index + 1:]:
                    self.assertFalse(box.overlaps(other))
            before = [text.get_position() for text in ax.texts]
            _place_direct_labels(ax)
            self.assertEqual(before, [text.get_position() for text in ax.texts])
            self.assertTrue(any(text.arrow_patch.get_visible() for text in ax.texts))

    def test_svg_and_png_preserve_requested_width(self):
        spec = {"version": "1.0", "kind": "chart.line", "title": "Physical dimensions",
                "data": {"columns": {"x": [1, 2], "y": [2, 3]}},
                "layout": {"width_mm": 89, "aspect_ratio": 1.6},
                "output": {"primary": "svg", "additional": ["png"], "dpi": 100}}
        render_chart(spec, ROOT / "unused.json", self.directory, THEME)
        svg = ET.parse(self.directory / "figure.svg").getroot()
        self.assertAlmostEqual(float(svg.get("width").removesuffix("pt")), 89 / 25.4 * 72, places=4)
        image = plt.imread(self.directory / "figure.png")
        self.assertLessEqual(abs(image.shape[1] - 89 / 25.4 * 100), 1)

    def test_labels_at_opposite_extremes_stay_on_canvas(self):
        with plt.rc_context(_rc_params(THEME)):
            fig, ax = plt.subplots(figsize=(7, 4), constrained_layout=True)
            columns = {"x": [1, 2], "low": [0, 0], "a": [1, 10], "b": [2, 10], "c": [3, 10]}
            spec = {"kind": "chart.line", "series": [{"x": "x", "y": name} for name in columns if name != "x"],
                    "style": {"direct_labels": True}}
            _line(ax, spec, columns, THEME, False)
            ax.set_ylim(0, 10)
            _save(fig, spec, self.directory)
            fig.canvas.draw()
            renderer = fig.canvas.get_renderer()
            bounds = ax.get_window_extent(renderer)
            for text in ax.texts:
                box = text.get_bbox_patch().get_window_extent(renderer)
                self.assertGreaterEqual(box.y0 + 0.01, bounds.y0)
                self.assertLessEqual(box.y1 - 0.01, bounds.y1)

    def test_gantt_dependency_paths_are_rendered(self):
        spec = {"kind": "project.gantt", "tasks": [
            {"id": "design", "label": "Design", "start": "2026-01-01", "end": "2026-01-03"},
            {"id": "build", "label": "Build", "start": "2026-01-05", "end": "2026-01-07", "depends_on": "design"},
        ]}
        render_gantt(spec, self.directory, THEME)
        svg = (self.directory / "figure.svg").read_text()
        self.assertIn('id="dependency-design-build"', svg)


if __name__ == "__main__":
    unittest.main()
