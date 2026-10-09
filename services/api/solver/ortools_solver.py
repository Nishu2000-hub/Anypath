"""OR-Tools routing with guided local search (SPEC: 11-15 nodes, 1 s limit).

Constraint encoding:
* fixed end   -> vehicle start/end nodes = (start, end)
* round trip  -> depot = start
* open path   -> a dummy end node reachable from every node at zero cost
* lock first  -> NextVar(route start) == lock_first
"""

from __future__ import annotations

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from .model import Problem

DEFAULT_TIME_LIMIT_S = 1.0


def solve_ortools(problem: Problem, time_limit_s: float = DEFAULT_TIME_LIMIT_S) -> list[int]:
    c = problem.constraints
    n = problem.n
    open_path = c.terminal is None
    dummy = n if open_path else None

    if open_path:
        manager = pywrapcp.RoutingIndexManager(n + 1, 1, [c.start], [dummy])
    elif c.round_trip:
        manager = pywrapcp.RoutingIndexManager(n, 1, c.start)
    else:
        manager = pywrapcp.RoutingIndexManager(n, 1, [c.start], [c.end])
    routing = pywrapcp.RoutingModel(manager)

    def arc_cost(from_index: int, to_index: int) -> int:
        i = manager.IndexToNode(from_index)
        j = manager.IndexToNode(to_index)
        if i == dummy or j == dummy:
            return 0
        return problem.weight(i, j)

    transit = routing.RegisterTransitCallback(arc_cost)
    routing.SetArcCostEvaluatorOfAllVehicles(transit)

    if c.lock_first is not None:
        routing.solver().Add(
            routing.NextVar(routing.Start(0)) == manager.NodeToIndex(c.lock_first)
        )

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    params.time_limit.FromMilliseconds(max(1, int(time_limit_s * 1000)))

    assignment = routing.SolveWithParameters(params)
    if assignment is None:
        raise RuntimeError("OR-Tools found no solution")

    order: list[int] = []
    index = routing.Start(0)
    while not routing.IsEnd(index):
        order.append(manager.IndexToNode(index))
        index = assignment.Value(routing.NextVar(index))
    if not open_path:
        order.append(manager.IndexToNode(index))
    return order
