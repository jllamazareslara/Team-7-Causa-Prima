# Investigación con fuentes — Duelos III (Team 7, The Bazaar)

Fecha: 4 de octubre de 2026. Solo investigación; no se ha tocado código ni repositorio.

Cómo leer este documento:
- **[T]** = leí el texto completo de la fuente (PDF convertido a texto).
- **[R]** = abrí la página y las cifras salen del resumen o abstract de esa página.
- **[S]** = fuente secundaria (nota de prensa o artículo que cuenta el estudio).
- **"Lectura propia"** = deducción mía a partir de la mecánica que medisteis. No es de ninguna fuente.

La mecánica usada es la vuestra, sin cambios: puntuación = utilidad × 0,9^rondas, con rondas = mín(mensajes nuestros, mensajes del rival) — cuentan también los mensajes sin precio (duelo real 277); 12 ticks; una aceptación por equipo y tick; la aceptación se liquida en el tick siguiente.

---

## Lo que dice la investigación, en limpio

1. **Contra rivales que ceden solos, lo que decide es cuándo aceptar, no qué ofrecer.** El peso de la regla de aceptación pasa del 5 % al 47 % del resultado cuando el rival es concesivo (Baarslag 2014). Callar y esperar está respaldado.
2. **Ser duro paga contra concesivos** (cuanto menos se cede, más se gana: R² = 0,86, ANAC 2011). Contra un duro que no se mueve, lo único que da puntos es aceptar si la utilidad es positiva.
3. **Aceptar mirando el reloj y el historial gana a las reglas ingenuas**: 0,675 frente a 0,567 de "acepto si iguala mi próxima oferta". Un umbral fijo alto solo cierra el 26-38 % de los tratos.
4. **Un modelo complejo del rival no compensa** (4 % del resultado; mejora de 0,01 a 0,03). Basta clasificar al rival en 2-3 ticks: mudo, caminante, fijo o reactivo.
5. **Regla de un mensaje (lectura propia):** hablar solo si p × ΔU > U_actual / 9. Contra un rival mudo, hablar es gratis (rondas = 0).
6. **El día de entrega es donde está el valor escondido**: hasta 10 × |w_s − w_b| primas. Un solo mensaje de trueque día-por-precio puede valer mucho más que el 10 % que cuesta. Y toda aceptación debe calcularse con la utilidad completa, días incluidos.
7. **Los acuerdos se amontonan al final del plazo, pero apurar demasiado rompe tratos**: los fracasos suben del 4,5 % al 31-38 % con plazos muy cortos, y las acciones de último segundo pueden no entrar. Con una aceptación por tick y 4 duelos, hay que escalonar.
8. **El ancla funciona con rivales que reaccionan** (LLM: correlación 0,716 entre primera oferta y precio final) y no con los que caminan solos. Ancla extrema = riesgo de ruptura.
9. **Un agente determinista debe ignorar el texto del rival**: los LLM ceden ante lenguaje de "desesperación" (+20 %), revelan su límite y parten la diferencia.

---

## 0. Cuentas propias a partir de la mecánica (no son de ninguna fuente)

- **Coste de un mensaje.** Si el rival ha hablado más que nosotros, cada mensaje nuestro multiplica todo por 0,9. Sea U_f lo que ganaríamos callados (aceptando lo que hay) y U_n lo que ganaríamos si el mensaje funciona, con probabilidad p. Hablar compensa solo si
  **p × (U_n − U_f) > U_f / 9.**
  Ejemplo: U_f = 30 y U_n = 70 → basta p > 8,3 %. Con U_f = 50 y U_n = 55 → haría falta p > 111 %: nunca.
- **Rival mudo.** rondas = mín(nuestros, 0) = 0. Podemos mandar las ofertas que queramos sin perder nada mientras él no escriba.
- **Quién pierde más por ronda.** El 10 % se aplica a la utilidad de cada uno. Si vamos ganando 60 y el rival está pegado a su límite ganando 5, cada ronda nos cuesta 6 a nosotros y 0,5 a él. Regatear cuando vamos por delante nos perjudica a nosotros.

