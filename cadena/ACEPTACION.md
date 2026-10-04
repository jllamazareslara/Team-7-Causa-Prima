# Team 7 · criterios de aceptación de los agentes encadenados

Una rama por agente (`infra/t7-<agente>`) con su código y su ficha. Esta rama, `infra/t7`, tiene la cadena entera
y todas las pruebas. Desde `cadena/`: `python -m unittest discover -s tests -v` (100 pruebas, sin red).

Orden en cada tick: Ojos → Contable → Cambista / Duelista / Regateador → Guardia (una firma) → diario. Guion y Ojeador van al lado.

1. **Ojos** (`t7/ojos.py`): miran cómo estamos (`/api/me`, como la skill estado-equipo) y las mejores oportunidades (`/api/feed`, `/api/me/offers`, tablón). No pasan por el Escudo ni por el Guardia.
2. Al lado: **Guion** (`t7/guion.py`) anticipa lo que viene del calendario; **Ojeador** (`t7/ojeador.py`) vigila los
   precios de El Rastro y se los pasa al Regateador y al Cambista.
3. **Contable** (`t7/contable.py` con la calculadora `t7/valor.py`): ¿renta? ¿cuánto? Da los números a los
   negociadores y la ficha de cada trato al Guardia. No decide.
4. **Negociadores**, cada uno con sus ayudantes:
   - **Cambista**: El Rastro y equipos · + Portavoz
   - **Duelista**: duelos · + Portavoz · Espía
   - **Regateador**: vendedores · + Portavoz · Observador · Espía
5. **Guardia**: el único que firma, con la ficha de la Contable. UNA como mucho; la firma vuelve al juego.

El Vigía va aparte (`vigia.py`, solo lee). El Casamentero (`t7/broker.py`) no está encadenado: no supera al
puesto gratuito en el simulador.

| Agente | Rama | Lugar en la cadena |
|---|---|---|
| Los Ojos | `infra/t7` (`t7/ojos.py`) | 1 · leen el juego |
| El Escudo | `infra/t7-escudo` | 3 · ayudante del Regateador y la Duelista: texto sospechoso |
| El Guion | `infra/t7` (`t7/guion.py`) | al lado · anticipa lo que viene |
| El Ojeador | `infra/t7` (`t7/ojeador.py`) | al lado · vigila los precios para el Regateador y el Cambista |
| La Contable | `infra/t7-contable` | 2 · ¿renta? ¿cuánto? para los negociadores y el Guardia |
| El Cambista | `infra/t7-cambista` | 3 · El Rastro y equipos |
| La Duelista | `infra/t7-duelista` | 3 · duelos |
| El Regateador | `infra/t7-regateador` | 3 · vendedores |
| El Portavoz | `infra/t7-portavoz` | 3 · ayudante del Cambista, la Duelista y el Regateador: escribe el mensaje de cada precio nuevo |
| El Espía | `infra/t7-espia` | 3 · ayudante de la Duelista y el Regateador: lee pistas del texto y solo las apunta |
| El Observador | `infra/t7-observador` | 3 · ayudante del Regateador: perfil de cada vendedor |
| El Guardia | `infra/t7-guardia` | 4 · el único que firma; la única puerta antes de `accept` |
| El Vigía | `infra/t7-vigia` | aparte · solo lee, puede ir a la vez que el programa que juega |
| La cadena | `infra/t7` | todo · `cadena.tick()` recorre a los agentes en orden; no habla con el juego |

## La cadena · `infra/t7`

**Quién conecta la cadena con el juego** (no es un agente ni un paso del flujo: son las flechas con EL JUEGO): `jugar.py`, para **los vendedores (el Regateador) y El Rastro (el Cambista)** en un solo proceso: lee el juego, llama a `cadena.tick()`, manda los precios del Regateador (una conversación por vendedor, todos a la vez, según `menus.json` y `cadena.operaciones()`), aplica la única firma del Guardia (vendedor o El Rastro), abre sobres antes de comprar y publica anuncios, peticiones y cambios si `rastro.publicar` / `cambista.pedir` = 1. No abre mercado propio. Duelos: no los juega. En vivo toma el candado; no lanzar a la vez `dealers/smart_agent.py` ni `play.py`.

