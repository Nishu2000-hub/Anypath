"""Exact Held-Karp DP for small instances (SPEC: <= 10 nodes).

The DP runs backwards: ``best[mask][j]`` is the cheapest way to finish the
route from node ``j`` having already visited the free stops in ``mask``.
Scanning candidate next stops in ascending index order and keeping only
strictly better ones makes the reconstructed path the lexicographically
smallest among all optimal paths, which is the SPEC's final tie-break.
"""

from __future__ import annotations

from .model import Problem


def solve_held_karp(problem: Problem) -> list[int]:
    c = problem.constraints
    terminal = c.terminal
    prefix = [c.start] if c.lock_first is None else [c.start, c.lock_first]
    head = prefix[-1]
    fixed = set(prefix)
    if terminal is not None:
        fixed.add(terminal)
    free = [v for v in range(problem.n) if v not in fixed]  # ascending
    k = len(free)
    full = (1 << k) - 1
    w = problem.weight

    # best/nxt are indexed [mask][node]; node is a matrix index.
    best: list[dict[int, int]] = [dict() for _ in range(full + 1)]
    nxt: list[dict[int, int]] = [dict() for _ in range(full + 1)]

    for mask in range(full, -1, -1):
        if mask == 0:
            currents = [head]
        else:
            currents = [free[b] for b in range(k) if mask >> b & 1]
        for j in currents:
            if mask == full:
                best[mask][j] = 0 if terminal is None else w(j, terminal)
                continue
            best_cost = None
            best_u = -1
            for b in range(k):
                if mask >> b & 1:
                    continue
                u = free[b]
                cost = w(j, u) + best[mask | 1 << b][u]
                if best_cost is None or cost < best_cost:
                    best_cost, best_u = cost, u
            best[mask][j] = best_cost
            nxt[mask][j] = best_u

    order = list(prefix)
    mask, cur = 0, head
    pos = {v: b for b, v in enumerate(free)}
    while mask != full:
        cur = nxt[mask][cur]
        order.append(cur)
        mask |= 1 << pos[cur]
    if terminal is not None:
        order.append(terminal)
    return order