---

## 1. Negociación automática (ANAC y alrededores)

### 1.1 Tácticas dependientes del tiempo — Faratin, Sierra y Jennings (1998) [T]
Definen la oferta como función del tiempo con un parámetro β: **Boulware** (β < 1) mantiene la oferta hasta casi el final y entonces cede hasta el valor de reserva; **Conceder** (β > 1) va rápido a su reserva. En sus experimentos, Boulware no fue el mejor: obtuvo utilidad alta cuando cerró, pero cerró bastantes menos tratos; ganaron las tácticas de concesión constante (lineales) y, después, las imitativas. Con plazos cortos, solo Conceder cerraba cerca del 90 % de los tratos. El artículo ya incluye un **coste por mensaje**: la utilidad ajustada es la utilidad multiplicada por una función del número de mensajes intercambiados, y con ese coste las tácticas rápidas se quedan con más.

**Qué significa para nuestro agente:** los rivales tipo (b) son Conceder o lineales, y contra ellos conviene esperar. Si nos toca hablar (rival mudo), una escalera tipo Boulware es correcta porque ahí los mensajes son gratis, pero debe llegar a tiempo: Boulware pierde tratos por apurar.

### 1.2 Condiciones de aceptación — Baarslag, Hindriks y Jonker (2011; versión revista 2014) [T]
Definiciones: **AC_next** acepta si la oferta del rival vale al menos lo que yo iba a ofrecer; **AC_const(α)** acepta por encima de un umbral fijo; **AC_time(T)** acepta cualquier cosa pasado el instante T; **AC_combi(T, α)** = AC_next, o bien "ya pasó T y la oferta supera α", donde α es el máximo (o la media) de lo que el rival ofreció en una ventana anterior del mismo tamaño que el tiempo que queda. Resultados (168 negociaciones por condición, T = 0,99):

| Condición | % acuerdos | Utilidad media de los acuerdos | Media total |
|---|---|---|---|
| AC_combi (máximo de la ventana) | 99 % | 0,679 | 0,675 |
| AC_time(0,99) | 99 % | 0,622 | 0,618 |
| AC_next | 72 % | 0,787 | 0,567 |
| AC_const(0,8) | 38 % | 0,851 | 0,324 |
| AC_const(0,9) | 26 % | 0,935 | 0,239 |

AC_combi rinde un 18 % más que AC_next y un 7 % más que los mecanismos propios de los agentes. Exigir "lo mejor visto en toda la negociación" funciona peor (89 % de acuerdos).

**Qué significa para nuestro agente:** regla de aceptación = "cerca del final, acepto si la oferta actual iguala lo mejor que el rival dio en los últimos k ticks, siendo k los ticks que quedan". Nunca un umbral fijo exigente. Los rivales tipo (d) usan AC_next: aceptan en cuanto nuestra oferta iguala su próxima demanda, así que hablarles no nos da nada que no consigamos esperando un tick y aceptando sin coste.

### 1.3 Aceptar de forma óptima — Baarslag y Hindriks (2013) [T]
Tratan la aceptación como un problema de parada óptima: con j ofertas por ver, aceptar x solo si x ≥ v_j, con v_j = E[máx(X, v_{j−1})] − C y v_0 = 0, donde C es el coste de ver una oferta más. Frente a un rival aleatorio uniforme, v_j = 1/2 + v_{j−1}²/2 (0,5; 0,625; 0,695...). La regla supera a los mecanismos de aceptación de los agentes ANAC, sobre todo cuando quedan pocas rondas.

**Qué significa para nuestro agente:** mientras callamos, C = 0: ver una oferta más no cuesta nada, así que se espera mientras el rival siga mejorando. Cuando el rival se estanca, esperar ya no aporta y se acepta. El umbral debe bajar según se acaban los ticks.

