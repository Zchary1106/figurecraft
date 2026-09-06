"""Final SVG media sizing and source-based, physical text-size checks."""
from __future__ import annotations

import copy
import html
import math
import re
import xml.etree.ElementTree as ET
from typing import Any


_NUMBER = r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?"
_LENGTH = re.compile(rf"^\s*({_NUMBER})\s*(px|pt|pc|mm|cm|in|em|rem|%)?\s*$")
_UNITS = {"": 1.0, "px": 1.0, "pt": 96 / 72, "pc": 16.0, "mm": 96 / 25.4, "cm": 96 / 2.54, "in": 96.0}
_MEDIA = {"paper-single", "paper-double", "slide", "web"}
_IDENTITY = (1.0, 0.0, 0.0, 1.0)


def raster_dpi(spec: dict[str, Any]) -> int | float:
    """Use native slide pixels by default; explicit DPI enables supersampling."""
    return spec.get("output", {}).get("dpi", 96 if spec.get("layout", {}).get("medium") == "slide" else 300)


def _layout(spec: dict[str, Any]) -> dict[str, Any]:
    layout = spec.get("layout", {})
    if not isinstance(layout, dict):
        raise ValueError("layout must be an object")
    medium = layout.get("medium")
    if "medium" in layout and (not isinstance(medium, str) or medium not in _MEDIA):
        raise ValueError(f"Unsupported layout.medium: {medium}")
    for key in ("width_mm", "height_mm", "min_font_pt", "min_font_px", "aspect_ratio"):
        if key in layout:
            value = layout[key]
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"layout.{key} must be a finite positive number")
    return layout


def _explicit(layout: dict[str, Any]) -> bool:
    return any(key in layout for key in ("medium", "width_mm", "height_mm", "min_font_pt", "min_font_px"))


def _minimums(layout: dict[str, Any]) -> tuple[float | None, float | None]:
    paper = (layout.get("medium") or "").startswith("paper-") or (
        not layout.get("medium") and ("width_mm" in layout or "height_mm" in layout)
    )
    pt = layout.get("min_font_pt")
    px = layout.get("min_font_px")
    if pt is None and px is None:
        if paper:
            pt = 7.0
        elif layout.get("medium") == "slide":
            px = 18.0
    return pt, px


def _paper_height_limit(layout: dict[str, Any]) -> float | None:
    medium = layout.get("medium")
    if "height_mm" not in layout and (
        medium in {"paper-single", "paper-double"} or (medium is None and "width_mm" in layout)
    ):
        return 240.0
    return None


