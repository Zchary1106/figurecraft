---
name: figurecraft-research-frameworks
description: Creates professional research frameworks, theoretical and conceptual models, methodology diagrams, experiment pipelines, hypothesis maps, input-method-evidence-outcome figures, and academic study designs. Use for 研究框架图, 理论框架, 概念模型, 技术路线图, 研究设计, methodology framework, hypothesis model, experiment framework, or paper method overview. Do not use for software architecture, quantitative charts, or neural-network topology.
license: MIT
compatibility: Requires the sibling figurecraft core skill and Python 3.11.
metadata:
  author: figurecraft
  version: "0.26.0"
---

# FigureCraft Research Frameworks

Turn a study's argument into a figure whose constructs, method, evidence, and
outcomes can be verified against the manuscript.

## Select the framework grammar

- **Conceptual/theoretical:** constructs plus typed causal, moderating,
  mediating, or associative relationships.
- **Methodology:** research question → data → method → analysis → evidence.
- **Experiment design:** factors, controls, treatments, measurements, and
  comparisons.
- **Technical route:** stages, dependencies, feedback, and deliverables.
- **Paper method overview:** input → modules → outputs plus one representative
  detail inset.
- **Complex framework matrix:** phases across columns, parallel workstreams
  across rows, constrained cross-track links, integration hub, and outcome.

## Workflow

1. Extract the research question, constructs, hypotheses, inputs, transformations,
   evidence, outcomes, and scope from the source text.
2. Separate procedural flow from causal/theoretical relationships.
3. Use `diagram.research-framework` with `framework_stages`, stable item IDs,
   role-specific cards, concise labels, a central narrative spine, and an
   optional outer feedback loop.
   For multiple parallel workstreams, use `diagram.framework-matrix` with
   `phases`, `tracks`, `cross_links`, `integration`, and `outcome`.
4. Keep one dominant reading direction and no more than four hierarchy levels.
5. Use color for role families: source/input, method, evidence/evaluation,
   outcome, and external/context.
   Use `editorial-contrast` when stronger color anchors are appropriate,
   `warm-academic` for paper-like conceptual work, and `midnight-technical`
   only for screen-first dark output.
6. Locate sibling `figurecraft/scripts/figure.py`, validate, render, and lint.
7. Deliver SVG, FigureSpec, manifest, and Draw.io for manual academic editing.

## Edge semantics

- Solid arrow: transformation or supported directional hypothesis.
- Dashed arrow: proposed, optional, feedback, or unverified relationship.
- Plain line: association without direction.
- Edge labels use verbs or hypothesis IDs; never rely on arrow direction alone.

## Publication rules

- Every visible construct maps to manuscript text.
- Do not invent hypotheses or causal direction.
- Distinguish data sources, methods, measures, and conclusions by role.
- Put detailed statistics in charts or tables, not tiny framework boxes.
- Split overview and subsystem detail when labels require shrinking.
- Select paper-single/paper-double using the core final-size rules; `render-set`
  retains the complete reference and generates bounded views.
- Put conceptual/source-derived status and key limitations in visible provenance,
  not only in a hidden assumptions list.
- Figure title states the framework or claim; the full explanation belongs in
  the caption.

Missing constructs, reversed causality, mixed process/causal semantics,
unreadable labels, or decorative groups are blocking failures.
