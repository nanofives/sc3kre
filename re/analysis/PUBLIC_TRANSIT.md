# Transporte p├║blico en SimCity 3000 Unlimited: qu├® muestra el repo

En resumen, el transporte p├║blico aparece en el c├│digo como modos extra que el router de viajes puede usar. No hay un modelo de pasajeros ni de capacidad. Un viaje solo puede usar bus, tren o metro si el edificio de origen tiene esos modos habilitados y si sale bien un sorteo de "usar transporte masivo" (60% por defecto). Se cobra por pasajero y se paga mantenimiento mensual. El beneficio confirmado es que los tramos en bus no suman congesti├│n vial y que el metro carga su propia capa, separada de la de calles. La relaci├│n con contaminaci├│n, valor del suelo y demanda RCI no est├í trazada en el c├│digo.

## 1. Tipos de transporte y piezas que necesita cada uno

El router de SimTransit trabaja con un byte de tipo por nodo [CONFIRMED @ SimTransit 0x1000755e]. Los costos de cada modo vienen de `STTraffic.ini` en SYS.PAK (copia extra├¡da en `re/data/syspak/STTraffic.ini`).

| Modo | Byte de tipo | Piezas | Costo por celda |
|---|---|---|---|
| Bus | 0x50 parada, 0x41/0x43 calle con bus, 0x42 autopista con bus | Parada de bus (`BusStop`, men├║ "Bus Stop") sobre la red vial | parada 8, calle con bus 3, autopista con bus 1 |
| Tren | 4 v├¡a, 0x14 estaci├│n | V├¡as (`Lay Rail`) m├ís estaci├│n `RailStation` | v├¡a 2, estaci├│n 6 |
| Metro | 8 t├║nel, 0x18 estaci├│n | V├¡as subterr├íneas (`Lay Subway Rail`) m├ís `SubwayStation` | t├║nel 1, estaci├│n 6 |
| Conexi├│n tren-metro | 0x30 | `SubwayRailStation` ("Rail To Subway") | 6 |

El bus no tiene red propia. Usa calles y autopistas, y la parada habilita los tipos 0x41 a 0x43. Los constructores de las cuatro estaciones leen `OptimalMonthlyUpkeep` de `SC3Tune.ini` [CONFIRMED @ SimTransit 0x1000d3a7, 0x1000d625, 0x1000d8e7, 0x1000dbc7].

**Tren elevado:** no existe como red aparte. `NETMOD_CATALOG.md` no encontr├│ ninguna red, tipo de agente ni exemplar con ese nombre. Las piezas de tren son variantes de la misma red RAIL (sobre calle 16014, bajo autopista 17208). El metro no tiene archivo de puentes [CONFIRMED @ SIMNTWRK 0x10017f98].

En la calle animada (STRTSIM), los veh├¡culos de clase 1 (tren) y 2 (metro) eligen v├¡a al azar en cada nodo, sin destino [CONFIRMED @ STRTSIM 0x1001c290]. Igual que los autos, son decoraci├│n.

## 2. C├│mo un viaje elige transporte o auto

**Viajes mensuales de edificios.** El emisor es `FUN_100097b9` [CONFIRMED @ SimTransit 0x100097b9]:

- Cada edificio se procesa una vez por mes, en la semana `d├¡a/7 == this+0x10`.
- El destino lo elige `FUN_100099f1` seg├║n el tipo de zona de origen y la tabla `TrafficTripDestinationThresholds` [CONFIRMED @ SimTransit 0x100099f1]:

  | Origen | Valores de la tabla |
  |---|---|
  | Residencial | 10,40,100 |
  | Comercial | 70,80,100 |
  | Industrial | 50,70,100 |
  | Mixto | 33,66,100 |

- **Decisi├│n de transporte.** Si el byte `+0xf` del objeto del edificio est├í activo, se tira `rand(100)`. Si el resultado es `<= layer+0xc9` (`TrafficUseMassTransitChance` = 60), el viaje recibe los tres flags de modo del edificio (`+0xc/+0xd/+0xe`). Si no, sale con los tres en 0, es decir solo auto. Si `+0xf` est├í en 0, los flags pasan sin sorteo.
- `HIGHWAY_TRIPS.md` midi├│ en Sacramento combinaciones (1,1,1), (1,0,0) y (0,0,0). Seg├║n el orden en que `FUN_1000755e` habilita los tipos de estaci├│n, son bus, tren y metro.
- Los sondeos de crecimiento de zonas desde SIMRCI pasan por `FUN_1000706a` con destino 3 y sin el flag de dep├│sito [CONFIRMED @ SimTransit 0x1000706a, CAR_TRIPS 6.3].

**Distancia caminando.** El nodo de arranque (tipo 0x80) busca celdas dentro de `TripMaxDistanceToRoad` alrededor del lote: Res 4, Com 3, Ind 5, Default 5. Si encuentra una calle arranca como tipo 1, si no arranca en una estaci├│n [CONFIRMED @ SimTransit 0x1000755e, rama 0x80].

