# Para Ana: Ojos, Guion y Ojeador

Los tres que miran en la **capa 1** de la estructura (ver `ESTRUCTURA.md`), en paralelo con la Contable.
Ninguno manda mensajes ni firma: solo miran y aconsejan. Firma solo el Guardia.

| Quién | Archivo | Mira | Entrega |
|---|---|---|---|
| **Los Ojos** | [`t7/ojos.py`](t7/ojos.py) | **el presente**: leen el juego; su ayudante, el Escudo, mira el texto sospechoso | los números a la Contable y la `vista` del tick (`mirar()`) |
| **El Guion** | [`t7/guion.py`](t7/guion.py) | **el futuro del juego**: el calendario (`/api/schedule`) | la jugada preparada para cada evento antes de que llegue; las cartas que esperan una fiebre (`reservadas()`); si un rumor es cierto (`rumor()`) |
| **El Ojeador** | [`t7/ojeador.py`](t7/ojeador.py) | **el pasado de los precios** (el vigilante de precios) y el futuro del mercado según el calendario | comprar ya o esperar (`comprar_ahora()`), precio de los anuncios (`precio_venta()`), vendedores que descansan (`descanso()`), cartas que se agotan (`escasez()`), quién quiere qué (`compradores_probables()`) |

## Dónde se llaman

Todo desde `t7/cadena.py`:

- `tick()` empieza con `ojear()` (Guion y Ojeador: guarda calendario, catálogo, feed y cierres de vendedores; deja
  `hora`, `momento` y `escasez` en la lectura) y luego `ojos.mirar()` (la vista).
- En El Rastro, antes de aceptar una compra que renta, el Cambista pregunta al Ojeador `comprar_ahora()`.
- `operaciones()`: la cola del Regateador con las cartas guardadas (Guion), los vendedores que descansan, El Rastro más
  barato y las cartas que se agotan (Ojeador).
- `anuncios()`: los anuncios del Cambista sin las cartas guardadas y con el precio del Ojeador.

## Qué tiene que pasar en la lectura quien lance la cadena

`calendario` (/api/schedule), `catalogo` (/api/catalog), `feed` (/api/feed), `t_hours` y `tick_segundos`
(/api/clock), `niveles` de los vendedores (/api/dealers) y, en cada vendedor cerrado, `cerrado` (closed_reason) y
`until_tick`. El Director no es parte del flujo: hoy lo hace `jugar.py` para vendedores y El Rastro (`leer()`, `leer_calendario()`, `vendedores_nuevos()`);
duelos, pendiente. Lo que falte se salta: la cadena sigue sin ese consejo.

## Pruebas

`python -m unittest tests.test_guion -v` desde `cadena/`: Guion, Ojeador y su conexión con la cadena, sin red.
Todo el conjunto: `python -m unittest discover -s tests` (133 pruebas, con `datos/estado-actual.json`).
Prueba en seco contra el juego real: ver `PRUEBA-EN-SECO-03-10.md`.
