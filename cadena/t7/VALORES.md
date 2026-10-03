# Valores: cómo puntúa el juego y qué confirma la API en vivo

Anexo de referencia para `cadena/t7/valor.py` (El Guardia). La fórmula y las constantes de ese módulo
(`FACTOR_COPIA = [1.0, 0.25]` + resto `0.1`, `bono = 0.25`, `bono_extra = 0.10`, `NUESTROS_MULT`) coinciden
con lo confirmado aquí abajo llamando a `GET /api/catalog` y `GET /api/me` (§7). Este archivo documenta el
porqué de esos números con casos reales; `valor.py` es el código que los usa y los actualiza en caliente
con `configurar(afinidad, catalogo, cartas)` cuando alguien le pasa datos frescos de la API.

- **`your_value` de `GET /api/me/value`** = lo que ganaríamos con una copia más, **incluyendo el bonus de página**
  si esa carta completa la página (`smart_agent.py` ya lo usa así).
- **Sobres cerrados** también tienen `your_value` (valor esperado); entran en `collection_value`.
- `collection_value` = Σ por carta distinta de sus copias (1 + 0.25 + 0.10 + ...) × base + bonus de páginas + sobres.

### Comprobación con la captura real

| Caso | Cálculo | Servidor |
|---|---|---|
| LAT-04 común, 1 copia | 10 × 1.6 = 16 | 16.0 ✔ |
| LAT-03 común, 2 copias (cada una) | 0.25 × 16 = 4 | 4.0 ✔ |
| Una 3ª copia de LAT-03 | 0.10 × 16 = 1.6 | 1.6 ✔ |
| MAL-12 legendaria, no la tenemos | 450 × 0.5 = 225 | 225.0 ✔ |
| LAT-09 rara, no la tenemos (página LAT 8/10: no completa) | 70 × 1.6 = 112 | 112.0 ✔ |
| **LAV-10 rara, completaría la página LAV (9/10)** | 70 × 1.1 + 0.25 × 265 × 1.1 = 77 + 72.9 | **149.9 ✔** |
| `collection_value` | cartas 482.0 + sobre 47.8 | 529.8 ✔ |

## 5. Reglas base para todos los agentes

Son consecuencias directas de cómo se puntúa (no estrategias): cualquier regla de agente debería respetarlas.

- **V1 · Ganancia = valor recibido − valor entregado**, todo medido en `your_value` y primas. Una operación solo
  suma si esa diferencia es positiva. El número de operaciones no puntúa.
- **V2 · Comprar:** nunca pagar más que `GET /api/me/value?card=...` de esa carta (lo que vale *una copia más*).
- **V3 · Vender / dar:** nunca aceptar menos que el `your_value` de esa copia en `GET /api/me`. Si la comisión del
  venue la pagamos nosotros (El Rastro: 5 % + 1 P por carta), hay que sumarla para no perder valor.
- **V4 · Refrescar el valor después de cada operación.** El valor es marginal: comprar una carta convierte la
  siguiente copia en repetida (×0.25) y vender la única copia la deja a valor completo. No reutilices valores viejos.
- **V5 · Las repetidas valen poco para nosotros y mucho para quien no la tiene:** son nuestra moneda de cambio.
  Al dar una repetida, damos la copia con menor `your_value`.
- **V6 · La carta que completa una página vale mucho más** (bonus = 0.25 × 265 × multiplicador). Vigilar
  `album.pages[].have` = 9 de 10: esa carta que falta es prioritaria, y cualquier carta de una página completa
  valdrá también el bonus si la damos (perderíamos la página).
- **V7 · Prioridad por barrio** según §2: a igualdad de rareza, LAT > RET > LAV > CHA > SAL > MAL.
- **V8 · Valores privados:** no revelar nunca nuestros multiplicadores ni `your_value` en mensajes a otros equipos
  o dealers. Lo que otros digan de sus valores pueden ser palabras; solo vincula la oferta estructurada.

## 6. Qué no cubre este archivo

- **Duelos:** no usan `your_value`. Cada duelo trae su propio límite (`your_limit`: coste si vendemos, valor si
  compramos) y en las sesiones de dos temas `your_days_weight`.
- **Market Test (broker):** los compradores y vendedores sintéticos traen su propio valor/coste oculto; nuestro
  `your_value` no interviene.
- **Escalera de dealers:** puntúa la parte del rango de precio del dealer que capturamos; aun así V2/V3 evitan
  pagar más de lo que la carta vale o vender por debajo de su valor.

## 7. Confirmado en vivo (tick 272, sáb 2026-10-03, `GET /api/catalog` y `GET /api/me`)

- **Constantes oficiales de `catalog().values`**: `copy_marginals: [1.0, 0.25, 0.1]`, `page_bonus: 0.25`,
  `master_bonus: 0.1`. Esto confirma exactamente los multiplicadores de copia (1ª, 2ª, 3ª) y el 0.25 usado en el
  bonus de página de la tabla de arriba — no son valores inferidos, están en la API.
- **`affinity` de Team 7 ahora mismo**: `LAV 1.1, MAL 0.5, LAT 1.6, SAL 0.7, RET 1.3, CHA 0.9`. Coincide con los
  multiplicadores usados en los ejemplos de este documento (LAT 1.6, MAL 0.5, LAV 1.1) — **no ha cambiado** desde
  que se escribieron, confirmando que se asignan una vez y no varían en vivo.
- **El bonus de página SÍ está incluido en `your_value` de cualquier carta de una página ya completa**, no solo en
  la carta que la completó. Con la página LAV ya completa (10/10) ahora mismo:
  - `LAV-04` (común, 1 sola copia): `your_value = 83.9` = 10×1.1 + 0.25×265×1.1 (11 + 72.9). Si la diéramos,
    la página pasaría a 9/10 y perderíamos el bonus — por eso vale tanto aunque no sea "la carta que faltaba".
  - `LAV-09` y `LAV-10` (raras, 1 copia cada una): ambas `your_value = 149.9` = 70×1.1 + 72.9, mismo motivo.
  - Confirma que 265 = suma de `book` de las 10 cartas de página de un set (5 comunes×10 + 3 unco×25 + 2 raras×70).
- **3ª+ copia con el mismo patrón**: `MAL-04` (común, book 10, afinidad 0.5), con 3 copias en mano, cada una
  muestra `your_value = 0.5` = 0.10 × 10 × 0.5 (el marginal de la 3ª copia). Consistente con `copy_marginals`.
- **Pendiente real, sin confirmar todavía**: el `master_bonus = 0.1` (bonus adicional por tener también épica +
  legendaria del set, con `album.pages[].master = true`). Ningún equipo tiene aún epic/legendary de LAV
  (`minted: 0` en catálogo para LAV-11 y LAV-12), así que no hay un caso real en vivo para verificar la fórmula
  exacta de `master_bonus` todavía — solo sabemos que la constante es 0.1 (vs 0.25 de `page_bonus`).
- **4ª copia en adelante**: `copy_marginals` solo trae 3 valores (`[1.0, 0.25, 0.1]`); no hay ninguna carta en
  nuestra colección con 4+ copias ahora mismo para confirmar si el marginal de la 4ª es 0 o repite 0.1.
