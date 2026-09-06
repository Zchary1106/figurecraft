from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/figurecraft"
sys.path.insert(0, str(SKILL / "scripts"))

from figurelib.diagrams import render_diagram
from figurelib.styles import load_theme


class RasterExportTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("cairosvg"), "CairoSVG is optional")
    def test_png_dpi_scales_pixels_without_changing_vector_canvas(self) -> None:
        spec = {
            "kind": "diagram.architecture",
            "nodes": [{"id": "n", "label": "Export resolution"}],
            "output": {"primary": "svg", "additional": ["png", "pdf"], "dpi": 96},
        }
        sizes = []
        canvases = []
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            for dpi in (96, 192):
                spec["output"]["dpi"] = dpi
                render_diagram(spec, output, load_theme(spec, SKILL))
                with Image.open(output / "figure.png") as image:
                    sizes.append(image.size)
                canvases.append((output / "figure.svg").read_text())
                self.assertTrue((output / "figure.pdf").read_bytes().startswith(b"%PDF-"))
        self.assertEqual(sizes[1], tuple(value * 2 for value in sizes[0]))
        self.assertEqual(canvases[0], canvases[1])


if __name__ == "__main__":
    unittest.main()