- [ ] Un tick recorre en orden Ojos → Contable → Cambista / Duelista / Regateador → Guardia (una firma) → diario.
- [ ] Una sola firma por tick, y el duelo urgente va primero.
- [ ] Un fallo en una conversación, un duelo o una oferta se salta con `ERROR`; el resto del tick sigue.
- [ ] `revisar.py` dice OK / AVISO / FALTA antes de jugar; con un FALTA no se juega en vivo.
- [ ] La memoria se guarda en disco y se recupera.

Pruebas:

- `python -m unittest tests.test_todo.Cadena`
- `python -m unittest tests.test_todo.Robustez`
- `python -m unittest tests.test_revisar`
- `python -m unittest tests.test_todo.Estructura`

## Los Ojos · `t7/ojos.py`

- [ ] Van primero en cada tick: antes de la Contable, de los negociadores y del Guardia.
- [ ] Dicen cómo estamos (dinero, puntos, puesto, qué falta en cada página, repetidas) desde `/api/me`, con las claves tapadas.
- [ ] Sacan lo más importante de `/api/feed` y de las ofertas: cartas que nos faltan a la venta (las que completan página
      primero), quién paga por nuestras repetidas (más margen sobre su your_value primero), precios de los tratos,
      avisos del juego (cada uno una vez) y ofertas que nos hacen a nosotros.
- [ ] Solo miran: no deciden nada, no pasan por el Escudo ni por el Guardia, y una lectura rota no tira el tick.
- [ ] El Escudo (ahora con el Regateador y la Duelista) lee cada texto nuevo una sola vez: avisos por contraparte y
      candidatos a mala fe.

## El Guion y El Ojeador · al lado de la cadena

- [ ] El Guion avisa en el diario de lo que viene (con `lectura["calendario"]`), cada evento una vez, sin cambiar ninguna decisión.
- [ ] El Ojeador apunta los precios de El Rastro aunque el Cambista esté apagado, y se los pasa al Regateador y al Cambista.

Pruebas:

- `python -m unittest tests.test_todo.Estructura`

## La Contable · `infra/t7-contable`

- [ ] El valor de la colección coincide con el juego al céntimo (679,12 frente a 679,1) y carta a carta.
- [ ] El bono de página es el 25 % de la suma de la página; la carta que completa página vale su valor más ese bono.
- [ ] Una carta protegida nunca aparece como vendible; `liquidez()` solo propone ventas sin perder valor.
- [ ] Con datos del juego (`configurar`) sustituye los supuestos; lo que no entiende no cambia nada.
- [ ] Modo holgado no cambia ningún ajuste; justo vende primero y baja el tope; seco no compra pero vende.
- [ ] En la cadena da al Regateador su tope o suelo y lo que deja pagar la caja; a la Duelista, antes de que decida, nuestro límite y lo que daría aceptar ya; y al Guardia la ficha de cada firma (también la ganancia de cada duelo).

Pruebas:

- `python -m unittest tests.test_todo.Calculadora`
- `python -m unittest tests.test_todo.ValoresDelJuego`
- `python -m unittest tests.test_todo.Situacion`
- `python -m unittest tests.test_todo.Estructura.test_la_contable_da_los_numeros_a_la_duelista`

## El Guardia · `infra/t7-guardia`

- [ ] Con `runs/STOP` no firma nada.
- [ ] Como mucho una firma por tick para todo el equipo.
- [ ] Un campo desconocido en la oferta, o una oferta cuyo precio cambió desde que el agente la miró: no firma.
- [ ] Solo firma buen negocio mirando el valor de las cartas: comprando, paga como mucho el 90 % de lo que nos vale; vendiendo, cobra al menos el valor + 10 % (`guardia.margen_compra`, `guardia.margen_venta`).
- [ ] Una carta protegida solo sale por 1,5 veces lo que perdemos al darla, o más (`guardia.protegida_factor`).
- [ ] Una compra nunca baja de la reserva de 60 P; una venta no se bloquea nunca por la reserva.
- [ ] Una categoría apagada en `hoy.json` no se firma; con caja justa respeta el tope por trato.
- [ ] Un duelo solo se firma dentro de nuestro límite.

