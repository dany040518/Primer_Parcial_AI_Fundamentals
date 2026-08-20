# Diseño del agente

Este documento debe completarse **antes** de la implementación principal del agente.

Use sus propias palabras y notación. No reemplace este archivo por una transcripción
del enunciado. Las subsecciones existen para que no se le olvide una decisión;
usted decide el contenido.

El entorno, según las propiedades vistas en clase, es totalmente observable,
determinista, secuencial, estático, discreto y de agente único. Bajo esas
condiciones la solución es un **plan completo** y el marco correcto es la
búsqueda clásica. Justifique cada componente con ese marco (AIMA, cap. 3).

---

## Estado

### Definición formal

Escriba la tupla de estado. Cada componente debe ser una variable que el robot
necesita para saber qué podrá hacer después.

```text
s = ⟨ zona, batería,
      payload = (llaves_cargadas, herramientas_cargadas, materiales_cargados),
      llaves_en_suelo, herramientas_en_suelo, materiales_en_suelo,
      puertas_abiertas, paneles_ok, estaciones_online ⟩
```

Donde:

- `zona`: id de la zona donde está el robot ahora. Un solo valor, no un historial.
- `batería`: entero, energía disponible ahora mismo.
- `llaves_cargadas`, `herramientas_cargadas`: conjuntos de ids que el robot lleva encima.
- `materiales_cargados`: conjunto de pares `(tipo, cantidad)` que lleva encima.
- `llaves_en_suelo`, `herramientas_en_suelo`: mapeo id → zona, pero **solo para los objetos
  que todavía importan** (ver "Relevancia" más abajo). No incluyo aquí objetos que ya
  cumplieron su función.
- `materiales_en_suelo`: mapeo tipo → conjunto de `(zona, cantidad)`, también recortado a
  lo que todavía hace falta.
- `puertas_abiertas`: conjunto de ids de puertas ya abiertas.
- `paneles_ok`: conjunto de ids de paneles ya reparados.
- `estaciones_online`: conjunto de ids de estaciones ya activadas.

No hay campo separado para "zona de cada llave sin recoger" fuera de
`llaves_en_suelo`: si una llave no está ahí y tampoco está en `llaves_cargadas`,
es porque ya es irrelevante y dejé de rastrearla (otra vez, ver "Relevancia").

### Por qué cada variable es necesaria

Criterio de clase (`Applicable`): una variable pertenece al estado **si y solo si**
dos configuraciones que difieran en ella pueden diferir en las acciones legales
futuras o en su resultado.

Pase ese filtro con cada variable. En particular:

- la **batería** forma parte de la situación física (§2.1 del enunciado);
- la **posición de los objetos** no se deduce del escenario inicial si el robot
  puede soltarlos (`DROP`);
- los cambios permanentes (puertas, paneles, estaciones) condicionan el futuro.
- **zona**: cambia qué corredores están disponibles como `MOVE`, qué hay tirado en el suelo para hacer `PICKUP`, y sobre qué puerta/panel/estación puedo actuar con `INTERACT`. Dos estados con distinta zona casi siempre difieren en sus acciones legales. Necesaria.
- **batería**: toda acción exige `batería ≥ costo`, así que el nivel determina directamente qué acciones siguen siendo legales. Además `RECHARGE` falla si la batería ya está llena, así que el valor exacto (no solo "alta/baja") importa.Necesaria.
- **llaves_cargadas\herramientas_cargadas\materiales_cargados**: `OPEN_DOOR` exige la llave en el payload; `REPAIR` exige la herramienta y el material en el payload; y el peso de lo que cargo decide si el próximo `PICKUP` cabe. Necesaria.
- **llaves_en_suelo\herramientas_en_suelo\materiales_en_suelo**: determinan si un `PICKUP` es legal en la zona actual. El escenario inicial no basta para saberlo, porque el robot puede haber soltado algo en una zona distinta a la original. Necesaria mientras el objeto siga vivo.
- **puertas_abiertas**: condiciona qué `MOVE` cruza un corredor con puerta y si `OPEN_DOOR` sigue siendo legal (falla si ya está abierta). Necesaria.
- **paneles_ok**: condiciona si `REPAIR` sigue siendo legal (falla si ya está OK) y si `ACTIVATE` de la estación que lo requiere es legal. Necesaria.
- **estaciones_online**: condiciona `ACTIVATE` de estaciones que dependen de otra (`stations_online`), condiciona si `ACTIVATE` sobre ella misma sigue siendo legal, y **es literalmente la condición de meta**. Necesaria.


### Qué información se deriva y NO se almacena

Peso de la carga, grafo de corredores, costos, capacidad, batería máxima, etc. Si se puede calcular a partir del estado y de las constantes del escenario, no es una variable de estado.

