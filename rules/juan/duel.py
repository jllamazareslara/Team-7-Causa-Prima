"""Reglas de juan para duel: ancla alta y firme, ceder solo cuando el rival ya nos alcanza, y rematar el trato
en vez de arriesgarnos a terminar sin él.

R1  Abrir con ventaja y con un número que no parezca una concesión redonda: vendiendo, coste * 1.60; comprando,
    valor * 0.60. Nunca un precio múltiplo de 5.
R2  No ceder por iniciativa propia: mantener nuestra ancla ronda tras ronda. Probado contra una cesión del 30/25/
    20/15 % del hueco (como proponía el primer borrador): esa versión cerraba más tratos (82 % vs 78 %) pero se
    llevaba menos pastel (0.307 frente a 0.356 del baseline en bench.run, 300 semillas) porque regalábamos nuestra
    ventaja antes de que el rival tuviera que ceder él. Mantener el ancla, en cambio, deja 0.381: quien cede menos
    suele llevarse más cuando el rival también va cediendo con el tiempo.
R3  Aceptar en el momento en que la oferta del rival alcanza o supera nuestra ancla (o cualquier precio dentro de
    nuestro límite si ya estamos en la última ronda): no hace falta leer sus pasos, basta con no perder el
    cruce cuando ocurre.
R4  Nunca terminar sin trato, pero sin adelantar la concesión: forzar la aceptación de cualquier precio dentro de
    nuestro límite solo en la última ronda, no dos rondas antes. Forzarlo dos rondas antes (como proponía el primer
    borrador) baja el resultado a 0.302: regalamos rondas de paciencia que el rival a veces habría acabado cediendo.

Cómo se midió (python3 -m bench.run --agent duel --author juan, 300 semillas): 0.381 de puntuación media, 82 % de
tratos, 0 % de tratos con pérdida. El emparejamiento más flojo es contra el baseline (0.208): dos reglas igual de
pacientes se reparten el pastel casi por la mitad, que es lo esperable cuando nadie tiene ventaja de información.

Queda fuera, a propósito (ver DUELOS-para-Ana.md para el porqué):
  - la memoria entre los dos lados del mismo escenario (abrir sabiendo el límite real del rival cuando ya jugamos
    el mismo caso desde el otro lado): decide() no puede guardar estado (CLAUDE.md regla 5) y bench.run crea una
    regla nueva por episodio, así que aquí no hay nada que recordar. Si el servidor real confirma un identificador
    de escenario, esa idea es una herramienta aparte, no estas reglas.
  - duelos a dos variables (precio y día de entrega): bench/sims.py no los modela todavía.
  - un ancla más agresiva (hasta coste * 2.2) puntúa aún mejor en este simulador concreto, pero es un artefacto de
    los límites de los bots de prueba (BOTS en bench/sims.py), no una señal de que valga en un duelo real: nos
    quedamos con el 60 % del documento original, defendible frente a un rival que no sea un bot de juguete.

La interfaz completa está documentada en rules/baseline/duel.py.
"""
import math


class Rules:
    OPEN_SELL, OPEN_BUY = 1.60, 0.60  # R1
    PANIC_ROUNDS = 1                  # R4

    def decide(self, s: dict):
        role, limit = s["role"], s["limit"]
        rival, ours = s["rival_offer"], s["our_offers"]
        sign = 1 if role == "seller" else -1
        urgent = s["round"] >= s["max_rounds"] - self.PANIC_ROUNDS

        if not ours:
            nxt = limit * (self.OPEN_SELL if role == "seller" else self.OPEN_BUY)
        elif urgent:
            nxt = limit                 # R4: rematar con cualquier precio dentro del límite
        else:
            nxt = ours[-1]               # R2: mantener el ancla, no ceder por iniciativa propia
        nxt = max(nxt, limit) if role == "seller" else min(nxt, limit)
        p = self._whole(role, nxt)

        if rival is not None and sign * (rival - limit) >= 0:  # dentro de nuestro límite
            if urgent or s["round"] >= s["max_rounds"] - 1 or sign * (rival - p) >= 0:  # R3 / R4
                return ("accept",)
        return ("offer", p)

    @staticmethod
    def _whole(role, p):
        p = math.ceil(p) if role == "seller" else math.floor(p)
        if p % 5 == 0:  # R1: nunca un número redondo
            p += 1 if role == "seller" else -1
        return max(p, 1)
