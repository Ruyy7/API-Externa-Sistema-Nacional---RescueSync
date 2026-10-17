# I-3.5 — Liberación y cierre

> "Endpoint para reportar la finalización de las actividades de la ONG y el cierre del proyecto, permitiendo liberar los recursos bloqueados a nivel nacional." (enunciado, ítem 3, punto 5)

Es el último eslabón del proceso [E-7]: "las ONGs marcan sus actividades como finalizadas en la aplicación local. Una vez concluida su labor, la plataforma informa este estado al sistema centralizado a través de la API del Cloud, permitiendo marcar los proyectos como terminados y liberando formalmente los recursos de las ONGs". Se apoya en el modelo y el locking de `docs/04-bloqueo-y-compromiso.md`: el punto 4 termina cuando un compromiso queda `COMPROMETIDO`; desde ahí en adelante es de este punto.

## 1. Flujo

| Momento | Tarea del BPMN | Quién llama | Endpoint | Estado | Inventario de la ONG |
|---|---|---|---|---|---|
| La ONG marca una actividad como finalizada en la webapp | *Marcar actividad como finalizada* (lane ONGs) | Webapp | `POST /actividades` | `COMPROMETIDO` → `FINALIZADO` cuando no queda nada pendiente | Reutilizable: `comprometida -= n`. Consumible: `comprometida -= n` y `total -= n` |
| El coordinador sigue el despliegue; Bonita decide *Finalizaron todas las tareas?* | *Monitorear recursos* | Bonita, webapp, auditor | `GET /emergencias/{ref}/liberacion` | — | Sin cambios |
| Termina la ejecución (con o sin todas las actividades informadas) | *Liberar recursos* (lane Sistema) | Bonita o webapp | `POST /emergencias/{ref}/liberacion` | Todo lo `COMPROMETIDO` → `FINALIZADO` | Libera o consume lo que quedaba pendiente |
| Se cierra el proyecto | *Cerrar proyecto* | Bonita o webapp | `POST /emergencias/{ref}/cierre` | — | Sin cambios; exige que no quede nada comprometido |

- **Se libera a medida que termina cada actividad**, no al final: "yo lo iría liberando a medida que termina cada actividad de la ONG" (respuesta del docente). Así un paramédico que ya terminó puede ofrecerse en otra emergencia sin esperar al cierre.
- **Una actividad es una llamada**, no una entidad que haya que dar de alta antes: "es simplemente invocar un endpoint donde se dice 'para esta emergencia, para esta ONG, para esta categoría y estos recursos, se cumplió la tarea en tal fecha y con tales observaciones'" (respuesta del docente). Ese es, campo por campo, el cuerpo de `POST /actividades`.
- **Liberación y cierre son dos endpoints**, porque en el diagrama son dos tareas de servicio consecutivas, y porque el camino *Corroborar lotes* → "no" → *Relevar informe* → *Liberar recursos* muestra que el proceso contempla cerrar con recursos que la ONG nunca informó. La liberación los libera igual (con origen `CIERRE`); el cierre, en cambio, no libera nada: si queda algo comprometido responde 409 y obliga a liberar primero. Una llamada equivocada al cierre nunca mueve inventario.
- **El "proyecto" es la emergencia** (AMB-18 del análisis de la webapp). La emergencia vive en la webapp; acá se la conoce por `convocatoria.emergencia_referencia` (el id de la webapp, `emergenciaId` en Bonita) y el cierre es su único dato propio.

**Identificadores del contrato**, los mismos del resto de la API: la ONG por `ong_cuit`, la categoría por `tipo_recurso` (código del catálogo compartido con la webapp), la emergencia y la oferta por sus ids en la webapp, como texto.

## 2. Decisiones

