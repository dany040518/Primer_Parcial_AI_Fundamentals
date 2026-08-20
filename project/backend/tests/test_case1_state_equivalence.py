"""Caso 1 del enunciado — estados equivalentes.

Dos historias de búsqueda distintas que llegan a la misma configuración
física tienen que producir el mismo estado lógico: mismo `==`, mismo hash.
La prueba es a nivel de `State`, no de plan — construyo dos secuencias de
acciones internas que solo difieren en el orden en que recogen dos objetos
independientes (KEY2 y FUSE, ninguno depende del otro) y comparo los `State`
resultantes directamente, no los planes que los produjeron.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from simulator import load_scenario  # noqa: E402
from state import initial_state  # noqa: E402
from successors import successors  # noqa: E402


def _apply(scenario: dict, state, path_cache: dict, kind: str, target: str):
    for action, nxt in successors(scenario, state, path_cache):
        if action.kind == kind and action.target == target:
            return nxt
    raise AssertionError(f"no encontré un sucesor {kind} {target} desde este estado")


def test_pickup_order_does_not_change_the_resulting_state() -> None:
    scenario = load_scenario()
    cache_a: dict = {}
    cache_b: dict = {}

    s0 = initial_state(scenario)
    s1 = _apply(scenario, s0, cache_a, "PICKUP_KEY", "KEY1")
    s2 = _apply(scenario, s1, cache_a, "OPEN_DOOR", "DOOR1")
    s3 = _apply(scenario, s2, cache_a, "MOVE_TO", "Z2")  # KEY2 y FUSE están los dos acá

    # Camino A: KEY2 primero, FUSE después.
    a1 = _apply(scenario, s3, cache_a, "PICKUP_KEY", "KEY2")
    a2 = _apply(scenario, a1, cache_a, "PICKUP_MATERIAL", "FUSE")

    # Camino B: FUSE primero, KEY2 después. Misma zona de partida (s3),
    # cache aparte para no mezclar el Dijkstra con el camino A (no debería
    # importar, pero así el test no depende de compartirlo).
    b1 = _apply(scenario, s3, cache_b, "PICKUP_MATERIAL", "FUSE")
    b2 = _apply(scenario, b1, cache_b, "PICKUP_KEY", "KEY2")

    assert a2 == b2
    assert hash(a2) == hash(b2)

    # Los estados intermedios sí difieren (llevan cosas distintas en el
    # camino) — el punto es que la meta física final es la misma pese a
    # que la historia para llegar ahí no lo fue.
    assert a1 != b1


if __name__ == "__main__":
    test_pickup_order_does_not_change_the_resulting_state()
    print("Caso 1 (equivalencia de estados) OK.")
