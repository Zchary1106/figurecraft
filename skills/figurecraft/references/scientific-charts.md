# Scientific charts

## Selection

- Bar: compare discrete magnitudes. Start the quantitative axis at zero unless
  a clearly disclosed exception is scientifically necessary.
- Line: ordered continuous progression. Do not smooth unless the method is
  stated and the raw observations remain available.
- Scatter: relationship or distribution of paired observations.
- Error bar: central estimate plus explicitly defined uncertainty.
- Histogram: distribution of one variable; disclose bin policy when material.
- Box: compare distributions; do not imply sample size through box width.
- Heatmap: matrix patterns; use a perceptually ordered map for quantitative data.

## Requirements

- Preserve source ordering unless sorting is requested or documented.
- Include units in axis labels rather than repeating them in every tick.
- Direct-label small series sets when it improves lookup.
- For grouped bars, use `style.annotate_values` for small category sets and
  `legend_location: top` when an internal legend would cover marks. The
  renderer reserves separate title and legend bands.
- `style.title_alignment` accepts `left`, `center`, or `right`. Use centered
  titles when requested; left alignment remains the publication default.
- Use markers or line styles in addition to color.
- Avoid dual axes, 3D effects, excessive grid lines, and decorative gradients.
- For multi-panel figures, keep scales consistent when comparison is intended.
- For uncertainty bands, provide explicit `lower` and `upper` fields on the
  series and state the interval kind, level, and method in `semantics`.
- Use per-series `linewidth`, `markersize`, and `interval_alpha` to distinguish
  the primary method from a muted baseline. `direct_label_values` may append
  final values and units to line-end labels.
- For a two-series grouped bar comparison, `annotate_delta` adds difference
  badges above each category. Units follow `semantics.y_unit`; `%` yields
  percentage points (`pp`). Use `semantics.delta_unit` or `style.delta_unit`
  for an explicit label override. This does not rescale fractional data.
- Error bars and interval bands require `semantics.uncertainty`. Numeric values
  must be finite; lower bounds cannot exceed upper bounds. Invalid data is
  rejected before drawing.
- Direct labels are separated in display coordinates with leader lines when
  needed. Crowded labels that cannot fit require a larger figure.
- Export retains the requested `layout.width_mm` instead of changing the
  physical width with a tight bounding-box crop.
- Treat chart data, transforms, marks, scales, facets, annotations, and theme as
  separate decisions. A theme must never alter values or transforms.