- **Peso total del payload**: sumo el peso declarado de cada objeto que cargo. No guardo un contador de peso aparte porque quedaría desincronizado en cuanto edite el payload en dos lugares distintos.
- **Vecinos de una zona**: los saco filtrando `corridors` por `from == zona`. No guardo un grafo de adyacencia propio.
- **`cargo_capacity`, `battery_max`, `action_costs`, costos de corredor**: son constantes del escenario (el entorno es estático), no varían durante la búsqueda. Los leo del JSON recibido, nunca los hardcodeo ni los copio al estado.
- **Si una acción es aplicable en `s`**: se calcula on-the-fly comparando `s` contra el escenario, no se precomputa ni se guarda una lista de "acciones disponibles" dentro del estado.

### Qué pertenece al historial de búsqueda y no al estado físico

`g(n)`, el padre y la acción que trajo aquí describen *cómo llegó*, no *dónde está*. Viven en el **Nodo**. Si se meten en el estado, CLOSED no puede reconocer la misma situación física alcanzada por dos rutas.

El **Nodo** de búsqueda es `(estado, padre, acción, g)`. `g(n)` es el costo acumulado hasta aquí, `padre` y `acción` son cómo llegué. Ninguno de los tres cambia qué puedo hacer desde `s` hacia adelante — dos robots parados en la misma zona, con la misma batería, la misma carga y el mismo entorno, tienen exactamente las mismas acciones legales sin importar si uno llegó dando un rodeo y gastó más.

La consecuencia concreta de meter `g(n)` (o el padre) dentro del estado: dos rutas que llegan a la misma configuración física casi nunca tienen el mismo costo acumulado, así que sus estados dejarían de ser iguales para `==`/hash. CLOSED nunca detectaría el duplicado, y la búsqueda re-expandiría la misma situación física una y otra vez por cada ruta distinta que llegue a ella — en un grafo con ciclos (ida y vuelta entre zonas conectadas) eso es explosión, no un caso raro.

### Cuándo dos configuraciones son el mismo estado

Materiales equivalentes por tipo (§2.2): no les ponga ids artificiales.
Estructuras canónicas (conjuntos, contadores) para que `==` y el hash coincidan con la equivalencia física.

Uso estructuras inmutables y sin orden para cada componente, de modo que el orden en que se generaron no afecte el hash:
- `llaves_cargadas`, `herramientas_cargadas`: `frozenset` de ids.
- `materiales_cargados`: `frozenset` de pares `(tipo, cantidad)` — nunca una lista de unidades individuales. Dos `FUSE` recogidos en momentos distintos son indistinguibles; solo importa cuántos tengo de ese tipo.
- `llaves_en_suelo` / `herramientas_en_suelo`: convierto el dict `id → zona` a `frozenset` de pares `(id, zona)` antes de comparar.
- `materiales_en_suelo`: `frozenset` de tripletas `(tipo, zona, cantidad)`.
- `puertas_abiertas`, `paneles_ok`, `estaciones_online`: `frozenset` de ids.
- `zona`: string. `batería`: entero.

El estado completo es una tupla de estos campos. Una tupla de `str`, `int` y `frozenset` es hasheable directamente, así que la uso tal cual como clave de CLOSED y como elemento de un `set`. Dos configuraciones físicamente iguales producen la misma tupla sin importar el orden en que el robot recogió o soltó cada cosa — que es justo la propiedad que necesito para que `==` y el hash coincidan con "es el mismo mundo".

### Relevancia: objetos que ya no cambian el futuro

Los cambios del entorno son **monótonos** (una puerta abierta no se cierra). Pregúntese: una llave cuya puerta ya está abierta, o una herramienta cuyo panel ya está reparado, ¿sigue distinguiendo estados si solo cambia *dónde* está en el suelo? Si no habilita ninguna acción futura, incluirla multiplica el espacio con permutaciones de objetos muertos. Justifique si las ignora y por qué eso no pierde el óptimo.

Defino un objeto como **vivo** en el estado `s` si todavía puede habilitar alguna acción futura relevante para la meta:

- una **llave** está viva si existe al menos una puerta que la requiere y que sigue `CLOSED`;
- una **herramienta** está viva si existe al menos un panel `DAMAGED` cuyo `requires.tool` sea esa herramienta;
- una unidad de **material** de un tipo está viva mientras el número de paneles `DAMAGED` que todavía piden ese tipo sea mayor que las unidades ya contadas como vivas (las unidades de más, si las hay, ya no sirven para nada).

En cuanto un objeto deja de ser vivo (la puerta que abría ya está `OPEN`, el panel que reparaba ya está `OK`, o ya conté las unidades de material que hacían falta), lo saco por completo de `llaves_en_suelo` \ `herramientas_en_suelo` \ `materiales_en_suelo` — dejo de preguntarme dónde está.

Esto no pierde el óptimo porque mi generador de sucesores **nunca vuelve a generar un `PICKUP` de un objeto muerto** (ver la sección de `Applicable` más abajo): si nunca lo voy a recoger de nuevo, su posición en el suelo no puede afectar ninguna acción legal futura ni el resultado de ninguna acción. Es exactamente el filtro de la sección "Por qué cada variable es necesaria", aplicado a la mitad de la variable en vez de a la variable completa: dejo de rastrear la posición solo cuando esa posición ya no puede cambiar nada.

