"""Reusable Plotly chart builders.

Every figure goes through :mod:`src.theme` so the whole dashboard shares
the same palette, typography and margins.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.theme import (
    ACCENT,
    GRID_X,
    MUTED,
    PANEL,
    RISK,
    RISK_MATRIX_SCALE,
    TRANSPARENT,
    severity_color,
    style_bars,
    style_figure,
)


def bar_h(
    data: pd.DataFrame,
    *,
    category: str,
    value: str,
    color: str | None = ACCENT,
    height: int = 300,
    sort_by_value: bool = True,
    text: str | None = None,
) -> go.Figure:
    """Horizontal bar chart (long labels read best)."""
    frame = data.sort_values(value) if sort_by_value else data
    fig = px.bar(
        frame,
        x=value,
        y=category,
        orientation="h",
        text=text or value,
        labels={value: "", category: ""},
    )
    style_bars(fig, color=color)
    return style_figure(fig, height=height)


def stacked_bar_h(
    data: pd.DataFrame,
    *,
    category: str,
    value: str,
    color_col: str,
    palette: callable = severity_color,
    height: int = 320,
) -> go.Figure:
    """Horizontal stacked bars with a per-slice color function."""
    fig = px.bar(
        data,
        x=value,
        y=category,
        color=color_col,
        orientation="h",
        labels={value: "Accidentes", category: ""},
        color_discrete_map=(
            {label: palette(label) for label in data[color_col].astype(str).unique()}
            if palette is not None
            else None
        ),
    )
    fig.update_layout(barmode="stack", legend_title_text="")
    return style_figure(fig, height=height, showlegend=True)


def line_trend(
    data: pd.DataFrame,
    *,
    x: str,
    y: str,
    color: str = ACCENT,
    fill: bool = True,
    height: int = 300,
    markers: bool = True,
) -> go.Figure:
    """Line chart with optional area fill and markers."""
    fig = go.Figure()
    fill_style = "tozeroy" if fill else None
    fig.add_trace(
        go.Scatter(
            x=data[x],
            y=data[y],
            mode="lines+markers" if markers else "lines",
            line={"color": color, "width": 3},
            marker={"color": color, "size": 7},
            fill=fill_style,
            fillcolor=_hex_to_rgba(color, 0.08),
        )
    )
    return style_figure(fig, height=height)


def _hex_to_rgba(color: str, alpha: float) -> str:
    """Turn ``#rrggbb`` into an ``rgba(...)`` string with the given alpha."""
    if color.startswith("#") and len(color) == 7:
        return (
            f"rgba({int(color[1:3], 16)},{int(color[3:5], 16)},"
            f"{int(color[5:7], 16)},{alpha})"
        )
    return color


def line_multi(
    data: pd.DataFrame,
    *,
    x: str,
    series_col: str,
    y: str,
    height: int = 300,
) -> go.Figure:
    """Multi-series line chart from long data with markers."""
    fig = go.Figure()
    for label, subset in data.groupby(series_col, sort=False, dropna=False):
        color = severity_color(label)
        fig.add_trace(
            go.Scatter(
                x=subset[x],
                y=subset[y],
                name=str(label),
                mode="lines+markers",
                line={"color": color, "width": 2.4},
                marker={"color": color, "size": 6},
            )
        )
    fig.update_layout(legend={"orientation": "h", "y": -0.18, "x": 0})
    return style_figure(fig, height=height, showlegend=True)


def combo_bar_line(
    data: pd.DataFrame,
    *,
    x: str,
    bar_col: str,
    line_col: str,
    bar_color: str = ACCENT,
    line_color: str = "#7dd3fc",
    height: int = 300,
) -> go.Figure:
    """Bars plus an overlay line (e.g. monthly counts + rolling average)."""
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=data[x],
            y=data[bar_col],
            name=bar_col,
            marker={"color": bar_color, "opacity": 0.85},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=data[x],
            y=data[line_col],
            name=line_col,
            mode="lines",
            line={"color": line_color, "width": 2.6},
        )
    )
    fig.update_layout(legend={"orientation": "h", "y": 1.08, "x": 0})
    return style_figure(fig, height=height, showlegend=True)


def heat_yearly_monthly(
    matrix: pd.DataFrame,
    *,
    height: int = 320,
) -> go.Figure:
    """Year x month fatality heatmap (rows: years, cols: months 1-12)."""
    years = matrix.index.astype(str).tolist()
    fig = go.Figure(
        go.Heatmap(
            z=matrix.values,
            x=[str(m) for m in range(1, 13)],
            y=years,
            colorscale=RISK_MATRIX_SCALE,
            zmin=0,
            zmax=float(matrix.values.max()) if matrix.size else 1,
            text=matrix.values.astype(int).astype(str),
            texttemplate="%{text}",
            textfont={"size": 11, "color": "#e2e8f0"},
            hovertemplate="%{y} · mes %{x}: %{z} fallecidos<extra></extra>",
            colorbar={"title": "", "tickfont": {"color": MUTED, "size": 10}},
        )
    )
    fig.update_layout(
        height=height,
        margin={"l": 6, "r": 10, "t": 14, "b": 6},
        paper_bgcolor=TRANSPARENT,
        plot_bgcolor=TRANSPARENT,
        font={"family": "Outfit, sans-serif", "color": "#d8dee9", "size": 12},
        yaxis={"autorange": "reversed", "gridcolor": GRID_X},
        xaxis={"gridcolor": GRID_X},
    )
    return fig


def risk_matrix(
    frame: pd.DataFrame,
    *,
    index: str,
    columns: str,
    values: str,
    height: int = 380,
) -> go.Figure:
    """Comuna x franja heatmap of expected daily frequency."""
    pivot = (
        frame.pivot_table(index=index, columns=columns, values=values, aggfunc="first")
        .reindex(sorted(set(frame[index].astype(str))), axis=0)
        .fillna(0)
    )
    fig = go.Figure(
        go.Heatmap(
            z=pivot.values,
            x=pivot.columns.astype(str).tolist(),
            y=pivot.index.astype(str).tolist(),
            colorscale=RISK_MATRIX_SCALE,
            zmin=0,
            zmax=float(pivot.values.max()) if pivot.size else 1,
            text=pivot.values.round(2).astype(str),
            texttemplate="%{text}",
            textfont={"size": 10},
            hovertemplate="%{y} · %{x}: %{text} siniestros/día<extra></extra>",
            colorbar={"thickness": 12, "thicknessmode": "pixels", "tickfont": {"color": MUTED, "size": 10}},
        )
    )
    fig.update_layout(
        height=height,
        margin={"l": 6, "r": 10, "t": 10, "b": 6},
        paper_bgcolor=TRANSPARENT,
        plot_bgcolor=TRANSPARENT,
        font={"family": "Outfit, sans-serif", "color": "#d8dee9", "size": 12},
        yaxis={"autorange": "reversed"},
    )
    return fig


def donut(
    data: pd.DataFrame,
    *,
    names: str,
    values: str,
    colors: dict[str, str] | None = None,
    height: int = 280,
) -> go.Figure:
    """Donut chart with a semantic color mapping."""
    fig = go.Figure(
        go.Pie(
            labels=data[names],
            values=data[values],
            hole=0.5,
            marker={"colors": [colors.get(str(label)) if colors else None for label in data[names]]},
            textinfo="percent",
            textfont={"size": 11},
            hovertemplate="%{label}: %{value:,} (%{percent})<extra></extra>",
        )
    )
    return style_figure(fig, height=height, showlegend=True)