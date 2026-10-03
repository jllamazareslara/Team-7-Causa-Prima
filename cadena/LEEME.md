# La cadena · Team 7

Piezas de cálculo para el sistema de negociación, y `rastro.py`, el programa que juega la cadena en El Rastro.
La explicación completa, con dibujos, está en la pestaña **Los agentes** del artefacto Team 7.

## Probarlo (sin red)

```
cd cadena
python -m unittest discover -s tests -v     # con estado-actual.json un nivel por encima
python sim/informe.py                        # simulaciones con los ajustes actuales → resultados/resumen.json
```

## La estructura

Ver [`ESTRUCTURA.md`](ESTRUCTURA.md). En cada tick: **Ojos** (+ Escudo) → **Contable** → **Cambista / Duelista /
Regateador** → **Guardia**, el único que firma. **El Guion** (el futuro: calendario) y **El Ojeador** (precios en el
tiempo, momento del juego, escasez) van al lado y solo aconsejan. Sin Director.

## Qué hay

| Archivo | Quién | Qué hace |
|---|---|---|
| `t7/cadena.py` | **La cadena** | Encadena a todos en un tick: `tick(lectura, memoria)` devuelve los mensajes, UNA firma como mucho, los cierres y el diario. Sin red. `cola_de_operaciones()` dice qué abrir con cada vendedor libre (primero vender) · `ojear()` al empezar cada tick (Guion y Ojeador); `operaciones()` (Regateador) y `anuncios()` (Cambista) con sus consejos |
| `vigia.py` | El Vigía | Va aparte. Avisa de lo nuevo en el juego y propone qué hacer. Solo lee (siete lecturas por pasada), así que puede ir a la vez que el programa que juega. `python vigia.py` una pasada; `python vigia.py --cada 60` sin parar, con pitido. Vigila ritmo y límites, calendario, niveles, vendedores, barrios nuevos, mercados y lo nuestro (efectivo, nivel, sobres, puesto), y avisa una vez de lo que empieza en 20 ticks o menos. Escribe `runs/novedades.jsonl`. Las reglas están en `t7/novedades.py`. **Probado solo contra un juego de mentira: la forma real del calendario y de los niveles no se ha visto** |
| `t7/guion.py` | El Guion | El futuro del juego: lee el calendario y tiene la jugada preparada para cada evento antes de que llegue (duelos, vendedores que abren, fiebre de un barrio, cierres). Guarda las cartas que esperan una fiebre (`reservadas()`) y comprueba rumores contra el calendario (`rumor()`) · En la cadena avisa en el diario de lo que viene, una vez por evento |
| `rastro.py` | — (programa, no es un agente) | Juega la cadena solo en El Rastro: lee el tablón, acepta lo que firma el Guardia, abre sobres y publica anuncios, peticiones y cambios (si sus interruptores están a 1). En seco por defecto; `--live` para jugar. **Nadie lo ha lanzado contra el juego real** |
| `revisar.py` | La revisión | Antes de jugar: lee el juego (solo lee) y dice con OK, AVISO o FALTA si todo está listo: reloj, caja, multiplicadores y rarezas leídos del juego, la calculadora comparada carta a carta con el valor del juego, vendedores nuevos y menús. Escribe `menus.borrador.json`. **Probada solo contra un juego de mentira** |
| `t7/menus.py` | — | Saca del juego (`dealers()`) un borrador de `menus.json`: qué vende y qué compra cada vendedor. Acepta menús por carta o por rareza; lo que no entiende lo dice y no lo adivina |
| `t7/parametros.json` | — | Todos los ajustes: valor, rango permitido, estado (medido / simulado / supuesto / decisión) y por qué |
| `t7/hoy.json` | — | Las noticias del día: duración del tick, lo visto en un duelo real, vendedores que se enfadan, categorías que se apagan, decisiones del equipo. Se cambia aquí, sin tocar código |
| `t7/situacion.py` | El plan del día | Con el efectivo del juego y `hoy.json` saca el modo de caja (holgado, justo, seco) y los ajustes de todos los agentes. `plan(estado)` devuelve los ajustes (`["p"]`) y lo forzado (`["forzar"]`) que se pasan a los agentes y al guardia; `resumen()` lo escribe para la pantalla. |
| `t7/ojos.py` | Los Ojos | Primer paso de cada tick: leen el juego y pasan los números a la Contable. Su ayudante, el Escudo, mira el texto sospechoso. Solo miran |
| `t7/ojeador.py` | El Ojeador | El vigilante de precios: historial en el tiempo (El Rastro y feed), tendencia, momento del juego, escasez, compradores probables. Dice cuándo comprar y vender; vendedores que descansan tras cupo agotado o enfado · Al lado de la cadena: pasa los precios al Regateador y al Cambista (`vigilar`, `precios`) |
| `t7/contable.py` | La Contable | Segundo paso, ¿renta? ¿cuánto?: con la calculadora hace las cuentas para el Regateador (tope o suelo, caja) y la ficha del Guardia (y la ganancia de cada duelo). No decide |
| `t7/valor.py` | La Contable | Calculadora. Coincide con el juego al céntimo (679,12 frente a 679,1; cada carta). `liquidez()` dice qué cartas pequeñas vender cuando el efectivo baja del colchón |
| `t7/guardia.py` | El Guardia | Única puerta antes de `accept`. Último paso: confirma con la ficha de la Contable. Cinco comprobaciones y firma solo, sin aprobación humana |
| `t7/tienda.py` | El Regateador | Comprar y vender a vendedores |
| `t7/duelo.py` | La Duelista | Duelos de precio (y utilidades para precio + día). Con día de entrega manda siempre un día: el que más nos vale según `your_days_weight` si llega como lista o diccionario por día (`mejor_dia`), y el día 5 si no se entiende. El precio todavía no se ajusta según el día |
| `t7/cambista.py` | El Cambista | El Rastro, mapa de deseos, cazador de páginas. Vender: `cadena.anuncios_rastro()` dice qué anunciar y a cuánto (lista × 1,3, 1 P menos por caducidad, nunca por debajo de lo que nos vale + 1) y el programa que juega lo tendría que publicar (`rastro.py`, con `rastro.publicar` = 1). **Viene apagado (`rastro.publicar` = 0): enseña lo que anunciaría y no manda nada. Publicar no se ha probado contra el juego.** Lo que un vendedor aún puede comprarnos hoy para su escalera no se anuncia. **Comprar (3/10):** `cambista.lista_compra()` ordena las cartas que faltan por lo que hacen ganar, con el bono de página (25 %) repartido entre las que faltan cuando quedan 1 o 2; el tope de cada compra es lo que esa carta nos vale hoy × 0,85. Las peticiones en El Rastro (`rastro.py` las publica con `cambista.pedir` = 1) (abren a 0,45 × base, suben 0,10 × base por caducidad, 4 a la vez, se cancelan si la carta ya llegó). Usa los precios del tablón que apuntan los Ojos (`memoria.mercado`). **Viene apagado (`cambista.pedir` = 0)** |
| `t7/broker.py` | El Casamentero | Market Test (no supera al puesto gratuito en nuestro simulador) |
| `t7/prioridad.py` | La cadena (parte) | Qué aceptar primero; los 3 tratos de la escalera |
| `t7/sondas.py` | El Espía | Gandalf al revés: sacar información a vendedores; detector de mala fe. Añadido el 3/10: sondas transformadas (¿me acerco o me alejo?, ¿par o impar?, etiqueta), termómetro del tono, cuaderno que ordena las sondas por lo medido, y canario + pregunta directa para duelos. La cadena usa el termómetro, el canario y una pregunta directa por duelo. **Cambiado el 3/10 tras `feedback-agentes-team7.md`:** lo que sale de un texto solo se apunta, nunca cambia un precio; con vendedores pregunta en una sola conversación de prueba al día y solo con los tres tratos de ese vendedor ya hechos (`espia.tras_tratos`, `espia.conversaciones_por_dia`; poner el segundo a 0 lo apaga) |
| `t7/defensa.py` | El Escudo | Filtro de entrada, tres avisos, filtro de salida, y el detector de incoherencias (el texto dice 15, la oferta pide 25), que antes estaba en el Espía |
| `t7/portavoz.py` | El Portavoz | Mensajes con tácticas; nunca otro número que el precio |
| `t7/perfiles.py` | El Observador | Ayudante del Regateador. Con quién ser duro; clasificar vendedores nuevos |
| `sim/` | — | Vendedores, duelos y Market Test simulados, y los torneos |
| `grabador.py` | El Grabador | Market Test: guarda los libros (solo lee) y `--rejugar` compara el automático con El Casamentero sin red |
| `datos/calendario-03-10.json` | — | El calendario real del sábado, para las pruebas |
| `PLAN-EQUIPO-03-10.md`, `PLAN-SABADO-03-10.md` | — | El plan del día, de lo más urgente a lo menos |

