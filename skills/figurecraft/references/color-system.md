# Professional color system

Color is a semantic layer, not a decoration layer.

## Public guidance distilled

- ColorBrewer distinguishes qualitative, sequential, and diverging schemes:
  https://colorbrewer2.org/learnmore/schemes_full.html
- Paul Tol recommends separate bright, muted, high-contrast, and pale use cases;
  pale colors are backgrounds, not thin data lines:
  https://sronpersonalpages.nl/~pault/
- Okabe–Ito color-universal design requires redundant shape, line, position, or
  label encoding:
  https://jfly.uni-koeln.de/color/
- IBM Carbon emphasizes planned categorical order and neutral-dominant
  interfaces:
  https://carbondesignsystem.com/data-visualization/color-palettes/
- Nature requires color-vision accessibility, editable text, and restrained
  decoration:
  https://research-figure-guide.nature.com/figures/preparing-figures-our-specifications/
- WCAG 2.2 requires 4.5:1 normal-text contrast and 3:1 meaningful non-text
  graphical contrast:
  https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html

## FigureCraft rules

1. Keep 70–80% of a technical figure neutral.
2. Use tints for panels, cards, intervals, and quiet context.
3. Use strong accents for phase headers, track identity, primary data, and
   selected outcomes.
4. Limit ordinary categorical accents to six.
5. Baselines and non-focus edges use muted neutrals.
6. Status colors do not participate in category rotation.
7. Color is always backed by text, icon, shape, line style, or position.
8. Dark themes use layered dark surfaces, never pure black cards.
9. Print-oriented output must have a light-theme alternative.

## Theme family

- `editorial-contrast`: high-contrast light theme for architecture, papers, and
  complex frameworks; uses solid phase/track anchors and a dark integration hub.
- `warm-academic`: paper-like warm neutral surfaces for social science,
  conceptual frameworks, and book-style figures.
- `midnight-technical`: dark screen theme with jewel accents and layered dark
  surfaces for presentations and technical dashboards.
- `paper-light`: restrained default for charts.
- `cnn-paper`: tensor and neural-network plate theme.
- `technical-landscape`: soft engineering map theme.
- `presentation-dark`: general dark presentation theme.

The bundled colors are original combinations based on the public principles
above; they do not reproduce branded palettes or third-party theme files.
