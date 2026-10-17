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
- Login con JWT y registro directo de ONGs con sus categorías y topes (I-3.1).
- Despliegue en Render con `render.yaml`.

No implementa todavía la liberación (I-3.5).

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
POST /api/v1/login                 # I-3.1, devuelve el JWT
POST /api/v1/ongs                  # I-3.1, registro directo de una ONG
GET  /api/v1/ongs/yo               # I-3.1, token de ONG
PUT  /api/v1/ongs/yo/categorias    # I-3.1, token de ONG
```

## Login y registro de ONGs (I-3.1)

Las cuentas de servicio (`webapp`, `bonita` y `auditor`) se crean con las contraseñas del `.env`
(`CUENTA_*_PASSWORD`):

```bash
docker compose exec api flask cuentas-servicio
```

Después se pide el token con `POST /api/v1/login` (`{"usuario": "webapp", "password": "..."}`) y
se pega en **Authorize** del Swagger. Las ONGs se registran con `POST /api/v1/ongs` y entran con su
email. Contrato, decisiones y colección de Postman: `docs/06-login-y-registro.md`.

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
`SISTEMA_BONITA` o `AUDITOR`), que se pide en `POST /api/v1/login`. Para desarrollo también se
puede emitir uno directamente:

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

## Despliegue en Render

`render.yaml` describe el servicio web (desde `backend/Dockerfile`) y su base PostgreSQL, ambos en
el plan gratuito. En cada arranque, `backend/arranque-produccion.sh` aplica las migraciones, carga el
seed si la base está vacía, crea las cuentas de servicio y levanta gunicorn. El Dockerfile y el
`docker compose` de desarrollo no cambian.

**Crear el despliegue (una vez):**

1. En https://render.com, entrar con la cuenta de GitHub que tiene acceso al repo.
2. *New → Blueprint*, elegir este repositorio y la rama de `render.yaml`.
3. Completar `CUENTA_WEBAPP_PASSWORD`, `CUENTA_BONITA_PASSWORD` y `CUENTA_AUDITOR_PASSWORD`.
   `JWT_SECRET_KEY` la genera Render.
4. Cuando termina, el Swagger queda en `https://<servicio>.onrender.com/api/v1/docs`.

Cada push a esa rama redespliega solo. Para desplegar desde `main`, se cambia la rama en
*Settings* del servicio; la URL no cambia.

**Límites del plan gratuito:**

- El servicio se "duerme" después de 15 minutos sin pedidos y el primero tarda cerca de un minuto.
- **La base gratuita vence a los 30 días de creada** (y Render la borra 14 días después). Para el
  coloquio, unos días antes se borra la base vencida y se crea otra gratuita con el mismo nombre
  desde el panel; al redesplegar, el arranque vuelve a crear las tablas, el catálogo y las cuentas.
  Pagar la base solo hace falta si hay que conservar datos cargados.

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

El login y el registro de ONGs (I-3.1) están en `docs/06-login-y-registro.md`, y su plan con el
despliegue en `docs/05-plan-login-registro-despliegue.md`.

Ver `docs/01-catalogo-y-consulta.md` para las decisiones del punto I-3.2,
`docs/02-reservas-y-compromisos.md` para la preparación del modelo de I-3.4 y
`docs/04-bloqueo-y-compromiso.md` para su implementación.
