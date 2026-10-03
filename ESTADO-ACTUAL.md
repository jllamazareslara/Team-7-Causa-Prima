# Team 7 · Estado actual — sábado 03/10, 17:10

## Dónde estamos
| | Total | Negociar | Mercado |
|---|---|---|---|
| **Team 7 (17.º de 18)** | **18,58** | 9,50 | 9,08 |
| Team 14 (1.º) | 29,82 | 20,58 | 9,24 |
| Team 5 (2.º) | 29,73 | 22,23 | 7,50 |
| Team 1 (3.º) | 29,09 | 21,59 | 7,50 |

**El hueco está en «negociar» (−11 a −13 puntos), no en el mercado.** Nuestra escalera de vendedores vale 0,08: casi no tenemos tratos buenos con los vendedores de nivel alto (Pilar nivel 3, Los Pícaros nivel 4). El mercado está bien (encima de la base 7,5): no se toca.

Estrategia: subir sin riesgo. **Reserva de 60 P intocable.** Caja ≈ 69 P.

## Qué está corriendo ahora
| Programa | Quién | Estado |
|---|---|---|
| Vendedores (`noche-03-10/director.py`) | PC de Betty | EN VIVO desde 16:58, corregido |
| Cambista / El Rastro (`team7-main/cadena/rastro.py`) | PC de Betty | EN VIVO desde 16:16 |
| Duelos (`team7-main/cadena/duelos.py`) | **Juan** | Duelos II ≈ 20:34 |

## Lo que se ha hecho esta tarde
1. **Vendedores corregidos y relanzados.** Ya no vende por debajo de la oferta del vendedor («él 0»), no insiste con Chato/RET-10 cuando se acaba el cupo y abre alto (Abuela 5 → pedimos 18-50).
2. **Los niveles altos eligen primero.** Antes Abuela (nivel 1) se quedaba las cartas que Pilar (nivel 3) también compra.
3. **SAL-07 protegida** (`no_vender` en `t7/hoy.json`): se guarda para cambiarla por RET-08. Ni a Pilar en la fiebre ni en El Rastro.
4. **Abuela ya no compra nuestras comunes** (paga ≈ 12 P y pesa poco): las guardamos para el Taller y Los Pícaros.
5. **El Cambista** compró en El Rastro una carta que nos vale 100 P por 48 P (+52).
6. GitHub (ramas, sin tocar main):
   - `infra/t7-regateador-vende-bien`: no abrir una compra que la caja no alcanza → [abrir PR](https://github.com/jllamazareslara/Team-7-Causa-Prima/pull/new/infra/t7-regateador-vende-bien)
   - `infra/t7-duelos-ii` (para Juan): descuento por ronda 0,92 (decay 0,08 de Duelos II) → [abrir PR](https://github.com/jllamazareslara/Team-7-Causa-Prima/pull/new/infra/t7-duelos-ii)

## Próximos pasos
| Hora | Qué | Por qué |
|---|---|---|
| ahora | **Taller (The Workshop)**: 3 comunes repetidas → 1 poco común (`noche-03-10/taller.py --live`) | Gratis según las reglas. La poco común se vende a Pilar = primer trato de nivel 3 |
| ≈ 17:35 | **Los Pícaros abren** (nivel 4, el que más pesa): 3 ventas de comunes repetidas | Compran comunes. Un vigilante añade su menú solo en cuanto abren |
| ≈ 18:04-20:04 | **Fiebre Salamanca** en Pilar (+25 % en SAL) | Automático por el calendario; SAL-07 queda fuera |
| cuando haya caja | **RET-08 en Abuela** (≤ 24 P) | Completa El Retiro (nos faltan RET-08 y RET-10) |
| ≈ 20:15 | Parar Cambista y vendedores antes de los duelos | |
| ≈ 20:34 | **Duelos II** (Juan): 2 rondas, 16 ticks, −8 %/ronda | Ceder el día si pesa poco, mantener precio, cerrar pronto |
| domingo ≈ 11:35 | +150 P → **RET-10** (Chato ≈ 82 P) | Página El Retiro completa |

## ⚠️ Para Juan
- **No crear `team7-main/cadena/runs/STOP` para parar el Cambista**: `duelos.py` usa la misma carpeta y también se pararía. El Cambista se para por su número de proceso.
- La rama `infra/t7-duelos-ii` pone `descuento_ronda` a 0,92: con el decay real, la Duelista acepta antes un buen precio.

## Lo que no sabemos
- Si el +25 % de la fiebre cuenta para la escalera o solo para el precio.
- Rumor de Radio Rastro «Abuela ya no compra comunes»: sin confirmar.
- Horario real del domingo (el calendario muestra eventos después del cierre de las 15:00): preguntar a la mesa.
- Por qué tenemos −11,9 P en tratos entre equipos.
