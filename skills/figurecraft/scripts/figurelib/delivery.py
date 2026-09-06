"""Local, source-linked delivery pages and transactional figure-set publication."""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import shutil
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from io import StringIO
from typing import Callable
from urllib.parse import quote
from uuid import uuid4

from .io import copy_source, load_spec, sha256, write_json
from .provenance import provenance_description
from .views import plan_views


def _text(value: object) -> str:
    return html.escape(str(value), quote=True)


def _link(path: str, label: str) -> str:
    return f'<a href="{_text(quote(path, safe="/."))}">{_text(label)}</a>'


def _list(items: list) -> str:
    return "<ul>" + "".join(f"<li>{_text(item)}</li>" for item in items) + "</ul>"


def _edge_summary(edge: dict) -> str:
    arrow = {"bidirectional": "↔", "none": "—"}.get(edge.get("direction"), "→")
    return f'{edge["from"]} {arrow} {edge["to"]}' + (f' · {edge["label"]}' if edge.get("label") else "")


_CSS = """
:root{color-scheme:light;font:16px/1.6 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#172033;background:#fff}
*{box-sizing:border-box}body{margin:0}a{color:#2458c5;text-underline-offset:3px}a:hover{color:#173778}
a:focus-visible,summary:focus-visible{outline:3px solid #3569e8;outline-offset:5px}
header,main,footer{width:min(1120px,100% - 48px);margin:auto}
header{padding:40px 0 24px;border-bottom:1px solid #c7d0dd}
h1{font-size:clamp(1.65rem,4vw,2.6rem);line-height:1.2;max-width:30ch;margin:0 0 16px;text-wrap:balance;overflow-wrap:anywhere}
h2{font-size:1.35rem;line-height:1.3;margin:0 0 12px}h3{font-size:1rem;margin:24px 0 8px}
p{max-width:72ch;margin:12px 0}nav,.links{display:flex;flex-wrap:wrap;gap:12px 24px;margin:18px 0}
section{padding:32px 0;border-bottom:1px solid #e4e7ec}
.figure{display:grid;grid-template-columns:minmax(0,1fr) minmax(240px,320px);gap:32px}
.preview{display:block;max-width:100%;width:auto;height:auto;margin:auto}.reference .preview{max-height:420px}
.canvas{min-width:0;align-self:start;background:#f8fafc;padding:20px}
.meta{min-width:0;overflow-wrap:anywhere}.note{color:#475467}.status{font-weight:650}
details{margin-top:16px}summary{cursor:pointer;padding:8px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.85rem;background:#f8fafc;padding:16px}
ul{padding-left:22px}li{margin:6px 0}footer{padding:32px 0;color:#475467}
@media(max-width:720px){header,main,footer{width:calc(100% - 32px)}header{padding-top:24px}.figure{grid-template-columns:1fr;gap:20px}.canvas{padding:8px}section{padding:24px 0}}
"""


