"""Caso 4 del enunciado — sin solución.

`mini_no_solution.json` pide reparar un panel con `TOOL_GHOST`, una
herramienta que no existe en ningún lado del escenario — la meta es
inalcanzable sin importar cuánto explore. El agente tiene que terminar y
decir `FAILURE`, no quedarse buscando: `solution_found: false`, `steps: []`.

El enunciado prohíbe expresamente una ejecución que se quede atrapada
explorando — así que el test falla si tarda más de unos segundos, no solo si
la respuesta está mal.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from agent import solve  # noqa: E402

SCENARIO_PATH = ROOT.parent / "scenarios" / "mini_no_solution.json"
MAX_SECONDS = 5.0


def test_unreachable_goal_returns_failure_and_terminates_promptly() -> None:
    with SCENARIO_PATH.open(encoding="utf-8") as f:
        scenario = json.load(f)

    t0 = time.time()
    result = solve(scenario)
    elapsed = time.time() - t0

    assert result["solution_found"] is False
    assert result["steps"] == []
    assert elapsed < MAX_SECONDS, (
        f"tardó {elapsed:.2f}s en concluir FAILURE — el enunciado prohíbe quedarse "
        f"explorando indefinidamente"
    )


if __name__ == "__main__":
    test_unreachable_goal_returns_failure_and_terminates_promptly()
    print("Caso 4 (sin solución) OK.")
