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

from figurelib.diagrams import _semantic_style, render_diagram
from figurelib.lint import lint_svg
from figurelib.styles import load_theme
from figurelib.validate import validate_spec
from figurelib.cli import _render
from figurelib.revision import prepare_revision


class VisualGrammarTests(unittest.TestCase):
    def spec(self):
        return {
            "version": "1.0", "kind": "diagram.architecture", "title": "Evidence pipeline",
            "nodes": [
                {"id": "input", "label": "Request", "role": "actor", "layer": 0},
                {"id": "work", "label": "Research", "role": "agent", "layer": 1},
                {"id": "verify", "label": "Verify", "role": "agent", "layer": 2},
                {"id": "record", "label": "Evidence record", "subtitle": "Sources and limitations",
                 "role": "artifact", "layer": 3},
            ],
            "edges": [{"from": "input", "to": "work"}, {"from": "work", "to": "verify"},
                      {"from": "verify", "to": "record"}],
            "style": {"preset": "editorial-contrast", "visual_grammar": "semantic"},
            "output": {"primary": "svg", "additional": ["drawio"]},
        }

    def test_roles_not_layer_positions_determine_color(self):
        spec = self.spec()
        before = copy.deepcopy(spec)
        resolved, theme = _semantic_style(spec, load_theme(spec, SKILL))
        self.assertEqual(resolved["nodes"][1]["color"], resolved["nodes"][2]["color"])
        self.assertEqual(resolved["nodes"][1]["accent"], resolved["nodes"][2]["accent"])
        self.assertNotEqual(resolved["nodes"][0]["color"], resolved["nodes"][1]["color"])
        self.assertEqual(resolved["nodes"][-1]["shape"], "document")
        self.assertEqual(theme["card_accent"], "none")
        self.assertEqual(spec, before)
        self.assertEqual(resolved["edges"], before["edges"])

    def test_explicit_visual_decisions_win(self):
        spec = self.spec()
        spec["nodes"][0].update(shape="rect", color="#ffffff", accent="#123456")
        resolved, _ = _semantic_style(spec, load_theme(spec, SKILL))
        for key in ("shape", "color", "accent"):
            self.assertEqual(resolved["nodes"][0][key], spec["nodes"][0][key])

    def test_no_role_inferred_from_label(self):
        spec = self.spec()
        spec["nodes"][0] = {"id": "input", "label": "Database decision report"}
        resolved, theme = _semantic_style(spec, load_theme(spec, SKILL))
        self.assertNotIn("shape", resolved["nodes"][0])
        self.assertEqual(resolved["nodes"][0]["color"], theme["node_fill"])

    def test_legacy_style_unchanged(self):
        spec = self.spec()
        spec["style"].pop("visual_grammar")
        resolved, theme = _semantic_style(spec, load_theme(spec, SKILL))
        self.assertEqual(resolved, spec)
        self.assertEqual(theme["card_accent"], "legacy")
        self.assertNotIn("color", resolved["nodes"][1])

    def test_document_geometry_and_editable_semantics(self):
        spec = self.spec()
        self.assertEqual(validate_spec(spec, SKILL), [])
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            _, engine, geometry = render_diagram(spec, out, load_theme(spec, SKILL))
            self.assertEqual(lint_svg(out / "figure.svg")[0], [])
            self.assertEqual(len(geometry), 4)
            self.assertEqual(len(engine["edges"]), 3)
            drawio = ET.parse(out / "figure.drawio")
            self.assertIn("shape=note", drawio.find(".//mxCell[@id='node-record']").get("style"))
            root = ET.parse(out / "figure.svg").getroot()
            self.assertFalse(any(e.get("x") == "28" and e.get("width") == "4" for e in root))
            self.assertIn("Evidence record", "".join(root.itertext()))

    def test_real_role_rich_figures_render_repeatably_across_themes(self):
        for name in ("agent-evidence-workflow", "research-evidence-flow"):
            original = json.loads((SKILL / "assets/examples" / f"{name}.json").read_text())
            for theme in sorted((SKILL / "assets/themes").glob("*.json")):
                with self.subTest(figure=name, theme=theme.stem), tempfile.TemporaryDirectory() as directory:
                    spec = copy.deepcopy(original)
                    spec["style"]["preset"] = theme.stem
                    before = copy.deepcopy(spec)
                    first, second = Path(directory) / "first", Path(directory) / "second"
                    first.mkdir()
                    second.mkdir()
                    _, engine, geometry = render_diagram(spec, first, load_theme(spec, SKILL))
                    _, again, repeated = render_diagram(spec, second, load_theme(spec, SKILL))
                    self.assertEqual(geometry, repeated)
                    self.assertEqual(engine, again)
                    self.assertEqual((first / "figure.svg").read_bytes(), (second / "figure.svg").read_bytes())
                    self.assertEqual((first / "figure.drawio").read_bytes(), (second / "figure.drawio").read_bytes())
                    self.assertEqual(lint_svg(first / "figure.svg")[0], [])
                    self.assertEqual(len(engine["edges"]), len(spec["edges"]))
                    self.assertEqual(len(geometry), len(spec["nodes"]))
                    self.assertEqual(spec, before)

    def test_semantic_document_can_be_revised_without_layout_drift(self):
        spec = self.spec()
        spec["nodes"] = [{"id": "record", "label": "Long evidence report\nLong evidence report",
                          "role": "artifact", "icon": "document"}]
        spec["edges"] = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "source.json"
            source.write_text(json.dumps(spec), encoding="utf-8")
            base = root / "base"
            self.assertEqual(_render(source, base, False), 0)
            revised = prepare_revision(base / "figure-manifest.json", source, "content-only")
            out = root / "revised"
            out.mkdir()
            _, engine, geometry = render_diagram(revised, out, load_theme(revised, SKILL))
            manifest = json.loads((base / "figure-manifest.json").read_text())
            self.assertEqual(geometry, manifest["geometry"])
            self.assertEqual(engine["canvas"], manifest["engine"]["canvas"])

    def test_semantic_actor_stays_compact_and_revisable(self):
        spec = self.spec()
        spec["nodes"] = [{"id": "input", "label": "User request", "role": "actor",
                          "subtitle": "Goal and acceptance criteria"}]
        spec["edges"] = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "source.json"
            source.write_text(json.dumps(spec), encoding="utf-8")
            self.assertEqual(_render(source, root / "base", False), 0)
            revised = prepare_revision(root / "base/figure-manifest.json", source, "content-only")
            out = root / "revised"
            out.mkdir()
            _, _, geometry = render_diagram(revised, out, load_theme(revised, SKILL))
            self.assertLess(geometry[0]["height"], geometry[0]["width"])
            self.assertEqual(lint_svg(out / "figure.svg")[0], [])
            manifest = json.loads((root / "base/figure-manifest.json").read_text())
            self.assertEqual(geometry, manifest["geometry"])


if __name__ == "__main__":
    unittest.main()
