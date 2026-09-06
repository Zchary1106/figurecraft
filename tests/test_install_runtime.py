from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/figurecraft/scripts"))

from figurelib import bootstrap

_SPEC = importlib.util.spec_from_file_location("runtime_installer", ROOT / "install.py")
installer = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(installer)


class RuntimeInstallerTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory(dir=ROOT, prefix=".runtime-test-")))
        self.enterContext(patch("sys.stdout", new_callable=io.StringIO))

    def test_platform_interpreter_paths(self):
        self.assertEqual(self.root / "Scripts/python.exe", installer.runtime_python(self.root, "win32"))
        self.assertEqual(self.root / "bin/python", installer.runtime_python(self.root, "darwin"))

    def test_one_shared_runtime_is_wired_into_all_seven_skills_for_all_hosts(self):
        project = self.root / "project with spaces"
        runtime = {"schema": "figurecraft.runtime/1", "python": sys.executable, "library_dirs": []}
        argv = ["install.py", "--setup", "--scope", "project", "--project", str(project)]
        with patch.object(sys, "argv", argv), patch.object(installer, "prepare_runtime", return_value=runtime) as setup:
            self.assertEqual(installer.main(), 0)
        setup.assert_called_once()
        for relative in installer.PROJECT_LOCATIONS.values():
            base = project / relative
            for name in installer.SKILL_NAMES:
                self.assertTrue((base / name / "SKILL.md").is_file())
            config = base / "figurecraft/scripts/.figurecraft-runtime.json"
            self.assertEqual(json.loads(config.read_text()), runtime)
            command = base / "figurecraft/scripts/figure.py"
            result = subprocess.run([sys.executable, str(command), "--help"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("render", result.stdout)
        self.assertFalse((ROOT / "skills/figurecraft/scripts/.figurecraft-runtime.json").exists())

    def test_all_hosts_are_preflighted_before_setup_or_copying(self):
        project = self.root / "project"
        (project / ".agents/skills/figurecraft").mkdir(parents=True)
        argv = ["install.py", "--setup", "--project", str(project)]
        with patch.object(sys, "argv", argv), patch.object(installer, "prepare_runtime") as setup:
            with self.assertRaises(FileExistsError):
                installer.main()
        setup.assert_not_called()
        self.assertFalse((project / ".claude").exists())
        self.assertFalse((project / ".github").exists())

    def test_copy_only_upgrade_retains_managed_runtime(self):
        runtime = {"schema": "figurecraft.runtime/1", "python": sys.executable, "library_dirs": []}
        installer.install("copilot", "project", self.root, False, runtime)
        installer.install("copilot", "project", self.root, True)
        config = self.root / ".github/skills/figurecraft/scripts/.figurecraft-runtime.json"
        self.assertEqual(json.loads(config.read_text()), runtime)

    def test_runtime_setup_uses_local_project_and_strict_probe(self):
        def create(directory):
            python = installer.runtime_python(directory)
            python.parent.mkdir()
            python.write_text("fake interpreter")

        root = self.root / "runtime with spaces"
        with patch.object(installer.venv, "EnvBuilder") as builder, patch.object(installer.subprocess, "run") as execute:
            builder.return_value.create.side_effect = create
            runtime = installer.prepare_runtime(root, require_export=True)
        builder.assert_called_once_with(with_pip=True)
        commands = [call.args[0] for call in execute.call_args_list]
        self.assertEqual(commands[0], [runtime["python"], "-m", "pip", "install", f"{ROOT}[export]"])
        self.assertEqual(commands[1][-6:], ["check-env", "--formats", "svg", "drawio", "png", "pdf"])
        self.assertTrue(all(call.kwargs["check"] for call in execute.call_args_list))
        directory = Path(runtime["python"]).parent.parent
        self.assertEqual(json.loads((directory / "runtime.json").read_text()), runtime)
        self.assertFalse((directory / "probe.py").exists())

    def test_failed_runtime_setup_preserves_existing_runtime(self):
        root = self.root / "runtimes"
        old = root / "old-runtime"
        old.mkdir(parents=True)
        (old / "keep").write_text("old")
        for failure in (1, 2):
            with self.subTest(command=failure):
                error = subprocess.CalledProcessError(1, ["pip" if failure == 1 else "probe"])
                effects = [error] if failure == 1 else [Mock(), error]
                with patch.object(installer.venv, "EnvBuilder"), patch.object(
                        installer.subprocess, "run", side_effect=effects):
                    with self.assertRaises(subprocess.CalledProcessError):
                        installer.prepare_runtime(root)
                self.assertEqual(list(root.iterdir()), [old])
                self.assertEqual((old / "keep").read_text(), "old")

    def test_invalid_library_path_fails_before_venv_creation(self):
        with patch.object(installer.venv, "EnvBuilder") as builder:
            with self.assertRaisesRegex(ValueError, "Cairo library directory"):
                installer.prepare_runtime(self.root / "runtimes", cairo_dirs=[self.root / "missing"])
        builder.assert_not_called()

    def test_setup_failure_does_not_install_skills(self):
        argv = ["install.py", "--setup", "--project", str(self.root / "project")]
        with patch.object(sys, "argv", argv), patch.object(
                installer, "prepare_runtime", side_effect=RuntimeError("probe failed")):
            with self.assertRaisesRegex(RuntimeError, "probe failed"):
                installer.main()
        self.assertFalse((self.root / "project").exists())

    def test_setup_only_flags_are_rejected_without_setup(self):
        for flag in (["--require-export"], ["--runtime-root", "runtime"], ["--cairo-dir", "cairo"]):
            with self.subTest(flag=flag), patch.object(sys, "argv", ["install.py", *flag]), patch(
                    "sys.stderr", new_callable=io.StringIO):
                with self.assertRaises(SystemExit) as error:
                    installer.parse_args()
                self.assertEqual(error.exception.code, 2)

    @unittest.skipUnless(shutil.which("bash") and os.name != "nt", "POSIX launcher")
    def test_shell_launcher_help_from_another_directory(self):
        result = subprocess.run(["bash", str(ROOT / "install.sh"), "--help"], cwd=self.root,
                                env={**os.environ, "FIGURECRAFT_PYTHON": sys.executable},
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--setup", result.stdout)
        self.assertIn("--require-export", result.stdout)

    @unittest.skipUnless(os.name == "nt", "Native Windows launcher")
    def test_powershell_launcher_help_from_another_directory(self):
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "install.ps1"), "--help"],
            cwd=self.root, env={**os.environ, "FIGURECRAFT_PYTHON": sys.executable},
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--setup", result.stdout)


class RuntimeBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory(dir=ROOT, prefix=".bootstrap-test-")))
        self.config = self.root / "runtime.json"

    def write(self, value):
        self.config.write_text(json.dumps(value), encoding="utf-8")

    def test_missing_config_uses_callers_interpreter(self):
        with patch("figurelib.cli.main", return_value=7):
            self.assertEqual(bootstrap.run(self.config), 7)

    def test_matching_interpreter_does_not_relaunch(self):
        self.write({"schema": "figurecraft.runtime/1", "python": sys.executable, "library_dirs": []})
        with patch("figurelib.cli.main", return_value=3), patch.object(bootstrap.subprocess, "run") as launch:
            self.assertEqual(bootstrap.run(self.config), 3)
        launch.assert_not_called()

    def test_dispatch_keeps_arguments_with_spaces_and_exit_code(self):
        python = self.root / "other env" / "python.exe"
        python.parent.mkdir()
        python.touch()
        self.write({"schema": "figurecraft.runtime/1", "python": str(python), "library_dirs": []})
        argv = ["a path/figure.py", "render", "a spec.json", "--output", "output path"]
        with patch.object(sys, "argv", argv), patch.object(
                bootstrap.subprocess, "run", return_value=Mock(returncode=9)) as launch:
            self.assertEqual(bootstrap.run(self.config), 9)
        launch.assert_called_once_with([str(python), *argv], check=False)

    def test_invalid_or_missing_configured_runtime_is_not_silently_ignored(self):
        valid = {"schema": "figurecraft.runtime/1", "python": sys.executable}
        for value in ([], {}, {**valid, "python": "relative/python"},
                      {**valid, "python": str(self.root / "missing")},
                      {**valid, "library_dirs": "wrong"},
                      {**valid, "library_dirs": [str(self.root / "missing")]}):
            with self.subTest(value=value):
                self.write(value)
                with self.assertRaises(ValueError):
                    bootstrap.load_runtime(self.config)

    def test_native_library_configuration_is_process_scoped(self):
        for platform, key in (("darwin", "DYLD_FALLBACK_LIBRARY_PATH"), ("win32", "PATH")):
            with self.subTest(platform=platform), patch.object(sys, "platform", platform), patch.dict(
                    os.environ, {key: "existing"}), patch.object(
                    bootstrap.os, "add_dll_directory", create=True) as add:
                with patch.object(bootstrap, "_DLL_HANDLES", []):
                    bootstrap.configure_libraries([str(self.root)])
                    self.assertEqual(os.environ[key], str(self.root) + os.pathsep + "existing")
                    if platform == "win32":
                        add.assert_called_once_with(str(self.root))
                        self.assertEqual(len(bootstrap._DLL_HANDLES), 1)


if __name__ == "__main__":
    unittest.main()