**C├│mo es la b├║squeda.** El router `FUN_100070d0` es una b├║squeda en profundidad, no un camino m├ís corto:

- Termina en el primer nodo que pasa la prueba de llegada `FUN_10008a94`.
- Los costos por celda (los de la tabla de arriba m├ís densidad/divisor) solo se suman y se comparan con un presupuesto. Con la base 256 medida en Sacramento son 4 x 256 = 1.024 unidades.
- Los costos nunca ordenan a los vecinos. En calles gana el vecino m├ís congestionado por debajo de `TrafficAnnoyanceLevel` 165 [CONFIRMED @ SimTransit 0x100070d0, 0x1000755e, 0x10007a63].
- Consecuencia: que el metro cueste 1 por celda y la calle 4 no atrae viajes al metro. Solo ampl├¡a hasta d├│nde llega el presupuesto. Esto est├í demostrado para autopistas (`HIGHWAY_TRIPS.md`). Para estaciones lo infiero del mismo c├│digo, no se midi├│.
- Las estaciones entran en el ring scan como candidatas cuando la celda tiene el bit 0x10 y el modo correspondiente est├í habilitado (`LANE_DENSITY.md`). La regla de preferencia entre estaci├│n y calle no est├í medida: `HIGHWAY_TRIPS` excluy├│ a prop├│sito los pasos con estaci├│n vecina.

**Capacidad y ridership.** No encontr├® ning├║n campo de capacidad de estaci├│n ni conteo de pasajeros por l├¡nea. Lo ├║nico que el router acumula de los tramos en bus es un float en `layer[0x40]` [CONFIRMED @ SimTransit 0x100070d0]. Su lector no est├í identificado.

**Cu├ínto se usa.** En Berl├¡n el 92-93% de los viajes que llegan usan solo calles. En Europolis 1024 es el 38-39%, y bajo la vista central la mayor├¡a de los nodos son de metro (`CAR_TRIPS.md` 3.2, medido en juego).

## 3. Qu├® cambia en la simulaci├│n

**Tr├ífico vial.** Los tramos en bus (0x41 a 0x43) no depositan densidad. Confirmado leyendo el switch y con un stub testigo en 75.539 viajes [CONFIRMED @ SimTransit 0x100070d0, CAR_TRIPS 6.1]. El metro deposita en su propia capa (m├íscara 8) y el tren y sus estaciones en la capa de superficie (0x15) sobre sus propias celdas. Un viaje que pasa a transporte deja de cargar calles en ese tramo. Los autos visibles son `0.008 x` la congesti├│n vial sumada de la vista, con un m├íximo de 200 [CONFIRMED @ STRTSIM 0x1001f556]. Menos congesti├│n vial significa menos autos en pantalla.

**Costos de construir y mantener:**

| Concepto | Valor (INI) | C├│digo |
|---|---|---|
| Mantenimiento por estaci├│n | Metro 10, Tren 10, Metro-Tren 10, Bus 5 por mes (`SC3Tune.ini`) | constructores citados arriba |
| Mantenimiento por celda de v├¡a | Tren 1, Metro 20 (`OptimalMonthlyFundingCostPer*`) | costo mensual = suma de `vt+0x10` de cada estaci├│n + ceil(celdas x costo por celda) [CONFIRMED @ SimTransit 0x10008ef5] |
| L├¡nea de presupuesto | celda x ancho x alto | [CONFIRMED @ SimTransit 0x1001557e] |
| Costo de construcci├│n | no encontrado | |

**Tarifas.** `PerTileTransitIncome` es Tren 10, Metro 10 y Bus 5, escalado por `_DAT_1001a50c` y copiado al layer en `+0xcc/+0xd0/+0xd4` [CONFIRMED @ SimTransit 0x100015b1, 0x100087fd]. No encontr├® el c├│digo que convierte eso en ingreso.

**Financiamiento y eficiencia.** Al fijar el financiamiento, el porcentaje se guarda en `+0xe5`, se propaga a cada estaci├│n, y una curva con `MaxEfficiencyTransit` 120 y `MysticalETransit` 30 da la eficiencia en `+0xf8` [CONFIRMED @ SimTransit 0x10008dbd].

**Huelgas.** `FUN_10008968` compara el financiamiento con `MinFundingForNoStrike` (70) cuando el costo es mayor que 0 [CONFIRMED @ SimTransit 0x10008968]. El cuerpo exportado est├í truncado tras el ftol. La INI tambi├®n da `StrikeChanceAtZeroFunding` 35 y `MaxLengthofStrikeInMonths` 24. La m├íquina de 3 estados `FUN_1000929a` lee justo `+0xe5`, el costo `+0xe0` y un contador acotado por `DAT_1001f124`, que es `MaxLengthofStrikeInMonths` (loader, l├¡nea 1276). `SIMTRANSIT_CLUSTER2.md` la hab├¡a llamado "congesti├│n", pero por los campos que lee es la m├íquina de huelgas. Esto es una relectura m├¡a y no tiene testigo en juego. En iOS existen `ChanceOfStrike` y `EndStrike` [iOS-HINT].

