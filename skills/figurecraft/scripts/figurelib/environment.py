"""Non-installing runtime probes for the local Python interpreter."""

from __future__ import annotations

import importlib
import importlib.metadata
import io
import shlex
import sys
from typing import Any, Callable

from .typography import measure_text


_SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="2" height="2"><rect width="2" height="2" fill="black"/></svg>'
_CJK_SAMPLE = "中文图表"
_CJK_HELP = (
    "Install Noto Sans CJK SC (Linux: sudo apt-get install fonts-noto-cjk), "
    "or enable PingFang SC on macOS / Microsoft YaHei on Windows. Restart Python "
    "after installing fonts; set style.overrides.svg_font_family for custom fonts. "
    "The CJK probe covers a sample, not every glyph in your figure."
)
_CAIRO_HELP = (
    "Install native Cairo: macOS: brew install cairo; Debian/Ubuntu: "
    "sudo apt-get install libcairo2; Windows: install Cairo via MSYS2 "
    "(pacman -S mingw-w64-x86_64-cairo) and make its bin directory available "
    "to the Python process. On Apple Silicon Homebrew normally installs "
    "libcairo.2.dylib at /opt/homebrew/lib/libcairo.2.dylib; if discovery fails, "
    "launch the command with DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib. "
    "Use matching Python/Cairo architectures; no environment variables are changed by this check."
)


def _pip(*packages: str) -> str:
    arguments = [sys.executable, "-m", "pip", "install", "--upgrade", *packages]
    if sys.platform == "win32":
        return "& " + " ".join("'" + argument.replace("'", "''") + "'" for argument in arguments)
    return shlex.join(arguments)


def _probe(action: Callable[[], Any], distribution: str | None = None) -> dict[str, Any]:
    version = None
    if distribution:
        try:
            version = importlib.metadata.version(distribution)
        except (importlib.metadata.PackageNotFoundError, ValueError, OSError):
            pass
    try:
        action()
    except (ImportError, OSError, RuntimeError, ValueError, AttributeError) as exc:
        # Exception messages can contain private paths or environment values.
        return {"available": False, "version": version,
                "detail": f"Runtime probe failed ({type(exc).__name__})"}
    return {"available": True, "version": version, "detail": "Runtime probe passed"}


def _font_probe(text: str) -> None:
    if measure_text(text, 12) <= 0:
        raise RuntimeError("Font measurement is empty")


def _matplotlib_probe() -> None:
    importlib.import_module("matplotlib")
    figure = importlib.import_module("matplotlib.figure").Figure(figsize=(1, 1))
    figure.add_subplot().plot([0, 1], [0, 1])


def _chart_probe(extension: str) -> None:
    figure = importlib.import_module("matplotlib.figure").Figure(figsize=(1, 1))
    importlib.import_module("matplotlib.backends.backend_agg").FigureCanvasAgg(figure)
    figure.add_subplot().plot([0, 1], [0, 1])
    output = io.BytesIO()
    figure.savefig(output, format=extension)
    if not output.getvalue():
        raise RuntimeError("Empty chart export")


def _cairo_probe() -> None:
    cairo = importlib.import_module("cairocffi")
    if not cairo.cairo_version_string():
        raise RuntimeError("Native Cairo unavailable")


def _conversion_probe(extension: str) -> None:
    cairo = importlib.import_module("cairosvg")
    data = getattr(cairo, f"svg2{extension}")(bytestring=_SVG)
    signature = b"\x89PNG\r\n\x1a\n" if extension == "png" else b"%PDF"
    if not data.startswith(signature):
        raise RuntimeError("Invalid conversion output")