Sin este recorte, cada objeto muerto seguiría multiplicando el espacio de estados por "en cuál de las zonas quedó" cada vez que se soltara, aunque nunca volviera a usarse — es la misma explosión combinatoria que la advertencia de `DROP` en el enunciado, pero aplicada a objetos que ya cumplieron su función.

---

## Acciones

Defina las acciones **internas** del agente (nombres libres). Para cada una: precondiciones, efectos, costo. Toda acción del mundo exige además `batería ≥ costo`.

Puede usar una tabla:

```text
Acción | Precondiciones | Efectos | Costo
```

Todas las acciones exigen además `batería ≥ costo` (lo omito de la columna de precondiciones para no repetirlo diez veces).

| Acción | Precondiciones | Efectos | Costo |
|---|---|---|---|
| `MOVE(z, z')` | robot en `z`; existe corredor `(z,z')`; si el corredor tiene puerta, esa puerta ∈ `puertas_abiertas` | `zona := z'` | `corridor.cost` |
| `PICKUP_KEY(k)` | `k` vivo y en `llaves_en_suelo[k] == zona`; peso(payload)+peso(k) ≤ `cargo_capacity` | `k` sale de `llaves_en_suelo`, entra a `llaves_cargadas` | `action_costs.pickup` |
| `PICKUP_TOOL(t)` | igual que arriba, con `herramientas_en_suelo` | análogo | `action_costs.pickup` |
| `PICKUP_MATERIAL(tipo)` | tipo vivo con unidades en `materiales_en_suelo[tipo]` en `zona`; peso+1 ≤ `cargo_capacity` | decrementa una unidad en el suelo, incrementa una en `materiales_cargados[tipo]` | `action_costs.pickup` |
| `DROP(x)` | `x` ∈ payload (ver condición exacta de generación abajo) | `x` sale del payload; si `x` sigue vivo, reaparece en `*_en_suelo[zona]`; si ya está muerto, se descarta y no se vuelve a rastrear | `action_costs.drop` |
| `OPEN_DOOR(d)` | robot en una de las dos zonas de `d`; `d ∉ puertas_abiertas`; `llave(d) ∈ llaves_cargadas` | `puertas_abiertas += d` | `action_costs.interact` |
| `REPAIR(p, material)` | robot en `zona(p)`; `p ∉ paneles_ok`; `herramienta_requerida(p) ∈ herramientas_cargadas`; `material == material_requerido(p)` y hay al menos 1 unidad en `materiales_cargados` | `paneles_ok += p`; `materiales_cargados[material] -= 1` (la herramienta no se toca) | `action_costs.interact` |
| `ACTIVATE(e)` | robot en `zona(e)`; `e ∉ estaciones_online`; todo panel en `requires.panels_ok` ∈ `paneles_ok`; toda estación en `requires.stations_online` ∈ `estaciones_online` | `estaciones_online += e` | `action_costs.interact` |
| `RECHARGE(c)` | robot en `zona(c)` donde `c` es un cargador real del escenario; `batería < battery_max` | `batería := battery_max` | `action_costs.recharge` |

Estos nombres son internos. Antes de emitir el plan los traduzco al contrato:
`MOVE`→`MOVE`, `PICKUP_KEY/TOOL/MATERIAL`→`PICKUP`, `DROP`→`DROP`,
`OPEN_DOOR`→`INTERACT{action:OPEN_DOOR}`, `REPAIR`→`INTERACT{action:REPAIR,
consumes:tipo}`, `ACTIVATE`→`INTERACT{action:ACTIVATE}`, `RECHARGE`→
`INTERACT{action:RECHARGE}`.

### `Applicable` interno vs legalidad del contrato

El simulador dice cuándo un paso es **legal**. Su generador de sucesores dice qué acciones son **relevantes para buscar**. No tienen que ser el mismo conjunto.

El contrato **permite** `DROP` en cualquier zona si el objeto está en la carga.
Si su agente genera ese `DROP` en cada estado con carga, el espacio deja de ser
«5 zonas y unas tareas» y pasa a ser «en cuál de las 5 zonas quedó cada objeto».
Eso no se arregla cambiando `cargo_capacity` ni apagando la batería: el escenario
es la fuente de verdad y el profesor probará otras instancias.

Usted puede (y se espera que) restrinja `DROP` —y cualquier otra acción— a los casos que un plan **óptimo** podría necesitar. Justifique que ningún plan de costo mínimo usa una acción que usted dejó de generar.

Antes de restringir nada, verifiqué cuatro hechos leyendo `simulator.py` y `executor.ts` en vez de suponerlos:

