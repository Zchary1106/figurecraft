from __future__ import annotations

import datetime as dt
import html
import inspect
import io
from pathlib import Path
from typing import Any

from .io import load_columns
from .media import apply_svg_media, prepare_media, raster_dpi
from .provenance import provenance_description
from .validate import validate_chart_data


def render_chart(
    spec: dict[str, Any],
    spec_path: Path,
    output_dir: Path,
    theme: dict[str, Any],
) -> tuple[list[Path], dict[str, Any]]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    spec, theme = prepare_media(spec, theme)
    columns = (
        {}
        if spec["kind"] == "chart.heatmap" and "matrix" in spec.get("data", {})
        else load_columns(spec, spec_path)
    )
    if columns:
        errors = validate_chart_data(spec, columns)
        if errors:
            raise ValueError("\n".join(errors))
    layout = spec.get("layout", {})
    width_mm = float(layout.get("width_mm", 178))
    aspect = float(layout.get("aspect_ratio", 1.6))
    width_in = width_mm / 25.4
    height_in = float(layout["height_mm"]) / 25.4 if "height_mm" in layout else width_in / aspect

    with plt.rc_context(_rc_params(theme)):
        fig, ax = plt.subplots(figsize=(width_in, height_in), constrained_layout=True)
        kind = spec["kind"]
        if kind == "chart.line":
            _line(ax, spec, columns, theme, scatter=False)
        elif kind == "chart.scatter":
            _line(ax, spec, columns, theme, scatter=True)
        elif kind == "chart.errorbar":
            _errorbar(ax, spec, columns, theme)
        elif kind == "chart.bar":
            _bar(ax, spec, columns, theme)
        elif kind == "chart.histogram":
            _histogram(ax, spec, columns, theme)
        elif kind == "chart.box":
            _box(ax, spec, columns, theme)
        elif kind == "chart.heatmap":
            _heatmap(fig, ax, spec, columns, theme, np)
        else:
            raise ValueError(f"Unsupported chart kind: {kind}")
        _decorate(ax, spec, theme, show_grid=kind != "chart.heatmap")
        _add_provenance(fig, spec, theme)
        media: dict[str, Any] = {}
        try:
            outputs = _save(fig, spec, output_dir, media)
        finally:
            plt.close(fig)
    return outputs, {"renderer": "matplotlib", "matplotlib": matplotlib.__version__, "media": media}


def render_gantt(
    spec: dict[str, Any],
    output_dir: Path,
    theme: dict[str, Any],
) -> tuple[list[Path], dict[str, Any]]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    spec, theme = prepare_media(spec, theme)
    tasks = spec["tasks"]
    layout = spec.get("layout", {})
    width_mm = float(layout.get("width_mm", 178))
    height_in = max(2.5, 0.42 * len(tasks) + 1.2)
    if "height_mm" in layout:
        height_in = float(layout["height_mm"]) / 25.4
    elif "aspect_ratio" in layout:
        height_in = width_mm / 25.4 / float(layout["aspect_ratio"])
    with plt.rc_context(_rc_params(theme)):
        fig, ax = plt.subplots(
            figsize=(width_mm / 25.4, height_in), constrained_layout=True
        )
        colors = theme["palette"]
        groups: dict[str, int] = {}
        task_boxes: dict[str, tuple[float, float, float]] = {}
        for index, task in enumerate(tasks):
            group = str(task.get("group", "default"))
            groups.setdefault(group, len(groups))
            start = dt.date.fromisoformat(task["start"])
            end = dt.date.fromisoformat(task["end"])
            duration = max(1, (end - start).days + 1)
            y = len(tasks) - index - 1
            color = colors[groups[group] % len(colors)]
            if task.get("id"):
                task_boxes[task["id"]] = (mdates.date2num(start), mdates.date2num(start) + duration, y)
            ax.barh(y, duration, left=mdates.date2num(start), color=color, height=0.62)
            completion = task.get("completion")
            if completion is not None:
                fraction = max(0.0, min(1.0, float(completion)))
                ax.barh(
                    y,
                    duration * fraction,
                    left=mdates.date2num(start),
                    color=theme["foreground"],
                    alpha=0.28,
                    height=0.62,
                )
        _gantt_dependencies(ax, tasks, task_boxes, theme)
        ax.set_yticks(range(len(tasks)))
        ax.set_yticklabels([task["label"] for task in reversed(tasks)])
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
        _decorate(ax, spec, theme)
        ax.grid(axis="y", visible=False)
        ax.grid(
            axis="x",
            color=theme["grid"],
            linewidth=0.65,
            linestyle=(0, (2.5, 2.5)),
        )
        _add_provenance(fig, spec, theme)
        media: dict[str, Any] = {}
        try:
            outputs = _save(fig, spec, output_dir, media)
        finally:
            plt.close(fig)
    return outputs, {"renderer": "matplotlib-gantt", "matplotlib": matplotlib.__version__, "media": media}


