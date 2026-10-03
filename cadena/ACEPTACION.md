# El Escudo · criterios de aceptación

**Rama:** `infra/t7-escudo` · **Lugar en la cadena:** 1 · mira el texto que llega y el que sale

Filtro de entrada (diez patrones de trampa), tres avisos = modo firme, filtro de salida, y el detector de incoherencias (el texto dice 15, la oferta pide 25), que antes estaba en el Espía.

## Aceptado cuando

- [ ] Detecta las trampas típicas de nuestra lista (8 de 8).
- [ ] Ningún mensaje nuestro sale con otro número que el precio ni con palabras que revelen límites.
- [ ] Una incoherencia texto/oferta se apunta como candidato a mala fe una sola vez; señalar lo decide el equipo.
- [ ] Nunca cambia una decisión: los mensajes con trampas dejan las acciones del tick idénticas.

## Cómo se comprueba (sin red)

Las pruebas viven en la rama `infra/t7`, que tiene la cadena entera. Desde `cadena/`:

- `python -m unittest tests.test_todo.Palabras.test_defensa_detecta_trampas`
- `python -m unittest tests.test_todo.Palabras.test_salida_sin_limites`
- `python -m unittest tests.test_todo.Palabras.test_mala_fe`
- `python -m unittest tests.test_todo.Cadena.test_las_trampas_no_cambian_las_acciones`
- `python -m unittest tests.test_todo.Cadena.test_mala_fe_se_apunta_una_vez_y_no_se_senala`

Nada de esta rama llama al juego, lee la clave ni acepta ofertas.
