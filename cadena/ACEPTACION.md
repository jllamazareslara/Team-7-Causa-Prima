# El Cambista · criterios de aceptación

**Rama:** `infra/t7-cambista` · **Lugar en la cadena:** 5 · El Rastro (cuando el director trae el tablón)

Pasa cada oferta de El Rastro por la Contable en los dos sentidos, mapa de deseos y cazador de páginas. Anuncia a lista × 1,3, baja 1 P por caducidad, nunca por debajo de lo que nos vale + 1.

## Aceptado cuando

- [ ] Solo propone lo que renta según la Contable; nunca da una carta protegida.
- [ ] Detecta la carta que completa página y la marca como oportunidad.
- [ ] Anuncio: nunca por debajo de lo que nos vale + 1; lo que un vendedor aún puede comprarnos hoy no se anuncia.
- [ ] Viene apagado (`rastro.publicar` = 0): enseña lo que anunciaría y no manda nada.

## Cómo se comprueba (sin red)

Las pruebas viven en la rama `infra/t7`, que tiene la cadena entera. Desde `cadena/`:

- `python -m unittest tests.test_todo.Cambista`
- `python -m unittest tests.test_todo.Cadena.test_anuncios_de_el_rastro`
- `python -m unittest tests.test_todo.DirectorRobusto.test_precios_de_venta`

Nada de esta rama llama al juego, lee la clave ni acepta ofertas.
