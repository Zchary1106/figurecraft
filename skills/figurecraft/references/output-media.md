# Final-size output

Choose the delivery medium before composing a figure. A readable SVG at 200%
zoom is not evidence that the same figure is readable in a paper.

| `layout.medium` | Intended surface | Default constraint |
|---|---|---|
| `paper-single` | Single-column paper figure | 85 mm wide; at most 240 mm high; minimum 7 pt |
| `paper-double` | Double-column paper figure | 180 mm wide; at most 240 mm high; minimum 7 pt |
| `slide` | Presentation | 1920 x 1080; minimum 18 output pixels |
| `web` | Zoomable document or browser | Native dimensions; no implied paper readiness |

Slide PNGs default to 96 DPI (1920 x 1080 pixels). An explicit `output.dpi`
requests higher or lower raster sampling without changing the SVG slide canvas.
Paper PNGs retain the default 300 DPI.

`width_mm` and `height_mm` specify physical dimensions. `aspect_ratio` requests
an output ratio without distorting the diagram. Override `min_font_pt` or
`min_font_px` for an actual publication or presentation requirement, not merely
to suppress a failure. A journal's own specification takes precedence.
The default paper height cap also applies when only a physical width is supplied;
an explicit `height_mm` replaces it. Short figures are not padded to 240 mm.

The renderer checks the effective output size, including captions and footnotes.
If content cannot meet the selected threshold, single-figure rendering stops
with an explanation. Keep a full web reference and generate smaller views:

```bash
python skills/figurecraft/scripts/figure.py render-set input.json --output output/figure-set
```

The overview explains the main entities and their relationships. Detail views
retain source identifiers and identify relationships crossing a view boundary.
The complete source remains authoritative. Partitioning is not permission to
invent an edge, shorten a factual label, discard a limitation, or claim that an
overview contains every detail.

For an existing drawing, preserve the approved content and style. Change its
reading level before changing its palette: group related work, show repeated
blocks once, or separate a scenario from a static component inventory.

Legacy specs without an explicit medium continue to render as before. Their
existence does not constitute a publication-readiness claim.
