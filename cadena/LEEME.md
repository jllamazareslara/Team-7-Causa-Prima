# El Guardia · Team 7

Esta rama trae solo a **El Guardia** y lo que necesita para funcionar:

- `cadena/t7/__init__.py`
- `cadena/t7/params.py`
- `cadena/t7/parametros.json`
- `cadena/t7/hoy.json`
- `cadena/t7/valor.py`
- `cadena/t7/guardia.py`
- `cadena/t7/VALORES.md` — por qué esos números: casos reales confirmados contra `GET /api/catalog` y `GET /api/me`

Criterios de aceptación: [`ACEPTACION.md`](ACEPTACION.md). La cadena completa, con todos los agentes encadenados,
el director y las 78 pruebas, está en la rama `infra/t7`.

## Sábado 3/10: la estructura en tres capas, El Guion y El Ojeador

Ver [`ESTRUCTURA.md`](ESTRUCTURA.md): 1) Ojos (`t7/ojos.py`) → Contable (`t7/contable.py`), con El Guion y El Ojeador
en paralelo; 2) Cambista / Duelista / Regateador; 3) Guardia, el único que firma.

| Archivo | Quién | Qué hace |
|---|---|---|
| `t7/guion.py` | El Guion | El futuro del juego: lee el calendario y tiene la jugada preparada para cada evento antes de que llegue (duelos, vendedores que abren, fiebre de un barrio, cierres). Guarda las cartas que esperan una fiebre (`reservadas()`) y comprueba rumores contra el calendario (`rumor()`) |
| `t7/ojeador.py` | El Ojeador | El vigilante de precios: historial en el tiempo (El Rastro y feed), tendencia, momento del juego, escasez, compradores probables. Dice cuándo comprar y vender; vendedores que descansan tras cupo agotado o enfado |
| `t7/cadena.py` | — | `ojear()` al empezar cada tick; `operaciones()` (Regateador) y `anuncios()` (Cambista) con los consejos del Guion y el Ojeador |
| `grabador.py` | El Grabador | Market Test: guarda los libros (solo lee) y `--rejugar` compara el automático con El Casamentero sin red |
| `datos/calendario-03-10.json` | — | El calendario real del sábado, para las pruebas |
| `PLAN-EQUIPO-03-10.md`, `PLAN-SABADO-03-10.md` | — | El plan del día, de lo más urgente a lo menos |

126 pruebas sin red, todas pasan (`python -m unittest discover -s tests`, con `estado-actual.json` un nivel por encima).
