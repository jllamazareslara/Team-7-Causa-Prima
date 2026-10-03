"""Los Ojos: lo primero de cada tick. Leen el juego y pasan los números a la Contable. Solo miran: no deciden nada.

Su ayudante es el Escudo (`defensa.py`): mira el texto que llega de vendedores y rivales de duelo, cuenta avisos por
contraparte (con muchos, esa contraparte pasa a "modo firme") y apunta candidatos a mala fe (el texto dice un precio
y la oferta pide otro). El texto nunca llega a quien decide: solo los números.

Entregan la `vista`:
    vista = {"textos_nuevos": {hilo o "duelo-<id>" cuyo texto es nuevo en este tick}, "mala_fe": [...]}
Los textos nuevos los usa el Espía (ayudante del Regateador y la Duelista) para no leer dos veces lo mismo.
"""
from . import defensa


def _nuevo(mem, clave, texto):
    """True solo la primera vez que vemos este texto de esta contraparte."""
    if not texto or mem.vistos.get(clave) == texto:
        return False
    mem.vistos[clave] = texto
    return True


def mirar(lectura, mem, apunta=None):
    """Lee la lectura del tick y devuelve la vista. Tolera piezas rotas: lo que no se entiende se salta."""
    apunta = apunta or (lambda *_: None)
    t = lectura.get("tick")
    vendedores = [c for c in lectura.get("vendedores") or [] if isinstance(c, dict) and "id" in c]
    duelos = [d for d in lectura.get("duelos") or [] if isinstance(d, dict) and "id" in d]
    tablon = lectura.get("tablon")
    apunta("OJOS", f"efectivo {lectura.get('efectivo', 0)} · {len(vendedores)} conversaciones · {len(duelos)} duelos · "
                   f"tablón {'sí' if tablon else 'no'}")
    nuevos, mala_fe = set(), []

    # ---------- Escudo: el texto de los vendedores ----------
    for c in vendedores:
        hilo, quien, texto = str(c["id"]), c.get("vendedor"), c.get("texto") or ""
        if not _nuevo(mem, hilo, texto):
            continue
        nuevos.add(hilo)
        motivos, _ = mem.escudo.anotar(quien, texto)
        if motivos:
            apunta("ESCUDO", f"{quien}: {', '.join(motivos)}")
        suyas = c.get("suyas") or []
        motivo = defensa.incoherencia(texto, suyas[-1]) if suyas and not c.get("cerrado") else None
        if motivo:
            mala_fe.append({"hilo": c["id"], "vendedor": quien, "motivo": motivo, "tick": t})
            apunta("ESCUDO", f"{quien} · candidato a mala fe: {motivo}. Lo decide el equipo.")

    # ---------- Escudo: el texto de los rivales de duelo ----------
    for d in duelos:
        quien = f"duelo-{d['id']}"
        if not _nuevo(mem, quien, d.get("texto") or ""):
            continue
        nuevos.add(quien)
        motivos, _ = mem.escudo.anotar(quien, d["texto"])
        if motivos:
            apunta("ESCUDO", f"{quien}: {', '.join(motivos)}" + (" · modo firme" if mem.escudo.firme(quien) else ""))

    return {"textos_nuevos": nuevos, "mala_fe": mala_fe}
