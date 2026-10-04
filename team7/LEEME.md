# team7 · el sistema de negociación del Team 7

Código del Team 7 para *The Bazaar · Cromos de Madrid*: una cadena de agentes que lee el juego, decide y firma como
mucho un trato por tick. Python 3 de la biblioteca estándar, sin dependencias. El SDK (`bazaar_sdk.py`) está en la raíz
del repositorio.

## Las carpetas

```
team7/
├── agentes/      la cadena: un archivo por agente, sin red (se prueban sin el juego)
│   ├── hoy.json          las noticias del día: se cambian aquí, sin tocar código
│   └── parametros.json   todos los ajustes, con su rango y de dónde salen
├── programas/    los que hablan con el juego (en seco por defecto; --live para jugar)
├── lanzadores/   .ps1 para abrir cada programa en su propia ventana de Windows
├── sim/          simuladores sin red: vendedores, duelos, Market Test y torneos
├── tests/        pruebas sin red
├── datos/        datos reales guardados (calendario, duelos, estado) para pruebas y simulación
├── menus.json    qué compra y qué vende cada vendedor
└── ESTRUCTURA.md el dibujo de la cadena y quién hace qué
```

`runs/` (registros de cada ejecución) y `resultados/` (salida de los simuladores) se crean solos y no se suben.

## Probarlo sin red

```
cd team7
python -m unittest discover -s tests          # todas las pruebas
python programas/simular_vivo.py --ticks 200  # jugar.py --live contra un juego de mentira → runs/simulacion/
python sim/informe.py                         # simulaciones con los ajustes actuales → resultados/resumen.json
```

## Los programas

Todos se lanzan desde `team7/`. Los que pueden jugar van **en seco por defecto** (escriben lo que harían y no mandan
nada); con `--live` juegan de verdad. La clave se lee de la variable de entorno `BAZAAR_KEY` y no se escribe en ningún sitio.

| Programa | Qué hace | ¿Juega? |
|---|---|---|
| `programas/revisar.py` | Antes de jugar: comprueba que todo está listo (reloj, caja, valores, vendedores, menús) | Solo lee |
| `programas/jugar.py` | Juega la cadena con los vendedores y en El Rastro. `--vendedores picaros,abuela` para elegir con quién | Sí, con `--live` |
| `programas/duelos.py` | Juega la cadena solo en los duelos | Sí, con `--live` |
| `programas/ojos.py` | Cada 12 s lo ve todo, lo valida con la Contable y propone; no acepta nada | Solo lee |
| `programas/marcador.py` | Lee nuestra puntuación y avisa si algo va mal | Solo lee |
| `programas/vigia.py` | Avisa de lo nuevo en el juego (calendario, vendedores, mercados) | Solo lee |
| `programas/grabador.py` | Guarda los libros del Market Test; `--rejugar` los compara sin red | Solo lee |
| `programas/grabador_duelos.py` | Guarda cada duelo nuestro ronda a ronda | Solo lee |
| `programas/simular_vivo.py` | `jugar.py --live` contra un juego de mentira | Sin red |

En una ventana propia: `lanzadores\jugar.ps1`, `lanzadores\duelos.ps1` (en seco; `-Live` para jugar) y `lanzadores\ojos.ps1`.

### Reglas para jugar en vivo

- **Primero en seco**, y `programas/revisar.py` antes de la primera vez del día.
- **Un solo programa que acepte por clave.** `jugar.py` y `duelos.py` toman un candado (`agentes/candado.py`), pero
  solo lo ven los programas del mismo ordenador. No lanzar a la vez `dealers/smart_agent.py` ni `play.py`.
- **Parar:** crear el archivo `team7/runs/STOP`. El Guardia deja de firmar y se retira lo publicado en El Rastro, pero
  el proceso sigue vivo: para cerrarlo, Ctrl + C o cerrar la ventana. Borrar `runs/STOP` antes de volver a lanzar.

## Los agentes (`agentes/`)

En cada tick: **Ojos → Contable → Comerciante / Duelista → Guardia**, y **el Guion** al lado. Solo el Guardia firma.
El dibujo completo está en [`ESTRUCTURA.md`](ESTRUCTURA.md).

| Archivo | Agente | Qué hace |
|---|---|---|
| `cadena.py` | La cadena | `tick(lectura, memoria)` recorre a todos en orden y devuelve mensajes, cierres, el diario y como mucho UNA firma. Sin red |
| `ojos.py` | Los Ojos | Cómo estamos y las mejores oportunidades (`/api/me`, feed, ofertas, tablón). Guardan la memoria del mercado. Solo miran |
| `contable.py`, `valor.py` | La Contable | ¿Renta? ¿Cuánto? Jugando usa solo el `your_value` del juego; la calculadora (`valor.py`) queda para el simulador y las pruebas |
| `comerciante.py` | El Comerciante | Qué comprar y vender, y por qué canal: vendedores (`tienda.py`, el regateo) o El Rastro (`cambista.py`) |
| `duelo.py` | La Duelista | Duelos de precio y de precio + día |
| `guardia.py` | El Guardia | La única puerta antes de `accept`: comprueba la ficha de la Contable y que la oferta real coincide con lo hablado |
| `guion.py` | El Guion | Lee el calendario y prepara la jugada de cada evento antes de que llegue |
| `defensa.py` | El Escudo | Filtra textos sospechosos de entrada y de salida, y detecta incoherencias (el texto dice 15, la oferta pide 25) |
| `portavoz.py` | El Portavoz | Escribe el mensaje de cada precio; nunca pone otro número que el precio |
| `perfiles.py` | El Observador | Perfil de cada vendedor: con quién ser duro |
| `sondas.py` | El Espía | Sondas y detector de mala fe; lo que saca de un texto solo se apunta, nunca cambia un precio |
| `situacion.py` | El plan del día | Con el efectivo y `hoy.json` saca el modo de caja y los ajustes de todos |
| `prioridad.py` | — | Qué aceptar primero; los tres tratos de la escalera |
| `broker.py` | El Casamentero | Emparejador del Market Test (en el simulador no supera al puesto gratuito) |
| `menus.py`, `novedades.py`, `params.py`, `candado.py` | — | Menús de vendedores, avisos del Vigía, lectura de ajustes y candado de un solo aceptador |

Cómo se calcula el valor de una carta: [`agentes/VALORES.md`](agentes/VALORES.md).

## Ajustar sin tocar código

- `agentes/hoy.json`: duración del tick, páginas que completar, solo vender, categorías apagadas, enfados de vendedores,
  mercado barato donde publicar, y cualquier ajuste por su nombre en `"ajustes"`.
- `agentes/parametros.json`: el valor por defecto de cada ajuste, su rango y por qué.
- `menus.json`: `python programas/revisar.py --menus` añade los vendedores nuevos que lee del juego.

La historia de cómo se llegó aquí (planes, pruebas en seco, criterios de aceptación) está en [`../docs/historia/`](../docs/historia/).