### 1.4 Qué pesa más: pujar, aceptar o modelar al rival — Baarslag, Dirkzwager, Hindriks y Jonker (2014) [T]
1.584 agentes combinados y 277.200 negociaciones. Parte del resultado explicada por cada pieza: estrategia de oferta 58 %, aceptación 12 %, modelo del rival 4 %. Sin modelo: 0,69; con el mejor modelo: 0,72. Contra rivales cada vez más concesivos, el peso de la oferta baja del 77 % al 42 % y el de la aceptación sube del 5 % al 47 %.

**Qué significa para nuestro agente:** contra caminantes, el esfuerzo de esta mañana va a la regla de aceptación y a su calendario, no a un modelo fino del rival.

### 1.5 Modelos de frecuencia para pesos — Baarslag, Hendrikx, Hindriks y Jonker (2012) [T]
Los modelos de frecuencia estiman el peso de cada cuestión por lo poco que el rival la cambia entre ofertas. Ganan a los bayesianos de forma consistente y son más robustos ante rivales erráticos. La ganancia es pequeña: +0,0135 sobre no usar modelo; con modelo perfecto, +0,041 en el dominio más grande. Ayudan más cuanto más duro es el rival.

**Qué significa para nuestro agente:** con solo dos cuestiones (precio y día) basta una regla simple: si el rival mueve el precio y deja el día clavado en su extremo, o nunca toca el día o el día le importa mucho. Si en dos ofertas cambia día por precio, su peso es Δprecio / Δdías. No hace falta más.

### 1.6 Ganadores ANAC y por qué ganaron
- **2010, AgentK** [T, descrito en 1.2]: aceptación basada en media y varianza de las ofertas recibidas, para estimar la mejor oferta que aún puede llegar. Los tres primeros usaban aceptación por tiempo y utilidad; los de solo utilidad quedaron detrás.
- **2011, HardHeaded (0,749) y Gahboninho (0,740)** [T]: HardHeaded cede poco y tarde (Boulware y, con descuento, cambia a Conceder); usa un modelo de frecuencia para elegir, entre ofertas que le valen lo mismo, la mejor para el rival. Gahboninho mide cuánto cede el rival y, cuanto más cede, más duro se pone; al final propone la mejor oferta que el rival hizo. Contra un concesivo, ceder menos da más (R² = 0,86). Contra un duro, ceder da algo más, con relación débil (R² = 0,20), y ahí manda la aceptación.
- **2012, CUHKAgent** [T, una frase en Baarslag et al. 2015]: evita ser explotado y maximiza la aceptabilidad de su propuesta.
- **Lecciones generales** [T/R]: "no compensa ser demasiado amable"; no hay una estrategia que gane en todos los escenarios; "los agentes duros rinden mejor, los modelos de rival importan menos de lo pensado, los modelos simples son los mejores" (Jonker et al. 2017).
- **MiCRO (de Jonge 2022)** [T]: estrategia mínima sin modelo de rival: hace una concesión mínima solo cuando el rival hace una oferta nueva; si el rival repite, MiCRO repite. Acepta si la oferta recibida iguala lo peor que está dispuesto a proponer. Supera a los mejores de ANAC 2012, 2013 y 2018 y empata con AgentGG (2019). Aviso del autor: una estrategia puramente adaptativa no es estable; si todos esperan a que ceda el otro, gana el duro.
- **ANAC 2025** [T]: en la liga de cadena de suministro (precio, cantidad y fecha de entrega) ganaron por segundo año heurísticas específicas y prudentes frente a modelos de rival complejos; el ganador fija suelos de precio para que todo contrato dé beneficio positivo.

**Qué significa para nuestro agente:** de MiCRO se toma "no ceder nunca ante una repetición" y la regla de aceptación. No se copia el responder a cada mensaje, porque aquí eso es justo lo que cuesta. Suelo innegociable: utilidad positiva con días incluidos. Si muchos equipos pasan a callar, habrá más duelos mudo contra mudo (ver sección 6).

---

## 2. Varias cuestiones: trueques y ofertas equivalentes

