---
name: figurecraft-visual-critic
description: Audits and improves existing charts and diagrams for data fidelity, topology, layout, typography, accessibility, editability, and publication quality. Use when asked to review, critique, polish, redesign, fix overlap, improve aesthetics, compare against a reference figure, or 审图、优化图表、检查遮挡、提升美观. Use after another FigureCraft specialist renders a candidate.
license: MIT
compatibility: Requires the sibling figurecraft core skill and access to the rendered manifest and source.
metadata:
  author: figurecraft
  version: "0.26.0"
---

# FigureCraft Visual Critic

Review semantics before aesthetics. Never “improve” a figure by changing data,
topology, dimensions, labels, or architecture facts.

## Review order

1. Data and logic: values, units, intervals, nodes, edges, directions.
2. Representation: correct chart/diagram family and reader-facing view.
3. Completeness: labels, legends, dimensions, stage counts, dependencies.
4. Geometry: clipping, overlap, edge crossing, label collision, alignment.
5. Typography and accessibility: final-size text, contrast, color redundancy,
   SVG title/description.
6. Reproducibility: FigureSpec, manifest, input hash, versions, editable output.

## Workflow

1. Read source, manifest, and rendered output.
2. Locate sibling `figurecraft/scripts/figure.py` and run `lint`.
3. Inspect the image at actual target scale, not only zoomed in.
   Use effective final-size font metadata, not SVG coordinate font size. Reject
   a paper-readiness claim for an unspecified medium or unreadable resized text.
4. Report concrete, locatable failures.
5. Apply at most two targeted revision rounds.
6. Re-render and reject completion if a blocking issue remains.

Check visible provenance and whether the chosen view answers one reader question.
For revisions, verify promised locks and the authoritative source. Deliver one
current index with history rather than a collection of indistinguishable previews.

Data/topology errors, clipped content, overlap, unreadable text, undefined
uncertainty, invalid SVG/Draw.io, and missing source are blocking.
