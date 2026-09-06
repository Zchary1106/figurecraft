from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/figurecraft/scripts"))

from figurelib import environment

_INSTALL_SPEC = importlib.util.spec_from_file_location("figurecraft_installer", ROOT / "install.py")
installer = importlib.util.module_from_spec(_INSTALL_SPEC)
_INSTALL_SPEC.loader.exec_module(installer)


class EnvironmentTests(unittest.TestCase):
    def setUp(self) -> None:
        for name in ("_matplotlib_probe", "_chart_probe", "_cairo_probe", "_conversion_probe"):
            self.enterContext(patch.object(environment, name))
        self.enterContext(patch.object(environment, "measure_text", return_value=10))
        self.enterContext(patch.object(environment.importlib, "import_module", return_value=Mock()))
        self.enterContext(patch.object(environment.importlib.metadata, "version", return_value="1.0"))

    def test_baseline_does_not_require_optional_exports_or_cjk(self) -> None:
        environment._conversion_probe.side_effect = OSError("secret value must not be exposed")
        environment._cairo_probe.side_effect = OSError("secret")
        environment.measure_text.side_effect = lambda text, size: (
            10 if text == "FigureCraft" else self._missing_glyph()
        )
        report = environment.environment_report()
        self.assertTrue(report["ready"])
        self.assertFalse(report["capabilities"]["diagram.png"]["available"])
        self.assertFalse(report["capabilities"]["cjk-text"]["available"])
        self.assertNotIn("secret", json.dumps(report))
        self.assertIn("/opt/homebrew/lib/libcairo.2.dylib", " ".join(report["remedies"]))

    @staticmethod
    def _missing_glyph():
        raise ValueError("Missing font glyph")

    def test_requested_diagram_conversion_failure_blocks_readiness(self) -> None:
        environment._conversion_probe.side_effect = lambda extension: (
            self._missing_glyph() if extension == "png" else None
        )
        png = environment.environment_report(["png"])
        self.assertFalse(png["ready"])
        self.assertTrue(environment.environment_report(["pdf"])["ready"])
        self.assertTrue(png["dependencies"]["cairosvg"]["available"])
        self.assertTrue(png["dependencies"]["native-cairo"]["available"])
        self.assertFalse(png["dependencies"]["cairo-png"]["available"])

    def test_chart_png_pdf_and_gantt_do_not_require_cairo(self) -> None:
        environment._cairo_probe.side_effect = OSError("native library missing")
        environment._conversion_probe.side_effect = OSError("native library missing")
        for kind in ("chart.line", "project.gantt"):
            self.assertTrue(environment.environment_report(["png", "pdf"], kind)["ready"])
        self.assertFalse(environment.environment_report(["png", "pdf"])["ready"])

    def test_chart_export_smoke_failure_is_required(self) -> None:
        environment._chart_probe.side_effect = RuntimeError("export broken")
        self.assertFalse(environment.environment_report(["pdf"], "chart.line")["ready"])
        self.assertTrue(environment.environment_report(["drawio"])["ready"])

    def test_cjk_is_required_only_when_requested(self) -> None:
        environment.measure_text.side_effect = lambda text, size: (
            10 if text == "FigureCraft" else self._missing_glyph()
        )
        self.assertTrue(environment.environment_report()["ready"])
        report = environment.environment_report(check_cjk=True)
        self.assertFalse(report["ready"])
        self.assertIn("fonts-noto-cjk", " ".join(report["remedies"]))

    def test_installed_metadata_does_not_hide_broken_import(self) -> None:
        environment.importlib.import_module.side_effect = ImportError("broken native module")
        report = environment.environment_report(["svg", "drawio"])
        self.assertEqual(report["dependencies"]["jsonschema"]["version"], "1.0")
        self.assertFalse(report["dependencies"]["jsonschema"]["available"])
        self.assertFalse(report["ready"])
        self.assertIn(environment._pip("matplotlib>=3.8", "numpy>=1.26", "jsonschema>=4.20"),
                      report["remedies"])

    def test_diagram_svg_drawio_require_measured_font_runtime(self) -> None:
        environment.measure_text.side_effect = ImportError("matplotlib font runtime failed")
        for extension in ("svg", "drawio"):
            self.assertFalse(environment.environment_report([extension])["ready"])

    def test_matplotlib_failure_blocks_every_pipeline(self) -> None:
        environment._matplotlib_probe.side_effect = ImportError("numpy ABI mismatch")
        self.assertFalse(environment.environment_report(["svg"])["ready"])
        self.assertFalse(environment.environment_report(["png"], "chart.line")["ready"])

    def test_deterministic_json_and_no_environment_changes(self) -> None:
        before = dict(os.environ)
        report = environment.environment_report(["png", "svg", "png"])
        self.assertEqual(report, environment.environment_report(["svg", "png"]))
        self.assertEqual(report, json.loads(json.dumps(report)))
        self.assertEqual(before, dict(os.environ))
        self.assertIn("ready=yes", environment.format_environment_report(report))

    def test_unsupported_formats_and_kind(self) -> None:
        with self.assertRaises(ValueError):
            environment.environment_report(["drawio"], "chart.line")
        with self.assertRaises(ValueError):
            environment.environment_report(["jpg"])
        with self.assertRaises(ValueError):
            environment.environment_report(kind="invalid")


class InstallerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = self.enterContext(tempfile.TemporaryDirectory(dir=ROOT, prefix=".install-test-"))
        self.root = Path(self.folder)
        self.source = self.root / "source"
        self.project = self.root / "project"
        self.enterContext(patch.object(installer, "__file__", str(self.source / "install.py")))
        self.enterContext(patch.object(installer, "SKILL_NAMES", ("figurecraft", "specialist")))
        for name in installer.SKILL_NAMES:
            skill = self.source / "skills" / name
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("new version", encoding="utf-8")

    def install(self, force=False):
        return installer.install("copilot", "project", self.project, force)

    def test_nonforce_existing_copies_remain_unchanged(self) -> None:
        destinations = self.install()
        marker = destinations[0] / "custom.txt"
        marker.write_text("local changes")
        with self.assertRaises(FileExistsError):
            self.install()
        self.assertEqual(marker.read_text(), "local changes")
        self.assertFalse((destinations[0].parent / ".figurecraft-backups").exists())

    def test_force_preserves_modified_copy_in_backup(self) -> None:
        destinations = self.install()
        (destinations[0] / "SKILL.md").write_text("local changes")
        (destinations[0] / "custom.txt").write_text("must survive")
        self.install(force=True)
        self.assertEqual((destinations[0] / "SKILL.md").read_text(), "new version")
        backups = list((destinations[0].parent / ".figurecraft-backups").iterdir())
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / "figurecraft/SKILL.md").read_text(), "local changes")
        self.assertEqual((backups[0] / "figurecraft/custom.txt").read_text(), "must survive")
        self.assertFalse(list(destinations[0].parent.glob(".figurecraft-stage-*")))

    def test_copy_failure_does_not_replace_any_copy(self) -> None:
        destinations = self.install()
        (destinations[0] / "SKILL.md").write_text("local changes")
        original = installer.shutil.copytree

        def fail_second(source, target, **kwargs):
            if Path(source).name == "specialist":
                raise OSError("simulated full disk")
            return original(source, target, **kwargs)

        with patch.object(installer.shutil, "copytree", side_effect=fail_second):
            with self.assertRaises(OSError):
                self.install(force=True)
        self.assertEqual((destinations[0] / "SKILL.md").read_text(), "local changes")
        self.assertEqual((destinations[1] / "SKILL.md").read_text(), "new version")
        self.assertFalse(list(destinations[0].parent.glob(".figurecraft-stage-*")))

    def test_rename_failure_rolls_back_all_replacements(self) -> None:
        destinations = self.install()
        for destination in destinations:
            (destination / "SKILL.md").write_text("local changes")
        rename = Path.rename

        def fail_second(path, target):
            if path.parent.name.startswith(".figurecraft-stage-") and path.name == "specialist":
                raise OSError("simulated replacement error")
            return rename(path, target)

        with patch.object(Path, "rename", fail_second):
            with self.assertRaises(OSError):
                self.install(force=True)
        for destination in destinations:
            self.assertEqual((destination / "SKILL.md").read_text(), "local changes")

    def test_self_install_and_nested_source_targets_rejected(self) -> None:
        for target in (self.source / "skills", self.source / "skills/figurecraft/nested"):
            with patch.dict(installer.USER_LOCATIONS, {"copilot": target}):
                with self.assertRaises(ValueError):
                    installer.install("copilot", "user", self.project, True)
        self.assertEqual((self.source / "skills/figurecraft/SKILL.md").read_text(), "new version")

    def test_symlink_destination_does_not_modify_external_copy(self) -> None:
        target = self.project / ".github/skills"
        target.mkdir(parents=True)
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "keep").write_text("safe")
        (target / "figurecraft").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.install(force=True)
        self.assertEqual((outside / "keep").read_text(), "safe")

    def test_each_host_location(self) -> None:
        for agent, relative in installer.PROJECT_LOCATIONS.items():
            destinations = installer.install(agent, "project", self.project, False)
            self.assertEqual(destinations[0].parent, self.project / relative)
            user_target = self.root / "user" / agent
            with patch.dict(installer.USER_LOCATIONS, {agent: user_target}):
                user_copies = installer.install(agent, "user", self.project, False)
            self.assertEqual(user_copies[0].parent, user_target)

    def test_invalid_scope_does_not_fall_back_to_user_install(self) -> None:
        with self.assertRaises(ValueError):
            installer.install("copilot", "typo", self.project, False)


