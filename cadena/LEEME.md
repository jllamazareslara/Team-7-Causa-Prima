# Noche del 3 de octubre · Team 7

Piezas de cálculo para el sistema de negociación. **Nada de aquí llama al juego, lee la clave ni acepta ofertas.**
La explicación completa, con dibujos, está en la pestaña **Los agentes** del artefacto Team 7.

## Probarlo en 2 minutos (sin red)

```
cd noche-03-10
python -m unittest discover -s tests -v     # 78 pruebas, todas pasan (3/10)
python sim/informe.py                        # simulaciones con los ajustes actuales → resultados/resumen.json
```

## Qué hay

| Archivo | Agente | Qué hace |
|---|---|---|
| `t7/cadena.py` | **La cadena** | Encadena a todos en un tick: `tick(lectura, memoria)` devuelve los mensajes, UNA firma como mucho, los cierres y el diario. Sin red. `cola_de_operaciones()` dice qué abrir con cada vendedor libre (primero vender) |
| `director.py` | El Director | El único que habla con el juego: lee, llama a la cadena y aplica. En seco por defecto; `--live` para jugar. **Probado solo contra un juego de mentira: nadie lo ha lanzado contra el juego real** |
| `vigia.py` | El Vigía | Avisa de lo nuevo en el juego y propone qué hacer. Solo lee (siete lecturas por pasada), así que puede ir a la vez que el director. `python vigia.py` una pasada; `python vigia.py --cada 60` sin parar, con pitido. Vigila ritmo y límites, calendario, niveles, vendedores, barrios nuevos, mercados y lo nuestro (efectivo, nivel, sobres, puesto), y avisa una vez de lo que empieza en 20 ticks o menos. Escribe `runs/novedades.jsonl`. Las reglas están en `t7/novedades.py`. **Probado solo contra un juego de mentira: la forma real del calendario y de los niveles no se ha visto** |
| `revisar.py` | La revisión | Antes de lanzar el director: lee el juego (solo lee) y dice con OK, AVISO o FALTA si todo está listo: reloj, caja, multiplicadores y rarezas leídos del juego, la calculadora comparada carta a carta con el valor del juego, vendedores nuevos y menús. Escribe `menus.borrador.json`. **Probada solo contra un juego de mentira** |
| `t7/menus.py` | — | Saca del juego (`dealers()`) un borrador de `menus.json`: qué vende y qué compra cada vendedor. Acepta menús por carta o por rareza; lo que no entiende lo dice y no lo adivina |
| `t7/parametros.json` | — | Todos los ajustes: valor, rango permitido, estado (medido / simulado / supuesto / decisión) y por qué |
| `t7/hoy.json` | — | Las noticias del día: duración del tick, lo visto en un duelo real, vendedores que se enfadan, categorías que se apagan, decisiones del equipo. Se cambia aquí, sin tocar código |
| `t7/situacion.py` | El plan del día | Con el efectivo del juego y `hoy.json` saca el modo de caja (holgado, justo, seco) y los ajustes de todos los agentes. `plan(estado)` devuelve los ajustes (`["p"]`) y lo forzado (`["forzar"]`) que se pasan a los agentes y al guardia; `resumen()` lo escribe para la pantalla. |
| `t7/valor.py` | La Contable | Calculadora. Coincide con el juego al céntimo (679,12 frente a 679,1; cada carta). `liquidez()` dice qué cartas pequeñas vender cuando el efectivo baja del colchón |
| `t7/guardia.py` | El Guardia | Única puerta antes de `accept`. Cinco comprobaciones y firma solo: ya no hay Semáforo ni aprobación humana (quitado el 3/10 porque hacía esperar) |
| `t7/tienda.py` | El Regateador | Comprar y vender a vendedores |
| `t7/duelo.py` | La Duelista | Duelos de precio (y utilidades para precio + día). Con día de entrega manda siempre un día: el que más nos vale según `your_days_weight` si llega como lista o diccionario por día (`mejor_dia`), y el día 5 si no se entiende. El precio todavía no se ajusta según el día |
| `t7/cambista.py` | El Cambista | El Rastro, mapa de deseos, cazador de páginas. Vender: `cadena.anuncios_rastro()` dice qué anunciar y a cuánto (lista × 1,3, 1 P menos por caducidad, nunca por debajo de lo que nos vale + 1) y `director.anunciar()` lo publica. **Viene apagado (`rastro.publicar` = 0): enseña lo que anunciaría y no manda nada. Publicar no se ha probado contra el juego.** Lo que un vendedor aún puede comprarnos hoy para su escalera no se anuncia. **Comprar (3/10):** `cambista.lista_compra()` ordena las cartas que faltan por lo que hacen ganar, con el bono de página (25 %) repartido entre las que faltan cuando quedan 1 o 2; el tope de cada compra es lo que esa carta nos vale hoy × 0,85. `director.pedir()` publica peticiones en El Rastro (abren a 0,45 × base, suben 0,10 × base por caducidad, 4 a la vez, se cancelan si la carta ya llegó). Aprende los precios del tablón (`memoria.mercado`). **Viene apagado (`cambista.pedir` = 0)** |
| `t7/broker.py` | El Casamentero | Market Test (no supera al puesto gratuito en nuestro simulador) |
| `t7/prioridad.py` | El Director (parte) | Qué aceptar primero; los 3 tratos de la escalera |
| `t7/sondas.py` | El Espía | Gandalf al revés: sacar información a vendedores; detector de mala fe. Añadido el 3/10: sondas transformadas (¿me acerco o me alejo?, ¿par o impar?, etiqueta), termómetro del tono, cuaderno que ordena las sondas por lo medido, y canario + pregunta directa para duelos. La cadena usa el termómetro, el canario y una pregunta directa por duelo. **Cambiado el 3/10 tras `feedback-agentes-team7.md`:** lo que sale de un texto solo se apunta, nunca cambia un precio; con vendedores pregunta en una sola conversación de prueba al día y solo con los tres tratos de ese vendedor ya hechos (`espia.tras_tratos`, `espia.conversaciones_por_dia`; poner el segundo a 0 lo apaga) |
| `t7/defensa.py` | El Escudo | Filtro de entrada, tres avisos, filtro de salida, y el detector de incoherencias (el texto dice 15, la oferta pide 25), que antes estaba en el Espía |
| `t7/portavoz.py` | El Portavoz | Mensajes con tácticas; nunca otro número que el precio |
| `t7/perfiles.py` | El Observador | Con quién ser duro; clasificar vendedores nuevos |
| `sim/` | — | Vendedores, duelos y Market Test simulados, y los torneos |