def _gantt_dependencies(ax: Any, tasks: list[dict[str, Any]], boxes: dict[str, tuple[float, float, float]], theme: dict[str, Any]) -> None:
    import matplotlib.dates as mdates
    from matplotlib.patches import FancyArrowPatch
    from matplotlib.path import Path as PlotPath

    if not boxes:
        return
    left = min(mdates.date2num(dt.date.fromisoformat(task["start"])) for task in tasks)
    right = max(mdates.date2num(dt.date.fromisoformat(task["end"])) + 1 for task in tasks)
    gap = max(0.3, (right - left) * 0.025)
    lane = 0
    for index, task in enumerate(tasks):
        dependencies = task.get("depends_on", [])
        dependencies = [dependencies] if isinstance(dependencies, str) else dependencies
        target_start = mdates.date2num(dt.date.fromisoformat(task["start"]))
        target_y = len(tasks) - index - 1
        for dependency in dependencies:
            if dependency not in boxes:
                raise ValueError(f"Unknown Gantt dependency: {dependency}")
            _, source_end, source_y = boxes[dependency]
            lane += 1
            bus = right + gap * (1 + lane * 0.45)
            corridor_y = target_y + 0.46
            approach = target_start - gap
            vertices = [
                (source_end, source_y), (bus, source_y), (bus, corridor_y),
                (approach, corridor_y), (approach, target_y), (target_start, target_y),
            ]
            arrow = FancyArrowPatch(
                path=PlotPath(vertices, [PlotPath.MOVETO] + [PlotPath.LINETO] * 5),
                arrowstyle="-|>", mutation_scale=8, linewidth=0.85,
                color=theme.get("edge", theme["muted"]), zorder=4,
            )
            arrow.set_gid(f"dependency-{dependency}-{task.get('id', index)}")
            ax.add_patch(arrow)
    if lane:
        ax.set_xlim(left - gap * 2, right + gap * (2 + lane * 0.45))
        ax.set_ylim(-0.6, len(tasks) - 0.35)


def _rc_params(theme: dict[str, Any]) -> dict[str, Any]:
    return {
        "figure.facecolor": theme["background"],
        "axes.facecolor": theme["background"],
        "savefig.facecolor": theme["background"],
        "text.color": theme["foreground"],
        "axes.labelcolor": theme["foreground"],
        "axes.edgecolor": theme["muted"],
        "axes.linewidth": 0.8,
        "axes.axisbelow": True,
        "xtick.color": theme["foreground"],
        "ytick.color": theme["foreground"],
        "xtick.direction": "out",
        "ytick.direction": "out",
        "xtick.major.size": 3.5,
        "ytick.major.size": 3.5,
        "xtick.major.width": 0.7,
        "ytick.major.width": 0.7,
        "font.family": theme["font_family"],
        "font.size": theme["font_size"],
        "axes.titlesize": theme["font_size"] + 2,
        "axes.labelsize": theme["font_size"],
        "legend.fontsize": max(7, theme["font_size"] - 1),
        "lines.linewidth": theme["line_width"],
        "lines.markersize": 5,
        "legend.frameon": False,
        "legend.handlelength": 1.8,
        "legend.handletextpad": 0.6,
        "legend.columnspacing": 1.2,
        "savefig.pad_inches": 0.08,
        "savefig.bbox": None,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
    }


