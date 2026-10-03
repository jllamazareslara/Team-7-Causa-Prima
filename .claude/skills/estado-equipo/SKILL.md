---
name: estado-equipo
description: Cómo está y cómo trabaja el Team 7 en el Bazaar — dinero, puntos, cartas, álbum, repetidas y programas en marcha — leído de GET /api/me. Úsala cuando alguien pregunte cuánto dinero o puntos tenemos, qué cartas nos faltan o sobran, si nos conviene comprar o vender una carta, o cómo funciona el equipo.
---

# Estado del equipo (Team 7 · t07)

## 0. Antes de nada

- Leer `/api/me` es una llamada al servidor. Por `CLAUDE.md` (regla 1) solo se hace si el usuario lo pide en ese
  mensaje (invocar esta skill cuenta como pedirlo). Es **solo lectura**: esta skill nunca abre conversaciones, ofrece
  ni acepta.
- `/api/me` devuelve `starter_broker_key`. **Nunca la muestres** ni la copies. Usa siempre el script, que tapa todas
  las claves; no llames a `b.me()` a mano para imprimirlo.

```bash
python .claude/skills/estado-equipo/estado.py                       # resumen
python .claude/skills/estado-equipo/estado.py --valor RET-06 RET-09 # + valor de UNA copia más (GET /api/me/value)
python .claude/skills/estado-equipo/estado.py --json                # todo, con claves tapadas
```

Con la salida, contesta lo que pidió el usuario. Si pregunta por el estado en general, da: dinero, puntuación y
puesto con su desglose, páginas del álbum (qué falta), repetidas y conversaciones abiertas.

## 1. Cómo leer `/api/me`

| Campo | Qué es |
|---|---|
| `cash` | primas (P). Se empieza con 400. Solo es medio: no puntúa por sí mismo |
| `level`, `unlocked` | nivel = nº de vendedores con los que podemos tratar (abuela, chato, pilar, picaros, banco…) |
| `assets[]` | cada carta con `ref`, `serial`, `rarity` y **`your_value`** (lo que vale PARA NOSOTROS esa copia) |
| `collection_value` | suma de nuestros valores privados |
| `album.pages[]` | por barrio: `have/of`, `complete`, `master`. Una página = cartas 01–10 (5 comunes, 3 poco comunes, 2 raras) |
| `score` | puntuación en vivo (el leaderboard público va con retraso) |
| `venue` | nuestro puesto (el starter `v11`, mecanismo auto) |
| `open_threads` | conversaciones abiertas (máx. 6 a la vez) |

**Puntos (`score`)**, según `RULES.md`: Negociar 30 % (`negotiating` ← `duel_points` duelos, `ladder_points`
escalera de vendedores, `neg_points` valor ganado con otros equipos), Mercado 30 % (`market` ← `bench_points` /
`bench_efficiency` del Market Test, `mm_points` valor creado en nuestro puesto), Jueces 40 % (no sale en la API).
**No puntúan**: número de tratos, comisiones, `luck` (lo que sale de sobres), regalos. `adjustments` = penalizaciones.

**Valores privados**: multiplicadores por barrio (`affinity`; los nuestros: LAT 1,6 · RET 1,3 · LAV 1,1 · CHA 0,9 ·
SAL 0,7 · MAL 0,5). Una **repetida vale muy poco para nosotros** (el valor fuerte va a la primera copia y al bono
de página): se vende o se cambia a quien le falta.

## 2. Antes de comprar o vender una carta

1. Mira si ya la tenemos (`assets`). Si sí, la siguiente copia vale mucho menos:
   `estado.py --valor <CARTA>` da el `your_value` de **una copia más**. No te fíes de estimaciones de "primera copia".
   (03/10: compramos un 2.º RET-09 a 64 P y una copia más nos valía 22,8.)
2. Compara con precios: menús de vendedores en `cadena/menus.json` (`vende` = nos venden a ese precio, `compra` =
   nos compran), y el tablón de El Rastro en `cadena/runs/memoria.json` → `mercado` / `historial`.
3. Prioriza lo que **completa página** (bono): mira qué falta en `album.pages`.
4. Comprueba la oferta **estructurada**, nunca el texto: `give` debe traer exactamente la carta pedida (`assets[].ref`
   o `types: ["card:XXX-NN"]`) y `want` solo efectivo ≤ tope. Los Pícaros dicen una carta y ofrecen otra (03/10:
   hablaban de RET-09 y la oferta daba `card:RET-08` a 73 P).
5. Nada de comprar o vender sin que el usuario lo pida y fije un tope.

## 3. Cómo trabaja el equipo

- **Reglas por miembro**: cada uno en `rules/<nombre>` (dealer, broker, duel), medidas offline con `bench/`
  (skill `aportar-reglas`). `main` no se toca para reglas.
- **La cadena** (`cadena/`, ver `cadena/LEEME.md` y `ESTRUCTURA.md`): `jugar.py` juega vendedores y El Rastro
  (Ojos → Contable → Cambista / Regateador → Guardia, con Guion y Ojeador). En seco por defecto; `--live` solo desde
  el ordenador con la clave. `duelos.py` juega los duelos por separado. `vigia.py` y `grabador.py` solo leen.
- **Una aceptación por tick para todo el equipo.** Quien acepte en vivo toma el candado
  (`t7/candado.py`, archivo `%TEMP%\team7-acepta.lock`); los duelos usan su propio candado
  (`cadena/duelos-acepta.lock`). Un candado de un pid que ya no existe está libre. Antes de aceptar algo a mano,
  mira quién lo tiene.
- **Parar todo**: crear `cadena/runs/STOP`.
- Registros: `cadena/runs/diario.jsonl` (tick a tick), `tratos.jsonl`, `errores.jsonl`, `memoria.json`
  (precios vistos, escasez, calendario).
- Límites del juego por tick: 1 aceptación, 1 mensaje por conversación, 12 anuncios nuevos; máx. 6 conversaciones y
  30 ofertas abiertas. Lo aceptado se liquida en el tick siguiente. `GET /api/clock` → `limits` tiene los vigentes.
- Claves: `BAZAAR_KEY` en el entorno, nunca en archivos, commits ni mensajes.
