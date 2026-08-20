"""Consultas de solo lectura sobre el escenario crudo. Nada de estado aquí."""

from __future__ import annotations

from typing import Any


def corridors_from(scenario: dict[str, Any], zone: str) -> list[dict[str, Any]]:
    return [c for c in scenario["corridors"] if c["from"] == zone]


def key_by_id(scenario: dict[str, Any], key_id: str) -> dict[str, Any]:
    return next(k for k in scenario["keys"] if k["id"] == key_id)


def tool_by_id(scenario: dict[str, Any], tool_id: str) -> dict[str, Any]:
    return next(t for t in scenario["tools"] if t["id"] == tool_id)


def material_by_type(scenario: dict[str, Any], material_type: str) -> dict[str, Any]:
    return next(m for m in scenario["materials"] if m["type"] == material_type)


def chargers_at(scenario: dict[str, Any], zone: str) -> list[dict[str, Any]]:
    return [c for c in scenario["chargers"] if c["zone"] == zone]


def key_weight(scenario: dict[str, Any], key_id: str) -> int:
    return int(key_by_id(scenario, key_id)["weight"])


def tool_weight(scenario: dict[str, Any], tool_id: str) -> int:
    return int(tool_by_id(scenario, tool_id)["weight"])


def material_weight(scenario: dict[str, Any], material_type: str) -> int:
    return int(material_by_type(scenario, material_type)["weight"])


# --- doors_open/panels_ok/stations_online van como bitmask (int), no frozenset.
# Un int se hashea y compara en O(1); con 3-20 puertas/paneles/estaciones un
# frozenset de strings paga overhead de objeto por cada elemento para nada.
# El índice se cachea por escenario (id() del dict) porque no cambia durante
# una búsqueda: el mismo escenario se consulta miles de veces por segundo.

_index_cache: dict[int, dict[str, dict[str, int]]] = {}


def _index(scenario: dict[str, Any]) -> dict[str, dict[str, int]]:
    cached = _index_cache.get(id(scenario))
    if cached is not None:
        return cached
    idx = {
        "door": {d["id"]: i for i, d in enumerate(scenario["doors"])},
        "panel": {p["id"]: i for i, p in enumerate(scenario["panels"])},
        "station": {s["id"]: i for i, s in enumerate(scenario["stations"])},
    }
    _index_cache[id(scenario)] = idx
    return idx


def door_open(scenario: dict[str, Any], doors_open: int, door_id: str) -> bool:
    return bool(doors_open & (1 << _index(scenario)["door"][door_id]))


def panel_ok(scenario: dict[str, Any], panels_ok: int, panel_id: str) -> bool:
    return bool(panels_ok & (1 << _index(scenario)["panel"][panel_id]))


def station_online(scenario: dict[str, Any], stations_online: int, station_id: str) -> bool:
    return bool(stations_online & (1 << _index(scenario)["station"][station_id]))


def with_door_open(scenario: dict[str, Any], doors_open: int, door_id: str) -> int:
    return doors_open | (1 << _index(scenario)["door"][door_id])


def with_panel_ok(scenario: dict[str, Any], panels_ok: int, panel_id: str) -> int:
    return panels_ok | (1 << _index(scenario)["panel"][panel_id])


def with_station_online(scenario: dict[str, Any], stations_online: int, station_id: str) -> int:
    return stations_online | (1 << _index(scenario)["station"][station_id])


def needed_material_count(scenario: dict[str, Any], material_type: str, panels_ok: int) -> int:
    return sum(
        1
        for p in scenario["panels"]
        if not panel_ok(scenario, panels_ok, p["id"]) and p["requires"]["material"] == material_type
    )


def key_is_live(scenario: dict[str, Any], key_id: str, doors_open: int) -> bool:
    # Viva = todavía abre algo. Sin esto cada llave usada seguiría cargando el
    # estado con "en qué zona quedó tirada" para siempre. Ver design.md, Relevancia.
    return any(
        d["key"] == key_id and not door_open(scenario, doors_open, d["id"])
        for d in scenario["doors"]
    )


def tool_is_live(scenario: dict[str, Any], tool_id: str, panels_ok: int) -> bool:
    return any(
        p["requires"]["tool"] == tool_id and not panel_ok(scenario, panels_ok, p["id"])
        for p in scenario["panels"]
    )
