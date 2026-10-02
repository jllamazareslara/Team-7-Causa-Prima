# Reglas deterministas: una carpeta y una rama por persona

Cada miembro del equipo entrena a los agentes escribiendo **reglas deterministas** en su propia carpeta y en su propia rama.
Nadie toca el trabajo de otro, y un diagnóstico compara todas las ramas con la misma vara de medir.

```
main
├── rules/
│   ├── baseline/            ← reglas por defecto (las de starter_agent.py / starter_broker.py). Referencia común.
│   │   ├── dealer.py        ← regatear con Abuela y los demás dealers
│   │   ├── broker.py        ← emparejar el libro de nuestro mercado (Market Test)
│   │   └── duel.py          ← duelos 1 contra 1
│   └── <nombre>/            ← SOLO en la rama rules/<nombre>
│       ├── dealer.py  broker.py  duel.py
├── bench/
│   ├── sims.py              ← simuladores del juego (la vara de medir, común a todos)
│   ├── run.py               ← benchmark de las carpetas de tu copia local
│   ├── diagnose.py          ← diagnóstico completo de TODAS las ramas rules/* → results/diagnostico.md
│   ├── new_member.py        ← crea tu rama y tu carpeta desde el baseline
│   └── guard.py             ← comprueba que tu rama solo toca tu carpeta
└── play.py                  ← ejecuta en vivo las reglas de cualquiera contra el servidor

ramas:  main ── rules/ana
            ├── rules/juan
            └── rules/<nombre> ...
```

## Reglas del juego entre nosotros

1. **Tu rama es `rules/<tu_nombre>` y solo cambias `rules/<tu_nombre>/`.** `bench/guard.py` lo comprueba y la
   acción de GitHub falla si la rama toca cualquier otro archivo.
2. **`main` no se toca para reglas.** Cambios en el SDK, `bench/`, `play.py` o el baseline van en su propia rama
   (`infra/...`) con pull request a `main`. Si cambias `bench/sims.py` cambias la vara de medir de todos: avisa.
3. **Un commit por cambio de reglas**, y el mensaje dice qué cambiaste. El diagnóstico usa cada commit como una
   versión, así que se ve qué aportó cada cambio.
4. **Documenta tus reglas** en el docstring de cada archivo como `R1 ...`, `R2 ...`. El diagnóstico las copia en el
   informe cuando tu versión es la mejor del agente.
5. **Deterministas**: mismo estado → misma decisión. Nada de `random`, hora del reloj ni llamadas a la API dentro de
   las reglas. Si no tocas un agente, se usa el baseline.

## Empezar

```bash
git clone https://github.com/jllamazareslara/Team-7-Causa-Prima.git && cd Team-7-Causa-Prima
python3 -m bench.new_member ana              # crea la rama rules/ana con rules/ana/{dealer,broker,duel}.py
# ... edita rules/ana/dealer.py ...
python3 -m bench.run --author ana            # tu score frente al baseline (results/benchmark.md)
git commit -am "rules/ana dealer: R2 no repetir precio"
git push -u origin rules/ana                 # GitHub ejecuta guard + benchmark y lo muestra en el resumen
```

Para traer mejoras de `main` (nuevo baseline, simuladores...) a tu rama: `git pull origin main`.

## Diagnóstico completo

```bash
python3 -m bench.diagnose                    # descarga todas las ramas y mide cada commit de cada una
```

`results/diagnostico.md` contiene:

- **Mejores reglas por agente**: la mejor versión de cada persona (commit y score, Δ frente al baseline) y la
  mejor del equipo, con sus reglas R1, R2...
- **Evolución de cada autor**: commit a commit, el score de cada agente y cuánto lo movió ese commit.
- **Torneo de duelos**: la mejor regla de duelo de cada uno contra la de todos los demás.
- **Avisos**: reglas que fallan y ramas que tocan archivos fuera de su carpeta.

Todas las versiones se miden con los simuladores de la copia desde la que lanzas el diagnóstico (normalmente `main`) y
con las mismas semillas, así que las comparaciones son justas aunque cada rama lleve un `bench/` distinto.

## Qué mide el benchmark

| agente | score (más alto = mejor) | otras columnas |
|---|---|---|
| dealer | parte del rango del dealer que capturamos: (apertura − pagado) / (apertura − suelo). Sin trato = 0; pagar el precio de apertura = 0 (no cuenta para la escalera) | % de tratos, excedente medio frente a nuestro valor privado, % de veces que pagamos más de lo que vale |
| broker | eficiencia en el Market Test: ganancias reales conseguidas / ganancias posibles | emparejamientos y rechazos por sesión |
| duel | parte media del pastel que nos llevamos × descuento por ronda, como comprador y como vendedor, contra 4 bots y el baseline | % de tratos, % de tratos con pérdida, resultado por rival |

Los simuladores son un **modelo** basado en `RULES.md`, no el servidor real. Modelan:

- **Dealers**: suelo oculto, concesiones recíprocas, paciencia limitada y oferta final.
- **Market Test**: traders que esconden su límite y van relajando su precio.
- **Duelos**: el pastel encoge en cada ronda.

Cuando veamos en vivo que el servidor se comporta distinto, ajustamos `bench/sims.py` en una rama `infra/...`.

## Probar en vivo

Quien tenga la clave ejecuta las reglas de cualquiera. Si su carpeta no está en tu copia, se cogen de su rama
`origin/rules/<nombre>`:

```bash
export BAZAAR_KEY=tk-xxxx-xxxx
python3 play.py dealer --rules ana --deals 3
BROKER_KEY=bk_... python3 play.py broker --rules ana
python3 play.py duel --rules baseline
```

Cada decisión queda en `runs/<autor>/<agente>.jsonl` (fuera de git).

La cuota de tratos por hora con cada dealer es compartida por todo el equipo. Para comparar a dos personas en igualdad
de condiciones, ejecutad sus reglas en la misma hora.
