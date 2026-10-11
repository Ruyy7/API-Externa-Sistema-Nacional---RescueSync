# I-3.2 — Catálogo y Consulta

Este repositorio implementa el punto 2 de los servicios mínimos del Sistema Nacional:

- consulta de ONGs habilitadas;
- consulta de certificaciones;
- disponibilidad global de recursos.

## Decisiones tomadas para este incremento

1. **Misma arquitectura que RescueSync E2:** Application Factory, Controller fino, Service Layer,
   Repository, SQLAlchemy, Marshmallow/flask-smorest, Alembic, errores uniformes, seed y pytest.
2. **Catálogo compartido:** los códigos de `TipoRecurso` y `UnidadMedida` del seed son los mismos de
   la webapp RescueSync. Esto permite que los sistemas se integren por código sin compartir base.
3. **Habilitación explícita:** `ONG.estado` puede ser `PENDIENTE`, `HABILITADA` o `SUSPENDIDA`.
   Este punto no decide qué regla cambia el estado; esa lógica pertenece al onboarding/habilitación.
4. **Reserva ≠ compromiso:** el inventario guarda `cantidad_total`, `cantidad_bloqueada` y
   `cantidad_comprometida`. La disponibilidad es `total - bloqueada - comprometida`. Una oferta
   presentada puede bloquear recursos sin tratarlos todavía como adjudicados.
5. **Reutilización explícita:** `TipoRecurso.reutilizable` distingue recursos que vuelven al stock
   al finalizar (personal, carpas, frazadas) de consumibles (raciones, agua, medicamentos). La
   categoría `MATERIAL` no alcanza para expresar esta regla.
6. **Base para I-3.4 sin adelantar sus endpoints:** se agregan `convocatoria`, `compromiso` y
   `compromiso_item`. La convocatoria conserva cierre y límite de adjudicación; el compromiso es
   único por oferta+ONG; cada ítem separa cantidad reservada y cantidad comprometida. Las
   operaciones, locking y transiciones se implementarán en el punto correspondiente.
7. **Disponibilidad global provisional:** `GET /recursos/disponibilidad` suma por tipo de recurso y,
   por defecto, considera únicamente ONGs `HABILITADA`. Si el docente define otra semántica, queda
   aislada en `RecursoRepository.disponibilidad_global` y `RecursoService`.

## Endpoints

- `GET /api/v1/ongs?habilitada=true`
- `GET /api/v1/ongs/{id}`
- `GET /api/v1/ongs/{id}/certificaciones`
- `GET /api/v1/ongs/{id}/recursos`
- `GET /api/v1/certificaciones`
- `GET /api/v1/tipos-recursos`
- `GET /api/v1/recursos/disponibilidad`

Todos los listados principales usan paginación de flask-smorest (`page`, `page_size`) y exponen
`X-Pagination`.


## Flujo preparado para la integración posterior

El modelo permite implementar, sin otro cambio estructural, el siguiente ciclo:

1. La oferta presentada reserva recursos (`cantidad_bloqueada`).
2. Modificar o retirar la oferta ajusta/libera esa reserva.
3. Al cerrar la ventana, la reserva puede mantenerse hasta `fecha_limite_adjudicacion`.
4. La adjudicación mueve la cantidad seleccionada de bloqueada a comprometida y libera la diferencia.
5. Al finalizar, los reutilizables vuelven a disponibilidad; los consumibles reducen el stock total.

La concurrencia seguirá resolviéndose en el servicio de I-3.4 con una transacción y
`SELECT ... FOR UPDATE` sobre `inventario_recurso`.
