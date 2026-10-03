# Para Ana: El Cambista

El que negocia con los **otros equipos** en El Rastro. Capa 2 de la estructura (ver `cadena/ESTRUCTURA.md`), junto a la
Duelista y el Regateador. Recibe las cuentas de la Contable y los consejos del Guion y el Ojeador
(carpeta `../ojos-guion-ojeador/`). No firma: lo que quiere aceptar pasa por el Guardia.

> El código está en [`cadena/t7/cambista.py`](../../cadena/t7/cambista.py): cualquier cambio se hace allí.
> El programa que lo juega en El Rastro es [`cadena/rastro.py`](../../cadena/rastro.py) (`--ticks 3` en seco, `--live` en vivo).

## Por qué importa

Con los vendedores solo cuentan los tres mejores tratos. Con los equipos cuenta **todo el valor ganado**, medido con
nuestros valores privados, y esos valores son muy distintos entre equipos: una repetida nos vale 0,5–4 y a quien le
falta para completar página le puede valer 50–150.

## Lo que hace ([`cambista.py`](../../cadena/t7/cambista.py))

| Función | Qué hace |
|---|---|
| `vendibles()` | qué podemos dar perdiendo poco (repetidas, barrios que nos valen poco); nunca una carta protegida |
| `oportunidades()` | cada oferta del tablón pasada por la calculadora, en los dos sentidos: las que nos conviene aceptar |
| `precio_anuncio()` | a cuánto anunciar una venta y cómo baja si caduca, nunca por debajo de lo que nos vale + 1 |
| `lista_compra()` | qué cartas nos faltan y cuál comprar primero; la página a la que le faltan 1 o 2 va arriba (bono del 25 %); mochila exacta si la caja es corta |
| `peticiones()` | lo que publicamos «pago X por esta carta»: abre bajo, sube si caduca, nunca pasa del tope |
| `trueques()` | cambios carta por carta: damos repetidas por cartas que nos faltan, sin efectivo |
| `mapa_deseos()`, `cazador_de_paginas()` | qué barrio valora cada equipo; quién pide una carta una y otra vez (a ese se le cobra caro) |

## Con el Guion y el Ojeador (desde `cadena/t7/cadena.py`)

- **Antes de aceptar una compra que renta**, pregunta al Ojeador `comprar_ahora()`: «ya» si completa página, se agota,
  sube o es la más barata vista; «espera» si baja con varios vendiendo y el margen es pequeño.
- **Al anunciar** (`cadena.anuncios()`): el Guion quita las cartas que esperan una fiebre (hoy Salamanca, para Doña Pilar)
  y el Ojeador pone el precio según el mercado y el momento del juego.

## Ajustes

En `cadena/t7/parametros.json`, los que empiezan por `cambista.` y `rastro.` (`rastro.publicar` y `cambista.pedir`
vienen a 0: enseña lo que haría y no manda nada hasta que el equipo lo encienda).

## Pruebas

Desde `cadena/`: `python -m unittest tests.test_todo.Cambista tests.test_todo.CambistaCompras -v`.

## Hecho el sábado a mediodía (lo que faltaba)

1. **Prueba en seco contra el juego real**: hecha (3 ticks, sin mandar nada). Ver `cadena/PRUEBA-EN-SECO-03-10.md`.
   El Cambista preparó anuncios, lista de la compra, peticiones y cambios con las cartas reales.
2. **Venta y compra encendidas**: `rastro.publicar` = 1 y `cambista.pedir` = 1 en `cadena/t7/hoy.json`. Solo publica
   cuando se lanza en vivo.
3. **Márgenes iguales**: `oportunidades(..., p=...)` solo propone lo que el Guardia firma (neto ≥ 10 % del valor).
4. **Un solo programa acepta**: `cadena/t7/candado.py`. `rastro.py` lo toma en vivo; `play.py` debería tomarlo también.
5. **Datos de prueba**: `cadena/datos/estado-actual.json`.

Vendedores y duelos siguen dependiendo del programa que los juegue (`play.py`).
