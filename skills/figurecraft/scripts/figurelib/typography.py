from __future__ import annotations

import html
import math
import re
from functools import lru_cache
from typing import Any


DEFAULT_FONT = "Inter, PingFang SC, Microsoft YaHei, Arial, Helvetica, DejaVu Sans, sans-serif"


@lru_cache(maxsize=64)
def _font_candidates(family: str, weight: str) -> tuple[Any, ...]:
    from matplotlib import font_manager
    from matplotlib.ft2font import FT2Font

    names = [name.strip().strip("'\"") for name in family.split(",")]
    names.extend(["DejaVu Sans", "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC",
                  "Lantinghei SC", "Arial Unicode MS", "Heiti TC"])
    available = {entry.name for entry in font_manager.fontManager.ttflist}
    paths: list[str] = []
    for name in names:
        if name not in available:
            continue
        path = font_manager.findfont(
            font_manager.FontProperties(family=[name], weight=weight),
            fallback_to_default=False,
        )
        if path not in paths:
            paths.append(path)
    if not paths:
        raise ValueError(f"No installed font matches {family!r}")
    return tuple(FT2Font(path) for path in paths)


@lru_cache(maxsize=4096)
def _glyph_font(character: str, family: str, weight: str) -> Any:
    candidates = _font_candidates(family, weight)
    for font in candidates:
        if character.isspace() or font.get_char_index(ord(character)):
            return font
    raise ValueError(
        f"Missing font glyph U+{ord(character):04X} ({character!r}); "
        "install a font covering this character and add it to style.overrides.svg_font_family"
    )


def _runs(text: str, family: str, weight: str) -> list[tuple[Any, str]]:
    runs: list[tuple[Any, str]] = []
    for character in text:
        font = _glyph_font(character, family, weight)
        if runs and runs[-1][0] is font:
            runs[-1] = (font, runs[-1][1] + character)
        else:
            runs.append((font, character))
    return runs


@lru_cache(maxsize=16384)
def measure_text(
    text: str, size: float, family: str = DEFAULT_FONT, weight: str = "normal"
) -> float:
    from matplotlib.ft2font import LoadFlags

    width = 0.0
    for font, value in _runs(text, family, weight):
        font.set_size(size, 72)
        font.set_text(value, 0, flags=LoadFlags.NO_HINTING)
        width += font.get_width_height()[0] / 64
    return width * 1.06


def wrap_text(
    text: str, width: float, size: float, family: str = DEFAULT_FONT,
    weight: str = "normal",
) -> list[str]:
    if not math.isfinite(width) or width <= 0:
        raise ValueError("Text area must have positive finite width")
    lines: list[str] = []
    for paragraph in str(text).splitlines() or [""]:
        line = ""
        for token in re.findall(r"\S+\s*|\s+", paragraph):
            candidate = line + token
            if measure_text(candidate.rstrip(), size, family, weight) <= width + 1e-6:
                line = candidate
                continue
            if line.strip():
                lines.append(line.rstrip())
                line = ""
            units: list[str] = []
            for character in token.lstrip():
                if units and (character in "，。、：；！？）】》」』％" or units[-1][-1] in "（【《「『"):
                    units[-1] += character
                else:
                    units.append(character)
            for unit in units:
                if measure_text(line + unit, size, family, weight) > width + 1e-6:
                    if not line:
                        raise ValueError("Text area is narrower than a single glyph or punctuation group")
                    lines.append(line.rstrip())
                    line = ""
                if measure_text(unit, size, family, weight) > width + 1e-6:
                    raise ValueError("Text area is narrower than a single glyph or punctuation group")
                line += unit
        lines.append(line.rstrip())
    return lines


def label_height(
    title: str, subtitle: str, width: float, family: str = DEFAULT_FONT,
    title_size: float = 11, subtitle_size: float = 8.8,
) -> float:
    height = len(wrap_text(title, width, title_size, family, "bold")) * title_size * 1.4
    if subtitle:
        height += 5 + len(wrap_text(subtitle, width, subtitle_size, family)) * subtitle_size * 1.4
    return height


def luminance(color: str) -> float:
    from matplotlib.colors import to_rgb

    channels = to_rgb(color)
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return sum(c * w for c, w in zip(linear, (0.2126, 0.7152, 0.0722), strict=True))


def contrast_ratio(first: str, second: str) -> float:
    low, high = sorted((luminance(first), luminance(second)))
    return (high + 0.05) / (low + 0.05)


def readable_color(preferred: str, background: str, minimum: float = 4.5) -> str:
    if contrast_ratio(preferred, background) >= minimum:
        return preferred
    candidate = max(("#FFFFFF", "#101722"), key=lambda value: contrast_ratio(value, background))
    if contrast_ratio(candidate, background) >= minimum:
        return candidate
    return max(("#FFFFFF", "#000000"), key=lambda value: contrast_ratio(value, background))


def label_svg(
    title: str, subtitle: str, x: float, y: float, width: float, height: float,
    family: str = DEFAULT_FONT, title_size: float = 11, subtitle_size: float = 8.8,
    foreground: str = "#18202B", muted: str = "#5C6673", background: str = "#FFFFFF",
    align: str = "middle",
) -> list[str]:
    title_lines = wrap_text(str(title), width, title_size, family, "bold")
    subtitle_lines = wrap_text(str(subtitle), width, subtitle_size, family) if subtitle else []
    total = len(title_lines) * title_size * 1.4
    total += 5 + len(subtitle_lines) * subtitle_size * 1.4 if subtitle_lines else 0
    if total > height + 0.1:
        raise ValueError(f"Text does not fit its container: {title!r}; needs {total:.1f}px, has {height:.1f}px")
    cursor = y + (height - total) / 2
    parts: list[str] = []
    text_x = x + width / 2 if align == "middle" else x
    for lines, size, color, weight in (
        (title_lines, title_size, foreground, "bold"),
        (subtitle_lines, subtitle_size, muted, "normal"),
    ):
        if not lines:
            continue
        if lines is subtitle_lines:
            cursor += 5
        color = readable_color(color, background)
        for line in lines:
            names = list(dict.fromkeys(font.family_name for font, _ in _runs(line, family, weight)))
            resolved = ", ".join(names) or family
            measured = measure_text(line, size, family, weight)
            left = text_x - measured / 2 if align == "middle" else text_x
            parts.append(
                f'<text x="{text_x:.2f}" y="{cursor + size * 0.7:.2f}" '
                f'text-anchor="{align}" dominant-baseline="middle" '
                f'font-family="{html.escape(resolved, quote=True)}" font-size="{size:g}" '
                f'font-weight="{weight}" fill="{color}" '
                f'data-text-box="{left:.2f},{cursor:.2f},{measured:.2f},{size * 1.4:.2f}" '
                f'data-text-container="{x:.2f},{y:.2f},{width:.2f},{height:.2f}" '
                f'data-text-background="{background}">{html.escape(line)}</text>'
            )
            cursor += size * 1.4
    return parts
