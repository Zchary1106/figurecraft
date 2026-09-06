# Semantic icon system

Icons are optional recognition aids. Text remains the complete source of
meaning.

## Defaults

- Use local, versioned, monochrome semantic icons.
- Prefer section-header icons for dense system landscapes.
- Use card icons only when they distinguish a real element type.
- Target roughly 30%–50% icon coverage; do not decorate every service.
- Keep one alignment model per layer: header icon, left card icon, or icon above
  text. Do not mix all three.
- Render icons with `aria-hidden="true"` when an adjacent text label exists.

## Built-in names

`hosts`, `package`, `workflow`, `model`, `render`, `quality`, `data`, `engine`,
`artifact`, `reproducibility`, `theme`, `distribution`, `user`, `api`, `chart`,
`diagram`, `queue`, `storage`, `security`, and `monitor`.

Unknown names deterministically fall back to `diagram` and record
`data-icon-fallback` in the SVG. They never produce a blank node.

## Size and alignment

- Header icon: about 1.3–1.5 times the section-title size.
- Card-left icon: about 1.25–1.5 times the primary label size.
- Icon width must remain below 25% of card width.
- Icons do not affect edge ports or card geometry.
- Use the section accent color; do not encode status through icon color alone.

## Brand icons

Brand and cloud-provider icons are not bundled. Use them only when provider
identity affects the architecture, and only from a reviewed local asset with
its own license and trademark record. Do not assume a repository's code license
covers embedded logos.

## Prohibited defaults

- remote Iconify or CDN fetches;
- system emoji as semantic icons;
- base64 screenshots inside SVG;
- multicolor logos in every node;
- icon-only nodes without accessible text.
