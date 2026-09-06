# Editable outputs

## FigureSpec

The canonical semantic source. Edit data, nodes, relationships, view, layout,
and theme, then render again. Best for version control and reproducibility.

Rendering bundles external CSV/JSON data alongside `figure-source.json` (or
YAML), rewrites its data reference to the bundled copy, and records input hashes
in the manifest. Move the entire output directory rather than the source file
alone. Re-render that bundled source to reproduce the figure without access to
the original data directory.

## Draw.io

Use `.drawio` when a human needs drag-and-drop editing:

- macro zones are container cells;
- sections are nested containers;
- cards and nodes are individual vertices;
- relationships are editable orthogonal edges;
- labels and styles remain editable;
- the file uses readable, uncompressed mxGraph XML.

Draw.io output is a handoff format. Manual edits do not automatically update the
FigureSpec. Keep both files and state which one is authoritative after manual
changes.

Framework stages/items, matrix phases/tracks/cells/integration, and CNN stage
and block structure are exported as separate editable elements. Relationship
direction, status, semantic color, ports, and routed waypoints are preserved.
SVG and Draw.io share layout calculations, but text rendering and decorative
effects may differ between applications; do not treat them as pixel-identical.

## SVG

Vector and editable in Figma, Illustrator, and Inkscape, but its elements do not
carry the same container and connector behavior as Draw.io.

## PNG and PDF

Delivery formats, not semantic editing formats. PNG is raster. PDF may retain
vector objects but is not the canonical source.

Diagram conversion requires `pip install '.[export]'` and the native Cairo
library. On macOS install Cairo with `brew install cairo`; if a non-Homebrew
Python cannot find it, set `DYLD_FALLBACK_LIBRARY_PATH` to the Homebrew `lib`
directory for the render command. Do not silently fall back to another renderer.

SVG diagram coordinates use CSS pixels (96 pixels per inch). PNG output scales
those coordinates by `output.dpi / 96`; changing DPI therefore changes the
actual raster dimensions. SVG/Draw.io remain the vector sources.