class RuntimeProbeTests(unittest.TestCase):
    def test_windows_remediation_is_a_powershell_command(self) -> None:
        with patch.object(sys, "platform", "win32"), patch.object(
                sys, "executable", r"C:\User's Python\python.exe"):
            self.assertEqual(
                environment._pip("CairoSVG>=2.7"),
                r"& 'C:\User''s Python\python.exe' '-m' 'pip' 'install' '--upgrade' 'CairoSVG>=2.7'",
            )

    def test_cairo_conversion_checks_real_output_signature(self) -> None:
        cairo = Mock()
        cairo.svg2png.return_value = b"\x89PNG\r\n\x1a\npayload"
        cairo.svg2pdf.return_value = b"%PDF-payload"
        with patch.object(environment.importlib, "import_module", return_value=cairo):
            environment._conversion_probe("png")
            environment._conversion_probe("pdf")
            cairo.svg2png.assert_called_once_with(bytestring=environment._SVG)
            cairo.svg2pdf.assert_called_once_with(bytestring=environment._SVG)
            cairo.svg2png.return_value = b"invalid"
            with self.assertRaises(RuntimeError):
                environment._conversion_probe("png")

    def test_native_cairo_is_used_after_import(self) -> None:
        cairo = Mock()
        cairo.cairo_version_string.side_effect = OSError("shared library failed")
        with patch.object(environment.importlib, "import_module", return_value=cairo):
            self.assertFalse(environment._probe(environment._cairo_probe)["available"])
        cairo.cairo_version_string.assert_called_once()

    def test_font_probe_uses_existing_glyph_measurement(self) -> None:
        with patch.object(environment, "measure_text", side_effect=ValueError("Missing font glyph")) as measure:
            self.assertFalse(environment._probe(
                lambda: environment._font_probe(environment._CJK_SAMPLE)
            )["available"])
        measure.assert_called_once_with(environment._CJK_SAMPLE, 12)


if __name__ == "__main__":
    unittest.main()
