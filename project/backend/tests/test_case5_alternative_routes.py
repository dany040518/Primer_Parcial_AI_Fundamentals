"""Caso 5 del enunciado — rutas alternativas.

`mini_alternative_routes.json` tiene dos caminos disjuntos de Z1 a la misma
zona meta: por Z2 (costo 5+5=10) y por Z3 (costo 3+3=6). Las dos llegan a la
misma condición del mundo — `STATION1` online, que es toda la meta —, así
que un agente que solo mirara "¿llegué?" podría devolver cualquiera de las
dos. La estrategia elegida (UCS, minimizar `g(n)`) tiene que quedarse con la
barata: compruebo el costo exacto y que el plan devuelto nunca pisa Z2, la
ruta que existe pero no conviene.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from agent import solve  # noqa: E402
from simulator import goal_satisfied, simulate  # noqa: E402

SCENARIO_PATH = ROOT.parent / "scenarios" / "mini_alternative_routes.json"

EXPENSIVE_ROUTE_COST = 5 + 5 + 2  # por Z2
CHEAP_ROUTE_COST = 3 + 3 + 2  # por Z3


def test_agent_picks_the_cheap_route_not_just_any_legal_one() -> None:
    with SCENARIO_PATH.open(encoding="utf-8") as f:
        scenario = json.load(f)

    result = solve(scenario)

    assert result["solution_found"] is True
    assert result["total_cost"] == CHEAP_ROUTE_COST
    assert result["total_cost"] < EXPENSIVE_ROUTE_COST, (
        "las dos rutas no quedaron con costos distintos — la instancia no está "
        "demostrando lo que dice demostrar"
    )

    visited_zones = {s["to"] for s in result["steps"] if s["op"] == "MOVE"}
    assert "Z2" not in visited_zones, "el plan pisó la ruta cara, existiendo la barata"
    assert "Z3" in visited_zones

    final = simulate(scenario, result["steps"])
    assert goal_satisfied(scenario, final)
    assert final["energy_spent"] == result["total_cost"]


if __name__ == "__main__":
    test_agent_picks_the_cheap_route_not_just_any_legal_one()
    print("Caso 5 (rutas alternativas) OK.")
