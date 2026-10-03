# Plan del sábado 3/10 · Team 7

Fuentes: `GET /api/levels`, `/api/schedule` y `/api/catalog` (leídos sin clave hacia las 10:10), la pantalla grande (pistas del día) y `bazaar-kit/RULES.md`.
Horas de pared calculadas desde el calendario (Duelos I = 11:30, Duelos II = 18:00): **pueden moverse**, mirar `GET /api/schedule`.

## 1. Lo que viene

| Hora (aprox.) | Qué | Qué hacer |
|---|---|---|
| 11:20 | Market Test (cada 2 h: 13:20, 15:20, 17:20, 19:20) | El puesto gratuito ya da la mitad de los puntos. No abrir mercado propio sin medir. |
| **11:30** | **Duelos I**: solo precio, 16 rondas, −6 % por ronda, todos contra todos | **Un duelo sin respuesta = 0 para los dos.** Tener un agente de duelos encendido antes. |
| ~11:50 | **Doña Pilar** abierta a todos. Coleccionista: paga caro las cartas buscadas, vende sobres oro | 3 tratos regateados con ella (escalera). |
| ~12:45 | **El Chato** abierto a todos. Poco comunes y raras, mejores sobres a buen precio | 3 tratos regateados con él (escalera). |
| — | **Radio Rastro**: boletín, Radio Rastro y El Tablón. Mezcla datos ciertos y rumores | Solo apuntar. Nunca cambiar un precio por un rumor. |
| **~15:30 → 17:30** | **Fiebre Salamanca**: Pilar paga un 25 % sobre el valor de catálogo por Salamanca | Vender a Pilar nuestras Salamanca que nos valen poco. Guardarlas hasta entonces. |
| **18:00** | **Duelos II**: precio + día de entrega (0–10), 2 vueltas, −8 % por ronda | Negociar los dos temas a la vez (ver §3). |
| ~21:00 | Market Test duro: 12 traders más firmes e impacientes | — |
| 23:00 | Cierre | — |
| Dom 09:30 | Sale Chamberí, +150 P para todos | — |
| Dom ~11:30 | Duelos III: 12 rondas, −10 % por ronda | Cerrar todavía antes. |
| Dom ~14:30 | Cierran los puestos + Gran Final de duelos | — |

## 2. De dónde salen los puntos y dónde poner el esfuerzo

| Bloque | Puntos | Lo que cuenta | Nuestra jugada |
|---|---|---|---|
| Jurado | 40 | Ideas y oficio | La cadena de agentes, el diario con el motivo de cada decisión, el Espía/Escudo, el banco de simulación. **Contarlo con datos reales del día.** |
| Negociar | 30 | Duelos (parte del pastel) · escalera (los 3 mejores tratos por vendedor, uno que falte = 0, **los niveles altos pesan más**) · valor ganado con otros equipos | 1) responder todos los duelos y cerrar pronto; 2) 3 tratos regateados con **cada** vendedor, empezando por Pilar y Chato; 3) vender a otros equipos lo que nos vale poco. |
| Mercado | 30 | Market Test · valor creado entre otros equipos en nuestro puesto | Mantener el puesto gratuito (la mitad seguro). Solo abrir mercado propio si el banco demuestra que superamos al automático. |

Reglas que no se rompen (pantalla grande, pistas 1 y 5):
- **Un trato por encima de nuestro valor resta puntos.** Mirar `GET /api/me/value?card=…` antes de comprar.
- Repetir el mismo precio no es un paso; inundar a un vendedor hace que deje de hablarnos.
- El volumen no puntúa. El efectivo tampoco: sirve solo para poder hacer más tratos buenos.

## 3. Duelos: la cuenta que manda

El pastel se encoge un 6 % por ronda (8 % en Duelos II, 10 % el domingo).
Quedarse el 60 % en la ronda 1 vale 0,60. Quedarse el 70 % en la ronda 5 vale 0,70 × 0,94⁴ = **0,55**. **Cerrar pronto gana.**
- Abrir con una oferta que el otro pueda aceptar (pista 3): cerca del reparto a medias, un poco a nuestro favor.
- Aceptar en cuanto la oferta del otro nos da más de lo que ganaríamos esperando una ronda más.
- Menos de la mitad de los duelos de práctica del viernes acabaron en trato: cerrar ya es ventaja.

