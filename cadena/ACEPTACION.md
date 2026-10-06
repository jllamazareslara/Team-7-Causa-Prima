# La Duelista · criterios de aceptación

**Rama:** `infra/t7-duelista` · **Lugar en la cadena:** 4 · una decisión por duelo

Juega los duelos con la curva Boulware (aguanta alto, cierra cuando esperar cuesta más del 6 %). En duelos con día de entrega manda siempre un día (`mejor_dia`).

## Aceptado cuando

- [ ] Nunca ofrece ni acepta fuera de nuestro límite (4.000 duelos simulados, cero pérdidas).
- [ ] Las 20 trampas de texto no cambian ninguna decisión: solo mira los números.
- [ ] Sin tarta (límites que no se cruzan) no cierra.
- [ ] Con día de entrega siempre manda `days`: el que más nos vale según `your_days_weight`, o el día 5 si no se entiende.
- [ ] En el simulador saca 0,44 de la tarta frente a 0,41 de las reglas actuales.

## Cómo se comprueba (sin red)

Las pruebas viven en la rama `infra/t7`, que tiene la cadena entera. Desde `cadena/`:

- `python -m unittest tests.test_todo.Duelo`
- `python -m unittest tests.test_todo.Cadena.test_dia_de_entrega_segun_nuestros_pesos`

Nada de esta rama llama al juego, lee la clave ni acepta ofertas.