def environment_report(
    formats: list[str] | None = None,
    kind: str = "diagram.architecture",
    check_cjk: bool = False,
) -> dict[str, Any]:
    """Report tested capabilities; only requirements of the selected pipeline gate ready.

    No formats selects the baseline SVG pipeline, while still probing optional
    exports. CJK availability is always reported but only gates ready on request.
    """
    family = "chart" if kind.startswith("chart.") or kind == "project.gantt" else "diagram"
    if family == "diagram" and not kind.startswith("diagram."):
        raise ValueError(f"Unsupported figure kind: {kind}")
    requested = sorted({str(item).lower().lstrip(".") for item in formats or ["svg"]})
    supported = {"svg", "png", "pdf"} | ({"drawio"} if family == "diagram" else set())
    unsupported = sorted(set(requested) - supported)
    if unsupported:
        raise ValueError(f"Unsupported {family} formats: {', '.join(unsupported)}")

    dependencies = {
        "matplotlib": _probe(_matplotlib_probe, "matplotlib"),
        "numpy": _probe(lambda: importlib.import_module("numpy").array([1]).sum(), "numpy"),
        "jsonschema": _probe(
            lambda: importlib.import_module("jsonschema").validate({}, {"type": "object"}),
            "jsonschema",
        ),
        "yaml": _probe(lambda: importlib.import_module("yaml").safe_load("probe: true"), "PyYAML"),
        "font-metrics": _probe(lambda: _font_probe("FigureCraft")),
        "cjk-fonts": _probe(lambda: _font_probe(_CJK_SAMPLE)),
        "cairosvg": _probe(lambda: importlib.import_module("cairosvg"), "CairoSVG"),
        "native-cairo": _probe(_cairo_probe),
    }
    if not dependencies["cjk-fonts"]["available"]:
        dependencies["cjk-fonts"]["detail"] = (
            f"Cannot measure CJK sample {_CJK_SAMPLE!r}; font runtime or glyph coverage is missing"
        )
    for extension in ("svg", "png", "pdf"):
        dependencies[f"chart-{extension}"] = _probe(lambda ext=extension: _chart_probe(ext))
    for extension in ("png", "pdf"):
        dependencies[f"cairo-{extension}"] = _probe(lambda ext=extension: _conversion_probe(ext))

    base = ["matplotlib", "numpy", "jsonschema", "font-metrics"]
    needs = {
        "diagram.svg": base,
        "diagram.drawio": base,
        "diagram.png": base + ["cairosvg", "native-cairo", "cairo-png"],
        "diagram.pdf": base + ["cairosvg", "native-cairo", "cairo-pdf"],
        **{f"chart.{ext}": ["matplotlib", "numpy", "jsonschema", f"chart-{ext}"]
           for ext in ("svg", "png", "pdf")},
        "yaml-input": ["yaml"],
        "cjk-text": ["matplotlib", "font-metrics", "cjk-fonts"],
    }
    required = {f"{family}.{ext}" for ext in requested}
    if check_cjk:
        required.add("cjk-text")
    capabilities = {
        name: {"available": all(dependencies[item]["available"] for item in items),
               "required": name in required, "dependencies": list(items)}
        for name, items in needs.items()
    }
    issues = []
    remedies = []
    failed = set()
    for name, capability in capabilities.items():
        if not capability["available"]:
            missing = [item for item in capability["dependencies"] if not dependencies[item]["available"]]
            failed.update(missing)
            issues.append({"capability": name, "required": capability["required"],
                           "message": f"{name} unavailable: {', '.join(missing)}"})
    if failed & {"matplotlib", "numpy", "jsonschema", "font-metrics",
                 "chart-svg", "chart-png", "chart-pdf"}:
        remedies.append(_pip("matplotlib>=3.8", "numpy>=1.26", "jsonschema>=4.20"))
    if "yaml" in failed:
        remedies.append(_pip("PyYAML>=6.0"))
    if failed & {"cairosvg", "native-cairo", "cairo-png", "cairo-pdf"}:
        remedies.extend([_pip("CairoSVG>=2.7"), _CAIRO_HELP])
    if "cjk-fonts" in failed or (check_cjk and "font-metrics" in failed):
        remedies.append(_CJK_HELP)
    return {
        "ready": not any(issue["required"] for issue in issues),
        "capabilities": capabilities, "dependencies": dependencies,
        "issues": issues, "remedies": remedies,
    }


def format_environment_report(report: dict[str, Any]) -> str:
    lines = [f"ready={'yes' if report['ready'] else 'no'}"]
    for name, dependency in report["dependencies"].items():
        status = "available" if dependency["available"] else "unavailable"
        version = f" ({dependency['version']})" if dependency.get("version") else ""
        lines.append(f"{name}={status}{version}: {dependency['detail']}")
    for name, capability in report["capabilities"].items():
        status = "available" if capability["available"] else "unavailable"
        requirement = "required" if capability["required"] else "optional"
        lines.append(f"{name}={status} ({requirement})")
    lines.extend(f"remedy: {remedy}" for remedy in report["remedies"])
    return "\n".join(lines)