def delivery_html(payload: dict) -> str:
    """Escape all user-controlled text; links are encoded local artifact paths."""
    provenance = provenance_description({
        "provenance": payload.get("provenance") or {},
        "language": payload.get("language", "en"),
    })
    complete = payload.get("status") == "complete"
    status = ("Version snapshot" if payload.get("snapshot") else "Current delivery") if complete else "Needs review · not a completed delivery"
    body = [
        "<!doctype html>",
        '<!-- Read-mode delivery: paper-light palette, artifact-first reading order. '
        'Overview leads, details retain source evidence, history is a stable secondary entrance. '
        'Desktop pairs preview and facts; mobile stacks them without shrinking the text. -->',
        f'<html lang="{_text(payload.get("language", "en"))}"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
        "style-src 'unsafe-inline'; img-src 'self' data:; base-uri 'none'; form-action 'none'\">",
        f'<title>{_text(payload.get("title", "Figure delivery"))} — FigureCraft</title>',
        f"<style>{_CSS}</style></head><body><header>",
        f'<h1>{_text(payload.get("title", "Figure delivery"))}</h1>',
        f'<p class="status">{status}</p>',
        f'<p class="note">{_text(payload.get("media_note", "Web viewing; publication sizing has not been verified."))}</p>',
        '<nav aria-label="Delivery navigation">',
        _link(payload["source"], "Full source"),
        _link(payload["manifest"], "Delivery manifest"),
        '<a href="#provenance">Provenance &amp; assumptions</a>',
    ]
    if payload.get("history"):
        body.append('<a href="#history">Version history</a>')
    if payload.get("original_source"):
        body.append(_link(payload["original_source"], "Original input file"))
    if payload.get("current_index"):
        body.append(_link(payload["current_index"], "Open current delivery"))
    body.append("</nav>")
    if len(payload.get("views", [])) > 1:
        body.append(f'<details><summary>Browse {len(payload["views"])} views</summary><ul>')
        for entry in payload["views"]:
            body.append(f'<li><a href="#{_text(entry["id"])}">{_text(entry["title"])}</a></li>')
        body.append("</ul></details>")
    body.append("</header><main>")
    for entry in payload.get("views", []):
        role_class = " reference" if entry.get("role") == "reference" else ""
        body.append(f'<section class="figure{role_class}" id="{_text(entry["id"])}"><div class="canvas">')
        preview = next((p["path"] for p in entry.get("outputs", []) if p["format"] == "svg"), None)
        if preview:
            body.append(f'<a href="{_text(quote(preview, safe="/."))}" aria-label="Open {_text(entry["title"])}">'
                        f'<img class="preview" src="{_text(quote(preview, safe="/."))}" alt="{_text(entry["title"])}"></a>')
        body.append(f'</div><div class="meta"><h2>{_text(entry["title"])}</h2>')
        if entry.get("role") == "reference":
            body.append('<p class="note">Complete original composition for web inspection. Not a printable overview.</p>')
        body.append('<div class="links">')
        for output in entry.get("outputs", []):
            body.append(_link(output["path"], output["format"].upper()))
        body.extend([_link(entry["manifest"], "Manifest"), _link(entry["source"], "View source"), "</div>"])
        if entry.get("metadata"):
            body.append(_link(entry["metadata"], "Source IDs & boundary relations"))
        omissions = entry.get("view_omissions", [])
        if omissions:
            body.append("<h3>What this view leaves out</h3>" + _list(omissions))
        boundary = entry.get("boundary_edges", [])
        if boundary:
            body.append("<details><summary>Cross-boundary relations</summary>" +
                        _list([_edge_summary(e) for e in boundary]) + "</details>")
        if entry.get("context_boundary_edges"):
            body.append("<details><summary>Parent-level boundary references</summary>" +
                        _list([_edge_summary(e) for e in entry["context_boundary_edges"]]) + "</details>")
        body.append("</div></section>")
    body.extend(['<section id="provenance"><h2>Provenance &amp; assumptions</h2>',
                 f'<p><strong>{_text(provenance["label"])}</strong> · '
                 f'{_text(provenance["summary"] or "No source derivation was supplied.")}</p>',
                 '<p>Verification is a source-author declaration, not an automatic guarantee: '
                 f'<strong>{"declared verified" if provenance["verification_declared"] else "not declared verified"}</strong>.</p>'])
    if provenance.get("sources"):
        body.append("<h3>Declared sources</h3>" + _list(provenance["sources"]))
    body.append(_list(payload.get("assumptions", [])) if payload.get("assumptions") else
                '<p class="note">No assumptions were supplied. This does not establish scientific validity.</p>')
    body.append("</section>")
    if payload.get("history"):
        body.append('<section id="history"><h2>Version history</h2><ul>')
        for item in reversed(payload["history"]):
            body.append("<li>" + _link(item["index"], item["generated_at"]) + "</li>")
        body.append("</ul></section>")
    body.append("</main><footer>FigureCraft · Local files only. No remote assets or data uploads.</footer></body></html>")
    return "\n".join(body)


