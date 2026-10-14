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
- Modelo preparado para convocatoria, reserva, adjudicación parcial y liberación, sin exponer todavía
  endpoints del punto de bloqueo/compromiso.
- PostgreSQL + Alembic.
- Swagger/OpenAPI con flask-smorest.
- Seed idempotente.
- Tests con pytest.
- Docker Compose.

No implementa todavía login/onboarding, niveles de competencia ni las operaciones HTTP de
reserva/compromiso/liberación porque corresponden a otros puntos de la Entrega 3. El esquema base
para esas operaciones sí queda preparado para evitar una remodelación posterior.

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

Además se incorporan `convocatoria`, `compromiso` y `compromiso_item` como base del punto I-3.4.
Todavía no hay endpoints que las modifiquen: el locking con `SELECT ... FOR UPDATE` y las
transiciones reserva → compromiso → liberación se implementan en ese incremento.

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

Ver `docs/01-catalogo-y-consulta.md` para las decisiones del punto I-3.2 y
`docs/02-reservas-y-compromisos.md` para la preparación del modelo de I-3.4.
