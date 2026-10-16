# I-3.4 — Control de concurrencia y bloqueo

> "Endpoints para validar restricciones y ejecutar el bloqueo/compromiso transaccional de recursos al ser adjudicados, implementando *locking* en PostgreSQL para prevenir *race conditions*." (enunciado, ítem 3, punto 4)

Se apoya en el modelo de `docs/02-reservas-y-compromisos.md`.

## 1. Flujo acordado por el equipo

| Momento | Quién llama | Endpoint | Estado | Inventario de la ONG |
|---|---|---|---|---|
| La ONG arma la oferta | Webapp | `POST /compromisos/verificacion` | — | Sin cambios: solo informa la disponibilidad |
| La ONG presenta la oferta | Webapp | `POST /compromisos` | `RESERVADO` | `bloqueada += n`. Si no alcanza: 409 y no se reserva nada |
| La ONG modifica la oferta | Webapp | `PUT /compromisos/{id}` | `RESERVADO` | Se ajusta por la diferencia |
| La ONG retira la oferta | Webapp | `POST /compromisos/{id}/cancelacion` | `CANCELADO` | `bloqueada -= n` |
| Se reabre la convocatoria | Webapp o Bonita | `PUT /convocatorias/{ref}` | `RESERVADO` | Sin cambios; el vencimiento pasa a las fechas nuevas |
| Se reformula la convocatoria | Webapp o Bonita | `POST /convocatorias/{ref}/reformulacion` | `RESERVADO` | Sin cambios; las reservas pasan a la convocatoria nueva |
| El municipio adjudica (*Comprometer recursos*) | Webapp o Bonita | `POST /compromisos/{id}/confirmacion` | `COMPROMETIDO` | Lo adjudicado pasa de bloqueado a comprometido; la diferencia se libera en ese momento |
| Termina la ventana de adjudicación sin adjudicar | Nadie: la API lo resuelve por fecha | — | `VENCIDO` | `bloqueada -= n` |
| La ONG termina sus actividades | Webapp o Bonita | Liberación (I-3.5) | `FINALIZADO` | Fuera de este punto |

- La reserva dura la ventana de ofertas **y** la ventana de adjudicación. Así, el municipio siempre adjudica sobre recursos que siguen bloqueados.
- La convocatoria se registra sola con la primera reserva que la nombra.
- El vencimiento se aplica de dos formas: cada reserva, ajuste o verificación vence primero las reservas atrasadas de los recursos que toca, y `flask vencer-reservas` barre el resto (se puede programar).
- La adjudicación es una tarea humana del municipio en la webapp (respuesta del profesor). Por eso la confirmación la puede enviar la webapp, que tiene los ids de los compromisos y las cantidades elegidas, o Bonita desde *Comprometer recursos* [D-4]. Es idempotente: repetir la misma adjudicación responde 200, y una distinta 409.

**Identificadores del contrato** (los mismos en todos los puntos de la API):

| Qué | Cómo viaja | Ejemplo |
|---|---|---|
| ONG | `ong_cuit`, el CUIT registrado en el Sistema Nacional (igual que en `POST /validaciones`). En la base, la FK sigue siendo `ong_id`. | `30-11111111-1` |
| Categoría (tipo de recurso) | `tipo_recurso`, el código del catálogo compartido con la webapp | `PARAMEDICO` |
| Oferta, convocatoria y emergencia | `oferta_referencia`, `convocatoria.referencia` y `convocatoria.emergencia_referencia`: los ids de la webapp, como texto | `"123"` |

La emergencia se guarda porque la liberación (I-3.5) informa las actividades "para esta emergencia, para esta ONG, para esta categoría" (respuesta del profesor), y `GET /compromisos?emergencia=...` permite encontrarlas.

## 2. Restricciones que se validan

