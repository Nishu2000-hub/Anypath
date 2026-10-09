"""Problem model shared by both solver backends.

A problem is an N x N cost matrix (``primary``, the objective) plus an
optional same-shape ``secondary`` matrix used only to break ties
(SPEC §5: Fastest breaks ties by distance, Shortest by time). Remaining ties
go to the lexicographically smallest visiting order.

All costs are rounded to integers on entry (seconds / meters). Weather
multipliers make the adjusted matrix fractional; rounding gives both backends
the same exact arithmetic, so ties are real ties and results are deterministic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

MIN_POINTS = 2
MAX_POINTS = 15

# Total combined cost must fit in OR-Tools' int64 arc/route costs.
_INT64_SAFE = 2**62

Matrix = Sequence[Sequence[float]]


@dataclass(frozen=True)
class Constraints:
    """Route shape (SPEC §2).

    * ``start`` — first node of the route.
    * ``end`` — optional fixed last node ("finish at home").
    * ``round_trip`` — return to ``start``; mutually exclusive with ``end``.
    * ``lock_first`` — optional stop that must be visited right after start.

    With neither ``end`` nor ``round_trip`` the route is an open path that
    ends at whichever stop is cheapest.
    """

    start: int = 0
    end: int | None = None
    round_trip: bool = False
    lock_first: int | None = None

    @property
    def terminal(self) -> int | None:
        """Node the route must finish at, or None for an open path."""
        return self.start if self.round_trip else self.end


@dataclass(frozen=True)
class Solution:
    """``order`` lists node indices from start to finish; a round trip ends
    with ``start`` again."""

    order: list[int]
    primary_cost: int
    secondary_cost: int
    method: str  # "held_karp" | "ortools"


@dataclass(frozen=True)
class Problem:
    n: int
    primary: list[list[int]]
    secondary: list[list[int]]
    constraints: Constraints
    # Arc weight = primary * scale + secondary. ``scale`` exceeds any route's
    # secondary total, so comparing weights compares (primary, secondary)
    # lexicographically.
    scale: int

    def weight(self, i: int, j: int) -> int:
        return self.primary[i][j] * self.scale + self.secondary[i][j]

    def costs(self, order: Sequence[int]) -> tuple[int, int]:
        legs = list(zip(order, order[1:]))
        return (
            sum(self.primary[i][j] for i, j in legs),
            sum(self.secondary[i][j] for i, j in legs),
        )


def _to_int_matrix(name: str, m: Matrix, n: int) -> list[list[int]]:
    if len(m) != n or any(len(row) != n for row in m):
        raise ValueError(f"{name} matrix must be {n}x{n}")
    out: list[list[int]] = []
    for i, row in enumerate(m):
        int_row = []
        for j, v in enumerate(row):
            if i == j:
                int_row.append(0)
                continue
            if not math.isfinite(v):
                raise ValueError(
                    f"{name}[{i}][{j}] is not finite; reachability must be "
                    "checked before solving"
                )
            if v < 0:
                raise ValueError(f"{name}[{i}][{j}] is negative")
            int_row.append(int(round(v)))
        out.append(int_row)
    return out


def build_problem(
    primary: Matrix, secondary: Matrix | None, constraints: Constraints
) -> Problem:
    n = len(primary)
    if not MIN_POINTS <= n <= MAX_POINTS:
        raise ValueError(f"point count must be {MIN_POINTS}-{MAX_POINTS}, got {n}")
    p = _to_int_matrix("primary", primary, n)
    s = _to_int_matrix("secondary", secondary, n) if secondary is not None else [
        [0] * n for _ in range(n)
    ]

    c = constraints
    if not 0 <= c.start < n:
        raise ValueError("start out of range")
    if c.end is not None and c.round_trip:
        raise ValueError("round_trip and a fixed end are mutually exclusive")
    if c.end is not None:
        if not 0 <= c.end < n:
            raise ValueError("end out of range")
        if c.end == c.start:
            raise ValueError("end equals start; use round_trip instead")
    if c.lock_first is not None:
        if not 0 <= c.lock_first < n:
            raise ValueError("lock_first out of range")
        if c.lock_first in (c.start, c.end):
            raise ValueError("lock_first must be a stop, not the start or end")

    scale = sum(max(row) for row in s) + 1
    if (sum(max(row) for row in p) + 1) * scale >= _INT64_SAFE:
        raise ValueError("costs too large to combine safely")
    return Problem(n=n, primary=p, secondary=s, constraints=c, scale=scale)
