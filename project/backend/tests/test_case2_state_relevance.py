"""Caso 2 del enunciado — información relevante.

Dos configuraciones que difieren en algo que puede cambiar las acciones
futuras tienen que seguir siendo estados distintos. Construyo dos `State`
que solo difieren en si DOOR1 está abierta o cerrada y compruebo dos cosas:
que son estados distintos (`!=`, hash distinto), y que la diferencia es real
— con la puerta cerrada, Z2 es inalcanzable; con la puerta abierta, deja de
serlo. No basta con que los estados no sean iguales; tienen que serlo *por
una razón que le importa a la búsqueda*.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from scenario import with_door_open  # noqa: E402
from simulator import load_scenario  # noqa: E402
from state import State, build_state, initial_state  # noqa: E402
from successors import successors  # noqa: E402


def _reachable_move_targets(scenario: dict, state: State) -> set[str]:
    return {a.target for a, _ in successors(scenario, state) if a.kind == "MOVE_TO"}


def test_door_state_is_relevant_and_kept_distinct() -> None:
    scenario = load_scenario()
    s_closed = initial_state(scenario)

    s_open = build_state(
        scenario,
        zone=s_closed.zone,
        battery=s_closed.battery,
        keys_carried=s_closed.keys_carried,
        tools_carried=s_closed.tools_carried,
        materials_carried=dict(s_closed.materials_carried),
        keys_ground=dict(s_closed.keys_ground),
        tools_ground=dict(s_closed.tools_ground),
        materials_ground={(t, z): c for t, z, c in s_closed.materials_ground},
        doors_open=with_door_open(scenario, s_closed.doors_open, "DOOR1"),
        panels_ok=s_closed.panels_ok,
        stations_online=s_closed.stations_online,
    )

    assert s_closed != s_open
    assert hash(s_closed) != hash(s_open)

    # La diferencia no es cosmética: con DOOR1 cerrada, Z2 no aparece entre
    # los destinos alcanzables (ni por el corredor directo ni por Z3-DOOR2,
    # las dos rutas a Z2 pasan por una puerta cerrada). Abierta, sí aparece.
    targets_closed = _reachable_move_targets(scenario, s_closed)
    targets_open = _reachable_move_targets(scenario, s_open)
    assert "Z2" not in targets_closed
    assert "Z2" in targets_open


def test_battery_level_is_relevant_and_kept_distinct() -> None:
    scenario = load_scenario()
    s_full = initial_state(scenario)
    s_low = s_full._replace(battery=1)

    assert s_full != s_low
    assert hash(s_full) != hash(s_low)

    # Con batería 1, ningún MOVE_TO cuesta poco: la instancia arranca sin
    # nada al alcance por 1 de batería. Con batería completa, sí hay adónde
    # ir. Es la misma razón del caso anterior con otra variable.
    targets_full = _reachable_move_targets(scenario, s_full)
    targets_low = _reachable_move_targets(scenario, s_low)
    assert targets_low != targets_full


if __name__ == "__main__":
    test_door_state_is_relevant_and_kept_distinct()
    test_battery_level_is_relevant_and_kept_distinct()
    print("Caso 2 (información relevante) OK.")
