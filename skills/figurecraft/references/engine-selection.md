# Engine selection

Use the simplest deterministic engine that preserves the required semantics.

| Requirement | Engine |
|---|---|
| Static scientific data plot | Bundled Matplotlib renderer |
| Gantt chart | Bundled Matplotlib renderer |
| Flow, architecture, neural, research, algorithm, swimlane | Bundled SVG renderer |
| Browser interaction | Vega-Lite specification; preserve a static fallback |
| Strict LaTeX typography | TikZ/PGF, only when the environment supports it |
| Nontechnical manual editing | draw.io XML, only when explicitly requested |

Do not select an image generation model for factual charts or diagrams.
Graphviz and Mermaid may be used when the user explicitly needs those source
formats, but the bundled renderer is the portable default.
