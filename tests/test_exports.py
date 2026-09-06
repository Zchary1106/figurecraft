from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/figurecraft"
sys.path.insert(0, str(SKILL / "scripts"))

from figurelib.cli import _render
from figurelib.diagrams import render_diagram
from figurelib.io import copy_source, load_columns, load_spec, sha256
from figurelib.styles import load_theme


class ExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace = ROOT / f".export-test-{uuid.uuid4().hex}"
        self.workspace.mkdir()
        self.addCleanup(shutil.rmtree, self.workspace)

    def drawio(self, spec: dict) -> tuple[dict[str, ET.Element], dict]:
        spec = {"version": "1.0", "output": {"primary": "drawio"}, **spec}
        theme = load_theme(spec, SKILL)
        render_diagram(spec, self.workspace, theme)
        tree = ET.parse(self.workspace / "figure.drawio")
        cells = {cell.get("id"): cell for cell in tree.iter("mxCell")}
        for cell in cells.values():
            if cell.get("edge") == "1":
                self.assertIn(cell.get("source"), cells)
                self.assertIn(cell.get("target"), cells)
        return cells, theme

    def test_generic_relationship_semantics(self) -> None:
        cells, theme = self.drawio({
            "kind": "diagram.architecture",
            "nodes": [
                {"id": "a", "label": "Agent", "layer": 0, "status": "READY"},
                {"id": "b", "label": "State", "layer": 1},
            ],
            "edges": [
                {"id": "sync", "from": "a", "to": "b", "label": "updates",
                 "direction": "bidirectional", "status": "SYNC", "kind": "state",
                 "source_port": "S", "target_port": "N", "from_anchor": 0.3,
                 "to_anchor": 0.7},
                {"id": "gate", "from": "a", "to": "b", "direction": "none",
                 "state": "GATED", "color": "#123456", "style": "dashed"},
            ],
        })
        self.assertIn("READY", cells["node-a"].get("value"))
        sync = cells["edge-sync"]
        self.assertIn("SYNC", sync.get("value"))
        for expected in ("startArrow=block", "endArrow=block", "exitX=0.3", "exitY=1",
                         "entryX=0.7", "entryY=0", f"strokeColor={theme['accents'][3]}"):
            self.assertIn(expected, sync.get("style"))
        gate = cells["edge-gate"]
        self.assertIn("GATED", gate.get("value"))
        for expected in ("startArrow=none", "endArrow=none", "strokeColor=#123456", "dashed=1"):
            self.assertIn(expected, gate.get("style"))

    def test_landscape_relationship_semantics(self) -> None:
        cells, theme = self.drawio({
            "kind": "diagram.system-landscape",
            "zones": [
                {"id": "a", "title": "Runtime", "column": 0, "span": 6,
                 "sections": [{"title": "Agent", "items": [{"label": "Worker", "status": "READY"}]}]},
                {"id": "b", "title": "Storage", "column": 6, "span": 6, "sections": []},
            ],
            "connections": [
                {"from": "a", "to": "b", "direction": "bidirectional",
                 "status": "DURABLE", "kind": "state", "from_anchor": 0.25, "to_anchor": 0.75},
                {"from": "b", "to": "a", "direction": "none", "status": "GATED",
                 "color": "#654321"},
            ],
        })
        edge = cells["connection-0"]
        self.assertIn("DURABLE", edge.get("value"))
        for expected in ("startArrow=block", "endArrow=block", "exitX=1", "exitY=0.25",
                         "entryX=0", "entryY=0.75", f"strokeColor={theme['accents'][3]}"):
            self.assertIn(expected, edge.get("style"))
        self.assertIn("endArrow=none", cells["connection-1"].get("style"))
        self.assertIn("strokeColor=#654321", cells["connection-1"].get("style"))

    def test_landscape_nested_geometry_matches_adaptive_helpers(self) -> None:
        from figurelib.diagrams import landscape_section_layout, landscape_zone_layout

        zone = {
            "id": "runtime", "title": "Runtime architecture", "subtitle": "Adaptive multiline evidence processing",
            "section_columns": 2, "sections": [
                {"title": "Research workers", "subtitle": "Independent reproducible evaluations",
                 "columns": 2, "items": [
                     {"label": "Detailed worker responsibilities " * 7, "subtitle": "Measurable evidence " * 5},
                     {"label": "Validator"},
                 ], "note": "Every result retains source provenance and a reproducible configuration. " * 3},
                {"title": "State", "items": [{"label": "Checkpoint store"}]},
            ],
        }
        cells, theme = self.drawio({"kind": "diagram.system-landscape", "layout": {"width": 720},
                                    "zones": [zone]})
        zone_width = float(cells["zone-runtime"].find("mxGeometry").get("width"))
        zone_layout = landscape_zone_layout(zone, zone_width, theme)
        for section_box in zone_layout["sections"]:
            index = section_box["index"]
            section_id = f"zone-runtime-section-{index}"
            exported = cells[section_id].find("mxGeometry")
            for key in ("x", "y", "width", "height"):
                self.assertAlmostEqual(section_box[key], float(exported.get(key)), places=2)
            section = zone["sections"][index]
            positions = landscape_section_layout(section, section_box["width"], theme)
            for card in positions["items"]:
                exported = cells[f"{section_id}-card-{card['index']}"].find("mxGeometry")
                for key in ("x", "y", "width", "height"):
                    self.assertAlmostEqual(card[key], float(exported.get(key)), places=2)
            if section.get("note"):
                note = cells[f"{section_id}-note"]
                self.assertEqual(section["note"], note.get("value"))
                self.assertAlmostEqual(positions["note"]["height"],
                                       float(note.find("mxGeometry").get("height")), places=2)
        self.assertGreater(float(cells["zone-runtime-section-0-card-0"].find("mxGeometry").get("height")), 54)

    def test_framework_exports_all_cards_and_relationships_with_shared_geometry(self) -> None:
        from figurelib.framework import framework_layout

        spec = {
            "kind": "diagram.research-framework", "title": "Editable research",
            "layout": {"width": 880},
            "framework_stages": [
                {"id": "input", "title": "Inputs", "connect_items": True, "items": [
                    {"label": "Observed datasets", "shape": "database"},
                    {"label": "A long analysis description that wraps into multiple lines",
                     "subtitle": "Scientific evidence and uncertainty", "shape": "diamond"},
                    {"label": "Assumptions", "status": "CHECKED"},
                ]},
                {"id": "model", "title": "Model", "transition": "estimate", "items": [
                    {"label": "Validated predictor", "subtitle": "Independent test"}
                ]},
            ],
            "feedback": {"from": "model", "to": "input", "label": "revisit"},
            "outcome": {"label": "Findings", "subtitle": "Reproducible"},
        }
        cells, theme = self.drawio(spec)
        positions = framework_layout(spec, theme)
        expected_vertices = {
            "figure-title", "framework-stage-input", "framework-stage-model",
            "framework-stage-input-item-0", "framework-stage-input-item-1",
            "framework-stage-input-item-2", "framework-stage-model-item-0", "framework-outcome",
        }
        self.assertEqual(expected_vertices, {key for key, cell in cells.items() if cell.get("vertex") == "1"})
        edges = [cell for cell in cells.values() if cell.get("edge") == "1"]
        self.assertEqual(5, len(edges))
        self.assertIn("estimate", cells["framework-transition-0"].get("value"))
        self.assertIn("dashed=1", cells["framework-feedback"].get("style"))
        self.assertIn("CHECKED", cells["framework-stage-input-item-2"].get("value"))
        for stage, stage_box in zip(spec["framework_stages"], positions["stages"]):
            parent = cells[f"framework-stage-{stage['id']}"]
            self.assertIn("container=1", parent.get("style"))
            for index, box in enumerate(stage_box["items"]):
                cell = cells[f"framework-stage-{stage['id']}-item-{index}"]
                self.assertEqual(parent.get("id"), cell.get("parent"))
                geometry = cell.find("mxGeometry")
                self.assertAlmostEqual(box["height"], float(geometry.get("height")), places=2)
                self.assertAlmostEqual(box["y"] - stage_box["y"], float(geometry.get("y")), places=2)

    def test_framework_matrix_exports_every_phase_track_cell_and_link(self) -> None:
        from figurelib.framework_matrix import matrix_layout

        spec = {
            "kind": "diagram.framework-matrix", "title": "Evidence matrix",
            "phases": [{"id": "p1", "title": "Design"}, {"id": "p2", "title": "Evaluate"}],
            "tracks": [
                {"id": "t1", "title": "Experiments", "cells": [
                    {"id": "a", "phase": "p1", "label": "Sample"},
                    {"id": "b", "phase": "p2", "label": "Benchmark", "status": "READY"},
                ]},
                {"id": "t2", "title": "Theory", "cells": [
                    {"id": "c", "phase": "p1", "label": "Hypotheses"},
                    {"id": "d", "phase": "p2", "label": "Long theoretical result " * 8},
                ]},
            ],
            "cross_links": [{"from": "b", "to": "d", "label": "constrain",
                             "direction": "bidirectional", "status": "SYNC"}],
            "integration": {"label": "Synthesis", "chips": ["Confidence", "Replicability"]},
            "outcome": {"label": "Conclusions"},
        }
        cells, theme = self.drawio(spec)
        positions = matrix_layout(spec, theme)
        for cell_id in ("matrix-phase-p1", "matrix-phase-p2", "matrix-track-t1", "matrix-track-t2",
                        "matrix-cell-a", "matrix-cell-b", "matrix-cell-c", "matrix-cell-d",
                        "matrix-integration", "matrix-outcome"):
            self.assertEqual("1", cells[cell_id].get("vertex"))
        self.assertEqual(6, len([cell for cell in cells.values() if cell.get("edge") == "1"]))
        self.assertIn("SYNC", cells["matrix-cross-link-0"].get("value"))
        self.assertIn("startArrow=block", cells["matrix-cross-link-0"].get("style"))
        self.assertTrue(any("Confidence" in cell.get("value", "") for cell in cells.values()))
        self.assertIn("Confidence", cells["matrix-integration-chip-0"].get("value"))
        self.assertEqual("matrix-integration", cells["matrix-integration-chip-0"].get("parent"))
        for cell_id, box in positions["cells"].items():
            geometry = cells[f"matrix-cell-{cell_id}"].find("mxGeometry")
            self.assertAlmostEqual(box["height"], float(geometry.get("height")), places=2)
            self.assertTrue(cells[f"matrix-cell-{cell_id}"].get("parent").startswith("matrix-track-"))

    def test_cnn_export_uses_normalized_adaptive_layout(self) -> None:
        from figurelib.cnn import block_layout, cnn_layout_spec, legend_layout

        spec = {
            "kind": "diagram.cnn-architecture",
            "stages": [
                {"id": "input", "title": "Input", "spatial": 32, "channels": 3},
                {"id": "operator", "title": "Operator", "type": "operator",
                 "label": "A detailed scientific operation requiring several wrapped lines",
                 "subtitle": "Preserve the adaptive operator geometry"},
            ],
            "block_detail": {
                "title": "Expanded block",
                "steps": [{"label": f"Detailed scientific operation {index}"} for index in range(8)],
                "shortcut": {"label": "Projection", "subtitle": "Align feature dimensions"},
            },
            "stage_table": [{"stage": "Feature extractor", "output": "32×32×64",
                             "block": "Repeated convolution", "repeat": 8}],
            "note": "Long scientific architecture explanation with reproducibility details. " * 5,
        }
        before = json.dumps(spec)
        cells, theme = self.drawio(spec)
        normalized = cnn_layout_spec(spec, theme)
        box = cells["cnn-stage-operator"].find("mxGeometry")
        self.assertAlmostEqual(normalized["stages"][1]["height"], float(box.get("height")), places=2)
        inset = cells["cnn-block-detail"].find("mxGeometry")
        self.assertAlmostEqual(normalized["layout"]["inset_width"], float(inset.get("width")), places=2)
        self.assertAlmostEqual(normalized["layout"]["inset_height"], float(inset.get("height")), places=2)
        layout = normalized["layout"]
        block = block_layout(normalized["block_detail"], layout["inset_x"], layout["inset_y"],
                             layout["inset_width"], theme.get("svg_font_family", theme["font_family"]))
        for index in range(8):
            step = cells[f"cnn-detail-step-{index}"].find("mxGeometry")
            self.assertAlmostEqual(block["card_height"], float(step.get("height")), places=2)
            self.assertAlmostEqual(block["path_y"] - layout["inset_y"] - block["card_height"] / 2,
                                   float(step.get("y")), places=2)
        self.assertIn("cnn-detail-shortcut", cells)
        self.assertIn("cnn-detail-output", cells)
        legend_box = cells["cnn-legend"].find("mxGeometry")
        legend = legend_layout(normalized, float(legend_box.get("width")),
                               theme.get("svg_font_family", theme["font_family"]))
        note_box = cells["cnn-legend-note"].find("mxGeometry")
        self.assertAlmostEqual(legend["note_height"], float(note_box.get("height")), places=2)
        self.assertEqual(spec["note"], cells["cnn-legend-note"].get("value"))
        self.assertIn("cnn-legend-row-0-block", cells)
        self.assertEqual(before, json.dumps(spec))
        spec["block_detail"]["residual"] = False
        without_residual, _ = self.drawio(spec)
        self.assertNotIn("cnn-detail-residual", without_residual)
        self.assertNotIn("cnn-detail-shortcut", without_residual)
        self.assertNotIn("cnn-detail-merge", without_residual)
        self.assertNotIn("cnn-detail-main-merge", without_residual)
        self.assertEqual("cnn-detail-step-7", without_residual["cnn-detail-output-edge"].get("source"))
        self.assertEqual("cnn-detail-output", without_residual["cnn-detail-output-edge"].get("target"))

    def test_matrix_skip_track_link_preserves_shared_route(self) -> None:
        from figurelib.framework_matrix import _matrix_routes, matrix_layout

        spec = {
            "kind": "diagram.framework-matrix",
            "phases": [{"id": "phase", "title": "Analysis"}],
            "tracks": [
                {"id": f"t{index}", "title": f"Track {index}", "cells": [
                    {"id": f"c{index}", "phase": "phase", "label": f"Evidence {index}"}]}
                for index in range(3)
            ],
            "cross_links": [{"from": "c0", "to": "c2", "label": "Compare independent evidence"}],
        }
        cells, theme = self.drawio(spec)
        geometry = _matrix_routes(spec, matrix_layout(spec, theme), theme)
        route = next(edge["points"] for edge in geometry.edges if edge["id"] == "matrix-cross-0")
        points = cells["matrix-cross-link-0"].findall("mxGeometry/Array/mxPoint")
        self.assertEqual(len(route) - 2, len(points))
        self.assertGreater(len(points), 2)
        for point, expected in zip(points, route[1:-1]):
            self.assertAlmostEqual(expected[0], float(point.get("x")), places=2)
            self.assertAlmostEqual(expected[1], float(point.get("y")), places=2)

    def test_external_data_bundle_rerenders_json_and_yaml(self) -> None:
        for spec_suffix, data_suffix in ((".json", ".csv"), (".yaml", ".json")):
            with self.subTest(spec=spec_suffix, data=data_suffix):
                home = self.workspace / spec_suffix[1:]
                home.mkdir()
                data_path = home / f"data{data_suffix}"
                data_path.write_text(
                    "x,y\n1,2\n2,4\n" if data_suffix == ".csv" else '{"x":[1,2],"y":[2,4]}',
                    encoding="utf-8",
                )
                spec = {
                    "version": "1.0", "kind": "chart.line",
                    "data": {"source": data_path.name},
                    "series": [{"x": "x", "y": "y", "label": "Score"}],
                    "output": {"primary": "svg"},
                }
                original = home / f"spec{spec_suffix}"
                if spec_suffix == ".json":
                    original.write_text(json.dumps(spec), encoding="utf-8")
                else:
                    import yaml
                    original.write_text(yaml.safe_dump(spec), encoding="utf-8")
                before = original.read_bytes()
                output = home / "output"
                self.assertEqual(0, _render(original, output, False))
                manifest = json.loads((output / "figure-manifest.json").read_text())
                copied = output / manifest["spec"]["path"]
                reference = load_spec(copied)["data"]["source"]
                self.assertEqual([{"path": reference, "sha256": sha256(data_path)}], manifest["inputs"])
                self.assertEqual(before, original.read_bytes())
                self.assertEqual(data_path.read_bytes(), (output / reference).read_bytes())
                expected = load_columns(load_spec(copied), copied)
                data_path.unlink()
                self.assertEqual(0, _render(copied, home / "second", False))
                self.assertEqual(0, _render(copied, output, False))
                self.assertEqual(expected, load_columns(load_spec(copied), copied))

    def test_bundle_does_not_overwrite_untracked_source_or_symlink(self) -> None:
        original = self.workspace / "spec.json"
        original.write_text('{"version":"1.0"}', encoding="utf-8")
        output = self.workspace / "output"
        output.mkdir()
        destination = output / "figure-source.json"
        destination.write_text('{"keep":"me"}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "untracked"):
            copy_source(original, output)
        self.assertEqual('{"keep":"me"}', destination.read_text())
        destination.unlink()
        destination.symlink_to(original)
        with self.assertRaisesRegex(ValueError, "symlink"):
            copy_source(original, output)
        self.assertEqual('{"version":"1.0"}', original.read_text())

    def test_same_directory_original_source_is_not_mutated(self) -> None:
        original = self.workspace / "figure-source.json"
        data = self.workspace / "measurements.csv"
        data.write_text("x,y\n1,3\n2,5\n", encoding="utf-8")
        original.write_text(json.dumps({
            "version": "1.0", "kind": "chart.line", "data": {"source": data.name},
            "series": [{"x": "x", "y": "y"}], "output": {"primary": "svg"},
        }), encoding="utf-8")
        before = original.read_bytes()
        self.assertEqual(0, _render(original, self.workspace, False))
        self.assertEqual(before, original.read_bytes())
        copied = self.workspace / "figure-source-bundled.json"
        self.assertTrue(copied.is_file())
        self.assertEqual(0, _render(copied, self.workspace, False))
        self.assertEqual(before, original.read_bytes())

    def test_bundle_rejects_conflicting_data_and_manifest_input(self) -> None:
        data = self.workspace / "data.csv"
        data.write_text("x,y\n1,2\n", encoding="utf-8")
        spec = {"version": "1.0", "kind": "chart.line", "data": {"source": data.name},
                "series": [{"x": "x", "y": "y"}]}
        original = self.workspace / "spec.json"
        original.write_text(json.dumps(spec), encoding="utf-8")
        output = self.workspace / "output"
        output.mkdir()
        conflicting = output / f"figure-input-{sha256(data)}.csv"
        conflicting.write_text("unrelated data", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "conflicting"):
            copy_source(original, output)
        self.assertEqual("unrelated data", conflicting.read_text())
        reserved = self.workspace / "figure-manifest.json"
        reserved.write_text(json.dumps(spec), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "overwrite an input"):
            _render(reserved, self.workspace, False)
        self.assertEqual(spec, json.loads(reserved.read_text()))

    def test_invalid_external_data_can_be_corrected_and_rerendered(self) -> None:
        original = self.workspace / "spec.json"
        data = self.workspace / "data.csv"
        original.write_text(json.dumps({
            "version": "1.0", "kind": "chart.line", "data": {"source": data.name},
            "series": [{"x": "x", "y": "y"}], "output": {"primary": "svg"},
        }), encoding="utf-8")
        data.write_text("x,y\n1,bad\n2,3\n", encoding="utf-8")
        output = self.workspace / "output"
        with self.assertRaisesRegex(ValueError, "finite numeric"):
            _render(original, output, False)
        self.assertFalse(output.exists())
        data.write_text("x,y\n1,2\n2,3\n", encoding="utf-8")
        self.assertEqual(0, _render(original, output, False))


if __name__ == "__main__":
    unittest.main()
