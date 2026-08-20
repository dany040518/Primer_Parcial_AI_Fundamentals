"""Applicable(s) y Result(s, a).

Genero menos de lo que CONTRATO.md permitiría. La regla de DROP, el filtro de
objetos vivos, el MOVE compuesto (ver travel.py) y el SWAP acotado están
justificados con argumento de intercambio en design.md, sección "Applicable
interno vs legalidad del contrato" — esta función es la única que decide qué
es un sucesor; nada más en el agente vuelve a tocarlo.
"""

from __future__ import annotations

from typing import Any, Iterator

from internal_action import InternalAction
from scenario import (
    chargers_at,
    door_open,
    key_is_live,
    key_weight,
    material_weight,
    needed_material_count,
    panel_ok,
    station_online,
    tool_is_live,
    tool_weight,
    with_door_open,
    with_panel_ok,
    with_station_online,
)
from state import State, build_state, carried_weight
from travel import naive_move_successors, travel_successors


def _ground_dicts(
    state: State,
) -> tuple[dict[str, str], dict[str, str], dict[tuple[str, str], int]]:
    keys_ground = dict(state.keys_ground)
    tools_ground = dict(state.tools_ground)
    materials_ground = {(t, z): c for t, z, c in state.materials_ground}
    return keys_ground, tools_ground, materials_ground


def _blockers(scenario: dict[str, Any], state: State) -> list[tuple[str, str, int]]:
    # Objetos vivos en el suelo de esta zona que no caben con lo que cargo
    # ahora. Fuera de esta lista, soltar es un paseo, no una decisión.
    cap = scenario["robot"]["cargo_capacity"]
    current = carried_weight(scenario, state)
    out: list[tuple[str, str, int]] = []
    for kid, z in state.keys_ground:
        if z != state.zone:
            continue
        w = key_weight(scenario, kid)
        if current + w > cap:
            out.append(("key", kid, w))
    for tid, z in state.tools_ground:
        if z != state.zone:
            continue
        w = tool_weight(scenario, tid)
        if current + w > cap:
            out.append(("tool", tid, w))
    for t, z, c in state.materials_ground:
        if z != state.zone or c <= 0:
            continue
        w = material_weight(scenario, t)
        if current + w > cap:
            out.append(("material", t, w))
    return out


def _carried_candidates(scenario: dict[str, Any], state: State) -> list[tuple[str, str, int]]:
    out: list[tuple[str, str, int]] = []
    for kid in state.keys_carried:
        out.append(("key", kid, key_weight(scenario, kid)))
    for tid in state.tools_carried:
        out.append(("tool", tid, tool_weight(scenario, tid)))
    for mtype, count in state.materials_carried:
        if count > 0:
            out.append(("material", mtype, material_weight(scenario, mtype)))
    return out


def _is_dead_carried(scenario: dict[str, Any], state: State, kind: str, ident: str) -> bool:
    if kind == "key":
        return not key_is_live(scenario, ident, state.doors_open)
    if kind == "tool":
        return not tool_is_live(scenario, ident, state.panels_ok)
    return False  # un material cargado nunca sobra: PICKUP_MATERIAL ya lo impide


def _drop_candidates(
    scenario: dict[str, Any],
    state: State,
    candidates: list[tuple[str, str, int]],
    naive: bool,
    weight_blind: bool = False,
) -> list[tuple[str, str, int]]:
    # Entre lo que cargo, prefiero soltar un muerto — nunca vuelve a hacer
    # falta — pero solo si pesa al menos lo que pesa cada vivo que me quedo
    # cargando: si el vivo pesara más, quedármelo en vez del muerto puede
    # tumbar un PICKUP posterior que sí pasaba en el plan original, no solo
    # encarecerlo. Ver design.md, "Applicable interno vs legalidad del
    # contrato". `naive=True` la apaga del todo (test de solidez de podas).
    # `weight_blind=True` deja la preferencia puesta pero sin la condición
    # de peso — la versión ingenua que restringe a los muertos sin comparar
    # cuánto pesan los vivos que se queda cargando. Existe solo para medir
    # contra ella en test_prunings_soundness.py.
    if naive:
        return candidates
    dead = [c for c in candidates if _is_dead_carried(scenario, state, c[0], c[1])]
    if not dead:
        return candidates
    if weight_blind:
        return dead
    live = [c for c in candidates if c not in dead]
    max_live_weight = max((w for _, _, w in live), default=0)
    safe_dead = [c for c in dead if c[2] >= max_live_weight]
    return safe_dead if safe_dead else candidates