### 2.1 Algoritmo de trueque de Faratin, Sierra y Jennings (2002) — no verificado en texto completo
No pude abrir el artículo (acceso denegado en tres repositorios). Solo confirmé la ficha y la descripción breve: el agente se mueve por su curva de igual utilidad hacia la oferta más parecida a la última del rival, usando similitud difusa y escalada. Lo que sigue es lectura propia.

**Lectura propia con vuestras utilidades.** Excedente conjunto = valor − coste + (w_s − w_b) × días. Si w_s > w_b, el día eficiente es 10; si w_s < w_b, es 0. Mover el día Δ a favor del rival y cobrárselo en precio a nuestra tasa nos deja igual y a él le da (w_rival − w_nuestro) × Δ: solo le interesa si su peso es mayor que el nuestro.

**Qué significa para nuestro agente:** con peso propio alto (por ejemplo 7-9), el día vale hasta 70-90 primas, más que la ganancia típica: hay que pelear el día. Con peso bajo (1-2), se regala el día y se cobra en precio.

### 2.2 Ofertas equivalentes simultáneas (MESO) — Leonardelli, Gu, McRuer, Medvec y Galinsky (2019) [R]
Seis experimentos comparan dar a elegir entre varias primeras ofertas de igual valor para quien las hace frente a una sola. Las MESO anclan más fuerte (se perciben como intento sincero de acuerdo), dan mayor resultado conjunto (es más probable que una de ellas sea un buen punto de partida para el otro) y mejoran la reputación de quien ofrece. El trabajo original de Medvec y Galinsky (2005) no lo abrí.

**Qué significa para nuestro agente:** "misma utilidad para nosotros, distinto día" es la versión de dos cuestiones de una MESO. Si el formato admite dos paquetes en un mensaje (día 0 a precio P, o día 10 a P ± 10 × w_nuestro), se mandan juntos: cuesta una ronda y el rival revela su peso al elegir. Si solo admite un paquete, alternarlos es gratis contra un mudo; contra un hablador se manda uno solo, el de la esquina que nos conviene, y solo si pasa la regla de la sección 0.

---

## 3. Coste por intercambio, plazos, espera y última hora

### 3.1 Rubinstein (1982) [R]
Ofertas alternas sin plazo. Con descuento común δ, quien propone primero se lleva **1/(1+δ)** y el otro δ/(1+δ); con descuentos distintos, (1−δ₂)/(1−δ₁δ₂). Con δ = 0,9: 52,6 % y 47,4 %. El acuerdo es inmediato. Con coste fijo por periodo (c₁, c₂): si c₁ < c₂, el jugador 1 se lleva todo; si c₁ > c₂, solo c₂.

**Qué significa para nuestro agente:** el modelo supone que esperar cuesta a los dos. Aquí esperar callado no cuesta nada y el descuento solo corre cuando hablan ambos, así que la presión no viene del descuento sino del plazo de 12 ticks. Del caso de coste fijo queda una idea: el reparto es muy sensible a quién soporta el coste de seguir; no hay que ser nosotros.

### 3.2 Efecto del plazo — Roth, Murnighan y Schoumaker (1988); Gneezy, Haruvy y Roth (2003) [T el segundo]
El artículo de 1988 no lo abrí; lo cito a través del de 2003, que dice que la concentración de acuerdos al final del tiempo es mucho más robusta que cualquier otro rasgo del resultado. En el experimento de 2003, el 87,5 % de los acuerdos llegó en los últimos 10 segundos con plazo de un minuto, y el 75,6 % en los últimos 20 con plazo de tres. Quien propone retrasa a propósito sus ofertas para convertir el final en un "lo tomas o lo dejas", y con plazo se lleva más: la parte aceptada por el otro baja de 13,34 (sin plazo) a 10,52-11,48 sobre 25.

**Qué significa para nuestro agente:** quien fija la última oferta antes del cierre se queda con más. Contra un mudo que solo acepta, mantener alto y bajar tarde; contra un caminante, su último precio es el mejor, así que aceptar tarde.

