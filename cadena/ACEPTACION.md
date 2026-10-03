# El Observador · criterios de aceptación

**Rama:** `infra/t7-observador` · **Lugar en la cadena:** ayuda al Regateador (perfil de cada vendedor)

Con quién ser duros. Un vendedor nuevo empieza como «desconocido» y tras su primera conversación se le asigna el perfil más parecido (k̂, rondas que aguanta, si se ofendió).

## Aceptado cuando

- [ ] Clasifica bien los perfiles conocidos: (0,8, 14 rondas, sin ofenderse) → abuela; (0,6, 7, ofendido) → chato.
- [ ] Un vendedor que no se ha visto nunca se trata como desconocido (prudente).

## Cómo se comprueba (sin red)

Las pruebas viven en la rama `infra/t7`, que tiene la cadena entera. Desde `cadena/`:

- `python -m unittest tests.test_todo.Cambista.test_perfil_nuevo`

Nada de esta rama llama al juego, lee la clave ni acepta ofertas.
