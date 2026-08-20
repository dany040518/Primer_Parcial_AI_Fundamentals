"""Punto de entrada del agente de búsqueda. Reemplaza a `demo_plan` en el endpoint."""

from __future__ import annotations

from typing import Any

from scenario import Scenario
from state import initial_state
from translate import to_contract_steps
from ucs import reconstruct, search


def solve(
    scenario: dict[str, Any],
    naive: bool = False,
    fully_naive: bool = False,
    weight_blind: bool = False,
) -> dict[str, Any]:
    # `naive`/`fully_naive`/`weight_blind` son un gancho de prueba (ver
    # tests/test_prunings_soundness.py), no algo que /api/solve exponga:
    # apagan las podas opcionales y, con `fully_naive`, también las
    # fundacionales, para comparar el costo óptimo contra el generador sin
    # ellas. `weight_blind` es aparte: deja todo encendido salvo la
    # condición de peso de la preferencia de muerto.
    #
    # El índice de bits de puertas/paneles/estaciones se calcula una sola
    # vez acá, no en un caché de módulo compartido entre requests — ver
    # scenario.py.
    scenario = Scenario(scenario)
    start = initial_state(scenario)
    goal_node = search(
        scenario, start, naive=naive, fully_naive=fully_naive, weight_blind=weight_blind
    )

    if goal_node is None:
        return {
            "solution_found": False,
            "total_cost": 0,
            "steps": [],
            "message": "FAILURE: no existe un plan que deje la misión cumplida",
        }

    steps = to_contract_steps(reconstruct(goal_node))
    total_cost = sum(int(s["cost"]) for s in steps)
    return {
        "solution_found": True,
        "total_cost": total_cost,
        "steps": steps,
        "message": f"UCS: {len(steps)} pasos, costo {total_cost}",
    }
