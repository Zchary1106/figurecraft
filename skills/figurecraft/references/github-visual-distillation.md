# GitHub visual pattern distillation

Research snapshot: 2026-09-03. Popularity changes over time. The repositories
below were inspected for actual galleries, diagram files, theme definitions, or
layout source code. Learn from their information design; do not copy branded
assets, icons, palettes, or unique compositions.

## Scientific and data visualization

| Project | Source | Distilled lesson |
|---|---|---|
| SciencePlots | https://github.com/garrettj403/SciencePlots | Design at final physical size; use thin axes, restrained type, tight export, and journal-aware presets. |
| seaborn | https://github.com/mwaskom/seaborn | Map data semantics consistently; uncertainty bands and small multiples are first-class structures. |
| Matplotlib | https://github.com/matplotlib/matplotlib | Preserve low-level control, deterministic seeds, vector output, and explicit error representations. |
| ggplot2 | https://github.com/tidyverse/ggplot2 | Separate data, transforms, marks, scales, facets, and themes. |
| Observable Plot | https://github.com/observablehq/plot | Prefer direct encodings, accessible SVG, ordered facets, and contextual background marks. |
| Altair | https://github.com/vega/altair | Use concise declarative layers for estimate plus interval and repeatable small multiples. |
| Vega-Lite | https://github.com/vega/vega-lite | Validate a serializable grammar with schema; make transforms and interval meaning explicit. |
| Plotly.py | https://github.com/plotly/plotly.py | Keep interaction optional and always preserve a static fallback; avoid browser-only meaning. |
| ProPlot | https://github.com/proplot-dev/proplot | Reserve layout space for panel labels, legends, and color bars rather than covering data. |
| plotnine | https://github.com/has2k1/plotnine | Compose themes, but do not remove axes or guides when they are needed for quantitative reading. |

## Diagram and architecture engines

| Project | Source | Distilled lesson |
|---|---|---|
| D2 | https://github.com/d2lang/d2 | Layout nested children first, then containers, then cross-container edges; themes use semantic color roles. |
| Mermaid | https://github.com/mermaid-js/mermaid | Provide diagram-specific grammars, explicit edge ports, alignment constraints, and stable seeds. |
| Graphviz | https://graphviz.org/ | Separate rank assignment, crossing minimization, coordinate assignment, and edge routing. |
| PlantUML | https://github.com/plantuml/plantuml | Different information problems need dedicated visual grammars, especially sequence, state, activity, and deployment. |
| Structurizr | https://github.com/structurizr/java | Keep one semantic model and generate context, container, component, dynamic, and deployment views from it. |
| C4-PlantUML | https://github.com/plantuml-stdlib/C4-PlantUML | Use stable element roles and the text hierarchy name, technology, description. |
| LikeC4 | https://github.com/likec4/likec4 | Treat model, view filters, layout constraints, theme, and persisted geometry as separate layers. |
| Excalidraw | https://github.com/excalidraw/excalidraw | Persist element IDs, bindings, arrow label position, bend points, fixed segments, and deterministic seeds. |
| diagrams.net | https://github.com/jgraph/drawio | Route around node obstacles; expose layered layout and routing strategy without silently moving locked nodes. |
| mingrammer/diagrams | https://github.com/mingrammer/diagrams | Programmatic clusters and a curated icon vocabulary accelerate cloud diagrams, but icons never replace labels. |

## Neural-network and academic figures

| Project | Source | Distilled lesson |
|---|---|---|
| NN-SVG | https://github.com/alexlenail/NN-SVG | Parameterize tensor dimensions, channels, filter windows, and SVG output. |
| PlotNeuralNet | https://github.com/HarisIqbal88/PlotNeuralNet | Use named anchors, tensor blocks, operator glyphs, and dedicated skip-connection routing. |
| neural-netz | https://github.com/edgaremy/neural-netz | Separate topology from modern themes; expose one physical scale for paper width. |
| visualkeras | https://github.com/paulgavrikov/visualkeras | Offer layered, graph, and collapsed-block views of the same model. |
| Netron | https://github.com/lutzroeder/netron | Extract a factually correct computation graph first, then produce a human-oriented abstraction. |
| PaperVizAgent | https://github.com/google-research/papervizagent | Separate retrieval, planning, styling, rendering, and critique; keep factual plots deterministic. |
| PaperBanana | https://github.com/dwzhu-pku/PaperBanana | Generate multiple candidates and select with a critic instead of endlessly mutating one weak composition. |
| draw_convnet | https://github.com/gwding/draw_convnet | Collapse repeated channels with first/last examples, an ellipsis, and the exact count. |
| Net2Vis | https://github.com/viscom-ulm/Net2Vis | Make abstraction level configurable while retaining external topology and tensor shape. |
| torchview | https://github.com/mert-kurttutan/torchview | Capture a real execution path, explicit train/eval mode, nested modules, and repeated shapes. |
| HiddenLayer | https://github.com/waleedka/hiddenlayer | Fold low-level operator sequences into named repeated blocks for a publication view. |

