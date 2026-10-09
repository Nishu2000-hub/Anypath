from __future__ import annotations

import itertools
import random

from hypothesis import strategies as st

from solver import Constraints, Problem


def brute_force(problem: Problem) -> list[int]:
    """Reference optimum: enumerate every order. ``itertools.permutations`` of
    a sorted list yields lexicographic order, so keeping only strictly better
    costs returns the lexicographically smallest optimal order."""
    c = problem.constraints
    prefix = [c.start] if c.lock_first is None else [c.start, c.lock_first]
    suffix = [] if c.terminal is None else [c.terminal]
    fixed = set(prefix) | set(suffix)
    free = sorted(v for v in range(problem.n) if v not in fixed)
    best_order, best_cost = None, None
    for perm in itertools.permutations(free):
        order = prefix + list(perm) + suffix
        cost = problem.costs(order)
        if best_cost is None or cost < best_cost:
            best_order, best_cost = order, cost
    return best_order


def random_matrix(rng: random.Random, n: int, lo: int, hi: int) -> list[list[int]]:
    """Asymmetric matrix (traffic makes A->B != B->A), zero diagonal."""
    return [[0 if i == j else rng.randint(lo, hi) for j in range(n)] for i in range(n)]


@st.composite
def instances(draw, min_n: int = 2, max_n: int = 9, max_cost: int = 3600):
    """(primary, secondary, constraints) covering every SPEC route shape:
    open path / fixed end / round trip, each with or without a locked stop."""
    n = draw(st.integers(min_n, max_n))
    cell = st.integers(1, max_cost)
    primary = [[0 if i == j else draw(cell) for j in range(n)] for i in range(n)]
    secondary = [[0 if i == j else draw(cell) for j in range(n)] for i in range(n)]
    start = draw(st.integers(0, n - 1))
    shape = draw(st.sampled_from(["open", "end", "round_trip"]))
    end = None
    if shape == "end":
        end = draw(st.sampled_from([v for v in range(n) if v != start]))
    stops = [v for v in range(n) if v not in (start, end)]
    lock = draw(st.one_of(st.none(), st.sampled_from(stops))) if stops else None
    return primary, secondary, Constraints(
        start=start, end=end, round_trip=shape == "round_trip", lock_first=lock
    )