**Ordenanzas que tocan transporte:**

| Ordenanza (nombre seg├║n la clave INI) | Efecto mec├ínico | C├│digo |
|---|---|---|
| Transporte masivo subsidiado `0xc2d1b025` | +20 a la chance de usar transporte (m├íximo 255). Multiplica los tres ingresos por tarifa por 35 x `_DAT_1001a514` | [CONFIRMED @ SimTransit 0x100087fd] |
| Servicio de shuttle `0xa2bf1de5` | +1 a las cuatro distancias `TripMaxDistanceToRoad` | [CONFIRMED @ SimTransit 0x100087fd] |
| Multas de estacionamiento, autos en d├¡as alternos, carpooling, guardias de cruce, promoci├│n tur├¡stica | Ajustan los factores de decaimiento mensual de densidad de calle, autopista y tren | [CONFIRMED @ SimTransit 0x100093e9] |

**Contaminaci├│n, valor del suelo y demanda:**

- **Valor del suelo:** `FUN_1001deca` de SIMRCI lee una capa de tr├ífico junto a contaminaci├│n y crimen, acotada a ┬▒150 (`SIMRCI_CLUSTER1.md`, solo notas). Menos tr├ífico vial mejorar├¡a el valor por esa v├¡a, pero el t├®rmino exacto no est├í le├¡do.
- **Contaminaci├│n del aire:** no encontr├® ning├║n enlace entre tr├ífico o transporte y contaminaci├│n en SimTransit ni en las notas.
- **Crecimiento de zonas:** `SC3Tune.ini` tiene `MaxDistFromTransport` (Ind 4, Com 2, Res 3), que leen los developers de SIMRCI en `0x1000f022`, `0x10016290` y `0x10028198`. iOS lo llama `IsNearTransport` [iOS-HINT]. Si una estaci├│n cuenta como "transporte" para esa regla no est├í le├¡do. Los sondeos de viaje de SIMRCI muestran que el crecimiento consulta al router. Qu├® hace la zona cuando el viaje falla no est├í decodificado.
- **Tiempo de viaje:** no existe como magnitud. Solo hay costo sumado contra el presupuesto y ├®xito o fracaso, que se cuenta en `layer[0x2d]`.

## 4. Qu├® no se sabe

- **Qu├® contienen las grillas `+0x84/+0x88/+0x8c`.** `FUN_1000559e` las llena con radio `+0xc5/c6/c7` alrededor de ocupantes cuyo tipo `FUN_1000532c` traduce a 0, 1 o 2 desde ids de clase (3000, 5000, 8000 y otros). `SIMTRANSIT_CLUSTER1` las llam├│ "cobertura de estaci├│n". El c├│digo encaja mejor con "celdas al alcance de un edificio R/C/I", que sirven de destinos. Sigue [UNCERTAIN] (abierto tambi├®n en `CAR_TRIPS.md` y `HIGHWAY_TRIPS.md`).
- **Qu├® fija los bytes `+0xc..+0xf` del edificio.** Son los que deciden si un edificio puede usar bus, tren o metro. Falta el escritor.
- **Factores de escala.** Los valores de `_DAT_1001a514` y `_DAT_1001a50c` no se leyeron de `.data`. Por c├│mo se usan parecen escalas de porcentaje, sin confirmar.
- **Ingreso por tarifa y float de bus.** Qui├®n lee `+0xcc..+0xd4` (ingreso) y `layer[0x40]` (bus).
- **Preferencia por estaciones.** La regla del ring scan entre estaci├│n y calle, y si el transporte reduce de verdad la congesti├│n de una ciudad. Ninguna clave de `STTraffic.ini` se ha medido en juego, salvo el costo de autopista, que no tuvo efecto.
- **Huelgas.** La f├│rmula exacta y qu├® hace una huelga a los viajes.
- **Contaminaci├│n y demanda RCI.** Ning├║n v├¡nculo trazado en c├│digo.
- **Texto del juego.** No revis├® textos de ayuda en `Apps/Res`. Las ├║nicas fuentes de juego le├¡das son `STTraffic.ini` y `SC3Tune.ini` extra├¡dos de SYS.PAK.

Todas las citas de SimTransit son nivel C2 (cuerpo le├¡do), salvo los dep├│sitos y el router, que tienen medici├│n en juego en `CAR_TRIPS.md` y `HIGHWAY_TRIPS.md`.

(Worker research 2026-10-28, owner question "cómo funciona el transporte público y qué beneficios tiene". Notes-level where marked, C2 reads of SimTransit elsewhere.)