def prepare_media(spec: dict[str, Any], theme: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Copy inputs and configure chart canvases/type before their layout pass."""
    spec, theme = copy.deepcopy(spec), copy.deepcopy(theme)
    layout = _layout(spec)
    if not _explicit(layout) or not (spec.get("kind", "").startswith("chart.") or spec.get("kind") == "project.gantt"):
        return spec, theme
    layout = spec.setdefault("layout", {})
    medium = layout.get("medium")
    if medium in {"paper-single", "paper-double"}:
        layout.setdefault("width_mm", 85 if medium == "paper-single" else 180)
    elif medium == "slide":
        layout.update(width_mm=508.0, height_mm=285.75)
    maximum = _paper_height_limit(layout)
    if maximum is not None:
        if spec["kind"] == "project.gantt" and "aspect_ratio" not in layout:
            height_mm = max(2.5, 0.42 * len(spec.get("tasks", [])) + 1.2) * 25.4
        else:
            height_mm = layout.get("width_mm", 178) / layout.get("aspect_ratio", 1.6)
        if height_mm > maximum + 1e-6:
            raise ValueError(
                "Chart exceeds the default 240mm paper height before canvas allocation; "
                "use render-set / split into detail figures or explicitly set layout.height_mm"
            )
    if "height_mm" in layout:
        layout["aspect_ratio"] = layout.get("width_mm", 178) / layout["height_mm"]
    pt, px = _minimums(layout)
    minimum = max(pt or 0, (px or 0) * 72 / 96)
    if minimum:
        # Chart annotations may use base minus two points; size them before layout.
        theme["font_size"] = max(theme.get("font_size", 10), minimum + 2)
    return spec, theme


def _length(value: str, parent: float = 16, root: float = 16) -> float:
    keywords = {"xx-small": 9.6, "x-small": 12, "small": 13.333333, "medium": 16, "large": 18, "x-large": 24, "xx-large": 32}
    if value in keywords:
        return keywords[value]
    if value in {"inherit", "unset"}:
        return parent
    if value == "initial":
        return 16
    if value in {"smaller", "larger"}:
        return parent * (0.8 if value == "smaller" else 1.2)
    match = _LENGTH.fullmatch(value)
    if not match:
        raise ValueError(f"Cannot determine SVG text size from {value!r}; use explicit font-size units")
    number, unit = float(match[1]), match[2] or ""
    factor = parent / 100 if unit == "%" else parent if unit == "em" else root if unit == "rem" else _UNITS[unit]
    result = number * factor
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"Invalid SVG size: {value!r}")
    return result


def _tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _declarations(style: str) -> dict[str, str]:
    result = {}
    for declaration in style.split(";"):
        if ":" not in declaration:
            continue
        key, value = declaration.split(":", 1)
        key, value = key.strip().lower(), value.strip()
        if key == "font":
            match = re.search(rf"(?:^|\s)({_NUMBER}(?:px|pt|pc|mm|cm|in|em|rem|%)|xx-small|x-small|small|medium|large|x-large|xx-large)(?=[\s/])", value)
            if match:
                result["font-size"] = match[1] + (" !important" if "!important" in value else "")
            elif value in {"inherit", "initial", "unset"}:
                result["font-size"] = value
        else:
            result[key] = value
    return result


def _matches(element: ET.Element, selector: str) -> bool:
    match = re.fullmatch(r"(\*|[\w-]+)?((?:[.#][\w-]+)*)", selector)
    if not match or (match[1] not in (None, "*", _tag(element))):
        return False
    for kind, value in re.findall(r"([.#])([\w-]+)", match[2]):
        if kind == "#" and element.get("id") != value:
            return False
        if kind == "." and value not in element.get("class", "").split():
            return False
    return True


def _selector_matches(path: list[ET.Element], selector: str) -> bool:
    tokens = selector.split()
    if not tokens or not _matches(path[-1], tokens[-1]):
        return False
    index = len(path) - 2
    for token in reversed(tokens[:-1]):
        while index >= 0 and not _matches(path[index], token):
            index -= 1
        if index < 0:
            return False
        index -= 1
    return True


def _multiply(a: tuple[float, ...], b: tuple[float, ...]) -> tuple[float, ...]:
    return (a[0] * b[0] + a[2] * b[1], a[1] * b[0] + a[3] * b[1],
            a[0] * b[2] + a[2] * b[3], a[1] * b[2] + a[3] * b[3])


def _transform(value: str) -> tuple[float, ...]:
    result = _IDENTITY
    for operation, arguments in re.findall(r"(\w+)\s*\(([^)]*)\)", value):
        numbers = [float(item) for item in re.findall(_NUMBER, arguments)]
        matrix = _IDENTITY
        if operation == "scale" and numbers:
            matrix = (numbers[0], 0, 0, numbers[1] if len(numbers) > 1 else numbers[0])
        elif operation == "matrix" and len(numbers) == 6:
            matrix = tuple(numbers[:4])
        elif operation == "rotate" and numbers:
            angle = math.radians(numbers[0])
            matrix = (math.cos(angle), math.sin(angle), -math.sin(angle), math.cos(angle))
        elif operation in {"skewX", "skewY"} and numbers:
            skew = math.tan(math.radians(numbers[0]))
            matrix = (1, 0, skew, 1) if operation == "skewX" else (1, skew, 0, 1)
        result = _multiply(result, matrix)
    return result


def _smallest_scale(matrix: tuple[float, ...]) -> float:
    a, b, c, d = matrix
    squared = a * a + b * b + c * c + d * d
    determinant = a * d - b * c
    largest = math.sqrt(max(0, (squared + math.sqrt(max(0, squared * squared - 4 * determinant * determinant))) / 2))
    return abs(determinant) / largest if largest else 0


def _text_sizes(root: ET.Element) -> list[dict[str, Any]]:
    rules = []
    for element in root.iter():
        if _tag(element) == "style":
            css = re.sub(r"/\*.*?\*/", "", "".join(element.itertext()), flags=re.S)
            for selectors, declarations in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
                for selector in selectors.split(","):
                    selector = selector.strip()
                    specificity = (selector.count("#"), selector.count("."), len(re.findall(r"(?:^|\s)[a-zA-Z]", selector)))
                    rules.append((specificity, selector, _declarations(declarations)))
    rules.sort(key=lambda rule: rule[0])
    sizes: list[dict[str, Any]] = []
    references = {element.get("id"): element for element in root.iter() if element.get("id")}

    def visit(element: ET.Element, path: list[ET.Element], inherited: float, root_size: float,
              transform: tuple[float, ...], in_text: bool = False, source: str = "16px",
              visibility: str = "visible") -> None:
        tag = _tag(element)
        if tag in {"defs", "style", "metadata", "title", "desc", "symbol", "clipPath", "mask"}:
            return
        path = [*path, element]
        style: dict[str, str] = {}
        priorities: dict[str, tuple[Any, ...]] = {}

        def cascade(declarations: dict[str, str], specificity: tuple[int, ...]) -> None:
            for key, value in declarations.items():
                important = bool(re.search(r"\s*!important\s*$", value))
                priority = (important, *specificity)
                if priority >= priorities.get(key, (-1,)):
                    priorities[key] = priority
                    style[key] = re.sub(r"\s*!important\s*$", "", value)

        cascade({key: element.get(key) for key in ("font-size", "display", "visibility") if element.get(key) is not None}, (0, 0, 0, 0))
        for specificity, selector, declarations in rules:
            if _selector_matches(path, selector):
                cascade(declarations, (0, *specificity))
        cascade(_declarations(element.get("style", "")), (1, 0, 0, 0))
        if style.get("display") == "none":
            return
        visibility = style.get("visibility", visibility)
        declared = style.get("font-size")
        size = _length(declared, inherited, root_size) if declared else inherited
        if declared:
            source = f"{declared} (from {source})" if declared in {"inherit", "unset"} else declared
        if element is root:
            root_size = size
        transform = _multiply(transform, _transform(style.get("transform", element.get("transform", ""))))
        if tag == "svg" and element is not root and element.get("viewBox"):
            _, _, box_width, box_height = map(float, re.split(r"[\s,]+", element.get("viewBox").strip()))
            sx = _length(element.get("width", str(box_width))) / box_width
            sy = _length(element.get("height", str(box_height))) / box_height
            ratio = element.get("preserveAspectRatio", "")
            if "none" not in ratio:
                sx = sy = max(sx, sy) if "slice" in ratio else min(sx, sy)
            transform = _multiply(transform, (sx, 0, 0, sy))
        in_text = in_text or tag == "text"

        def record(text: str | None) -> None:
            if in_text and visibility not in {"hidden", "collapse"} and text and text.strip():
                sizes.append({"text": text.strip()[:120], "source_font_size": source,
                              "source_font_px": size, "transformed_font_size": size * _smallest_scale(transform)})

        record(element.text)
        if tag == "use":
            href = element.get("href", element.get("{http://www.w3.org/1999/xlink}href", ""))
            reference = references.get(href[1:]) if href.startswith("#") else None
            if reference is not None and reference not in path:
                visit(reference, path, size, root_size, transform, in_text, source, visibility)
        for child in element:
            visit(child, path, size, root_size, transform, in_text, source, visibility)
            record(child.tail)

    visit(root, [], 16, 16, _IDENTITY)
    return sizes


def apply_svg_media(svg: str, spec: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Size an SVG without distorting geometry and reject unreadable final text.

    Native SVGs are returned byte-for-byte unless a physical size or medium is
    requested. Text measurements are source-derived em sizes, not glyph bounds.
    """
    layout = _layout(spec)
    root = ET.fromstring(svg)
    view_box = root.get("viewBox")
    if view_box:
        values = [float(value) for value in re.split(r"[\s,]+", view_box.strip())]
        if len(values) != 4:
            raise ValueError("SVG viewBox must have four numbers")
        x, y, width, height = values
    else:
        x = y = 0.0
        width, height = _length(root.get("width", "300")), _length(root.get("height", "150"))
    if not all(math.isfinite(value) for value in (x, y, width, height)) or min(width, height) <= 0:
        raise ValueError("SVG must have finite positive viewBox dimensions")
    root_style = _declarations(root.get("style", ""))
    native_width = _length(re.sub(r"\s*!important\s*$", "", root_style.get("width", root.get("width", str(width)))), width)
    native_height = _length(re.sub(r"\s*!important\s*$", "", root_style.get("height", root.get("height", str(height)))), height)
    medium = layout.get("medium")
    final_width, final_height = native_width, native_height
    physical = "width_mm" in layout or "height_mm" in layout or medium in {"paper-single", "paper-double"}
    max_height_mm = _paper_height_limit(layout)
    height_capped = False
    resize = physical or medium == "slide"
    if medium == "slide":
        final_width, final_height = 1920.0, 1080.0
    elif physical:
        default_width = 85 if medium == "paper-single" else 180 if medium == "paper-double" else None
        requested_width = layout.get("width_mm", default_width)
        aspect = layout.get("aspect_ratio", width / height)
        if requested_width is not None:
            final_width = requested_width * 96 / 25.4
            final_height = layout.get("height_mm", requested_width / aspect) * 96 / 25.4
        else:
            final_height = layout["height_mm"] * 96 / 25.4
            final_width = final_height * aspect
        if max_height_mm is not None:
            maximum = max_height_mm * 96 / 25.4
            height_capped = final_height > maximum
            final_height = min(final_height, maximum)
    if min(final_width, final_height) <= 0:
        raise ValueError("SVG must have positive final dimensions")
    if resize:
        scale = min(final_width / width, final_height / height)
        padded_width, padded_height = final_width / scale, final_height / scale
        x -= (padded_width - width) / 2
        y -= (padded_height - height) / 2
        width, height = padded_width, padded_height
    scale = min(final_width / width, final_height / height)
    if not resize and "slice" in root.get("preserveAspectRatio", ""):
        scale = max(final_width / width, final_height / height)
    sizes = _text_sizes(root)
    for item in sizes:
        item["final_font_px"] = item.pop("transformed_font_size") * scale
        item["final_font_pt"] = item["final_font_px"] * 72 / 96
    smallest = min(sizes, key=lambda item: item["final_font_px"]) if sizes else None
    min_pt, min_px = _minimums(layout)
    if smallest and ((min_pt is not None and smallest["final_font_pt"] + 1e-6 < min_pt)
                     or (min_px is not None and smallest["final_font_px"] + 1e-6 < min_px)):
        required = ", ".join(f"{value:g}{unit}" for value, unit in ((min_pt, "pt"), (min_px, "px")) if value is not None)
        raise ValueError(
            f"Unreadable final text {smallest['text']!r}: {smallest['final_font_pt']:.2f}pt "
            f"({smallest['final_font_px']:.2f}px), below required {required} for "
            f"{medium or 'explicit physical media'}. Use render-set / split into overview and detail "
            "figures, reduce information, or choose a larger medium; do not scale-to-fit tiny text."
        )
    metadata = {
        "medium": medium or ("custom" if physical else "native"),
        "explicit": _explicit(layout),
        "requested_medium": medium,
        "width_mm": final_width * 25.4 / 96, "height_mm": final_height * 25.4 / 96,
        "default_max_height_mm": max_height_mm, "height_capped": height_capped,
        "width_px": final_width, "height_px": final_height,
        "view_box": [x, y, width, height],
        "min_font_pt": smallest["final_font_pt"] if smallest else None,
        "min_font_px": smallest["final_font_px"] if smallest else None,
        "required_min_font_pt": min_pt, "required_min_font_px": min_px,
        "font_measurement": "source SVG computed font-size, inherited styles and transforms",
        "font_units": {"min_font_pt": "pt", "min_font_px": "px", "source_font_px": "SVG user units"},
        "smallest_text": smallest, "text_run_count": len(sizes),
        "letterboxed": resize and (abs(width - (values[2] if view_box else native_width)) > 1e-6
                                   or abs(height - (values[3] if view_box else native_height)) > 1e-6),
    }
    if resize:
        attributes = {
            "width": f"{final_width:g}" if medium == "slide" else f"{final_width * 25.4 / 96:.10g}mm",
            "height": f"{final_height:g}" if medium == "slide" else f"{final_height * 25.4 / 96:.10g}mm",
            "viewBox": " ".join(f"{value:.12g}" for value in (x, y, width, height)),
            "preserveAspectRatio": "xMidYMid meet",
        }
        if "width" in root_style or "height" in root_style:
            style = re.sub(r"(?:^|;)\s*(?:width|height)\s*:[^;]*", "", root.get("style", ""), flags=re.I).strip("; ")
            style += f"; width: {attributes['width']} !important; height: {attributes['height']} !important"
            attributes["style"] = html.escape(style.lstrip("; "), quote=True)
        match = re.search(r"<(?:[\w-]+:)?svg\b[^>]*>", svg)
        if match is None:
            raise ValueError("Missing SVG root element")
        opening = match[0]
        for key, value in attributes.items():
            opening = re.sub(rf"\s{key}\s*=\s*(['\"]).*?\1", "", opening, flags=re.S)
            ending = "/>" if opening.endswith("/>") else ">"
            opening = opening[:-len(ending)] + f' {key}="{value}"' + ending
        svg = svg[:match.start()] + opening + svg[match.end():]
    return svg, metadata