1. **¿Alguna precondición exige no llevar un objeto?** No. Repasé las siete acciones (`MOVE`, `PICKUP`, `DROP`, `OPEN_DOOR`, `REPAIR`, `ACTIVATE`,`RECHARGE`) una por una y ninguna precondición pide "payload vacío" ni "sin cierto objeto". Nada distinto de la capacidad obliga a soltar algo.
2. **¿El costo de `MOVE` depende del peso cargado?** No. En ambos simuladores `MOVE` gasta `corridor.cost` (o `step.cost`, que yo siempre fijo igual al costo del corredor); el peso del payload no entra en esa cuenta.
3. **¿Dónde se comprueba la capacidad?** Solo en `PICKUP`: ahí se compara peso(payload) + peso(objeto nuevo) contra `cargo_capacity`. `MOVE`,`OPEN_DOOR`,`REPAIR`,`ACTIVATE`,`RECHARGE` no la miran para nada.
4. **¿El costo de `DROP` depende de la zona?** No. Es siempre `action_costs.drop`, un valor plano del escenario, igual en cualquier zona.

**Regla que genero:** un sucesor `DROP(x)` solo existe en un estado `s` donde el robot está en una zona `z`, hay un objeto vivo `y` en el suelo de `z` que todavía no cargo, y agregar `y` al payload excedería `cargo_capacity`. En ese estado genero un `DROP(x)` por cada `x` que llevo actualmente (vivo o muerto), como sucesores alternativos — nunca genero `DROP` en ningún otro momento.

**Por qué esto no pierde el óptimo (argumento de intercambio):** tomo cualquier plan óptimo `π` que contenga un `DROP(x)` en un punto donde mi regla no lo generaría (es decir, en ese momento el payload no estaba bloqueando ningún `PICKUP` necesario). Por el hecho 2, cargar `x` un poco más no le cuesta nada extra a ningún `MOVE` posterior de `π`. Por el hecho 4, soltar `x` más tarde—justo cuando por fin haga falta el hueco, si es que hace falta—cuesta exactamente lo mismo que soltarlo ahora. Entonces puedo **retrasar** ese `DROP` hasta el primer punto en que sí libere espacio para un `PICKUP` que `π` necesita, sin tocar el costo de ningún otro paso de `π`. Dos casos al terminar de retrasarlo:

- Ese punto nunca llega (nada en `π` vuelve a necesitar la capacidad liberada):
  entonces el `DROP` original era prescindible. Lo elimino de `π` —y, si `π` volvía a recoger `x` más adelante, también elimino ese `PICKUP`— y obtengo un plan de costo estrictamente menor o igual que sigue llegando a la meta. Contradice que `π` fuera óptimo con ese `DROP` de más, salvo que costara 0 soltar y volver a cargar, en cuyo caso el plan sin el `DROP` es igual de bueno y sí está en mi espacio de búsqueda.
- Ese punto sí llega: entonces el `DROP` retrasado cae exactamente en un estado donde mi regla lo genera (payload lleno + `PICKUP` necesario bloqueado en esa zona). El plan transformado tiene el mismo costo que `π` y usa solo los `DROP` que yo genero.

En ambos casos obtengo un plan de costo menor o igual a `π` dentro de mi espacio de búsqueda. Como `π` era óptimo, el plan transformado también lo es —así que existe un plan óptimo que usa exclusivamente los `DROP` que genero. No genero ningún `PICKUP` de un objeto muerto, por la razón dada en "Relevancia": ningún plan óptimo necesita recoger algo que ya no habilita nada.

**`MOVE_TO`: salto directo entre zonas con algo que hacer.** No genero un `MOVE` por cada corredor adyacente. Genero un salto directo desde la zona actual hacia cada zona donde, en el estado actual, `Applicable` produciría al menos una acción no-`MOVE` (`PICKUP`, `OPEN_DOOR`, `REPAIR`, `ACTIVATE` o `RECHARGE`) — el costo es el del camino más barato entre las dos zonas usando solo corredores cuya puerta, si tienen, esté en `puertas_abiertas` en ese momento. Se apoya en el hecho 2 ya verificado: como el costo de `MOVE` no depende de nada más que el corredor, entre dos paradas donde el robot hace algo, ningún plan óptimo se beneficia de deambular — el camino más barato con las puertas abiertas de ese momento es siempre al menos tan bueno como cualquier rodeo, y las puertas no cambian a mitad de un tramo de puro viaje porque abrir una es en sí misma una parada. El camino se recalcula por estado (indexado por zona y por `puertas_abiertas`, no una tabla fija) porque abrir una puerta cambia qué corredores están disponibles. El plan que emito no ve este salto: lo reexpando en los `MOVE` de un solo corredor que lo componen, cada uno con el costo oficial de su tramo. Esto es legal porque todos los costos de corredor son no negativos: la suma parcial de cualquier prefijo de un camino es ≤ la suma total, así que si `batería ≥ costo_total_del_salto` entonces `batería ≥ costo_de_cada_tramo` en el momento en que ese tramo se ejecuta — ningún hop intermedio puede fallar por batería aunque el chequeo agregado sí haya pasado.

A qué zonas exactamente salto (`zonas_de_interés`) — crucé cada condición contra lo que `Applicable` genera en cada zona, para no dejar ninguna parada útil afuera:

