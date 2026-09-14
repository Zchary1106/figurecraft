# Contributing to FigureCraft

Thanks for helping make agent-generated figures more accurate, reproducible,
and useful.

## Good first contributions

- Add a real-world FigureSpec example with a clearly declared provenance type.
- Improve a renderer without changing the meaning or reading order of existing
  examples.
- Add a regression test for clipping, connector routing, typography, export, or
  validation behavior.
- Improve installation diagnostics on macOS, Windows, Claude Code, GitHub
  Copilot, or OpenAI Codex.
- Document a workflow that produces an editable and reproducible deliverable.

If you want to propose a new chart or diagram family, open a feature request
before implementing it. Include the intended audience, final medium, required
semantics, and why an existing figure family is insufficient.

## Development setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[export]"
```

On macOS, diagram PNG/PDF export requires native Cairo:

```bash
brew install cairo
```

If Python cannot discover the Homebrew library, prefix export-related commands
with:

```bash
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib
```

## Validate your change

Run the full test suite:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Validate every bundled FigureSpec:

```bash
for spec in skills/figurecraft/assets/examples/*.json; do
  .venv/bin/python skills/figurecraft/scripts/figure.py validate "$spec"
done
```

When changing a renderer or visual example:

1. Render the affected FigureSpec.
2. Run the manifest lint command.
3. Inspect the actual SVG or PNG at its final intended size.
4. Confirm that labels, values, units, relationships, and reading order remain
   correct.
5. Commit the FigureSpec together with any regenerated checked-in preview.

## Figure requirements

Contributions must not:

- invent missing values, labels, units, uncertainty definitions, or
  relationships;
- use color as the only carrier of meaning;
- silently clip text or accept missing glyphs;
- replace a reproducible figure with an image-generation result;
- copy a reference image pixel-for-pixel;
- claim measured results or implemented architecture without supporting
  provenance.

Use SVG as the default primary output. Keep the FigureSpec or deterministic
source alongside the preview.

## Pull requests

Keep pull requests focused. In the description, include:

- the problem being solved;
- the affected figure families or hosts;
- the validation commands you ran;
- before/after previews for visual changes;
- known limitations or optional dependencies not verified locally.

By contributing, you agree that your contribution is licensed under the
[MIT License](LICENSE).