def _series(spec: dict[str, Any], columns: dict[str, list[Any]]) -> list[dict[str, Any]]:
    series = spec.get("series")
    if series:
        return series
    keys = list(columns)
    if len(keys) < 2:
        raise ValueError("Chart requires series or at least two data columns")
    return [{"x": keys[0], "y": key, "label": key} for key in keys[1:]]


def _values(columns: dict[str, list[Any]], field: str) -> list[Any]:
    if field not in columns:
        raise ValueError(f"Data field not found: {field}")
    values = columns[field]
    if any(value is None for value in values):
        raise ValueError(f"Data field contains missing values: {field}")
    return values


def _line(ax: Any, spec: dict[str, Any], columns: dict[str, list[Any]], theme: dict[str, Any], scatter: bool) -> None:
    markers = ("o", "s", "^", "D", "v", "P", "X", "*")
    styles = ("-", "--", "-.", ":")
    for index, item in enumerate(_series(spec, columns)):
        x = _values(columns, item["x"])
        y = _values(columns, item["y"])
        kwargs = {
            "label": item.get("label", item["y"]),
            "color": item.get("color", theme["palette"][index % len(theme["palette"])]),
            "marker": item.get("marker", markers[index % len(markers)]),
            "alpha": float(item.get("alpha", 1.0)),
        }
        if scatter:
            ax.scatter(
                x,
                y,
                s=item.get("size", 34),
                edgecolors=theme["background"],
                linewidths=0.8,
                zorder=3,
                **kwargs,
            )
        else:
            ax.plot(
                x,
                y,
                linestyle=item.get("linestyle", styles[index % len(styles)]),
                linewidth=float(item.get("linewidth", theme["line_width"])),
                markersize=float(item.get("markersize", 5)),
                markeredgecolor=theme["background"],
                markeredgewidth=0.75,
                zorder=3,
                **kwargs,
            )
            lower = item.get("lower")
            upper = item.get("upper")
            if lower is not None and upper is not None:
                ax.fill_between(
                    x,
                    _values(columns, lower),
                    _values(columns, upper),
                    color=kwargs["color"],
                    alpha=float(
                        item.get(
                            "interval_alpha",
                            theme.get("interval_alpha", 0.16),
                        )
                    ),
                    linewidth=0,
                    zorder=2,
                    label="_nolegend_",
                )
            if spec.get("style", {}).get("direct_labels") and x and y:
                label = item.get("label", item["y"])
                if spec.get("style", {}).get("direct_label_values"):
                    number_format = spec.get("style", {}).get(
                        "direct_label_format", ".1f"
                    )
                    unit = spec.get("semantics", {}).get("y_unit", "")
                    label = f"{label}  {format(float(y[-1]), number_format)}{unit}"
                annotation = ax.annotate(
                    label,
                    (x[-1], y[-1]),
                    xytext=(1.02, 0.5),
                    textcoords="axes fraction",
                    color=kwargs["color"],
                    va="center",
                    fontsize=max(7, theme["font_size"] - 1),
                    fontweight="semibold",
                    annotation_clip=False,
                    arrowprops={"arrowstyle": "-", "color": kwargs["color"], "linewidth": 0.7},
                    bbox={
                        "boxstyle": "round,pad=0.18",
                        "facecolor": theme["background"],
                        "edgecolor": "none",
                        "alpha": 0.88,
                    },
                )
                annotation._figure_direct_label = True


