from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_theme(spec: dict[str, Any], skill_root: Path) -> dict[str, Any]:
    preset = spec.get("style", {}).get("preset", "paper-light")
    path = skill_root / "assets/themes" / f"{preset}.json"
    if not path.is_file():
        raise ValueError(f"Unknown style preset: {preset}")
    theme = json.loads(path.read_text(encoding="utf-8"))
    overrides = spec.get("style", {}).get("overrides", {})
    if not isinstance(overrides, dict):
        raise ValueError("style.overrides must be an object")
    theme.update(overrides)
    return theme
