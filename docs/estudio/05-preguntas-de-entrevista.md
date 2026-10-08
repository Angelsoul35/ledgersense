# 05 — Preguntas de entrevista

Preguntas típicas sobre este proyecto y cómo responderlas.

### "¿Por qué no usas un LLM para todo el libro mayor?"
Porque la contabilidad exige **determinismo y auditoría**: un asiento o cuadra o
no cuadra, y eso es una regla matemática, no una opinión. El núcleo es
determinista y la IA solo asiste (sugiere la cuenta de un cargo). Mezclar las dos
responsabilidades haría el sistema imposible de auditar.

### "¿Por qué enteros en céntimos y no `float` o `Decimal`?"
`float` no representa decimales exactos y acumula error (`0,1 + 0,2 ≠ 0,3`).
Enteros en céntimos dan sumas exactas. `Decimal` también serviría, pero los
enteros son más simples y rápidos para este alcance; lo documento como decisión
(ADR 0001) y señalo que importes sub-céntimo quedarían fuera.

### "Tu categorizador de IA, ¿no está sobreajustado?"
Lo mido justamente para saberlo: en vez de un split aleatorio (que sobre datos de
plantilla daría ~1,0 engañoso), evalúo con un **split disjunto por anclas** —
retiro vocabulario de comercio entero del entrenamiento— y promedio sobre varios
seeds. Así da **0,89 ± 0,04** con una brecha train-test acotada de **0,11**: si
el modelo hubiera memorizado las plantillas, esa brecha sería grande y la
exactitud disjunta se desplomaría. Reporto el promedio de varios seeds, no un
único split con suerte.

### "¿Qué pasa si el modelo clasifica mal un cargo?"
Nada grave: si la confianza es baja, no se contabiliza y va a revisión humana. Y
aunque contabilizara, pasa por `Ledger.post`, que rechaza cualquier asiento que
no cuadre. El modelo puede sugerir mal, pero no puede corromper los libros.

### "¿Cómo garantizas que el historial no se manipula?"
Con una **cadena de hash**: cada asiento guarda `SHA-256(prev_hash +
contenido)`. Editar un asiento antiguo rompe su hash y todos los siguientes;
`verify()` señala el primer asiento manipulado. Es evidencia de manipulación, no
una cadena de bloques.

### "¿Por qué z robusto y no la desviación estándar para anomalías?"
Porque el outlier infla la media y la desviación y se enmascara. La mediana y la
MAD son insensibles a outliers, así que el importe raro sobresale en vez de
esconderse.

### "¿Qué harías para llevar esto a producción?"
Persistencia (base de datos), usuarios autenticados, multidivisa, cierre de
periodos, y sobre todo **reentrenar el categorizador con transacciones reales
etiquetadas**, midiendo contra el score disjunto (el honesto), no el de dentro de
distribución.
