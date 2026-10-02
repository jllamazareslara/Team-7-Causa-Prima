---
name: aportar-reglas
description: Aportar reglas deterministas de un miembro del equipo a sus agentes del Bazaar (dealer, broker, duel) en su rama rules/<nombre>, medirlas con el benchmark offline y subirlas. Úsala siempre que alguien quiera añadir, cambiar o probar sus reglas, entrenar a sus agentes o subir su aportación.
---

# Aportar reglas al Bazaar

Sigue estos pasos en orden. Las reglas inquebrantables de `CLAUDE.md` siguen valiendo: **no ejecutes agentes contra
el servidor** (nada de `play.py`, starters ni llamadas a la API) y **no toques nada fuera de `rules/<nombre>/`**.

## 1. Quién y qué

- Nombre del miembro: el que diga el usuario o el argumento de la skill (`/aportar-reglas ana`). Si falta, pregunta.
  Formato: minúsculas, sin espacios ni tildes.
- Qué agente y qué regla: si el usuario no lo ha dicho, pregunta qué agente (`dealer`, `broker`, `duel`) y qué
  regla quiere añadir o cambiar, con sus palabras. No inventes reglas tú.

## 2. Rama al día

```bash
git fetch origin
git status --short
```

Si hay cambios sin commitear fuera de `rules/<nombre>/`, para y pregunta.

- Si existe `rules/<nombre>` (local u `origin/rules/<nombre>`): `git switch rules/<nombre>`, después
  `git pull --ff-only origin rules/<nombre>` (solo si existe en origin) y `git merge --no-edit origin/main`.
  Si el merge da conflictos, para y explícaselos al usuario.
- Si no existe: `python3 -m bench.new_member <nombre>`.

## 3. Escribir la regla

1. Lee el docstring de `rules/baseline/<agente>.py`: es la interfaz (qué recibe `decide`/`plan`/`cap` y qué devuelve).
2. Lee el `rules/<nombre>/<agente>.py` actual y sus líneas `R1 ...`, `R2 ...`.
3. Implementa la regla del usuario en ese archivo:
   - determinista (sin `random`, hora, red, ficheros ni entorno);
   - respeta la interfaz exacta;
   - añade o actualiza su línea `R<n>  <descripción>` en el docstring, con numeración continua. Si es la primera
     regla propia, cambia la primera línea del docstring a `"""Reglas de <nombre> para <agente>.`.
4. Cambia un solo concepto por aportación. Si el usuario pide varias reglas, aporta cada una por separado
   (pasos 4 y 5 por cada una).

## 4. Medir

```bash
python3 -m bench.contribute --dry-run
```

Enseña al usuario el resultado antes → después de cada agente. Si el archivo falla, corrígelo. Si la puntuación baja,
dilo claramente y pregunta si quiere aportarla igualmente, ajustarla o descartarla (`git checkout -- rules/<nombre>/<agente>.py`).

## 5. Aportar

```bash
python3 -m bench.contribute "R<n> <qué cambió, en pocas palabras>" --push
```

Hace el commit solo de `rules/<nombre>/` con las puntuaciones en el mensaje, ejecuta `bench.guard` y sube la rama.
Si el push falla por cambios remotos: `git pull --rebase origin rules/<nombre>` (solo tu rama, nunca main) y repite el push.

## 6. Informar

Di al usuario, en pocas líneas:

- el commit;
- la regla que se aportó;
- la puntuación antes → después de cada agente;
- que GitHub Actions comprueba la rama;
- que `python3 -m bench.diagnose` compara al equipo entero.