## Cómo está encadenado

```
el juego → (programa que juega: play.py) → lectura (números; el texto va aparte)
        → cadena.tick():  Ojos → Contable → Cambista / Duelista / Regateador → Guardia (una firma) → diario
                          Ojos + Escudo · al lado Guion y Ojeador (precios → Regateador y Cambista)
                          Cambista + Portavoz · Duelista + Portavoz, Espía · Regateador + Portavoz, Observador, Espía
        → (programa que juega) aplica las acciones → el juego
```

- **Parar:** crear `runs/STOP`. El Guardia deja de firmar en el tick siguiente.
- **Ajustar sin tocar código:** `t7/hoy.json` (apagar una categoría, rondas de duelo vistas, enfados) y `t7/parametros.json`.

## Lo que la hace resistente (añadido el 3/10, con los consejos del día)

| Consejo del día | Qué hace el sistema |
|---|---|
| Conocer el valor antes de comprar | Al arrancar hay que leer del juego nuestros multiplicadores (`me()["affinity"]`) y las rarezas (`catalog()`) y los pone en lugar de los supuestos (`valor.configurar()`). Lo que cambie sale en pantalla como `AVISO`. Una carta de un barrio sin multiplicador o con un código que no se entiende no se abre ni se sigue |
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
python rastro.py --ticks 3          # 1. El Rastro en seco: escribe lo que haría, no manda ni acepta nada
python rastro.py --live             # 2. El Rastro en vivo
```

La revisión primero, y otra vez cada vez que se anuncie un vendedor nuevo. Con algún `FALTA` no se juega en vivo. Deja en
`menus.borrador.json` los menús que entiende del juego: se miran y, si están bien, `python revisar.py --menus` añade a
`menus.json` los vendedores que falten (lo ya escrito no se toca).

**Quién conecta la cadena con el juego** (no es un agente ni un paso del flujo: son las flechas con EL JUEGO): `rastro.py`, **solo El Rastro** (el Cambista): lee el tablón, llama a `cadena.tick()`, acepta lo que firme el Guardia eligiendo qué copia nuestra se da, abre sobres antes de comprar y publica anuncios, peticiones y cambios si `rastro.publicar` / `cambista.pedir` = 1. Vendedores y duelos siguen sin programa (`director.py` se quitó): lo tiene que hacer `play.py`. Un solo programa que acepte con la clave del equipo.

Un solo proceso con la clave del equipo.

## Para meterlo en el repositorio del equipo

Lo decide el equipo. Dos caminos:

- **Entero:** copiar `t7/`, `revisar.py`, `tests/` y `sim/` a una rama `infra/t7` con Pull Request.
- **Solo la cadena:** copiar `t7/` y que `play.py` construya `lectura` y aplique las acciones de `cadena.tick()`. Así `play.py` conserva su forma de leer el juego, que ya está probada en vivo.