## Cómo está encadenado

```
el juego → director.leer() → lectura (números; el texto va aparte)
        → cadena.tick():  Escudo → Espía → Regateador / Duelista / Cambista → Contable → Guardia (una firma) → Portavoz → diario
        → director.aplicar() → el juego
```

- **Parar:** crear `runs/STOP`. El Guardia deja de firmar en el tick siguiente.
- **Ajustar sin tocar código:** `t7/hoy.json` (apagar una categoría, rondas de duelo vistas, enfados) y `t7/parametros.json`.
- **A 15 segundos:** El Rastro se lee un tick de cada tres (`RASTRO_CADA` en `director.py`).

## Lo que la hace resistente (añadido el 3/10, con los consejos del día)

| Consejo del día | Qué hace el sistema |
|---|---|
| Conocer el valor antes de comprar | Al arrancar, `director.preparar()` lee del juego nuestros multiplicadores (`me()["affinity"]`) y las rarezas (`catalog()`) y los pone en lugar de los supuestos (`valor.configurar()`). Lo que cambie sale en pantalla como `AVISO`. Una carta de un barrio sin multiplicador o con un código que no se entiende no se abre ni se sigue |
| Llega El Retiro | La página de un barrio sale del catálogo del juego, no de suponer que son las cartas 01 a 10 |
| Calidad antes que cantidad | Con 3 tratos regateados hoy con un vendedor, ya no se le abren compras, salvo la carta que completa una página. Vender sigue |
| El latido rápido | Sale `LENTO` si un tick tarda más del 60 % de lo que dura. Un corte de red no tira el programa: espera y sigue |
| Caras nuevas | La primera vez que aparece un vendedor sale `VENDEDOR` en pantalla y queda tal cual en `runs/crudo.jsonl`. No se adivina su menú: hay que añadirlo a `menus.json` |

- **Un fallo, una pieza:** una conversación, un duelo o una oferta que falla o llega con otra forma se salta y sale `ERROR` en el diario; el resto del tick sigue. Un error al revisar una propuesta nunca firma nada.
- **No regatea por lo que la caja no paga:** el tope de una compra es lo que nos vale, lo que queda sobre la reserva y, con la caja justa, el tope por trato.
- **Sobres antes de comprar:** si hay un sobre sin abrir se abre primero, y las compras esperan al tick siguiente.
- **Conversación muda:** una conversación abierta en la que no entendemos la oferta durante 4 ticks se suelta, para no bloquear a ese vendedor.
- **Sin comprobar todavía:** la forma real de `affinity`, de `catalog()` y de `dealers()`. Si no se entienden, se dice y se sigue con los supuestos.

## Lanzarlo (lo hace quien tiene la clave, en su ordenador)

```
python revisar.py                   # 0. la revisión: solo lee. Dice qué está listo y qué falta
python director.py --ticks 3        # 1. en seco: escribe lo que haría, no manda ni acepta nada
python director.py --live           # 2. en vivo
```

0. La revisión primero, y otra vez cada vez que se anuncie un vendedor nuevo. Con algún `FALTA` no se lanza en vivo. Deja en `menus.borrador.json` los menús que entiende del juego: se miran y, si están bien, `python revisar.py --menus` añade a `menus.json` los vendedores que falten (lo ya escrito no se toca).
1. Siempre en seco primero. Mirar `runs/crudo.jsonl`: ahí queda la primera conversación y el primer duelo tal como los da el juego.
2. Si los nombres de los campos no son los que espera `director.leer()`, esa conversación o ese duelo se salta. Se corrige ahí, no en la cadena.
3. Para que abra conversaciones hace falta `menus.json` junto a `director.py`: `{"abuela": {"vende": {"RET-01": 10}, "compra": {"LAT-03": 4}}}`. Sin él solo sigue duelos y El Rastro.
4. Un solo proceso con la clave del equipo. Si `play.py` está en marcha, no lanzar `director.py` a la vez.

## Para meterlo en el repositorio del equipo

Lo decide el equipo. Dos caminos:

- **Entero:** copiar `t7/`, `director.py`, `tests/` y `sim/` a una rama `infra/t7` con Pull Request.
- **Solo la cadena:** copiar `t7/` y que `play.py` construya `lectura` y aplique las acciones de `cadena.tick()`. Así `play.py` conserva su forma de leer el juego, que ya está probada en vivo.
