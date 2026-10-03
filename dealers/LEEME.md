# dealers/

`smart_agent.py` es el agente de Ana que regateó con los vendedores en vivo el 3/10. **Se queda como referencia y no se
usa en vivo.** Lo bueno que tenía (una conversación por vendedor, todos a la vez; precios en un solo sentido y sin
repetir; aceptar la oferta final dentro del límite; lo que ningún vendedor compra, a El Rastro) lo hace ahora la cadena
con `cadena/jugar.py`, pasando por la Contable, el Guion, el Ojeador y el Guardia.

**No lanzar `smart_agent.py` a la vez que `cadena/jugar.py`:** no toma el candado (`cadena/t7/candado.py`) y los dos
gastarían la única aceptación por tick del equipo. Tampoco abre ya mercado propio: no usar `OPEN_VENUE=1`.

La copia original e histórica está en la rama `ana/smart-agent`.
