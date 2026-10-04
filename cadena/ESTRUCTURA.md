# La estructura de la cadena · Team 7 (domingo 4/10)

Sin Director. Tres capas. Desde el 4/10 no hay Ojeador: lo que servía (vendedores que descansan, precios del tablón y
del feed) lo guardan los Ojos. El Regateador y el Cambista son ahora **un solo Comerciante** con dos canales.

```
                              EL JUEGO  ◄──────────────── firma ─────────────┐
            ┌──────────────────┬──┴───────────────┐                          │
          Ojos  ──────────►  Contable            Guion                      │   ← 1 · leen y miden
  (cómo estamos, las mejores  (¿renta? ¿cuánto?)  (anticipa lo               │
   oportunidades, el tablón,                      que viene)                 │
   vendedores que descansan)   │                                             │
          ┌────────────────────┴───────────┐                                 │
     Comerciante                       Duelista                              │   ← 2 · negocian
   UNA decisión, dos canales:            duelos                              │
   vendedores (tienda.py)            + Portavoz · Escudo · Espía             │
   El Rastro (cambista.py)                                                   │
   + Portavoz · Escudo · Observador · Espía                                  │
          └────────────────────┬───────────┘                                 │
                            Guardia  ── el único que firma ──────────────────┘   ← 3 · firma
                               │
                       Diario y avisador

Los Ojos van también en su ventana (`ojos.py`, cada 12 s): solo leen y proponen; quien acepta ahí es una persona.
Sin Director: las flechas con EL JUEGO las pone un programa que no es un agente: `jugar.py` (vendedores y El Rastro).
Fuera de la cadena: El Vigía (solo lee, enseña en pantalla lo que viene) · El Casamentero y El Grabador (Market Test)
```

## Quién mira qué

| Papel | Nombre | Archivo |
|---|---|---|
| El presente: cómo estamos (`/api/me`) y las mejores oportunidades (`/api/feed`, `/api/me/offers`, tablón). Sin Escudo ni Guardia | Los Ojos | `t7/ojos.py` (`leer()` y `mirar()`): la vista de cada tick |
| La memoria del mercado: quién vende y pide qué en El Rastro, tratos del feed, vendedores que descansan | Los Ojos | `t7/ojos.py` (`observar`, `observar_feed`, `apuntar_mercado`, `descanso`), guardado por `cadena.ojear()` |
| Cuánto vale y cuánto renta | La Contable | `t7/contable.py`, con la calculadora `t7/valor.py` |
| El futuro del juego · anticipar la estrategia según lo que viene | El Guion | `t7/guion.py` |
| Enseñárselo al equipo en pantalla | El Vigía | `vigia.py` |

Nadie predice los precios. Ya no se espera a que una compra baje, ni se sube un anuncio por el momento del juego o
la escasez: si la Contable dice que renta, se hace.

## Qué recibe cada negociador

| Negociador | De la Contable | De los Ojos y el Guion |
|---|---|---|
| Comerciante | nuestro valor; tope o suelo; si una oferta de El Rastro renta, y cuánto | último trato del feed (no se paga más ni se vende por menos); si El Rastro lo da mejor (entonces no con el vendedor); vendedores que descansan; propuestas validadas; cartas guardadas para una fiebre (Guion) |
| Duelista | nuestro límite | nada: un duelo no tiene precio de mercado (el Guion solo avisa «duelo en 30 min») |

Los Ojos y el Guion solo aconsejan: no mandan mensajes ni firman. Firma solo el Guardia, y solo lo que la Contable dice que renta.

## Dónde vive cada cosa en el código

Todo vive en `t7/` y se llama desde `t7/cadena.py`. La conexión con el juego la hace un programa que no es un agente:
`jugar.py` (vendedores y El Rastro) y `duelos.py` (duelos).

| Función | Cuándo | Qué hace |
|---|---|---|
| `cadena.tick(lectura, mem, ...)` | cada tick | toda la cadena; empieza llamando a `ojear()` |
| `cadena.ojear(lectura, mem)` | al empezar el tick, sola | los Ojos guardan calendario, niveles, feed, tablón y cierres de vendedores; deja en la lectura la `hora` |
| `comerciante.vendedor()` · `rastro()` · `propuestas_ojos()` | dentro del tick | los dos canales del Comerciante y las propuestas de los Ojos, hasta la cola del Guardia |
| `comerciante.operaciones(cuenta, efectivo, menus, mem, lectura, ...)` | para abrir conversaciones con vendedores | qué abrir con cada vendedor libre, con los consejos del Guion y los Ojos |
| `comerciante.anuncios(cuenta, p, mem, lectura, ...)` | para anunciar en El Rastro | qué anunciar y a cuánto, sin las cartas guardadas y nunca por menos que el último trato |

## Lo que tiene que hacer el programa que lance la cadena

Leer el juego y poner en `lectura`, tal cual llega:

| Clave | De dónde | Cada cuánto |
|---|---|---|
| `tick`, `efectivo`, `cuenta`, `vendedores`, `duelos`, `tablon` | `/api/clock`, `/api/me`, conversaciones, `/api/duels`, `/api/venues/rastro/offers` | cada tick (el tablón, uno de cada tres) |
| `t_hours`, `tick_segundos` | `/api/clock` | cada tick |
| `calendario` | `/api/schedule` | cada 20 ticks |
| `feed` | `/api/feed` | cada 6 ticks |
| `niveles` | `/api/dealers` → `{vendedor: level}` | cada 20 ticks |
| en cada vendedor cerrado: `cerrado`, `until_tick` | `closed_reason`, `until_tick` de la conversación | cuando cierra |

Después: `cadena.tick()`, aplicar sus mensajes y su única firma, y llamar a `comerciante.operaciones()` y
`comerciante.anuncios()` para abrir conversaciones y anunciar. Lo que falte en la lectura se salta: la cadena sigue sin ese consejo.

## Estado

217 pruebas sin red, todas pasan (`python -m unittest discover -s tests`, con `estado-actual.json` un nivel por encima).
