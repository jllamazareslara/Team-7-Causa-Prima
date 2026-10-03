# El Espía · criterios de aceptación

**Rama:** `infra/t7-espia` · **Lugar en la cadena:** 2 · lee pistas del texto y solo las apunta

Gandalf al revés. Modificado el 3/10: sondas transformadas, termómetro, cuaderno, canario y pregunta directa en duelos. Tras la revisión del equipo, lo que sale de un texto solo se apunta.

## Aceptado cuando

- [ ] Lo que sale de un texto va al diario y a las palabras, nunca a un precio.
- [ ] Con vendedores pregunta en una sola conversación de prueba al día (`espia.conversaciones_por_dia`, 0 = apagado).
- [ ] Solo pregunta a un vendedor con sus 3 tratos del día ya hechos (`espia.tras_tratos`).
- [ ] Abuela 2 preguntas por conversación como mucho, Chato 0, nuevos 0; nunca la misma familia dos veces.
- [ ] Ningún mensaje suyo revela un límite ni un valor nuestro.
- [ ] Canario en la primera ronda de cada duelo; la pregunta directa solo a un rival que lee el texto.

## Cómo se comprueba (sin red)

Las pruebas viven en la rama `infra/t7`, que tiene la cadena entera. Desde `cadena/`:

- `python -m unittest tests.test_todo.Palabras.test_sondas_solo_con_permiso`
- `python -m unittest tests.test_todo.Palabras.test_espia_no_revela_nada`
- `python -m unittest tests.test_todo.Palabras.test_termometro`
- `python -m unittest tests.test_todo.Palabras.test_canario_y_pregunta`
- `python -m unittest tests.test_todo.Palabras.test_cuaderno_ordena_por_lo_medido`
- `python -m unittest tests.test_todo.Cadena.test_espia_solo_con_la_escalera_hecha_y_una_conversacion`
- `python -m unittest tests.test_todo.Cadena.test_el_texto_no_cambia_ningun_precio`

Nada de esta rama llama al juego, lee la clave ni acepta ofertas.
