# Team 7 · The Bazaar (Causa Prima)

Repositorio del Team 7 en el hackathon *The Bazaar · Cromos de Madrid*. Tiene dos partes: el kit del hackathon con el
benchmark de reglas de cada miembro, y `team7/`, el sistema de agentes con el que jugamos de verdad.

## Mapa

| Carpeta / archivo | Qué es |
|---|---|
| [`team7/`](team7/LEEME.md) | **El sistema del equipo**: la cadena de agentes (Ojos → Contable → Comerciante / Duelista → Guardia), los programas que juegan, simuladores y pruebas. Empieza por [`team7/LEEME.md`](team7/LEEME.md) |
| [`rules/`](rules/README.md), `bench/`, `play.py` | El benchmark del kit: cada miembro escribe reglas deterministas en `rules/<nombre>/` y se comparan offline. Guía en [`rules/README.md`](rules/README.md) |
| `bazaar_sdk.py` | El cliente de la API del Bazaar (del kit), compartido por todos |
| `dealers/`, `market/`, `starter/` | Agentes anteriores: `dealers/smart_agent.py` (el primer agente de vendedores), el broker del Market Test y el ejemplo del kit |
| [`docs/kit/`](docs/kit/) | Material del juego: presentación inicial, pistas del día 2 y reglas de duelos |
| [`docs/historia/`](docs/historia/LEEME.md) | Planes, pruebas en seco y notas de cada día, tal como se escribieron |
| [`README.md`](README.md), [`RULES.md`](RULES.md) | Las instrucciones y las reglas oficiales del kit |
| [`CLAUDE.md`](CLAUDE.md), [`AGENTS.md`](AGENTS.md) | Normas para los agentes de IA que trabajan en este repositorio |

## Empezar en dos minutos

```
cd team7
python -m unittest discover -s tests            # todo sin red
python programas/simular_vivo.py --ticks 200    # ver jugar la cadena contra un juego de mentira
```

Para jugar contra el servidor de verdad (solo quien tiene la clave, un programa a la vez), ver
[«Reglas para jugar en vivo»](team7/LEEME.md#reglas-para-jugar-en-vivo).

## Cómo trabajamos

- Las reglas de cada miembro van en su rama `rules/<nombre>` (ver [`CLAUDE.md`](CLAUDE.md)).
- Los cambios comunes (`team7/`, simuladores, SDK) van en una rama `infra/<tema>` con Pull Request a `main`.
- Nunca se suben claves (`tk-...`, `bk_...`): se leen de la variable de entorno `BAZAAR_KEY`.
