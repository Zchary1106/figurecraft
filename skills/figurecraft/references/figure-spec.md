# FigureSpec 1.0

FigureSpec is the reproducible source of truth. Prefer JSON. YAML is supported
when PyYAML is installed.

## Shared fields

- `version`: must be `"1.0"`.
- `kind`: one of the kinds in the bundled JSON Schema.
- `title`, `caption`, `intent`, `audience`: optional communicative context.
- `view`: reader-facing view metadata such as `type`, `scope`, `include`, and
  `exclude`. Keep it independent from the underlying elements.
- `style.preset`: `paper-light`, `presentation-dark`, `editorial-contrast`,
  `warm-academic`, `midnight-technical`, `cnn-paper`, or `technical-landscape`.
- `layout`: physical size, aspect ratio, or diagram direction.
- `output.primary`: `svg`, `png`, `pdf`, or diagram-only `drawio`; SVG is the
  default.
- `output.additional`: extra formats.
- `output.dpi`: PNG resolution, normally 300 or 600.
- `assumptions`: explicit reversible decisions made without user input.
- `language`: `en` or `zh-CN`; controls explanatory metadata, not label translation.
- `provenance`: visible source-basis declaration and a short factual limitation;
  see [language-and-provenance.md](language-and-provenance.md).
- `layout.medium`: `paper-single`, `paper-double`, `slide`, or `web`. Physical
  `width_mm`/`height_mm` and final-size `min_font_pt`/`min_font_px` constraints
  are described in [output-media.md](output-media.md).
- `layout.placement`: revision-generated geometry constraints; use the
  [controlled revision workflow](controlled-edits.md), not ad-hoc coordinates.

## Data charts

Use inline `data.columns` or `data.source` pointing to CSV/JSON. Series fields
refer to column names.

```json
{
  "version": "1.0",
  "kind": "chart.errorbar",
  "data": {"source": "results.csv"},
  "series": [
    {"x": "epoch", "y": "mean", "error": "std", "label": "Proposed"}
  ],
  "semantics": {
    "x_label": "Epoch",
    "y_label": "Accuracy",
    "y_unit": "%",
    "uncertainty": "standard deviation"
  }
}
```

Error bars require both `series[].error` and `semantics.uncertainty`.
Bands also require `semantics.uncertainty` and both `lower` and `upper` fields.
Numeric data must be finite and bounds correctly ordered. Data files referenced
by a rendered source are bundled with that source for portable re-rendering.

## Diagrams

Nodes require unique `id` and non-empty `label`. Edges require valid `from` and
`to` IDs. Optional node fields: `layer`, `group`, `lane`, `shape`, `color`.
Shapes:

- `rounded` and `rect` for processes or components;
- `pill` for inputs, outputs, and compact states;
- `diamond` for decisions;
- `database` for persistent or cached stores;
- `tensor` for matrices, feature maps, and model tensors;
- `operation` for mathematical operators;
- `ellipse` for conventional start/end nodes.
- `document` for evidence records, reports, and deliverable artifacts.

Nodes may include `subtitle` for dimensions, protocols, implementation details,
or other secondary information. Keep the primary label short.

Generic framework and architecture nodes may also set:

- `role`: `input`, `data`, `method`, `evidence`, `analysis`, `risk`, `outcome`,
  or a domain-specific role;
- `icon`: a bundled semantic icon for content-aware composition;
- `step`: a short method-step badge.

`style.visual_grammar: semantic` makes explicit roles control shape and palette
slot rather than deriving color from the layer number. Actors/inputs/data use
one color family, processing/agents/tools another, decisions/risks a third,
memory/storage a fourth, and evidence/reports/outcomes a fifth. Colors come
from the selected theme. Unknown roles remain neutral; no role is guessed from
the node label. Explicit `shape`, `color`, and `accent` always take precedence.
This opt-in grammar also removes decorative title stripes and outcome double
outlines. Legacy styling remains the default for already accepted diagrams.

`layout.optimize: true` enables crossing-reducing layer ordering and coordinated
connection routing for explicit-node diagrams. Explicit ranks, graph endpoints,
and user-supplied ports remain authoritative. Sparse rank numbers are compressed
spatially, not rewritten in source. Inspect the final paths: heuristic layout is
not a guarantee of zero crossings. Use controlled revisions, not a fresh
optimization, to protect accepted node positions.
For system landscapes and swimlanes, optimization coordinates routes without
reordering their fixed zones or lanes. CNN, staged-framework, and framework-matrix
plates keep their dedicated layout engines and explicitly reject this flag.

For a publication-oriented research framework, prefer `framework_stages`:

