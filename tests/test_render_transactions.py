from __future__ import annotations

import copy
import io
import os
import shutil
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/figurecraft/scripts"))

from figurelib.cli import _render, main
from figurelib.io import load_spec, sha256, write_json
from figurelib.lint import lint_manifest
from figurelib.transactions import reject_symlinks


class RenderTransactionTests(unittest.TestCase):
    def setUp(self):
        self.workspace = ROOT / f".render-transactions-{uuid4().hex}"
        self.workspace.mkdir()
        self.addCleanup(shutil.rmtree, self.workspace)
        self.source = self.workspace / "original.json"
        self.output = self.workspace / "bundle"
        self.spec = {
            "version": "1.0", "kind": "diagram.architecture",
            "nodes": [{"id": "a", "label": "Stable baseline"}],
            "output": {"primary": "svg", "additional": ["png", "pdf", "drawio"]},
        }
        self.enterContext(redirect_stdout(io.StringIO()))

    def render(self, spec=None, source=None, output=None, no_lint=False):
        source = source or self.source
        if spec is not None:
            write_json(source, spec)
        return _render(source, output or self.output, no_lint)

    def hashes(self):
        return {str(path.relative_to(self.output)): sha256(path)
                for path in self.output.rglob("*") if path.is_file() and not path.is_symlink()}

    def baseline(self):
        self.assertEqual(0, self.render(self.spec))
        manifest = load_spec(self.output / "figure-manifest.json")
        self.assertTrue(manifest["checks"]["passed"])
        self.assertTrue((self.output / "figure.png").read_bytes().startswith(b"\x89PNG"))
        self.assertTrue((self.output / "figure.pdf").read_bytes().startswith(b"%PDF"))
        return self.hashes()

    def assert_clean(self):
        self.assertFalse((self.output / ".figure-render.lock").exists())
        self.assertFalse(list(self.output.glob(".figure-stage-*")))

    def test_legacy_brand_manifest_rerenders_with_new_name(self):
        self.baseline()
        path = self.output / "figure-manifest.json"
        legacy = load_spec(path)
        legacy["skill"]["name"] = "vizweaver"
        write_json(path, legacy)
        self.spec["nodes"][0]["label"] = "Renamed renderer"
        self.assertEqual(0, self.render(self.spec))
        current = load_spec(path)
        self.assertEqual("figurecraft", current["skill"]["name"])
        self.assertTrue(current["checks"]["passed"])
        self.assert_clean()

    def test_cairo_failure_keeps_every_previous_artifact(self):
        before = self.baseline()
        self.spec["nodes"][0]["label"] = "Updated artifact"
        for exporter in ("svg2png", "svg2pdf"):
            with self.subTest(exporter=exporter), patch(f"cairosvg.{exporter}", side_effect=OSError("forced Cairo failure")):
                with self.assertRaisesRegex(OSError, "forced Cairo failure"):
                    self.render(self.spec)
            self.assertEqual(before, self.hashes())
            self.assert_clean()

    def test_missing_glyph_and_final_size_failure_keep_previous_bundle(self):
        before = self.baseline()
        invalid = copy.deepcopy(self.spec)
        invalid["nodes"][0]["label"] = "Unsupported \u0378"
        with self.assertRaisesRegex(ValueError, "Missing font glyph"):
            self.render(invalid)
        self.assertEqual(before, self.hashes())
        invalid = copy.deepcopy(self.spec)
        invalid["layout"] = {"medium": "paper-single", "width_mm": 1}
        with self.assertRaisesRegex(ValueError, "font|text|readab|render-set"):
            self.render(invalid)
        self.assertEqual(before, self.hashes())
        self.assert_clean()

    def test_lint_failure_does_not_publish_but_no_lint_is_explicit(self):
        before = self.baseline()
        self.spec["nodes"][0]["label"] = "Changed"
        failure = {"passed": False, "failures": ["forced lint failure"], "warnings": []}
        with patch("figurelib.cli.lint_manifest", return_value=failure), redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(1, self.render(self.spec))
        self.assertIn("forced lint failure", errors.getvalue())
        self.assertEqual(before, self.hashes())
        with patch("figurelib.cli.lint_manifest", side_effect=AssertionError("lint was requested")):
            self.assertEqual(0, self.render(no_lint=True))
        self.assertIsNone(load_spec(self.output / "figure-manifest.json")["checks"])
        self.assertIn("not a completed delivery", (self.output / "index.html").read_text())
        self.assert_clean()

    def test_first_failure_returns_error_without_complete_manifest(self):
        write_json(self.source, self.spec)
        with patch("cairosvg.svg2pdf", side_effect=OSError("forced Cairo failure")), redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(2, main(["render", str(self.source), "--output", str(self.output)]))
        self.assertIn("forced Cairo failure", errors.getvalue())
        self.assertFalse((self.output / "figure-manifest.json").exists())
        self.assertFalse((self.output / "figure.svg").exists())
        self.assertFalse((self.output / "index.html").exists())
        self.assert_clean()
        self.assertEqual(0, self.render())

    def test_first_lint_failure_does_not_leave_a_manifest(self):
        failure = {"passed": False, "failures": ["lint failed"], "warnings": []}
        with patch("figurelib.cli.lint_manifest", return_value=failure), redirect_stderr(io.StringIO()):
            self.assertEqual(1, self.render(self.spec))
        self.assertFalse((self.output / "figure-manifest.json").exists())
        self.assert_clean()

    def test_external_csv_and_same_folder_source_remain_reusable(self):
        self.output.mkdir()
        original = self.output / "figure-source.json"
        data = self.output / "measurements.csv"
        data.write_text("x,y\n1,3\n2,5\n", encoding="utf-8")
        spec = {"version": "1.0", "kind": "chart.line",
                "data": {"source": "measurements.csv"},
                "series": [{"x": "x", "y": "y"}], "output": {"primary": "svg"}}
        write_json(original, spec)
        original_hash, data_hash = sha256(original), sha256(data)
        self.assertEqual(0, self.render(source=original))
        self.assertEqual(original_hash, sha256(original))
        self.assertEqual(data_hash, sha256(data))
        source = self.output / load_spec(self.output / "figure-manifest.json")["spec"]["path"]
        self.assertEqual("figure-source-bundled.json", source.name)
        source_hash = sha256(source)
        data.unlink()
        self.assertEqual(0, self.render(source=source))
        self.assertEqual(source_hash, sha256(source))
        self.assertEqual(original_hash, sha256(original))
        self.assertEqual(0, self.render(source=source, output=self.workspace / "another"))
        self.assertTrue(lint_manifest(self.output / "figure-manifest.json")["passed"])
        self.assert_clean()

    def test_success_replaces_only_owned_files_and_preserves_unrelated_files(self):
        before = self.baseline()
        notes = self.output / "notes"
        notes.mkdir()
        (notes / "keep.txt").write_text("untouched", encoding="utf-8")
        unrelated = self.output / "research.svg"
        unrelated.write_text("not a generated artifact", encoding="utf-8")
        external = self.workspace / "external"
        external.write_text("outside", encoding="utf-8")
        (self.output / "unrelated-link").symlink_to(external)
        retained = {path: (sha256(path), path.stat().st_ino) for path in (notes / "keep.txt", unrelated, external)}
        self.spec["nodes"][0]["label"] = "A changed successful result"
        self.assertEqual(0, self.render(self.spec))
        self.assertNotEqual(before["figure.svg"], sha256(self.output / "figure.svg"))
        for path, identity in retained.items():
            self.assertEqual(identity, (sha256(path), path.stat().st_ino))
        self.assertTrue((self.output / "unrelated-link").is_symlink())
        self.assertTrue(lint_manifest(self.output / "figure-manifest.json")["passed"])
        self.assert_clean()

    def test_format_roundtrip_removes_stale_exports_and_restores_requested_formats(self):
        before = self.baseline()
        self.spec["nodes"][0]["label"] = "Updated SVG-only content"
        self.spec["output"] = {"primary": "svg"}
        self.assertEqual(0, self.render(self.spec))
        for extension in ("png", "pdf", "drawio"):
            self.assertFalse((self.output / f"figure.{extension}").exists())
        manifest = load_spec(self.output / "figure-manifest.json")
        self.assertEqual(["svg"], [item["format"] for item in manifest["outputs"]])
        self.spec["output"]["additional"] = ["png", "pdf", "drawio"]
        self.assertEqual(0, self.render(self.spec))
        manifest = load_spec(self.output / "figure-manifest.json")
        self.assertEqual({"svg", "png", "pdf", "drawio"}, {item["format"] for item in manifest["outputs"]})
        for item in manifest["outputs"]:
            self.assertEqual(item["sha256"], sha256(self.output / item["path"]))
            self.assertNotEqual(before[item["path"]], item["sha256"])
        self.assertTrue(manifest["checks"]["passed"])
        self.assert_clean()

    def test_obsolete_exports_are_restored_if_manifest_promotion_fails(self):
        before = self.baseline()
        self.spec["nodes"][0]["label"] = "Updated SVG-only content"
        self.spec["output"] = {"primary": "svg"}
        replace = os.replace

        def fail_after_removals(source, destination):
            if Path(source).name == "figure-manifest.json" and Path(source).parent.name.startswith(".figure-stage-"):
                for extension in ("png", "pdf", "drawio"):
                    self.assertFalse((self.output / f"figure.{extension}").exists())
                raise OSError("forced failure after obsolete exports removed")
            return replace(source, destination)

        with patch("figurelib.transactions.os.replace", side_effect=fail_after_removals):
            with self.assertRaisesRegex(OSError, "forced failure after obsolete exports removed"):
                self.render(self.spec)
        self.assertEqual(before, self.hashes())
        self.assert_clean()

    def test_obsolete_manual_edits_symlinks_and_unrelated_exports_are_preserved(self):
        self.baseline()
        modified = self.output / "figure.png"
        modified.write_bytes(b"manually replaced PNG")
        unrelated = self.output / "unrelated.pdf"
        unrelated.write_bytes(b"unrelated export")
        external = self.workspace / "external.drawio"
        external.write_text("outside", encoding="utf-8")
        linked = self.output / "figure.drawio"
        linked.unlink()
        linked.symlink_to(external)
        retained = {path: (sha256(path), path.stat().st_ino) for path in (modified, unrelated, external)}
        self.spec["nodes"][0]["label"] = "Updated SVG-only content"
        self.spec["output"] = {"primary": "svg"}
        self.assertEqual(0, self.render(self.spec))
        self.assertFalse((self.output / "figure.pdf").exists())
        self.assertTrue(linked.is_symlink())
        for path, identity in retained.items():
            self.assertEqual(identity, (sha256(path), path.stat().st_ino))
        self.assert_clean()

    def test_modified_output_or_delivery_is_not_silently_overwritten(self):
        self.baseline()
        self.spec["nodes"][0]["label"] = "A new result"
        for name in ("figure.svg", "figure-source.json", "index.html"):
            with self.subTest(name=name):
                path = self.output / name
                original = path.read_bytes()
                path.write_bytes(original + b"\nmanual edit")
                before = self.hashes()
                with self.assertRaisesRegex(ValueError, "modified|untracked"):
                    self.render(self.spec)
                self.assertEqual(before, self.hashes())
                path.write_bytes(original)
                self.assert_clean()

    def test_untracked_reserved_artifact_is_not_overwritten(self):
        self.output.mkdir()
        path = self.output / "figure.svg"
        path.write_text("user owned", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "untracked"):
            self.render(self.spec)
        self.assertEqual({"figure.svg": sha256(path)}, self.hashes())
        self.assert_clean()

    def test_legacy_bundle_can_be_replaced_without_trusting_modified_index(self):
        self.baseline()
        manifest_path = self.output / "figure-manifest.json"
        manifest = load_spec(manifest_path)
        manifest.pop("generated_files")
        write_json(manifest_path, manifest)
        index = self.output / "index.html"
        original = index.read_bytes()
        index.write_bytes(original + b"\nmanual edit")
        before = self.hashes()
        self.spec["title"] = "Updated title"
        with self.assertRaisesRegex(ValueError, "modified delivery"):
            self.render(self.spec)
        self.assertEqual(before, self.hashes())
        index.write_bytes(original)
        self.assertEqual(0, self.render(self.spec))
        self.assertIn("generated_files", load_spec(manifest_path))
        self.assert_clean()

    def test_malformed_existing_manifest_is_a_clean_cli_error(self):
        self.output.mkdir()
        write_json(self.source, self.spec)
        manifest = self.output / "figure-manifest.json"
        write_json(manifest, {"skill": "not a valid manifest"})
        before = self.hashes()
        with redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(2, main(["render", str(self.source), "--output", str(self.output)]))
        self.assertIn("untracked manifest", errors.getvalue())
        self.assertEqual(before, self.hashes())
        self.assert_clean()

    def test_symlink_output_and_source_are_rejected(self):
        self.baseline()
        original = self.workspace / "outside.svg"
        original.write_text("outside", encoding="utf-8")
        (self.output / "figure.svg").unlink()
        (self.output / "figure.svg").symlink_to(original)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.render()
        self.assertEqual("outside", original.read_text())
        linked_output = self.workspace / "linked-output"
        linked_output.symlink_to(self.output, target_is_directory=True)
        with redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(2, main(["render", str(self.source), "--output", str(linked_output)]))
        self.assertIn("symlink", errors.getvalue())
        linked_source = self.workspace / "linked.json"
        linked_source.symlink_to(self.source)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.render(source=linked_source)
        self.assert_clean()

    @unittest.skipUnless(sys.platform == "darwin", "macOS system directory aliases")
    def test_real_macos_var_alias_works_without_allowing_output_symlinks(self):
        self.assertTrue(Path("/var").is_symlink())
        self.assertEqual(Path("/private/var"), Path("/var").resolve())
        write_json(self.source, self.spec)
        # Exercise the real OS alias while keeping every written file inside the repository.
        prefix = Path("/var/../..")
        source = prefix / self.source.relative_to("/")
        output = prefix / self.output.relative_to("/")
        self.assertEqual(0, main(["render", str(source), "--output", str(output)]))
        self.assertTrue(lint_manifest(self.output / "figure-manifest.json")["passed"])
        before = self.hashes()
        linked = self.workspace / "linked-output"
        linked.symlink_to(self.output, target_is_directory=True)
        with redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(2, main(["render", str(source), "--output", str(prefix / linked.relative_to("/"))]))
        self.assertIn("symlink", errors.getvalue())
        self.assertEqual(before, self.hashes())
        self.assert_clean()

    @unittest.skipUnless(sys.platform == "darwin", "macOS system directory aliases")
    def test_system_alias_requires_exact_expected_destination(self):
        readlink = Path.readlink

        def wrong_destination(path):
            return Path("/private/unexpected") if path == Path("/var") else readlink(path)

        with patch.object(Path, "readlink", wrong_destination):
            with self.assertRaisesRegex(ValueError, "symlink"):
                reject_symlinks(Path("/var"))
        imitation = self.workspace / "var"
        imitation.symlink_to("/private/var", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            reject_symlinks(imitation)
        with patch("figurelib.transactions.sys.platform", "linux"):
            with self.assertRaisesRegex(ValueError, "symlink"):
                reject_symlinks(Path("/var"))

    def test_concurrent_render_reports_lock_without_disturbing_owner(self):
        from figurelib.diagrams import render_diagram
        write_json(self.source, self.spec)

        def competing_render(*args, **kwargs):
            with redirect_stderr(io.StringIO()) as errors:
                self.assertEqual(2, main(["render", str(self.source), "--output", str(self.output)]))
            self.assertIn("already rendering", errors.getvalue())
            self.assertTrue((self.output / ".figure-render.lock").exists())
            return render_diagram(*args, **kwargs)

        with patch("figurelib.diagrams.render_diagram", side_effect=competing_render):
            self.assertEqual(0, self.render())
        self.assert_clean()

    def test_output_edit_during_render_is_a_conflict(self):
        self.baseline()
        path = self.output / "figure.svg"
        preserved = self.hashes()

        def lint_and_edit(manifest):
            result = lint_manifest(manifest)
            path.write_text("concurrent manual edit", encoding="utf-8")
            return result

        with patch("figurelib.cli.lint_manifest", side_effect=lint_and_edit):
            with self.assertRaisesRegex(ValueError, "changed during render"):
                self.render()
        preserved["figure.svg"] = sha256(path)
        self.assertEqual(preserved, self.hashes())
        self.assert_clean()

    def test_promotion_failure_restores_every_old_artifact(self):
        before = self.baseline()
        self.spec["nodes"][0]["label"] = "Replacement"
        replace = os.replace

        def fail_manifest(source, destination):
            if Path(source).name == "figure-manifest.json" and Path(source).parent.name.startswith(".figure-stage-"):
                raise OSError("forced promotion failure")
            return replace(source, destination)

        with patch("figurelib.transactions.os.replace", side_effect=fail_manifest):
            with self.assertRaisesRegex(OSError, "forced promotion failure"):
                self.render(self.spec)
        self.assertEqual(before, self.hashes())
        self.assert_clean()

    def test_symlink_inserted_during_promotion_is_not_followed(self):
        before = self.baseline()
        external = self.workspace / "external"
        external.write_text("outside", encoding="utf-8")
        replace = os.replace
        injected = False

        def insert_symlink(source, destination):
            nonlocal injected
            if not injected and Path(destination).parent == self.output and Path(destination).name == "figure.drawio":
                injected = True
                target = self.output / "figure.pdf"
                target.unlink()
                target.symlink_to(external)
            return replace(source, destination)

        self.spec["nodes"][0]["label"] = "Replacement"
        with patch("figurelib.transactions.os.replace", side_effect=insert_symlink):
            with self.assertRaisesRegex(ValueError, "symlink"):
                self.render(self.spec)
        self.assertEqual("outside", external.read_text())
        for name, digest in before.items():
            if name != "figure.pdf":
                self.assertEqual(digest, sha256(self.output / name))
        self.assertTrue((self.output / "figure.pdf").is_symlink())
        self.assert_clean()


if __name__ == "__main__":
    unittest.main()
