"""UCS en grafo. Ver design.md, sección "Estrategia de búsqueda" y
"Batería como recurso" para la justificación de cada pieza de acá.
"""

from __future__ import annotations

import heapq
import itertools
from typing import Any, Optional

from internal_action import InternalAction
from scenario import station_online
from state import State
from successors import successors


class Node:
    __slots__ = ("state", "parent", "action", "cost")

    def __init__(
        self, state: State, parent: Optional["Node"], action: InternalAction | None, cost: int
    ) -> None:
        self.state = state
        self.parent = parent
        self.action = action
        self.cost = cost


def goal_test(scenario: dict[str, Any], state: State) -> bool:
    return all(
        station_online(scenario, state.stations_online, sid)
        for sid in scenario["goal"]["stations_online"]
    )


def _config_without_battery(state: State) -> tuple[Any, ...]:
    return (
        state.zone,
        state.keys_carried,
        state.tools_carried,
        state.materials_carried,
        state.keys_ground,
        state.tools_ground,
        state.materials_ground,
        state.doors_open,
        state.panels_ok,
        state.stations_online,
    )


def search(scenario: dict[str, Any], start: State) -> Node | None:
    counter = itertools.count()
    frontier: list[tuple[int, int, Node]] = [(0, next(counter), Node(start, None, None, 0))]
    closed: set[State] = set()
    path_cache: dict = {}  # dijkstra por (zona, puertas_abiertas) — vive toda la búsqueda

    # Dominancia de batería (design.md): por config física sin batería guardo
    # el frente de Pareto (costo, batería) visto hasta ahora. Un candidato
    # dominado por alguna entrada no puede mejorar ningún plan futuro — se
    # descarta sin insertarlo. Guardo el frente completo, no solo el mejor,
    # porque dos puntos incomparables (uno más barato, otro con más batería)
    # pueden ser necesarios los dos.
    pareto: dict[tuple[Any, ...], list[tuple[int, int]]] = {}

    def dominated(config: tuple[Any, ...], cost: int, battery: int) -> bool:
        return any(c <= cost and b >= battery for c, b in pareto.get(config, ()))

    def record(config: tuple[Any, ...], cost: int, battery: int) -> None:
        kept = [(c, b) for c, b in pareto.get(config, ()) if not (cost <= c and battery >= b)]
        kept.append((cost, battery))
        pareto[config] = kept

    while frontier:
        cost, _, node = heapq.heappop(frontier)
        if node.state in closed:
            continue
        if goal_test(scenario, node.state):
            return node
        closed.add(node.state)

        for action, nxt in successors(scenario, node.state, path_cache):
            if nxt in closed:
                continue
            new_cost = cost + action.cost
            config = _config_without_battery(nxt)
            if dominated(config, new_cost, nxt.battery):
                continue
            record(config, new_cost, nxt.battery)
            heapq.heappush(frontier, (new_cost, next(counter), Node(nxt, node, action, new_cost)))

    return None


def reconstruct(node: Node) -> list[InternalAction]:
    actions: list[InternalAction] = []
    while node.action is not None:
        actions.append(node.action)
        node = node.parent  # type: ignore[assignment]
    actions.reverse()
    return actions
