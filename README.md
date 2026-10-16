# RescueSync — API del Sistema Nacional (I-3.2)

Implementación del punto **Catálogo y Consulta** del Sistema Nacional de Gestión de Recursos y
Riesgos. Está construida siguiendo la misma arquitectura del backend de RescueSync E2.

## Alcance implementado

- ONGs y estado de habilitación.
- Catálogo de certificaciones y certificaciones por ONG.
- Catálogo de tipos de recurso con los mismos códigos que la webapp RescueSync.
- Inventario por ONG, distinguiendo recursos bloqueados de recursos ya comprometidos.
- Tipos de recurso con indicador `reutilizable` para distinguir lo que vuelve al stock de lo consumible.
- Disponibilidad global agregada por tipo de recurso.
- Bloqueo y compromiso de recursos (I-3.4): reserva al presentar la oferta, ajuste, cancelación,
  compromiso al adjudicar (también parcial) y vencimiento, con locking en PostgreSQL y endpoints
  protegidos con JWT.
- PostgreSQL + Alembic.
- Swagger/OpenAPI con flask-smorest.
- Seed idempotente.
- Tests con pytest.
- Docker Compose.

No implementa todavía login/onboarding, niveles de competencia ni la liberación (I-3.5), porque
corresponden a otros puntos de la Entrega 3.

## Levantar

```bash
cp .env.example .env
docker compose up --build
docker compose exec api flask seed
```

La API queda en `http://localhost:5001` y Swagger en:

```text
http://localhost:5001/api/v1/docs
```

## Endpoints principales

```text
GET /api/v1/ongs?habilitada=true
GET /api/v1/ongs/{id}
GET /api/v1/ongs/{id}/certificaciones
GET /api/v1/ongs/{id}/recursos
GET /api/v1/certificaciones
GET /api/v1/tipos-recursos
GET /api/v1/recursos/disponibilidad
POST /api/v1/validaciones          # I-3.3, requiere JWT
```

Filtros útiles de disponibilidad:

```text
GET /api/v1/recursos/disponibilidad?tipo_recurso_id=1
GET /api/v1/recursos/disponibilidad?ong_id=1
GET /api/v1/recursos/disponibilidad?solo_ongs_habilitadas=false
```

## Bloqueo y compromiso de recursos (I-3.4)

```text
POST /api/v1/compromisos/verificacion             valida restricciones sin reservar (webapp)
POST /api/v1/compromisos                          reserva al presentar la oferta (webapp)
PUT  /api/v1/compromisos/{id}                     ajusta la reserva al modificar la oferta (webapp)
POST /api/v1/compromisos/{id}/cancelacion         libera la reserva al retirar la oferta (webapp)
POST /api/v1/compromisos/{id}/confirmacion        compromete lo adjudicado (webapp o Bonita)
GET  /api/v1/compromisos y /api/v1/compromisos/{id}
GET  /api/v1/convocatorias/{referencia}
PUT  /api/v1/convocatorias/{referencia}           fechas nuevas al reabrir
POST /api/v1/convocatorias/{referencia}/reformulacion
```

Estos endpoints exigen un token con el rol de la cuenta de servicio (`SISTEMA_WEBAPP`,
`SISTEMA_BONITA` o `AUDITOR`). Hasta que exista el login (I-3.1), se puede emitir uno para probar
desde Swagger (botón *Authorize*):

```bash
docker compose exec api flask token-servicio SISTEMA_WEBAPP
```

Las reservas no adjudicadas vencen al terminar la ventana de adjudicación de su convocatoria. Cada
reserva vence las atrasadas de los recursos que toca, y este comando barre el resto:

```bash
docker compose exec api flask vencer-reservas
```

El flujo, las restricciones, el locking y las alternativas descartadas están en
`docs/04-bloqueo-y-compromiso.md`.

## Tests y calidad

```bash
docker compose run --rm api pytest
docker compose run --rm api ruff check .
docker compose run --rm api ruff format .
```

## Modelo de disponibilidad

La base diferencia una reserva provisional de una adjudicación efectiva:

```text
cantidad_total
cantidad_bloqueada       # reservada por ofertas todavía no adjudicadas
cantidad_comprometida    # adjudicada / en ejecución
cantidad_disponible = cantidad_total - cantidad_bloqueada - cantidad_comprometida
```

`TipoRecurso.reutilizable` indica qué recursos vuelven al stock al finalizar. Una carpa o una
persona son reutilizables; una ración, agua o medicamentos son consumibles.

`convocatoria`, `compromiso` y `compromiso_item` registran qué oferta reservó o comprometió cada
cantidad. Los cambios en el inventario se hacen con `SELECT ... FOR UPDATE` (ver I-3.4).

## Ejecución local del backend sin Docker

Docker Compose sigue siendo la forma recomendada. Si necesitás ejecutar Flask desde un entorno
virtual, la configuración puede derivar la URL de PostgreSQL a partir de `POSTGRES_*` y `DB_PORT`,
sin duplicar `DATABASE_URL` en `.env`:

```bash
cd backend
source .venv/Scripts/activate
flask --app app --env-file ../.env db upgrade
flask --app app --env-file ../.env run --debug --port 5001
```

En Docker, Compose continúa inyectando explícitamente `DATABASE_URL` con `db:5432`.

La validación por niveles de competencia (I-3.3), su contrato y cómo probarla con Postman están en
`docs/03-validacion-por-competencia.md`.

Ver `docs/01-catalogo-y-consulta.md` para las decisiones del punto I-3.2,
`docs/02-reservas-y-compromisos.md` para la preparación del modelo de I-3.4 y
`docs/04-bloqueo-y-compromiso.md` para su implementación.
