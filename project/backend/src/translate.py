"""Traduce las acciones internas al contrato cerrado de CONTRATO.md.

OPEN_DOOR, MOVE_TO, SWAP, etc. son nombres internos; lo único que sale hacia
`/api/solve` son las cuatro operaciones de acá. `MOVE_TO` es un salto
compuesto (ver travel.py) — lo reexpando en los MOVE de un solo corredor que
trae en `extra`. `SWAP` es un DROP+PICKUP fusionado (ver successors.py) — lo
separo en los dos pasos del contrato, cada uno con su costo oficial.
"""

from __future__ import annotations

from typing import Any

from internal_action import InternalAction

_INTERACT_ACTIONS = {"OPEN_DOOR", "REPAIR", "ACTIVATE", "RECHARGE"}


def to_contract_steps(actions: list[InternalAction]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for a in actions:
        if a.kind == "MOVE_TO":
            for frm, to, cost in a.extra:
                steps.append({"op": "MOVE", "from": frm, "to": to, "cost": cost})
        elif a.kind in ("PICKUP_KEY", "PICKUP_TOOL", "PICKUP_MATERIAL"):
            steps.append({"op": "PICKUP", "item": a.target, "cost": a.cost})
        elif a.kind == "DROP":
            steps.append({"op": "DROP", "item": a.target, "cost": a.cost})
        elif a.kind == "SWAP":
            dropped_item, drop_cost, pickup_cost = a.extra
            steps.append({"op": "DROP", "item": dropped_item, "cost": drop_cost})
            steps.append({"op": "PICKUP", "item": a.target, "cost": pickup_cost})
        elif a.kind in _INTERACT_ACTIONS:
            step = {"op": "INTERACT", "target": a.target, "action": a.kind, "cost": a.cost}
            if a.kind == "REPAIR":
                step["consumes"] = a.extra
            steps.append(step)
        else:
            raise ValueError(f"acción interna sin traducción al contrato: {a.kind}")
    return steps
