# Orquestación por Bonita: qué llama el proceso en cada tarea

> **Estado (19/11/2026):** implementado en la rama `feature/orquestacion-bonita`, con 42 tests (`backend/tests/test_orquestacion.py`). Los conectores están configurados en el proceso de Bonita (`docs/rescue-sync_e5.bos` del repositorio de la webapp) y el proceso completo se probó de punta a punta con el motor de Bonita, la webapp y esta API, en los cuatro caminos: feliz, reabrir, reformular y continuar parcial. También con la API caída: la tarea de Bonita queda fallida y, al reintentarla, la llamada se repite sin efecto doble. Desde el 20/11, la API solo acepta esas operaciones con la cuenta `bonita` (sección 2) y las colecciones de Postman, incluida la nueva I-3.6, la usan (sección 7).

## 1. Por qué

La cátedra fijó para el coloquio este principio (pautas del 19/11):

> Los servicios de la API Cloud (validación de competencias, compromiso/bloqueo de recursos y liberación) son invocados **exclusivamente por Bonita** como motor orquestador. La aplicación web bajo ninguna circunstancia debe invocar de forma directa a la API en la nube.

Hasta ahora la webapp reservaba al presentar la oferta, comprometía al adjudicar, informaba las actividades y cerraba (docs 04 y 07). Con este cambio, cada uno de esos pasos lo invoca Bonita desde la tarea que le corresponde. Bonita le pide los datos a la webapp, los envía a la API y le devuelve el resultado a la webapp: el mismo patrón de la Directiva 3 del enunciado, repetido en cada paso.

## 2. Qué llama Bonita en cada tarea

Todas las llamadas se ubican por la emergencia, que es la variable `emergenciaId` del proceso, y usan el token de `POST /login` con la cuenta de servicio `bonita`.

| Tarea del proceso | Llamada | Qué hace | Cuerpo |
|---|---|---|---|
| *Validar ofertas* | `POST /emergencias/{emergenciaId}/bloqueo` | Valida por niveles de competencia y bloquea lo aceptado | El JSON que devuelve la webapp en `GET /sistema/emergencias/{id}/ofertas`, tal cual |
| *Reabrir convocatoria* y *Reformular lotes* | `POST /emergencias/{emergenciaId}/desbloqueo` | Libera los bloqueos que no se adjudicaron | Sin cuerpo, o `{}` (es lo que manda el conector) |
| *Comprometer recursos* | `POST /emergencias/{emergenciaId}/adjudicacion` | Compromete lo adjudicado y libera el resto | Lo que adjudicó el municipio, que Bonita le pide a la webapp |
| *Marcar actividad como finalizada* | `POST /emergencias/{emergenciaId}/actividades` | Registra las actividades cumplidas y libera sus recursos | Las actividades sin informar, que Bonita le pide a la webapp |
| *Liberar recursos* | `POST /emergencias/{emergenciaId}/liberacion` (ya existía, doc 07) | Libera lo que siga comprometido | `{}` |
| *Cerrar proyecto* | `POST /emergencias/{emergenciaId}/cierre` (ya existía, doc 07) | Registra el cierre | `{}` o `{"observaciones": "..."}` |

Todas las operaciones del proceso las acepta solo la cuenta `bonita` (`ORQUESTADOR` en `app/security.py`): con cualquier otra cuenta, incluida la de la webapp, responden `403 PROHIBIDO`. Vale también para las de a una oferta de I-3.3 a I-3.5 (`POST /validaciones`, `/compromisos`, su ajuste, cancelación y confirmación, las fechas y la reformulación de convocatorias, `POST /actividades`). La cuenta `webapp` conserva las consultas y el inventario de una ONG por CUIT, que es un ABM fuera del proceso. `tests/test_seguridad.py` lo verifica endpoint por endpoint, y falla si se agrega una escritura sin decidir si es del proceso.

## 3. Cambio de fondo: el bloqueo pasa de la presentación a la validación

| | Antes (doc 04) | Ahora |
|---|---|---|
| Cuándo se bloquea | Cuando la ONG presenta la oferta | Cuando vence la ventana y Bonita valida |
| Quién lo pide | La webapp | Bonita |
| Durante la ventana | Los recursos ya están reservados | No hay nada bloqueado: las ofertas viven solo en la webapp (Directiva 1) |
| Qué se bloquea | Lo ofrecido | Lo aceptado por la validación |

