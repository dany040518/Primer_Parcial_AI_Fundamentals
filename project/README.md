# Proyecto — Emergency Control

El diseño del agente está en [`design.md`](design.md): estado, acciones, `DROP`,
batería, tamaño del espacio, con el argumento de por qué cada poda no pierde el
óptimo. El enunciado completo está en el `README.MD` de la raíz; las reglas del
mundo, en [`../CONTRATO.md`](../CONTRATO.md).

Instrucciones para Linux — es lo que uso.

## Estructura

```text
project/
├── frontend/          # React + R3F — simulación 3D voxel
├── backend/
│   └── src/
│       ├── scenario.py       # consultas sobre el escenario crudo
│       ├── state.py          # estado canónico de búsqueda
│       ├── successors.py     # Applicable(s) y Result(s, a)
│       ├── travel.py         # MOVE compuesto (zones_of_interest, Dijkstra)
│       ├── ucs.py            # UCS en grafo, dominancia de batería
│       ├── translate.py      # acciones internas -> contrato
│       ├── agent.py          # solve(scenario) -> plan
│       ├── demo_plan.py      # plan artesanal del profesor (sin usar, no se borró)
│       └── main.py           # FastAPI, POST /api/solve
├── scenarios/
│   ├── scenario.json          # instancia del profesor — no se toca
│   └── mini_*.json            # instancias propias para los tests
├── design.md
└── README.md
```

## 1. Instalar dependencias

Backend:

```bash
cd project/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Frontend:

```bash
cd project/frontend
npm install
```

Todo el backend es librería estándar de Python más FastAPI/uvicorn — no hay
dependencias nuevas para el agente en sí.

## 2. Levantar el backend

```bash
cd project/backend
source .venv/bin/activate
uvicorn main:app --reload --app-dir src --port 8000
```

Comprobar: `curl http://127.0.0.1:8000/api/health` → `{"status":"ok"}`

## 3. Levantar el frontend

En otra terminal:

```bash
cd project/frontend
npm run dev
```

Abrir http://localhost:5173 — el frontend llama a `/api/solve` a través del
proxy de Vite hacia el puerto 8000.

## 4. Correr el agente / probar una misión

`POST /api/solve` ya no devuelve el plan demo: resuelve con el agente de
`agent.py` (UCS en grafo sobre el estado canónico de `state.py`). El plan
demo de `demo_plan.py` sigue en el repo pero el endpoint no lo llama.

**Desde el navegador:** con las dos terminales corriendo, entrar a
http://localhost:5173 y pulsar **EXECUTE PLAN**. El frontend pide el plan al
backend y lo reproduce casilla a casilla sobre `scenario.json`.

**Desde la terminal**, sin el frontend, contra cualquier escenario:

```bash
curl -s -X POST http://127.0.0.1:8000/api/solve \
  -H "Content-Type: application/json" \
  --data-binary @project/scenarios/scenario.json | python3 -m json.tool
```

Cambiar el archivo de `--data-binary` por cualquiera de `project/scenarios/mini_*.json`
prueba el agente contra una instancia distinta, no solo la demo.

## 5. Leer el resultado

La respuesta de `/api/solve`:

```json
{
  "solution_found": true,
  "total_cost": 80,
  "steps": [ { "op": "MOVE", "from": "Z1", "to": "Z2", "cost": 4 }, ... ],
  "message": "UCS: 35 pasos, costo 80"
}
```

- `solution_found`: si existe plan para esta instancia. En `false`, `steps`
  viene vacío y no hay que buscar nada más ahí — es el caso `FAILURE`.
- `total_cost`: suma de los `cost` de cada paso, con los valores oficiales
  del escenario recibido (nunca inventados).
- `steps`: el plan traducido al contrato — solo `MOVE`/`PICKUP`/`DROP`/
  `INTERACT`, cada uno con su `cost`.

En el frontend, el panel lateral muestra batería, posición, el log paso a
paso (cada `INTERACT` incluye su `action`) y el costo acumulado mientras se
reproduce el plan.

## 6. Correr los tests

```bash
cd project/backend
source .venv/bin/activate
for f in tests/test_*.py; do python3 "$f"; done
```

O uno por uno:

```bash
python3 tests/test_demo_plan.py                    # plan demo del profesor sigue siendo legal
python3 tests/test_case1_state_equivalence.py       # estados equivalentes por distinto orden de recolección
python3 tests/test_case2_state_relevance.py         # info relevante (puerta, batería) mantiene estados distintos
python3 tests/test_case3_steps_vs_cost.py           # menos pasos no es menor costo
python3 tests/test_case4_failure.py                 # sin solución -> FAILURE, sin quedarse explorando
python3 tests/test_case5_alternative_routes.py      # entre rutas alternativas, se queda con la barata
python3 tests/test_scenario_index_isolation.py      # dos escenarios distintos resueltos seguidos no se mezclan
python3 tests/test_prunings_soundness.py            # las podas no cambian el costo óptimo (~40 instancias, ~20s)
```

No usan pytest — son scripts que corren sus propios `assert` y terminan con
`print(...)`/`AssertionError`, siguiendo el patrón de `test_demo_plan.py`.

## Contrato visual vs agente (importante)

La versión oficial y completa de este contrato (esquema JSON, acciones de
`INTERACT`, reglas del mundo y costos) está en `../CONTRATO.md`, que forma
parte del enunciado.

El enunciado fija **4 operaciones visuales** que el frontend entiende:

```text
MOVE | PICKUP | DROP | INTERACT
```

`REPAIR`, `ACTIVATE`, `OPEN_DOOR`, `RECHARGE` **no son ops del plan de alto
nivel**: son el campo `action` dentro de un paso `INTERACT`.

```json
{ "op": "INTERACT", "target": "PANEL_A", "action": "REPAIR", "consumes": "FUSE", "cost": 2 }
```

El agente modela internamente acciones propias (`PICKUP_KEY`, `SWAP`,
`MOVE_TO`, etc. — ver `design.md`) y `translate.py` las traduce a estas 4
antes de que salgan de `/api/solve`. El frontend / banco de pruebas solo
ejecuta esas 4 ops; nunca ve los nombres internos.