### 3.3 Presión de tiempo — Karagözoğlu y Kocher (2019) [T]
Con plazo de 10 minutos fracasa el 4,5 % de las negociaciones; con 90 segundos, el 31,4 %; con 45 segundos, el 38,1 %. Primeras propuestas, concesiones y acuerdos son parecidos; lo que cambia es que se rompen más tratos, sobre todo cuando las primeras propuestas están muy lejos.

**Qué significa para nuestro agente:** aceptar tarde, pero no lo último. Un ancla muy lejana con 12 ticks es la combinación que más tratos rompe.

### 3.4 Pujas de último minuto — Roth y Ockenfels (2002) [R]
En subastas con cierre fijo (eBay) hay mucha más puja de último momento que con cierre prorrogable (Amazon), y más entre expertos. Pujar tarde es racional porque evita guerras de pujas, pero las pujas muy tardías tienen una probabilidad real de no llegar a registrarse.

**Qué significa para nuestro agente:** la aceptación se liquida un tick después y solo hay una por tick para 4 duelos. Tomar el tick 11 como último seguro hasta confirmar si una aceptación en el 12 liquida. Aceptar primero los duelos estancados (esperar ya no da nada) y dejar los ticks finales para los que siguen caminando, ordenados por utilidad en juego. El rival tiene el mismo cuello de botella: nuestras mejores ofertas a un mudo deben estar puestas hacia el tick 9-10.

---

## 4. Primera oferta y ancla

- **Galinsky y Mussweiler (2001)** [R]: en tres experimentos, quien hizo la primera oferta obtuvo mejor resultado y la primera oferta predijo con fuerza el precio final. El efecto desaparece si el otro piensa en su propio objetivo o en el límite de quien ancla.
- **Mason, Lee, Wiley y Ames (2013)** [S]: una primera oferta con cifra precisa (5.015 en vez de 5.000) hace que el otro contraoferte más cerca, porque atribuye más información a quien la hace.
- **Loschelder, Trötschel, Swaab, Friese y Galinsky (2016)** [R]: la primera oferta ancla, pero también revela prioridades. Si las revela y el otro es egoísta, mover primero pasa a ser desventaja.
- **Schweinsberg, Ku, Wang y Pillutla (2012)** [R]: las primeras ofertas extremas ofenden y provocan ruptura; anclan solo si se evita la ruptura. No pude verificar las tasas exactas de ruptura.

**Qué significa para nuestro agente:** el ancla solo sirve contra rivales que reaccionan (espejo, partidores de diferencia, LLM). Contra los que caminan solos no mueve nada y cuesta un 10 %. Si se ancla: un solo mensaje, cifra precisa, exigente pero no absurda, y sin dejar ver cuánto nos importa el día. Un rival bien hecho que piensa en su propio objetivo anula el ancla; nuestro agente debe hacer lo mismo y no dejar que la cifra del rival mueva su límite.

---

## 5. LLM contra LLM

- **NegotiationArena — Bianchi et al. (2024)** [R]: en compraventa (vendedor valora 40, comprador 60, el vendedor abre, 10 turnos) el precio final correlaciona 0,716 con la primera propuesta. Los agentes parten la diferencia entre las dos últimas ofertas. Fingirse desesperado mejora el pago un 20 % contra GPT-4. Un comprador con valoración inflada contraoferta por encima de lo que pedía el vendedor el 41 % de las veces. Los precios quedaron bajo el punto medio (GPT-4 comprador: 41 de media), es decir, abrir primero no bastó.
- **Xia et al. (2024)** [R]: comprar es mucho más difícil que vender para un LLM; los compradores abren al 90-100 % de su presupuesto. Un generador determinista de ofertas (precio = (0,5 + 0,5 × turno/turnos_máx) × presupuesto) con el LLM solo redactando sube la tasa de acuerdo del 26,67 % al 88,88 % y multiplica por diez el beneficio.
- **Shah et al. (2025)** [R]: los LLM anclan en los extremos de la zona de acuerdo, varios revelan pronto su precio de reserva, algunos casi no tienen rigidez (ceden a todo) y otros son más rígidos que los humanos; no se adaptan al poder relativo.
- **Zhu et al. (2025)** [R]: agentes distintos logran resultados muy distintos; anomalías: pagar por encima del presupuesto (hasta 11,76 % de los casos en el peor modelo), aceptar caro tras revelar el presupuesto, bucles sin acuerdo.
- **Vaccaro et al. (2025), competición con 182.812 negociaciones** [R]: los agentes "cálidos" cierran más tratos; los "dominantes" reclaman más valor pero cierran menos y alargan la conversación. Uno de los mejores usó inyección de instrucciones para que el rival revelara su posición.
- **Project Deal (Anthropic, diciembre 2025)** [S]: 186 tratos; el modelo más capaz vendió más caro (+2,68 a +3,64 dólares por artículo). Los vendedores "agresivos" sacaron más solo porque abrían más alto.
- No encontré ningún relato fiable de un hackathon 2025-2026 con la mecánica de este juego.

