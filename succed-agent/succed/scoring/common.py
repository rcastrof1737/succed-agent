from __future__ import annotations

from typing import Optional, Sequence


def piecewise(value: Optional[float], points: Sequence[Sequence[float]]) -> Optional[float]:
    """Linear interpolation over sorted [x, y] points; flat beyond the ends. None -> None."""
    if value is None:
        return None
    pts = sorted((float(x), float(y)) for x, y in points)
    if value <= pts[0][0]:
        return pts[0][1]
    if value >= pts[-1][0]:
        return pts[-1][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= value <= x1:
            return y0 + (y1 - y0) * (value - x0) / (x1 - x0)
    return pts[-1][1]  # pragma: no cover


def band_for(score: float, bands: list[dict]) -> tuple[str, str]:
    for b in sorted(bands, key=lambda b: -b["min"]):
        if score >= b["min"]:
            return b["label"], b["action"]
    return "", ""


OPS = {
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "==": lambda a, b: a == b,
}