def write_single_delivery(output: Path, manifest: dict, spec: dict) -> Path:
    medium = spec.get("layout", {}).get("medium")
    payload = {
        "title": spec.get("title", "Figure delivery"), "language": spec.get("language", "en"),
        "status": "complete" if (manifest.get("checks") or {}).get("passed") else "needs-review",
        "source": manifest["spec"]["path"], "manifest": "figure-manifest.json",
        "provenance": spec.get("provenance"), "assumptions": spec.get("assumptions", []),
        "media_note": (f"Requested medium: {medium}. Consult manifest checks; rendering is not a publication guarantee."
                       if medium else "Medium unspecified. Web preview only; no publication-readiness claim."),
        "views": [{"id": "figure", "title": spec.get("title", "Figure"), "role": "figure",
                   "manifest": "figure-manifest.json", "source": manifest["spec"]["path"],
                   "outputs": manifest["outputs"]}],
    }
    destination = output / "index.html"
    if destination.is_symlink():
        raise ValueError(f"Refusing to overwrite delivery symlink: {destination}")
    destination.write_text(delivery_html(payload), encoding="utf-8")
    return destination


def render_set(spec_path: Path, output: Path, render: Callable[[Path, Path, bool], int]) -> Path:
    """Publish immutable version folders; failure leaves the last entrance intact."""
    if output.is_symlink():
        raise ValueError("Figure-set output must not be a symlink")
    output.mkdir(parents=True, exist_ok=True)
    lock = output / ".figure-set.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValueError("Figure set is already publishing or has a retained lock; check .figure-set.lock before retrying") from exc
    try:
        return _render_set_locked(spec_path, output, render)
    finally:
        os.close(descriptor)
        lock.unlink()