def _errorbar(ax: Any, spec: dict[str, Any], columns: dict[str, list[Any]], theme: dict[str, Any]) -> None:
    markers = ("o", "s", "^", "D")
    for index, item in enumerate(_series(spec, columns)):
        ax.errorbar(
            _values(columns, item["x"]),
            _values(columns, item["y"]),
            yerr=_values(columns, item["error"]),
            label=item.get("label", item["y"]),
            color=item.get("color", theme["palette"][index % len(theme["palette"])]),
            marker=item.get("marker", markers[index % len(markers)]),
            capsize=3,
            markeredgecolor=theme["background"],
            markeredgewidth=0.75,
            elinewidth=1.0,
            zorder=3,
        )


def _bar(ax: Any, spec: dict[str, Any], columns: dict[str, list[Any]], theme: dict[str, Any]) -> None:
    import numpy as np

    series = _series(spec, columns)
    categories = _values(columns, series[0]["x"])
    positions = np.arange(len(categories))
    stacked = bool(spec.get("layout", {}).get("stacked"))
    group_width = float(spec.get("style", {}).get("bar_group_width", 0.72))
    width = group_width if stacked else group_width / len(series)
    positive = np.zeros(len(categories))
    negative = np.zeros(len(categories))
    plotted_values: list[Any] = []
    for index, item in enumerate(series):
        values = np.asarray(_values(columns, item["y"]), dtype=float)
        plotted_values.append(values)
        offset = 0 if stacked else (index - (len(series) - 1) / 2) * width
        bars = ax.bar(
            positions + offset,
            values,
            width=width,
            bottom=np.where(values >= 0, positive, negative) if stacked else None,
            label=item.get("label", item["y"]),
            color=item.get("color", theme["palette"][index % len(theme["palette"])]),
            edgecolor=theme["background"],
            linewidth=0.8,
        )
        if spec.get("style", {}).get("annotate_values"):
            ax.bar_label(
                bars,
                fmt=spec.get("style", {}).get("value_format", "%.1f"),
                label_type="center" if stacked else "edge",
                padding=3,
                fontsize=max(7, theme["font_size"] - 2),
                color=theme["foreground"],
            )
        if stacked:
            positive += np.maximum(values, 0)
            negative += np.minimum(values, 0)
    if (
        spec.get("style", {}).get("annotate_delta")
        and not stacked
        and len(plotted_values) == 2
    ):
        first, second = plotted_values
        highest = float(max(np.max(first), np.max(second)))
        low, high = ax.get_ylim()
        span = max(high - low, 1e-9)
        ax.set_ylim(top=max(high, highest + span * 0.18))
        semantics = spec.get("semantics", {})
        unit = spec.get("style", {}).get("delta_unit", semantics.get("delta_unit"))
        if unit is None:
            unit = semantics.get("y_unit", "")
            if unit == "%":
                unit = "pp"
        for position, initial, final in zip(
            positions,
            first,
            second,
            strict=True,
        ):
            delta = float(final - initial)
            sign = "+" if delta >= 0 else ""
            ax.text(
                position,
                max(float(initial), float(final)) + span * 0.075,
                f"{sign}{delta:.1f}{' ' + unit if unit else ''}",
                ha="center",
                va="bottom",
                fontsize=max(7, theme["font_size"] - 2),
                fontweight="semibold",
                color=theme["muted"],
                bbox={
                    "boxstyle": "round,pad=0.25",
                    "facecolor": theme["background"],
                    "edgecolor": theme["grid"],
                    "linewidth": 0.6,
                },
            )
    ax.set_xticks(positions)
    ax.set_xticklabels(categories)


