"""Route-order solver (SPEC "Architecture: Solver").

One entry point, ``solve``; the backend is picked by size:
exact Held-Karp for <= 10 nodes, OR-Tools guided local search above that.
"""

from __future__ import annotations

from .held_karp import solve_held_karp
from .model import MAX_POINTS, MIN_POINTS, Constraints, Matrix, Problem, Solution, build_problem
from .ortools_solver import DEFAULT_TIME_LIMIT_S, solve_ortools

EXACT_MAX_NODES = 10

__all__ = [
    "Constraints",
    "DEFAULT_TIME_LIMIT_S",
    "EXACT_MAX_NODES",
    "MAX_POINTS",
    "MIN_POINTS",
    "Problem",
    "Solution",
    "build_problem",
    "solve",
    "solve_held_karp",
    "solve_ortools",
]


def solve(
    primary: Matrix,
    secondary: Matrix | None = None,
    constraints: Constraints = Constraints(),
    *,
    time_limit_s: float = DEFAULT_TIME_LIMIT_S,
) -> Solution:
    """Return the visiting order minimizing ``primary``, ties broken by
    ``secondary`` then lexicographic order. Raises ``ValueError`` on invalid
    input (the API layer maps it to 422)."""
    problem = build_problem(primary, secondary, constraints)
    if problem.n <= EXACT_MAX_NODES:
        order, method = solve_held_karp(problem), "held_karp"
    else:
        order, method = solve_ortools(problem, time_limit_s), "ortools"
    p, s = problem.costs(order)
    return Solution(order=order, primary_cost=p, secondary_cost=s, method=method)
