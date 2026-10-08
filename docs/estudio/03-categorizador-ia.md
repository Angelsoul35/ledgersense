# 03 — El categorizador de IA

## Qué hace

Recibe la descripción libre de un cargo ("monthly cloud hosting invoice") y
sugiere una **cuenta contable** (p. ej. `6100 Software Subscriptions`), con una
**confianza** y una **explicación** (las palabras que más pesaron). Es un
`FeatureUnion` de TF-IDF de palabras (1-2 gramas) y de caracteres (`char_wb`,
3-5) alimentando una regresión logística. Al ser lineal, cada sugerencia viene
con los términos que la motivaron: un contable puede ver *por qué* y corregir.

## La trampa del sobreajuste (y cómo la evitamos)

Si entrenas y evalúas con las mismas plantillas sintéticas, obtienes una
exactitud de ~1,0 que **no significa nada**: el modelo memorizó las frases, no
aprendió a categorizar. El síntoma es una exactitud dentro de distribución casi
perfecta que se desploma en cuanto evalúas descripciones cuyo vocabulario no
estaba en el entrenamiento, con una brecha train-test grande. Por eso no
confiamos en el número dentro de distribución: medimos con un split disjunto por
anclas, que es donde la memorización se nota.

### La corrección

Modelamos las descripciones como son de verdad en un extracto bancario: cada
cuenta tiene **palabras ancla recurrentes** ("rent", "payroll", "software
subscription") que comparten raíces parciales ("lease"/"rent",
"software"/"subscription"). La evaluación hace un **split disjunto por anclas**:
retira *anclas completas* del entrenamiento, de modo que el texto de prueba gira
en torno a vocabulario de comercio **nunca visto**. Es la pregunta difícil y
realista: ¿puede el modelo colocar un cargo del que no tiene la palabra exacta?

```
accuracy (media ± std, 6 seeds): 0,89 ± 0,04   # 9 cuentas; el azar es ~0,11
train accuracy                  : 1,00
train-test gap                  : 0,11          # acotada -> aprende la raíz, no la plantilla
```

### Lo que el número sí dice y lo que no dice

- **Sí** dice que generaliza a *frases nuevas* apoyándose en raíces compartidas:
  "studio lease" se clasifica como alquiler porque "lease"/"rent" se repiten en
  el entrenamiento.
- **No** dice que sea perfecto: un ancla sin ninguna raíz pariente en el
  entrenamiento (un vocabulario de comercio genuinamente nuevo) es donde cae ese
  ~11 % de error. Cerrar esa brecha necesita datos reales etiquetados, no más
  datos sintéticos.

El comando `python -m ledgersense.evaluation` **promedia varios seeds a
propósito**: un único split puede caer en un 0,95 con suerte, y reportar eso
sería el mismo autoengaño que el split aleatorio.

## La IA nunca escribe sola

Una sugerencia por debajo del umbral de confianza **no se contabiliza**: se
devuelve para revisión humana. Todo lo que entra en los libros pasa por
`Ledger.post`, que rechaza lo que no cuadra. Así, un modelo que se equivoque
puede *sugerir* mal, pero **nunca** puede producir un libro inválido.
