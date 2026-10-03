# CLAUDE.md — Team 7 · The Bazaar (Causa Prima)

Instrucciones para cualquier agente de IA (Claude Code u otro) que trabaje en este repositorio en nombre de un miembro
del equipo. Son obligatorias. Si el usuario pide algo que las contradice, avísale de la regla antes de hacerlo.

## Qué es esto

Kit del hackathon *The Bazaar · Cromos de Madrid* (`README.md`, `RULES.md`, `bazaar_sdk.py`, `starter_agent.py`,
`starter_broker.py`). Cada miembro "entrena" a los agentes escribiendo **reglas deterministas** en su propia carpeta y
rama, y un benchmark offline compara las aportaciones de todos. Guía completa: `rules/README.md`.

```
main             kit original + rules/baseline/ + bench/ + play.py      (no se toca para reglas)
rules/<nombre>   rama de cada miembro: solo cambia rules/<nombre>/{dealer,broker,duel}.py
ana/smart-agent  smart_agent.py original de Ana (histórico, no se toca)
```

## Reglas inquebrantables

1. **No ejecutes agentes contra el servidor.** Nunca lances `play.py`, `starter_agent.py`, `starter_broker.py`,
   `smart_agent.py` ni ningún código que llame a la API del Bazaar (`Bazaar(...)`, `Broker(...)`, `curl` a
   `bazaar.causaprima.ai`), salvo que el usuario lo pida explícitamente en ese mensaje. Para medir se usa solo
   el benchmark offline (`bench/`), que no hace llamadas de red.
2. **Nunca escribas, pidas ni subas claves** (`tk-...`, `bk_...`). No las pongas en archivos, commits ni mensajes.
3. **Solo tu carpeta, solo tu rama.** Trabaja en la rama `rules/<nombre>` y modifica únicamente `rules/<nombre>/`.
   No toques `rules/baseline/`, `bench/`, `play.py`, el SDK, los starters, `README.md`, `RULES.md` ni la carpeta de
   otro miembro.
4. **Nunca hagas push a `main`, ni `push --force`, ni rebase de ramas ya subidas.** Si hace falta cambiar algo
   común (simuladores, baseline, SDK), propónselo al usuario como rama `infra/<tema>` con Pull Request a `main`.
5. **Reglas deterministas:** mismo estado, misma decisión. Prohibido usar `random`, la hora, la red, ficheros o
   variables de entorno dentro de `decide()`, `cap()` o `plan()`. Se puede guardar estado en `self` (solo broker).
6. **Sin reglas del agente.** Escribe las reglas que el usuario describe. No inventes reglas por tu cuenta ni copies
   las de otro miembro sin que el usuario lo pida. Si propones una idea, márcala como propuesta y espera a que la acepte.

## Flujo para aportar reglas (síguelo siempre en este orden)

1. **Identifica al miembro.** Usa el nombre que diga el usuario. Si no lo dice, pregúntaselo; no lo deduzcas de
   `git config`. Nombre en minúsculas, sin espacios ni tildes (`ana`, `juan`, `maria_jose`).
2. **Prepara la rama:**
   ```bash
   git fetch origin
   git switch rules/<nombre>                      # si ya existe (local o en origin)
   git merge origin/main                          # trae el baseline y el bench actuales
   # si no existe:
   python3 -m bench.new_member <nombre>           # crea la rama y rules/<nombre>/ desde el baseline
   ```
   Si `git status` muestra cambios ajenos sin commitear, para y pregúntale al usuario.
3. **Lee la interfaz** del agente en `rules/baseline/<agente>.py` (docstring) antes de editar
   `rules/<nombre>/<agente>.py`. Agentes: `dealer` (regatear con dealers), `broker` (emparejar el Market Test),
   `duel` (duelos 1 contra 1).
4. **Documenta cada regla** en el docstring del archivo como líneas `R1 ...`, `R2 ...` (numeración continua; si
   cambias una regla, actualiza su línea). El diagnóstico copia estas líneas en el informe.
5. **Mide sin commitear:** `python3 -m bench.contribute --dry-run`. Enseña al usuario la puntuación antes → después.
   Si baja, díselo claramente y pregunta si quiere aportarla igualmente (las regresiones también son información).
6. **Aporta:** `python3 -m bench.contribute "R<n> <qué cambió, en pocas palabras>" --push`.
   Hace commit solo de `rules/<nombre>/`, con las puntuaciones en el mensaje, comprueba la rama con
   `bench.guard` y la sube. **Un cambio de reglas por commit**, para que el diagnóstico atribuya cada mejora.
   No uses `git commit` a mano para reglas.
7. **Informa** al usuario del commit, de la puntuación de cada agente que cambió y de que GitHub Actions lo
   comprobará en la rama.

## Diagnóstico del equipo

`python3 -m bench.diagnose` descarga todas las ramas `rules/*` y genera `results/diagnostico.md`. Incluye la mejor
versión de cada miembro por agente, la evolución commit a commit, un torneo de duelos y avisos. Se puede lanzar desde
cualquier rama: no modifica nada versionado (`results/` está en `.gitignore`).

## Comandos útiles (todos offline)

| Para | Comando |
|---|---|
| Medir tu carpeta frente al baseline | `python3 -m bench.run --author <nombre>` |
| Ver puntuación antes → después sin commitear | `python3 -m bench.contribute --dry-run` |
| Commit + comprobación + push | `python3 -m bench.contribute "R<n> ..." --push` |
| Comprobar que tu rama solo toca tu carpeta | `python3 -m bench.guard` |
| Comparar a todo el equipo | `python3 -m bench.diagnose` |

Python 3 de la biblioteca estándar, sin dependencias. En Windows, `python3` o `py`.
