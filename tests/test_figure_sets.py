from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from copy import deepcopy
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import unquote
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/figurecraft"
sys.path.insert(0, str(SKILL / "scripts"))

from figurelib.cli import main
from figurelib.delivery import delivery_html, render_gallery, render_set
from figurelib.io import sha256, write_json
from figurelib.validate import validate_spec
from figurelib.views import plan_views


def graph(count=13):
    return {
        "version": "1.0", "kind": "diagram.architecture", "title": "Source graph",
        "nodes": [{"id": f"n{i}", "label": f"Step {i}", "group": f"group-{i // 5}"}
                  for i in range(count)],
        "edges": [{"id": f"e{i}", "from": f"n{i}", "to": f"n{i + 1}"}
                  for i in range(count - 1)],
        "provenance": {"type": "conceptual", "summary": "Illustrative",
                       "sources": ["local notes"], "verified": False},
        "assumptions": ["Not extracted from implementation"],
        "output": {"primary": "svg"},
    }


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in {"src", "href"} and not value.startswith("#"):
                self.paths.append(unquote(value))


class ViewPlanningTests(unittest.TestCase):
    def test_source_ids_and_edges_survive_without_invented_relations(self):
        source = graph()
        original = deepcopy(source)
        plans = plan_views(source)
        self.assertEqual(original, source)
        original_ids = {n["id"] for n in source["nodes"]}
        detail_ids = {n for p in plans if p["role"] == "detail" for n in p["source_ids"]}
        self.assertEqual(original_ids, detail_ids)
        real_edges = {(e["from"], e["to"]) for e in source["edges"]}
        for plan in plans:
            self.assertEqual(original, plan["full_source"])
            self.assertEqual([], validate_spec(plan["spec"], SKILL))
            if plan["role"] == "reference":
                continue
            self.assertEqual(original, plan["spec"]["view"]["full_source"])
            self.assertEqual(plan["source_ids"], plan["spec"]["view"]["source_ids"])
            self.assertNotIn("full_source", plan["spec"])
            self.assertLessEqual(len(plan["spec"]["nodes"]), 6)
            for edge in plan["spec"]["edges"]:
                self.assertIn((edge["from"], edge["to"]), real_edges)
            for edge in plan["boundary_edges"]:
                self.assertNotEqual(edge["from"] in plan["source_ids"], edge["to"] in plan["source_ids"])
        represented = {e["id"] for p in plans[:-1] for e in p["source_edges"] + p["boundary_edges"]}
        self.assertEqual({e["id"] for e in source["edges"]}, represented)

    def test_duplicate_crossings_have_all_evidence(self):
        source = graph(3)
        source["edges"].append({**source["edges"][0], "id": "duplicate"})
        overview = plan_views(source)[0]
        self.assertEqual(2, len(overview["spec"]["edges"]))
        self.assertEqual(2, len(overview["rendered_edges"][0]["source_relations"]))

    def test_planner_preserves_palette_and_semantically_distinct_edge_colors(self):
        spec = graph(2)
        spec["style"] = {"preset": "midnight-technical", "overrides": {
            "font_size": 20, "palette": ["#123456", "#654321"], "edge": "#345678"}}
        spec["nodes"][0].update(color="#e8f0ff", accent="#2458c5")
        edge = {"from": "n0", "to": "n1", "kind": "control", "color": "#123456"}
        spec["edges"] = [edge, {**edge, "id": "duplicate"},
                         {**edge, "color": "#654321"}, {**edge, "kind": "feedback"}]
        original = deepcopy(spec)
        for medium in ("web", "slide"):
            spec["layout"] = {"medium": medium}
            overview = plan_views(spec)[0]
            self.assertEqual(original["style"], overview["spec"]["style"])
            self.assertEqual("#e8f0ff", overview["spec"]["nodes"][0]["color"])
            self.assertEqual("#2458c5", overview["spec"]["nodes"][0]["accent"])
            self.assertEqual({("control", "#123456"), ("control", "#654321"), ("feedback", "#123456")},
                             {(e["kind"], e["color"]) for e in overview["spec"]["edges"]})
            self.assertEqual(2, len(overview["rendered_edges"][0]["source_relations"]))
        self.assertEqual(original["style"], spec["style"])
        spec["style"]["overrides"]["font_size"] = 9
        self.assertEqual(16, plan_views(spec)[0]["spec"]["style"]["overrides"]["font_size"])

    def test_landscape_has_only_macro_edges(self):
        source = json.loads((SKILL / "assets/examples/system-landscape.json").read_text())
        plans = plan_views(source)
        overview = plans[0]
        self.assertEqual({"backend", "agent-core", "infrastructure"}, set(overview["source_ids"]))
        self.assertEqual(3, len(overview["spec"]["edges"]))
        for detail in [p for p in plans if p["role"] == "detail"]:
            self.assertEqual([], detail["spec"]["edges"])
            self.assertTrue(detail["source_objects"])
            self.assertTrue(detail["context_boundary_edges"])

    def test_matrix_progression_and_aggregated_evidence(self):
        spec = {
            "version": "1.0", "kind": "diagram.framework-matrix",
            "phases": [{"id": "p1", "title": "First"}, {"id": "p2", "title": "Second"}],
            "tracks": [
                {"id": "a", "title": "A", "cells": [
                    {"id": "a2", "phase": "p2", "label": "A2"},
                    {"id": "a1", "phase": "p1", "label": "A1"}]},
                {"id": "b", "title": "B", "cells": [
                    {"id": "b1", "phase": "p1", "label": "B1"},
                    {"id": "b2", "phase": "p2", "label": "B2"}]},
            ],
            "integration": {"label": "Merge"}, "outcome": {"label": "Result"},
            "cross_links": [{"from": "a1", "to": "b2", "label": "check"}],
        }
        plans = plan_views(spec)
        overview = plans[0]
        evidence = next(e for e in overview["source_edges"] if e.get("label") == "check")
        self.assertEqual(["a1", "b2"], evidence["original_endpoints"])
        detail = next(p for p in plans if p["role"] == "detail" and p["title"] == "A")
        self.assertEqual([("a1", "a2")], [(e["from"], e["to"]) for e in detail["spec"]["edges"]])
        self.assertTrue(any(e["to"] == "b2" for e in detail["boundary_edges"]))
        for plan in plans:
            self.assertEqual([], validate_spec(plan["spec"], SKILL))

    def test_cnn_steps_residual_and_projection(self):
        spec = json.loads((SKILL / "assets/examples/cnn-architecture.json").read_text())
        spec["block_detail"]["shortcut"] = {"label": "1×1 projection", "subtitle": "stride 2"}
        plans = plan_views(spec)
        details = [p for p in plans if p["role"] == "detail"]
        edges = {(e["from"], e["to"]) for p in details for e in p["source_edges"] + p["boundary_edges"]}
        self.assertIn(("/block_detail/input", "/block_detail/shortcut"), edges)
        self.assertIn(("/block_detail/shortcut", "/block_detail/add"), edges)
        self.assertIn(("/block_detail/steps/2", "/block_detail/add"), edges)
        self.assertIn(("/block_detail/add", "/block_detail/output"), edges)
        self.assertNotIn(("/block_detail/input", "/block_detail/add"), edges)
        self.assertTrue(all(len(p["spec"]["nodes"]) <= 6 for p in plans[:-1]))
        self.assertEqual(spec["block_detail"]["steps"][0],
                         details[0]["source_objects"]["/block_detail/steps/0"]["source"])
        spec["block_detail"]["residual"] = False
        ids = {n for p in plan_views(spec)[:-1] for n in p["source_ids"]}
        self.assertNotIn("/block_detail/add", ids)
        self.assertNotIn("/block_detail/shortcut", ids)

    def test_framework_items_do_not_invent_edges(self):
        spec = {"version": "1.0", "kind": "diagram.research-framework",
                "framework_stages": [
                    {"id": "a", "title": "A", "items": [{"label": "A1"}, {"label": "A2"}]},
                    {"id": "b", "title": "B", "items": [{"label": "B1"}]}],
                "outcome": {"label": "Result"}, "feedback": {"from": "b", "to": "a"}}
        plans = plan_views(spec)
        self.assertEqual(3, len(plans[0]["spec"]["edges"]))
        self.assertTrue(all(not p["spec"]["edges"] for p in plans if p["role"] == "detail"))

    def test_explicit_media_and_provenance_copy_without_native_dimensions(self):
        spec = graph(3)
        spec["layout"] = {"medium": "paper-double", "width": 2000, "inset_width": 1800}
        plans = plan_views(spec)
        for plan in plans[:-1]:
            self.assertEqual("paper-double", plan["spec"]["layout"]["medium"])
            self.assertNotIn("width", plan["spec"]["layout"])
            self.assertNotIn("inset_width", plan["spec"]["layout"])
            self.assertEqual(spec["provenance"], plan["spec"]["provenance"])
        self.assertEqual("web", plans[-1]["spec"]["layout"]["medium"])
        self.assertEqual("paper-double", plans[-1]["full_source"]["layout"]["medium"])

    def test_unsupported_and_unknown_endpoints_are_explicit(self):
        with self.assertRaisesRegex(ValueError, "unsupported"):
            plan_views({"kind": "chart.line"})
        source = graph(3)
        source["edges"].append({"from": "missing", "to": "n0"})
        with self.assertRaisesRegex(ValueError, "unknown relation endpoint"):
            plan_views(source)


class FigureSetDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.workspace = ROOT / (".figure-set-tests-" + uuid4().hex)
        self.workspace.mkdir()
        self.addCleanup(shutil.rmtree, self.workspace)
        self.source = self.workspace / "source.json"
        self.output = self.workspace / "delivery"
        write_json(self.source, graph(3))

    def fake_render(self, source, output, no_lint):
        shutil.copyfile(source, output / "figure-source.json")
        (output / "figure.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
        write_json(output / "figure-manifest.json", {
            "spec": {"path": "figure-source.json"}, "checks": {"passed": True},
            "outputs": [{"format": "svg", "path": "figure.svg", "sha256": sha256(output / "figure.svg")}],
        })
        return 0

    def assert_links(self, directory):
        links = Links()
        links.feed((directory / "index.html").read_text())
        for path in links.paths:
            self.assertTrue((directory / path).is_file(), path)

    def test_delivery_links_source_and_immutable_history(self):
        render_set(self.source, self.output, self.fake_render)
        first = json.loads((self.output / "figure-set.json").read_text())
        version_dir = self.output / "versions" / first["current_version"]
        first_hashes = {p.relative_to(version_dir): sha256(p) for p in version_dir.rglob("*") if p.is_file()}
        write_json(self.source, graph(5))
        render_set(self.source, self.output, self.fake_render)
        current = json.loads((self.output / "figure-set.json").read_text())
        self.assertEqual(graph(5), current["full_source"])
        self.assertEqual(1, len(current["history"]))
        self.assertEqual(first["current_version"], current["history"][0]["version"])
        for path, digest in first_hashes.items():
            self.assertEqual(digest, sha256(version_dir / path))
        self.assert_links(self.output)
        self.assert_links(version_dir)

    def test_failed_rerender_does_not_advertise_complete_or_replace_current(self):
        render_set(self.source, self.output, self.fake_render)
        before = {p.name: p.read_bytes() for p in self.output.iterdir() if p.is_file()}
        with self.assertRaisesRegex(ValueError, "failed validation"):
            render_set(self.source, self.output, lambda *_: 1)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.output.iterdir() if p.is_file()})
        self.assertFalse(list(self.output.glob(".building-*")))
        failed_output = self.workspace / "failed"
        with self.assertRaises(ValueError):
            render_set(self.source, failed_output, lambda *_: 1)
        self.assertFalse((failed_output / "index.html").exists())
        self.assertFalse((failed_output / "figure-set.json").exists())

    def test_legacy_delivery_schemas_keep_immutable_history(self):
        def gallery_renderer(source, output, no_lint):
            output.mkdir()
            return self.fake_render(source, output, no_lint)

        for name in ("figure-set", "gallery"):
            with self.subTest(name=name):
                output = self.output / name

                def publish():
                    if name == "figure-set":
                        render_set(self.source, output, self.fake_render)
                    else:
                        render_gallery(self.workspace, output, gallery_renderer)

                publish()
                path = output / f"{name}.json"
                legacy = json.loads(path.read_text())
                legacy["schema"] = f"vizweaver.{name}/1"
                write_json(path, legacy)
                history = {p: sha256(p) for p in output.rglob("*")
                           if p.is_file() and p.parent != output}
                publish()
                self.assertEqual(f"figurecraft.{name}/1", json.loads(path.read_text())["schema"])
                for artifact, digest in history.items():
                    self.assertEqual(digest, sha256(artifact))
                self.assert_links(output)

    def test_unverified_view_is_not_published_even_when_renderer_returns_zero(self):
        def unchecked(source, output, no_lint):
            self.fake_render(source, output, no_lint)
            manifest = json.loads((output / "figure-manifest.json").read_text())
            manifest["checks"] = None
            write_json(output / "figure-manifest.json", manifest)
            return 0

        with self.assertRaisesRegex(ValueError, "not verified complete"):
            render_set(self.source, self.output, unchecked)
        self.assertFalse((self.output / "index.html").exists())

    def test_untracked_index_and_symlinks_are_not_overwritten(self):
        self.output.mkdir()
        (self.output / "index.html").write_text("User data")
        with self.assertRaisesRegex(ValueError, "untracked"):
            render_set(self.source, self.output, self.fake_render)
        self.assertEqual("User data", (self.output / "index.html").read_text())
        (self.output / "index.html").unlink()
        (self.output / "versions").symlink_to(self.workspace, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            render_set(self.source, self.output, self.fake_render)

    def test_html_escapes_all_user_labels(self):
        payload = {"title": '<script>alert("bad")</script>', "source": "full source.json",
                   "manifest": "figure-set.json", "status": "complete", "views": [],
                   "provenance": {"summary": '<img src=x onerror="bad">', "sources": ["javascript:alert(1)"]},
                   "assumptions": ["<b>Not trusted</b>"]}
        page = delivery_html(payload)
        self.assertNotIn("<script>", page)
        self.assertNotIn("<img src=x", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn('href="full%20source.json"', page)
        self.assertNotIn('href="javascript:', page)

    def test_actual_generic_render_set_and_single_index(self):
        self.assertEqual(0, main(["render-set", str(self.source), "--output", str(self.output)]))
        self.assert_links(self.output)
        single = self.workspace / "single"
        self.assertEqual(0, main(["render", str(self.source), "--output", str(single)]))
        self.assertIn("Medium unspecified", (single / "index.html").read_text())
        self.assert_links(single)
        no_lint = self.workspace / "unverified"
        self.assertEqual(0, main(["render", str(self.source), "--output", str(no_lint), "--no-lint"]))
        self.assertIn("not a completed delivery", (no_lint / "index.html").read_text())

    def test_cli_environment_options_and_readiness_exit(self):
        report = {"ready": False, "capabilities": {}, "dependencies": {}, "issues": [], "remedies": []}
        with patch("figurelib.environment.environment_report", return_value=report) as probe:
            self.assertEqual(1, main(["check-env", "--format", "svg", "--format", "pdf",
                                      "--kind", "diagram.architecture", "--cjk", "--json"]))
            probe.assert_called_once_with(formats=["svg", "pdf"], kind="diagram.architecture", check_cjk=True)

    def test_cli_environment_documented_aliases(self):
        report = {"ready": True, "capabilities": {}, "dependencies": {}, "issues": [], "remedies": []}
        with patch("figurelib.environment.environment_report", return_value=report) as probe:
            self.assertEqual(0, main(["check-env", "--formats", "svg", "drawio",
                                      "--check-cjk", "--json"]))
            probe.assert_called_once_with(formats=["svg", "drawio"], kind="diagram.architecture", check_cjk=True)

    def test_environment_entry_does_not_import_renderers(self):
        code = (
            f"import sys; sys.path.insert(0, {str(SKILL / 'scripts')!r}); "
            "import figurelib.cli; "
            "assert 'figurelib.diagrams' not in sys.modules; "
            "assert 'figurelib.charts' not in sys.modules; "
            "assert 'figurelib.delivery' not in sys.modules"
        )
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_revision_rejects_same_base_and_nonempty_output_before_rendering(self):
        self.output.mkdir()
        base = self.output / "figure-manifest.json"
        base.write_text("{}")
        with patch("figurelib.revision.prepare_revision") as prepare:
            self.assertEqual(2, main(["revise", str(base), str(self.source),
                                      "--output", str(self.output), "--mode", "reflow"]))
            self.assertEqual(2, main(["revise", str(base), str(self.source),
                                      "--output", str(self.workspace), "--mode", "reflow"]))
            prepare.assert_not_called()

    def test_cli_revision_preserves_changed_natural_width_footer_and_second_revision(self):
        spec = graph(3)
        spec["nodes"][0].update(label="An intentionally wide source operation", visual_height=140)
        write_json(self.source, spec)
        self.assertEqual(0, main(["render", str(self.source), "--output", str(self.output)]))
        base = self.output / "figure-manifest.json"
        original_manifest = base.read_bytes()
        expected = json.loads(original_manifest)
        first_box = next(box for box in expected["geometry"] if box["id"] == "n0")
        self.assertGreater(first_box["width"], 132)
        self.assertEqual(140, first_box["height"])
        for index, label in enumerate(("A", "B"), 1):
            spec["nodes"][0]["label"] = label
            updated = self.workspace / f"revision-{index}.json"
            destination = self.workspace / f"revision-{index}"
            write_json(updated, spec)
            self.assertEqual(0, main(["revise", str(base), str(updated), "--mode", "content-only",
                                      "--output", str(destination)]))
            revised = json.loads((destination / "figure-manifest.json").read_text())
            self.assertEqual(expected["geometry"], revised["geometry"])
            self.assertEqual(expected["engine"]["canvas"], revised["engine"]["canvas"])
            self.assertEqual(expected["engine"]["edges"], revised["engine"]["edges"])
            self.assertEqual("content-only", revised["revision"]["mode"])
            base = destination / "figure-manifest.json"
        self.assertEqual(original_manifest, (self.output / "figure-manifest.json").read_bytes())

    def test_current_diagram_examples_deliver_complete_links(self):
        for source in sorted((SKILL / "assets/examples").glob("*.json")):
            if not json.loads(source.read_text())["kind"].startswith("diagram."):
                continue
            with self.subTest(name=source.name):
                destination = self.workspace / source.stem
                self.assertEqual(0, main(["render-set", str(source),
                                          "--output", str(destination)]))
                self.assert_links(destination)
                payload = json.loads((destination / "figure-set.json").read_text())
                for view in payload["views"]:
                    metadata = json.loads((destination / view["metadata"]).read_text())
                    self.assertEqual(payload["full_source"], metadata["full_source"])

    def test_requested_media_passes_actual_final_size_checks(self):
        for medium in ("paper-single", "paper-double", "slide"):
            with self.subTest(medium=medium):
                spec = json.loads((SKILL / "assets/examples/cnn-architecture.json").read_text())
                spec["layout"]["medium"] = medium
                source = self.workspace / f"{medium}.json"
                write_json(source, spec)
                destination = self.workspace / medium
                self.assertEqual(0, main(["render-set", str(source), "--output", str(destination)]))
                payload = json.loads((destination / "figure-set.json").read_text())
                for view in payload["views"]:
                    manifest = json.loads((destination / view["manifest"]).read_text())
                    self.assertTrue(manifest["checks"]["passed"])
                    actual = json.loads((destination / view["source"]).read_text())
                    self.assertEqual("web" if view["role"] == "reference" else medium, actual["layout"]["medium"])

    def test_concurrent_or_untracked_lock_is_retained(self):
        self.output.mkdir()
        lock = self.output / ".figure-set.lock"
        lock.write_text("another publisher")
        with self.assertRaisesRegex(ValueError, "already publishing"):
            render_set(self.source, self.output, self.fake_render)
        self.assertEqual("another publisher", lock.read_text())

    def test_publication_checks_entrance_again_after_rendering(self):
        render_set(self.source, self.output, self.fake_render)
        original = self.fake_render
        modified = False

        def concurrent_edit(source, output, no_lint):
            nonlocal modified
            if not modified:
                (self.output / "index.html").write_text("Manual update")
                modified = True
            return original(source, output, no_lint)

        with self.assertRaisesRegex(ValueError, "changed during rendering"):
            render_set(self.source, self.output, concurrent_edit)
        self.assertEqual("Manual update", (self.output / "index.html").read_text())

    def test_gallery_cli_renders_every_example_with_svg_only(self):
        self.assertEqual(0, main(["gallery", "--output", str(self.output)]))
        self.assert_links(self.output)
        payload = json.loads((self.output / "gallery.json").read_text())
        self.assertEqual(len(list((SKILL / "assets/examples").glob("*.json"))), len(payload["examples"]))
        self.assertEqual(0, payload["failed"])
        for entry in payload["examples"]:
            original = SKILL / "assets/examples" / entry["filename"]
            self.assertEqual(original.read_bytes(), (self.output / entry["original_source"]).read_bytes())
            preview = json.loads((self.output / entry["preview_source"]).read_text())
            self.assertEqual({"primary": "svg", "additional": []}, preview["output"])
            self.assertEqual("web", preview["layout"]["medium"])
            self.assertNotEqual(entry["original_source"], entry["preview_source"])
            manifest = json.loads((self.output / entry["manifest"]).read_text())
            self.assertEqual(["svg"], [item["format"] for item in manifest["outputs"]])
            source = json.loads(original.read_text())
            self.assertEqual(source.get("provenance", {}).get("type", "unspecified"), entry["provenance"]["type"])
        page = (self.output / "index.html").read_text()
        if any(entry["provenance"]["type"] == "unspecified" for entry in payload["examples"]):
            self.assertIn("Source basis unspecified", page)
        self.assertIn("Conceptual illustration", page)
        self.assertEqual(len(payload["examples"]), page.count("<img "))

    def test_gallery_keeps_original_export_settings_and_prior_runs(self):
        spec = graph(3)
        spec.update(title="<script>Unsafe title</script>", output={"primary": "png", "additional": ["pdf"]})
        spec["layout"] = {"medium": "paper-double", "width_mm": 180, "min_font_pt": 9}
        write_json(self.source, spec)

        def renderer(source, output, no_lint):
            self.assertEqual({"primary": "svg", "additional": []}, json.loads(source.read_text())["output"])
            output.mkdir()
            return self.fake_render(source, output, no_lint)

        first = render_gallery(self.workspace, self.output, renderer)
        self.assertEqual(0, first["failed"])
        entry = first["examples"][0]
        self.assertEqual(spec, json.loads((self.output / entry["original_source"]).read_text()))
        page = (self.output / "index.html").read_text()
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)
        digest = sha256(self.output / entry["svg"])
        second = render_gallery(self.workspace, self.output, renderer)
        self.assertNotEqual(first["run_id"], second["run_id"])
        self.assertEqual(digest, sha256(self.output / entry["svg"]))
        self.assert_links(self.output)

    def test_gallery_missing_cjk_is_visible_and_not_success(self):
        spec = graph(3)
        spec.update(title="中文案例", language="zh-CN")
        write_json(self.source, spec)
        renderer = Mock()
        with patch("figurelib.environment.environment_report",
                   return_value={"capabilities": {"cjk-text": {"available": False}}}):
            payload = render_gallery(self.workspace, self.output, renderer)
        renderer.assert_not_called()
        self.assertEqual("partial", payload["status"])
        self.assertEqual(1, payload["failed"])
        page = (self.output / "index.html").read_text()
        self.assertIn("Preview unavailable", page)
        self.assertIn("Noto Sans CJK SC", page)
        self.assertNotIn("<img ", page)
        self.assert_links(self.output)
        with patch("figurelib.delivery.render_gallery", return_value=payload):
            self.assertEqual(1, main(["gallery", "--output", str(self.output)]))

    def test_gallery_never_invents_missing_provenance(self):
        spec = graph(3)
        del spec["provenance"]
        write_json(self.source, spec)

        def renderer(source, output, no_lint):
            output.mkdir()
            return self.fake_render(source, output, no_lint)

        payload = render_gallery(self.workspace, self.output, renderer)
        self.assertEqual("unspecified", payload["examples"][0]["provenance"]["type"])
        self.assertIn("Source basis unspecified", (self.output / "index.html").read_text())

    def test_gallery_refuses_untracked_index(self):
        self.output.mkdir()
        (self.output / "index.html").write_text("User page")
        with self.assertRaisesRegex(ValueError, "untracked"):
            render_gallery(self.workspace, self.output, self.fake_render)
        self.assertEqual("User page", (self.output / "index.html").read_text())


if __name__ == "__main__":
    unittest.main()
