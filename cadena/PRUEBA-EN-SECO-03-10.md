# Primera prueba en seco contra el juego real · sábado 3/10, mediodía

> Después de esta prueba, `director.py` se quitó (el Director no es parte del flujo). La parte de El Rastro la juega
> ahora `rastro.py` (`python rastro.py --ticks 3`). Las formas reales de duelos y vendedores de abajo quedan apuntadas
> para el programa que juegue duelos y vendedores (`play.py`); su prueba está en `tests/test_cambista_listo.py`, saltada.

`python director.py --ticks 3`, sin `--live`: leyó el juego y escribió lo que haría. **No mandó ni aceptó nada.**

## Lo que funcionó
- Multiplicadores y rarezas leídos del juego (72 cartas con rareza): LAT 1,6 · RET 1,3 · LAV 1,1 · CHA 0,9 · SAL 0,7 · MAL 0,5.
- Caja: 184 P, holgada. Venta y compra en El Rastro encendidas en `hoy.json` (`rastro.publicar`, `cambista.pedir`).
- El Cambista preparó anuncios de repetidas y de Malasaña, la lista de la compra (primero RET-09), peticiones y
  cambios carta por carta (LAV-06 → RET-07, LAT-06 → RET-08).
- El Ojeador apuntó 30 precios del tablón real; el Guion leyó el calendario; escasez de 72 cartas.

## Lo que estaba mal y se ha corregido
| Qué | Visto en el juego | Arreglo |
|---|---|---|
| Duelos | el identificador se llama `duel` (no `id`), el plazo `deadline_tick`, las rondas `rounds`; trae `your_offer`, `rival_offer`, `messages`, `decay_per_round` | `director.leer()` los entiende; solo juega duelos `live`. Antes la cadena **saltaba todos los duelos** |
| Vendedores | `/api/dealers` responde `{"personas": [...]}` | `director.vendedores_nuevos()`, `t7/menus.py` y `revisar.py` lo entienden. Antes **no veía ningún vendedor** (ni niveles, ni menús) |

## Visto de paso (no es de la cadena)
Un duelo en vivo (comprador, límite 150, 3 rondas, −6 % por ronda): **otro programa del equipo** repetía «89?» en cada
mensaje mientras el rival bajaba de 171 a 148 y a 139, dentro de nuestro límite. Repetir el mismo precio no mueve al
rival; y sin trato el duelo vale 0. Hay que revisar ese programa antes de Duelos II.

## Además
- Márgenes: el Cambista ya solo propone lo que el Guardia firma (neto ≥ 10 % del valor de las cartas).
- Candado (`t7/candado.py`): en vivo, el lanzador toma un candado; si otro programa del mismo ordenador lo tiene, no
  arranca. Todo programa que acepte en vivo (también `play.py`) debería tomarlo: `candado.tomar(candado.RUTA, "play.py")`.
- Datos de prueba: `datos/estado-actual.json` (nuestras cartas del viernes, sin claves).
