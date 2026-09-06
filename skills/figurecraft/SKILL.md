---
name: figurecraft
description: Orchestrates multi-figure and cross-domain visualization work and provides the shared FigureSpec renderer, themes, exporters, and validation used by the FigureCraft specialist skills. Use when the user explicitly requests FigureCraft, asks to install or configure the suite, requests several different figure families together, or needs shared export and quality infrastructure. For a single chart, architecture diagram, neural network, process diagram, or critique, prefer the matching figurecraft-* specialist skill.
license: MIT
compatibility: Requires Python 3.11+, jsonschema, matplotlib and numpy. SVG typography uses Matplotlib FreeType font metrics; YAML specs require PyYAML. PNG/PDF diagram conversion additionally requires CairoSVG.
metadata:
  author: figurecraft
  version: "0.26.0"
---

# FigureCraft

Create figures that are semantically correct, reproducible, editable, and
appropriate for their final medium. Never trade data or structural accuracy for
decoration.

## Non-negotiable rules

1. Generate quantitative charts with deterministic code, never with an image
   generation model.
2. Do not invent missing values, labels, units, error definitions, nodes, or
   relationships.
3. Default to SVG and retain the FigureSpec or source code.
4. Treat incorrect values, axis semantics, node relationships, or reading order
   as blocking failures.
5. Use color as a secondary encoding. Preserve meaning in grayscale and for
   common color-vision deficiencies.
6. Do not silently substitute a renderer when a requested output cannot be
   produced. Report the missing dependency or unsupported requirement.

## Workflow

### 1. Inspect the available inputs

Read data files, existing figure source, manuscript text, captions, or sketches
before asking questions. Determine:

- communicative goal and audience;
- figure family and required content;
- final medium, dimensions, and output formats;
- data fields, units, uncertainty meaning, and ordering;
- editability, language, and style constraints.

When installed with the one-command setup, `scripts/figure.py` automatically
selects the shared managed interpreter recorded in `scripts/.figurecraft-runtime.json`;
manual activation is unnecessary. For copies without that configuration, select
the active project virtual environment and use the same interpreter for checks
and rendering. See
[references/installation.md](references/installation.md) for host installation
and format-specific dependency diagnostics.

Only ask for information that changes the figure's meaning. If a reversible
visual preference is missing, choose the `paper-light` preset and state the
assumption in the manifest.

Declare `provenance.type` and a short visible `provenance.summary` for new figures.
Do not label a conceptual example as an implemented architecture or measured
result. Follow [references/language-and-provenance.md](references/language-and-provenance.md)
for source declarations, Chinese text, mixed terminology, and formula limits.

If the user supplies a reference image, first follow
[references/reference-distillation.md](references/reference-distillation.md).
The extracted layout skeleton must affect diagram-kind selection; do not reduce
a specific reference grammar to a generic flowchart.

### 2. Select the playbook and engine

For architecture and project diagrams, first select the reader-facing view
using [references/view-selection.md](references/view-selection.md). Do not put
context, component, deployment, and sequence semantics into one figure.

Read only the relevant reference:

- data plots: [references/scientific-charts.md](references/scientific-charts.md)
- flow, architecture, neural, research, or algorithm diagrams:
  [references/technical-diagrams.md](references/technical-diagrams.md)
- Gantt or swimlanes:
  [references/gantt-and-swimlanes.md](references/gantt-and-swimlanes.md)
- visual styling:
  [references/academic-style.md](references/academic-style.md)
- renderer choice:
  [references/engine-selection.md](references/engine-selection.md)

When visual quality or a new template is required, consult the distilled public
repository evidence in
[references/github-visual-distillation.md](references/github-visual-distillation.md)
and reject patterns listed in
[references/visual-anti-patterns.md](references/visual-anti-patterns.md).

### 3. Create a FigureSpec

Use JSON by default. YAML is accepted when PyYAML is available. Follow
[references/figure-spec.md](references/figure-spec.md) and validate before
rendering:

```bash
python scripts/figure.py validate path/to/spec.json
```

