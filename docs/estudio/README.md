# Guía de estudio — LedgerSense

Una guía en español para entender el proyecto a fondo y poder defenderlo en una
entrevista. El código, los comentarios y la documentación técnica están en
inglés (como en un entorno profesional real); esta guía explica el *porqué* de
cada decisión.

## Orden sugerido

1. [01 — Contabilidad de doble partida](01-contabilidad-doble-partida.md)
   Qué es un asiento, por qué debe cuadrar, y las cinco cuentas.
2. [02 — El libro mayor y la cadena de hash](02-libro-mayor-y-hash.md)
   Cómo se registra un asiento y por qué el historial es a prueba de manipulación.
3. [03 — El categorizador de IA](03-categorizador-ia.md)
   Cómo se clasifica un cargo en lenguaje libre y cómo se evalúa con rigor.
4. [04 — Detección de anomalías](04-deteccion-anomalias.md)
   Por qué usamos la mediana (z robusto) y no la media para detectar importes raros.
5. [05 — Preguntas de entrevista](05-preguntas-de-entrevista.md)
   Preguntas típicas y cómo responderlas con este proyecto.

## La idea en una frase

Un libro mayor de doble partida **determinista y auditable** (todo asiento cuadra,
el historial no se puede reescribir sin dejar rastro), con una capa de IA que
**solo sugiere** la cuenta de un cargo y **nunca** escribe en los libros sin
supervisión.
