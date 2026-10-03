# El Guardia · criterios de aceptación

**Rama:** `infra/t7-guardia` · **Lugar en la cadena:** 6 · la única puerta antes de `accept`

Es la única función que puede devolver «firma». No lee texto. Cinco comprobaciones y firma solo, sin aprobación humana.

## Aceptado cuando

- [ ] Con `runs/STOP` no firma nada.
- [ ] Como mucho una firma por tick para todo el equipo.
- [ ] Un campo desconocido en la oferta, o una oferta cuyo precio cambió desde que el agente la miró: no firma.
- [ ] Solo firma buen negocio mirando el valor de las cartas: comprando, paga como mucho el 90 % de lo que nos vale; vendiendo, cobra al menos el valor + 10 % (`guardia.margen_compra`, `guardia.margen_venta`).
- [ ] Una carta protegida solo sale por 1,5 veces lo que perdemos al darla, o más (`guardia.protegida_factor`).
- [ ] Una compra nunca baja de la reserva de 60 P; una venta no se bloquea nunca por la reserva.
- [ ] Una categoría apagada en `hoy.json` no se firma; con caja justa respeta el tope por trato.
- [ ] Un duelo solo se firma dentro de nuestro límite.

## Cómo se comprueba (sin red)

Las pruebas viven en la rama `infra/t7`, que tiene la cadena entera. Desde `cadena/`:

- `python -m unittest tests.test_todo.Guardia`

Nada de esta rama llama al juego, lee la clave ni acepta ofertas.