def _render_set_locked(spec_path: Path, output: Path, render: Callable[[Path, Path, bool], int]) -> Path:
    spec = load_spec(spec_path)
    plans = plan_views(spec)
    if output.is_symlink() or (output / "versions").is_symlink():
        raise ValueError("Figure-set output and versions must not be symlinks")
    output.mkdir(parents=True, exist_ok=True)
    previous = None
    set_path, index_path = output / "figure-set.json", output / "index.html"
    for path in (set_path, index_path):
        if path.is_symlink():
            raise ValueError(f"Refusing to overwrite delivery symlink: {path}")
    if set_path.exists() or index_path.exists():
        try:
            previous = json.loads(set_path.read_text(encoding="utf-8"))
            tracked = (previous.get("schema") in ("figurecraft.figure-set/1", "vizweaver.figure-set/1") and
                       previous.get("status") == "complete" and
                       isinstance(previous.get("current_version"), str) and
                       re.fullmatch(r"\d{8}T\d{6}-[0-9a-f]{10}", previous["current_version"]) and
                       isinstance(previous.get("generated_at"), str) and
                       isinstance(previous.get("history"), list) and
                       all(isinstance(item, dict) and isinstance(item.get("index"), str) and
                           isinstance(item.get("generated_at"), str) for item in previous["history"]) and
                       (output / "versions" / previous["current_version"] / "index.html").is_file() and
                       previous.get("index_sha256") == sha256(index_path))
        except (OSError, ValueError, AttributeError):
            tracked = False
        if not tracked:
            raise ValueError("Refusing to overwrite an untracked or modified delivery entrance")
    original_set = set_path.read_bytes() if set_path.exists() else None
    original_index = index_path.read_bytes() if index_path.exists() else None
    now = datetime.now(timezone.utc)
    version = now.strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:10]
    staging = output / f".building-{version}"
    versions = output / "versions"
    final = versions / version
    staging.mkdir()
    try:
        write_json(staging / "full-source.json", spec)
        original_name = "original-source" + spec_path.suffix.lower()
        shutil.copyfile(spec_path, staging / original_name)
        if load_spec(staging / original_name) != spec:
            raise ValueError("Input changed during view planning; retry with a stable source")
        entries = []
        for plan in plans:
            directory = staging / plan["id"]
            directory.mkdir()
            source_path = directory / "view-spec.json"
            write_json(source_path, plan["spec"])
            with redirect_stdout(StringIO()):
                rendered = render(source_path, directory, False)
            if rendered:
                raise ValueError(f"View {plan['id']} failed validation or lint; previous delivery was retained")
            manifest = json.loads((directory / "figure-manifest.json").read_text(encoding="utf-8"))
            if not (manifest.get("checks") or {}).get("passed"):
                raise ValueError(f"View {plan['id']} is not verified complete")
            write_json(directory / "view-metadata.json", plan)
            entry = {k: deepcopy_value(plan[k]) for k in
                     ("id", "role", "title", "source_ids", "boundary_edges", "context_boundary_edges", "view_omissions")}
            entry.update({
                "manifest": f"{plan['id']}/figure-manifest.json",
                "source": f"{plan['id']}/{manifest['spec']['path']}",
                "metadata": f"{plan['id']}/view-metadata.json",
                "outputs": [{**item, "path": f"{plan['id']}/{item['path']}"} for item in manifest["outputs"]],
            })
            for artifact in (entry["manifest"], entry["source"], entry["metadata"],
                             *(item["path"] for item in entry["outputs"])):
                if not (staging / artifact).is_file():
                    raise ValueError(f"Missing delivered artifact: {artifact}")
            entries.append(entry)
        payload = {
            "schema": "figurecraft.figure-set/1", "status": "complete", "current_version": version,
            "snapshot": True, "current_index": "../../index.html",
            "generated_at": now.isoformat(), "title": spec.get("title", "Figure set"),
            "language": spec.get("language", "en"), "source": "full-source.json",
            "source_sha256": sha256(staging / "full-source.json"), "full_source": spec,
            "original_source": original_name, "original_source_sha256": sha256(staging / original_name),
            "manifest": "figure-set.json", "views": entries,
            "provenance": spec.get("provenance"),
            "assumptions": list(dict.fromkeys(a for p in plans for a in p["spec"].get("assumptions", []))),
            "media_note": "Read the overview first, then details. The complete original is a web reference, not a printable figure.",
            "history": [],
        }
        (staging / "index.html").write_text(delivery_html(payload), encoding="utf-8")
        write_json(staging / "figure-set.json", payload)
        root_payload = deepcopy_value(payload)
        root_payload["snapshot"] = False
        root_payload.pop("current_index")
        prefix = f"versions/{version}/"
        root_payload["source"] = prefix + payload["source"]
        root_payload["original_source"] = prefix + payload["original_source"]
        for entry in root_payload["views"]:
            for key in ("manifest", "source", "metadata"):
                entry[key] = prefix + entry[key]
            for artifact in entry["outputs"]:
                artifact["path"] = prefix + artifact["path"]
        root_payload["history"] = (previous or {}).get("history", [])
        if previous:
            root_payload["history"].append({
                "version": previous["current_version"], "generated_at": previous["generated_at"],
                "index": f"versions/{previous['current_version']}/index.html",
            })
        index = delivery_html(root_payload)
        root_payload["index_sha256"] = hashlib.sha256(index.encode("utf-8")).hexdigest()
        (staging / "next-index.html").write_text(index, encoding="utf-8")
        write_json(staging / "next-set.json", root_payload)
        if ((set_path.read_bytes() if set_path.exists() else None) != original_set or
                (index_path.read_bytes() if index_path.exists() else None) != original_index):
            raise ValueError("Delivery entrance changed during rendering; refusing to overwrite it")
        versions.mkdir(exist_ok=True)
        staging.rename(final)
        old_index = index_path.read_bytes() if index_path.exists() else None
        try:
            os.replace(final / "next-index.html", index_path)
            os.replace(final / "next-set.json", set_path)
        except OSError:
            if old_index is None:
                index_path.unlink(missing_ok=True)
            else:
                index_path.write_bytes(old_index)
            raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return set_path