**Duelos II (precio + día):** cada lado tiene un peso privado por día (`your_days_weight`). El pastel crece si cada uno se queda con lo que más le importa:
- Si el día nos importa poco, dárselo al rival a cambio de precio.
- Si nos importa mucho, pedir nuestro día y ceder un poco de precio.
- Leer qué día pide el rival en sus ofertas (`dia_preferido_rival`) para saber cuánto le importa.

## 4. Dónde se añade cada cosa en el código

| # | Qué | Dónde | Estado |
|---|---|---|---|
| 1 | **Agente de duelos encendido para las 11:30** | `bazaar-kit/duel_agent.py` (ya existe) o `director.py` solo con duelos (`apagar` todo lo demás en `t7/hoy.json`) | Urgente. Lo lanza quien tiene la clave. |
| 2 | Precio que cambia según el día (cesión cruzada precio ↔ día) | `t7/duelo.py`: nueva función junto a `paquetes_iguales()`, usada por `decidir()` cuando el duelo trae `days` | Hoy antes de las 18:00. Hoy `duelo.py` manda el mejor día pero **no ajusta el precio**. |
| 3 | Cerrar antes con el pastel que se encoge | `t7/duelo.py` `decidir()`: aceptar si la oferta ≥ lo que esperamos sacar × (1 − descuento) | Hoy. `descuento_ronda` desde `t7/hoy.json` → `duelo` (0,94 / 0,92 / 0,90). |
| 4 | Pilar y Chato: qué venden y compran | `menus.json` (lo saca `revisar.py --menus` de `dealers()`) | En cuanto se abran. |
| 5 | Escalera: los niveles altos pesan más | `t7/prioridad.py` `mejora_escalera()`: multiplicar por el nivel del vendedor | Pequeño. |
| 6 | Fiebre Salamanca | `t7/cambista.py` + `t7/hoy.json`: guardar Salamanca hasta ~15:30 y ofrecérselas a Pilar en la ventana; `t7/novedades.py` avisa con `persona_patch` | Antes de las 15:30. |
| 7 | Radio Rastro / El Tablón: solo apuntar | `t7/sondas.py` (cuaderno) y `t7/defensa.py` (nunca cambia un precio) | Pequeño. |
| 8 | Señalar mala fe solo con prueba | `t7/defensa.py` detector de incoherencias → `POST /api/flags` | Un aviso correcto puntúa, uno falso resta: solo si el texto contradice la oferta. |

## 4 bis. Hecho: El Guion (`t7/guion.py`)

Lee el calendario del juego y tiene **una jugada preparada para cada evento antes de que llegue**: duelos, Market Test, vendedor que abre, fiebre de un barrio, fin de fiebre, barrio nuevo, dinero para todos, ronda nueva, cierre de un vendedor en la final, cierre del día, congelación de puntos. Además da una jugada por defecto para niveles que aún no conocemos (vendedor, radio, otro).
- `guion.bloqueadas()`: las cartas de un barrio con fiebre próxima no se venden a otro sitio (6 h antes y durante).
- `guion.venta_fiebre()`: qué copias venderle al vendedor de la fiebre, con margen, sin romper nunca una página. Con nuestros multiplicadores, Salamanca nos vale × 0,7: la fiebre es para nosotros.
- El Vigía ya avisa con antelación con el calendario real, que va en horas (`at_hours`) y no en ticks: 2 h antes de una fiebre, 1,5 h antes de que cierre un vendedor, 30 min antes de un duelo.
- Sin red: `python -m t7.guion datos/calendario-03-10.json --hora 10:10` (añadir `--cartas cartas.json` para la lista de la fiebre).
- Pruebas: `tests/test_guion.py` (sin lanzar todavía).

Falta conectar `bloqueadas()` a `cambista.py` / `cadena.py` para que el Cambista no anuncie esas cartas en El Rastro.

## 5. Para GitHub

Rama nueva `infra/t7-sabado` desde `infra/t7` con este plan y los cambios 2–7, cada uno con su prueba en `tests/`.
Las pruebas y el envío a GitHub se lanzan solo con el sí del equipo.
