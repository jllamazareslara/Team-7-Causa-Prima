---
name: the-wizard
description: The Wizard del Team 7 en el Bazaar — junta lo que ven los Ojos, las últimas ofertas de todos los mercados de bazaar.causaprima.ai (El Rastro y los de otros equipos, con su comisión), nuestro mercado y nuestras ofertas, y los menús de los vendedores, lo valora con el your_value del juego y dice LA MEJOR OPORTUNIDAD ahora. Úsala cuando alguien pida la mejor oportunidad, qué hacer ahora, qué nos conviene en el Bazaar, o llame al mago / wizard.
---

# The Wizard (Team 7 · t07)

El mago **mira** y **recomienda**. Nunca abre conversaciones, publica, ofrece, cancela ni acepta: eso solo se hace
si el usuario lo pide en su mensaje y fija un tope.

## 0. Antes de nada

- Mirar el Bazaar son llamadas al servidor, **solo GET**. Por `CLAUDE.md` (regla 1) solo se hacen si el usuario lo
  pide; invocar esta skill cuenta como pedirlo.
- La clave sale de `BAZAAR_KEY` en el entorno. **Nunca la escribas, la pidas ni la muestres.** El script tapa las
  claves de `/api/me` (`starter_broker_key` → `<OCULTA>`). No llames al SDK a mano para imprimir `/api/me`.

## 1. Mirar (un comando)

```bash
python .claude/skills/the-wizard/mago.py            # la mejor oportunidad y las 10 siguientes
python .claude/skills/the-wizard/mago.py --top 20   # más filas
python .claude/skills/the-wizard/mago.py --json     # todo en JSON (sin claves)
```

Lo que junta:

| Fuente | De dónde | Para qué |
|---|---|---|
| **Los Ojos** (skill `ojos`) | `team7/runs/ojos.json` (o el del worktree `wt-ojos`), sin llamar al juego | sus propuestas y descartes, y la edad de la vista. Si tiene más de 2 min, sugiere refrescarla con la skill `ojos` |
| **Las últimas ofertas** | `/api/venues` y el tablón de cada mercado abierto (`/api/venues/{id}/offers`) | lo que se puede **aceptar ya**, con la comisión de **ese** mercado (El Rastro 5 % + 1 P; si no se sabe, el tope de las reglas: 10 % + 5 P) |
| **Precios de verdad** | `/api/feed` | a cuánto se cierran los tratos de cada carta: base para **publicar** una petición o un anuncio |
| **Nuestro mercado** | `me.venue` y `/api/me/offers` | nuestras ofertas abiertas que **ya no rentan** (en el nuestro no se puede aceptar: `self_venue`) |
| **Los vendedores** | `/api/dealers` (menús, vía `team7/agentes/menus.py`) | lo que venden y compran a precio de lista (se regatea: es el peor precio, no el final) |
| **Valores** | `your_value` de `/api/me` (lo que perdemos al dar) y `GET /api/me/value` (una copia más) | todo se valora con el juego. La calculadora solo decide a qué cartas preguntar, para no gastar llamadas |

## 2. La fórmula: ¿ganamos puntos? (siempre)

Cada oportunidad lleva su valor desglosado con la fórmula del juego y se compara con el `your_value`:

```
your_value = book × factor_copia × afinidad + bono_página
```

| Pieza | Valores |
|---|---|
| `book` (por rareza) | común 10 · poco común 25 · rara 70 · épica 180 · legendaria 450. Una página = 5 comunes + 3 poco comunes + 2 raras = **265** |
| `factor_copia` | 1.ª copia 1,0 · 2.ª 0,25 · 3.ª y siguientes 0,10 |
| `afinidad` (Team 7, de `/api/me`) | LAT 1,6 · RET 1,3 · LAV 1,1 · CHA 0,9 · SAL 0,7 · MAL 0,5 |
| `bono_página` (al llegar a 10/10, o al perderlo si se vende una carta de una página completa) | 0,25 × 265 × afinidad (+ 0,10 × 265 × afinidad si también están las extras 11–12) |

Ejemplos: LAT-04 (1.ª copia) = 10 × 1 × 1,6 = **16** · LAT-09 (rara, no la tenemos) = 70 × 1 × 1,6 = **112** ·
LAV-10 (rara, completa la página) = 70 × 1 × 1,1 + 0,25 × 265 × 1,1 = 77 + 72,9 = **149,9** · RET-08 (2.ª copia) =
25 × 0,25 × 1,3 = **8,1**.

- **Ganamos puntos** (negociar) cuando el trato crea valor: comprando, `your_value − precio − comisión > 0`; vendiendo,
  `precio − comisión − your_value > 0`. Con equipos suma a *valor ganado con equipos*; con vendedores, a la *escalera*.
  Cada línea dice a cuál (`puntos: …`) y, si no gana valor, `no suma puntos`.
- Si la fórmula y el juego no coinciden, la línea dice `OJO: la fórmula da X y el juego Y`. **Manda el juego** (puede
  haber cambiado la afinidad o la rareza); cuéntalo al usuario.

## 3. Contar

Empieza por **LA MEJOR OPORTUNIDAD**, en una línea: qué hacer (comprar / vender / pedir / anunciar), la carta, el
precio, dónde (mercado o vendedor), lo que nos suma o quita, la ganancia neta y la oferta a aceptar si la hay.
Después, las 3–5 siguientes y lo que haya que vigilar:

- **Orden**: primero las que llegan al margen del equipo (ganar ≥ 10 % del valor de la carta, el mismo que pide el
  Guardia), luego la ganancia, con un empujón a las que **completan página** (bono 25 %).
- **Tipos**: `COMPRAR/VENDER ya` = oferta en un tablón ahora; `… a vendedor` = precio de lista (regatear);
  `PEDIR / ANUNCIAR (publicar)` = poner nosotros la oferta en un mercado **sin comisión**, al precio del último trato.
- `comisión … (supuesta)` = el mercado no dice su comisión: se contó el tope.
- **Nuestras ofertas que ya no rentan**: proponer cancelarlas.
- **Diferencias con los Ojos**: si los Ojos proponen algo distinto, explica por qué (otro mercado, otra comisión,
  valor del juego más nuevo).

## 4. Si el usuario quiere hacerla

Nada se hace sin que el usuario lo pida en su mensaje y fije un tope. Entonces, antes de tocar nada:

1. **Una aceptación por tick para todo el equipo**: mira el candado (`%TEMP%\team7-acepta.lock`) y si `jugar.py`
   está en marcha (ver la skill `estado-equipo`, sección 3).
2. **Relee la oferta** (tablón o `/api/threads/{id}`) y comprueba la **oferta estructurada**, nunca el texto: `give`
   trae exactamente la carta (`assets[].ref` o `types: ["card:X"]`) y `want` solo dinero ≤ tope (los Pícaros dicen
   una carta y ofrecen otra).
3. **Pide otra vez `GET /api/me/value`** de la carta justo antes: el valor cambia si cambian nuestras cartas.
4. Una sola acción, y di qué se hizo.