## Architecture diagrams in popular projects

| Project | Exact source | Distilled lesson |
|---|---|---|
| n8n | https://github.com/n8n-io/n8n/blob/master/packages/%40n8n/instance-ai/docs/architecture.md | High-density engineering views need explicit process and external-system subgraphs. |
| Backstage | https://github.com/backstage/backstage/blob/master/docs/features/techdocs/architecture.md | Separate build/write path from retrieval/read path. |
| Argo Workflows | https://github.com/argoproj/argo-workflows/blob/main/docs/architecture.md | Deployment boundaries, namespaces, controller queues, and UI deserve separate diagrams. |
| Kubernetes | https://github.com/kubernetes/website/blob/main/content/en/docs/concepts/overview/components.md | A beginner overview should stop at cluster, control plane, node, and major components. |
| Temporal | https://github.com/temporalio/temporal/blob/main/docs/architecture/README.md | Ownership boundaries belong in overview; history and queues belong in lifecycle views. |
| Ray Serve | https://github.com/ray-project/ray/blob/master/doc/source/serve/llm/architecture/serving-patterns/prefill-decode.md | Use line style to distinguish request flow from large state transfer. |
| Supabase | https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/auth/architecture.mdx | Gateway, services, and shared database form a clear three-band product architecture. |
| Airbyte | https://github.com/airbytehq/airbyte/blob/master/docs/platform/understanding-airbyte/high-level-view.md | Keep the asynchronous workload path central and state stores lateral. |
| Cilium | https://github.com/cilium/cilium/blob/main/Documentation/overview/component-overview.rst | Control layer, node control plane, and kernel data plane need distinct horizontal bands. |
| Grafana Tempo | https://github.com/grafana/tempo/blob/main/docs/sources/tempo/reference-tempo-architecture/about-tempo-architecture/_index.md | Split read and write paths rather than building one dense service mesh. |
| Apache Airflow | https://github.com/apache/airflow/blob/main/airflow-core/docs/core-concepts/overview.rst | Generated deployment diagrams and sequence diagrams should complement each other. |
| Istio | https://github.com/istio/istio/blob/master/architecture/ambient/ztunnel-cni-lifecycle.md | Draw one engineering question at a time: lifecycle, configuration, or data path. |
| vLLM | https://github.com/vllm-project/vllm/blob/main/docs/design/arch_overview.md | Use progressive disclosure from API entry points to processes and GPU topology. |
| OpenTelemetry Collector | https://github.com/open-telemetry/opentelemetry-collector/blob/main/docs/internal-architecture.md | Startup call flow and runtime state machine are different views. |

## Distilled laws

1. **One model, multiple views.** Never force context, container, component,
   deployment, data path, and sequence semantics into one canvas.
2. **One figure, one question.** Define the reader and the decision the figure
   supports before selecting a diagram family.
3. **Progressive disclosure.** Start with 3–8 major elements; link or generate
   detail views for dense subsystems.
4. **Stable semantic vocabulary.** A shape, color, line style, or icon carries
   one meaning throughout the figure.
5. **Model and style are independent.** A theme cannot add, remove, reorder, or
   relabel factual content.
6. **Layout is a constraint problem.** Stable order, rank, alignment, ports,
   spacing, and obstacle avoidance beat random aesthetic placement.
7. **Edges are data.** Give important relationships IDs, kinds, action labels,
   technologies, endpoint ports, and optional importance.
8. **Labels have geometry.** Measure and route around edge labels; do not paint
   text on top of lines or nodes.
9. **Density has a ceiling.** Above roughly 15 elements, collapse repetition,
   shorten secondary text, or produce overview and detail views.
10. **Real model before narrative model.** For neural networks and deployed
    systems, extract factual topology first, then create a deliberate abstraction.
11. **Static output is complete.** Interaction and hover may enrich a figure
    but cannot be required to understand it.
12. **Accessibility and reproducibility are output requirements.** Include
    vector source, title/description metadata, stable IDs, version, data hash,
    fonts, scale, and a raster fallback.

## License boundary

Repository licenses differ and may not cover trademarks, logos, cloud-provider
icons, screenshots, or third-party templates. This skill copies no source
theme, branded palette, icon set, or diagram asset. It only implements original
rules distilled from publicly documented information-design patterns.

## README icon addendum

Popular repository diagrams show three stable icon strategies:

- Kubernetes and selected Backstage diagrams use a small number of semantic
  component or actor pictograms.
- Supabase, vLLM, OpenTelemetry, and many Temporal diagrams remain highly
  readable with text and semantic shapes only.
- Argo Workflows, Airflow, Cilium, LikeC4, and cloud-provider diagram tools use
  more brand icons, but this increases visual inconsistency, diff size,
  trademark risk, and dependency on external assets.

The skill therefore defaults to local monochrome semantic icons at section
headers, keeps text as the complete meaning, and does not bundle third-party
logos. See [icon-system.md](icon-system.md).
