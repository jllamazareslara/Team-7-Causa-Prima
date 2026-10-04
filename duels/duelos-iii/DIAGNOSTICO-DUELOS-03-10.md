# Diagnóstico de los duelos del 3/10 · Team 7

Fuente: `cadena/datos/duelos-reales-03-10.json` del `main` actual (89 duelos grabados, 83 terminados).
Todo lo que sigue está contado sobre esos datos; lo que es deducción mía lo digo.

## Lo más importante: cómo puntúa de verdad un duelo

Comprobado duelo a duelo, sin una sola excepción en los 59 tratos:

```
resultado = ganancia × (1 − decay)^rondas          (si la ganancia es negativa, resta tal cual)
ganancia  = precio − coste + peso × días            vendiendo
            valor − precio − peso × días            comprando
rondas    = el que MENOS mensajes ha mandado de los dos
```

De ahí salen tres cosas que cambian la forma de jugar:

1. **Callar no cuesta.** Si el rival manda diez ofertas y nosotros una, cuenta una ronda. Si aceptamos su oferta sin haber escrito nada, cuentan cero rondas y el trato entra entero (duelos 5810 y 6088: 45,4 y 60,2 P sin descuento).
2. **Repetir una oferta sí cuesta.** Cada mensaje nuestro, cuando el rival también habla, es una ronda más (−6 % ayer, −10 % hoy).
3. **El día de entrega entra en la cuenta.** Vendiendo, cada día nos suma nuestro peso; comprando, nos lo quita. En los 21 duelos con día fue siempre así.

## Las cifras

| Sesión | Duelos | Con trato | Puntos | Rondas por trato | Tratos a 0 puntos | Tratos que restaron |
|---|---|---|---|---|---|---|
| 1 (solo precio, decay 0,06) | 34 | 22 (65 %) | 257,8 | 3,2 | 10 | 0 |
| 2 (solo precio, decay 0,06) | 34 | 25 (74 %) | 449,6 | 3,8 | 1 | 0 |
| 3 (precio + día, decay 0,08; solo 15 grabados) | 15 | 12 (80 %) | 237,8 | 2,0 | 0 | 2 |

Por los números de tick, la sesión 1 parece la práctica del viernes y la 2, Duels I; la 3 es Duels II. No está escrito en los datos: es mi lectura.

## Lo malo, por orden de lo que costó

1. **El 71 % de nuestros mensajes repetía la oferta anterior** (441 de 625). «173?» quince veces, «122?» quince veces. En el duelo 2440 el rival subió solo de 51 a 86 mientras repetíamos: 16 rondas, y 10 P de ganancia se quedaron en 3,7.
   Con los mismos precios y una sola ronda por trato, los tratos con puntos habrían dado 1 084 P en vez de 952 (+14 %).
2. **Cinco tratos que estaban dentro del límite se quedaron sin cerrar** (2367, 2467, 2487, 2550, 2551): 71 P de ganancia en la mesa. En los cinco el rival tenía en pie una oferta que nos daba ganancia y el duelo llegó al plazo sin aceptarla. Dos de ellos (2367 y 2467) acababan en el mismo tick que otro duelo, y el juego deja una sola aceptación por equipo y tick (`accepts_per_team_per_tick: 1`). De los otros tres no sé la causa: el programa de entonces solo aceptaba en el último tick, sin segundo intento.
3. **Diez tratos a cero puntos en la sesión 1**: cerramos exactamente en nuestro límite.
4. **Dos tratos restaron en Duels II** (5635: −4,2 y 5888: −3,1): el precio era bueno, pero el día 10 nos costaba más que la diferencia. Se miró solo el precio. Ana lo corrigió anoche con el precio efectivo.
5. **Siete duelos de Duels II sin un solo mensaje nuestro.** Es el cuello de botella de «una oferta por tick para todo el equipo» que Juan quitó en `7bef648`.
6. **El «objeto» no es el escenario.** La cadena guardaba el límite del rival por nombre de objeto, pero el mismo objeto sale con límites distintos en cada duelo (El Tren Fantasma: coste 83 en uno; en otro, valor 114 con un rival que vendía a 73). Esa memoria podía hacer creer que no había trato posible.

## Lo bueno

- Los dos mejores resultados (71 y 74 P, duelos 2450 y 2451) fueron ofertas nuestras de apertura a ×1,6 y ×0,6 que el rival aceptó sin escribir nada: cero rondas.
- En 35 de los 59 tratos aceptamos una oferta del rival; en 23 aceptó él la nuestra. Las dos vías dan puntos.
- Nunca se cerró con el precio fuera del límite.

## Cómo se comportan los rivales (lo que se ve en los datos)

- **19 de 83 no escribieron nada** (23 %). Cuatro de ellos aceptaron una oferta nuestra; los demás no hicieron nada.
- **Muchos caminan solos**: suben o bajan su precio cada tick, hagamos lo que hagamos, y luego se plantan (Verde 51→86, Oro 110→78, Sol 32→72 de tres en tres).
- **Algunos dicen un precio y no se mueven** (128 dos veces; 109 cinco veces; 83 seis veces).
- **Algunos van a saltos**: paran varios ticks y siguen (duelos 277, 2309, 2334). Con ticks de 15 s hoy habrá más: un agente que llama a un modelo no llega a todos los ticks.
- **Algunos solo se mueven cuando nos movemos** y aceptan en cuanto cedemos un par de veces (5690, 5691).
- **El 83 % de los que escriben lo hace en el primer tick** del duelo.
- **Con el día**: los rivales que compran proponen casi siempre el día 0; los que venden, el 10 (o el 0). Varios siguieron nuestro día cuando lo mantuvimos. Uno cambió de día bajando el precio 33 P (duelo 5772): a ese rival cada día le costaba unas 6,6 P.
- Nuestros pesos por día fueron de 0,85 a 5,94 vendiendo (mediana 2,4) y de 1,71 a 9,0 comprando (mediana 3,4).

## Lo que NO se puede sacar de estos datos

- **Qué equipo es cada rival.** Hay 8 alias para 17 equipos, y el mismo alias se comporta de formas opuestas de un duelo a otro. El «ranking de rivales por alias» de mi borrador de anoche no significa nada: está retirado.
- **Los límites de los rivales**: nunca los vemos.
- **Qué harán hoy**: los demás equipos también han tenido la noche para cambiar su agente.
