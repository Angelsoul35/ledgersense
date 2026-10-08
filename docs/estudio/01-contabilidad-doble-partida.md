# 01 — Contabilidad de doble partida

## La regla de oro

En la contabilidad de doble partida, **cada transacción toca al menos dos
cuentas** y la suma de los **débitos** (debe) es igual a la suma de los
**créditos** (haber). No es una convención arbitraria: es una ecuación que se
mantiene siempre y que permite detectar errores. Si un asiento no cuadra, está
mal, y el sistema lo rechaza.

Ejemplo: la empresa paga 1.200 € de alquiler con dinero del banco.

| Cuenta            | Debe (débito) | Haber (crédito) |
| ----------------- | ------------- | --------------- |
| Gasto de alquiler | 1.200         |                 |
| Caja / Banco      |               | 1.200           |

El gasto **aumenta** (débito) y el efectivo **disminuye** (crédito). Los dos
lados suman 1.200: el asiento cuadra.

## Las cinco cuentas y su lado "natural"

Cada cuenta tiene un lado por el que crece:

| Tipo        | Crece por… | Ejemplo                      |
| ----------- | ---------- | ---------------------------- |
| Activo      | débito     | Caja, cuentas por cobrar     |
| Gasto       | débito     | Alquiler, nóminas            |
| Pasivo      | crédito    | Cuentas por pagar            |
| Patrimonio  | crédito    | Capital del propietario      |
| Ingreso     | crédito    | Ventas, servicios            |

En el código esto es una sola propiedad (`AccountType.is_debit_normal`): activos
y gastos son de "débito natural"; pasivos, patrimonio e ingresos son de "crédito
natural". Esa propiedad decide el signo del saldo de cada cuenta.

## Por qué los importes son enteros (céntimos)

Los ordenadores no representan `0,1 + 0,2` exactamente en coma flotante binaria
(da `0,30000000000000004`). Un libro mayor construido sobre `float` acumula error
y un balance que debería ser cero no lo es. Por eso **todos los importes son
`int` en céntimos**: la suma es exacta y un asiento cuadrado cuadra de verdad. El
formato con símbolo de moneda solo ocurre al mostrarlo, nunca en el cálculo.

## Balance de comprobación

Si todos los asientos cuadran, entonces la suma de todos los débitos es igual a
la suma de todos los créditos en todo el libro. Eso es el **balance de
comprobación** (`trial_balance`): la prueba global de que la contabilidad es
consistente. El resultado de la cuenta de resultados (ingresos − gastos) sale de
los saldos naturales de las cuentas de ingreso y gasto.
