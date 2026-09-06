---
name: figurecraft-architecture
description: Creates professional software and system architecture diagrams, including README overviews, C4-style context and container views, deployment views, nested system landscapes, component maps, and editable Draw.io output. Use for architecture diagrams, system design, project structure, 架构图, 系统图, 项目框架图, deployment topology, service map, or technical landscape. Do not use for quantitative charts or neural-network architecture.
license: MIT
compatibility: Requires the sibling figurecraft core skill and Python 3.11.
metadata:
  author: figurecraft
  version: "0.26.0"
---

# FigureCraft Architecture

Create one reader-facing architecture view at a time. Preserve real boundaries
and relationships rather than decorating a package list.

## Select the view first

- Product purpose and actors: system context.
- Deployable services and stores: container architecture.
- Internals of one service: component view.
- Pods, nodes, regions, and volumes: deployment view.
- One request/event journey: data path or sequence.
- Many domains plus shared platforms: system landscape.

Keep the requested complete view. For complex explicit-node diagrams, try
`layout.optimize: true` to reduce crossings and separate fan-in/fan-out ports.
Do not split solely because a diagram contains more than 15 elements.
Use `render-set` only for a requested multi-view delivery or when required paper
dimensions cannot fit the complete drawing. A landscape is not a task sequence.
Declare whether the figure is conceptual or derived from named code sources.
Prefer action labels over unexplained protocol/state badges. Optional
`style.visual_grammar: semantic` uses explicit roles for consistent colors and
shapes, including folded documents for evidence/artifacts. Same-role agents
keep the same color across layers; unknown roles stay neutral. Explicit node
colors, accents, and shapes take precedence. Do not guess roles from names.
The narrower `style.semantic_shapes` option only resolves roles to shapes;
`style.card_accent: none` removes repetitive landscape card accent strips.

## Workflow

1. Inspect real repository docs, manifests, entry points, composition roots,
   adapters, stores, and runtime boundaries.
2. Build `diagram.architecture` for a focused layered view or
   `diagram.system-landscape` for a dense engineering map.
3. Give important relationships stable IDs, action labels, technologies, and
   optional N/E/S/W ports.
4. Use semantic shapes and a restrained local icon vocabulary; text remains
   complete meaning.
5. Locate sibling `figurecraft/scripts/figure.py`, validate, render, and lint.
6. Deliver SVG, FigureSpec, manifest, and structured `.drawio` when editing is
   requested.

## Quality gate

Reject invented services, mixed logical/physical semantics, decorative
boundaries, edge crossings through labels, overloaded single canvases, remote
icons, or outputs without editable source.
