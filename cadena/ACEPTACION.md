# La Contable · criterios de aceptación

**Rama:** `infra/t7-contable` · **Lugar en la cadena:** 6 · antes de cada firma (con el Guardia)

Calcula cuánto nos vale cada carta (valor marginal, con bono de página) y si un trato renta. Con `situacion.py` saca el modo de caja del día (holgado, justo, seco).

## Aceptado cuando

- [ ] El valor de la colección coincide con el juego al céntimo (679,12 frente a 679,1) y carta a carta.
- [ ] El bono de página es el 25 % de la suma de la página; la carta que completa página vale su valor más ese bono.
- [ ] Una carta protegida nunca aparece como vendible; `liquidez()` solo propone ventas sin perder valor.
- [ ] Con datos del juego (`configurar`) sustituye los supuestos; lo que no entiende no cambia nada.
- [ ] Modo holgado no cambia ningún ajuste; justo vende primero y baja el tope; seco no compra pero vende.

## Cómo se comprueba (sin red)

Las pruebas viven en la rama `infra/t7`, que tiene la cadena entera. Desde `cadena/`:

- `python -m unittest tests.test_todo.Calculadora`
- `python -m unittest tests.test_todo.ValoresDelJuego`
- `python -m unittest tests.test_todo.Situacion`

Nada de esta rama llama al juego, lee la clave ni acepta ofertas.