**Qué significa para nuestro agente:**
- Defensa: leer solo precio y día; ignorar todo el texto (lástima, urgencia, "última oferta", instrucciones incrustadas). No revelar nunca coste, valor ni peso del día.
- Aprovechar: muchos rivales LLM ceden solos o se pegan a su límite enseguida, así que callar y aceptar su mejor oferta funciona. Si un rival parte la diferencia, un ancla lejana mueve su siguiente oferta la mitad de la distancia: se envía si esa mitad supera U_actual / 9. El texto de "desesperación" es gratis solo como añadido a un mensaje que ya íbamos a mandar.

---

## 6. Lo que contradice "callar, dejar andar al rival, aceptar tarde, hablar solo si se estanca"

1. **Rival mudo (25 %).** Callar los dos da 0. Aquí hablar es gratis, así que hay que hablar pronto: si en 1-2 ticks no ha escrito, empezar la escalera. Si más equipos adoptan el silencio, este caso crecerá (de Jonge 2022).
2. **El día de entrega.** Aceptar en silencio es tragarse el día que nombra el rival, casi siempre su extremo. Con peso propio alto, un mensaje de trueque puede crear decenas de primas y supera de sobra el 10 % (sección 2). Es la contradicción más rentable.
3. **Rivales espejo o MiCRO.** Solo ceden cuando hacemos una oferta nueva. Callar los congela. Cada mensaje compra una concesión suya: merece la pena si esa concesión supera U_actual / 9.
4. **Ancla contra reactivos.** La literatura de primera oferta y los datos de LLM dicen que quien ancla gana, siempre que el rival reaccione. El silencio renuncia a eso.
5. **"Aceptar tarde" tiene tope.** Los fracasos se disparan con el plazo apurado, las acciones de última hora pueden no entrar y solo hay una aceptación por tick. Además, a un rival fijo (c) hay que aceptarlo pronto: esperar no da nada y ocupa un hueco final.
6. **Boulware puro cierra menos tratos** (Faratin 1998). Esperar sin plan de salida pierde duelos; hace falta un tick límite por duelo.

Lo que sí respalda la estrategia: dureza contra concesivos, peso de la aceptación, coste por mensaje (Faratin ya lo midió) y poca utilidad de modelos complejos.

---

## 7. Fuentes abiertas

