# VALOR.md — Cómo se define nuestro valor (Team 7)

Información base para **todos** los agentes (dealer, broker, duel, trades entre equipos) y para cualquier persona que
escriba reglas. Antes de negociar o decidir, parte de aquí: el marcador solo cuenta **valor creado medido con
nuestros valores privados** (`your_value`), nunca el número de operaciones.

Fuentes: `RULES.md` (sección *Cards* y *Scoring*), `README.md` (*Private values*), *The Bazaar – Kickoff.pdf*
(diapositiva "Same card, two values") y la captura real de nuestra cuenta en `dealers/test_data/` (`me.json` =
`GET /api/me`, `values.json` = `GET /api/me/value` para cada carta, tick 130 del viernes). La fórmula de abajo se
ha deducido de esa captura y cuadra exactamente con el `collection_value` que devuelve el servidor.

> **Fuente de verdad: el servidor.** Esta fórmula sirve para entender y anticipar, pero en vivo manda siempre lo que
> devuelvan `GET /api/me` y `GET /api/me/value?card=...`. Si no coinciden, gana el servidor y hay que actualizar este
> archivo.

---

## 1. De dónde sale el valor (API)

| Llamada | SDK | Qué devuelve | Para qué sirve |
|---|---|---|---|
| `GET /api/me` | `b.me()` | `assets[]` con `your_value` en cada carta/sobre, `affinity`, `album`, `collection_value`, `score` | **Valor de lo que tenemos**: lo que perderíamos si damos esa copia |
| `GET /api/me/value?card=LAV-03` | `b.value("LAV-03")` | `{card, your_value}` | **Valor de UNA copia más** de esa carta: lo máximo que ganamos si la conseguimos |

Campos útiles de `GET /api/me`:

- `affinity`: nuestros multiplicadores por barrio (ver §2).
- `assets[].your_value`: valor privado de cada copia que tenemos (también los sobres cerrados).
- `album.pages[]`: por barrio, `have` / `of` (10 cartas de página), `complete`, `master`.
- `collection_value`: suma del valor de toda nuestra colección (cartas + sobres cerrados).
- `score`: puntuación en vivo (la pública del leaderboard se refresca cada pocos minutos).

## 2. Multiplicador por barrio (privado)

Todos los equipos reciben **los mismos seis multiplicadores, barajados**: cada equipo valora más unos barrios que
otros. Nadie ve los de los demás y nosotros no vemos los suyos.

Los nuestros (captura de `GET /api/me` → `affinity`):

| Barrio | Set | Multiplicador | Prioridad |
|---|---|---|---|
| La Latina | `LAT` | **1.6** | 1ª |
| El Retiro (sábado) | `RET` | **1.3** | 2ª |
| Lavapiés | `LAV` | **1.1** | 3ª |
| Chamberí (domingo) | `CHA` | **0.9** | 4ª |
| Salamanca | `SAL` | **0.7** | 5ª |
| Malasaña | `MAL` | **0.5** | 6ª |

Consecuencia directa: la misma carta vale **3,2 veces más** para nosotros en La Latina que en Malasaña, y otro
equipo puede tener justo el reparto contrario. Ahí está el valor de comerciar.

## 3. Precio base por rareza (`book`)

De `GET /api/catalog` (también en `dealers/test_data/catalog.json`):

| Rareza | `book` (P) | Tirada | Cartas por barrio |
|---|---|---|---|
| common | 10 | 300 | 5 |
| uncommon | 25 | 90 | 3 |
| rare | 70 | 30 | 2 |
| epic | 180 | 9 | 1 |
| legendary | 450 | 3 | 1 |

Una **página** = los 5 commons + 3 uncommons + 2 rares de un barrio (10 cartas, `book` total 265 P). La épica y la
legendaria van "encima" de la página. Hay también una carta oculta (`hidden`): solo prestigio, ningún dealer la compra.

## 4. La fórmula

```
base(carta)        = book[rareza] × multiplicador[barrio]

valor de la copia nº k de la misma carta:
    1ª copia       = 1.00 × base
    2ª copia       = 0.25 × base
    3ª y siguientes= 0.10 × base

bonus de página    = 0.25 × 265 × multiplicador[barrio]       (al completar las 10 cartas de página)
bonus épica+legendaria sobre página completa ("master") = "un poco más" — cantidad no observada todavía
```

Y cómo lo reporta el servidor:

- **`your_value` de una carta que tenemos** (`GET /api/me`) = lo que perderíamos al quedarnos sin esa copia.
  Si tenemos 2 copias de LAT-03, **las dos** aparecen con 4.0 (= 0.25 × 16), porque cualquiera de ellas es la
  repetida. Si solo tenemos una, aparece con su valor completo.
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

## 7. Pendiente de confirmar en vivo

- Multiplicadores: la captura es del viernes; confirmar que `affinity` no cambia (las reglas dicen que se asignan
  una vez, barajados).
- Cuánto suma exactamente el bonus de épica + legendaria sobre página completa (`master`).
- Si `your_value` de las cartas de una página ya completa incluye el bonus de página (deducido, no observado).