Pruebas:

- `python -m unittest tests.test_todo.Guardia` (18 pruebas)

## El Regateador · `infra/t7-regateador`

- [ ] Nunca cruza nuestro tope (comprando) ni nuestro suelo (vendiendo).
- [ ] Nunca repite el mismo precio dos veces seguidas.
- [ ] Con 3 tratos regateados hoy con un vendedor no le abre más compras, salvo la carta que completa página.
- [ ] No regatea por lo que la caja no paga (tope = lo que vale, lo que queda sobre la reserva, tope por trato).
- [ ] En el simulador captura más rango que la regla actual del equipo (0,54 frente a 0,40 con Abuela).

- [ ] En `jugar.py`: una conversación por vendedor, todos a la vez; manda el precio que decide; la oferta final solo se acepta si la firma el Guardia; en seco no manda, no cierra y no acepta; una conversación muda 4 ticks se suelta; al arrancar cierra las conversaciones que no recuerda.

Pruebas:

- `python -m unittest tests.test_todo.Tienda`
- `python -m unittest tests.test_todo.Jugar` (vendedores)
- `python -m unittest tests.test_todo.Robustez.test_calidad_antes_que_cantidad`
- `python -m unittest tests.test_todo.Robustez.test_no_regatea_por_lo_que_la_caja_no_paga`

## La Duelista · `infra/t7-duelista`

- [ ] Nunca ofrece ni acepta fuera de nuestro límite (4.000 duelos simulados, cero pérdidas).
- [ ] Las 20 trampas de texto no cambian ninguna decisión: solo mira los números.
- [ ] Sin tarta (límites que no se cruzan) no cierra.
- [ ] Con día de entrega siempre manda `days`: el que más nos vale según `your_days_weight`, o el día 5 si no se entiende.
- [ ] En el simulador saca 0,44 de la tarta frente a 0,41 de las reglas actuales.

Pruebas:

- `python -m unittest tests.test_todo.Duelo`
- `python -m unittest tests.test_todo.Cadena.test_dia_de_entrega_segun_nuestros_pesos`

## El Cambista · `infra/t7-cambista`

- [ ] Solo propone lo que renta según la Contable; nunca da una carta protegida.
- [ ] Detecta la carta que completa página y la marca como oportunidad.
- [ ] Anuncio: nunca por debajo de lo que nos vale + 1; lo que un vendedor aún puede comprarnos hoy no se anuncia.
- [ ] Viene apagado (`rastro.publicar` = 0): enseña lo que anunciaría y no manda nada.
- [ ] Comprar: la lista de la compra pone primero la página a la que le faltan 1 o 2 cartas (bono del 25 % repartido entre ellas).
- [ ] Comprar: el tope de cada compra es lo que esa carta nos vale hoy × 0,85; la última de una página lleva el bono dentro.
- [ ] Comprar: no entra una carta que esperamos pagar más de lo que nos vale.
- [ ] Peticiones: abren a 0,45 × base, suben 0,10 × base por caducidad sin pasar del tope, una por carta, 4 a la vez, sin tocar la reserva; vienen apagadas (`cambista.pedir` = 0).
- [ ] Aprende los precios: apunta lo que anuncian otros equipos (una carta por efectivo) y espera pagar lo más barato visto.
- [ ] Caja: con la caja corta elige con una mochila exacta el conjunto de compras que más gana en total.
- [ ] Cambios carta por carta: da repetidas (nunca protegidas ni ya anunciadas) por cartas que faltan, sin efectivo; como mucho 2 vivos; si caduca, le toca a una petición.
- [ ] Competencia: si otro equipo pide la misma carta, ofrece 1 P más mientras quepa en el tope; si no, no le sigue.
- [ ] Aprende: una petición que funcionó hace abrir la siguiente de esa rareza al 85 % de ese precio.
- [ ] Tramo final (30 min antes del fin): tope al 98 % de lo que vale y peticiones directas al tope.
- [ ] `jugar.py` acepta como mucho una oferta por tick (la que firma el Guardia); si pide una carta nuestra, da una copia libre (nunca una ya anunciada o comprometida); en seco o con `runs/STOP` no acepta ni publica nada.

