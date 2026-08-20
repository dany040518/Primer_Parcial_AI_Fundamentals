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
#
# El índice es un dato derivado del escenario: vive con él, no en un caché de
# módulo. Un caché por `id(scenario)` era un bug real — Python reutiliza esa
# dirección de memoria en cuanto el dict anterior se recolecta como basura,
# así que una segunda llamada a `solve()` con OTRO escenario podía heredar el
# índice del primero si cayó en el mismo `id()`. `/api/solve` recibe un dict
# nuevo en cada request, así que esto pasaba en producción, no solo en un
# test con muchos escenarios efímeros.
#
# `Scenario` hereda de `dict` en vez de envolverlo con `__getitem__`: así es
# un diccionario de verdad (`isinstance(x, dict)`, `.get()`, `in`, JSON, todo
# funciona sin reimplementar nada) con un atributo de más. `agent.solve()` lo
# construye una vez al entrar y todo el agente lo usa de ahí en adelante —
# cada búsqueda tiene su propio índice, sin nada compartido entre requests.


def _build_index(data: dict[str, Any]) -> dict[str, dict[str, int]]:
    return {
        "door": {d["id"]: i for i, d in enumerate(data["doors"])},
        "panel": {p["id"]: i for i, p in enumerate(data["panels"])},
        "station": {s["id"]: i for i, s in enumerate(data["stations"])},
    }


class Scenario(dict):
    __slots__ = ("index",)

    def __init__(self, data: dict[str, Any]) -> None:
        super().__init__(data)
        self.index = _build_index(self)


def _index(scenario: dict[str, Any]) -> dict[str, dict[str, int]]:
    # Los tests llaman a veces estas funciones con un dict pelado (sin pasar
    # por agent.solve()): sigue funcionando, solo que sin la ventaja de
    # calcularlo una sola vez.
    if isinstance(scenario, Scenario):
        return scenario.index
    return _build_index(scenario)


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