| Tema | Decisión | Por qué |
|---|---|---|
| Cuánto se liberó de cada ítem | Columna `compromiso_item.cantidad_liberada`, con `CHECK (cantidad_liberada <= cantidad_comprometida)`, **y** la tabla `actividad` como historial. Lo pendiente es `comprometida - liberada`. | La columna da el CHECK en la base y lo pendiente sin sumar nada; la tabla da el historial que pidió el docente (fecha y observaciones) y alimenta el Dashboard [I-4] ("suministros movilizados en el mes" es la suma de las actividades `CONSUMIDO` por mes). |
| Reutilizable o consumible | Lo decide `tipo_recurso.reutilizable` en el momento de liberar, y lo que pasó queda en `actividad.accion` (`LIBERADO` o `CONSUMIDO`). | Si el catálogo cambia después, el historial no cambia. |
| Qué significa consumir | `consumir(n)` baja también `cantidad_total`, que desde I-3.1 es el tope que la ONG declaró para la categoría. | Entregar 500 raciones deja 500 raciones menos. La ONG vuelve a subir el tope con `PUT /ongs/yo/categorias` cuando repone. Lo disponible no cambia: esas raciones ya no estaban disponibles. |
| Cómo se ubica el ítem | Por emergencia, ONG y categoría. Si la ONG tiene más de un compromiso con esa categoría en la emergencia (una oferta propia y un consorcio), hace falta `oferta_referencia`; si no, 422 `COMPROMISO_AMBIGUO` con las ofertas candidatas. | Es lo que el docente describió, sin obligar a la webapp a conocer los ids internos de la API. |
| Reintentos | `actividad_referencia` (el id de la actividad en la webapp) es obligatoria y única: repetir el mismo pedido devuelve 200 con la actividad registrada; la misma referencia con otros datos es 409 `ACTIVIDAD_DUPLICADA`. | Después de un timeout, la webapp puede reintentar sin liberar dos veces. |
| Cierre con recursos sin informar | El cierre no libera: responde 409 `RECURSOS_SIN_LIBERAR` con el detalle. `POST .../liberacion` es el que libera lo que quede. | Separar los dos pasos del BPMN y evitar que un cierre por error mueva inventario. |
| Reservas al cerrar | Las reservas `RESERVADO` no se tocan; se informan en `reservas_vigentes`. | Las reservas son del punto 4 y vencen por fecha (`flask vencer-reservas`). |
| Después del cierre | Ninguna actividad ni liberación más para esa emergencia: 409 `PROYECTO_CERRADO`. | El proyecto terminó. |
| Fecha de cumplimiento | La informa el cliente (ISO-8601; sin zona se toma como UTC) y no puede ser futura, con 5 minutos de tolerancia de reloj. En la liberación y el cierre es opcional: si falta, es el momento de la llamada. | Es la fecha en que la ONG cumplió la tarea, no la del registro. |

## 3. Contrato

Todos los endpoints exigen `Authorization: Bearer <JWT>` de una cuenta de servicio (`docs/06-login-y-registro.md`).

### `POST /api/v1/actividades` — la ONG cumplió una actividad

```json
{
  "actividad_referencia": "ACT-88",
  "emergencia_referencia": "12",
  "ong_cuit": "30-11111111-1",
  "tipo_recurso": "PARAMEDICO",
  "cantidad": 3,
  "fecha": "2026-10-20T15:30:00-03:00",
  "observaciones": "Evacuación del barrio Norte terminada",
  "oferta_referencia": null
}
```

Responde `201` (o `200` si es un reintento) con la actividad y cómo queda el ítem:

```json
{
  "id": 41,
  "actividad_referencia": "ACT-88",
  "origen": "INFORMADA",
  "accion": "LIBERADO",
  "emergencia_referencia": "12",
  "oferta_referencia": "OF-15",
  "compromiso_id": 7,
  "estado_compromiso": "COMPROMETIDO",
  "ong": {"id": 1, "cuit": "30-11111111-1", "razon_social": "Rescatistas del Río"},
  "tipo_recurso": {"codigo": "PARAMEDICO", "nombre": "Paramédico"},
  "cantidad": "3.00",
  "fecha": "2026-10-20T18:30:00+00:00",
  "observaciones": "Evacuación del barrio Norte terminada",
  "registrada_por": "1",
  "creado_en": "2026-10-20T18:31:02+00:00",
  "item": {
    "tipo_recurso": {"codigo": "PARAMEDICO", "nombre": "Paramédico"},
    "cantidad_comprometida": "5.00",
    "cantidad_liberada": "3.00",
    "cantidad_pendiente": "2.00"
  }
}
```

