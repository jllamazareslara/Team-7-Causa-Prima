"""El candado: un solo programa acepta en el juego a la vez.

El juego deja UNA aceptación por tick a todo el equipo. Si dos programas aceptan con la misma clave (el lanzador de la
cadena y play.py, por ejemplo), se pisan: uno gasta la aceptación que el otro necesitaba, o los dos firman cosas que
juntas rompen la caja. Regla: todo programa que vaya a aceptar (en vivo) toma el candado antes de empezar y lo suelta
al terminar. Los que solo leen (vigía, grabador, en seco) no lo necesitan.

    tomar(ruta, quien)  → (True, "") o (False, motivo). Crea el archivo con el pid, quién y cuándo, sin pisar otro.
    soltar(ruta)        → borra el archivo si es nuestro.
    quien_lo_tiene(ruta)

Un candado de un proceso que ya no existe (se cerró sin soltar) se considera libre. Uno de más de
`caduca_horas` también, por si el pid se reutilizó.
"""
import json
import os
import tempfile
import time

CADUCA_HORAS = 12
# El mismo archivo para todos los programas del equipo en este ordenador (se puede cambiar con TEAM7_CANDADO).
# Dos ordenadores distintos no se ven: por eso la clave del equipo se usa en vivo desde UN solo ordenador.
RUTA = os.environ.get("TEAM7_CANDADO") or os.path.join(tempfile.gettempdir(), "team7-acepta.lock")


def _vivo(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    if pid == os.getpid():
        return True
    try:
        if os.name == "nt":
            import ctypes
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)      # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return False
            codigo = ctypes.c_ulong()
            ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(codigo))
            ctypes.windll.kernel32.CloseHandle(h)
            return codigo.value == 259                                       # STILL_ACTIVE
        os.kill(pid, 0)
        return True
    except (OSError, AttributeError):
        return False


def quien_lo_tiene(ruta):
    """Lo que dice el archivo del candado, o None si no hay."""
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def tomar(ruta, quien, caduca_horas=CADUCA_HORAS, ahora=None):
    ahora = time.time() if ahora is None else ahora
    os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)
    otro = quien_lo_tiene(ruta)
    if otro is not None:
        libre = (not _vivo(otro.get("pid"))) or ahora - otro.get("desde", 0) > caduca_horas * 3600
        if otro.get("pid") == os.getpid():
            return True, ""
        if not libre:
            return False, (f"ya acepta otro programa: {otro.get('quien')} (pid {otro.get('pid')}, desde "
                           f"{time.strftime('%H:%M', time.localtime(otro.get('desde', 0)))}). Páralo o borra {ruta} si sabes que no corre")
        try:
            os.remove(ruta)
        except OSError:
            pass
    try:
        fd = os.open(ruta, os.O_CREAT | os.O_EXCL | os.O_WRONLY)       # atómico: si dos llegan a la vez, gana uno
    except FileExistsError:
        return False, "otro programa ha tomado el candado en este mismo momento"
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"pid": os.getpid(), "quien": quien, "desde": ahora}, f)
    return True, ""


def soltar(ruta):
    otro = quien_lo_tiene(ruta)
    if otro is not None and otro.get("pid") == os.getpid():
        try:
            os.remove(ruta)
        except OSError:
            pass