def _histogram(ax: Any, spec: dict[str, Any], columns: dict[str, list[Any]], theme: dict[str, Any]) -> None:
    items = spec.get("series") or [{"field": next(iter(columns)), "label": next(iter(columns))}]
    bins = spec.get("layout", {}).get("bins", "auto")
    for index, item in enumerate(items):
        field = item.get("field", item.get("y"))
        ax.hist(
            _values(columns, field),
            bins=bins,
            alpha=0.72,
            label=item.get("label", field),
            color=item.get("color", theme["palette"][index % len(theme["palette"])]),
            edgecolor=theme["background"],
            linewidth=0.8,
        )


def _box(ax: Any, spec: dict[str, Any], columns: dict[str, list[Any]], theme: dict[str, Any]) -> None:
    items = spec.get("series") or [
        {"field": key, "label": key} for key in columns
    ]
    values = [_values(columns, item.get("field", item.get("y"))) for item in items]
    labels = [item.get("label", item.get("field", item.get("y"))) for item in items]
    label_parameter = (
        "tick_labels"
        if "tick_labels" in inspect.signature(ax.boxplot).parameters
        else "labels"
    )
    result = ax.boxplot(
        values,
        patch_artist=True,
        medianprops={"color": theme["foreground"], "linewidth": 1.4},
        whiskerprops={"color": theme["muted"], "linewidth": 1.0},
        capprops={"color": theme["muted"], "linewidth": 1.0},
        flierprops={
            "marker": "o",
            "markerfacecolor": theme["background"],
            "markeredgecolor": theme["muted"],
            "markersize": 3.5,
        },
        **{label_parameter: labels},
    )
    for index, patch in enumerate(result["boxes"]):
        patch.set_facecolor(theme["palette"][index % len(theme["palette"])])
        patch.set_alpha(0.82)
        patch.set_edgecolor(theme["background"])


def _heatmap(fig: Any, ax: Any, spec: dict[str, Any], columns: dict[str, list[Any]], theme: dict[str, Any], np: Any) -> None:
    data = spec.get("data", {})
    matrix = data.get("matrix")
    if matrix is None:
        matrix = [columns[key] for key in columns]
    array = np.asarray(matrix, dtype=float)
    image = ax.imshow(
        array,
        aspect=spec.get("layout", {}).get("cell_aspect", "equal"),
        cmap=spec.get("style", {}).get("colormap", "viridis"),
    )
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    row_labels = data.get("row_labels")
    col_labels = data.get("column_labels")
    if row_labels:
        ax.set_yticks(range(len(row_labels)), labels=row_labels)
    if col_labels:
        ax.set_xticks(range(len(col_labels)), labels=col_labels)
    ax.set_xticks([value - 0.5 for value in range(1, array.shape[1])], minor=True)
    ax.set_yticks([value - 0.5 for value in range(1, array.shape[0])], minor=True)
    ax.grid(which="minor", color=theme["background"], linestyle="-", linewidth=1.2)
    ax.tick_params(which="minor", bottom=False, left=False)
    if spec.get("style", {}).get("annotate"):
        for row in range(array.shape[0]):
            for column in range(array.shape[1]):
                rgb = image.cmap(image.norm(array[row, column]))[:3]
                linear = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in rgb]
                luminance = sum(channel * weight for channel, weight in zip(linear, (0.2126, 0.7152, 0.0722)))
                color = "black" if (luminance + 0.05) / 0.05 >= 1.05 / (luminance + 0.05) else "white"
                ax.text(column, row, f"{array[row, column]:g}", ha="center", va="center", color=color)