Negociación automática
- Faratin, Sierra, Jennings (1998). Negotiation decision functions for autonomous agents. Robotics and Autonomous Systems 24. [T] https://jmvidal.cse.sc.edu/library/faratin98a.pdf
- Baarslag, Hindriks, Jonker (2011). Acceptance Conditions in Automated Negotiation. [T] https://homepages.cwi.nl/~baarslag/pub/Acceptance_conditions_in_automated_negotiation.pdf — versión de revista (2014), Decision Support Systems 60: [R] https://research.tue.nl/en/publications/effective-acceptance-conditions-in-real-time-automated-negotiatio/
- Baarslag, Hindriks (2013). Accepting Optimally in Automated Negotiation with Incomplete Information. AAMAS. [T] https://homepages.cwi.nl/~baarslag/pub/Accepting_Optimally_in_Automated_Negotiation_with_Incomplete_Information.pdf
- Baarslag, Dirkzwager, Hindriks, Jonker (2014). The Significance of Bidding, Accepting and Opponent Modeling in Automated Negotiation. ECAI. [T] https://homepages.cwi.nl/~baarslag/pub/The_significance_of_bidding_accepting_and_opponent_modeling_in_automated_negotiation.pdf
- Baarslag, Hendrikx, Hindriks, Jonker (2012). Measuring the Performance of Online Opponent Models in Automated Bilateral Negotiation. [T] https://homepages.cwi.nl/~baarslag/pub/Measuring_the_performance_of_online_opponent_models_in_automated_bilateral_negotiation.pdf
- Baarslag et al. (2013). Evaluating practical negotiating agents: results and analysis of the 2011 international competition. Artificial Intelligence 198. [T] https://homepages.cwi.nl/~baarslag/pub/Evaluating_practical_negotiating_agents-results_and_analysis_of_the_2011_international_competition.pdf
- Baarslag, Aydoğan, Hindriks, Fujita, Ito, Jonker (2015). The Automated Negotiating Agents Competition, 2010-2015. AI Magazine 36(4). [T] https://homepages.cwi.nl/~baarslag/pub/The_Automated_Negotiating_Agents_Competition-2010-2015.pdf
- Jonker, Aydoğan, Baarslag, Fujita, Ito, Hindriks (2017). Automated Negotiating Agents Competition (ANAC). AAAI. [R, copia en texto] https://object.cloud.sdsc.edu/v1/AUTH_da4962d3368042ac8337e2dfdd3e7bf3/ml-papers-txt/AAAI/2017/automated_negotiating_agents_competition_anac__046ffb49.txt
- de Jonge (2022). An Analysis of the Linear Bilateral ANAC Domains Using the MiCRO Benchmark Strategy. IJCAI. [T] https://www.ijcai.org/proceedings/2022/0032.pdf
- Aydoğan, Baarslag, Florijn, Fujita, Jonker, Mohammad (2026). The Automated Negotiating Agents Competition (ANAC) 2025: Challenges and Results. IJCAI. [T] https://www.ijcai.org/proceedings/2026/0957.pdf
- Lista de ganadores ANAC 2010-2025 (documentación de NegMAS). [R] https://negmas.readthedocs.io/en/latest/anac.html

Varias cuestiones
- Leonardelli, Gu, McRuer, Medvec, Galinsky (2019). Multiple equivalent simultaneous offers (MESOs) reduce the negotiator dilemma. OBHDP 152. [R] https://ideas.repec.org/a/eee/jobhdp/v152y2019icp64-83.html
- Wikipedia, Multiple Equivalent Simultaneous Offers. [R] https://en.wikipedia.org/wiki/Multiple_Equivalent_Simultaneous_Offers

Regateo, plazos y última hora
- Rubinstein (1982). Perfect Equilibrium in a Bargaining Model. Econometrica 50(1). [R] https://www.econometricsociety.org/publications/econometrica/1982/01/01/perfect-equilibrium-bargaining-model — fórmulas también en https://en.wikipedia.org/wiki/Rubinstein_bargaining_model
- Gneezy, Haruvy, Roth (2003). Bargaining under a deadline: evidence from the reverse ultimatum game. Games and Economic Behavior 45. [T] https://stanford.edu/~alroth/papers/2005_GEB_Bargaining_Under.pdf
- Karagözoğlu, Kocher (2019). Bargaining under time pressure from deadlines. Experimental Economics 22. [T, leído en la copia PDF de Cambridge Core] https://doi.org/10.1007/s10683-018-9579-y
- Roth, Ockenfels (2002). Last-Minute Bidding and the Rules for Ending Second-Price Auctions. American Economic Review 92(4). [R] https://www.nber.org/papers/w7729

