"""Tiny inline-SVG charts so pages need no JavaScript and archived pages keep working."""
from __future__ import annotations

import html


def _scale(values: list[float], x0: float, y0: float, w: float, h: float) -> list[tuple[float, float]]:
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    step = w / (len(values) - 1)
    return [(x0 + i * step, y0 + h * (1 - (v - lo) / span)) for i, v in enumerate(values)]


def _trend(values: list[float]) -> str:
    return "up" if values[-1] >= values[0] else "down"


def _pts(coords: list[tuple[float, float]]) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)


def sparkline_svg(values: list[float], width: int = 96, height: int = 28) -> str:
    if len(values) < 2:
        return ""
    coords = _scale(values, 2, 2, width - 4, height - 4)
    return (f'<svg class="spark {_trend(values)}" viewBox="0 0 {width} {height}" width="{width}" '
            f'height="{height}" aria-hidden="true"><polyline fill="none" stroke-width="1.5" '
            f'points="{_pts(coords)}"/></svg>')


def line_chart_svg(history: list[list], label: str, width: int = 640, height: int = 220) -> str:
    values = [float(v) for _, v in history]
    if len(values) < 2:
        return ""
    left, right, top, bottom = 56, 12, 12, 28
    inner_w, inner_h = width - left - right, height - top - bottom
    coords = _scale(values, left, top, inner_w, inner_h)
    base = top + inner_h
    area = f"{left:.1f},{base:.1f} {_pts(coords)} {coords[-1][0]:.1f},{base:.1f}"
    safe = html.escape(label)
    return (
        f'<svg class="chart {_trend(values)}" viewBox="0 0 {width} {height}" role="img" aria-label="{safe}">'
        f"<title>{safe}</title>"
        f'<line class="grid" x1="{left}" y1="{top}" x2="{width - right}" y2="{top}"/>'
        f'<line class="grid" x1="{left}" y1="{base}" x2="{width - right}" y2="{base}"/>'
        f'<text class="axis" x="{left - 6}" y="{top + 4}" text-anchor="end">{max(values):,.0f}</text>'
        f'<text class="axis" x="{left - 6}" y="{base + 4}" text-anchor="end">{min(values):,.0f}</text>'
        f'<text class="axis" x="{left}" y="{height - 8}">{html.escape(str(history[0][0]))}</text>'
        f'<text class="axis" x="{width - right}" y="{height - 8}" text-anchor="end">'
        f"{html.escape(str(history[-1][0]))}</text>"
        f'<polygon class="area" points="{area}"/>'
        f'<polyline class="line" fill="none" stroke-width="2" points="{_pts(coords)}"/>'
        "</svg>"
    )
