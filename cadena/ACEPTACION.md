# El Portavoz · criterios de aceptación

**Rama:** `infra/t7-portavoz` · **Lugar en la cadena:** 7 · escribe el mensaje de cada precio nuevo

Plantillas (sin llamar a un modelo): amable con Abuela, solo el número con Chato, tácticas en duelos. No conoce nuestros límites.

## Aceptado cuando

- [ ] Ningún mensaje lleva otro número que el precio (lo comprueba `defensa.revisar_salida`).
- [ ] Con Chato, solo el número y sin preguntas.
- [ ] Solo plantillas: cabe en un tick de 15 s.

## Cómo se comprueba (sin red)

Las pruebas viven en la rama `infra/t7`, que tiene la cadena entera. Desde `cadena/`:

- `python -m unittest tests.test_todo.Cadena.test_chato_sin_preguntas_y_solo_numeros`
- `python -m unittest tests.test_todo.Palabras.test_salida_sin_limites`

Nada de esta rama llama al juego, lee la clave ni acepta ofertas.
