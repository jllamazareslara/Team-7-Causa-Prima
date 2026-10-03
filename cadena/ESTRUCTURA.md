# La estructura de la cadena · Team 7 (sábado 3/10, mediodía)

Sin Director. Tres capas. El dibujo está en el artefact Team 7, pestaña «Los agentes», apartado «El esquema».

```
                              EL JUEGO  ◄──────────────── firma ─────────────┐
            ┌──────────────────┬──┴───────────────┬──────────────────┐        │
          Ojos  ──────────►  Contable            Guion            Ojeador     │   ← 1 · leen y miden
     (leen el juego)      (¿renta? ¿cuánto?)  (anticipa lo      (vigila los   │
      + Escudo: texto                          que viene)        precios)     │
        sospechoso             │                          ┊ precios ┊         │
          ┌────────────────────┼────────────────────┐   ┊         ┊          │
       Cambista             Duelista            Regateador ◄┄┄┄┄┄┄┄┘          │   ← 2 · negocian
   El Rastro, equipos        duelos              vendedores                   │
     + Portavoz          + Portavoz · Espía   + Portavoz · Observador · Espía  │
          └────────────────────┼────────────────────┘                         │
                            Guardia  ── el único que firma ───────────────────┘   ← 3 · firma
                               │
                       Diario y avisador

El Ojeador pasa los precios al Cambista y al Regateador. Sin Director: las flechas con EL JUEGO las pone un
programa que no es un agente: `jugar.py` (vendedores y El Rastro).
Fuera de la cadena: El Vigía (solo lee, enseña en pantalla lo que viene) · El Casamentero y El Grabador (Market Test)
```

## Quién mira qué

| Papel | Nombre | Archivo |
|---|---|---|
| El presente: leen el juego y pasan los números a la Contable; su ayudante, el Escudo, mira el texto sospechoso | Los Ojos | `t7/ojos.py` (`mirar()`): la vista de cada tick |
| Cuánto vale y cuánto renta | La Contable | `t7/contable.py`, con la calculadora `t7/valor.py` |
| El pasado del mercado · el vigilante de precios | El Ojeador | `t7/ojeador.py` |
| El futuro del juego · anticipar la estrategia según lo que viene | El Guion | `t7/guion.py` |
| El futuro del mercado | El Ojeador, con el calendario del Guion | `t7/ojeador.py`, `momento()` |
| Enseñárselo al equipo en pantalla | El Vigía | `vigia.py` |

Nadie predice los precios: el futuro del mercado sale del calendario (final del juego, dinero para todos, la víspera de ese dinero) y de seguir la tendencia de los precios pasados.

## Qué recibe cada negociador

| Negociador | De la Contable | Del Guion y el Ojeador |
|---|---|---|
| Cambista | si una oferta renta, y cuánto | comprar ya o esperar; precio de cada anuncio; cartas guardadas para una fiebre |
| Regateador | nuestro valor y nuestro tope | vendedor que descansa; carta que se agota; El Rastro más barato; cartas guardadas; niveles de la escalera |
| Duelista | nuestro límite | nada: un duelo no tiene precio de mercado (el Guion solo avisa «duelo en 30 min») |

El Guion y el Ojeador solo aconsejan: no mandan mensajes ni firman. Firma solo el Guardia, y solo lo que la Contable dice que renta.

## Dónde vive cada cosa en el código

Todo vive en `t7/` y se llama desde `t7/cadena.py`. `director.py` se quitó y no es parte del flujo. La conexión con el
juego la hace un programa que no es un agente: `jugar.py`, vendedores (el Regateador) y El Rastro (el Cambista). Duelos: pendiente.

| Función | Cuándo | Qué hace |
|---|---|---|
| `cadena.tick(lectura, mem, ...)` | cada tick | toda la cadena; empieza llamando a `ojear()` |
| `cadena.ojear(lectura, mem)` | al empezar el tick, sola | guarda calendario, catálogo, feed, niveles y cierres de vendedores; deja en la lectura `hora`, `momento` y `escasez` |
| `cadena.operaciones(cuenta, efectivo, menus, mem, lectura, ...)` | para abrir conversaciones con vendedores | la cola del Regateador con los consejos del Guion y el Ojeador |
| `cadena.anuncios(cuenta, p, mem, lectura, ...)` | para anunciar en El Rastro | los anuncios del Cambista sin las cartas guardadas y con el precio del Ojeador |

## Lo que tiene que hacer el programa que lance la cadena

Leer el juego y poner en `lectura`, tal cual llega:

| Clave | De dónde | Cada cuánto |
|---|---|---|
| `tick`, `efectivo`, `cuenta`, `vendedores`, `duelos`, `tablon` | `/api/clock`, `/api/me`, conversaciones, `/api/duels`, `/api/venues/rastro/offers` | cada tick (el tablón, uno de cada tres) |
| `t_hours`, `tick_segundos` | `/api/clock` | cada tick |
| `calendario` | `/api/schedule` | cada 20 ticks |
| `catalogo` | `/api/catalog` | cada 20 ticks |
| `feed` | `/api/feed` | cada 6 ticks |
| `niveles` | `/api/dealers` → `{vendedor: level}` | cada 20 ticks |
| en cada vendedor cerrado: `cerrado`, `until_tick` | `closed_reason`, `until_tick` de la conversación | cuando cierra |

Después: `cadena.tick()`, aplicar sus mensajes y su única firma, y llamar a `cadena.operaciones()` y `cadena.anuncios()` para abrir conversaciones y anunciar. Lo que falte en la lectura se salta: la cadena sigue sin ese consejo.

## Estado

116 pruebas sin red, todas pasan (`python -m unittest discover -s tests`, con `estado-actual.json` un nivel por encima). Nada se ha lanzado todavía contra el juego.