| Condición local en esa zona | ¿Es zona de interés? |
|---|---|
| Llave/herramienta/material vivo en el suelo | Sí |
| Puerta cerrada cuya llave cargo, en cualquiera de sus dos zonas | Sí |
| Panel dañado ahí con herramienta y material cargados | Sí |
| Estación offline ahí con sus dependencias cumplidas | Sí |
| Cargador, si `batería < battery_max` | Sí |
| Nada de lo anterior | No — pasar por ahí no cambia el estado, así que ningún plan la necesita como parada |

No hace falta que sea "toda zona alcanzable": si una zona no ofrece nada de la tabla, detenerse ahí no tiene ningún efecto sobre el mundo, y como el costo del salto es el de Dijkstra, pasar por ella de largo hacia el verdadero destino nunca sale más caro que "parar" sin hacer nada. Si una zona sí ofrece algo, está en la tabla y por lo tanto es su propio destino directo desde donde esté el robot — nunca queda escondida dentro de un salto más largo.

**`DROP` de un objeto muerto en vez de uno vivo, cuando ambos están cargados.** Cuando estoy bloqueada y entre lo que cargo hay al menos un objeto muerto cuyo peso es ≥ el peso de todo objeto vivo que también cargo, genero **solo** los `DROP` de esos muertos "seguros" — no los de los vivos. La razón: soltar cuesta lo mismo ahora mismo sin importar cuál suelte (costo plano, hecho 4), y en cualquiera de los dos casos libero exactamente un cupo — la diferencia es solo cuál objeto se queda ocupando el cupo que no se liberó. Un muerto nunca vuelve a aportar nada (por definición, y para siempre: el mundo es monótono); un vivo aporta un valor ≥ 0 (puede hacer falta después, o no, pero nunca negativo). Quedarme con el vivo en ese cupo, al mismo precio, nunca puede salir peor que quedarme con el muerto. La condición de peso es necesaria, no cosmética: si el vivo pesara más que el muerto, quedármelo en vez de soltarlo aumentaría el peso cargado de ahí en adelante, y eso podría **invalidar** —no solo encarecer— un `PICKUP` posterior que en el plan original sí pasaba. Por eso solo aplico la preferencia cuando el muerto pesa al menos lo que cada vivo cargado; si ningún muerto cumple esa condición, sigo generando también los `DROP` de los vivos, como antes.

**`SWAP(x, y)`: fusionar el `DROP` con el `PICKUP` que lo obliga.** Cuando estoy bloqueada porque un objeto vivo `y` no cabe, y soltar un solo objeto `x` (de los candidatos que sobreviven la preferencia de arriba) ya libera lo que `y` necesita, genero un único sucesor que suelta `x` y recoge `y` a la vez, con costo `drop + pickup`, en vez de generar el estado intermedio "ya solté, todavía no recogí" como un nodo de búsqueda aparte. Esto no es una poda nueva: es la forma canónica que ya probé arriba — todo `DROP` óptimo se puede normalizar para caer justo antes del `PICKUP` que lo necesita, en la misma visita a la zona — llevada a su conclusión de fusionar los dos pasos en uno solo, porque nada que se intercale entre ellos depende de que estén separados: cualquier otra acción local de esa visita que no dependa de `x` o `y` se puede reordenar libremente antes o después del par, y cualquiera que sí dependa de uno de los dos ya está forzada a ir antes o después por su propia precondición. Cuando `y` pesa más de lo que cualquier `x` disponible libera por sí solo (hace falta soltar más de uno), no genero `SWAP` para ese `y` — caigo al `DROP` suelto de antes, que sigue disponible como respaldo para encadenar varios sueltos hasta que alcance. En `scenario.json` esto nunca pasa (todo pesa 1), pero el escenario es la fuente de verdad y el profesor puede variar pesos.

---

## Modelo de transición

```text
s  --a-->  s'     solo si a ∈ Applicable(s)
```

`Result` es determinista y parcial. Qué puede cambiar: zona, carga/suelo, batería, entorno persistente. Qué se preserva. Si canonicaliza el estado tras una acción, dígalo aquí.

`Result(s, a)` es una función determinista y parcial: solo está definida si `a ∈ Applicable(s)`, y para una `s` y una `a` dadas siempre produce la misma `s'` (el entorno es determinista, sin dados ni sensores ruidosos de por medio).

Lo que puede cambiar según la acción: `zona` (solo `MOVE`), la partición carga/suelo de un objeto (`PICKUP`/`DROP`), `batería` (todas, siempre baja salvo `RECHARGE` que la fija al máximo), y el entorno persistente —`puertas_abiertas`, `paneles_ok`, `estaciones_online`— que solo crece, nunca se reduce.

Lo que se preserva siempre: todo lo demás. Un `MOVE` no toca payload ni
entorno; un `PICKUP`/`DROP` no toca puertas/paneles/estaciones; un `REPAIR` no toca la herramienta usada (no se consume) ni la posición del robot.

