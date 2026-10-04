# Duelos III · qué hay listo y cómo lanzarlo

Domingo 4/10. **Duels III a las 11:00** y **la final a las 14:00** (leído en `/api/schedule` a las 08:05): 12 ticks de 15 s por duelo, −10 % por ronda, precio + día de entrega, 4 duelos a la vez, dos vueltas.

## En una frase

Ayer perdíamos los puntos repitiendo la misma oferta cada tick. La Duelista nueva **calla mientras el rival se acerca solo, habla poco y cierra con margen de tiempo**. En las pruebas saca alrededor de un 60 % más que el código de `main` contra rivales inventados y un 37 % más con las ofertas reales de ayer, sin un solo trato fuera del límite.

## Por qué (medido en los 83 duelos terminados de ayer)

- `resultado = ganancia × (1 − decay)^rondas`, y **las rondas son los mensajes del que menos ha escrito**. Callar no descuenta. Aceptar su oferta sin haber hablado tampoco.
- El 71 % de nuestros mensajes repetía la oferta anterior. Cada uno costaba una ronda cuando el rival hablaba.
- Con día de entrega: vendiendo cada día nos **suma** nuestro peso, comprando nos lo **quita**.
- Detalle y cifras: `DIAGNOSTICO-DUELOS-03-10.md`.

## Qué hace la Duelista nueva

1. **Los dos primeros ticks escucha.** Si el rival abre con una oferta muy buena (al menos tres cuartos de lo que pediríamos nosotros al abrir), la acepta en el acto: cero rondas.
2. **Si el rival camina solo hacia nosotros, no le escribe.** Su oferta sigue en pie; se acepta cuando llega el turno de cierre, o antes si ya nos da lo que pedíamos.
3. **Si el rival no escribe, baja el precio poco a poco cada tick.** Es gratis: sin mensajes suyos no hay rondas. Nunca repite una oferta.
4. **Si el rival habla pero se planta fuera de nuestro límite, habla poco.** Con los que solo se mueven cuando nos movemos, cede una quinta parte de lo que ceden ellos. Como mucho cuatro rondas antes del remate.
5. **El día va a quien más le importa.** Si nuestro peso es alto, pedimos nuestro día (10 vendiendo, 0 comprando); si es bajo, le damos el suyo y cobramos en precio. Si su oferta buena viene en su día y a nosotros nos importa mucho más, una vez le pedimos el nuestro compensándole.
6. **Cierra con margen.** El juego deja una aceptación por equipo y tick: los duelos que acaban a la vez cierran a 2, 3, 4 y 5 ticks del final, uno por tick. Si dos coinciden, firma primero el que está en su último tick y después el que más da. Antes de aceptar vuelve a leer la oferta, por si el rival la ha cambiado.
7. **Nunca acepta ni ofrece algo que reste**, contando el día. El Guardia sigue firmando cada aceptación.

## Los números

| Prueba | Código de `main` | Duelista nueva |
|---|---|---|
| 4 800 duelos inventados, programa real de punta a punta (3 semillas) | 9,6 a 10,7 P por duelo · 46-48 % de tratos · 4,7 rondas | **15,9 a 16,3 P por duelo · 69-70 % de tratos · 1,9 rondas** |
| Ofertas reales que mandaron los rivales ayer, repetidas tick a tick (64 duelos) | 718 P | **983 P** (lo que pasó de verdad: 799 P) |
| Tratos fuera del límite | 0 | 0 |
| Errores del programa / peticiones rechazadas | 0 / 0 | 0 / 0 |
| Prueba de aguante: 40 000 duelos, 20 semillas (con día y solo precio) | no medido | 0 errores · 0 peticiones rechazadas · 0 tratos que resten |
| Tests | 193, con 8 fallos que ya trae `main` | 220: los mismos 8 fallos, 27 pruebas nuevas en verde |

Cómo leerlos:
- **Los rivales inventados son supuestos.** Copian lo que se vio ayer (mudos, los que caminan solos, los que se plantan, los que aceptan lo nuestro, los lentos), pero la mezcla de hoy no se conoce. Por eso miré cada tipo por separado: de los diez tipos que juegan, la nueva gana en nueve y pierde por poco contra el que parte la diferencia (25,3 frente a 27,2).
- **La repetición de duelos reales es un suelo**: el rival repetido no contesta a lo nuestro ni lo acepta, así que solo cuenta lo que sacaríamos aceptando ofertas que hizo de verdad.
- Ninguna de las dos cosas es el juego de hoy. Lo que sí es seguro: las reglas de puntuación están medidas, no supuestas.

## Cómo lanzarlo

Un solo programa juega los duelos con la clave del equipo. Antes de lanzar, **confirmad en el grupo que nadie más tiene `duelos.py` abierto**.

**En este ordenador** (carpeta ya preparada, con la rama `silo/duelo/duelos-iii`):

```
cd "…\causa prima hackathon\duelos-iii-listo\cadena"
.\lanzar-duelos.ps1            # en seco, 3 ticks: solo mira (hacedlo en cuanto empiecen los duelos)
.\lanzar-duelos.ps1 -Live      # en vivo: pide escribir SI
```

**En otro ordenador** (el de Juan o Ana), sobre un `main` al día:

```
git checkout -b silo/duelo/duelos-iii origin/main
git am "…\duelos-iii-noche\PROPUESTA-duelos-iii.patch"
cd cadena ; python -m unittest tests.test_duelista_ticks      # 27 OK
.\lanzar-duelos.ps1 -Live
```

No he subido nada a GitHub ni he lanzado nada contra el juego con la clave: eso lo decidís vosotras. Lo único que leí del juego fueron tres páginas públicas sin clave (`/api/schedule`, `/api/clock` y la portada), para confirmar la hora y el límite de aceptaciones.

Toca **15 líneas del núcleo** (`t7/cadena.py`, solo el bloque de duelos): hace falta el visto bueno de Juan y Ana según el plan del día. El parche va entero: sin ese trozo la cadena no le pasa a la Duelista el estado por ticks y se queda jugando la de ayer.

**Entre Duels III y la final** se puede afinar con lo que pase: `python grabador_duelos.py --cada 30` graba los duelos (solo lee) y `python sim\duelos_vivo.py --reales --datos datos\duelos-reales-04-10.json` dice qué habría sacado la Duelista con esas mismas ofertas.

## Revisión independiente

Un segundo agente, sin ver mi razonamiento, intentó romper la Duelista con 14 000 estados al azar y 959 duelos contra rivales erráticos: ningún trato ni oferta que reste, ningún precio al otro lado del límite. Reprodujo cuatro fallos y los cuatro están corregidos (tres con prueba propia): un paquete idéntico reenviado por el redondeo, un trato perdido porque la única aceptación del tick se la llevaba un duelo al que aún le quedaba tiempo, un `hoy.json` con forma equivocada que paraba el tick, y una excepción al releer la oferta.

Queda abierto, y no tiene arreglo desde nuestro lado: entre que releemos la oferta y aceptamos pasa una petición de red; si el rival cambia su oferta justo ahí, se acepta la nueva.

## Qué mirar en los primeros dos minutos

- La ventana escribe una línea `DUELISTA` por duelo y tick, con el motivo en claro («escuchamos», «viene solo hacia nosotros», «se acaba el tiempo»).
- `runs\crudo.jsonl`: el primer duelo tal cual llega. `days_meaning` debe decir *adds* si vendemos y *costs* si compramos. Si dijera otra cosa, **parad** (`runs\STOP`) y avisad: todo el cálculo del día depende de eso.
- `runs\errores.jsonl`: debe estar vacío o casi.
- Señal de que algo va mal: muchos «NO SE ACEPTA» seguidos, o duelos que llegan al final sin trato teniendo una oferta del rival con ganancia.

## Mandos (en `cadena\t7\hoy.json`, se releen en cada tick: no hay que relanzar)

| Si pasa esto | Tocar | A |
|---|---|---|
| Casi nadie acepta nuestras ofertas y acabamos en el remate | `duelo.apertura_vendedor` / `duelo.apertura_comprador` | 1.6 / 0.6 (ahora 1.8 / 0.55) |
| Muchos tratos cerrados con muy poca ganancia | `duelo.cuota_minima` | 0.25 (ahora 0.15) |
| Muchos duelos sin trato por pedir demasiado al final | `duelo.cuota_minima` | 0.05 |
| Se escapan tratos en el último tick | `duelo.cierre_ticks` | 3 (ahora 2) y `duelo.apurar` a 0 |
| Los rivales contestan muy lentos y hablamos antes de tiempo | `duelo.paciencia` | 3 (ahora 2) |
| Queréis volver a la Duelista de ayer | borrar la rama: `git checkout main` y relanzar | |

Se añaden dentro de `"ajustes": { … }` con su nombre completo. Un valor fuera de rango se recorta y se avisa en la ventana.

## Lo que no sé

- **Si hoy el juego cuenta las rondas igual que ayer.** El calendario solo cambia el decay y los ticks. El programa lee `rounds` del juego en cada tick; si viera otra cosa, se nota en `runs\diario.jsonl`.
- **Cuántas aceptaciones de duelo deja el juego por tick.** `/api/clock` dice 1 por equipo; el PDF oficial dice que los duelos tienen su propio cupo. He supuesto 1: es lo prudente y solo cuesta cerrar algún duelo dos o tres ticks antes.
- **Qué han cambiado los otros equipos esta noche.** Si muchos callan como nosotros, habrá más duelos de «rival mudo»: ahí bajamos el precio tick a tick, que es lo que toca.
- **El cambio de día.** Depende de que el rival acepte un día peor a cambio de precio. En el juego falso apenas mueve el resultado; está limitado a cuando el día vale al menos la mitad de lo que ya tenemos en la mesa. Se apaga con `duelo.cambiar_dia: 0`.

## Qué hay en esta carpeta

- `LEEME-DUELOS-III.md`: esta hoja.
- `DIAGNOSTICO-DUELOS-03-10.md`: lo bueno y lo malo de ayer, con cifras.
- `INVESTIGACION-CON-FUENTES.md`: teoría de negociación y torneos (ANAC, agentes con modelos de lenguaje), 28 fuentes abiertas y una lista de lo no verificado.
- `PROPUESTA-duelos-iii.patch`: el cambio entero, para `git am`.
- `_descartado-00h30-NO-USAR\`: mis borradores de las 00:30. Tenían errores; no los uséis.
