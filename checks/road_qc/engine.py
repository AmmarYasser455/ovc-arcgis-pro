# -*- coding: utf-8 -*-
"""
OVC ArcGIS Pro – Road QC Engine

Pure-Python algorithms for road network quality control.
No arcpy dependency — works with plain coordinate tuples for
maximum performance and testability.

Algorithms
----------
- **Dangle detection** – spatial-hash O(n) endpoint matching
- **Disconnected segment detection** – derived from dangle results
- **Self-intersection detection** – per-segment sweep with
  line-segment intersection math
"""

import math
from collections import defaultdict
from collections.abc import Mapping
from numbers import Real
from typing import Dict, List, Tuple, Optional


# ---------------------------------------------------------------------------
# Spatial hashing helpers
# ---------------------------------------------------------------------------

def _grid_key(x: float, y: float, cell: float) -> Tuple[int, int]:
    """Return the grid cell that contains (x, y)."""
    return (int(x // cell), int(y // cell))


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def _check_mapping(value, name: str) -> None:
    """Raise TypeError unless *value* is a ``{road_fid: …}`` mapping."""
    if not isinstance(value, Mapping):
        raise TypeError(
            f"{name} must be a mapping of road_fid -> coordinates, "
            f"got {type(value).__name__}"
        )


def _check_point(pt, fid) -> None:
    """Raise unless *pt* is an ``(x, y)`` pair of finite real numbers."""
    if isinstance(pt, (str, bytes)) or not hasattr(pt, "__len__") or len(pt) != 2:
        raise TypeError(f"road {fid!r}: point must be an (x, y) pair, got {pt!r}")
    for c in pt:
        if isinstance(c, bool) or not isinstance(c, Real):
            raise TypeError(
                f"road {fid!r}: coordinates must be real numbers, got {pt!r}"
            )
        if not math.isfinite(c):
            raise ValueError(
                f"road {fid!r}: coordinates must be finite, got {pt!r}"
            )


def _check_tolerance(tolerance) -> float:
    """Return *tolerance* as a float; reject non-numbers, NaN, inf and < 0."""
    if isinstance(tolerance, bool) or not isinstance(tolerance, Real):
        raise TypeError(
            f"tolerance must be a real number, got {type(tolerance).__name__}"
        )
    tolerance = float(tolerance)
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError(
            f"tolerance must be a finite number >= 0, got {tolerance!r}"
        )
    return tolerance


# ---------------------------------------------------------------------------
# Dangle detection  (O(n) amortised via spatial hash)
# ---------------------------------------------------------------------------

def find_dangles(
    endpoints_by_road: Dict[int, List[Tuple[float, float]]],
    tolerance: float = 0.5,
) -> List[Tuple[int, float, float, int]]:
    """
    Find dangling endpoints — endpoints that do not connect to any
    other road within *tolerance*.

    Parameters
    ----------
    endpoints_by_road : dict
        ``{road_fid: [(x, y), …]}`` — projected coordinates.
    tolerance : float
        Snap tolerance in **map units** (metres for a projected CRS).

    Returns
    -------
    list of (road_fid, x, y, endpoint_index)

    Raises
    ------
    TypeError
        If *endpoints_by_road* is not a mapping, a point is not an
        ``(x, y)`` pair of real numbers, or *tolerance* is not a real
        number (``None``, strings and booleans are rejected).
    ValueError
        If *tolerance* is negative, NaN or infinite, or a coordinate is
        NaN or infinite.
    """
    _check_mapping(endpoints_by_road, "endpoints_by_road")
    tolerance = _check_tolerance(tolerance)
    cell = max(tolerance, 1e-9)
    # Endpoints of the *same* road only connect when they coincide exactly
    # (a closed loop); near-misses within tolerance remain dangles.
    tol_sq = tolerance * tolerance

    # 1. Flatten + build spatial hash
    grid: Dict[Tuple[int, int], List[Tuple[int, float, float, int]]] = defaultdict(list)
    all_eps: List[Tuple[int, float, float, int]] = []

    for fid, pts in endpoints_by_road.items():
        for i, pt in enumerate(pts):
            _check_point(pt, fid)
            x, y = pt
            all_eps.append((fid, x, y, i))
            grid[_grid_key(x, y, cell)].append((fid, x, y, i))

    # 2. Check each endpoint against 3×3 neighbourhood
    dangles: List[Tuple[int, float, float, int]] = []
    for fid, x, y, ep_idx in all_eps:
        gx, gy = _grid_key(x, y, cell)
        connected = False
        for dx in (-1, 0, 1):
            if connected:
                break
            for dy in (-1, 0, 1):
                bucket = grid.get((gx + dx, gy + dy))
                if bucket is None:
                    continue
                for ofid, ox, oy, oidx in bucket:
                    if ofid == fid:
                        if oidx == ep_idx or (x, y) != (ox, oy):
                            continue
                        connected = True
                        break
                    if (x - ox) ** 2 + (y - oy) ** 2 <= tol_sq:
                        connected = True
                        break
                if connected:
                    break
        if not connected:
            dangles.append((fid, x, y, ep_idx))

    return dangles


# ---------------------------------------------------------------------------
# Disconnected-segment detection
# ---------------------------------------------------------------------------

def find_disconnected(
    endpoints_by_road: Dict[int, List[Tuple[float, float]]],
    tolerance: float = 0.5,
) -> Tuple[List[int], List[Tuple[int, float, float, int]]]:
    """
    Find completely disconnected road segments — segments whose
    **every** endpoint is a dangle.  Roads with no endpoints (null or
    empty geometry) are ignored rather than reported.

    Returns
    -------
    (disconnected_fids, dangles)
        *dangles* is the full dangle list (reused by callers to avoid
        running the hash twice).

    Raises
    ------
    TypeError, ValueError
        For invalid input, as in :func:`find_dangles`.
    """
    dangles = find_dangles(endpoints_by_road, tolerance)

    dangle_count: Dict[int, int] = defaultdict(int)
    for fid, _, _, _ in dangles:
        dangle_count[fid] += 1

    disconnected = [
        fid
        for fid, pts in endpoints_by_road.items()
        if pts and dangle_count.get(fid, 0) >= len(pts)
    ]
    return disconnected, dangles


# ---------------------------------------------------------------------------
# Self-intersection detection
# ---------------------------------------------------------------------------

def _cross2d(ox, oy, ax, ay, bx, by):
    """Signed area of parallelogram OA × OB."""
    return (ax - ox) * (by - oy) - (ay - oy) * (bx - ox)


def _on_segment(px, py, qx, qy, rx, ry):
    """True when (qx, qy) lies on segment (px, py)–(rx, ry)."""
    return (min(px, rx) <= qx <= max(px, rx) and
            min(py, ry) <= qy <= max(py, ry))


def _segments_cross(p1, q1, p2, q2) -> bool:
    """Test if segment p1–q1 properly intersects segment p2–q2."""
    d1 = _cross2d(p2[0], p2[1], q2[0], q2[1], p1[0], p1[1])
    d2 = _cross2d(p2[0], p2[1], q2[0], q2[1], q1[0], q1[1])
    d3 = _cross2d(p1[0], p1[1], q1[0], q1[1], p2[0], p2[1])
    d4 = _cross2d(p1[0], p1[1], q1[0], q1[1], q2[0], q2[1])

    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
       ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return True

    if d1 == 0 and _on_segment(p2[0], p2[1], p1[0], p1[1], q2[0], q2[1]):
        return True
    if d2 == 0 and _on_segment(p2[0], p2[1], q1[0], q1[1], q2[0], q2[1]):
        return True
    if d3 == 0 and _on_segment(p1[0], p1[1], p2[0], p2[1], q1[0], q1[1]):
        return True
    if d4 == 0 and _on_segment(p1[0], p1[1], q2[0], q2[1], q1[0], q1[1]):
        return True

    return False


def _folds_back(a, b, c) -> bool:
    """True when a->b->c is collinear and c lies back along b->a."""
    if _cross2d(a[0], a[1], b[0], b[1], c[0], c[1]) != 0:
        return False
    return (b[0] - a[0]) * (c[0] - b[0]) + (b[1] - a[1]) * (c[1] - b[1]) < 0


def _intersection_point(p1, q1, p2, q2) -> Optional[Tuple[float, float]]:
    """Return the intersection point of two crossing segments."""
    x1, y1 = p1
    x2, y2 = q1
    x3, y3 = p2
    x4, y4 = q2

    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-12:
        # Parallel segments: only reachable for collinear overlap or
        # touching.  Report the first endpoint lying on the other segment.
        for (px, py), (ax, ay), (bx, by) in (
            (p1, p2, q2), (q1, p2, q2), (p2, p1, q1), (q2, p1, q1),
        ):
            if (_cross2d(ax, ay, bx, by, px, py) == 0
                    and _on_segment(ax, ay, px, py, bx, by)):
                return (px, py)
        return None

    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))


