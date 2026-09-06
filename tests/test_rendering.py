from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/figurecraft"
CLI = SKILL / "scripts/figure.py"


class FigureCliTests(unittest.TestCase):
    def run_cli(self, *args: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(CLI), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(expected, result.returncode, result.stderr or result.stdout)
        return result

    def render(self, spec: dict) -> tuple[Path, dict]:
        temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, temp, True)
        spec_path = temp / "spec.json"
        output = temp / "output"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")
        self.run_cli("render", str(spec_path), "--output", str(output))
        manifest = json.loads((output / "figure-manifest.json").read_text())
        self.assertTrue(manifest["checks"]["passed"])
        return output, manifest

    def test_validate_example(self) -> None:
        for example in sorted((SKILL / "assets/examples").glob("*.json")):
            with self.subTest(example=example.name):
                self.run_cli("validate", str(example))

    def test_render_line_chart(self) -> None:
        output, manifest = self.render(
            {
                "version": "1.0",
                "kind": "chart.line",
                "data": {"columns": {"x": [1, 2, 3], "a": [2, 4, 5]}},
                "series": [{"x": "x", "y": "a", "label": "A"}],
                "semantics": {"x_label": "Step", "y_label": "Score"},
                "output": {"primary": "svg"},
            }
        )
        self.assertTrue((output / "figure.svg").is_file())
        self.assertEqual("matplotlib", manifest["engine"]["renderer"])
        self.assertNotIn(
            "SVG is missing an accessible description",
            manifest["checks"]["warnings"],
        )

    def test_render_line_uncertainty_band(self) -> None:
        output, _ = self.render(
            {
                "version": "1.0",
                "kind": "chart.line",
                "data": {
                    "columns": {
                        "x": [1, 2, 3],
                        "mean": [2.0, 2.5, 3.0],
                        "low": [1.8, 2.2, 2.7],
                        "high": [2.2, 2.8, 3.3],
                    }
                },
                "series": [
                    {
                        "x": "x",
                        "y": "mean",
                        "lower": "low",
                        "upper": "high",
                        "label": "95% CI",
                    }
                ],
                "semantics": {
                    "uncertainty": "95% confidence interval, analytic"
                },
                "output": {"primary": "svg"},
            }
        )
        self.assertGreater((output / "figure.svg").stat().st_size, 500)

    def test_render_heatmap(self) -> None:
        output, _ = self.render(
            {
                "version": "1.0",
                "kind": "chart.heatmap",
                "data": {
                    "matrix": [[1, 2], [3, 4]],
                    "row_labels": ["A", "B"],
                    "column_labels": ["X", "Y"],
                },
                "style": {"annotate": True},
                "output": {"primary": "svg"},
            }
        )
        self.assertGreater((output / "figure.svg").stat().st_size, 500)

    def test_render_bar_histogram_box_and_errorbar(self) -> None:
        specs = [
            {
                "version": "1.0",
                "kind": "chart.bar",
                "data": {"columns": {"group": ["A", "B"], "score": [3, 5]}},
                "series": [{"x": "group", "y": "score", "label": "Score"}],
                "style": {
                    "annotate_values": True,
                    "legend_location": "top",
                    "annotate_delta": True
                },
                "output": {"primary": "svg"},
            },
            {
                "version": "1.0",
                "kind": "chart.histogram",
                "data": {"columns": {"value": [1, 1, 2, 3, 5, 8]}},
                "series": [{"field": "value", "label": "Value"}],
                "output": {"primary": "svg"},
            },
            {
                "version": "1.0",
                "kind": "chart.box",
                "data": {"columns": {"A": [1, 2, 3], "B": [2, 4, 6]}},
                "output": {"primary": "svg"},
            },
            {
                "version": "1.0",
                "kind": "chart.errorbar",
                "data": {
                    "columns": {
                        "x": [1, 2, 3],
                        "mean": [2.0, 2.5, 3.0],
                        "std": [0.1, 0.2, 0.15],
                    }
                },
                "series": [
                    {"x": "x", "y": "mean", "error": "std", "label": "Mean"}
                ],
                "semantics": {"uncertainty": "standard deviation"},
                "output": {"primary": "svg"},
            },
        ]
        for spec in specs:
            with self.subTest(kind=spec["kind"]):
                output, manifest = self.render(spec)
                self.assertTrue((output / "figure.svg").is_file())
                self.assertEqual(spec["kind"], manifest["kind"])

    def test_render_architecture(self) -> None:
        output, manifest = self.render(
            {
                "version": "1.0",
                "kind": "diagram.architecture",
                "nodes": [
                    {"id": "ui", "label": "Web UI", "layer": 0},
                    {"id": "api", "label": "API", "layer": 1},
                    {"id": "db", "label": "Database", "layer": 2},
                ],
                "edges": [
                    {"from": "ui", "to": "api"},
                    {"from": "api", "to": "db"},
                ],
                "output": {"primary": "svg"},
            }
        )
        svg = (output / "figure.svg").read_text()
        self.assertIn('data-node-id="api"', svg)
        self.assertIn("figure-desc", svg)
        self.assertEqual(3, len(manifest["geometry"]))
        self.assertIn("canvas", manifest["engine"])

    def test_all_technical_diagram_kinds_render(self) -> None:
        for kind in (
            "diagram.flowchart",
            "diagram.algorithm",
            "diagram.architecture",
            "diagram.research-framework",
            "diagram.neural-network",
        ):
            with self.subTest(kind=kind):
                output, manifest = self.render(
                    {
                        "version": "1.0",
                        "kind": kind,
                        "nodes": [
                            {"id": "input", "label": "Input", "layer": 0},
                            {"id": "output", "label": "Output", "layer": 1},
                        ],
                        "edges": [{"from": "input", "to": "output"}],
                        "output": {"primary": "svg"},
                    }
                )
                self.assertTrue((output / "figure.svg").is_file())
                self.assertEqual(kind, manifest["kind"])

    def test_explicit_ports_and_relationship_technology(self) -> None:
        output, _ = self.render(
            {
                "version": "1.0",
                "kind": "diagram.architecture",
                "nodes": [
                    {"id": "client", "label": "Client", "layer": 0},
                    {"id": "api", "label": "API", "layer": 1},
                ],
                "edges": [
                    {
                        "from": "client",
                        "to": "api",
                        "label": "calls",
                        "technology": "HTTPS",
                        "source_port": "E",
                        "target_port": "W",
                    }
                ],
                "layout": {"density": "compact"},
                "output": {"primary": "svg", "additional": ["drawio"]},
            }
        )
        svg = (output / "figure.svg").read_text()
        self.assertIn("calls · HTTPS", svg)
        self.assertIn('data-edge-id="client--api"', svg)
        self.assertTrue((output / "figure.drawio").is_file())

    def test_render_system_landscape(self) -> None:
        example = SKILL / "assets/examples/system-landscape.json"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            self.run_cli("render", str(example), "--output", str(output))
            manifest = json.loads((output / "figure-manifest.json").read_text())
            self.assertTrue(manifest["checks"]["passed"])
            self.assertEqual(3, len(manifest["geometry"]))
            svg = (output / "figure.svg").read_text()
            self.assertIn("Agent Core", svg)
            self.assertIn("Infrastructure", svg)
            self.assertIn('id="shadow-zone"', svg)
            self.assertIn('dominant-baseline="middle"', svg)
            self.assertIn('font-size="11"', svg)
            self.assertIn('data-icon="', svg)
            drawio = output / "figure.drawio"
            self.assertTrue(drawio.is_file())
            drawio_root = ET.parse(drawio).getroot()
            self.assertEqual("mxfile", drawio_root.tag)
            cells = drawio_root.findall(".//mxCell")
            self.assertGreater(
                sum(cell.get("vertex") == "1" for cell in cells),
                20,
            )
            self.assertGreater(
                sum(cell.get("edge") == "1" for cell in cells),
                1,
            )

    def test_render_professional_cnn_architecture(self) -> None:
        example = SKILL / "assets/examples/cnn-architecture.json"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            self.run_cli("render", str(example), "--output", str(output))
            manifest = json.loads((output / "figure-manifest.json").read_text())
            self.assertTrue(manifest["checks"]["passed"])
            self.assertEqual("diagram.cnn-architecture", manifest["kind"])
            self.assertEqual(10, len(manifest["geometry"]))
            svg = (output / "figure.svg").read_text()
            self.assertIn("Residual Bottleneck", svg)
            self.assertIn("identity shortcut", svg)
            self.assertIn("Visual grammar", svg)
            drawio = ET.parse(output / "figure.drawio").getroot()
            cells = drawio.findall(".//mxCell")
            self.assertGreater(
                sum(cell.get("vertex") == "1" for cell in cells),
                10,
            )

    def test_render_swimlane(self) -> None:
        output, _ = self.render(
            {
                "version": "1.0",
                "kind": "diagram.swimlane",
                "lanes": [
                    {"id": "user", "label": "User"},
                    {"id": "system", "label": "System"},
                ],
                "nodes": [
                    {"id": "submit", "label": "Submit", "lane": "user", "layer": 0},
                    {"id": "confirm", "label": "Confirm", "lane": "user", "layer": 0},
                    {"id": "check", "label": "Validate", "lane": "system", "layer": 1},
                ],
                "edges": [
                    {"from": "submit", "to": "check"},
                    {"from": "confirm", "to": "check"}
                ],
                "output": {"primary": "svg"},
            }
        )
        self.assertIn("System", (output / "figure.svg").read_text())

    def test_render_top_to_bottom_diagram(self) -> None:
        output, manifest = self.render(
            {
                "version": "1.0",
                "kind": "diagram.flowchart",
                "title": "训练流程",
                "nodes": [
                    {"id": "start", "label": "开始训练", "layer": 0},
                    {"id": "fit", "label": "模型拟合", "layer": 1},
                    {"id": "end", "label": "评估结果", "layer": 2},
                ],
                "edges": [
                    {"from": "start", "to": "fit"},
                    {"from": "fit", "to": "end"},
                ],
                "layout": {"direction": "TB"},
                "output": {"primary": "svg"},
            }
        )
        geometry = manifest["geometry"]
        self.assertLess(geometry[0]["y"], geometry[1]["y"])
        self.assertIn("训练流程", (output / "figure.svg").read_text())

    def test_render_semantic_framework_roles(self) -> None:
        output, _ = self.render(
            {
                "version": "1.0",
                "kind": "diagram.research-framework",
                "title": "Research framework",
                "nodes": [
                    {
                        "id": "method",
                        "label": "Method",
                        "layer": 0,
                        "group": "Methodology",
                        "role": "method",
                        "icon": "workflow",
                        "step": "01",
                    },
                    {
                        "id": "evidence",
                        "label": "Evidence",
                        "layer": 1,
                        "group": "Evidence",
                        "role": "evidence",
                        "icon": "quality",
                    },
                    {
                        "id": "outcome",
                        "label": "Outcome",
                        "layer": 2,
                        "role": "outcome",
                        "shape": "pill",
                        "icon": "distribution",
                    },
                ],
                "edges": [
                    {"from": "method", "to": "evidence"},
                    {"from": "evidence", "to": "outcome"},
                ],
                "layout": {"direction": "TB"},
                "output": {"primary": "svg"},
            }
        )
        svg = (output / "figure.svg").read_text()
        self.assertIn('id="generic-card-shadow"', svg)
        self.assertIn('data-icon="workflow"', svg)
        self.assertIn(">01<", svg)

    def test_render_dedicated_research_framework(self) -> None:
        output, manifest = self.render(
            {
                "version": "1.0",
                "kind": "diagram.research-framework",
                "title": "Methodology",
                "framework_stages": [
                    {
                        "id": "inputs",
                        "title": "Inputs",
                        "role": "input",
                        "items": [
                            {
                                "id": "question",
                                "label": "Question",
                                "icon": "diagram",
                            }
                        ],
                    },
                    {
                        "id": "method",
                        "title": "Method",
                        "transition": "Operationalize",
                        "role": "method",
                        "items": [
                            {
                                "id": "execute",
                                "label": "Execute",
                                "step": "01",
                            }
                        ],
                    },
                ],
                "feedback": {
                    "from": "method",
                    "to": "inputs",
                    "label": "Refine",
                },
                "outcome": {
                    "label": "Outcome",
                    "icon": "distribution",
                },
                "output": {"primary": "svg"},
            }
        )
        self.assertEqual(3, len(manifest["geometry"]))
        svg = (output / "figure.svg").read_text()
        self.assertIn("framework-panel-shadow", svg)
        self.assertIn("Operationalize", svg)
        self.assertIn("Refine", svg)

    def test_render_complex_framework_matrix(self) -> None:
        output, manifest = self.render(
            {
                "version": "1.0",
                "kind": "diagram.framework-matrix",
                "title": "Complex framework",
                "phases": [
                    {"id": "design", "title": "Design"},
                    {"id": "evaluate", "title": "Evaluate"},
                ],
                "tracks": [
                    {
                        "id": "science",
                        "title": "Science",
                        "cells": [
                            {"id": "hypothesis", "phase": "design", "label": "Hypothesis"},
                            {"id": "metrics", "phase": "evaluate", "label": "Metrics"},
                        ],
                    },
                    {
                        "id": "governance",
                        "title": "Governance",
                        "cells": [
                            {"id": "risk", "phase": "design", "label": "Risk"},
                            {"id": "review", "phase": "evaluate", "label": "Review"},
                        ],
                    },
                ],
                "cross_links": [
                    {"from": "metrics", "to": "review", "label": "evidence"}
                ],
                "integration": {"label": "Integrate", "chips": ["Validity"]},
                "outcome": {"label": "Outcome"},
                "style": {"preset": "editorial-contrast"},
                "output": {"primary": "svg"},
            }
        )
        self.assertEqual(4, len(manifest["geometry"]))
        svg = (output / "figure.svg").read_text()
        self.assertIn("matrix-panel-shadow", svg)
        self.assertIn("Integrate", svg)
        self.assertIn("evidence", svg)

    def test_chart_uses_standard_additional_output_names(self) -> None:
        output, _ = self.render(
            {
                "version": "1.0",
                "kind": "chart.line",
                "data": {"columns": {"x": [1, 2], "y": [2, 3]}},
                "series": [{"x": "x", "y": "y"}],
                "output": {"primary": "svg", "additional": ["png"]},
            }
        )
        self.assertTrue((output / "figure.svg").is_file())
        self.assertTrue((output / "figure.png").is_file())

    def test_render_gantt(self) -> None:
        output, _ = self.render(
            {
                "version": "1.0",
                "kind": "project.gantt",
                "tasks": [
                    {
                        "id": "design",
                        "label": "Design",
                        "start": "2026-09-01",
                        "end": "2026-09-03",
                    },
                    {
                        "id": "build",
                        "label": "Build",
                        "start": "2026-09-04",
                        "end": "2026-09-08",
                        "depends_on": "design",
                    },
                ],
                "output": {"primary": "svg"},
            }
        )
        self.assertTrue((output / "figure.svg").is_file())

    def test_rejects_ambiguous_error_bars(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            spec_path = Path(directory) / "invalid.json"
            spec_path.write_text(
                json.dumps(
                    {
                        "version": "1.0",
                        "kind": "chart.errorbar",
                        "data": {"columns": {"x": [1], "y": [2]}},
                        "series": [{"x": "x", "y": "y"}],
                    }
                )
            )
            result = self.run_cli("validate", str(spec_path), expected=1)
            self.assertIn("uncertainty", result.stderr)

    def test_installer_for_all_agents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.run_cli("check-env")
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "install.py"),
                    "--agent",
                    "all",
                    "--scope",
                    "project",
                    "--project",
                    directory,
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            project = Path(directory)
            self.assertTrue(
                (project / ".claude/skills/figurecraft/SKILL.md").is_file()
            )
            self.assertTrue(
                (project / ".github/skills/figurecraft/SKILL.md").is_file()
            )
            self.assertTrue(
                (project / ".agents/skills/figurecraft/SKILL.md").is_file()
            )
            for specialist in (
                "figurecraft-charts",
                "figurecraft-architecture",
                "figurecraft-neural-networks",
                "figurecraft-research-frameworks",
                "figurecraft-process-diagrams",
                "figurecraft-visual-critic",
            ):
                self.assertTrue(
                    (project / ".claude/skills" / specialist / "SKILL.md").is_file()
                )
                self.assertTrue(
                    (project / ".github/skills" / specialist / "SKILL.md").is_file()
                )
                self.assertTrue(
                    (project / ".agents/skills" / specialist / "SKILL.md").is_file()
                )

    def test_yaml_and_relative_csv_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data.csv").write_text("step,value\n1,2.5\n2,3.5\n", encoding="utf-8")
            spec = root / "spec.yaml"
            spec.write_text(
                "\n".join(
                    [
                        'version: "1.0"',
                        "kind: chart.line",
                        "data:",
                        "  source: data.csv",
                        "series:",
                        "  - x: step",
                        "    y: value",
                        "output:",
                        "  primary: svg",
                    ]
                ),
                encoding="utf-8",
            )
            output = root / "output"
            self.run_cli("render", str(spec), "--output", str(output))
            self.assertTrue((output / "figure.svg").is_file())
            self.assertTrue((output / "figure-source.yaml").is_file())


if __name__ == "__main__":
    unittest.main()
