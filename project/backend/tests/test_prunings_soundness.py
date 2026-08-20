"""Ninguna poda puede cambiar el costo óptimo. Una poda solo quita
sucesores, nunca añade uno — si alguna se comiera el plan óptimo, el modo
con podas devolvería un costo **mayor** que el ingenuo (o perdería una
solución que sí existe), nunca uno menor: cualquier plan que devuelve
`solve()` es legal y el simulador lo valida. Que el costo coincida en muchas
instancias es evidencia empírica, no una demostración general — la garantía
general es el argumento de intercambio de design.md. Si se agrega una quinta
poda, estos tests la vigilan sola.

Cuatro capas:

1. `mini_pruning_check.json` y `mini_weight_guard_check.json`: instancias de
   mano, diseñadas para forzar que `SWAP`/preferencia de muerto/`MOVE_TO`/
   `zones_of_interest` disparen de verdad (no un caso vacío).
2. 30 instancias generadas al azar con solución + 10 sin ella, semilla fija.
   Varían zonas, corredores y costos, puertas, capacidad, batería inicial y
   el peso de los objetos (1 a 3) — la condición exacta de la que depende la
   preferencia de muerto sobre vivo. La mitad de las instancias con solución
   ponen una puerta sobre una arista del árbol de expansión (no un atajo):
   cruzarla es obligatorio y su llave siempre está del lado alcanzable sin
   cruzarla, así que la instancia sigue teniendo solución y de verdad ejercita
   la vivacidad de llaves — sin esto, ninguna de las 30 obligaba a recoger
   una llave y dejarla morir.
3. Un tercer modo, `weight_blind`, que deja todo encendido salvo la
   condición de peso de la preferencia de muerto — para demostrar (no solo
   afirmar) si esa condición muerde en algún caso concreto.

Comparo siempre contra `fully_naive=True` para (1) y (2): apaga también las
tres podas fundacionales (DROP solo si bloquea, objetos muertos fuera del
estado, dominancia de batería), no solo las cuatro opcionales — esas tres
son el centro del parcial y necesitan la misma validación empírica.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from agent import solve  # noqa: E402
from simulator import goal_satisfied, simulate  # noqa: E402

SCENARIOS_DIR = ROOT.parent / "scenarios"
RANDOM_SEED = 20260819
TARGET_SOLVABLE = 30
TARGET_UNSOLVABLE = 10
MAX_ATTEMPTS = 400


def _load_scenario(name: str) -> dict:
    with (SCENARIOS_DIR / name).open(encoding="utf-8") as f:
        return json.load(f)


def _assert_same_outcome(scenario: dict) -> None:
    with_prunings = solve(scenario)
    without_prunings = solve(scenario, fully_naive=True)

    assert with_prunings["solution_found"] == without_prunings["solution_found"], (
        "podadas y sin podar no coinciden en si hay solución"
    )
    if with_prunings["solution_found"]:
        assert with_prunings["total_cost"] == without_prunings["total_cost"], (
            f"costo óptimo distinto: podadas={with_prunings['total_cost']} "
            f"sin podar={without_prunings['total_cost']}"
        )


def test_mini_pruning_check_matches_fully_naive() -> None:
    _assert_same_outcome(_load_scenario("mini_pruning_check.json"))


def test_mini_weight_guard_check_matches_fully_naive() -> None:
    _assert_same_outcome(_load_scenario("mini_weight_guard_check.json"))


def test_both_modes_agree_on_both_fixed_instances_and_pass_simulator() -> None:
    for name in ("mini_pruning_check.json", "mini_weight_guard_check.json"):
        scenario = _load_scenario(name)
        for fully_naive in (False, True):
            result = solve(scenario, fully_naive=fully_naive)
            assert result["solution_found"] is True
            final = simulate(scenario, result["steps"])
            assert goal_satisfied(scenario, final)
            assert final["energy_spent"] == result["total_cost"]


def _subtree_nodes(tree_edges: list[tuple[str, str]], root: str) -> set[str]:
    children: dict[str, list[str]] = {}
    for p, c in tree_edges:
        children.setdefault(p, []).append(c)
    result: set[str] = set()
    stack = [root]
    while stack:
        n = stack.pop()
        if n in result:
            continue
        result.add(n)
        stack.extend(children.get(n, []))
    return result


def _build_random_scenario(rng: random.Random, force_mandatory_door: bool) -> dict:
    n_zones = rng.randint(3, 4)
    zone_ids = [f"Z{i + 1}" for i in range(n_zones)]

    # El árbol de expansión garantiza que toda zona es alcanzable desde el
    # arranque. Las aristas extra (atajos) llevan puertas al azar, siempre
    # opcionales — no obligan a recoger ninguna llave por sí solas.
    tree_edges: list[tuple[str, str]] = []
    connected = [zone_ids[0]]
    remaining = zone_ids[1:]
    rng.shuffle(remaining)
    for z in remaining:
        other = rng.choice(connected)
        tree_edges.append((other, z))
        connected.append(z)

    extra_edges: list[tuple[str, str]] = []
    for _ in range(rng.randint(0, 1)):
        a, b = rng.sample(zone_ids, 2)
        if (a, b) not in tree_edges and (b, a) not in tree_edges and (a, b) not in extra_edges:
            extra_edges.append((a, b))

    # Puerta obligatoria: una arista del propio árbol. Cruzarla dejar de ser
    # opcional, y la llave siempre queda del lado alcanzable sin cruzarla —
    # así la instancia sigue teniendo solución y de verdad obliga a recoger
    # la llave, abrir y dejarla morir. Sin esto ninguna instancia ejercita
    # la vivacidad de llaves (poda fundacional de Relevancia).
    mandatory_edge_idx = None
    far_side: set[str] = set()
    near_side: set[str] = set(zone_ids)
    if force_mandatory_door:
        mandatory_edge_idx = rng.randrange(len(tree_edges))
        _parent, child = tree_edges[mandatory_edge_idx]
        far_side = _subtree_nodes(tree_edges, child)
        near_side = set(zone_ids) - far_side

    doors: list[dict] = []
    corridors: list[dict] = []
    keys: list[dict] = []
    for idx, (a, b) in enumerate(tree_edges):
        cost = rng.randint(2, 8)
        if idx == mandatory_edge_idx:
            door_id, key_id = "DOOR_MANDATORY", "KEY_MANDATORY"
            doors.append({"id": door_id, "color": "x", "key": key_id, "state": "CLOSED", "between": [a, b]})
            keys.append(
                {"id": key_id, "color": "x", "zone": rng.choice(sorted(near_side)), "weight": rng.randint(1, 3)}
            )
            corridors.append({"from": a, "to": b, "cost": cost, "door": door_id})
            corridors.append({"from": b, "to": a, "cost": cost, "door": door_id})
        else:
            corridors.append({"from": a, "to": b, "cost": cost, "door": None})
            corridors.append({"from": b, "to": a, "cost": cost, "door": None})
    for a, b in extra_edges:
        cost = rng.randint(2, 8)
        door_id, key_id = f"DOOR{len(doors) + 1}", f"KEY{len(doors) + 1}"
        doors.append({"id": door_id, "color": "x", "key": key_id, "state": "CLOSED", "between": [a, b]})
        keys.append({"id": key_id, "color": "x", "zone": rng.choice(zone_ids), "weight": rng.randint(1, 3)})
        corridors.append({"from": a, "to": b, "cost": cost, "door": door_id})
        corridors.append({"from": b, "to": a, "cost": cost, "door": door_id})

    # Con puerta obligatoria, la tarea vive del lado lejano: cruzar deja de
    # ser una opción, es la única manera de llegar a la meta.
    task_zone_pool = sorted(far_side) if force_mandatory_door else zone_ids

    damage = "D1"
    tools = [{"id": "TOOL1", "repairs": damage, "zone": rng.choice(task_zone_pool), "weight": rng.randint(1, 3)}]
    materials = [
        {"type": "MAT1", "zone": rng.choice(task_zone_pool), "count": rng.randint(1, 2), "weight": rng.randint(1, 3)}
    ]
    panels = [
        {
            "id": "PANEL1",
            "zone": rng.choice(task_zone_pool),
            "damage": damage,
            "requires": {"tool": "TOOL1", "material": "MAT1"},
            "state": "DAMAGED",
        }
    ]
    stations = [
        {
            "id": "STATION1",
            "kind": "generic",
            "zone": rng.choice(task_zone_pool),
            "state": "OFFLINE",
            "requires": {"panels_ok": ["PANEL1"]},
        }
    ]

    chargers = []
    if rng.random() < 0.3:
        chargers.append({"id": "CHARGER1", "zone": rng.choice(zone_ids)})

    cargo_capacity = rng.randint(3, 6)
    battery_max = rng.randint(30, 90)
    battery_start = rng.randint(max(10, int(battery_max * 0.7)), battery_max)

    return {
        "meta": {"id": "random", "title": "random", "description": "generado por test_prunings_soundness"},
        "robot": {
            "start": zone_ids[0],
            "battery_max": battery_max,
            "battery_start": battery_start,
            "cargo_capacity": cargo_capacity,
        },
        "zones": [{"id": z, "name": z, "recharge": False} for z in zone_ids],
        "corridors": corridors,
        "doors": doors,
        "keys": keys,
        "tools": tools,
        "materials": materials,
        "panels": panels,
        "stations": stations,
        "chargers": chargers,
        "goal": {"stations_online": [s["id"] for s in stations]},
        "action_costs": {"pickup": 1, "drop": 1, "interact": 2, "recharge": 3},
    }


def test_random_instances_match_fully_naive_and_weight_blind() -> None:
    # `weight_blind` corre sobre las mismas 30 instancias con solución que
    # `fully_naive`, no en una prueba aparte: son 30 intentos de encontrar el
    # contraejemplo que tres construcciones a mano no encontraron, casi
    # gratis porque el escenario ya se generó para lo otro. `blind_cost >=
    # normal_cost` es una garantía comprobable siempre (weight_blind explora
    # un subconjunto de lo que explora el modo correcto, nunca puede hacerlo
    # mejor); una desigualdad estricta sería el contraejemplo que se buscó a
    # mano y no apareció — si alguna vez aparece acá, es un hallazgo real.
    rng = random.Random(RANDOM_SEED)
    solvable = 0
    unsolvable = 0
    attempts = 0
    strict_gaps: list[tuple[int, int, int]] = []

    while (solvable < TARGET_SOLVABLE or unsolvable < TARGET_UNSOLVABLE) and attempts < MAX_ATTEMPTS:
        force_door = attempts % 2 == 0
        scenario = _build_random_scenario(rng, force_door)
        attempts += 1

        with_prunings = solve(scenario)
        without_prunings = solve(scenario, fully_naive=True)

        assert with_prunings["solution_found"] == without_prunings["solution_found"], (
            f"intento {attempts} (semilla {RANDOM_SEED}): podadas y sin podar no "
            f"coinciden en si hay solución"
        )
        if with_prunings["solution_found"]:
            if solvable < TARGET_SOLVABLE:
                solvable += 1
                assert with_prunings["total_cost"] == without_prunings["total_cost"], (
                    f"intento {attempts} (semilla {RANDOM_SEED}): costo óptimo distinto: "
                    f"podadas={with_prunings['total_cost']} sin podar={without_prunings['total_cost']}"
                )

                blind = solve(scenario, weight_blind=True)
                assert blind["solution_found"] is True
                assert blind["total_cost"] >= with_prunings["total_cost"], (
                    f"intento {attempts} (semilla {RANDOM_SEED}): weight_blind dio costo MENOR "
                    f"({blind['total_cost']}) que el modo correcto ({with_prunings['total_cost']}) "
                    f"— imposible, revisar _drop_candidates"
                )
                if blind["total_cost"] > with_prunings["total_cost"]:
                    strict_gaps.append((attempts, with_prunings["total_cost"], blind["total_cost"]))
        elif unsolvable < TARGET_UNSOLVABLE:
            unsolvable += 1

    assert solvable >= TARGET_SOLVABLE, f"solo {solvable} instancias con solución en {attempts} intentos"
    assert unsolvable >= TARGET_UNSOLVABLE, f"solo {unsolvable} instancias sin solución en {attempts} intentos"

    if strict_gaps:
        print(f"weight_blind: {len(strict_gaps)} instancia(s) con costo estrictamente mayor:")
        for attempt, normal_cost, blind_cost in strict_gaps:
            print(f"  intento {attempt}: correcto={normal_cost} weight_blind={blind_cost}")
    else:
        print(f"weight_blind: sin divergencia en las {solvable} instancias con solución (semilla {RANDOM_SEED})")


def test_weight_blind_mode_agrees_on_fixed_instances() -> None:
    for name in ("mini_pruning_check.json", "mini_weight_guard_check.json"):
        scenario = _load_scenario(name)
        normal = solve(scenario)
        blind = solve(scenario, weight_blind=True)
        assert blind["solution_found"] == normal["solution_found"]
        if normal["solution_found"]:
            assert blind["total_cost"] >= normal["total_cost"], (
                f"{name}: weight_blind encontró un plan MÁS BARATO que el modo correcto "
                f"({blind['total_cost']} < {normal['total_cost']}) — eso no debería poder "
                f"pasar nunca, revisar _drop_candidates"
            )


if __name__ == "__main__":
    test_mini_pruning_check_matches_fully_naive()
    test_mini_weight_guard_check_matches_fully_naive()
    test_both_modes_agree_on_both_fixed_instances_and_pass_simulator()
    test_weight_blind_mode_agrees_on_fixed_instances()
    test_random_instances_match_fully_naive_and_weight_blind()
    print("All pruning-soundness tests passed.")
