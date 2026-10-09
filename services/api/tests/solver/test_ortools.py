"""SPEC quality target: for every random instance with <= 9 nodes the OR-Tools
result equals the brute-force optimum.

OR-Tools may pick a different order among equal-cost optima, so the
(primary, secondary) cost is compared, not the order. The test runs with a
0.3 s limit, stricter than the 1 s production limit, to keep the suite fast.
"""

from __future__ import annotations

from hypothesis import given, settings

from solver import build_problem, solve_ortools

from .conftest import brute_force, instances

TEST_TIME_LIMIT_S = 0.3


def assert_valid_route(problem, order):
    c = problem.constraints
    assert order[0] == c.start
    if c.lock_first is not None:
        assert order[1] == c.lock_first
    if c.terminal is not None:
        assert order[-1] == c.terminal
    visited = order[:-1] if c.round_trip else order
    assert sorted(visited) == list(range(problem.n))


@settings(max_examples=80, deadline=None)
@given(instances(min_n=2, max_n=9))
def test_ortools_matches_brute_force_optimum(instance):
    problem = build_problem(*instance)
    order = solve_ortools(problem, time_limit_s=TEST_TIME_LIMIT_S)
    assert_valid_route(problem, order)
    assert problem.costs(order) == problem.costs(brute_force(problem))
