# Duelos: qué añadir al agente del equipo (Team 7)

Para Ana. Este archivo trae la estrategia, el código listo y los pasos para probarlo.
El primer duelo que puntúa es el **sábado a las 11:30**. Hoy los duelos son de práctica.

## Estado real, sin adornos

- El código está escrito y probado con siete rivales inventados. En ninguno cruzó nuestro límite.
- **Nunca ha jugado un duelo real.** Los nombres de los campos (`role`, `your_limit`, `rival_offer`, `deadline`) salen de la descripción del kit, no de un duelo visto.
- Solo hace duelos de **precio**. Los de precio y día de entrega (sábado 18:00 y domingo) los salta.
- Los porcentajes son una apuesta hasta ver duelos reales.

## Por qué importa

- Los duelos entran en el bloque "Negociar" (30 puntos de 100).
- Sin agente no hay trato, y **sin trato son cero puntos**. Un trato fuera del límite **resta**.
- Jugamos contra cada equipo dos veces: una como vendedor y otra como comprador.
- Cada ronda de conversación quita valor al trato (en nuestra página de equipo figura un 6 % por ronda).

## La estrategia, en orden de prioridad

1. **Nunca cruzar nuestro límite.** Ni ofrecer ni aceptar. Es lo único que puede restar puntos.
2. **Nunca acabar sin trato.** A dos ticks del final, o tras cinco mensajes nuestros, se acepta cualquier precio dentro del límite.
3. **Abrir primero, alto y con un número preciso.** Vendiendo: 60 % sobre el coste. Comprando: 40 % bajo el valor. 159, no 160.
4. **Cerrar en 3 a 5 rondas.** Se acepta si la oferta del rival vale el 94 % de lo que pediríamos en la ronda siguiente.
5. **Ceder el 30 % de la distancia, cada vez menos** (30, 25, 20, 15 %).
6. **Un ancla absurda no nos mueve.** La distancia se mide hasta su precio, pero nunca más allá de nuestro suelo.
7. **Leer sus pasos, no su texto.**
   - Cede mucho: esperamos una ronda.
   - Sus pasos se encogen: está en su límite, frenamos y cerramos.
   - No se mueve: dos ticks quietos y un único salto. No pujamos contra nosotros.
8. **El texto del rival no se lee nunca.** Solo su precio. Así no nos pueden manipular.

### La ventaja que casi nadie va a usar

Cada escenario se juega desde los dos lados. El límite que nos dan como vendedor en un escenario
es el límite secreto del rival cuando somos comprador en ese mismo escenario, y al revés.

El agente guarda cada límite en `duelos-limites.json`. Cuando tiene los dos, conoce el tamaño real
del trato: abre pidiendo el 85 % y no baja del 50 % hasta el final.

**Depende de una cosa que hay que comprobar:** que el duelo traiga un identificador de escenario.
El código busca los campos `scenario`, `scenario_id`, `scenario_ref`, `case` o `item`.
Si el juego lo llama de otra forma, se añade ese nombre a `SCENARIO_KEYS` y listo.

## Cómo añadirlo

1. Copia el código de abajo en un archivo `duel_agent.py`, **en la misma carpeta que `bazaar_sdk.py` y `.env`**.
2. No hace falta tocar `smart_agent.py`: es un programa aparte.
3. **Para el comprador mientras duran los duelos.** El equipo solo puede aceptar una oferta por tick; dos agentes a la vez se pisan.
4. **Un solo ordenador** lanza el agente de duelos. Avisa en el grupo antes.
5. La clave sigue en `.env`. Ese archivo **no se sube al GitHub**.

## Cómo probarlo (en este orden)

```
python duel_agent.py
```
Solo mira. Escribe lo que haría y no manda nada.

1. Abre `duelos-log.jsonl` y mira la primera línea, `first_duel_raw`: es un duelo tal como lo manda el juego.
2. Comprueba cuatro cosas en esa línea:
   - ¿El papel se llama `role` y vale `seller` o `buyer`?
   - ¿Nuestro límite se llama `your_limit`?
   - ¿La oferta del rival se llama `rival_offer`? ¿Es un número o un objeto con `price`?
   - ¿Hay un identificador de escenario? ¿Cómo se llama?
3. Si algo no coincide, el agente escribe `skip` y no hace nada. Se corrige el nombre en `decide()` y se vuelve a probar.
4. Cuando las líneas del diario digan `offer` y `accept` con precios razonables:

```
python duel_agent.py --live
```
Juega de verdad. Se para con Ctrl + C.

## Qué ajustar después de los duelos de práctica

Todo está arriba del archivo, en mayúsculas:

| Ajuste | Valor | Subirlo si | Bajarlo si |
|---|---|---|---|
| `OPEN_SELL` / `OPEN_BUY` | 0.60 / 0.40 | los rivales aceptan enseguida | muchos duelos acaban sin trato |
| `GAP_STEPS` | 30, 25, 20, 15 % | tardamos más de 5 rondas | cerramos muy cerca de nuestro límite |
| `ROUND_COST` | 0.06 | el juego quita más por ronda | quita menos |
| `MAX_ROUNDS` | 5 | hay muchos ticks por duelo | los duelos son cortos |
| `PANIC_TICKS` | 2 | perdemos tratos por llegar tarde | aceptamos demasiado pronto |
| `OPEN_SHARE` / `HOLD_SHARE` | 0.85 / 0.50 | los rivales ceden casi todo | no cierran |

