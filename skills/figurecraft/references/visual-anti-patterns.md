# Visual anti-patterns

Reject or revise these patterns.

## Across all figures

- one canvas mixes overview, implementation, deployment, and sequence;
- color is decorative or carries several unrelated meanings;
- labels are smaller than the target medium permits;
- a raster screenshot is the only source;
- remote fonts, images, or data are required to reproduce the output;
- generated icons or text are treated as factual without verification.

## Data charts

- rainbow/jet colors for ordered quantitative data;
- bars with a hidden nonzero baseline;
- uncertainty without kind, level, and method;
- dual axes without an unavoidable analytical reason;
- legend or annotation covering data;
- smoothing that creates observations not present in the source;
- facets with inconsistent scales when comparison is intended.

## Technical diagrams

- every component connects to every other component;
- a boundary exists only for decoration;
- icons replace readable names;
- the same dashed line means skip, async, gradient, optional, and external;
- edges pass through nodes or edge labels;
- automatic layout silently discards manual constraints;
- technology names dominate the responsibility and relationship;
- high-density landscape is used where two focused path diagrams would explain
  the system faster.
- every node uses the same rounded rectangle, left accent stripe, padding, and
  border regardless of whether it is data, method, evidence, risk, or outcome;
- large dashed group boxes create empty space without adding hierarchy.

## Neural-network figures

- generic boxes hide tensor shape and repetition when those facts matter;
- a visually scaled tensor implies false numeric proportionality;
- concat and residual add use the same junction;
- train-only, inference-only, and shared paths are distinguished by color alone;
- a raw framework graph is published without folding low-level operations;
- a generative image is accepted despite misspelled labels or invalid topology.
