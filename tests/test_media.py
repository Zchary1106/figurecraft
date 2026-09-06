from __future__ import annotations

import copy
import importlib.util
import io
import re
import shutil
import sys
import unittest
import uuid
import warnings
import zlib
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/figurecraft"
sys.path.insert(0, str(SKILL / "scripts"))

from figurelib.media import apply_svg_media, prepare_media, raster_dpi


def svg_text(content: str = '<text font-size="32">Readable</text>', width: int = 720, height: int = 360) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">{content}</svg>'


def pdf_media_box(pdf: bytes) -> tuple[float, float] | None:
    contents = [pdf]
    # Cairo 1.18+ can place page dictionaries in Flate-compressed object streams.
    for stream in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", pdf, flags=re.S):
        try:
            contents.append(zlib.decompress(stream[1]))
        except zlib.error:
            continue
    for content in contents:
        match = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)", content)
        if match:
            return float(match[1]), float(match[2])
    return None


class MediaTests(unittest.TestCase):
    def test_raster_dpi_defaults_and_explicit_overrides(self) -> None:
        self.assertEqual(raster_dpi({}), 300)
        self.assertEqual(raster_dpi({"layout": {"medium": "paper-double"}}), 300)
        self.assertEqual(raster_dpi({"layout": {"medium": "slide"}}), 96)
        self.assertEqual(raster_dpi({"layout": {"medium": "slide"}, "output": {"dpi": 192}}), 192)
        self.assertEqual(raster_dpi({"layout": {"medium": "web"}, "output": {"dpi": 120.5}}), 120.5)

    def test_legacy_and_web_preserve_svg_exactly(self) -> None:
        svg = svg_text('<text font-size="2">Native web labels</text>')
        for layout in ({}, {"aspect_ratio": 2}, {"medium": "web"}):
            with self.subTest(layout=layout):
                result, media = apply_svg_media(svg, {"layout": layout})
                self.assertEqual(result, svg)
                self.assertEqual(media["min_font_pt"], 1.5)
                self.assertIsNone(media["required_min_font_pt"])
                self.assertEqual(media["explicit"], "medium" in layout)

    def test_paper_widths_and_physical_font_measurements(self) -> None:
        for medium, width in (("paper-single", 85), ("paper-double", 180)):
            with self.subTest(medium=medium):
                result, media = apply_svg_media(svg_text(), {"layout": {"medium": medium}})
                root = ET.fromstring(result)
                self.assertEqual(root.get("width"), f"{width}mm")
                self.assertEqual(root.get("height"), f"{width / 2:g}mm")
                self.assertAlmostEqual(media["width_mm"], width)
                self.assertAlmostEqual(media["min_font_pt"], 32 * width * 72 / (25.4 * 720))
                self.assertEqual(media["required_min_font_pt"], 7)
                self.assertEqual(media["smallest_text"]["source_font_size"], "32")
                self.assertTrue(media["explicit"])

    def test_default_paper_height_cap_rejects_unbounded_canvas(self) -> None:
        svg = svg_text('<text font-size="10">Overlong figure</text>', width=100, height=10000)
        for layout in ({"medium": "paper-single"}, {"medium": "paper-double"}, {"width_mm": 180}):
            with self.subTest(layout=layout), self.assertRaisesRegex(ValueError, "render-set / split"):
                apply_svg_media(svg, {"layout": layout})

    def test_paper_height_cap_preserves_short_figures_and_explicit_override(self) -> None:
        _, media = apply_svg_media(svg_text(), {"layout": {"medium": "paper-double"}})
        self.assertEqual(media["height_mm"], 90)
        self.assertEqual(media["default_max_height_mm"], 240)
        self.assertFalse(media["height_capped"])
        tall = svg_text('<text font-size="320">Readable tall figure</text>', width=100, height=10000)
        _, capped = apply_svg_media(tall, {"layout": {"medium": "paper-double"}})
        self.assertAlmostEqual(capped["height_mm"], 240)
        self.assertTrue(capped["height_capped"])
        self.assertTrue(capped["letterboxed"])
        _, explicit = apply_svg_media(tall, {"layout": {"medium": "paper-double", "height_mm": 480}})
        self.assertAlmostEqual(explicit["height_mm"], 480)
        self.assertIsNone(explicit["default_max_height_mm"])
        self.assertFalse(explicit["height_capped"])

    def test_explicit_width_enforces_seven_point_minimum(self) -> None:
        svg = svg_text('<text font-size="14">A publication label</text>')
        with self.assertRaisesRegex(ValueError, r"4\.69pt.*7pt.*render-set / split"):
            apply_svg_media(svg, {"layout": {"width_mm": 85}})
        _, media = apply_svg_media(svg, {"layout": {"width_mm": 180}})
        self.assertGreater(media["min_font_pt"], 7)

    def test_exact_font_threshold_and_no_text(self) -> None:
        size = 7 * 720 * 25.4 / (85 * 72)
        _, media = apply_svg_media(svg_text(f'<text font-size="{size}">Boundary</text>'), {"layout": {"width_mm": 85}})
        self.assertAlmostEqual(media["min_font_pt"], 7)
        _, media = apply_svg_media(svg_text('<text font-size="1"> \n </text>'), {"layout": {"medium": "paper-single"}})
        self.assertIsNone(media["min_font_pt"])
        self.assertEqual(media["text_run_count"], 0)

    def test_inheritance_tspan_tail_css_units_and_transforms(self) -> None:
        svg = svg_text('''
          <style>.label { font-size: 32px } text.small { font-size: 8pt }</style>
          <g class="label" transform="translate(4 5) rotate(90)">
            <text><tspan font-size="50%">Half</tspan>Parent tail</text>
            <text class="small" style="font-size: 2em">Inline wins</text>
          </g>
          <text font-size="2"></text>
          <text visibility="hidden" font-size="1">Hidden</text>
          <defs><text font-size="1">Unused</text></defs>
        ''')
        _, media = apply_svg_media(svg, {"layout": {"medium": "web", "min_font_px": 16}})
        self.assertEqual(media["min_font_px"], 16)
        self.assertEqual(media["smallest_text"]["text"], "Half")
        self.assertEqual(media["smallest_text"]["source_font_size"], "50%")
        self.assertEqual(media["text_run_count"], 3)

    def test_tiny_child_and_tail_are_not_hidden_by_parent_size(self) -> None:
        for content in (
            '<text font-size="40"><tspan font-size="1">Tiny child</tspan></text>',
            '<text font-size="1"><tspan font-size="40">Large child</tspan>Tiny tail</text>',
            '<g font-size="40" transform="scale(.02)"><text>Scaled tiny</text></g>',
            '<text style="font: 1px sans-serif">Shorthand tiny</text>',
        ):
            with self.subTest(content=content), self.assertRaisesRegex(ValueError, "render-set / split"):
                apply_svg_media(svg_text(content), {"layout": {"medium": "paper-double"}})

    def test_important_css_referenced_text_and_nested_viewport(self) -> None:
        cases = (
            '<style>.tiny {font: 1px sans-serif !important}</style><text class="tiny" style="font-size: 40px">Tiny CSS</text>',
            '<defs><g id="label"><text font-size="1">Referenced tiny</text></g></defs><use href="#label"/>',
            '<svg width="10" height="10" viewBox="0 0 100 100"><text font-size="10">Nested tiny</text></svg>',
        )
        for content in cases:
            with self.subTest(content=content), self.assertRaisesRegex(ValueError, "render-set / split"):
                apply_svg_media(svg_text(content), {"layout": {"medium": "paper-double"}})

    def test_letterbox_sixteen_by_nine_preserves_geometry(self) -> None:
        svg = svg_text(width=400, height=400)
        result, media = apply_svg_media(svg, {"layout": {"width_mm": 180, "aspect_ratio": 16 / 9}})
        root = ET.fromstring(result)
        self.assertEqual(root.get("width"), "180mm")
        self.assertEqual(root.get("height"), "101.25mm")
        x, y, width, height = map(float, root.get("viewBox").split())
        self.assertAlmostEqual(width / height, 16 / 9)
        self.assertAlmostEqual(x, -(width - 400) / 2)
        self.assertEqual(y, 0)
        self.assertTrue(media["letterboxed"])
        self.assertAlmostEqual(media["min_font_pt"], 32 * 101.25 * 72 / (25.4 * 400))
        self.assertIn('<text font-size="32">Readable</text>', result)

    def test_slide_fixed_pixels_letterbox_and_pixel_threshold(self) -> None:
        svg = svg_text('<text font-size="20">Slide text</text>', width=1000, height=1000)
        result, media = apply_svg_media(svg, {"layout": {"medium": "slide"}})
        root = ET.fromstring(result)
        self.assertEqual((root.get("width"), root.get("height")), ("1920", "1080"))
        self.assertAlmostEqual(media["min_font_px"], 21.6)
        self.assertEqual(media["required_min_font_px"], 18)
        with self.assertRaisesRegex(ValueError, r"18px.*render-set / split"):
            apply_svg_media(svg.replace('"20"', '"10"'), {"layout": {"medium": "slide"}})

    def test_explicit_height_and_custom_minimum(self) -> None:
        _, media = apply_svg_media(svg_text(), {"layout": {"height_mm": 50, "min_font_pt": 5}})
        self.assertAlmostEqual(media["height_mm"], 50)
        self.assertAlmostEqual(media["width_mm"], 100)
        self.assertEqual(media["required_min_font_pt"], 5)
        with self.assertRaisesRegex(ValueError, "40px"):
            apply_svg_media(svg_text(), {"layout": {"medium": "web", "min_font_px": 40}})

    def test_inline_canvas_sizes_cannot_override_physical_output(self) -> None:
        svg = svg_text().replace('width="720"', 'width="720" style="width: 720px; height: 360px; font: bold 32px serif"')
        result, media = apply_svg_media(svg, {"layout": {"medium": "paper-single"}})
        style = ET.fromstring(result).get("style")
        self.assertIn("width: 85mm !important", style)
        self.assertIn("font: bold 32px serif", style)
        self.assertAlmostEqual(media["width_mm"], 85)

    def test_prepare_copies_and_configures_chart_without_changing_diagram_fonts(self) -> None:
        spec = {"kind": "chart.line", "layout": {"medium": "slide"}}
        theme = {"font_size": 10, "palette": ["red"]}
        before_spec, before_theme = copy.deepcopy(spec), copy.deepcopy(theme)
        configured, configured_theme = prepare_media(spec, theme)
        self.assertEqual(spec, before_spec)
        self.assertEqual(theme, before_theme)
        self.assertEqual(configured["layout"]["width_mm"], 508)
        self.assertEqual(configured["layout"]["height_mm"], 285.75)
        self.assertGreaterEqual(configured_theme["font_size"] - 2, 18 * 72 / 96)
        configured_theme["palette"].append("blue")
        self.assertEqual(theme["palette"], ["red"])
        _, diagram_theme = prepare_media({"kind": "diagram.architecture", "layout": {"medium": "slide"}}, theme)
        self.assertEqual(diagram_theme, theme)

    def test_invalid_media_values_rejected_standalone(self) -> None:
        for layout in ({"medium": "poster"}, {"medium": None}, {"width_mm": 0}, {"height_mm": -2},
                       {"min_font_px": True}, {"min_font_pt": float("nan")}):
            with self.subTest(layout=layout), self.assertRaises(ValueError):
                apply_svg_media(svg_text(), {"layout": layout})

    @unittest.skipUnless(importlib.util.find_spec("cairosvg"), "CairoSVG is optional")
    def test_real_cairo_physical_png_and_pdf_sizes(self) -> None:
        import cairosvg
        from PIL import Image

        for width in (85, 180):
            svg, _ = apply_svg_media(svg_text(), {"layout": {"width_mm": width}})
            sizes = []
            for dpi in (96, 192):
                png = cairosvg.svg2png(bytestring=svg.encode(), dpi=96, scale=dpi / 96)
                with Image.open(io.BytesIO(png)) as image:
                    sizes.append(image.size)
                    self.assertAlmostEqual(image.width, width / 25.4 * dpi, delta=1)
            self.assertAlmostEqual(sizes[1][0], sizes[0][0] * 2, delta=1)
            pdf = cairosvg.svg2pdf(bytestring=svg.encode(), dpi=96)
            box = pdf_media_box(pdf)
            self.assertIsNotNone(box)
            self.assertAlmostEqual(box[0], width / 25.4 * 72, places=3)
            self.assertAlmostEqual(box[1], width / 2 / 25.4 * 72, places=3)


class ChartMediaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = ROOT / "tests" / f".media-output-{uuid.uuid4().hex}"
        self.directory.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.directory)

    def test_real_chart_paper_width_and_readable_source_type(self) -> None:
        from figurelib.charts import render_chart
        from figurelib.styles import load_theme

        for medium, width in (("paper-single", 85), ("paper-double", 180), ("slide", 508)):
            spec = {
                "kind": "chart.line", "layout": {"medium": medium},
                "data": {"columns": {"x": [1, 2, 3], "y": [2, 4, 3]}},
                "output": {"primary": "svg", "additional": ["png", "pdf"], "dpi": 96},
            }
            before = copy.deepcopy(spec)
            _, metadata = render_chart(spec, self.directory / "spec.json", self.directory, load_theme(spec, SKILL))
            self.assertEqual(spec, before)
            media = metadata["media"]
            self.assertAlmostEqual(media["width_mm"], width)
            if medium == "slide":
                self.assertGreaterEqual(media["min_font_px"], 18)
            else:
                self.assertGreaterEqual(media["min_font_pt"], 7)
            from PIL import Image
            with Image.open(self.directory / "figure.png") as image:
                self.assertAlmostEqual(image.width, width / 25.4 * 96, delta=1)
                if medium == "slide":
                    self.assertEqual(image.size, (1920, 1080))
            self.assertTrue((self.directory / "figure.pdf").read_bytes().startswith(b"%PDF"))
            pdf = (self.directory / "figure.pdf").read_bytes()
            box = pdf_media_box(pdf)
            self.assertIsNotNone(box)
            self.assertAlmostEqual(box[0], width / 25.4 * 72, places=3)

    def test_gantt_slide_and_legacy_chart_dimensions(self) -> None:
        from figurelib.charts import render_chart, render_gantt
        from figurelib.styles import load_theme

        spec = {"kind": "project.gantt", "layout": {"medium": "slide"},
                "output": {"primary": "svg", "additional": ["png"]},
                "tasks": [{"label": "Build", "start": "2026-09-01", "end": "2026-09-04"}]}
        _, metadata = render_gantt(spec, self.directory, load_theme(spec, SKILL))
        self.assertEqual(metadata["media"]["width_px"], 1920)
        self.assertEqual(metadata["media"]["height_px"], 1080)
        self.assertGreaterEqual(metadata["media"]["min_font_px"], 18)
        from PIL import Image
        with Image.open(self.directory / "figure.png") as image:
            self.assertEqual(image.size, (1920, 1080))
        spec = {"kind": "chart.line", "data": {"columns": {"x": [1, 2], "y": [1, 2]}}}
        _, metadata = render_chart(spec, self.directory / "spec.json", self.directory, load_theme(spec, SKILL))
        self.assertAlmostEqual(metadata["media"]["width_mm"], 178, places=5)
        self.assertFalse(metadata["media"]["explicit"])

    def test_chart_default_slide_pixels_and_paper_dpi(self) -> None:
        from figurelib.charts import render_chart
        from figurelib.styles import load_theme
        from PIL import Image

        for medium, dpi in (("slide", None), ("slide", 192), ("paper-double", None)):
            with self.subTest(medium=medium, dpi=dpi):
                spec = {
                    "kind": "chart.line", "layout": {"medium": medium},
                    "data": {"columns": {"x": [1, 2], "y": [2, 3]}},
                    "output": {"primary": "svg", "additional": ["png"]},
                }
                if dpi is not None:
                    spec["output"]["dpi"] = dpi
                _, metadata = render_chart(spec, self.directory / "spec.json", self.directory, load_theme(spec, SKILL))
                with Image.open(self.directory / "figure.png") as image:
                    if medium == "slide":
                        self.assertEqual(image.size, (1920, 1080) if dpi is None else (3840, 2160))
                    else:
                        self.assertAlmostEqual(image.width, 180 / 25.4 * 300, delta=1)
                        self.assertAlmostEqual(image.height, metadata["media"]["height_mm"] / 25.4 * 300, delta=1)

    @unittest.skipUnless(importlib.util.find_spec("cairosvg"), "CairoSVG is optional")
    def test_diagram_default_slide_pixels_and_paper_dpi(self) -> None:
        from figurelib.diagrams import render_diagram
        from figurelib.styles import load_theme
        from PIL import Image

        for medium, dpi in (("slide", None), ("slide", 192), ("paper-double", None)):
            with self.subTest(medium=medium, dpi=dpi):
                spec = {
                    "kind": "diagram.architecture", "layout": {"medium": medium},
                    "nodes": [{"id": "source", "label": "Readable geometry"}],
                    "output": {"primary": "svg", "additional": ["png"]},
                }
                if dpi is not None:
                    spec["output"]["dpi"] = dpi
                _, metadata, _ = render_diagram(spec, self.directory, load_theme(spec, SKILL))
                with Image.open(self.directory / "figure.png") as image:
                    if medium == "slide":
                        self.assertEqual(image.size, (1920, 1080) if dpi is None else (3840, 2160))
                    else:
                        self.assertAlmostEqual(image.width, 180 / 25.4 * 300, delta=1)
                        self.assertAlmostEqual(image.height, metadata["media"]["height_mm"] / 25.4 * 300, delta=1)

    def test_chart_provenance_is_visible_and_measured_on_fixed_page(self) -> None:
        from figurelib.charts import render_chart
        from figurelib.styles import load_theme

        spec = {
            "kind": "chart.line", "layout": {"medium": "paper-single"},
            "data": {"columns": {"x": [1, 2], "y": [2, 3]}},
            "provenance": {"type": "conceptual", "summary": "Illustrative values, not measured results."},
            "output": {"primary": "svg", "additional": ["png", "pdf"]},
        }
        _, metadata = render_chart(spec, self.directory / "spec.json", self.directory, load_theme(spec, SKILL))
        svg = ET.parse(self.directory / "figure.svg").getroot()
        footer = next(element for element in svg.iter() if element.get("id") == "figure-provenance")
        text = " ".join(footer.itertext())
        self.assertIn("Conceptual illustration", text)
        self.assertIn("Illustrative values", text)
        self.assertAlmostEqual(metadata["media"]["width_mm"], 85)
        self.assertGreaterEqual(metadata["media"]["min_font_pt"], 7)
        self.assertTrue((self.directory / "figure.png").is_file())
        self.assertTrue((self.directory / "figure.pdf").is_file())

    def test_oversized_provenance_fails_instead_of_overlapping_chart(self) -> None:
        from figurelib.charts import render_chart
        from figurelib.styles import load_theme

        spec = {
            "kind": "chart.line", "layout": {"medium": "paper-single", "height_mm": 40},
            "data": {"columns": {"x": [1, 2], "y": [2, 3]}},
            "provenance": {"type": "conceptual", "summary": "Long explanatory claim. " * 80},
        }
        with warnings.catch_warnings(), self.assertRaisesRegex(ValueError, "render-set / split"):
            warnings.simplefilter("ignore", UserWarning)
            render_chart(spec, self.directory / "spec.json", self.directory, load_theme(spec, SKILL))
        self.assertFalse(list(self.directory.iterdir()))

    def test_overheight_chart_cannot_export_uncapped_png_or_pdf(self) -> None:
        from figurelib.charts import render_chart
        from figurelib.styles import load_theme

        spec = {
            "kind": "chart.line", "layout": {"medium": "paper-double", "aspect_ratio": 0.5},
            "data": {"columns": {"x": [1, 2], "y": [2, 3]}},
            "output": {"primary": "png", "additional": ["pdf"]},
        }
        theme = {**load_theme(spec, SKILL), "font_size": 30}
        with patch("matplotlib.pyplot.subplots") as allocate:
            with self.assertRaisesRegex(ValueError, "240mm.*render-set / split"):
                render_chart(spec, self.directory / "spec.json", self.directory, theme)
            allocate.assert_not_called()
        self.assertFalse(list(self.directory.iterdir()))

    def test_overheight_gantt_is_rejected_before_canvas_allocation(self) -> None:
        from figurelib.charts import render_gantt
        from figurelib.styles import load_theme

        spec = {
            "kind": "project.gantt", "layout": {"medium": "paper-double"},
            "tasks": [{"label": f"Task {index}", "start": "2026-09-01", "end": "2026-09-04"} for index in range(100)],
            "output": {"primary": "png", "additional": ["pdf"]},
        }
        with patch("matplotlib.pyplot.subplots") as allocate:
            with self.assertRaisesRegex(ValueError, "240mm.*render-set / split"):
                render_gantt(spec, self.directory, load_theme(spec, SKILL))
            allocate.assert_not_called()
        self.assertFalse(list(self.directory.iterdir()))

    def test_explicit_tall_chart_height_is_consistent_in_all_formats(self) -> None:
        from figurelib.charts import render_chart
        from figurelib.styles import load_theme
        from PIL import Image

        spec = {
            "kind": "chart.line", "layout": {"medium": "paper-double", "height_mm": 300},
            "data": {"columns": {"x": [1, 2], "y": [2, 3]}},
            "output": {"primary": "svg", "additional": ["png", "pdf"], "dpi": 96},
        }
        _, metadata = render_chart(spec, self.directory / "spec.json", self.directory, load_theme(spec, SKILL))
        self.assertAlmostEqual(metadata["media"]["height_mm"], 300)
        self.assertIsNone(metadata["media"]["default_max_height_mm"])
        self.assertEqual(ET.parse(self.directory / "figure.svg").getroot().get("height"), "300mm")
        with Image.open(self.directory / "figure.png") as image:
            self.assertAlmostEqual(image.height, 300 / 25.4 * 96, delta=1)
        box = pdf_media_box((self.directory / "figure.pdf").read_bytes())
        self.assertIsNotNone(box)
        self.assertAlmostEqual(box[1], 300 / 25.4 * 72, places=3)


if __name__ == "__main__":
    unittest.main()
