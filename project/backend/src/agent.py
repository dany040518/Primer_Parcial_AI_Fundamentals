"""Punto de entrada del agente de búsqueda. Reemplaza a `demo_plan` en el endpoint."""

from __future__ import annotations

from typing import Any

from state import initial_state
from translate import to_contract_steps
from ucs import reconstruct, search


def solve(scenario: dict[str, Any]) -> dict[str, Any]:
    start = initial_state(scenario)
    goal_node = search(scenario, start)

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