Después de aplicar cualquier acción reconstruyo el estado con las mismas estructuras canónicas descritas en "Cuándo dos configuraciones son el mismo estado" (frozensets, tuplas ordenadas por clave) antes de guardarlo o compararlo contra CLOSED. Si no canonicalizo ahí, dos rutas que llegan al mismo mundo por distinto orden de inserción en un dict podrían producir objetos distintos en memoria aunque representen la misma física, y CLOSED fallaría en detectarlos como duplicados.

---

## Prueba de meta

```text
Goal(s) ⟺ scenario.goal.stations_online ⊆ s.estaciones_online
```

La misión se verifica sobre el **estado final del mundo**, no sobre haber ejecutado una lista de tareas. ¿Las puertas y los paneles son parte de la meta o solo medios?

Solo miro `estaciones_online`. No exijo payload vacío, ni todas las puertas abiertas, ni todos los paneles reparados — únicamente que las estaciones que pide `goal` estén `ONLINE`.

**Puertas y paneles son medios, no meta.** Ninguno aparece en `scenario.goal`. Importan solo porque `ACTIVATE` de una estación exige sus paneles en `paneles_ok`, y llegar a esos paneles exige a veces cruzar una puerta. Un panel que no esté en el `requires.panels_ok` de ninguna estación necesaria para la meta, o una puerta que no haga falta cruzar para llegar a esos paneles\estaciones, pueden quedar sin tocar en un plan óptimo — y de hecho mi filtro de "vivo" en la sección de Estado ni siquiera los rastrea si no hacen falta.

---

## Función de costo

```text
g(n) = Σ costo(aᵢ)   para la secuencia de acciones a₁...aₙ que llevan de s₀ a n
```

Debe ser la suma de los **costos oficiales** del escenario (no el número de pasos). Explique por qué minimizar pasos no es lo mismo que minimizar costo en este mundo (hay corredores baratos y caros).

Cada `costo(aᵢ)` es el valor oficial del escenario: `corridor.cost` para `MOVE`, y `action_costs.pickup/drop/interact/recharge` para el resto. No cuento pasos — cuento lo que efectivamente gasta el robot.

Minimizar pasos no es lo mismo que minimizar costo porque las acciones no cuestan lo mismo entre sí: `PICKUP`/`DROP` cuestan 1, `INTERACT` cuesta 2, `RECHARGE` cuesta 3, y un `MOVE` puede costar entre 3 y 12 según el corredor (`scenario.json` trae corredores de costo 3, 4, 5, 6, 8 y 12). Con esa mezcla, un plan de menos pasos puede salir más caro que uno con más pasos: un solo `MOVE` por el corredor Z2–Z5 (costo 12) pesa más por sí solo que un `MOVE` Z4–Z5 (costo 3) seguido de un `INTERACT REPAIR` (costo 2), que son dos pasos y suman 5. Si mi objetivo fuera "menos acciones", preferiría el salto caro de un solo tranco; minimizando costo real, ninguna búsqueda razonable lo haría.
Por eso la función de costo tiene que sumar valores del escenario, no contar `len(plan)`.

---

## Estrategia de búsqueda

Elija una estrategia **vista en clase** y justifíquela con las propiedades reales del problema (costos heterogéneos, plan de menor costo, espacio finito).

Discuta:

- completitud
- optimalidad (¿la prueba de meta se hace al extraer o al generar?)
- costo de camino
- tiempo y espacio (el `b` peligroso no es el grado del mapa: es cuántos
  `DROP`/`PICKUP` genera por estado)
- cuándo se rompen las garantías (costos 0 o negativos, estados mal canonicalizados, OPEN que no se vacía)

Graph Search exige una lista CLOSED sobre estados **canónicos**. Explique cómo evita reexplorar la misma situación física.

Elijo **Uniform-Cost Search (UCS) con búsqueda en grafo** (frontera como cola de prioridad por `g(n)`, más CLOSED de estados ya expandidos).

**Por qué UCS y no otra vista en clase:** no tengo una heurística admisible confiable a la mano (construir una que nunca sobreestime el costo de una secuencia MOVE+PICKUP+DROP+INTERACT heterogénea, y que siga siendo válida cuando el profesor cambie costos y disponibilidad de recursos, es más riesgo del que vale la pena para este alcance) — así que A* no aporta sobre UCS sin eso. BFS no sirve porque los costos no son uniformes (contaría pasos, no gasto real, y ya mostré que eso da la respuesta equivocada). DFS no garantiza ni completitud ni optimalidad en un espacio con ciclos. UCS es exactamente Dijkstra sobre el grafo de estados: exploro primero el nodo de menor `g(n)` acumulado, que es lo que la meta del enunciado pide minimizar.

**Completitud:** con costos estrictamente positivos (todos los `action_costs` y los `corridor.cost` del escenario lo son) y un espacio de estados finito (zonas, objetos y flags booleanos son todos finitos), UCS con grafo-search expande nodos en orden no decreciente de `g(n)` y termina por agotamiento de la frontera si no hay solución, o encuentra una si existe. Es completo bajo estas condiciones.

