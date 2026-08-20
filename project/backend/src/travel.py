"""MOVE compuesto: salto directo a la zona más cercana con algo que hacer.

MOVE no depende de nada más que el corredor (hecho verificado #2 en
design.md, "Applicable interno vs legalidad del contrato"). Entre dos
paradas donde el robot hace algo (PICKUP/DROP/INTERACT), ningún plan óptimo
se beneficia de deambular: mientras las puertas abiertas no cambien a mitad
de camino —y no cambian, porque abrir una puerta es en sí mismo una parada—
el camino más barato hacia la próxima parada es siempre al menos tan bueno
como cualquier rodeo. Comprimo esos tramos en un solo sucesor con el mismo
argumento de intercambio que uso para restringir DROP, aplicado a MOVE: sin
esto, la búsqueda pierde tiempo probando cada orden posible de deambular
entre las 5 zonas antes de llegar a donde importa.

El plan que sale de `/api/solve` no ve este salto: `translate.py` lo
reexpande en los MOVE de un solo corredor que trae `hops`.
"""

from __future__ import annotations

import heapq
from typing import Any, Iterator

from internal_action import InternalAction
from scenario import corridors_from, door_open, panel_ok, station_online
from state import State


def zones_of_interest(scenario: dict[str, Any], state: State) -> set[str]:
    zones: set[str] = set()
    for _kid, z in state.keys_ground:
        zones.add(z)
    for _tid, z in state.tools_ground:
        zones.add(z)
    for _mtype, z, count in state.materials_ground:
        if count > 0:
            zones.add(z)

    for d in scenario["doors"]:
        if not door_open(scenario, state.doors_open, d["id"]) and d["key"] in state.keys_carried:
            zones.update(d["between"])

    carried_materials = dict(state.materials_carried)
    for p in scenario["panels"]:
        if panel_ok(scenario, state.panels_ok, p["id"]):
            continue
        req = p["requires"]
        if req["tool"] in state.tools_carried and carried_materials.get(req["material"], 0) > 0:
            zones.add(p["zone"])

    for s in scenario["stations"]:
        if station_online(scenario, state.stations_online, s["id"]):
            continue
        req = s["requires"]
        if all(
            panel_ok(scenario, state.panels_ok, pid) for pid in req.get("panels_ok", [])
        ) and all(
            station_online(scenario, state.stations_online, sid)
            for sid in req.get("stations_online", [])
        ):
            zones.add(s["zone"])

    if state.battery < scenario["robot"]["battery_max"]:
        for c in scenario["chargers"]:
            zones.add(c["zone"])

    zones.discard(state.zone)
    return zones


def _dijkstra(
    scenario: dict[str, Any], start_zone: str, doors_open_mask: int
) -> tuple[dict[str, int], dict[str, tuple[str, str, int]]]:
    dist: dict[str, int] = {start_zone: 0}
    hop: dict[str, tuple[str, str, int]] = {}
    pending: list[tuple[int, str]] = [(0, start_zone)]
    while pending:
        d, z = heapq.heappop(pending)
        if d > dist[z]:
            continue
        for c in corridors_from(scenario, z):
            if c.get("door") and not door_open(scenario, doors_open_mask, c["door"]):
                continue
            nd = d + int(c["cost"])
            if nd < dist.get(c["to"], float("inf")):
                dist[c["to"]] = nd
                hop[c["to"]] = (z, c["to"], int(c["cost"]))
                heapq.heappush(pending, (nd, c["to"]))
    return dist, hop


def _path_hops(
    hop: dict[str, tuple[str, str, int]], start_zone: str, target_zone: str
) -> tuple[tuple[str, str, int], ...]:
    hops: list[tuple[str, str, int]] = []
    z = target_zone
    while z != start_zone:
        frm, to, cost = hop[z]
        hops.append((frm, to, cost))
        z = frm
    hops.reverse()
    return tuple(hops)


def travel_successors(
    scenario: dict[str, Any],
    state: State,
    path_cache: dict[tuple[str, int], tuple[dict[str, int], dict[str, tuple[str, str, int]]]],
) -> Iterator[tuple[InternalAction, State]]:
    targets = zones_of_interest(scenario, state)
    if not targets:
        return

    cache_key = (state.zone, state.doors_open)
    cached = path_cache.get(cache_key)
    if cached is None:
        cached = _dijkstra(scenario, state.zone, state.doors_open)
        path_cache[cache_key] = cached
    dist, hop = cached

    for z in targets:
        cost = dist.get(z)
        if cost is None or state.battery < cost:
            continue
        hops = _path_hops(hop, state.zone, z)
        # Solo cambian zona y batería: nada de lo que build_state() filtraría
        # (doors_open/panels_ok) se mueve en un tramo de puro viaje.
        nxt = state._replace(zone=z, battery=state.battery - cost)
        yield InternalAction("MOVE_TO", z, hops, cost), nxt