Resolve relative data paths against the FigureSpec file, not the current
working directory.

### 4. Render

For complex explicit-node graphs, `layout.optimize: true` enables deterministic
crossing reduction and coordinated connection ports without changing the graph.
Keep it off when preserving an approved legacy layout; use constrained revisions
for already accepted geometry. Optimization is a heuristic, not a zero-crossing
guarantee.

Use `style.visual_grammar: semantic` when the source supplies node roles.
People, storage, processing, decisions, and evidence should not all be identical
cards. Role colors stay consistent across positions; explicit styling wins.
Choose a structure appropriate to the content, not just a different palette:
branch/merge for actual parallel work, decision nodes for real conditional
paths, framework stages for a research progression, and tensor plates for
declared neural-network stages. Never add a dependency to fill empty space.

Default to one complete figure for ordinary drawing requests. Do not infer a
paper requirement or split a diagram merely because it is complex.
Select `layout.medium` using
[references/output-media.md](references/output-media.md). For papers, honor the
actual physical width and minimum effective type size. If a requested paper diagram
cannot fit, use `render-set` to deliver an overview plus bounded detail views;
retain the original full view as a zoomable reference. Do not lower the font
threshold merely to obtain a successful render.

```bash
python scripts/figure.py render path/to/spec.json --output path/to/output
```

The command writes a primary figure, editable source, and
`figure-manifest.json`. It runs lint automatically unless `--no-lint` is
provided for debugging.

Use `python scripts/figure.py check-env` before choosing optional formats or
engines. The built-in SVG diagram renderer does not require Graphviz or Mermaid.

### 5. Critique and revise

Read [references/critique-rubric.md](references/critique-rubric.md). Check:

- data and relationship fidelity;
- chart or diagram choice;
- labels, units, legends, captions, and reading order;
- overlap, clipping, type size, contrast, and grayscale legibility;
- requested dimensions, formats, and editability.

Run:

```bash
python scripts/figure.py lint path/to/output/figure-manifest.json
```

Make targeted corrections for concrete failures. Limit default automatic
revision to two rounds; do not redraw aimlessly for subjective novelty.

### 6. Deliver

Show the main SVG or PNG directly in the preview, not an HTML index, report,
manifest, or source document. The figure itself is the primary deliverable.
Reuse the current preview panel rather than opening another for each revision.
Identify the main figure, editable source, manifest, and any additional exports.
Briefly state the chosen visual encoding and assumptions that affect
interpretation.

The generated `index.html` is an optional download/history companion, not the
default preview. Open it only when the user requests an artifact browser or a
figure-set index. Likewise, `gallery --output DIRECTORY` builds an optional
example library; it does not replace drawing the requested figure.
For requested figure sets, show the main figure directly and offer detail
figures as secondary outputs instead of substituting a text-heavy report.

For manual editing requirements, read
[references/editable-outputs.md](references/editable-outputs.md) and add
`drawio` to diagram outputs. Keep FigureSpec as the reproducible source.

## Existing-figure requests

When improving an existing figure:

1. preserve all verified data and relationships;
2. identify specific problems before editing;
3. reconstruct from source data when available;
4. do not claim pixel-derived values are exact;
5. retain a before/after distinction and never overwrite the only source.

Use [references/controlled-edits.md](references/controlled-edits.md) to choose
content-only, local, or full-reflow revisions. Do not claim a region is locked
when the selected renderer cannot enforce that promise. Preserve manual Draw.io
edits rather than regenerating over them from an older FigureSpec.

## Failure behavior

- Missing data field: stop and name the field and source.
- Ambiguous uncertainty: require an explicit definition before drawing error
  bars.
- Unsupported format: keep valid source/output already generated, then report
  the exact optional dependency or backend needed.
- Lint failure: do not present the figure as complete.
- Invalid FigureSpec: report all schema paths that failed.
- Missing font glyph: report the character and install/configure an appropriate
  font; do not silently replace it with a box or omit the text.
- Content exceeds a constrained layout: grow the layout or report the constraint;
  do not shrink important text below readable size.
