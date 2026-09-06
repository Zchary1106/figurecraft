from __future__ import annotations

import html


_ICONS = {
    "hosts": (
        '<rect x="3" y="4" width="18" height="13" rx="2"/>'
        '<path d="M8 21h8M12 17v4"/>'
    ),
    "package": (
        '<path d="M4 7.5 12 3l8 4.5-8 4.5-8-4.5Z"/>'
        '<path d="M4 7.5V17l8 4 8-4V7.5M12 12v9"/>'
    ),
    "workflow": (
        '<circle cx="5" cy="6" r="2.2"/><circle cx="19" cy="18" r="2.2"/>'
        '<path d="M7.2 6H14a4 4 0 0 1 4 4v1M15 8l3 3 3-3"/>'
        '<path d="M16.8 18H10a4 4 0 0 1-4-4v-1M9 16l-3-3-3 3"/>'
    ),
    "model": (
        '<rect x="4" y="4" width="16" height="4" rx="1.5"/>'
        '<rect x="4" y="10" width="16" height="4" rx="1.5"/>'
        '<rect x="4" y="16" width="16" height="4" rx="1.5"/>'
    ),
    "render": (
        '<rect x="3" y="4" width="18" height="16" rx="2"/>'
        '<path d="m6 16 4-4 3 3 2-2 3 3M16.5 7.5h.01"/>'
    ),
    "quality": (
        '<path d="M12 3 20 6v5c0 5-3.4 8.2-8 10-4.6-1.8-8-5-8-10V6l8-3Z"/>'
        '<path d="m8.5 12 2.2 2.2 4.8-5"/>'
    ),
    "data": (
        '<ellipse cx="12" cy="5.5" rx="8" ry="3"/>'
        '<path d="M4 5.5v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>'
        '<path d="M4 11.5v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>'
    ),
    "engine": (
        '<circle cx="12" cy="12" r="3.5"/>'
        '<path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3"/>'
        '<path d="m5.3 5.3 2.1 2.1m9.2 9.2 2.1 2.1M18.7 5.3l-2.1 2.1m-9.2 9.2-2.1 2.1"/>'
    ),
    "artifact": (
        '<path d="M6 3h8l4 4v14H6V3Z"/>'
        '<path d="M14 3v5h5M9 12h6M9 16h6"/>'
    ),
    "reproducibility": (
        '<path d="M19 8a8 8 0 0 0-13-2L4 8"/>'
        '<path d="M4 4v4h4M5 16a8 8 0 0 0 13 2l2-2"/>'
        '<path d="M20 20v-4h-4"/>'
    ),
    "theme": (
        '<path d="M12 3a9 9 0 1 0 0 18h1.5a2 2 0 0 0 0-4H12a2 2 0 0 1 0-4h3a6 6 0 0 0 6-6c0-2.2-4-4-9-4Z"/>'
        '<circle cx="7.5" cy="9" r=".8" fill="currentColor" stroke="none"/>'
        '<circle cx="10" cy="6.5" r=".8" fill="currentColor" stroke="none"/>'
        '<circle cx="14" cy="6.5" r=".8" fill="currentColor" stroke="none"/>'
    ),
    "distribution": (
        '<circle cx="12" cy="5" r="2"/><circle cx="5" cy="19" r="2"/>'
        '<circle cx="19" cy="19" r="2"/>'
        '<path d="M12 7v5M5 17v-2a3 3 0 0 1 3-3h8a3 3 0 0 1 3 3v2"/>'
    ),
    "user": (
        '<circle cx="12" cy="8" r="4"/>'
        '<path d="M4.5 21a7.5 7.5 0 0 1 15 0"/>'
    ),
    "api": (
        '<path d="M8 5H5v14h3M16 5h3v14h-3"/>'
        '<path d="M9 9h6M12 6l3 3-3 3M15 15H9M12 12l-3 3 3 3"/>'
    ),
    "chart": (
        '<path d="M4 3v17h17"/>'
        '<path d="m7 15 4-5 3 2 5-7"/>'
        '<circle cx="7" cy="15" r="1"/><circle cx="11" cy="10" r="1"/>'
        '<circle cx="14" cy="12" r="1"/><circle cx="19" cy="5" r="1"/>'
    ),
    "diagram": (
        '<rect x="3" y="4" width="7" height="5" rx="1"/>'
        '<rect x="14" y="15" width="7" height="5" rx="1"/>'
        '<path d="M10 6.5h3a4 4 0 0 1 4 4V15M14 12l3 3 3-3"/>'
    ),
    "queue": (
        '<path d="M4 7h12M4 12h16M4 17h12"/>'
        '<path d="m14 4 3 3-3 3M14 14l3 3-3 3"/>'
    ),
    "storage": (
        '<path d="M5 4h14v16H5zM8 8h8M8 12h8M8 16h5"/>'
    ),
    "security": (
        '<rect x="5" y="10" width="14" height="11" rx="2"/>'
        '<path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3"/>'
    ),
    "monitor": (
        '<path d="M3 12h4l2-5 4 10 2-5h6"/>'
        '<rect x="3" y="3" width="18" height="18" rx="3"/>'
    ),
}


def render_icon(
    name: str,
    x: float,
    y: float,
    size: float,
    color: str,
) -> str:
    requested = str(name).strip().lower()
    resolved = requested if requested in _ICONS else "diagram"
    scale = size / 24
    fallback = (
        f' data-icon-fallback="{html.escape(resolved)}"'
        if requested != resolved
        else ""
    )
    return (
        f'<g data-icon="{html.escape(requested)}"{fallback} aria-hidden="true" '
        f'transform="translate({x:.1f} {y:.1f}) scale({scale:.4f})" '
        f'fill="none" stroke="{color}" stroke-width="1.8" '
        f'stroke-linecap="round" stroke-linejoin="round" '
        f'color="{color}">{_ICONS[resolved]}</g>'
    )
