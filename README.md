<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/figurecraft-wordmark-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="docs/images/figurecraft-wordmark-light.svg">
  <img src="docs/images/figurecraft-wordmark-light.svg" width="360" alt="FigureCraft — Deterministic figures for agents">
</picture>

### Deterministic scientific charts and technical diagrams for AI coding agents

Turn a structured **FigureSpec**, data, or a well-scoped prompt into an inspectable,
reproducible figure—not a one-off generated image.

**English** · [简体中文](README.zh-CN.md)

[Quick start](#quick-start) · [Examples](#examples) · [Documentation](#documentation) · [Development](#development)

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Install checks](https://github.com/Zchary1106/figurecraft/actions/workflows/install-platforms.yml/badge.svg)](https://github.com/Zchary1106/figurecraft/actions/workflows/install-platforms.yml)

</div>

> **What it is:** a portable Agent Skill suite for Claude Code, GitHub Copilot, and OpenAI Codex. It renders scientific charts and technical diagrams with deterministic layout, validation, provenance, and editable source artifacts.
>
> **What it is not:** an image-generation wrapper or a hosted drawing canvas. FigureCraft uses Matplotlib for quantitative charts and an SVG-first layout engine for diagrams.

## At a glance

| Need | FigureCraft provides |
| --- | --- |
| **Research figures** | Line, bar, scatter, error-bar, histogram, box, and heatmap charts with units, uncertainty, and data checks. |
| **Technical diagrams** | Architecture, agent systems, process flows, swimlanes, Gantt charts, research frameworks, system landscapes, and neural-network figures. |
| **Reliable output** | Schema validation, measured typography, deterministic layouts, structural SVG linting, provenance, and hashes. |
| **Usable deliverables** | SVG source, optional PNG/PDF, editable Draw.io, the input FigureSpec, manifest, and preview page. |
| **Safe iteration** | Controlled revisions can preserve approved geometry; failed exports do not replace the prior delivery. |

## Quick start

### 1. Install

Clone or download this repository, then run one command from its root.

**macOS**

```bash
bash ./install.sh
```

**Windows PowerShell**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

This installs the shared core plus all six specialists for **Claude Code**, **GitHub Copilot**, and **OpenAI Codex**, creates an isolated Python runtime, and performs readiness checks. Restart the agent or start a new session after installation.

<details>
<summary><strong>Install only one host, into one project, or upgrade an existing installation</strong></summary>

```bash
# Install for one host
bash ./install.sh --agent codex       # or: claude, copilot

# Make skills available to a single project
bash ./install.sh --scope project --project "/path/to/project"

# Update installed copies while preserving customized copies as backups
bash ./install.sh --force
```

</details>

### 2. Ask your agent for a figure

```text
Use FigureCraft to create a double-column scientific error-bar plot from results.csv.
The x-axis is epoch, the y-axis is accuracy, and error values are standard deviation.
Deliver SVG, 300 DPI PNG, and PDF.
```

```text
Use FigureCraft to draw a multi-agent research architecture.
Show the user request, planner, research agents, evidence record, reviewer,
and final report. Use an editable Draw.io export and a slide-ready PNG.
```

The agent selects the relevant specialist automatically. You can also explicitly say `figurecraft-charts`, `figurecraft-architecture`, or another specialist name.

### 3. Inspect the delivery

A normal render produces an output folder with the figure, its editable and reproducibility artifacts, and a local preview page.

```text
output/
├── figure.svg                 # Primary vector figure
├── figure.drawio              # Editable diagram file, when requested/supported
├── figure.png / figure.pdf    # Optional final-size exports
├── figure-source.json         # Normalized FigureSpec
├── figure-manifest.json       # Checks, provenance, hashes, environment metadata
└── index.html                 # Local preview and delivery index
```

## Examples

Every gallery image is generated from a checked-in FigureSpec. Select an image to open its input.

| Scientific chart | System architecture | Research framework |
| --- | --- | --- |
| [![Line chart](docs/images/line-chart.svg)](skills/figurecraft/assets/examples/line-chart.json) | [![Agent evidence workflow](docs/images/agent-evidence-workflow.svg)](skills/figurecraft/assets/examples/agent-evidence-workflow.json) | [![Research framework](docs/images/research-framework.svg)](skills/figurecraft/assets/examples/research-framework.json) |

| Neural-network plate | Process and schedule | Dense system landscape |
| --- | --- | --- |
| [![CNN architecture](docs/images/cnn-architecture.svg)](skills/figurecraft/assets/examples/cnn-architecture.json) | [![Gantt chart](docs/images/gantt.svg)](skills/figurecraft/assets/examples/gantt.json) | [![System landscape](docs/images/system-landscape.svg)](skills/figurecraft/assets/examples/system-landscape.json) |

See all checked-in inputs under [`skills/figurecraft/assets/examples/`](skills/figurecraft/assets/examples/).

## Pick the right specialist

| Skill | Best for |
| --- | --- |
| [`figurecraft`](skills/figurecraft/SKILL.md) | Shared FigureSpec workflow, rendering, exports, validation, and delivery. |
| [`figurecraft-charts`](skills/figurecraft-charts/SKILL.md) | Scientific plots, axes, units, uncertainty, annotations, and data validation. |
| [`figurecraft-architecture`](skills/figurecraft-architecture/SKILL.md) | Software architecture, system landscapes, agent systems, interfaces, and protocols. |
| [`figurecraft-neural-networks`](skills/figurecraft-neural-networks/SKILL.md) | Neural topology, tensor shapes, CNN stages, residual paths, and model plates. |
| [`figurecraft-research-frameworks`](skills/figurecraft-research-frameworks/SKILL.md) | Research methods, evidence chains, validity, and multi-workstream framework matrices. |
| [`figurecraft-process-diagrams`](skills/figurecraft-process-diagrams/SKILL.md) | Flowcharts, algorithms, swimlanes, and Gantt charts. |
| [`figurecraft-visual-critic`](skills/figurecraft-visual-critic/SKILL.md) | Reviewing and improving hierarchy, typography, routing, color, and readability. |

## How it works

[![How FigureCraft works: define the figure, validate constraints, compose the visual system, render deterministically, and deliver an auditable bundle.](docs/images/how-it-works.svg)](skills/figurecraft/assets/examples/how-it-works.json)

FigureCraft uses a `FigureSpec` as the source of truth. The spec captures the content, semantics, output formats, language, final-size medium, layout options, and provenance. This makes a figure reproducible, reviewable, and safer to revise than a bitmap-only workflow.

## Output formats and requirements

| Output | Use case | Requirement |
| --- | --- | --- |
| **SVG** | Primary vector output and diagrams | Included by default. |
| **Draw.io** | Manual editing of supported diagrams | Included by default for supported diagram grammars. |
| **PNG / PDF** | Papers, slides, and raster workflows | Charts use Matplotlib; diagram conversion requires native Cairo. |

For Chinese labels, install a CJK font such as PingFang SC, Microsoft YaHei, or Noto Sans CJK SC. SVG and Draw.io diagram output work without native Cairo. To require every export during install:

```bash
bash ./install.sh --require-export
```

On macOS, install the diagram-export dependency with:

```bash
brew install cairo
```

For detailed diagnostics, supported library paths, Windows setup, and safe upgrades, see [Installation and runtime readiness](skills/figurecraft/references/installation.md).

## Use the CLI directly

Agent use is the standard path, but the CLI is useful in CI and local development.

```bash
# Check the runtime for a requested pipeline
python3 skills/figurecraft/scripts/figure.py check-env \
  --format png --kind diagram.architecture --cjk

# Validate a FigureSpec without rendering
python3 skills/figurecraft/scripts/figure.py validate \
  skills/figurecraft/assets/examples/line-chart.json

# Render one figure
python3 skills/figurecraft/scripts/figure.py render \
  skills/figurecraft/assets/examples/agent-evidence-workflow.json \
  --output output/agent-evidence-workflow

# Render a coordinated overview/detail set
python3 skills/figurecraft/scripts/figure.py render-set \
  skills/figurecraft/assets/examples/framework-matrix.json \
  --output output/framework
```

## Reliability boundaries

FigureCraft is designed to make the correct workflow easy, but it does not claim to replace editorial judgment.

- Values, units, uncertainty semantics, Gantt dependencies, declared network dimensions, and FigureSpec structure are validated before rendering.
- Text is measured using installed FreeType fonts; missing glyphs and impossible layouts are reported instead of silently clipped.
- Rendering is transactional: an export or lint failure preserves the previous complete delivery.
- Dense diagrams may still benefit from decomposition, a secondary detail view, or human visual review.
- Draw.io changes are not imported back into the FigureSpec automatically.
- Reference images guide layout and visual language; they are not copied pixel for pixel.

## Documentation

- [FigureSpec reference](skills/figurecraft/references/figure-spec.md)
- [Installation and runtime readiness](skills/figurecraft/references/installation.md)
- [Scientific-chart guidance](skills/figurecraft/references/scientific-charts.md)
- [Technical-diagram guidance](skills/figurecraft/references/technical-diagrams.md)
- [Final-size output for papers and slides](skills/figurecraft/references/output-media.md)
- [Controlled revisions](skills/figurecraft/references/controlled-edits.md)
- [Language and provenance](skills/figurecraft/references/language-and-provenance.md)
- [Reference-figure distillation](skills/figurecraft/references/reference-distillation.md)
- [Visual critique rubric](skills/figurecraft/references/critique-rubric.md)

## Development

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[export]"

# Full test suite
.venv/bin/python -m unittest discover -s tests -v

# Validate every bundled example
for spec in skills/figurecraft/assets/examples/*.json; do
  .venv/bin/python skills/figurecraft/scripts/figure.py validate "$spec"
done
```

If macOS Python cannot discover Homebrew Cairo, run export tests with:

```bash
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
  .venv/bin/python -m unittest discover -s tests -v
```

## Repository layout

```text
.
├── install.py / install.sh / install.ps1  Cross-platform installer
├── skills/                                 Core and six specialist skills
│   └── figurecraft/                        Renderer, schema, examples, themes, and references
├── docs/images/                            Checked-in gallery outputs
├── tests/                                  Renderer, installer, export, and safety regressions
└── .github/workflows/                      Cross-platform install checks
```

## License

[MIT License](LICENSE)
