# El Vigía · criterios de aceptación

**Rama:** `infra/t7-vigia` · **Lugar en la cadena:** fuera de la cadena · solo lee, puede ir a la vez que el director

Nuevo el 3/10. Avisa de lo nuevo en el juego (ritmo, calendario, niveles, vendedores, barrios, mercados, lo nuestro) y propone qué hacer. Escribe `runs/novedades.jsonl`.

## Aceptado cuando

- [ ] Sin cambios en el juego, no avisa de nada.
- [ ] Cada novedad sale una vez, con su propuesta en frases cortas; lo que empieza en 20 ticks o menos se avisa una vez.
- [ ] Solo hace lecturas (GET); una lectura que falla no tira la pasada.
- [ ] Lo que no entiende sale como «ha cambiado, mirar el crudo», sin inventar.

## Cómo se comprueba (sin red)

Las pruebas viven en la rama `infra/t7`, que tiene la cadena entera. Desde `cadena/`:

- `python -m unittest tests.test_todo.Vigia`

Nada de esta rama llama al juego, lee la clave ni acepta ofertas.