| Restricción | Respuesta si no se cumple |
|---|---|
| La ONG existe en el Sistema Nacional | 422 `ONG_INEXISTENTE` |
| La ONG está `HABILITADA` | 422 `ONG_NO_HABILITADA` |
| El tipo de recurso existe en el catálogo y está activo, y no se repite en el pedido | 422 |
| La cantidad es entera si la unidad no admite decimales | 422 |
| La convocatoria sigue recibiendo ofertas (para reservar o ajustar) | 409 `VENTANA_CERRADA` |
| Hay disponibilidad: `total − bloqueada − comprometida ≥ pedido` | 409 `RECURSOS_INSUFICIENTES`, con el detalle por ítem |
| La transición de estado es válida | 409 `TRANSICION_INVALIDA` |
| La ventana de adjudicación no terminó (para confirmar) | 409 `RESERVA_VENCIDA` |
| La misma oferta y ONG no tiene otra reserva con datos distintos | 409 `COMPROMISO_EXISTENTE` |

La verificación no es binaria [E-4]: por ítem devuelve `DISPONIBLE`, `PARCIAL` o `SIN_DISPONIBILIDAD`, con la cantidad disponible.

## 3. Locking

**El problema.** La ONG X tiene 10 paramédicos libres y llegan dos reservas de 8 casi al mismo tiempo:

```text
Sin bloqueo   A lee 10 libres · B lee 10 libres · A reserva 8 · B reserva 8   → 16 de 10
Con bloqueo   A toma la fila (FOR UPDATE) · B espera · A reserva 8 y hace commit
              B toma la fila y relee: quedan 2                                 → 409
```

**Decisión: bloqueo pesimista con `SELECT ... FOR UPDATE`** (`app/repositories/bloqueos.py`).

- Cada operación que cambia el inventario corre en **una transacción**. Bloquea las filas involucradas, valida la disponibilidad con los valores ya bloqueados, aplica los cambios y hace commit. Si algo falla, el rollback no deja nada a medias y libera los bloqueos.
- **Orden fijo, para evitar deadlocks.** Una operación sobre un compromiso existente bloquea primero el compromiso y después el inventario, y las filas de inventario se bloquean siempre ordenadas por id. Un pedido de "paramédicos y rescatistas" y otro de "rescatistas y paramédicos" bloquean en el mismo orden, así que nunca se esperan en círculo.
- **Tope de espera.** `SET LOCAL lock_timeout` (`LOCK_TIMEOUT_MS`, 5 s por defecto). Si se agota, o si PostgreSQL detecta un deadlock, responde 409 `RECURSO_OCUPADO` y el cliente puede reintentar.
- **Transacciones cortas.** Nunca se hace una llamada HTTP con un bloqueo tomado.
- **Defensa en profundidad.** El CHECK `cantidad_bloqueada + cantidad_comprometida <= cantidad_total` frena en la base lo que el código dejara pasar. No alcanza solo: ante un *lost update* (dos transacciones que escriben valores calculados con datos viejos) el CHECK no ve nada raro. Por eso el bloqueo es imprescindible.
- **Idempotencia.** Una reserva es única por oferta y ONG (UNIQUE en la base). Si la webapp reintenta después de un timeout, recibe el compromiso existente (200) en lugar de reservar dos veces. La confirmación y la cancelación también se pueden repetir.
- **¿Por qué no un lock en Python?** En la nube corren varios procesos de la API. Lo único que comparten es la base.

**Alternativas descartadas:**

| Alternativa | Por qué no |
|---|---|
| `UPDATE ... SET bloqueada = bloqueada + n WHERE total - bloqueada - comprometida >= n` | Es atómico y válido, pero no permite responder el detalle de qué falta por ítem y es menos explícito para mostrar el *locking*. |
| Bloqueo optimista (columna de versión) | Obliga a reintentar justo cuando hay competencia por recursos escasos, que es el caso de una emergencia. |
| Aislamiento `SERIALIZABLE` | Es correcto, pero toda transacción en conflicto falla y hay que reintentarla. Es más difícil de explicar y de probar. |
| *Advisory locks* | No están atados a las filas: el código tiene que inventar las claves y acordarse de usarlas. |

