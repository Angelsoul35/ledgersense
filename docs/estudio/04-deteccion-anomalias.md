# 04 — Detección de anomalías

## El problema

Queremos marcar importes **raros** para su cuenta: un cargo de 9.400 € entre
facturas de software de ~60 €. Lo que buscamos es un valor atípico (outlier).

## Por qué NO usamos la media y la desviación estándar

La solución "obvia" —media y desviación estándar— tiene un fallo conocido: el
propio outlier que queremos detectar **infla** la media y la desviación, bajando
su propio z-score y escondiéndose. Es el efecto de **enmascaramiento**: un único
cargo enorme puede hacerse pasar por normal. Para detección de fraude, eso es
justo lo contrario de lo que queremos.

## El z-score robusto (mediana + MAD)

Usamos la **mediana** y la **desviación absoluta mediana** (MAD, *median absolute
deviation*):

```
z_robusto = 0,6745 · (x − mediana) / MAD
```

La mediana y la MAD son **insensibles** a unos pocos outliers, así que el importe
anómalo **sobresale** en lugar de esconderse. La constante 0,6745 escala la MAD
para que, con datos normales, el z robusto coincida con el z ordinario.

Detalles de diseño honestos:

- Cuentas con **menos de `min_samples`** movimientos se **saltan**: no hay
  suficiente historial para llamar anómalo a nada, y adivinar sería deshonesto.
- Cuentas cuyos importes son **todos idénticos** (MAD = 0) no producen anomalías.
- Cada hallazgo es **explicable**: dice el importe, la mediana típica de la
  cuenta y a cuántas desviaciones robustas está.

## Sus límites (dichos con claridad)

Es una comprobación **univariante** del importe, no detección de fraude. No
modela estacionalidad, proveedores ni patrones multivariable. Es un primer filtro
barato, determinista y auditable; un sistema de fraude real necesitaría un modelo
entrenado con historial etiquetado.
