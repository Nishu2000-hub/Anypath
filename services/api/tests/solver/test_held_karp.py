"""Held-Karp is exact: it must return the same order as brute force,
including the SPEC tie-break (secondary cost, then lexicographic order)."""

from __future__ import annotations

from hypothesis import given, settings

from solver import build_problem, solve_held_karp

from .conftest import brute_force, instances


@settings(max_examples=300, deadline=None)
@given(instances(max_n=9))
def test_matches_brute_force_order(instance):
    problem = build_problem(*instance)
    assert solve_held_karp(problem) == brute_force(problem)


@settings(max_examples=300, deadline=None)
@given(instances(max_n=8, max_cost=2))
def test_matches_brute_force_with_heavy_ties(instance):
    # Costs in {1, 2} make many orders tie, exercising both tie-break levels.
    problem = build_problem(*instance)
    assert solve_held_karp(problem) == brute_force(problem)
