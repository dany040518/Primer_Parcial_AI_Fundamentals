"""Caso 3 del enunciado — menos acciones no es menor costo.

No basta con decir que la función de costo importa; hay que construirlo. Uso
`mini_steps_vs_cost.json`: un salto directo Z1->Z3 de un corredor (costo 10)
contra dos saltos Z1->Z2->Z3 (costo 3+3=6). El plan de menos pasos usa el
salto directo (2 acciones: MOVE + ACTIVATE) y es perfectamente legal — pasa
el simulador sin problema — pero cuesta más que el plan óptimo real (3
acciones: MOVE + MOVE + ACTIVATE).

Para encontrar el plan de menos pasos corro una búsqueda aparte que reusa el
mismo `successors()` y el mismo `goal_test`, pero ordena la frontera por
número de pasos en vez de por `g(n)` — y con `naive=True`, para que `MOVE`
sea de un solo corredor (si dejo el `MOVE_TO` compuesto, siempre calcula el
camino más barato entre dos paradas y el conteo de pasos deja de significar
"cuántos MOVE de un corredor", que es lo que quiero contar acá).
"""

from __future__ import annotations

import heapq
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from agent import solve  # noqa: E402
from simulator import goal_satisfied, simulate  # noqa: E402
from state import initial_state  # noqa: E402
from successors import successors  # noqa: E402
from translate import to_contract_steps  # noqa: E402
from ucs import Node, goal_test, reconstruct  # noqa: E402

SCENARIO_PATH = ROOT.parent / "scenarios" / "mini_steps_vs_cost.json"


def _load_scenario() -> dict:
    with SCENARIO_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _search_fewest_steps(scenario: dict) -> Node | None:
    start = initial_state(scenario)
    counter = itertools.count()
    frontier: list[tuple[int, int, Node]] = [(0, next(counter), Node(start, None, None, 0))]
    closed = set()
    path_cache: dict = {}

    while frontier:
        steps, _, node = heapq.heappop(frontier)
        if node.state in closed:
            continue
        if goal_test(scenario, node.state):
            return node
        closed.add(node.state)
        for action, nxt in successors(scenario, node.state, path_cache, naive=True):
            if nxt in closed:
                continue
            real_cost = node.cost + action.cost
            heapq.heappush(frontier, (steps + 1, next(counter), Node(nxt, node, action, real_cost)))

    return None


def test_fewest_steps_plan_is_legal_but_more_expensive_than_optimal() -> None:
    scenario = _load_scenario()

    optimal = solve(scenario)
    assert optimal["solution_found"] is True

    fewest_steps_node = _search_fewest_steps(scenario)
    assert fewest_steps_node is not None
    fewest_steps_plan = to_contract_steps(reconstruct(fewest_steps_node))

    assert len(fewest_steps_plan) < len(optimal["steps"]), (
        "el plan de menos pasos no tiene menos pasos que el óptimo — la instancia no "
        "está demostrando lo que dice demostrar"
    )
    assert fewest_steps_node.cost > optimal["total_cost"], (
        "el plan de menos pasos no cuesta más que el óptimo — la instancia no está "
        "demostrando lo que dice demostrar"
    )

    # Legal de verdad, no solo "generado por mi agente": el simulador lo
    # tiene que aceptar paso a paso.
    final = simulate(scenario, fewest_steps_plan)
    assert goal_satisfied(scenario, final)
    assert final["energy_spent"] == fewest_steps_node.cost


if __name__ == "__main__":
    test_fewest_steps_plan_is_legal_but_more_expensive_than_optimal()
    print("Caso 3 (menos pasos no es menor costo) OK.")
