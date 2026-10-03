# AGENTS.md

Las instrucciones para agentes de IA de este repositorio están en [`CLAUDE.md`](CLAUDE.md) y son obligatorias para
cualquier agente (Claude Code, Codex, Cursor...). En resumen:

- No ejecutes agentes contra el servidor del Bazaar ni uses claves.
- Trabaja solo en la rama `rules/<nombre>` y solo en `rules/<nombre>/`.
- Aporta cada cambio de reglas con `python3 -m bench.contribute "R<n> ..." --push`.