`GET /api/v1/actividades` lista el historial paginado (filtros `emergencia`, `ong_cuit`, `tipo_recurso`, `origen` y `compromiso_id`) y `GET /api/v1/actividades/{id}` devuelve una.

### `GET /api/v1/emergencias/{referencia}/liberacion` — qué queda por liberar

```json
{
  "emergencia_referencia": "12",
  "todo_liberado": false,
  "cerrado": false,
  "cierre": null,
  "reservas_vigentes": 1,
  "compromisos": [
    {
      "id": 7,
      "oferta_referencia": "OF-15",
      "ong": {"id": 1, "cuit": "30-11111111-1", "razon_social": "Rescatistas del Río"},
      "estado": "COMPROMETIDO",
      "finalizado_en": null,
      "items": [
        {
          "tipo_recurso": {"codigo": "PARAMEDICO", "nombre": "Paramédico"},
          "cantidad_comprometida": "5.00",
          "cantidad_liberada": "3.00",
          "cantidad_pendiente": "2.00"
        }
      ]
    }
  ]
}
```

`todo_liberado` es lo que Bonita necesita para el gateway *Finalizaron todas las tareas?* (`tareasFin`).

### `POST /api/v1/emergencias/{referencia}/liberacion` — *Liberar recursos*

Cuerpo opcional: `{"fecha": "...", "observaciones": "..."}`. Responde `200` con el mismo estado de arriba más `liberaciones`: lo que liberó esta llamada, con `origen: "CIERRE"` y `actividad_referencia: null`. Si no quedaba nada pendiente, `liberaciones` es `[]` y nada cambia.

### `POST /api/v1/emergencias/{referencia}/cierre` — *Cerrar proyecto*

Mismo cuerpo opcional. Responde `201` con el cierre (`emergencia_referencia`, `fecha_cierre`, `observaciones`, `cerrado_por`, `creado_en`), o `200` con el cierre existente si se repite.

### Errores (formato uniforme `{codigo, mensaje, detalles}`)

| HTTP | `codigo` | Cuándo |
|---|---|---|
| 401 | `NO_AUTENTICADO` | Sin token, o con un token inválido o vencido |
| 403 | `PROHIBIDO` | El token no es de `SISTEMA_WEBAPP` ni `SISTEMA_BONITA` (el auditor solo consulta; un token de ONG no entra) |
| 404 | `NO_ENCONTRADO` | La ONG no tiene un compromiso con esa categoría en esa emergencia; o ninguna convocatoria nombra la emergencia; o la actividad no existe |
| 409 | `EXCEDE_PENDIENTE` | `cantidad` supera `comprometida - liberada`. `detalles` trae `pedida` y `pendiente` |
| 409 | `TRANSICION_INVALIDA` | El compromiso no está `COMPROMETIDO` (sigue `RESERVADO`, o ya está `FINALIZADO`). `detalles.compromisos` lista los candidatos con su estado |
| 409 | `ACTIVIDAD_DUPLICADA` | La misma `actividad_referencia` ya se usó con otros datos |
| 409 | `PROYECTO_CERRADO` | La emergencia ya tiene cierre |
| 409 | `RECURSOS_SIN_LIBERAR` | Se quiere cerrar y queda algo comprometido. `detalles.compromisos` dice cuáles y cuánto |
| 409 | `RECURSO_OCUPADO` | Se agotó la espera por un bloqueo (`LOCK_TIMEOUT_MS`); se puede reintentar |
| 422 | `VALIDACION` | Cuerpo mal formado, cantidad ≤ 0, decimales en una categoría que se cuenta en unidades, referencia con espacios |
| 422 | `FECHA_FUTURA` | La fecha está más allá de la tolerancia de reloj |
| 422 | `TIPO_RECURSO_DESCONOCIDO` | Código fuera del catálogo nacional (igual que en I-3.3) |
| 422 | `ONG_INEXISTENTE` | No hay una ONG con ese CUIT |
| 422 | `COMPROMISO_AMBIGUO` | Más de un compromiso posible; `detalles.ofertas` lista las referencias para reenviar con `oferta_referencia` |