def local_successors(
    scenario: dict[str, Any],
    state: State,
    naive: bool = False,
    fully_naive: bool = False,
    weight_blind: bool = False,
) -> Iterator[tuple[InternalAction, State]]:
    bat_max = scenario["robot"]["battery_max"]
    cap = scenario["robot"]["cargo_capacity"]
    keys_ground, tools_ground, materials_ground = _ground_dicts(state)
    materials_carried = dict(state.materials_carried)

    def make_next(**over: Any) -> State:
        fields: dict[str, Any] = dict(
            zone=state.zone,
            battery=state.battery,
            keys_carried=state.keys_carried,
            tools_carried=state.tools_carried,
            materials_carried=materials_carried,
            keys_ground=keys_ground,
            tools_ground=tools_ground,
            materials_ground=materials_ground,
            doors_open=state.doors_open,
            panels_ok=state.panels_ok,
            stations_online=state.stations_online,
        )
        fields.update(over)
        # Filtrar de nuevo solo tiene sentido si cambió lo que decide
        # vivacidad: puertas para llaves, paneles (o cuánto material cargo)
        # para herramientas y materiales. Ver el comentario en build_state.
        # `fully_naive` apaga el filtro entero (test_prunings_soundness.py):
        # rastrea objetos muertos y material de sobra a propósito.
        panels_changed = "panels_ok" in over
        return build_state(
            scenario,
            doors_changed="doors_open" in over,
            panels_changed=panels_changed,
            materials_recompute=panels_changed or "materials_carried" in over,
            relevance_filter=not fully_naive,
            **fields,
        )

    pickup_cost = int(scenario["action_costs"]["pickup"])
    current_weight = carried_weight(scenario, state)

    for kid, z in state.keys_ground:
        if z != state.zone or state.battery < pickup_cost:
            continue
        if current_weight + key_weight(scenario, kid) > cap:
            continue
        new_ground = dict(keys_ground)
        del new_ground[kid]
        nxt = make_next(
            battery=state.battery - pickup_cost,
            keys_carried=state.keys_carried | {kid},
            keys_ground=new_ground,
        )
        yield InternalAction("PICKUP_KEY", kid, None, pickup_cost), nxt

    for tid, z in state.tools_ground:
        if z != state.zone or state.battery < pickup_cost:
            continue
        if current_weight + tool_weight(scenario, tid) > cap:
            continue
        new_ground = dict(tools_ground)
        del new_ground[tid]
        nxt = make_next(
            battery=state.battery - pickup_cost,
            tools_carried=state.tools_carried | {tid},
            tools_ground=new_ground,
        )
        yield InternalAction("PICKUP_TOOL", tid, None, pickup_cost), nxt

    for mtype, z, count in state.materials_ground:
        if z != state.zone or count <= 0 or state.battery < pickup_cost:
            continue
        already = materials_carried.get(mtype, 0)
        if not fully_naive and already >= needed_material_count(scenario, mtype, state.panels_ok):
            continue
        if current_weight + material_weight(scenario, mtype) > cap:
            continue
        new_ground = dict(materials_ground)
        new_ground[(mtype, z)] = new_ground.get((mtype, z), 0) - 1
        new_carried = dict(materials_carried)
        new_carried[mtype] = already + 1
        nxt = make_next(
            battery=state.battery - pickup_cost,
            materials_carried=new_carried,
            materials_ground=new_ground,
        )
        yield InternalAction("PICKUP_MATERIAL", mtype, None, pickup_cost), nxt

    drop_cost = int(scenario["action_costs"]["drop"])
    blockers = _blockers(scenario, state)

    def apply_drop(over: dict[str, Any], kind: str, ident: str) -> None:
        if kind == "key":
            over["keys_carried"] = over.get("keys_carried", state.keys_carried) - {ident}
            if fully_naive or key_is_live(scenario, ident, state.doors_open):
                g = dict(over.get("keys_ground", keys_ground))
                g[ident] = state.zone
                over["keys_ground"] = g
            # si está muerta, ni la agrego al suelo: nunca se vuelve a
            # consultar (Relevancia), y así build_state no necesita
            # volver a filtrarla la próxima vez. `fully_naive` la fuerza a
            # trackearse igual, a propósito, para el test de solidez.
        elif kind == "tool":
            over["tools_carried"] = over.get("tools_carried", state.tools_carried) - {ident}
            if fully_naive or tool_is_live(scenario, ident, state.panels_ok):
                g = dict(over.get("tools_ground", tools_ground))
                g[ident] = state.zone
                over["tools_ground"] = g
        else:
            g = dict(over.get("materials_ground", materials_ground))
            g[(ident, state.zone)] = g.get((ident, state.zone), 0) + 1
            over["materials_ground"] = g
            mc = dict(over.get("materials_carried", materials_carried))
            mc[ident] = mc.get(ident, 0) - 1
            over["materials_carried"] = mc

    if fully_naive:
        # Sin la poda fundacional de DROP: cualquier objeto cargado se puede
        # soltar en cualquier estado, esté bloqueada o no. Es exactamente lo
        # que design.md describe como el generador ingenuo que explota — se
        # deja aquí solo para medir contra él, no para usarlo en producción.
        if state.battery >= drop_cost:
            for kind_x, ident_x, _w_x in _carried_candidates(scenario, state):
                over: dict[str, Any] = {}
                apply_drop(over, kind_x, ident_x)
                nxt = make_next(battery=state.battery - drop_cost, **over)
                yield InternalAction("DROP", ident_x, None, drop_cost), nxt
    elif blockers and state.battery >= drop_cost:

        def apply_pickup(over: dict[str, Any], kind: str, ident: str) -> None:
            if kind == "key":
                g = dict(over.get("keys_ground", keys_ground))
                del g[ident]
                over["keys_ground"] = g
                over["keys_carried"] = over.get("keys_carried", state.keys_carried) | {ident}
            elif kind == "tool":
                g = dict(over.get("tools_ground", tools_ground))
                del g[ident]
                over["tools_ground"] = g
                over["tools_carried"] = over.get("tools_carried", state.tools_carried) | {ident}
            else:
                g = dict(over.get("materials_ground", materials_ground))
                g[(ident, state.zone)] = g.get((ident, state.zone), 0) - 1
                over["materials_ground"] = g
                mc = dict(over.get("materials_carried", materials_carried))
                mc[ident] = mc.get(ident, 0) + 1
                over["materials_carried"] = mc

        candidates = _carried_candidates(scenario, state)
        drop_candidates = _drop_candidates(scenario, state, candidates, naive, weight_blind)

        if naive:
            # Sin SWAP: cada DROP es su propio sucesor, sin fusionar con el
            # PICKUP que lo motivó. Sigue restringido a "estoy bloqueada"
            # (esa poda no es de las opcionales) — pero explora el estado
            # intermedio "ya solté, todavía no recogí" que SWAP se salta.
            for kind_x, ident_x, _w_x in drop_candidates:
                over: dict[str, Any] = {}
                apply_drop(over, kind_x, ident_x)
                nxt = make_next(battery=state.battery - drop_cost, **over)
                yield InternalAction("DROP", ident_x, None, drop_cost), nxt
        else:
            multi_drop_needed = False

            # SWAP(x, y): suelto x y recojo y en un solo sucesor cuando soltar
            # un solo x ya libera lo que y necesita — es la forma canónica de
            # todo DROP que genero (design.md: siempre pegado al PICKUP que lo
            # pide), así que fusionarlos no pierde ningún plan, solo salta el
            # estado intermedio. Cuando ningún x solo alcanza (y pesa más de
            # lo que cualquier candidato libera), me falta más de un DROP —
            # ahí caigo al DROP suelto para ir liberando peso de a poco.
            for kind_y, ident_y, w_y in blockers:
                deficit = current_weight + w_y - cap
                eligible = [c for c in drop_candidates if c[2] >= deficit]
                if not eligible:
                    multi_drop_needed = True
                    continue
                for kind_x, ident_x, _w_x in eligible:
                    if kind_x == kind_y == "material" and ident_x == ident_y:
                        continue
                    over = {}
                    apply_drop(over, kind_x, ident_x)
                    apply_pickup(over, kind_y, ident_y)
                    nxt = make_next(battery=state.battery - drop_cost - pickup_cost, **over)
                    extra = (ident_x, drop_cost, pickup_cost)
                    yield InternalAction("SWAP", ident_y, extra, drop_cost + pickup_cost), nxt

            if multi_drop_needed:
                for kind_x, ident_x, _w_x in drop_candidates:
                    over = {}
                    apply_drop(over, kind_x, ident_x)
                    nxt = make_next(battery=state.battery - drop_cost, **over)
                    yield InternalAction("DROP", ident_x, None, drop_cost), nxt

    interact_cost = int(scenario["action_costs"]["interact"])
    if state.battery >= interact_cost:
        for d in scenario["doors"]:
            if state.zone not in d["between"] or door_open(scenario, state.doors_open, d["id"]):
                continue
            if d["key"] not in state.keys_carried:
                continue
            nxt = make_next(
                battery=state.battery - interact_cost,
                doors_open=with_door_open(scenario, state.doors_open, d["id"]),
            )
            yield InternalAction("OPEN_DOOR", d["id"], None, interact_cost), nxt

        for p in scenario["panels"]:
            if panel_ok(scenario, state.panels_ok, p["id"]) or p["zone"] != state.zone:
                continue
            req = p["requires"]
            if req["tool"] not in state.tools_carried:
                continue
            if materials_carried.get(req["material"], 0) <= 0:
                continue
            new_carried = dict(materials_carried)
            new_carried[req["material"]] -= 1
            nxt = make_next(
                battery=state.battery - interact_cost,
                materials_carried=new_carried,
                panels_ok=with_panel_ok(scenario, state.panels_ok, p["id"]),
            )
            yield InternalAction("REPAIR", p["id"], req["material"], interact_cost), nxt

        for s in scenario["stations"]:
            if station_online(scenario, state.stations_online, s["id"]) or s["zone"] != state.zone:
                continue
            req = s["requires"]
            if not all(panel_ok(scenario, state.panels_ok, pid) for pid in req.get("panels_ok", [])):
                continue
            if not all(
                station_online(scenario, state.stations_online, sid)
                for sid in req.get("stations_online", [])
            ):
                continue
            nxt = make_next(
                battery=state.battery - interact_cost,
                stations_online=with_station_online(scenario, state.stations_online, s["id"]),
            )
            yield InternalAction("ACTIVATE", s["id"], None, interact_cost), nxt

    recharge_cost = int(scenario["action_costs"]["recharge"])
    if state.battery < bat_max and state.battery >= recharge_cost:
        for charger in chargers_at(scenario, state.zone):
            nxt = make_next(battery=bat_max)
            yield InternalAction("RECHARGE", charger["id"], None, recharge_cost), nxt


def successors(
    scenario: dict[str, Any],
    state: State,
    path_cache: dict | None = None,
    naive: bool = False,
    fully_naive: bool = False,
    weight_blind: bool = False,
) -> Iterator[tuple[InternalAction, State]]:
    # `naive=True` apaga las cuatro podas opcionales (SWAP, preferencia de
    # muerto, MOVE_TO, zones_of_interest). `fully_naive=True` apaga además
    # las tres fundacionales (DROP solo si bloquea, objetos muertos fuera del
    # estado, dominancia de batería en CLOSED — esta última la apaga
    # ucs.search, no acá). `weight_blind=True` es un tercer modo aparte: deja
    # todo encendido salvo la condición de peso dentro de la preferencia de
    # muerto (ver `_drop_candidates`) — sirve para demostrar, corriéndolo,
    # que esa condición no es cosmética. Ver test_prunings_soundness.py.
    if path_cache is None:
        path_cache = {}
    no_travel_macro = naive or fully_naive
    yield from local_successors(
        scenario, state, naive=naive, fully_naive=fully_naive, weight_blind=weight_blind
    )
    if no_travel_macro:
        yield from naive_move_successors(scenario, state)
    else:
        yield from travel_successors(scenario, state, path_cache)