Ancla
- Galinsky, Mussweiler (2001). First offers as anchors: the role of perspective-taking and negotiator focus. JPSP 81(4). [R] https://pubmed.ncbi.nlm.nih.gov/11642352/
- Mason, Lee, Wiley, Ames (2013). Precise offers are potent anchors. JESP 49(4). [S] https://www.sciencedaily.com/releases/2013/06/130601133931.htm
- Loschelder, Trötschel, Swaab, Friese, Galinsky (2016). The information-anchoring model of first offers. Journal of Applied Psychology 101(7). [R] https://fis.leuphana.de/en/publications/the-information-anchoring-model-of-first-offers-when-moving-first/
- Schweinsberg, Ku, Wang, Pillutla (2012). Starting high and ending with nothing. JESP 48(1). [R] https://eprints.exchange.isb.edu/id/eprint/1559/

LLM
- Bianchi, Chia, Yuksekgonul, Tagliabue, Jurafsky, Zou (2024). How Well Can LLMs Negotiate? NegotiationArena Platform and Analysis. ICML. [R] https://arxiv.org/abs/2402.05863
- Xia et al. (2024). Measuring Bargaining Abilities of Language Models: A Benchmark and A Buyer-Enhancement Method. [R] https://arxiv.org/abs/2402.15813
- Shah, Agarwal, Garg, Heddaya (2025). LLM Rationalis? Measuring Bargaining Capabilities of AI Negotiators. [R] https://arxiv.org/abs/2512.13063
- Zhu, Sun, Nian, South, Pentland, Pei (2025). The Automated but Risky Game. [R] https://arxiv.org/abs/2506.00073
- Vaccaro, Caosun, Ju, Aral, Curhan (2025). Advancing AI Negotiations. [R] https://arxiv.org/abs/2503.06416
- Zhu et al. (2026). PieArena. [R, solo abstract; no usado en conclusiones] https://arxiv.org/abs/2602.05302
- Project Deal (Anthropic), contado por The Decoder. [S] https://the-decoder.com/anthropic-says-stronger-ai-models-cut-better-deals-and-the-losers-dont-even-notice/

---

## 8. No verificado

- **Faratin, Sierra, Jennings (2002), "Using similarity criteria to make issue trade-offs"**: texto no abierto; solo ficha bibliográfica (https://eprints.soton.ac.uk/256872).
- **Roth, Murnighan, Schoumaker (1988), "The deadline effect in bargaining"**: solo ficha (https://ideas.repec.org/a/aea/aecrev/v78y1988i4p806-23.html); su hallazgo va citado a través de Gneezy, Haruvy y Roth (2003).
- **Medvec y Galinsky (2005)** sobre MESO: no abierto.
- **Estrategias concretas de The Fawkes (2013), Agent M (2014), Atlas3 (2015), Caduceus (2016), PonPokoAgent (2017), AgreeableAgent2018 y AgentGG (2019)**: solo confirmé que figuran como ganadores o finalistas; no abrí ninguna descripción fiable de por qué ganaron. Además, las fuentes no coinciden sobre el ganador de 2018 (NegMAS lista MengWan; de Jonge trata a AgreeableAgent2018 como uno de los tres primeros).
- **Tasas exactas de ruptura con anclas extremas** (Schweinsberg et al.): solo el abstract, sin cifras.
- **Mason et al. (2013)**: solo nota de prensa; cifras del artículo sin comprobar.
- **Xia et al., Shah et al., Zhu et al., Vaccaro et al., Bianchi et al.**: páginas abiertas, pero las cifras las extrajo un resumen automático de la página; conviene comprobarlas antes de citarlas fuera del equipo.
- **Project Deal**: la página original de Anthropic dio error 404 en la dirección que tenía; solo fuente secundaria, y las fechas varían según el medio.
- **NegotiationToM** y relatos de hackathones de negociación 2025-2026: no encontré nada fiable.
- **Estrategia de espera estratégica** más allá de lo citado (Ma y Manove 1993; Admati y Perry 1987): no abiertos.