## 4. Modelo

La migración `7c3f9a1d2b64` (sobre `2166cf571c44`, la de I-3.1) agrega:

- `compromiso_item.cantidad_liberada`, con `CHECK (cantidad_liberada >= 0)` y `CHECK (cantidad_liberada <= cantidad_comprometida)`. Con el CHECK de I-3.4 queda garantizado en la base que `0 ≤ liberada ≤ comprometida ≤ reservada`.
- `actividad`: `referencia` (UNIQUE; obligatoria si `origen = 'INFORMADA'`, nula si `origen = 'CIERRE'`), `compromiso_item_id` (FK **sin** cascade: un ítem con historial no se borra), `origen`, `accion`, `cantidad` (`CHECK > 0`), `fecha_cumplimiento`, `observaciones` y `registrada_por` (la identidad del token, como `creado_por` en `compromiso`). Es de solo inserción.
- `cierre_proyecto`: `emergencia_referencia` (UNIQUE), `fecha_cierre`, `observaciones` y `cerrado_por`.

Los contadores del inventario se cambian solo con los métodos de `InventarioRecurso`, con la fila bloqueada (tabla completa en `docs/04`, sección 4): este punto usa `liberar(n)` para lo reutilizable y `consumir(n)` para lo consumible. Nunca toca `cantidad_bloqueada` ni `cantidad_reservada`.

## 5. Consistencia e integridad

Cada escritura de este punto sigue el mismo esquema que las de I-3.4: una transacción, bloqueos en un orden fijo, validaciones sobre los valores ya bloqueados, cambios y commit. Si algo falla, el manejador global hace `rollback`: no queda nada a medias y se sueltan los bloqueos.

**Orden de bloqueo:** primero el compromiso (`SELECT ... FOR UPDATE`), después las filas de inventario en orden de id. Es el mismo orden de la confirmación, la cancelación y el vencimiento de I-3.4, y ninguna operación del sistema toma inventario y después espera un compromiso (la reserva y el `PUT /ongs/yo/categorias` de I-3.1 toman solo inventario), así que no hay ciclo posible. La liberación de la emergencia bloquea todos sus compromisos `COMPROMETIDO` en orden de id y después todas las filas de inventario involucradas, también en orden de id.

**Valores frescos:** las entidades del ítem y del inventario se cargan recién con el compromiso bloqueado (la búsqueda previa devuelve solo ids), así ningún valor viejo que estuviera en la sesión decide cuánto falta liberar.

**Invariantes y quién las sostiene:**

| Invariante | Dónde |
|---|---|
| `bloqueada + comprometida ≤ total`, todo ≥ 0 | CHECK de `inventario_recurso` (I-3.2 y I-3.4) |
| `0 ≤ liberada ≤ comprometida ≤ reservada` por ítem | CHECK de `compromiso_item` |
| Σ `actividad.cantidad` del ítem = `cantidad_liberada` | Se escriben en la misma transacción; test |
| `inventario.comprometida` = Σ (`comprometida - liberada`) de sus ítems `COMPROMETIDO` | Cada liberación descuenta los dos lados bajo el mismo bloqueo; test |
| `FINALIZADO` ⇔ todos los ítems con pendiente 0 | La transición ocurre solo en ese caso; CHECK `finalizado_con_fecha` |
| Hay cierre ⇒ nada `COMPROMETIDO` en la emergencia | El cierre bloquea y verifica antes de insertar; después, `PROYECTO_CERRADO` |

**Carreras que cubren los tests** (`tests/test_concurrencia_liberacion.py`):