```json
{
  "framework_stages": [
    {
      "id": "method",
      "title": "Methodology",
      "transition": "Operationalize",
      "role": "method",
      "connect_items": true,
      "items": [{"id": "step-1", "label": "Compile contract", "step": "01"}]
    }
  ],
  "feedback": {"from": "analysis", "to": "method", "label": "Refine"},
  "outcome": {"label": "Reproducible delivery", "icon": "distribution"}
}
```

The dedicated renderer produces coherent stage panels, a central narrative
spine, optional internal step connections, one outer feedback lane, and a
visually distinct outcome.
Card labels use measured wrapping. Unconnected items can wrap into multiple
rows; stages grow to fit their content. Connected items must fit on one row;
use a wider panel or an explicit node-edge diagram for a multi-row flow.

For complex frameworks, use `diagram.framework-matrix`:

- `phases`: ordered column headers;
- `tracks`: parallel workstreams with phase-bound cells;
- `cross_links`: explicit dependencies between cells, including skipped tracks;
- `integration`: evidence or decision hub receiving the track outputs;
- `outcome`: final integrated contribution.

The matrix renderer keeps horizontal progression inside each track and reserves
the gaps between track bands for cross-track links.
`layout.convergence_gutter` reserves a right-side collection area where short
track branches join one shared evidence bus before entering the integration
hub; parallel full-height output lines are not used.
Column widths and track heights expand as needed for readable content.

Neural-network tensor nodes may set `visual_width` and `visual_height` to show
progressive spatial compression while retaining exact dimensions in the
subtitle. Visual size is explanatory and must not replace numeric shape labels.

## Professional CNN architecture

Use `diagram.cnn-architecture` for a stage-level publication plate. It requires
`stages`:

```json
{
  "id": "stage3",
  "title": "Stage 3",
  "type": "tensor",
  "spatial": [14, 14],
  "channels": 1024,
  "repeat": 6,
  "operation": "Residual block",
  "transition": "↓2 · C×2"
}
```

Operator stages use `type: operator` plus `label`, `subtitle`, `width`, and
`height`. Optional `block_detail` contains a representative sequence of
operator steps and an explicit residual path. The renderer adds tensor prisms,
stage bands, repeat badges, transitions, block inset, and visual legend.

For a downsampling residual block, add `block_detail.shortcut` with `label` and
`subtitle` to render an explicit projection branch. Optional `stage_table`
rows contain `stage`, `output`, `block`, and `repeat`; when present, the side
panel becomes a technical schedule instead of a generic legend.
The CNN plate remains an ordered pipeline, not an arbitrary model graph. Use
`diagram.neural-network` for explicit branches, skip connections between stages,
or attention topology. Exact numeric input/output shapes are validated when
provided; no executable dimensions are inferred from free-text labels.

Important edges should include:

- stable `id`;
- action-oriented `label`;
- optional `technology` or protocol;
- optional `source_port` and `target_port` (`N`, `E`, `S`, `W`);
- optional `style` such as `dashed` or `curved`.

System-landscape macro connections may additionally use:

- `kind`: `control`, `runtime`, `state`, `evidence`, or `feedback`;
- `direction`: `forward`, `bidirectional`, or `none`;
- `status`: a short connection-state badge such as `SYNC`, `DURABLE`, or
  `GATED`.

Connection state badges include a direction glyph, semantic color, short status,
and optional compact label. Do not place long prose on a macro connector.

`layout.density` accepts `compact`, `normal`, or `comfortable`. Density changes
spacing, never semantic content or minimum readable text size.

System landscapes may set `layout.column_gap` and `layout.row_gap`
independently. Reserve wider horizontal channels for macro relationship labels
without introducing excessive vertical whitespace.

## Editable Draw.io output

Diagram kinds may use `drawio` as the primary or an additional output:

```json
{
  "output": {
    "primary": "svg",
    "additional": ["drawio", "png"]
  }
}
```

The `.drawio` file is uncompressed mxGraph XML. Zones, sections, cards, nodes,
and edges are separate editable objects; it is not an embedded screenshot.
FigureSpec remains the canonical reproducible source, while Draw.io is the
preferred manual-layout handoff.

## System landscape

Use `diagram.system-landscape` for dense project architecture views with many
components. It uses `zones` instead of `nodes`:

- each zone has `id`, `title`, `row`, `column`, `span`, and `sections`;
- the canvas is a 12-column grid;
- `section_columns` controls the section grid within a zone;
- each section has `title`, semantic `tone`, card `columns`, and `items`;
- cards use `label` plus an optional short `subtitle`;
- `connections` join macro zones rather than individual cards.

Prefer this form when the figure has more than roughly 15 components or needs
to show service boundaries and shared infrastructure in one view.

## Gantt

Tasks require `label`, ISO `start`, and ISO `end`. Optional fields include
`group`, `completion`, and `depends_on`.
Dependencies refer to task IDs and are drawn as directed connectors. Duplicate
IDs, invalid references, and dependency cycles are rejected.
