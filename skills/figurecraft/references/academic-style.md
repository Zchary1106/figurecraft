# Academic and presentation style

## Paper

- Use `paper-light`.
- Size to the target column before choosing font size.
- Prefer SVG or PDF; use 300 DPI for color images and 600 DPI for line art when
  a raster format is required.
- Keep final figure text at least 7–8 pt.
- Use restrained grid lines and direct visual hierarchy.

## Presentation

- Use `presentation-dark` only for dark slides.
- Increase type and line widths for viewing distance.
- Reduce the amount of text rather than shrinking it.

## Accessibility

- Use the bundled colorblind-safe palette.
- Add line style, markers, labels, or position as redundant encoding.
- Maintain strong text/background contrast.
- Confirm the figure remains interpretable in grayscale.

## Visual hierarchy

- Use high-value pastel fills for stages and containers, not saturated panels.
- Use color to encode stage or status rather than decorating every object.
- Keep container boundaries lighter than component boundaries.
- Prefer orthogonal connectors for precise technical flows.
- Use secondary text sparingly and at lower contrast than node titles.
- Establish surface hierarchy before adding decoration: quiet canvas, elevated
  macro zones, tinted semantic sections, then compact cards.
- Use one small semantic marker and one card accent edge; avoid gradients,
  shadows, badges, and borders all competing at the same level.
- For SVG cards, use theme-controlled optical baseline correction in addition
  to `dominant-baseline`; mathematical centering alone can appear too high for
  some fonts.

See [visual-design-sources.md](visual-design-sources.md) for the open-source and
publisher references behind these defaults.
See [color-system.md](color-system.md) for semantic palette roles and theme
selection.
