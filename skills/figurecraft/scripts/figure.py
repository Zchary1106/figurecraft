#!/usr/bin/env python3
"""Validate, render, and lint FigureCraft FigureSpecs."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from figurelib.bootstrap import run


if __name__ == "__main__":
    try:
        raise SystemExit(run(SCRIPT_DIR / ".figurecraft-runtime.json"))
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"FigureCraft: {exc}", file=sys.stderr)
        raise SystemExit(2)
