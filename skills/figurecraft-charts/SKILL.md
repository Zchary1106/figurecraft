---
name: figurecraft-charts
description: Creates publication-quality quantitative charts, including line plots, grouped or stacked bars, scatter plots, error bars, uncertainty bands, histograms, box plots, and heatmaps. Use when the user asks for a chart, plot, curve, 柱状图, 折线图, 曲线图, 散点图, 热力图, 误差棒, statistical figure, benchmark plot, or data visualization. Do not use for architecture, process, or neural-network diagrams.
license: MIT
compatibility: Requires the sibling figurecraft core skill plus Python 3.11, matplotlib, numpy, jsonschema, and PyYAML for YAML.
metadata:
  author: figurecraft
  version: "0.26.0"
---

# FigureCraft Charts

Own quantitative chart tasks from data inspection through publication export.
Never generate a factual chart with an image-generation model.

## Workflow

1. Read the source data and identify fields, types, units, ordering, missing
   values, uncertainty meaning, audience, and final physical size.
2. Choose the chart by communicative intent:
   - discrete magnitude comparison: bar;
   - ordered progression: line;
   - paired relationship: scatter;
   - distribution: histogram or box;
   - matrix pattern: heatmap.
3. Build a validated FigureSpec using a `chart.*` kind.
4. Locate the sibling `figurecraft` skill and run its
   `scripts/figure.py validate`, then `render`.
5. Inspect values, axes, units, legend/direct labels, clipping, and output size.
6. Deliver SVG plus source and manifest; add PNG/PDF when requested.

## Publication rules

- Bars start at zero unless a disclosed scientific exception is necessary.
- Uncertainty requires kind, level, method, and explicit fields.
- Use a muted baseline and stronger primary method when comparison is intended.
- Use direct line labels for small series sets.
- Use color plus marker, line style, position, or text.
- Avoid rainbow maps, 3D bars, unreported smoothing, and unnecessary dual axes.
- Design at the requested final width; do not fix crowding only by shrinking text.
- Select the core output medium and declare provenance. Synthetic demonstration
  values must be visibly distinguished from measured results.

## Quality gate

Data mismatch, misleading axes, missing units, undefined uncertainty, clipped
labels, or invalid output are blocking failures.
