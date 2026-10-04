---
name: ojos
description: Los Ojos del Team 7 en el Bazaar — lo ven todo, lo validan con la Contable y proponen: cómo estamos y qué oferta aceptar ahora (cartas que nos faltan a la venta, quién paga por nuestras repetidas, precios de los tratos, avisos del juego, ofertas que nos hacen). Lee /api/me, /api/feed, /api/me/offers y el tablón. Úsala cuando alguien pregunte qué oportunidades hay, qué nos conviene comprar o vender ahora, qué dicen los Ojos, o quiera lanzar o parar los Ojos.
---

# Los Ojos (Team 7 · t07)

Los Ojos **ven** todo (/api/me, /api/feed, /api/me/offers, tablón), **validan** cada oportunidad con la Contable
(su ficha: valor que entra y sale, comisión de El Rastro, reserva de caja, protegidas, margen del equipo, y el
your_value del juego cuando lo hay) y **proponen** las que pasan. Solo proponen: nunca abren, ofrecen ni aceptan
nada, y no pasan por el Escudo ni por el Guardia. El código es
`cadena/t7/ojos.py` (`leer()` y `mirar()`); el programa que mira cada tick es `cadena/ojos.py`.

## 1. Mirar

1. **Si los Ojos están en marcha**, no hace falta llamar al juego: lee `cadena/runs/ojos.json` (la última vista, con
   su `tick` y su `hora`). Se reescribe cada 12 s: si la hora tiene menos de 1 minuto, úsala.
2. **Si no están en marcha o la vista es vieja**, una mirada (es una llamada al servidor, solo GET; invocar esta skill
   cuenta como pedirla, por la regla 1 de `CLAUDE.md`):
   ```bash
   cd cadena && python ojos.py --ticks 1
   ```
   Escribe la vista en `cadena/runs/ojos.json`.

Nunca muestres claves: `/api/me` ya llega tapado (`starter_broker_key` → `<OCULTA>`). No llames al SDK a mano para
imprimir `/api/me`.

## 2. Contar lo que ven

Con `vista` de `ojos.json`, en este orden y en pocas líneas:

| Campo | Qué decir |
|---|---|
| `propuestas` | **lo primero**: qué aceptar (oferta `aceptar`, carta, precio, `neto`, `motivo`), la de más neto primero |
| `descartadas` | si preguntan por una oportunidad que no salió: por qué la Contable no la valida |
| `estado` | dinero, puntos y puesto (negociar / mercado); páginas `casi` completas y qué les falta (`faltan`); repetidas |
| `comprar` | las mejores: carta, precio, oferta, si **completa página** (bono 25 %). Para saber si renta, `estado.py --valor <CARTA>` (skill estado-equipo) |
| `vender` | quién paga por una repetida: precio, `nos_vale` (your_value de nuestra copia) y `margen` |
| `para_nosotros` | ofertas que nos hacen a nosotros: quién, qué da y qué pide |
| `precios` | precio de los tratos recientes por carta (feed) |
| `avisos` | avisos nuevos del juego (límites, vendedores, niveles…) |
| `abiertas` | ofertas nuestras abiertas (máx. 30) |

Las propuestas son propuestas, no órdenes: **nada de comprar, vender ni aceptar sin que el usuario lo pida y fije un tope**
(ver la skill estado-equipo, sección 2: la oferta estructurada manda, nunca el texto).

## 3. Lanzar y parar (como duelos.py)

- Lanzar sin parar (solo si el usuario lo pide): `cd cadena && python ojos.py` en segundo plano, con `BAZAAR_KEY` en
  el entorno. Hace unas 5 lecturas cada 12 s, muy por debajo del límite (5 por segundo). No lleva candado: puede ir a la
  vez que `duelos.py` y `jugar.py`.
- En su propia ventana: `cadena\lanzar-ojos.ps1` (mira cada 12 s, y cada mirada escribe su propuesta y las oportunidades; `-Segundos N` para cambiarlo, `-Ticks N` para
  parar tras N miradas).
- Parar: Ctrl + C, o crear `cadena/runs/STOP` (ojo: STOP es de todo el equipo: con él duelos.py y jugar.py también dejan de firmar).
- Registros: `cadena/runs/ojos.json` (última vista) y `cadena/runs/ojos.jsonl` (una línea por mirada).