Motivos:

- **Directiva 4 del enunciado:** cuando Bonita invoca a la API con el JSON de ofertas, la API "aplicará los bloqueos necesarios (locking) para evitar sobre-asignaciones".
- **La sobre-asignación se resuelve sin rechazos:** si una ONG ofrece los mismos recursos en dos emergencias, la primera que se valida los bloquea, y la segunda recibe esa línea como `PARCIAL` o `NO_HABILITADO` con el motivo. Ninguna adjudicación falla después.
- **El compromiso no puede fallar por falta de recursos:** lo que se adjudica ya está bloqueado, así que el proceso no necesita un camino de error después de *Comprometer recursos*.

El ciclo de vida del compromiso (uno por oferta y ONG) queda así:

- `RESERVADO`: bloqueado por la validación.
- `COMPROMETIDO`: adjudicado.
- `CANCELADO`: el bloqueo se liberó, porque el coordinador reabrió o reformuló, o porque la oferta no se adjudicó.
- `VENCIDO`: terminó la ventana de adjudicación sin adjudicar.
- `FINALIZADO`: se liberó todo lo comprometido (doc 07).

Un compromiso `CANCELADO` o `VENCIDO` puede volver a `RESERVADO`. Pasa cuando una convocatoria reabierta se valida de nuevo y la misma oferta vuelve a aceptarse.

## 4. Contratos

### 4.1 `POST /emergencias/{ref}/bloqueo`

Pedido (lo arma la webapp; los campos que la API no usa se ignoran):

```json
{
  "convocatoria_referencia": "45",
  "emergencia_referencia": "12",
  "fecha_cierre": "2026-11-19T15:46:19+00:00",
  "fecha_limite_adjudicacion": "2026-11-26T15:46:19+00:00",
  "ofertas": [
    {
      "oferta_referencia": "123",
      "items": [
        {"lote_referencia": "7", "ong_cuit": "30-11111111-1", "tipo_recurso": "PARAMEDICO",
         "cantidad_requerida": "5.00", "cantidad_ofrecida": "3.00"}
      ]
    }
  ]
}
```

Respuesta `200`, con el mismo formato por línea que `POST /validaciones`:

```json
{
  "convocatoria_referencia": "45",
  "emergencia_referencia": "12",
  "reservas": 1,
  "ofertas": [
    {
      "oferta_referencia": "123",
      "nivel": "TOTAL",
      "items": [
        {"lote_referencia": "7", "ong_cuit": "30-11111111-1", "tipo_recurso": "PARAMEDICO",
         "cantidad_requerida": "5.00", "cantidad_ofrecida": "3.00",
         "cantidad_habilitada": "10.00", "cantidad_aceptada": "3.00",
         "nivel": "TOTAL", "motivo": null, "rol_sugerido": "APOYO"}
      ]
    }
  ]
}
```

- `ofertas` puede venir vacía: una convocatoria sin ofertas también pasa por *Validar ofertas*.
- Las ofertas se evalúan en orden: lo que acepta una ya no está disponible para la siguiente de la misma ONG. `POST /validaciones` sigue existiendo, no bloquea y evalúa cada oferta por separado.
- Repetirlo **reemplaza** los bloqueos de la convocatoria: lo que ya no se acepta se libera. Sirve para el reintento del conector y para validar de nuevo una convocatoria reabierta.
- Las fechas del pedido actualizan las de la convocatoria: los bloqueos vencen en `fecha_limite_adjudicacion`.
- Errores: `422 TIPO_RECURSO_DESCONOCIDO`, `409 CONVOCATORIA_ADJUDICADA`, `409 PROYECTO_CERRADO`, `409 RECURSO_OCUPADO` (reintentar).

### 4.2 `POST /emergencias/{ref}/desbloqueo`

Sin cuerpo. Respuesta `200`:

```json
{"emergencia_referencia": "12", "reservas_canceladas": 1}
```

No toca lo comprometido. Si no hay nada bloqueado, o la API todavía no conoce la emergencia, responde `200` con `0`: el conector nunca falla por eso.