def _decorate(
    ax: Any,
    spec: dict[str, Any],
    theme: dict[str, Any],
    show_grid: bool = True,
) -> None:
    semantics = spec.get("semantics", {})
    legend_location = spec.get("style", {}).get("legend_location", "best")
    title_alignment = spec.get("style", {}).get("title_alignment", "left")
    if title_alignment not in {"left", "center", "right"}:
        raise ValueError("style.title_alignment must be left, center, or right")
    if spec.get("title"):
        ax.set_title(
            spec["title"],
            loc=title_alignment,
            fontweight="semibold",
            pad=0 if legend_location == "top" else 12,
            y=1.13 if legend_location == "top" else None,
        )
    x_label = semantics.get("x_label", "")
    y_label = semantics.get("y_label", "")
    if semantics.get("x_unit"):
        x_label = f"{x_label} ({semantics['x_unit']})".strip()
    if semantics.get("y_unit"):
        y_label = f"{y_label} ({semantics['y_unit']})".strip()
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_linewidth(0.8)
    if show_grid:
        ax.grid(
            axis="y",
            color=theme["grid"],
            linewidth=0.65,
            linestyle=(0, (2.5, 2.5)),
            alpha=0.95,
        )
    else:
        ax.grid(False)
    handles, labels = ax.get_legend_handles_labels()
    if labels and not spec.get("style", {}).get("direct_labels"):
        if legend_location == "top":
            ax.legend(
                loc="lower left",
                bbox_to_anchor=(0, 1.02),
                ncols=min(4, len(labels)),
                borderaxespad=0,
                frameon=False,
            )
        else:
            ax.legend(
                loc=legend_location,
                frameon=True,
                facecolor=theme["background"],
                edgecolor="none",
                framealpha=0.88,
            )


def _formats(spec: dict[str, Any]) -> list[str]:
    output = spec.get("output", {})
    formats = [str(output.get("primary", "svg")).lower()]
    formats.extend(str(item).lower() for item in output.get("additional", []))
    unique: list[str] = []
    for item in formats:
        if item not in {"svg", "png", "pdf"}:
            raise ValueError(f"Unsupported chart output format: {item}")
        if item not in unique:
            unique.append(item)
    return unique


def _add_provenance(fig: Any, spec: dict[str, Any], theme: dict[str, Any]) -> None:
    if "provenance" not in spec:
        return
    from matplotlib.font_manager import FontProperties

    information = provenance_description(spec)
    description = "\n".join(value for value in (information["label"], information["summary"]) if value)
    size = max(7.0, float(theme["font_size"]) - 1)
    font = FontProperties(family=theme["font_family"], size=size)
    renderer = fig.canvas.get_renderer()
    margin = fig.dpi * 9 / 72
    available = fig.bbox.width - 2 * margin
    lines = []
    for paragraph in description.splitlines():
        line = ""
        for character in paragraph:
            candidate = line + character
            width = renderer.get_text_width_height_descent(candidate, font, ismath=False)[0]
            if line and width > available:
                boundary = line.rfind(" ")
                if boundary > 0:
                    lines.append(line[:boundary])
                    line = line[boundary + 1:] + character
                else:
                    lines.append(line)
                    line = character
            else:
                line = candidate
        lines.append(line.rstrip())
    # supxlabel participates in constrained layout, reserving the footer in all formats.
    footer = fig.supxlabel(
        "\n".join(lines), x=margin / fig.bbox.width, ha="left", multialignment="left",
        fontsize=size, fontfamily=theme["font_family"], color=theme["muted"],
        linespacing=1.25, parse_math=False,
    )
    footer.set_gid("figure-provenance")


