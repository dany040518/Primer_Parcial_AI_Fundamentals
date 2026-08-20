"""Estado canónico de búsqueda. Ver design.md, sección Estado.

`doors_open`/`panels_ok`/`stations_online` son bitmask (`int`), no frozenset:
con pocas puertas/paneles/estaciones un `int` se hashea y compara en O(1),
un frozenset de strings paga overhead de objeto por elemento para nada.
El resto son frozensets/tuplas para que dos configuraciones físicamente
iguales hasheen igual sin importar el orden en que se construyeron.
"""

from __future__ import annotations

from typing import Any, NamedTuple

from scenario import (
    key_is_live,
    key_weight,
    material_weight,
    needed_material_count,
    tool_is_live,
    tool_weight,
)


class State(NamedTuple):
    zone: str
    battery: int
    keys_carried: frozenset[str]
    tools_carried: frozenset[str]
    materials_carried: frozenset[tuple[str, int]]
    keys_ground: frozenset[tuple[str, str]]
    tools_ground: frozenset[tuple[str, str]]
    materials_ground: frozenset[tuple[str, str, int]]
    doors_open: int
    panels_ok: int
    stations_online: int


def build_state(
    scenario: dict[str, Any],
    *,
    zone: str,
    battery: int,
    keys_carried: frozenset[str],
    tools_carried: frozenset[str],
    materials_carried: dict[str, int],
    keys_ground: dict[str, str],
    tools_ground: dict[str, str],
    materials_ground: dict[tuple[str, str], int],
    doors_open: int,
    panels_ok: int,
    stations_online: int,
    doors_changed: bool = True,
    panels_changed: bool = True,
    materials_recompute: bool = True,
) -> State:
    # `doors_changed`/`panels_changed`/`materials_recompute` son una
    # optimización de implementación, no de diseño: la vivacidad de una
    # llave solo depende de `doors_open`, la de una herramienta y el
    # recorte de material solo de `panels_ok` (y de cuánto material cargo).
    # Si ninguno de esos cambió respecto al estado del que vengo, repetir el
    # filtro reproduce exactamente lo que ya tenía — así que lo salto. Es
    # seguro porque nada más puede colar una entrada muerta en el suelo:
    # `successors.py` ya no agrega al suelo un objeto muerto al soltarlo (se
    # descarta ahí mismo), así que si las puertas/paneles no cambiaron, lo
    # que entra aquí ya viene filtrado.
    if doors_changed:
        live_keys_ground = frozenset(
            (kid, z) for kid, z in keys_ground.items() if key_is_live(scenario, kid, doors_open)
        )
    else:
        live_keys_ground = frozenset(keys_ground.items())

    if panels_changed:
        live_tools_ground = frozenset(
            (tid, z) for tid, z in tools_ground.items() if tool_is_live(scenario, tid, panels_ok)
        )
    else:
        live_tools_ground = frozenset(tools_ground.items())

    if materials_recompute:
        ground_pairs: list[tuple[str, str, int]] = []
        material_types = {t for (t, _z) in materials_ground}
        for material_type in material_types:
            needed = needed_material_count(scenario, material_type, panels_ok)
            allowed = max(0, needed - materials_carried.get(material_type, 0))
            for z in sorted({z for (t, z) in materials_ground if t == material_type}):
                if allowed <= 0:
                    break
                take = min(allowed, materials_ground[(material_type, z)])
                if take > 0:
                    ground_pairs.append((material_type, z, take))
                    allowed -= take
        frozen_materials_ground = frozenset(ground_pairs)
    else:
        frozen_materials_ground = frozenset(
            (t, z, c) for (t, z), c in materials_ground.items() if c > 0
        )

    return State(
        zone=zone,
        battery=battery,
        keys_carried=frozenset(keys_carried),
        tools_carried=frozenset(tools_carried),
        materials_carried=frozenset((t, c) for t, c in materials_carried.items() if c > 0),
        keys_ground=live_keys_ground,
        tools_ground=live_tools_ground,
        materials_ground=frozen_materials_ground,
        doors_open=doors_open,
        panels_ok=panels_ok,
        stations_online=stations_online,
    )


def initial_state(scenario: dict[str, Any]) -> State:
    materials_ground: dict[tuple[str, str], int] = {}
    for m in scenario["materials"]:
        key = (m["type"], m["zone"])
        materials_ground[key] = materials_ground.get(key, 0) + int(m["count"])

    return build_state(
        scenario,
        zone=scenario["robot"]["start"],
        battery=int(scenario["robot"]["battery_start"]),
        keys_carried=frozenset(),
        tools_carried=frozenset(),
        materials_carried={},
        keys_ground={k["id"]: k["zone"] for k in scenario["keys"]},
        tools_ground={t["id"]: t["zone"] for t in scenario["tools"]},
        materials_ground=materials_ground,
        doors_open=0,
        panels_ok=0,
        stations_online=0,
    )


def carried_weight(scenario: dict[str, Any], state: State) -> int:
    total = sum(key_weight(scenario, k) for k in state.keys_carried)
    total += sum(tool_weight(scenario, t) for t in state.tools_carried)
    total += sum(material_weight(scenario, t) * c for t, c in state.materials_carried)
    return total