## 4. Modelo

La migración `e4a7c2d9b815` agrega, sobre el modelo de `02-reservas-y-compromisos.md`:

- `convocatoria.emergencia_referencia`, con índice.
- `compromiso`:
  - `creado_por` (la identidad del token);
  - `confirmado_en`, `cancelado_en`, `vencido_en` y `finalizado_en`, con CHECK que exigen la fecha de cada estado;
  - un índice parcial sobre las reservas vigentes, para el vencimiento.
- `compromiso_item.ong_id`, con dos FK compuestas: la base garantiza que el inventario reservado sea de la misma ONG del compromiso.
- `compromiso_item`: CHECK `cantidad_comprometida <= cantidad_reservada`.

Los ítems quedan como historial: al cancelar o vencer no se ponen en cero, porque el estado vive en el compromiso.

Las transiciones válidas están en `Compromiso.TRANSICIONES` (patrón State, como en la webapp). `transicionar()` registra la fecha de la transición en la misma operación:

```text
RESERVADO → COMPROMETIDO | CANCELADO | VENCIDO
COMPROMETIDO → FINALIZADO (I-3.5)
```

**Lo que queda listo para la liberación (I-3.5).** Los contadores del inventario se cambian solo con los métodos de `InventarioRecurso`, con la fila bloqueada:

| Evento | Punto | Método | Efecto |
|---|---|---|---|
| Reservar o ajustar | 4 | `bloquear(n)` / `desbloquear(n)` | `bloqueada ± n` |
| Cancelar o vencer | 4 | `desbloquear(reservada)` | `bloqueada -= n` |
| Confirmar | 4 | `comprometer(reservada, adjudicada)` | `bloqueada -= reservada`, `comprometida += adjudicada` |
| Actividad cumplida con un reutilizable | 5 | `liberar(n)` | `comprometida -= n` |
| Actividad cumplida con un consumible | 5 | `consumir(n)` | `comprometida -= n` y `total -= n` |

Cuál de los dos últimos corresponde lo decide `tipo_recurso.reutilizable`. `tests/test_modelo_liberacion.py` fija este contrato.

## 5. Seguridad

Todos los endpoints de este punto exigen el token de una cuenta de servicio con el rol en el claim `rol` (`app/security.py`):

| Rol | Puede |
|---|---|
| `SISTEMA_WEBAPP` | Verificar, reservar, ajustar, cancelar, confirmar lo adjudicado y cambiar las fechas de una convocatoria |
| `SISTEMA_BONITA` | Verificar, confirmar lo adjudicado y cambiar las fechas de una convocatoria |
| `AUDITOR` | Consultar |

El login que emite los tokens es parte de I-3.1. Mientras tanto, `flask token-servicio <ROL>` emite uno para probar desde Swagger.

## 6. Pruebas

- `tests/test_compromisos.py`: restricciones, reserva, ajuste, cancelación, confirmación total y parcial, vencimiento e idempotencia.
- `tests/test_seguridad.py`: token faltante o inválido, rol incorrecto y Swagger.
- `tests/test_modelo_liberacion.py`: el contrato del modelo para I-3.5 (`liberar`, `consumir`, `finalizado_en` y su CHECK).
- `tests/test_concurrencia.py`:
  - dos reservas que compiten de verdad por la misma fila (una conexión aparte la retiene hasta que las dos están esperando el bloqueo);
  - seis reservas simultáneas;
  - reservas cruzadas sin deadlock;
  - tope de espera;
  - el CHECK de la base.

**Control negativo.** Con el mismo código, pero leyendo el inventario sin `FOR UPDATE`, los tests de concurrencia fallan: las dos reservas de 8 sobre 10 devuelven 201, y las seis de 3 se aceptan todas.
