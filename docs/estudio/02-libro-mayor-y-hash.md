# 02 — El libro mayor y la cadena de hash

## Un diario que solo crece

El libro mayor (`ledger.py`) es un **diario de solo anexado** (append-only): los
asientos se añaden, nunca se borran ni se reordenan. `post()` hace dos cosas
antes de aceptar un asiento:

1. comprueba que **cuadra** (débitos = créditos y el total > 0), y
2. comprueba que **todas las cuentas existen** en el plan de cuentas.

Si algo falla, lanza una excepción y no registra nada. Es imposible meter un
asiento inválido.

## La cadena de hash: a prueba de manipulación

Cada asiento guarda un hash:

```
entry_hash = SHA-256( prev_hash + contenido_canónico_del_asiento )
```

donde `contenido_canónico` es una serialización JSON determinista de los campos
de negocio (secuencia, fecha, descripción, memo, líneas). El primer asiento
encadena desde un hash "génesis" fijo (64 ceros).

¿Por qué esto importa? Porque si alguien edita **a escondidas** un asiento
antiguo —por ejemplo, cambia un importe—, su `entry_hash` deja de coincidir con
el contenido, y el método `verify()` lo detecta y señala el **número de secuencia
del primer asiento manipulado**. Como cada asiento incluye el hash del anterior,
cambiar uno rompe toda la cadena a partir de ahí.

Es importante la distinción:

- Esto es **evidencia de manipulación** (tamper-evidence): no impide la edición,
  pero hace **imposible** una edición *no detectada*.
- No es una cadena de bloques: no hay consenso ni distribución. Para un libro con
  un único escritor, esta es la cantidad justa de mecanismo.

## Demostración en el demo

El `cli demo` registra actividad, verifica que la cadena está intacta, luego
**edita a propósito** un asiento histórico y vuelve a verificar: `verify()`
devuelve `False` y la secuencia rota. Al restaurar el asiento, vuelve a dar
`True`. Ver el fallo y la recuperación con tus propios ojos es la mejor prueba de
que el mecanismo funciona.
