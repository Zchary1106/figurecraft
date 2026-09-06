# Technical diagrams

## General

- Establish one dominant reading direction: left-to-right or top-to-bottom.
- Nodes are concepts or components; edges are relationships or flows.
- Use verb labels on edges when the relationship is not obvious.
- Store relationship action and technology separately; for example,
  `label: submits experiment` and `technology: HTTPS/JSON`.
- Use `source_port` and `target_port` (`N`, `E`, `S`, or `W`) when automatic
  routing creates ambiguity.
- Use groups for real boundaries, not decorative boxes.
- Keep shape semantics consistent across the figure.
- Prefer light, desaturated fills with one narrow accent per stage. Reserve
  saturated fills for the single most important result or exception.
- Route architecture and neural-network edges orthogonally. Use curves for
  feedback loops or narrative relationships.
- Use a concise bold primary label and a quieter subtitle for dimensions,
  protocols, or implementation details.

## Neural networks

- For CNN publication plates, read
  [cnn-paper-design.md](cnn-paper-design.md) and use
  `diagram.cnn-architecture` rather than a generic flowchart.
- Show tensor or feature dimensions only when known.
- Distinguish repeated blocks using a count annotation instead of copying many
  identical nodes.
- Separate training-only paths from inference paths.
- Never infer missing layer sizes from a model name.
- Represent tensors as shallow stacks, repeated modules as one grouped block,
  stores as cylinders, and operators as compact circles.

## Architecture

- Separate logical components from deployment infrastructure.
- Label protocols, stores, queues, and trust boundaries when relevant.
- Avoid crossing edges by using layers and groups.
- Choose `layout.density` from `compact`, `normal`, or `comfortable`; do not
  shrink font size to force an overloaded diagram onto the page.
- For a dense project overview, use `diagram.system-landscape`: two or more
  macro service domains across the top, nested functional sections inside each
  domain, and a shared infrastructure band below.
- Prefer `technical-landscape` when matching a compact engineering reference
  with thin dark boundaries, pastel subsystem outlines, dense capability cards,
  and no decorative shadows.
- Put technology stacks in low-contrast subtitles. Keep capabilities in compact
  cards, and connect macro domains rather than drawing every possible
  component-level dependency.
- Assign one stable semantic tone per subsystem: blue for interfaces, green for
  domain/data, purple for reasoning, orange for execution, and teal for memory.
- For optional pictograms, follow
  [icon-system.md](icon-system.md). Prefer bundled monochrome semantic icons in
  section headers; use brand icons only when provider identity changes the
  architecture.

## Research frameworks

- Map each claim in the caption or method text to a visible node or edge.
- Distinguish inputs, methods, outcomes, and evaluation.
- Use visual hierarchy, not decoration, to emphasize the contribution.
