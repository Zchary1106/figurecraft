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

from figurelib.cli import _render
from figurelib.diagrams import _route_edges, render_diagram
from figurelib.revision import prepare_revision
from figurelib.routing import segment_intersects_rect
from figurelib.styles import load_theme


class GraphRenderingTests(unittest.TestCase):
    def render(self, spec, directory):
        directory.mkdir()
        return render_diagram(spec, directory, load_theme(spec, SKILL))

    def test_real_diagrams_improve_actual_paths_and_keep_labels_clear(self):
        for name in ("agent-evidence-workflow", "research-evidence-flow"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                spec = json.loads((SKILL / "assets/examples" / f"{name}.json").read_text())
                original = copy.deepcopy(spec)
                legacy = copy.deepcopy(spec)
                legacy["layout"]["optimize"] = False
                _, before, _ = self.render(legacy, root / "before")
                _, after, nodes = self.render(spec, root / "after")
                old, new = before["layout_quality"], after["layout_quality"]
                self.assertLessEqual(new["crossings"], old["crossings"])
                self.assertLess(new["overlap_length"], old["overlap_length"])
                self.assertEqual(spec, original)
                for edge in after["edges"]:
                    for a, b in zip(edge["points"], edge["points"][1:]):
                        self.assertFalse(any(segment_intersects_rect(a, b, node) for node in nodes))
                for label in after["labels"]:
                    for index, edge in enumerate(after["edges"]):
                        if index != label["edge_index"]:
                            self.assertFalse(any(segment_intersects_rect(a, b, label)
                                                 for a, b in zip(edge["points"], edge["points"][1:])))
                xml = ET.parse(root / "after/figure.drawio")
                for index, edge in enumerate(after["edges"]):
                    identifier = spec["edges"][index].get("id", index)
                    cell = xml.find(f".//mxCell[@id='edge-{identifier}']")
                    self.assertIsNotNone(cell)
                    for key, value in edge["ports"].items():
                        self.assertEqual(cell.get(key), str(value))

    def test_optimized_ports_and_geometry_survive_chained_text_revisions(self):
        spec = json.loads((SKILL / "assets/examples/agent-evidence-workflow.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "source.json"
            source.write_text(json.dumps(spec), encoding="utf-8")
            self.assertEqual(_render(source, root / "base", False), 0)
            first_manifest = json.loads((root / "base/figure-manifest.json").read_text())
            previous = root / "base/figure-manifest.json"
            for index, label in enumerate(("Planner", "Task plan")):
                spec["nodes"][2]["label"] = label
                source.write_text(json.dumps(spec), encoding="utf-8")
                updated = prepare_revision(previous, source, "content-only")
                prepared = root / f"prepared-{index}.json"
                prepared.write_text(json.dumps(updated), encoding="utf-8")
                out = root / f"revision-{index}"
                self.assertEqual(_render(prepared, out, False), 0)
                current = json.loads((out / "figure-manifest.json").read_text())
                self.assertEqual(current["geometry"], first_manifest["geometry"])
                self.assertEqual(current["engine"]["edges"], first_manifest["engine"]["edges"])
                self.assertEqual(current["engine"]["canvas"], first_manifest["engine"]["canvas"])
                previous = out / "figure-manifest.json"

    def test_sparse_explicit_ranks_do_not_allocate_empty_layers(self):
        spec = {"version": "1.0", "kind": "diagram.architecture",
                "nodes": [{"id": "a", "label": "A", "layer": 0},
                          {"id": "b", "label": "B", "layer": 1000000000}],
                "edges": [{"from": "a", "to": "b"}], "layout": {"optimize": True}}
        with tempfile.TemporaryDirectory() as directory:
            _, engine, nodes = self.render(spec, Path(directory) / "out")
            self.assertEqual(len(nodes), 2)
            self.assertLess(engine["canvas"]["width"], 1000)

    def test_invalid_saved_ports_fail_explicitly(self):
        boxes = {"a": {"id": "a", "x": 0, "y": 0, "width": 100, "height": 60},
                 "b": {"id": "b", "x": 200, "y": 0, "width": 100, "height": 60}}
        edges = [{"id": "link", "from": "a", "to": "b"}]
        valid = {"source_port": "E", "target_port": "W", "from_anchor": .5, "to_anchor": .5}
        for ports in ({}, {"source_port": "E"}, "E",
                      {**valid, "to_anchor": float("nan")}, {**valid, "from_anchor": True},
                      {**valid, "to_anchor": 2}, {**valid, "target_port": "invalid"}):
            with self.subTest(ports=ports):
                spec = {"layout": {"optimize": True, "placement": {
                    "routes": [{**edges[0], "ports": ports, "points": [[100, 30], [200, 30]]}]}}}
                with self.assertRaisesRegex(ValueError, "invalid ports"):
                    _route_edges(spec, edges, boxes, list(boxes.values()))

    def test_specialized_plate_rejects_unimplemented_optimization(self):
        spec = json.loads((SKILL / "assets/examples/cnn-architecture.json").read_text())
        spec.setdefault("layout", {})["optimize"] = True
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "not specialized plates"):
                self.render(spec, Path(directory) / "out")


if __name__ == "__main__":
    unittest.main()
