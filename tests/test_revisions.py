from __future__ import annotations

import copy
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

from figurelib.diagrams import _layout_layered, render_diagram
from figurelib.io import sha256
from figurelib.revision import apply_placement, prepare_revision
from figurelib.styles import load_theme


class RevisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = ROOT / f".revision-tests-{uuid.uuid4().hex}"
        self.directory.mkdir()
        self.addCleanup(shutil.rmtree, self.directory)
        self.spec = {
            "version": "1.0", "kind": "diagram.architecture",
            "nodes": [{"id": "a", "label": "Input"}, {"id": "b", "label": "Process"},
                      {"id": "c", "label": "Output"}],
            "edges": [{"id": "ab", "from": "a", "to": "b"},
                      {"id": "bc", "from": "b", "to": "c"}],
            "output": {"primary": "svg"},
        }
        self.manifest_path = self.directory / "figure-manifest.json"
        self.source = self.directory / "figure-source.json"
        self.updated = self.directory / "updated.json"
        self.manifest = self.bundle(self.spec)

    def bundle(self, spec: dict, directory: Path | None = None) -> dict:
        directory = directory or self.directory
        directory.mkdir(exist_ok=True)
        source = directory / "figure-source.json"
        source.write_text(json.dumps(spec), encoding="utf-8")
        _, engine, geometry = render_diagram(spec, directory, load_theme(spec, SKILL))
        manifest = {
            "kind": spec["kind"], "spec": {"path": source.name, "sha256": sha256(source)},
            "engine": engine, "geometry": list(geometry),
        }
        (directory / "figure-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    def prepare(self, spec: dict, mode: str = "content-only", unlocked: list[str] | None = None) -> dict:
        self.updated.write_text(json.dumps(spec), encoding="utf-8")
        return prepare_revision(self.manifest_path, self.updated, mode, unlocked)

    def test_content_only_keeps_exact_rectangles_and_routes(self) -> None:
        updated = copy.deepcopy(self.spec)
        updated["nodes"][0]["label"] = "Inputs"
        revision = self.prepare(updated)
        theme = load_theme(revision, SKILL)
        boxes, width, height = _layout_layered(revision, "LR", theme)
        canvas = apply_placement(revision, boxes, width, height)
        self.assertEqual(tuple(self.manifest["engine"]["canvas"].values()), canvas)
        for rect in self.manifest["geometry"]:
            self.assertEqual({key: rect[key] for key in ("x", "y", "width", "height")},
                             {key: getattr(boxes[rect["id"]], key) for key in ("x", "y", "width", "height")})
        self.assertEqual(json.loads(json.dumps(self.manifest["engine"]["edges"])),
                         revision["layout"]["placement"]["routes"])

    def test_render_preserves_geometry_despite_changed_natural_width(self) -> None:
        spec = copy.deepcopy(self.spec)
        spec["nodes"][0]["visual_height"] = 140
        base = self.bundle(spec)
        updated = copy.deepcopy(spec)
        updated["nodes"][0]["label"] = "Incoming validation request"
        natural_boxes, _, _ = _layout_layered(updated, "LR", load_theme(updated, SKILL))
        self.assertNotEqual(base["geometry"][0]["width"], natural_boxes["a"].width)
        revision = self.prepare(updated)
        rendered = self.bundle(revision, self.directory / "revised")
        self.assertEqual(base["geometry"], rendered["geometry"])
        self.assertEqual(base["engine"]["edges"], rendered["engine"]["edges"])
        self.assertEqual(base["engine"]["canvas"], rendered["engine"]["canvas"])
        self.assertIn("Incoming", (self.directory / "revised/figure.svg").read_text())

    def test_render_chained_revisions_preserve_original_geometry(self) -> None:
        spec = copy.deepcopy(self.spec)
        spec["nodes"][0]["visual_height"] = 140
        base = self.bundle(spec)
        updated = copy.deepcopy(spec)
        updated["nodes"][0]["label"] = "Incoming validation request"
        first = self.prepare(updated)
        first_directory = self.directory / "first"
        self.bundle(first, first_directory)
        first_manifest = first_directory / "figure-manifest.json"
        first_inputs = {path: path.read_bytes() for path in first_directory.iterdir() if path.is_file()}
        second_update = copy.deepcopy(first)
        second_update["nodes"][0]["label"] = "Validated incoming request"
        self.updated.write_text(json.dumps(second_update), encoding="utf-8")
        second = prepare_revision(first_manifest, self.updated, "content-only")
        rendered = self.bundle(second, self.directory / "second")
        self.assertEqual(base["geometry"], rendered["geometry"])
        self.assertEqual(base["engine"]["edges"], rendered["engine"]["edges"])
        self.assertEqual(base["engine"]["canvas"], rendered["engine"]["canvas"])
        self.assertEqual(sha256(first_directory / "figure-source.json"),
                         second["layout"]["placement"]["source_sha256"])
        for path, contents in first_inputs.items():
            self.assertEqual(contents, path.read_bytes())

    def test_letterboxed_media_revision_locks_drawing_canvas_not_viewbox(self) -> None:
        spec = copy.deepcopy(self.spec)
        spec["layout"] = {"medium": "slide", "margin": 40.5, "gap": 72.5}
        spec["nodes"][0]["visual_height"] = 140
        base = self.bundle(spec)
        base_svg = ET.parse(self.directory / "figure.svg").getroot()
        view_box = list(map(float, base_svg.get("viewBox").split()))
        self.assertNotEqual(base["engine"]["canvas"]["height"], view_box[3])
        updated = copy.deepcopy(spec)
        updated["nodes"][0]["label"] = "Incoming validation request"
        revision = self.prepare(updated)
        rendered = self.bundle(revision, self.directory / "slide")
        revised_svg = ET.parse(self.directory / "slide/figure.svg").getroot()
        self.assertEqual(base["geometry"], rendered["geometry"])
        self.assertEqual(base["engine"]["canvas"], rendered["engine"]["canvas"])
        self.assertEqual(base["engine"]["edges"], rendered["engine"]["edges"])
        self.assertEqual(base_svg.get("viewBox"), revised_svg.get("viewBox"))
        self.assertEqual(("1920", "1080"), (revised_svg.get("width"), revised_svg.get("height")))

    def test_locked_long_text_raises_overflow(self) -> None:
        updated = copy.deepcopy(self.spec)
        updated["nodes"][0]["label"] = "This label must not silently enlarge a locked node. " * 30
        with self.assertRaisesRegex(ValueError, "overflow"):
            self.prepare(updated)

    def test_local_unlock_preserves_other_coordinates(self) -> None:
        updated = copy.deepcopy(self.spec)
        updated["nodes"][1]["label"] = "Process data"
        revision = self.prepare(updated, "local", ["b"])
        boxes, width, height = _layout_layered(revision, "LR", load_theme(revision, SKILL))
        original_unlocked = vars(boxes["b"]).copy()
        apply_placement(revision, boxes, width, height)
        self.assertEqual(original_unlocked, vars(boxes["b"]))
        self.assertEqual({"a", "c"}, set(revision["layout"]["placement"]["boxes"]))
        self.assertEqual([], revision["layout"]["placement"]["routes"])
        for rect in self.manifest["geometry"]:
            if rect["id"] != "b":
                self.assertEqual(rect["x"], boxes[rect["id"]].x)
                self.assertEqual(rect["y"], boxes[rect["id"]].y)

    def test_local_preserves_edges_not_touching_unlocked_nodes(self) -> None:
        updated = copy.deepcopy(self.spec)
        updated["nodes"][2]["label"] = "Outputs"
        revision = self.prepare(updated, "local", ["c"])
        self.assertEqual(["ab"], [route["id"] for route in revision["layout"]["placement"]["routes"]])

    def test_conflicting_placement_rejected_atomically(self) -> None:
        revision = self.prepare(self.spec)
        locks = revision["layout"]["placement"]["boxes"]
        locks["b"] = dict(locks["a"])
        boxes, width, height = _layout_layered(revision, "LR", load_theme(revision, SKILL))
        before = copy.deepcopy(boxes)
        with self.assertRaisesRegex(ValueError, "overlap"):
            apply_placement(revision, boxes, width, height)
        self.assertEqual(before, boxes)

    def test_out_of_canvas_rejected(self) -> None:
        revision = self.prepare(self.spec)
        revision["layout"]["placement"]["boxes"]["c"]["x"] = 100000
        boxes, width, height = _layout_layered(revision, "LR", load_theme(revision, SKILL))
        with self.assertRaisesRegex(ValueError, "out of canvas"):
            apply_placement(revision, boxes, width, height)

    def test_unlocked_node_cannot_obstruct_preserved_route(self) -> None:
        revision = self.prepare(self.spec, "local", ["c"])
        rectangles = {rect["id"]: dict(rect) for rect in self.manifest["geometry"]}
        start, end = revision["layout"]["placement"]["routes"][0]["points"][:2]
        rectangles["c"].update(x=(start[0] + end[0]) / 2 - 5,
                               y=(start[1] + end[1]) / 2 - 5, width=10, height=10)
        with self.assertRaisesRegex(ValueError, "Preserved route"):
            apply_placement(revision, rectangles, 1000, 1000)

    def test_reflow_clears_previous_constraints(self) -> None:
        updated = copy.deepcopy(self.spec)
        updated["layout"] = {"direction": "TB", "placement": {"mode": "content-only", "boxes": {}}}
        updated["nodes"][0]["fill"] = "#000000"
        revision = self.prepare(updated, "reflow")
        self.assertEqual({"direction": "TB"}, revision["layout"])
        self.assertEqual("#000000", revision["nodes"][0]["fill"])

    def test_modified_base_source_rejected_without_writes(self) -> None:
        self.source.write_text(self.source.read_text() + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.prepare(self.spec)

    def test_modified_base_geometry_and_routes_rejected(self) -> None:
        for field in ("geometry", "routes", "canvas", "ids"):
            with self.subTest(field=field):
                manifest = copy.deepcopy(self.manifest)
                if field == "geometry":
                    manifest["geometry"][0]["x"] += 1
                elif field == "routes":
                    manifest["engine"]["edges"][0]["points"] = [[0, 0], [1, 1]]
                elif field == "canvas":
                    manifest["engine"]["canvas"]["width"] += 1
                else:
                    manifest["geometry"][0]["id"] = "missing"
                self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "match"):
                    self.prepare(self.spec)

    def test_nontext_changes_rejected(self) -> None:
        changes = [
            lambda spec: spec["nodes"][0].update(fill="#000000"),
            lambda spec: spec["nodes"][0].update(visual_width=1000),
            lambda spec: spec["nodes"][0].update(shape="ellipse"),
            lambda spec: spec["edges"][0].update(to="c"),
            lambda spec: spec["edges"].pop(),
            lambda spec: spec.update(layout={"direction": "TB"}),
        ]
        for change in changes:
            updated = copy.deepcopy(self.spec)
            change(updated)
            with self.subTest(spec=updated), self.assertRaisesRegex(ValueError, "nontext"):
                self.prepare(updated)

    def test_unknown_missing_duplicate_and_empty_unlocks_rejected(self) -> None:
        for unlocked in (None, [], ["missing"], ["a", "a"]):
            with self.subTest(unlocked=unlocked), self.assertRaises(ValueError):
                self.prepare(self.spec, "local", unlocked)
        updated = copy.deepcopy(self.spec)
        updated["nodes"][0]["id"] = "missing"
        with self.assertRaises(ValueError):
            self.prepare(updated)
        updated["nodes"][0]["id"] = "b"
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.prepare(updated)

    def test_changed_kind_rejected(self) -> None:
        updated = copy.deepcopy(self.spec)
        updated["kind"] = "diagram.flowchart"
        with self.assertRaisesRegex(ValueError, "kind"):
            self.prepare(updated, "reflow")

    def test_prepare_never_overwrites_inputs(self) -> None:
        self.updated.write_text(json.dumps(self.spec), encoding="utf-8")
        files = {path: path.read_bytes() for path in self.directory.iterdir() if path.is_file()}
        result = prepare_revision(self.manifest_path, self.updated, "content-only")
        self.assertIn("placement", result["layout"])
        self.assertEqual(set(files), {path for path in self.directory.iterdir() if path.is_file()})
        for path, content in files.items():
            self.assertEqual(content, path.read_bytes())
        prepare_revision(self.manifest_path, self.source, "content-only")
        self.assertEqual(files[self.source], self.source.read_bytes())

    def test_specialized_renderer_requires_reflow(self) -> None:
        cnn = json.loads((SKILL / "assets/examples/cnn-architecture.json").read_text())
        self.bundle(cnn)
        with self.assertRaisesRegex(ValueError, "use reflow"):
            self.prepare(cnn)
        revision = self.prepare(cnn, "reflow")
        self.assertNotIn("placement", revision.get("layout", {}))

    def test_swimlane_requires_reflow_until_lane_geometry_can_be_locked(self) -> None:
        swimlane = json.loads((SKILL / "assets/examples/swimlane.json").read_text())
        self.bundle(swimlane)
        for mode, unlocked in (("content-only", None), ("local", [swimlane["nodes"][0]["id"]])):
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, "use reflow"):
                self.prepare(swimlane, mode, unlocked)
        revision = self.prepare(swimlane, "reflow")
        self.assertNotIn("placement", revision.get("layout", {}))

    def test_provenance_footer_is_reserved_not_duplicated(self) -> None:
        spec = copy.deepcopy(self.spec)
        spec["provenance"] = {"type": "conceptual", "summary": "Illustrative architecture"}
        manifest = self.bundle(spec)
        updated = copy.deepcopy(spec)
        updated["nodes"][0]["label"] = "Inputs"
        revision = self.prepare(updated)
        self.assertEqual(manifest["engine"]["canvas"], revision["layout"]["placement"]["canvas"])
        boxes, width, height = _layout_layered(revision, "LR", load_theme(revision, SKILL))
        width, content_height = apply_placement(revision, boxes, width, height)
        self.assertEqual(width, manifest["engine"]["canvas"]["width"])
        self.assertLess(content_height, manifest["engine"]["canvas"]["height"])
        rendered = self.bundle(revision, self.directory / "with-footer")
        self.assertEqual(manifest["engine"]["canvas"], rendered["engine"]["canvas"])
        self.assertEqual(manifest["geometry"], rendered["geometry"])
        root = ET.parse(self.directory / "with-footer/figure.svg").getroot()
        self.assertEqual(1, sum(element.get("id") == "figure-provenance" for element in root.iter()))
        self.updated.write_text(json.dumps(revision), encoding="utf-8")
        chained = prepare_revision(self.directory / "with-footer/figure-manifest.json", self.updated, "content-only")
        rerendered = self.bundle(chained, self.directory / "footer-again")
        self.assertEqual(manifest["engine"]["canvas"], rerendered["engine"]["canvas"])

    def test_landscape_dictionary_rectangles_are_locked(self) -> None:
        landscape = {
            "version": "1.0", "kind": "diagram.system-landscape", "output": {"primary": "svg"},
            "zones": [
                {"id": "one", "title": "One", "column": 0, "span": 6, "sections": []},
                {"id": "two", "title": "Two", "column": 6, "span": 6, "sections": []},
            ],
        }
        manifest = self.bundle(landscape)
        revision = self.prepare(landscape)
        rectangles = {rect["id"]: dict(rect, x=0, y=0) for rect in manifest["geometry"]}
        apply_placement(revision, rectangles, 10000, 10000)
        self.assertEqual(manifest["geometry"], list(rectangles.values()))

    def test_landscape_rejects_nested_movement_inside_unchanged_zone(self) -> None:
        landscape = {
            "version": "1.0", "kind": "diagram.system-landscape",
            "output": {"primary": "svg"}, "layout": {"width": 720},
            "zones": [
                {"id": "one", "title": "One", "column": 0, "span": 6,
                 "sections": [{"title": "Section", "items": [{"label": "Input"}]}]},
                {"id": "two", "title": "Two", "column": 6, "span": 6,
                 "sections": [{"title": "Section", "items": [{"label": "long label " * 60}]}]},
            ],
        }
        self.bundle(landscape)
        updated = copy.deepcopy(landscape)
        updated["zones"][0]["sections"][0]["items"][0]["label"] = "long label " * 12
        with self.assertRaisesRegex(ValueError, "internal geometry changed"):
            self.prepare(updated)
        with self.assertRaisesRegex(ValueError, "internal geometry changed"):
            self.prepare(updated, "local", ["two"])

    def test_landscape_small_item_text_edit_keeps_nested_geometry(self) -> None:
        landscape = {
            "version": "1.0", "kind": "diagram.system-landscape", "output": {"primary": "svg"},
            "zones": [
                {"id": "one", "title": "One", "sections": [
                    {"title": "Section", "items": [{"label": "Input"}]},
                ]},
            ],
        }
        base = self.bundle(landscape)
        original_svg = ET.parse(self.directory / "figure.svg").getroot()
        updated = copy.deepcopy(landscape)
        updated["zones"][0]["sections"][0]["items"][0]["label"] = "Inputs"
        revision = self.prepare(updated)
        self.assertIn("one", revision["layout"]["placement"]["boxes"])
        rendered = self.bundle(revision, self.directory / "landscape")
        revised_svg = ET.parse(self.directory / "landscape/figure.svg").getroot()
        shape_tags = {"rect", "line", "path", "circle", "ellipse", "polygon"}
        original_shapes = [(element.tag, element.attrib) for element in original_svg.iter()
                           if element.tag.rsplit("}", 1)[-1] in shape_tags]
        revised_shapes = [(element.tag, element.attrib) for element in revised_svg.iter()
                          if element.tag.rsplit("}", 1)[-1] in shape_tags]
        self.assertEqual(original_shapes, revised_shapes)
        self.assertEqual(base["geometry"], rendered["geometry"])
        self.assertEqual(base["engine"]["edges"], rendered["engine"]["edges"])
        self.assertEqual(base["engine"]["canvas"], rendered["engine"]["canvas"])


if __name__ == "__main__":
    unittest.main()