def _save(fig: Any, spec: dict[str, Any], output_dir: Path, media: dict[str, Any] | None = None) -> list[Path]:
    outputs: list[Path] = []
    dpi = raster_dpi(spec)
    for _ in range(2):
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        for footer in (text for text in fig.texts if text.get_gid() == "figure-provenance"):
            footer_bounds = footer.get_window_extent(renderer)
            if any(ax.get_tightbbox(renderer).y0 < footer_bounds.y1 for ax in fig.axes):
                raise ValueError("Provenance and chart content do not fit requested physical dimensions; use render-set / split into detail figures or increase chart height")
        for ax in fig.axes:
            _place_direct_labels(ax)
    fig.canvas.draw()
    # Freeze the measured layout so PNG, PDF, and SVG preserve the same physical page.
    fig.set_layout_engine("none")
    tight = fig.get_tightbbox(fig.canvas.get_renderer())
    width, height = fig.get_size_inches()
    tolerance = 1 / 72
    if tight is not None and (tight.x0 < -tolerance or tight.y0 < -tolerance or tight.x1 > width + tolerance or tight.y1 > height + tolerance):
        raise ValueError("Figure content does not fit requested physical dimensions; use render-set / split into detail figures, increase layout.width_mm, or reduce aspect_ratio/text")
    preview = io.StringIO()
    fig.savefig(preview, format="svg", bbox_inches=None)
    _, measured_media = apply_svg_media(preview.getvalue(), spec)
    if measured_media["height_capped"]:
        raise ValueError("Chart exceeds the default 240mm paper height; use render-set / split into detail figures or explicitly set layout.height_mm")
    if media is not None:
        media.update(measured_media)
    for extension in _formats(spec):
        path = output_dir / f"figure.{extension}"
        fig.savefig(path, dpi=dpi, bbox_inches=None)
        if extension == "svg":
            _add_svg_accessibility(path, spec)
            svg, _ = apply_svg_media(path.read_text(encoding="utf-8"), spec)
            if spec.get("layout", {}).get("medium"):
                path.write_text(svg, encoding="utf-8")
        outputs.append(path)
    return outputs


def _place_direct_labels(ax: Any) -> None:
    labels = [text for text in ax.texts if getattr(text, "_figure_direct_label", False)]
    if not labels:
        return
    renderer = ax.figure.canvas.get_renderer()
    bounds = ax.get_window_extent(renderer)
    gap = ax.figure.dpi * 3 / 72
    entries = []
    for order, label in enumerate(labels):
        label.update_bbox_position_size(renderer)
        height = label.get_bbox_patch().get_window_extent(renderer).height
        x, y = label.xy
        endpoint = ax.transData.transform((ax.convert_xunits(x), ax.convert_yunits(y)))
        entries.append((endpoint[1], order, height, label))
    entries.sort(key=lambda item: (item[0], item[1]))
    if sum(item[2] for item in entries) + gap * (len(entries) - 1) > bounds.height:
        raise ValueError("Direct labels do not fit; increase chart height or use a legend")
    positions = []
    for desired, _, height, _ in entries:
        minimum = bounds.y0 + height / 2 if not positions else positions[-1] + entries[len(positions) - 1][2] / 2 + gap + height / 2
        positions.append(max(desired, minimum))
    positions[-1] = min(positions[-1], bounds.y1 - entries[-1][2] / 2)
    for index in range(len(entries) - 2, -1, -1):
        positions[index] = min(positions[index], positions[index + 1] - (entries[index][2] + entries[index + 1][2]) / 2 - gap)
    for position, (desired, _, _, label) in zip(positions, entries):
        label.set_position((1.02, (position - bounds.y0) / bounds.height))
        label.arrow_patch.set_visible(abs(position - desired) > gap)


def _add_svg_accessibility(path: Path, spec: dict[str, Any]) -> None:
    text = path.read_text(encoding="utf-8")
    svg_start = text.find("<svg")
    opening_end = text.find(">", svg_start)
    if svg_start < 0 or opening_end < 0:
        raise ValueError("Matplotlib produced an invalid SVG root")
    title = html.escape(spec.get("title", spec["kind"]))
    description = html.escape(
        spec.get("caption", f"{spec['kind']} rendered from a validated FigureSpec")
    )
    opening = text[svg_start:opening_end]
    if 'role="img"' not in opening:
        opening += ' role="img" aria-labelledby="figure-title figure-desc"'
    accessible = (
        f'{opening}><title id="figure-title">{title}</title>'
        f'<desc id="figure-desc">{description}</desc>'
    )
    path.write_text(
        text[:svg_start] + accessible + text[opening_end + 1 :],
        encoding="utf-8",
    )