def deepcopy_value(value):
    return json.loads(json.dumps(value, ensure_ascii=False))


_GALLERY_POLICY = (
    "Gallery previews use SVG only and native web sizing, without PNG/PDF dependencies or a "
    "publication-readiness claim. Original specs retain their export and media settings; "
    "separate preview specs record these overrides. Click a thumbnail for the full SVG."
)
_GALLERY_ACTION = (
    "Run figure.py check-env --format svg --cjk to diagnose font/runtime requirements. "
    "For missing Chinese glyphs, install Noto Sans CJK SC, enable PingFang SC on macOS, "
    "or Microsoft YaHei on Windows, then rerun gallery. No example is silently skipped."
)


def gallery_html(payload: dict) -> str:
    """A local visual index: actual artifacts lead, source declarations stay visible."""
    entries = payload["examples"]
    failed = payload["failed"]
    css = _CSS + """
.gallery-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:36px 28px}
.example{min-width:0;overflow-wrap:anywhere}.example h3{font-size:1.2rem;line-height:1.35;margin:16px 0 8px}
.thumbnail{display:flex;align-items:center;justify-content:center;height:clamp(200px,28vw,340px);background:#f8fafc;padding:16px}
.thumbnail img{display:block;max-width:100%;max-height:100%;object-fit:contain}
.gallery-failure{background:#fff4ee;color:#792812;padding:24px;min-height:220px}
.example .links{gap:8px 20px;margin:12px 0}.example p{margin:8px 0}
@media(max-width:720px){.gallery-grid{grid-template-columns:1fr;gap:28px}.thumbnail{padding:8px}}
"""
    status = f"Partial gallery · {failed} preview{'s' if failed != 1 else ''} failed" if failed else "All previews rendered"
    parts = [
        '<!doctype html><html lang="en"><head><meta charset="utf-8">',
        '<!-- Example library extends paper-light delivery: actual SVG contact sheets, '
        'separate original/preview sources, visible provenance, no placeholder success. -->',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
        "style-src 'unsafe-inline'; img-src 'self' data:; base-uri 'none'; form-action 'none'\">",
        f"<title>Example library — FigureCraft</title><style>{css}</style></head><body>",
        "<header><h1>Example library</h1>",
        f'<p class="status">{_text(status)} · {len(entries)} bundled examples</p>',
        '<p>Choose a case by its visual structure, inspect the source, then adapt it to your own work.</p>',
        '<nav aria-label="Example categories">',
    ]
    categories = [("diagrams", "Diagrams", lambda kind: kind.startswith("diagram.")),
                  ("charts", "Charts", lambda kind: kind.startswith("chart.")),
                  ("planning", "Planning", lambda kind: kind.startswith("project.")),
                  ("other", "Other examples", lambda kind: not kind.startswith(("diagram.", "chart.", "project.")))]
    for anchor, title, matches in categories:
        count = sum(matches(entry["kind"]) for entry in entries)
        if count:
            parts.append(f'<a href="#{anchor}">{title} ({count})</a>')
    parts.extend([_link("gallery.json", "Gallery manifest"), '<a href="#preview-policy">Preview policy</a>',
                  "</nav></header><main>"])
    for anchor, title, matches in categories:
        cases = [entry for entry in entries if matches(entry["kind"])]
        if not cases:
            continue
        parts.append(f'<section id="{anchor}"><h2>{title}</h2><div class="gallery-grid">')
        for entry in cases:
            parts.append(f'<article class="example" id="{_text(entry["id"])}" lang="{_text(entry["language"])}">')
            if entry["status"] == "complete":
                parts.append(f'<a class="thumbnail" href="{_text(quote(entry["svg"], safe="/."))}">'
                             f'<img src="{_text(quote(entry["svg"], safe="/."))}" alt="{_text(entry["title"])} — SVG preview"></a>')
            else:
                parts.append('<div class="gallery-failure"><strong>Preview unavailable</strong>'
                             f'<p>{_text(entry["error"])}</p><p>{_text(entry["action"])}</p></div>')
            parts.append(f'<h3>{_text(entry["title"])}</h3><p class="note">{_text(entry["kind"])}</p>')
            provenance = entry["provenance"]
            parts.append(f'<p><strong>{_text(provenance["label"])}</strong></p>')
            if provenance["summary"]:
                parts.append(f'<p class="note">{_text(provenance["summary"])}</p>')
            parts.append('<div class="links">')
            for key, label in (("svg", "Open SVG"), ("original_source", "Original spec"),
                               ("preview_source", "Preview spec"), ("manifest", "Render manifest")):
                if entry.get(key):
                    parts.append(_link(entry[key], label))
            parts.append("</div></article>")
        parts.append("</div></section>")
    parts.extend(['<section id="preview-policy"><h2>Preview policy</h2>',
                  f"<p>{_text(payload['preview_policy'])}</p>",
                  "<p>Provenance is copied from each example. Missing declarations remain unspecified; "
                  "a successful preview does not verify scientific or implementation accuracy.</p>",
                  "</section></main><footer>FigureCraft · Local files only. No remote assets or data uploads.</footer></body></html>"])
    return "\n".join(parts)


