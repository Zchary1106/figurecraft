# Controlled revisions

Always name the authoritative source before revising a delivered figure.
Draw.io is a manual editing handoff; it is not a bidirectional FigureSpec editor.
If the user has changed Draw.io, preserve that file and obtain those changes
before regenerating from a stale FigureSpec.

The revision command takes a prior manifest and an updated FigureSpec. It
creates a new output without changing the prior source:

```bash
python skills/figurecraft/scripts/figure.py revise \
  output/original/figure-manifest.json updated.json \
  --mode content-only --output output/revision
```

| Mode | Promise |
|---|---|
| `content-only` | Preserve supported layout geometry while changing permitted text fields. Reject a change that does not fit. |
| `local` | Unlock explicitly named entities; preserve other supported rectangles. Reject collisions instead of moving approved regions silently. |
| `reflow` | Recompute layout. Use only when a broader rearrangement is authorized. |

Local revisions use `--unlock ID` to identify the changed region. Constraints
are stored in the revised source, so subsequent renders must respect them too.
The original source hash is checked before preparing a revision.

Initial constrained editing supports generic node diagrams and landscape zones.
Swimlanes, specialized CNN plates, and framework/matrix layouts require `reflow`; the tool
must report that boundary rather than pretending their internals are locked.
Content-only is not a topology editing mode. Local is not permission to change
every edge, recolor the whole figure, or increase the final canvas secretly.

After a revision, deliver the new version and identify the regions that changed.
Do not make the user discover layout drift by comparing every box manually.
