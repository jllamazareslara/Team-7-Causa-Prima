# El Regateador · criterios de aceptación

**Rama:** `infra/t7-regateador` · **Lugar en la cadena:** 3 · una decisión por conversación con un vendedor

Compra y vende a los vendedores: ancla baja, pasos repartidos entre las rondas que quedan, k̂ medido en vivo. `prioridad.py` decide qué aceptar primero (los 3 mejores tratos por vendedor).

## Aceptado cuando

- [ ] Nunca cruza nuestro tope (comprando) ni nuestro suelo (vendiendo).
- [ ] Nunca repite el mismo precio dos veces seguidas.
- [ ] Con 3 tratos regateados hoy con un vendedor no le abre más compras, salvo la carta que completa página.
- [ ] No regatea por lo que la caja no paga (tope = lo que vale, lo que queda sobre la reserva, tope por trato).
- [ ] En el simulador captura más rango que la regla actual del equipo (0,54 frente a 0,40 con Abuela).

## Cómo se comprueba (sin red)

Las pruebas viven en la rama `infra/t7`, que tiene la cadena entera. Desde `cadena/`:

- `python -m unittest tests.test_todo.Tienda`
- `python -m unittest tests.test_todo.Robustez.test_calidad_antes_que_cantidad`
- `python -m unittest tests.test_todo.Robustez.test_no_regatea_por_lo_que_la_caja_no_paga`

Nada de esta rama llama al juego, lee la clave ni acepta ofertas.