| Carrera | Resultado |
|---|---|
| Dos actividades de 3 sobre 5 pendientes | Una 201; la otra, al tomar el bloqueo, relee el ítem con 3 liberados y responde 409 `EXCEDE_PENDIENTE`. La base lo frenaría igual con el CHECK |
| El mismo pedido dos veces en paralelo | El bloqueo del compromiso los serializa; el segundo encuentra la actividad y responde 200. El UNIQUE de la referencia es la red de seguridad |
| Una actividad (punto 5) y una reserva nueva (punto 4) sobre la misma fila | Compiten solo por la fila de inventario; las dos terminan y `bloqueada` y `comprometida` quedan coherentes |
| Un cierre mientras una actividad está en curso | El cierre bloquea también las reservas (`RESERVADO` y `COMPROMETIDO`), espera a la actividad y decide con el estado final: si lo dejó `FINALIZADO`, cierra |
| Espera agotada | 409 `RECURSO_OCUPADO`, sin liberar nada; el cliente reintenta y, por la idempotencia, es seguro |

**Límite conocido:** si el cierre entra primero y después alguien confirma una reserva de esa emergencia (`POST /compromisos/{id}/confirmacion`), quedaría un compromiso `COMPROMETIDO` en un proyecto cerrado. La solución completa es que la confirmación verifique el cierre con el compromiso bloqueado (`LiberacionRepository.cierre_de()` ya existe para eso); queda propuesta para I-3.4. Mientras tanto, la actividad y la liberación de ese compromiso responderían `PROYECTO_CERRADO`.

## 6. Seguridad

| Rol | Puede |
|---|---|
| `SISTEMA_WEBAPP` | Informar actividades, liberar la emergencia, cerrar el proyecto y consultar |
| `SISTEMA_BONITA` | Lo mismo: *Liberar recursos* y *Cerrar proyecto* son tareas de servicio del proceso [D-4] |
| `AUDITOR` | Consultar |
| `ONG` | Nada en este punto (403): la plataforma informa por la ONG [E-7] |

## 7. Pruebas

- `tests/test_modelo_liberacion.py`: el contrato del modelo (lo pendiente, el CHECK de la base, las unidades).
- `tests/test_liberaciones.py`: reutilizables y consumibles, finalización, adjudicación parcial, exceso, reintentos, estados, ambigüedad, validaciones, historial, estado de la emergencia, liberación, cierre y seguridad.
- `tests/test_concurrencia_liberacion.py`: las carreras de la sección 5, con pedidos realmente simultáneos.
- **Postman:** `docs/postman/RescueSync-I-3.5.postman_collection.json` recorre el flujo completo en 52 pedidos (login, adjudicación con los endpoints de I-3.4, actividades, reglas, liberación, cierre, historial y seguridad). `docs/postman/casos-de-prueba-i-3.5.md` explica cómo correrla y muestra cada pedido con su respuesta real. Apunta a la API publicada en Render y solo pide las contraseñas de las cuentas de servicio. Cada corrida registra su propia ONG de prueba y usa referencias únicas, así se puede repetir sobre la misma base. Se verificó con Newman el 17/10 en local: 231 verificaciones sin fallas. Contra Render se puede correr desde que esta rama se integra a `main` (el despliegue aplica la migración solo).

## 8. Integración

- **Webapp:** cuando el representante de la ONG marca una actividad como finalizada, el backend de la webapp llama a `POST /actividades` con el id de su actividad como `actividad_referencia`, el id de la emergencia, el CUIT de la ONG, el código del tipo de recurso del lote y la cantidad. Si la ONG participa en más de una oferta de la emergencia, agrega el id de la oferta. Un 409 `RECURSO_OCUPADO` se reintenta; un 200 es un reintento que ya había entrado.
- **Bonita:** *Monitorear recursos* consulta `GET /emergencias/{emergenciaId}/liberacion` y toma `todo_liberado` para `tareasFin` (conviene un timer antes de volver a consultar); *Liberar recursos* llama a `POST .../liberacion` y *Cerrar proyecto* a `POST .../cierre`, los dos con el token de la cuenta `bonita`. Las tres llamadas se pueden repetir sin efectos.
- **Dashboard [I-4]:** `GET /actividades?origen=INFORMADA` y los `accion = CONSUMIDO` dan los suministros movilizados por período; `cierre_proyecto`, los proyectos terminados.
