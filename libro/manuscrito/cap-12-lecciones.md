# Capítulo 12 — Lecciones para quien afina modelos

> Borrador. Resume los capítulos 1–11; las cifras vienen de allí.

Empecé queriendo saber qué modelo pequeño aprende mejor ajedrez. Terminé aprendiendo algo
más útil: **casi siempre que medimos un modelo, medimos un sistema**. El modelo es una pieza;
alrededor hay un prompt, un parser, un respaldo, un filtro, una plantilla, un exportador.
Cualquiera de esas piezas puede ganar la partida por él.

Este capítulo destila lo aprendido en reglas que puedes aplicar a cualquier proyecto de
*fine-tuning*, juegue o no al ajedrez.

## 1. Mide al modelo, no al sistema

Pon siempre, junto a tu sistema completo, **la misma medición sin ayudas**. En este libro,
el modo `pure` frente al modo `arbiter`. La Copa del capítulo 11 lo dejó claro: con árbitro
contra sin árbitro, 9 a 0, fuera cual fuera el modelo.

## 2. Añade un jugador que no haga nada

El jugador más valioso del torneo fue el que no jugaba: **Qwen legacy + árbitro**, 1 jugada
propia de 193, empatado con los dos modelos entrenados. Un "modelo" que responde al azar
dentro de tu sistema es la línea base más honesta que existe. Si tu modelo no le gana, tu
modelo no aporta.

Y la anécdota que lo resume: en la ronda 7 ese mismo jugador ganó en **cinco jugadas**
(`1.h3 e5 2.g3 c5 3.c3 f5 4.f3 h5 5.g4 Qh4#`). Las cinco fueron respaldo. La última no la
eligió nadie: el árbitro, al ver un mate en una, ofrece solo esa jugada.

## 3. Los fallos son datos

Cuenta por separado lo que hace el modelo y lo que hace el sistema cuando el modelo falla.
Sin el contador de "respaldo" y "top-1 del motor" del capítulo 8, la ayuda era invisible.

## 4. El respaldo debe ser neutral

Si tu sistema tiene un *fallback*, que no sea mejor que el modelo. En ajedrez, el azar. En
un clasificador, la clase más frecuente. En un generador, un "no sé". Nunca la respuesta de
otro sistema más fuerte.

## 5. Parser estricto

Acepta solo el formato exacto con el que entrenaste. Un parser que "rescata" respuestas
convierte errores en aciertos y te hace creer que el modelo aprendió el formato.

## 6. Entrena y evalúa con el mismo prompt

Carácter por carácter. Y si cambias algo del prompt en la evaluación (como los candidatos
del árbitro), llámalo por su nombre y mídelo aparte.

## 7. Enmascara el prompt

Con prompts largos y respuestas cortas, la pérdida solo sobre la respuesta (`-100` en el
resto). Y entrena también el token de fin de turno.

## 8. Compara recetas iguales

Mismos datos, mismos hiperparámetros, mismas épocas. Si un modelo entrena 80 pasos y el
otro 625, no comparas modelos: comparas esfuerzos.

## 9. Una sola fuente de verdad para las rutas

El entrenador y el exportador deben leer la ruta del adaptador del mismo sitio. Imprime la
fecha y el log del adaptador que exportas.

## 10. Audita lo que no se te ocurrió auditar

El recorte silencioso a 45 jugadas del dataset (capítulo 3), el código muerto del árbitro
(capítulo 8), el traductor del navegador que congelaba el reloj (capítulo 10). Los errores
que importan suelen estar donde nadie mira.

## 11. Formato no es competencia

Gemma pura y Qwen V3 puro contestan en formato válido el 97,8 % de las veces y no saben
ganar: sus partidas entre ellos acaban en triple repetición. Mide por separado "sabe
contestar" y "sabe resolver".

## 12. Sospecha de tus conclusiones elegantes

*"Qwen demuestra mayor competencia nativa en el procesamiento de cadenas FEN densas"*. La
escribí yo. Si un resultado te sorprende y la explicación te halaga, es el momento de leer
el código otra vez.

## Lo que haría distinto

- **Más datos y menos atajos.** 5.000 posiciones bastan para aprender el formato, no para
  aprender a jugar. El siguiente paso serían decenas de miles, con la lista de jugadas
  completa y sin recortes.
- **Evaluar fuera del entrenamiento.** El sondeo usó posiciones del dataset. Un conjunto
  aparte, nunca visto, diría cuánto generalizan.
- **Muestras más grandes.** Una partida por emparejamiento sirve para ver tendencias
  gruesas, no diferencias finas. Con colores cambiados y muchas más partidas, las cifras
  tendrían intervalos de confianza.
- **Registrar todo desde el día uno**: cada adaptador con su `train_log`, cada exportación
  con la ruta y la fecha de su origen.

## Lo que te llevas de aquí

- Un modelo afinado vive dentro de un sistema. Mide los dos por separado.
- Las ayudas invisibles son el error más común y el más caro.
- Lo que no cuentas, no existe.

**Lo que viene:** en el capítulo 13, cómo publicar todo esto sin gastar un dólar más.
