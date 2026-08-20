"""Regresión: el índice de bits de puertas/paneles/estaciones no puede
mezclarse entre dos escenarios distintos resueltos en la misma sesión.

Bug real, encontrado con el generador aleatorio de test_prunings_soundness.py
(no algo que ese test buscara): `scenario.py` guardaba el índice en un caché
de módulo con `id(scenario)` como clave. Python reutiliza esa dirección de
memoria en cuanto el dict del escenario anterior se recolecta como basura,
así que una segunda llamada a `solve()` con OTRO escenario podía heredar el
índice de puertas del primero. `/api/solve` recibe un dict nuevo en cada
request — esto pasaba en producción, no solo corriendo muchos escenarios
efímeros en un test.

El arreglo: el índice vive en el propio objeto `Scenario` (`scenario.py`),
construido una sola vez al entrar a `agent.solve()`, no en un caché
compartido entre llamadas. Uso dos escenarios chicos (no `scenario.json`,
que tarda ~11s) porque el bug no depende del tamaño — solo de alternar
escenarios distintos.
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

SCENARIOS_DIR = ROOT.parent / "scenarios"


def _load(name: str) -> dict:
    with (SCENARIOS_DIR / name).open(encoding="utf-8") as f:
        return json.load(f)


def test_alternating_scenarios_never_cross_contaminate_bit_index() -> None:
    a = _load("mini_pruning_check.json")
    b = _load("mini_weight_guard_check.json")

    # Alterno a propósito, varias veces: es exactamente el patrón que
    # reventó el caché por id() — un escenario se libera, el siguiente
    # dict puede caer en la misma dirección de memoria.
    for _ in range(5):
        result_a = solve(a)
        assert result_a["solution_found"] is True
        assert result_a["total_cost"] == 15
        final_a = simulate(a, result_a["steps"])
        assert goal_satisfied(a, final_a)

        result_b = solve(b)
        assert result_b["solution_found"] is True
        assert result_b["total_cost"] == 41
        final_b = simulate(b, result_b["steps"])
        assert goal_satisfied(b, final_b)


if __name__ == "__main__":
    test_alternating_scenarios_never_cross_contaminate_bit_index()
    print("All scenario-index isolation tests passed.")