**Optimalidad:** UCS es óptimo si los costos son ≥ 0 (lo son) y hago la prueba de meta **al extraer** un nodo de la frontera, no al generarlo. Lo hago así:
si probara la meta al generar, podría devolver el primer camino que toca un estado meta aunque exista otro camino más barato hacia ese mismo estado todavía en la frontera sin explorar — UCS solo garantiza que la primera vez que un nodo sale de la frontera (no cuando entra) su `g(n)` es mínimo. Probar al extraer es lo que me da la garantía de optimalidad.

**Costo de camino:** heterogéneo y acotado por la suma de todos los costos posibles del escenario (finito), nunca negativo. Cumple lo que UCS necesita.

**Tiempo y espacio:** el factor de ramificación peligroso no es el grado del mapa (máximo 3 corredores por zona en esta instancia) sino cuántos `PICKUP`/`DROP` genero por estado. Con mi restricción de `Applicable` (solo objetos vivos para `PICKUP`, `DROP` solo cuando el payload bloquea un `PICKUP` necesario), la rama por estado queda acotada por: `MOVE` (≤ grado de la zona, ≤3 aquí) + `PICKUP` (≤ objetos vivos presentes en la zona) + `DROP` (≤`cargo_capacity`, y solo cuando estoy bloqueado) + `INTERACT` (≤ operaciones aplicables ahí, normalmente 0–2). Eso mantiene `b` de un solo dígito en la práctica, en vez de "5 zonas por cada objeto que cargo".

**Cuándo se rompen las garantías:** costos 0 permitirían ciclos de costo cero que UCS no detecta como "sin progreso" (seguiría siendo completo si el espacio es finito, pero podría reexplorar de más); costos negativos rompen optimalidad directamente (UCS asume no decrecientes). Un estado mal canonicalizado (por ejemplo comparar dicts por identidad en vez de por contenido, u olvidar convertir a `frozenset`) rompe la detección de duplicados en CLOSED y degenera a árbol de búsqueda. Un CLOSED que no se consulta antes de expandir (u "OPEN que no se vacía" por un bug de implementación) puede dejar la búsqueda corriendo sin terminar incluso en un espacio finito.

**Cómo evito reexplorar la misma situación física:** antes de expandir un nodo, canonicalizo su estado (frozensets, como ya expliqué) y lo uso como clave en CLOSED. Si ya está en CLOSED, no lo vuelvo a expandir — sin importar por qué ruta llegué la segunda vez, porque el estado (no el nodo) es lo que guardo ahí.

### Batería como recurso

La batería **sí** va en el estado (§2.1). Eso no implica explorar todos los paseos que solo gastan energía. Si dos caminos llegan a la **misma** configuración del mundo (zona, carga, suelo, entorno) y uno trae **más batería residual** a un **costo menor o igual**, el otro no puede mejorar ningún plan futuro: está dominado. Tratar cada nivel de batería como un mundo distinto, sin esa observación, hace que UCS recorra detours inútiles hasta agotar memoria. Justifique cómo CLOSED aprovecha (o no) esta dominancia.

CLOSED, tal como la describí arriba, guarda estados completos —batería
incluida— así que por sí sola no aplica la dominancia: dos rutas a la misma configuración física con distinta batería son, para CLOSED, dos claves distintas. Esto es correcto (no pierde nada), pero no aprovecha la observación del enunciado.

La dominancia es una **poda adicional** por encima de eso: antes de insertar un nodo nuevo en la frontera, lo comparo contra lo mejor que ya vi para su misma "configuración sin batería" (zona, carga, suelo, entorno persistente). Si ya tengo un nodo con esa misma configuración, costo ≤ y batería ≥, el nuevo nodo no puede llevar a ningún plan futuro mejor que el que ya tengo — cualquier acción que el nuevo pueda hacer, el que ya tengo también puede, y más barato. Lo descarto sin insertarlo.

**La objeción que me puedo encontrar:** `RECHARGE` falla si la batería ya está llena. ¿Eso rompe la dominancia? No. Si el nodo dominante ya tiene batería llena (o simplemente más batería que el dominado), y en algún punto posterior el plan dominado usa `RECHARGE` precisamente porque le hacía falta batería, al dominante puede que `RECHARGE` le falle ahí por estar lleno — pero no le hace falta: ya tiene la energía que el otro tuvo que ir a buscar. El dominante simplemente **se salta** esa acción (y su costo) y sigue con más batería efectiva que el dominado en el mismo punto. La regla "`RECHARGE` falla si está lleno" nunca le quita al dominante una acción que necesite; como mucho le quita una acción que no necesitaba. El argumento de dominancia se sostiene.

---

## Formulación y tamaño del espacio (obligatorio)

El mapa visible es pequeño. El espacio de estados **no** lo es, si se formula
mal. Responda con sus palabras:

1. ¿Por qué «5 zonas, ~10 objetos, capacidad 3» puede generar millones de nodos
   en un UCS ingenuo?
2. ¿Qué papel tiene `DROP` en esa explosión?
3. ¿Qué podas o abstracciones aplicó y por qué **no pierden el óptimo**
   (*sound*)?
4. ¿Por qué **no** es solución subir la capacidad, bajar las estaciones o
   ignorar la batería?