def render_gallery(examples: Path, output: Path, render: Callable[[Path, Path, bool], int]) -> dict:
    """Render bundled examples without optional exports; retain partial diagnostics."""
    paths = sorted(examples.glob("*.json"))
    if not paths:
        raise ValueError(f"No bundled JSON examples found in {examples}")
    if output.is_symlink() or (output / "gallery-runs").is_symlink():
        raise ValueError("Gallery output and gallery-runs must not be symlinks")
    output.mkdir(parents=True, exist_ok=True)
    lock = output / ".gallery.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValueError("Gallery is already rendering; check .gallery.lock before retrying") from exc
    staging = None
    try:
        index_path, manifest_path = output / "index.html", output / "gallery.json"
        if index_path.is_symlink() or manifest_path.is_symlink():
            raise ValueError("Refusing to overwrite a gallery entrance symlink")
        if index_path.exists() or manifest_path.exists():
            try:
                previous = load_spec(manifest_path)
                tracked = previous.get("schema") in ("figurecraft.gallery/1", "vizweaver.gallery/1") and previous.get("index_sha256") == sha256(index_path)
            except (OSError, ValueError):
                tracked = False
            if not tracked:
                raise ValueError("Refusing to overwrite an untracked or modified gallery entrance")
        original_index = index_path.read_bytes() if index_path.exists() else None
        original_manifest = manifest_path.read_bytes() if manifest_path.exists() else None
        run = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:10]
        staging = output / (".building-gallery-" + run)
        staging.mkdir()
        entries = []
        cjk_report = None
        for index, path in enumerate(paths):
            identifier = f"example-{index + 1:02d}"
            directory = staging / identifier
            directory.mkdir()
            original_dir, preview_dir, rendered_dir = directory / "original", directory / "preview-source", directory / "rendered"
            original_dir.mkdir()
            preview_dir.mkdir()
            original = original_dir / path.name
            shutil.copyfile(path, original)
            prefix = f"gallery-runs/{run}/{identifier}/"
            entry = {
                "id": identifier, "filename": path.name, "title": path.stem, "kind": "unknown",
                "language": "en", "status": "failed",
                "original_source": prefix + "original/" + path.name, "original_sha256": sha256(original),
                "provenance": provenance_description({}),
            }
            try:
                spec = load_spec(original)
                entry.update(title=spec.get("title", path.stem), kind=str(spec["kind"]), language=spec.get("language", "en"))
                declaration = spec.get("provenance", {})
                if isinstance(declaration, dict) and declaration.get("type", "unspecified") in {"conceptual", "code-derived", "data-derived", "unspecified"}:
                    entry["provenance"] = provenance_description(spec)
                bundled = copy_source(path, preview_dir)
                preview = load_spec(bundled)
                preview["output"] = {"primary": "svg", "additional": []}
                layout = preview.setdefault("layout", {})
                layout["medium"] = "web"
                for key in ("width_mm", "height_mm", "min_font_pt", "min_font_px"):
                    layout.pop(key, None)
                preview.setdefault("view", {})["gallery_preview"] = {
                    "policy": _GALLERY_POLICY, "original_source": "../original/" + path.name,
                    "original_sha256": entry["original_sha256"],
                }
                preview_path = preview_dir / "preview-spec.json"
                write_json(preview_path, preview)
                entry["preview_source"] = prefix + "preview-source/preview-spec.json"
                entry["preview_sha256"] = sha256(preview_path)
                if entry["language"] == "zh-CN" or re.search(r"[\u3400-\u9fff]", json.dumps(spec, ensure_ascii=False)):
                    if cjk_report is None:
                        from .environment import environment_report

                        cjk_report = environment_report(formats=["svg"], kind="diagram.architecture", check_cjk=True)
                    if not cjk_report["capabilities"]["cjk-text"]["available"]:
                        raise ValueError("CJK font support is unavailable; the preview was not rendered.")
                captured = StringIO()
                with redirect_stdout(captured), redirect_stderr(captured):
                    result = render(preview_path, rendered_dir, False)
                if result:
                    raise ValueError(captured.getvalue().strip() or "The preview failed validation or rendering.")
                manifest = load_spec(rendered_dir / "figure-manifest.json")
                if not (manifest.get("checks") or {}).get("passed") or not (rendered_dir / "figure.svg").is_file():
                    raise ValueError("The preview did not produce a verified SVG.")
                entry.update(status="complete", svg=prefix + "rendered/figure.svg",
                             svg_sha256=sha256(rendered_dir / "figure.svg"),
                             manifest=prefix + "rendered/figure-manifest.json")
            except (OSError, ValueError, RuntimeError, ImportError, KeyError, TypeError) as exc:
                entry.update(error=str(exc), action=_GALLERY_ACTION)
            entries.append(entry)
        failed = sum(entry["status"] != "complete" for entry in entries)
        payload = {
            "schema": "figurecraft.gallery/1", "status": "partial" if failed else "complete", "run_id": run,
            "generated_at": datetime.now(timezone.utc).isoformat(), "failed": failed,
            "preview_policy": _GALLERY_POLICY, "examples": entries,
        }
        page = gallery_html(payload)
        payload["index_sha256"] = hashlib.sha256(page.encode("utf-8")).hexdigest()
        (staging / "next-index.html").write_text(page, encoding="utf-8")
        write_json(staging / "next-gallery.json", payload)
        if ((index_path.read_bytes() if index_path.exists() else None) != original_index or
                (manifest_path.read_bytes() if manifest_path.exists() else None) != original_manifest):
            raise ValueError("Gallery entrance changed during rendering; refusing to overwrite it")
        runs = output / "gallery-runs"
        runs.mkdir(exist_ok=True)
        final = runs / run
        staging.rename(final)
        try:
            os.replace(final / "next-index.html", index_path)
            os.replace(final / "next-gallery.json", manifest_path)
        except OSError:
            if original_index is None:
                index_path.unlink(missing_ok=True)
            else:
                index_path.write_bytes(original_index)
            raise
        return payload
    finally:
        if staging and staging.exists():
            shutil.rmtree(staging)
        os.close(descriptor)
        lock.unlink()