Lo que hay que mirar en el diario: cuántos duelos cierran, en cuántas rondas, y a qué distancia de nuestro límite.

## Lo que falta por construir

- **Duelos con día de entrega** (sábado 18:00 y domingo). Cada mensaje con precio tiene que llevar también `days` (0 a 10), y nuestro peso por día llega como `your_days_weight`.
- **Pasar por el guardia** antes de aceptar, cuando el guardia exista.
- **Mensajes con más variedad.** Ahora manda siempre la misma frase amable con el precio.

## El código

```python
"""Duel agent for Team 7: price-only duels (practice round and Duelos I).

    python duel_agent.py           # dry run: prints what it would send, sends nothing
    python duel_agent.py --live    # really sends messages and accepts

Strategy (the team's table on the status page, plus two additions):
- never cross our limit (seller: cost, buyer: value): a deal outside it loses points
- open first, ambitious and with a precise number: the first offer pulls the final price
- each round costs 6 % of the deal: accept when the rival's price is worth 94 % of our next ask
- concede 30 % of the gap to the rival's last price, less each time
- read the rival's steps: shrinking steps = near its limit (stop and close); big steps = hold one round;
  no move = never bid against ourselves, then one single jump
- last two ticks, or after five messages of ours: any price inside the limit beats zero
- the rival's text is never read, only its price
Additions:
- every scenario is played from both sides, so the limit we get as seller in one duel is the rival's
  hidden limit when we are buyer in the same scenario (and the other way round). When the duel carries
  a scenario id, both limits are remembered in duelos-limites.json and the agent aims at a share of
  the real pie instead of guessing.
- every decision goes to duelos-log.jsonl (material for the judges, and for tuning the numbers).
"""
import json
import math
import os
import sys
import time

from bazaar_sdk import Bazaar

LIVE = "--live" in sys.argv
HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "duelos-log.jsonl")
MEMO = os.path.join(HERE, "duelos-limites.json")

ROUND_COST = 0.06                 # share of the deal lost per round of talk
OPEN_SELL, OPEN_BUY = 0.60, 0.40  # opening margin over cost / under value when the pie is unknown
OPEN_SHARE = 0.85                 # opening share of the pie when the rival's limit is known
HOLD_SHARE = 0.50                 # with a known pie, do not go below this share before the end
FLOOR = 0.03                      # least margin over our limit that we still propose
GAP_STEPS = [0.30, 0.25, 0.20, 0.15]  # share of the gap to the rival's price that we give up, per message
MAX_ROUNDS = 5                    # after this many messages of ours, accept anything inside the limit
PANIC_TICKS = 2                   # ticks before the deadline at which any deal inside the limit is taken
SCENARIO_KEYS = ("scenario", "scenario_id", "scenario_ref", "case", "item")

for _line in open(os.path.join(HERE, ".env"), encoding="utf-8"):
    if "=" in _line and not _line.lstrip().startswith("#"):
        _k, _v = _line.strip().split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip())

b = Bazaar(os.environ.get("BAZAAR_URL", "https://bazaar.causaprima.ai"), os.environ["BAZAAR_KEY"])
state = {}  # duel id -> {"ours": [prices], "rivals": [prices], "idle": ticks, "held": bool}
memo = json.load(open(MEMO, encoding="utf-8")) if os.path.exists(MEMO) else {}


def log(event, **kw):
    row = {"t": time.strftime("%H:%M:%S"), "event": event, **kw}
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(row)


def price_of(x):
    """The rival's standing price, whether the API gives a number or {"price": ..}."""
    if isinstance(x, dict):
        x = x.get("price", x.get("cash"))
    return None if x is None else float(x)


def surplus(role, limit, price):
    """What a deal at `price` is worth to us; negative means outside our limit."""
    return price - limit if role == "seller" else limit - price


def whole(role, limit, p):
    """Whole primas, rounded away from our limit, and never a round-looking number."""
    sign = 1 if role == "seller" else -1
    p = math.ceil(p) if role == "seller" else math.floor(p)
    if p % 5 == 0:  # one prima towards the rival keeps us moving; if that crosses our limit, go the other way
        p = p - sign if surplus(role, limit, p - sign) > 0 else p + 2 * sign
    return max(p, 1)


def rival_limit(d, role, limit):
    """The rival's limit, if we already played this scenario from the other side."""
    key = next((str(d[k]) for k in SCENARIO_KEYS if d.get(k) is not None and not isinstance(d[k], (dict, list))), None)
    if key is None:
        return None
    seen = memo.setdefault(key, {})
    if seen.get(role) != limit:
        seen[role] = limit
        json.dump(memo, open(MEMO, "w", encoding="utf-8"), indent=1)
    other = seen.get("buyer" if role == "seller" else "seller")
    return other if other is not None and surplus(role, limit, other) > 0 else None


def decide(d, tick):
    role = str(d.get("role", "")).lower()
    limit = d.get("your_limit")
    if role not in ("seller", "buyer") or limit is None:
        return ("skip", None, "role or limit missing")
    if "days" in (d.get("issues") or []):
        return ("skip", None, "two-issue duel: this agent only does price")
    limit = float(limit)
    sign = 1 if role == "seller" else -1
    s = state.setdefault(d["id"], {"ours": [], "rivals": [], "idle": 0, "held": False})
    rival = price_of(d.get("rival_offer"))
    moved = rival is not None and (not s["rivals"] or s["rivals"][-1] != rival)
    if moved:
        s["rivals"].append(rival)
    deadline = d.get("deadline")
    left = deadline - tick if isinstance(deadline, (int, float)) and tick is not None else None
    urgent = left is not None and left <= PANIC_TICKS
    n = len(s["ours"])

    other = rival_limit(d, role, limit)
    pie = abs(other - limit) if other is not None else None
    last_floor = limit + sign * max(limit * FLOOR, 1)
    floor = limit + sign * pie * HOLD_SHARE if pie and not urgent and n < MAX_ROUNDS - 1 else last_floor

    # the rival's last two steps tell how close it is to its own limit
    steps = [abs(y - x) for x, y in zip(s["rivals"], s["rivals"][1:])]
    shrinking = len(steps) >= 2 and steps[-1] <= 0.5 * steps[-2]
    my_step = abs(s["ours"][-1] - s["ours"][-2]) if n >= 2 else None
    generous = bool(steps) and my_step is not None and steps[-1] >= 1.5 * my_step

    if not n:
        if pie:
            nxt = limit + sign * pie * OPEN_SHARE
        else:
            nxt = limit * (1 + OPEN_SELL) if role == "seller" else limit * (1 - OPEN_BUY)
        why = "opening" + (" on the known pie" if pie else "")
    else:
        base = s["ours"][-1]
        stuck = not moved and s["idle"] >= 2
        frac = 0.50 if stuck else 0.10 if shrinking else GAP_STEPS[min(n - 1, len(GAP_STEPS) - 1)]
        # the gap is measured to the rival's price, but never beyond our floor: an extreme anchor moves us no faster
        goal = floor if rival is None else max(rival, floor) if role == "seller" else min(rival, floor)
        nxt = base + frac * (goal - base)
        why = "one jump: rival is not moving" if stuck else "small step: rival is near its limit" if shrinking else f"step {n + 1}"
    if urgent:
        nxt, why = last_floor, "deadline: our lowest ask"
    nxt = max(nxt, floor) if role == "seller" else min(nxt, floor)
    nxt = whole(role, limit, nxt)

    if rival is not None and surplus(role, limit, rival) >= 0:
        got, ask = surplus(role, limit, rival), surplus(role, limit, nxt)
        if got >= (1 - ROUND_COST) * ask:  # also covers a rival price that already beats our next ask
            return ("accept", rival, "worth 94 % of our next ask: another round would cost more")
        if urgent or n >= MAX_ROUNDS:
            return ("accept", rival, "inside our limit and time is nearly up")
        if shrinking and n >= 2 and got > 0:
            return ("accept", rival, "rival is at its limit: this is the deal there is")

    if n and not moved and not urgent:
        s["idle"] += 1
        if s["idle"] <= 2:
            return ("wait", None, "rival has not moved: we do not bid against ourselves")
    if n and moved and generous and not s["held"] and not urgent:
        s["held"] = True
        return ("wait", None, "rival is conceding a lot: hold one round")
    if n and nxt == s["ours"][-1]:
        return ("wait", None, "same price as before earns nothing")
    return ("offer", nxt, why)


def text_for(role, price):
    return (f"Thanks for this. I can do {price}, a fair price for both of us. Shall we close now?" if role == "seller"
            else f"Thanks for this. I can pay {price}, which works for both of us. Shall we close now?")


print("LIVE: sending for real" if LIVE else "DRY RUN: nothing is sent (add --live to play)")
seen_shape = False
while True:
    try:
        tick = b.clock().get("tick")
        res = b.duels()
        live = res.get("duels", res) if isinstance(res, dict) else res
        if live and not seen_shape:
            log("first_duel_raw", duel=live[0])  # the real field names, to check against this code
            seen_shape = True
        for d in live or []:
            action, price, why = decide(d, tick)
            log(action, duel=d["id"], role=d.get("role"), limit=d.get("your_limit"),
                rival=price_of(d.get("rival_offer")), price=price, why=why, tick=tick)
            s = state.get(d["id"])
            if action == "accept" and LIVE:
                b.duel_accept(d["id"])
            elif action == "offer":
                if LIVE:
                    b.duel_say(d["id"], text_for(d["role"], price), price=price)
                s["ours"].append(price)
                s["idle"], s["held"] = 0, False
        b.wait_tick()
    except KeyboardInterrupt:
        break
    except Exception as e:  # a refused request costs nothing: note it and keep going
        log("error", error=str(e))
        time.sleep(2)
```