Pruebas:

- `python -m unittest tests.test_todo.Cambista`
- `python -m unittest tests.test_todo.CambistaCompras`
- `python -m unittest tests.test_todo.Cadena.test_anuncios_de_el_rastro`
- `python -m unittest tests.test_todo.Jugar` (`jugar.py`: acepta, elige la copia, anuncia, pide, en seco y con STOP no toca nada)

## El Espía · `infra/t7-espia`

- [ ] Lo que sale de un texto va al diario y a las palabras, nunca a un precio.
- [ ] Con vendedores pregunta en una sola conversación de prueba al día (`espia.conversaciones_por_dia`, 0 = apagado).
- [ ] Solo pregunta a un vendedor con sus 3 tratos del día ya hechos (`espia.tras_tratos`).
- [ ] Abuela 2 preguntas por conversación como mucho, Chato 0, nuevos 0; nunca la misma familia dos veces.
- [ ] Ningún mensaje suyo revela un límite ni un valor nuestro.
- [ ] Canario en la primera ronda de cada duelo; la pregunta directa solo a un rival que lee el texto.

Pruebas:

- `python -m unittest tests.test_todo.Palabras.test_sondas_solo_con_permiso`
- `python -m unittest tests.test_todo.Palabras.test_espia_no_revela_nada`
- `python -m unittest tests.test_todo.Palabras.test_termometro`
- `python -m unittest tests.test_todo.Palabras.test_canario_y_pregunta`
- `python -m unittest tests.test_todo.Palabras.test_cuaderno_ordena_por_lo_medido`
- `python -m unittest tests.test_todo.Cadena.test_espia_solo_con_la_escalera_hecha_y_una_conversacion`
- `python -m unittest tests.test_todo.Cadena.test_el_texto_no_cambia_ningun_precio`

## El Escudo · `infra/t7-escudo`

- [ ] Detecta las trampas típicas de nuestra lista (8 de 8).
- [ ] Ningún mensaje nuestro sale con otro número que el precio ni con palabras que revelen límites.
- [ ] Una incoherencia texto/oferta se apunta como candidato a mala fe una sola vez; señalar lo decide el equipo.
- [ ] Nunca cambia una decisión: los mensajes con trampas dejan las acciones del tick idénticas.

Pruebas:

- `python -m unittest tests.test_todo.Palabras.test_defensa_detecta_trampas`
- `python -m unittest tests.test_todo.Palabras.test_salida_sin_limites`
- `python -m unittest tests.test_todo.Palabras.test_mala_fe`
- `python -m unittest tests.test_todo.Cadena.test_las_trampas_no_cambian_las_acciones`
- `python -m unittest tests.test_todo.Cadena.test_mala_fe_se_apunta_una_vez_y_no_se_senala`

## El Portavoz · `infra/t7-portavoz`

- [ ] Ningún mensaje lleva otro número que el precio (lo comprueba `defensa.revisar_salida`).
- [ ] Con Chato, solo el número y sin preguntas.
- [ ] Solo plantillas: cabe en un tick de 15 s.

Pruebas:

- `python -m unittest tests.test_todo.Cadena.test_chato_sin_preguntas_y_solo_numeros`
- `python -m unittest tests.test_todo.Palabras.test_salida_sin_limites`

## El Observador · `infra/t7-observador` · ayudante del Regateador

- [ ] Clasifica bien los perfiles conocidos: (0,8, 14 rondas, sin ofenderse) → abuela; (0,6, 7, ofendido) → chato.
- [ ] Un vendedor que no se ha visto nunca se trata como desconocido (prudente).

Pruebas:

- `python -m unittest tests.test_todo.Cambista.test_perfil_nuevo`

## El Vigía · `infra/t7-vigia` · aparte

- [ ] Sin cambios en el juego, no avisa de nada.
- [ ] Cada novedad sale una vez, con su propuesta en frases cortas; lo que empieza en 20 ticks o menos se avisa una vez.
- [ ] Solo hace lecturas (GET); una lectura que falla no tira la pasada.
- [ ] Lo que no entiende sale como «ha cambiado, mirar el crudo», sin inventar.

Pruebas:

- `python -m unittest tests.test_todo.Vigia`