### 4.3 `POST /emergencias/{ref}/adjudicacion`

```json
{
  "convocatoria_referencia": "45",
  "adjudicaciones": [
    {"oferta_referencia": "123", "ong_cuit": "30-11111111-1",
     "items": [{"tipo_recurso": "PARAMEDICO", "cantidad": 3}]}
  ]
}
```

Respuesta `200`: `emergencia_referencia`, `convocatoria_referencia`, `compromisos` (los que quedaron `COMPROMETIDO`) y `reservas_canceladas`.

- Todo o nada: si una adjudicación no es válida, no se compromete ninguna.
- Lo que no aparece, o aparece en 0, no se adjudica: su bloqueo se libera. Una lista vacía libera todos los bloqueos de la convocatoria.
- No se puede adjudicar más de lo bloqueado.
- Repetir la misma adjudicación no cambia nada.
- Errores: `404` (la emergencia no tiene esa convocatoria), `422 ADJUDICACION_INVALIDA` (con el detalle por oferta y ONG), `409 RESERVA_VENCIDA`, `409 PROYECTO_CERRADO`.

### 4.4 `POST /emergencias/{ref}/actividades`

```json
{
  "actividades": [
    {"actividad_referencia": "88", "ong_cuit": "30-11111111-1", "tipo_recurso": "PARAMEDICO",
     "cantidad": 2, "fecha": "2026-11-20T15:30:00-03:00", "observaciones": "Evacuación terminada"}
  ]
}
```

Respuesta `200`: `emergencia_referencia`, `nuevas` (cuántas registró esta llamada) y `actividades`.

- Cada actividad tiene las reglas de `POST /actividades` (doc 07) y es idempotente por `actividad_referencia`. Un reintento tiene que traer los mismos datos, incluida la `fecha`.
- La webapp puede mandar siempre todas las actividades que todavía no tiene confirmadas: las ya registradas no liberan dos veces.
- Una lista vacía no cambia nada.
- Si una actividad falla, las anteriores quedan registradas y el reintento sigue desde ahí.

## 5. Concurrencia

Las operaciones en lote usan el locking de I-3.4 (`repositories/bloqueos.py`):

1. Primero bloquean los compromisos de la convocatoria, en orden de id (`SELECT ... FOR UPDATE`).
2. Después bloquean, en una sola consulta y en orden de id, todas las filas de inventario que van a tocar.
3. Con las filas bloqueadas evalúan y modifican, y recién entonces confirman.

`test_dos_validaciones_simultaneas_no_sobreasignan` lo comprueba: dos emergencias validan a la vez ofertas por 8 paramédicos de una ONG que tiene 10. Una se queda con 8 y la otra con los 2 que quedan.

## 6. Pendiente

- **Render:** redesplegar esta rama. Los conectores de Bonita llaman a los endpoints nuevos, que la versión publicada todavía no tiene. El detalle de los conectores está en el repositorio de la webapp (`docs/11-guia-bonita-proceso-completo.md`).
- **Render:** al redesplegar, la cuenta `webapp` deja de poder invocar las operaciones del proceso. Las colecciones de Postman ya usan la cuenta `bonita` (sección 7).

## 7. Cómo probarlo con Postman

`docs/postman/RescueSync-I-3.6.postman_collection.json` hace, en orden, lo que hacen los conectores de Bonita: validar y bloquear, desbloquear al reabrir, comprometer, informar actividades, liberar y cerrar. Cierra con una carpeta de seguridad que muestra que la API rechaza a la cuenta `webapp` en cada operación y la deja consultar. Se corre entera con **Run collection**, poniendo las contraseñas de `bonita` y `webapp` en sus variables; la guía con cada caso y su respuesta real está en `docs/postman/casos-de-prueba-i-3.6.md`.

Las colecciones de I-3.1, I-3.4 e I-3.5 también pasaron a la cuenta `bonita`. Siguen probando los endpoints de a una oferta.

Verificado el 20/11/2026 contra la API local, ejecutando los scripts de cada colección: I-3.1 (21 pruebas), I-3.4 (185), I-3.5 (231) e I-3.6 (100), sin fallas.
