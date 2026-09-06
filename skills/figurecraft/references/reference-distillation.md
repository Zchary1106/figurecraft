# Reference-image distillation

When the user supplies a reference figure, do not merely reuse its colors and do
not copy its content. Extract a reusable visual profile before drawing.

## Six-part extraction

1. **Layout skeleton**
   - orientation and aspect ratio;
   - macro regions and their relative spans;
   - repeated rows, columns, bands, or nested containers;
   - where cross-region relationships travel.
2. **Information hierarchy**
   - title, domain, section, card, and metadata levels;
   - what is visible at first glance versus close inspection;
   - whether the figure is overview, landscape, deployment, path, or sequence.
3. **Density**
   - number of cards per region;
   - padding, gaps, line length, and text size;
   - whether compactness comes from grouping or from unreadably small type.
4. **Visual tokens**
   - background, surface, border, text, muted text, edge, and accent roles;
   - corner radius, stroke weight, and whether shadows are absent or functional;
   - color meaning by subsystem, status, or element kind.
5. **Shape and text grammar**
   - container, service, process, database, queue, actor, and external forms;
   - primary label, technology, and responsibility text hierarchy;
   - alignment and casing conventions.
6. **Routing grammar**
   - orthogonal, curved, or straight edges;
   - macro-domain versus component-level connections;
   - label placement, arrow direction, and auxiliary line styles.

## Selection rule

The extracted layout skeleton must influence the chosen diagram kind:

- nested wide domains plus a shared bottom platform:
  `diagram.system-landscape`;
- one clear transformation chain: layered architecture;
- role bands with handoffs: swimlane;
- time-ordered calls: sequence;
- physical runtime boundaries: deployment;
- real model topology: computation graph, followed by a collapsed publication
  view when needed.

Do not default back to a generic flowchart after recognizing a more specific
reference grammar.

## Fidelity boundary

Preserve the reference's abstract hierarchy, density strategy, alignment logic,
and token roles. Replace names, architecture facts, colors, icons, and exact
geometry with original choices suitable for the user's project. Record the
derived profile and any intentional deviations in the FigureSpec assumptions.