**1. Por qué explota un UCS ingenuo.** Si genero `DROP` en cualquier zona para cualquier objeto cargado y no distingo objetos vivos de muertos, el estado deja de ser "zona + banderas del mundo" y pasa a rastrear "en cuál de las 5 zonas (o en el payload) quedó cada uno de los ~9 objetos individuales del escenario" (3 llaves + 3 herramientas + 3 tipos de material, sin contar que hay más de una unidad de `FUSE`). Solo esa dimensión —posición de 9 objetos entre 6 lugares posibles (5 zonas + payload)— da hasta `6⁹ = 10 077 696` combinaciones. Multiplicado por hasta 101 niveles de batería (0 a `battery_max=100`) y por `2⁹=512` combinaciones de puertas (3) + paneles (3) + estaciones (3) abiertas/reparadas/online, y por la zona
del robot (5), el producto ya no cabe en memoria razonable ni en el tiempo de un examen — no hace falta terminar la multiplicación para ver que un UCS ingenuo no cierra.

**2. El papel de `DROP` en la explosión.** `DROP` es lo que convierte "9 objetos con una zona de origen fija" en "9 objetos que pueden terminar en cualquiera de 5 zonas". Sin `DROP` generado libremente, la posición de un objeto no recogido es fija (su zona en el escenario) y la de uno cargado es "en el payload" — dos posibilidades, no seis. `DROP` libre es exactamente el que multiplica esa dimensión por 5 (o 6, si cuento el payload) por cada objeto, y es acumulativo entre objetos porque son independientes entre sí.

**3. Qué podas apliqué y por qué no pierden el óptimo.** Seis, ya
justificadas arriba con argumento de intercambio o de dominancia, no solo por intuición:

- **`DROP` solo cuando bloquea un `PICKUP` necesario** (sección `Applicable` vs contrato): cualquier plan óptimo se puede transformar, sin subir su costo, en uno que solo suelta en ese momento exacto.
- **Nunca recojo un objeto muerto** (sección Relevancia): si nada lo va a usar, su posición no puede afectar ninguna acción futura por definición del filtro de estado — recogerlo no es un error, es simplemente algo que ningún plan óptimo necesita hacer.
- **Dominancia de batería en CLOSED**: dos rutas a la misma configuración física, la de menos batería a igual o mayor costo, nunca puede mejorar al dominante — argumento ya desarrollado arriba, incluida la objeción de `RECHARGE` sobre batería llena.
- **`MOVE_TO` compuesto**: ningún plan óptimo se beneficia de deambular entre paradas, así que colapso el tramo de puro viaje al camino más barato entre dos zonas con algo que hacer.
- **`DROP` de muerto antes que de vivo** (con la condición de peso): quedarme con el vivo en el cupo que dejaría libre el muerto nunca sale peor, al mismo costo.
- **`SWAP` cuando un solo `DROP` alcanza**: fusión directa de la primera poda de esta lista, sin perder generalidad porque el `DROP` suelto sigue disponible cuando hace falta soltar más de uno.

Ninguna de las seis cambia qué planes son alcanzables desde el estado
inicial — solo evita generar sucesores que un plan de costo mínimo no
necesitaría, o nodos que otro ya domina.

**Medido, no solo estimado.** Sobre `scenario.json`, con las tres primeras podas nada más, la búsqueda expandía 926 015 nodos entre 422 412 configuraciones físicas distintas (razón 2.19 — la batería multiplica poco, casi todo el volumen es mundo genuinamente distinto) y tardaba ~75s. Con las tres podas nuevas agregadas —`MOVE_TO`, preferencia de muerto sobre vivo, `SWAP`— eso bajó a 146 165 nodos expandidos, 68 142 configuraciones distintas (razón 2.15, se mantiene: la batería nunca fue el problema) y ~11s. La razón expandidos/configuraciones prácticamente no se movió entre una medición y otra — confirma que ninguna de las seis podas actúa sobre la batería, actúan sobre cuántos mundos físicos distintos hay que visitar, que es justo lo que argumenté arriba.

**4. Por qué no es solución subir la capacidad, bajar estaciones o ignorar la batería.** Esas "soluciones" resuelven la instancia de la demo, no el problema general que el profesor va a probar: subir `cargo_capacity` puede hacer que la demo nunca necesite `DROP`, pero con más objetos u otra capacidad menor en otra instancia el problema reaparece igual de explosivo.
Ignorar la batería quita una variable que el enunciado marca explícitamente como parte de la situación física (§2.1) — sin ella no puedo distinguir un estado donde `RECHARGE` es legal de uno donde no, ni detectar que el robot se quedó sin energía a mitad de plan; eso no poda el espacio, cambia las reglas del mundo, y el simulador seguiría exigiendo batería aunque yo la ignore internamente. Bajar estaciones cambia la meta que el profesor definió, no mi modelo. Ninguna de las tres es una poda: son formas de evitar diseñar el `Applicable` correcto, y todas fallan en cuanto cambie el escenario de
entrada.