"""Dispatcher, validation, determinism and timing."""

from __future__ import annotations

import random
import time

import pytest

from solver import Constraints, solve

from .conftest import random_matrix


def test_backend_selection():
    rng = random.Random(0)
    assert solve(random_matrix(rng, 10, 1, 100)).method == "held_karp"
    assert solve(random_matrix(rng, 11, 1, 100), time_limit_s=0.1).method == "ortools"


def test_route_shapes():
    m = [
        [0, 1, 9, 9],
        [9, 0, 1, 9],
        [9, 9, 0, 1],
        [1, 1, 9, 0],
    ]
    assert solve(m).order == [0, 1, 2, 3]
    assert solve(m, constraints=Constraints(round_trip=True)).order == [0, 1, 2, 3, 0]
    assert solve(m, constraints=Constraints(end=2)).order == [0, 3, 1, 2]
    locked = solve(m, constraints=Constraints(lock_first=2))
    assert locked.order[:2] == [0, 2]
    assert locked.order == [0, 2, 3, 1]


def test_minimum_two_points():
    assert solve([[0, 5], [7, 0]]).order == [0, 1]
    assert solve([[0, 5], [7, 0]], constraints=Constraints(round_trip=True)).order == [0, 1, 0]


def test_tie_breaks_follow_spec():
    # Primary ties everywhere: secondary decides.
    flat = [[0 if i == j else 10 for j in range(4)] for i in range(4)]
    secondary = [[0, 5, 5, 1], [5, 0, 5, 5], [5, 1, 0, 5], [5, 5, 5, 0]]
    assert solve(flat, secondary).order == [0, 3, 2, 1]
    # Everything ties: lexicographically smallest order wins.
    assert solve(flat, flat).order == [0, 1, 2, 3]


def test_deterministic_same_matrix_same_order():
    rng = random.Random(42)
    m = random_matrix(rng, 10, 1, 3)  # lots of ties
    s = random_matrix(rng, 10, 1, 3)
    c = Constraints(start=4, end=7, lock_first=1)
    orders = {tuple(solve(m, s, c).order) for _ in range(5)}
    assert len(orders) == 1


def test_fractional_costs_are_rounded():
    # Weather multipliers produce fractional durations.
    m = [[0, 100 * 1.15, 50.4], [10, 0, 10], [10, 10.6, 0]]
    sol = solve(m)
    assert sol.primary_cost == 50 + 11


@pytest.mark.parametrize(
    "primary, constraints, match",
    [
        ([[0]], Constraints(), "point count"),
        ([[0] * 16 for _ in range(16)], Constraints(), "point count"),
        ([[0, 1], [1]], Constraints(), "2x2"),
        ([[0, 1], [1, 0]], Constraints(end=1, round_trip=True), "mutually exclusive"),
        ([[0, 1], [1, 0]], Constraints(end=0), "end equals start"),
        ([[0, 1, 1], [1, 0, 1], [1, 1, 0]], Constraints(end=2, lock_first=2), "lock_first"),
        ([[0, 1], [1, 0]], Constraints(lock_first=0), "lock_first"),
        ([[0, float("inf")], [1, 0]], Constraints(), "reachability"),
        ([[0, -1], [1, 0]], Constraints(), "negative"),
    ],
)
def test_validation(primary, constraints, match):
    with pytest.raises(ValueError, match=match):
        solve(primary, constraints=constraints)


@pytest.mark.timing
@pytest.mark.parametrize(
    "constraints",
    [
        Constraints(start=0),
        Constraints(start=0, end=14, lock_first=5),
        Constraints(start=3, round_trip=True, lock_first=9),
    ],
    ids=["open", "fixed_end+lock", "round_trip+lock"],
)
def test_fifteen_points_under_1_5_seconds(constraints):
    # SPEC: 15 points solves in < 1.5 s (production 1 s OR-Tools limit).
    rng = random.Random(15)
    durations = random_matrix(rng, 15, 60, 7200)
    distances = random_matrix(rng, 15, 500, 150_000)
    t0 = time.perf_counter()
    sol = solve(durations, distances, constraints)
    elapsed = time.perf_counter() - t0
    print(f"\n15 nodes [{sol.method}] {elapsed:.3f}s order={sol.order}")
    assert sol.method == "ortools"
    assert sorted(set(sol.order)) == list(range(15))
    assert elapsed < 1.5
