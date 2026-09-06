# Language, formulas, and provenance

Set `language` to `en` or `zh-CN` for generated explanatory metadata. This does
not translate user-provided labels, rename an API, or change a technical term.
Use a declared terminology convention across the whole figure.

For Chinese and mixed-language diagrams:

- Require a font covering the actual text; check with `check-env --cjk`.
- Keep English identifiers and units intact. Prefer a short bilingual title
  over repeating both languages in every small card.
- Keep Chinese closing punctuation with the preceding text and opening
  punctuation with the following text.
- Do not replace an unavailable glyph with an approximate symbol.

Diagram labels are ordinary text with Unicode glyph support, not a LaTeX
parser. `H×W×C`, `μ`, and supported Unicode subscripts are text; `$x_i$` is not
automatically converted into a typeset equation. For full mathematical layout,
use an explicitly selected and available mathematical typesetting backend and
retain its source. Do not promise unsupported formula fidelity.

## Visible provenance

```json
{
  "language": "en",
  "provenance": {
    "type": "conceptual",
    "summary": "Illustrative workflow; not a deployed product."
  }
}
```

Use `conceptual`, `code-derived`, `data-derived`, or `unspecified`. Code-derived
and data-derived figures require `sources`, containing source paths or URLs.
Use `summary` for the short assumption or limitation that must travel with the
figure itself. The delivery page lists the full assumptions and source references.

`verified: true` records an author's declaration. It is not independent
verification by the renderer. The tool must not infer this flag because schema,
geometry, or numeric checks passed. When no provenance is provided, the delivery
page says that the source basis is unspecified; never silently label it factual.

For connection labels, explain the action first: `submits task`, `returns
evidence`, or `reads/writes state`. Attributes such as synchronous transport,
durability, and access gating describe different properties. They are not
interchangeable runtime states; explain them when retained.