def find_self_intersections(
    vertices_by_road: Dict[int, List[List[Tuple[float, float]]]],
) -> List[Tuple[int, float, float]]:
    """
    Find self-intersecting road segments.

    Parameters
    ----------
    vertices_by_road : dict
        ``{road_fid: [[part_vertices], …]}`` where each part is a
        list of ``(x, y)`` tuples.

    Returns
    -------
    list of (road_fid, ix, iy) — one entry per road (first crossing
    point only).

    Raises
    ------
    TypeError
        If *vertices_by_road* is not a mapping or a vertex is not an
        ``(x, y)`` pair of real numbers.
    ValueError
        If a coordinate is NaN or infinite.
    """
    _check_mapping(vertices_by_road, "vertices_by_road")
    results: List[Tuple[int, float, float]] = []

    for fid, parts in vertices_by_road.items():
        parts = [list(part) for part in parts]
        for part in parts:
            for pt in part:
                _check_point(pt, fid)
        found = False
        for part in parts:
            if found:
                break
            # Repeated consecutive vertices create zero-length segments
            # that would make neighbouring segments look non-adjacent.
            part = [v for k, v in enumerate(part) if k == 0 or v != part[k - 1]]
            n = len(part)
            if n < 3:
                continue
            for i in range(n - 1):
                if found:
                    break
                # A segment that doubles straight back over the previous
                # one (A -> B -> A') overlaps itself along a collinear run.
                if i + 2 < n and _folds_back(part[i], part[i + 1], part[i + 2]):
                    results.append((fid, part[i + 1][0], part[i + 1][1]))
                    found = True
                    break
                # Only compare non-adjacent segments
                for j in range(i + 2, n - 1):
                    # First and last segments of a closed ring share
                    # the closing vertex; that is not a self-crossing.
                    if i == 0 and j == n - 2 and part[0] == part[-1]:
                        continue
                    if _segments_cross(part[i], part[i + 1],
                                       part[j], part[j + 1]):
                        pt = _intersection_point(
                            part[i], part[i + 1],
                            part[j], part[j + 1],
                        )
                        if pt:
                            results.append((fid, pt[0], pt[1]))
                            found = True
                            break

    return results
