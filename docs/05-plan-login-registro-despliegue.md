# I-3.1 y despliegue — Plan (login, registro de ONGs y Render)

> **Estado:** plan del 17/10/2026, para aprobar antes de escribir código.
> **Rama:** `feature/login-onboarding`, creada desde `feature/bloqueo-compromiso` (contiene I-3.2, I-3.3 e I-3.4).
> **Tareas del plan de la E3** (`06-plan-entrega-3.md` de la webapp): S4 login (4 h-p), S5 registro de ONGs (5 h-p) y S3 despliegue en Render (5 h-p).

## 1. Punto de partida

**Tests sobre `feature/bloqueo-compromiso`, sin cambios míos (17/10):** 63 pasan y **2 fallan**. Ruff marca 6 errores y 5 archivos sin formato. Nada de eso es de este punto, así que no lo toco; queda anotado para el equipo:

| Falla | Causa | Impacto |
|---|---|---|
| `test_recursos.py::test_tipo_recurso_indica_si_vuelve_al_stock` | El endpoint quedó en `/api/v1/tipos`, pero el README, el test y `01-catalogo-y-consulta.md` dicen `/api/v1/tipos-recursos`. | El Swagger publicado va a mostrar una ruta distinta a la documentada. |
| `test_app.py::test_openapi_publicado` | `API_TITLE` es "Sistema Nacional…", y el test espera "RescueSync - Sistema Nacional…". | Solo el título del Swagger. |
| Ruff: `F821` en `models/catalogos.py` y `models/organizaciones.py` | Anotaciones con comillas sin el import para *type checking*. | El CI fallaría. |

**Lo que ya existe y este punto reutiliza:**

- `security.py` (Bianca): roles en el claim `rol` (`SISTEMA_WEBAPP`, `SISTEMA_BONITA`, `AUDITOR`), el decorator `@roles_required`, `emitir_token` y los errores de JWT con el formato uniforme.
- `ONG` (Agustina): `razon_social`, `cuit` único, contacto y `estado` (`PENDIENTE`, `HABILITADA`, `SUSPENDIDA`).
- `InventarioRecurso` (Agustina): una fila por ONG y tipo de recurso, con `cantidad_total` y los `CHECK` de cantidades.
- **Interpretación ya acordada** (`03-validacion-por-competencia.md`, correo del profesor del 08/10): **la categoría es una fila de `inventario_recurso` y el máximo es su `cantidad_total`**. Una ONG sin esa fila sale `NO_INSCRIPTA` en la validación.

## 2. Qué pide el enunciado y qué aclaró el docente

- [I-3.1] "Inicio de sesión (/login) con JWT y servicio de registro/onboarding de ONGs".
- Aclaraciones del docente:
  - **la ONG se registra sola, con un registro directo, y nadie la aprueba después**;
  - **al registrarse se inscribe en categorías y declara el máximo de recursos de cada una**;
  - la habilitación depende de esas categorías y topes, no de un sello global.
- [C-E3] La entrega es la API **desplegada en la nube**, con Swagger, Dockerfile y URLs. Se entrega la documentación con un instructivo para Postman y el **link del Swagger publicado**.

## 3. Decisiones para el equipo

| # | Pregunta | Opciones | Recomendación |
|---|---|---|---|
| D1 | **¿Con qué estado queda la ONG al registrarse?** Hoy la validación (I-3.3) y las reservas (I-3.4) exigen `HABILITADA`. | a) Queda `HABILITADA` al registrarse. `PENDIENTE` deja de usarse y `SUSPENDIDA` queda para una baja administrativa futura. b) Eliminar `estado` y que la habilitación salga solo del inventario: obliga a cambiar I-3.2, I-3.3 e I-3.4. c) Dejarla `PENDIENTE` hasta que alguien la apruebe: contradice al docente. | **a).** Cumple con el docente (la habilitación concreta la dan las categorías y sus topes) sin tocar el código de I-3.3 ni I-3.4. Hay que avisarle a Agustina, porque su seed tiene una ONG `PENDIENTE` a propósito. |
| D2 | **¿Quién inicia sesión?** | a) Solo las cuentas de servicio (webapp, Bonita y auditor). b) Las cuentas de servicio **y** las ONGs: el registro crea la cuenta de la ONG, que después entra y consulta o actualiza sus categorías. | **b).** El ítem se llama "Autenticación y **Gestión de Cuentas**", y sin cuenta la ONG no puede corregir sus topes después de registrarse. El costo extra es poco: una tabla y un rol. |
| D3 | **¿El registro es público?** | a) Público: cualquiera llama `POST /ongs` sin token. b) Solo con el token de la webapp (la ONG se registra desde la webapp). | **a).** El docente pide un registro directo de la propia ONG, y la E3 se prueba con Postman. La validación del CUIT y su unicidad frenan los duplicados. |
| D4 | **¿Desde qué rama despliega Render?** | a) Desde `main`, después de mergear las ramas. b) Desde `feature/login-onboarding` mientras tanto, y pasarlo a `main` cuando se mergee. | **b) y después a).** Render redespliega solo con cada push a la rama elegida. Cambiarla es una opción del panel y no cambia la URL. |
| D5 | **¿Plan gratuito de Render?** | a) Gratuito. b) El plan pago más chico de la base de datos. | **a) para la E3**, con dos riesgos: el servicio se "duerme" sin uso (el primer pedido tarda cerca de un minuto) y **la base gratuita vence a los 30 días**, antes del coloquio del 26/11. Hay que recrearla para el coloquio o pasar la base a un plan pago. Que lo decida el equipo. |

## 4. Diseño (con las recomendaciones de la sección 3)

### 4.1 Modelo de datos

Una tabla nueva y ningún cambio en las tablas existentes:

**`cuenta`**

| Columna | Tipo | Restricciones | Notas |
|---|---|---|---|
| id | bigint | PK | |
| usuario | varchar(254) | NOT NULL, UNIQUE | El email de la ONG, o el nombre de la cuenta de servicio (`webapp`, `bonita`, `auditor`). |
| password_hash | varchar(255) | NOT NULL | Hash de `werkzeug.security`, que ya viene con Flask: sin dependencias nuevas. |
| rol | varchar(30) | NOT NULL, CHECK | `SISTEMA_WEBAPP`, `SISTEMA_BONITA`, `AUDITOR` u `ONG`. |
| ong_id | bigint | FK → ong, NULL | `CHECK ((rol = 'ONG') = (ong_id IS NOT NULL))`: solo las cuentas de ONG tienen ONG. |
| activa | boolean | NOT NULL DEFAULT true | |
| creado_en, actualizado_en | timestamptz | | Mismo mixin que el resto. |

Las categorías del registro **son filas de `inventario_recurso`**, con `cantidad_total` como tope y `cantidad_bloqueada` y `cantidad_comprometida` en 0. No hace falta otra tabla.

### 4.2 Contrato REST

| Método y ruta | Quién | Cuerpo | Respuesta |
|---|---|---|---|
| `POST /api/v1/login` | Público | `{"usuario", "password"}` | `200 {"access_token", "token_type": "Bearer", "expira_en_segundos", "rol"}`. Credenciales inválidas o cuenta inactiva: `401 CREDENCIALES_INVALIDAS`, con el mismo mensaje en los dos casos para no revelar qué cuentas existen. |
| `POST /api/v1/ongs` | Público | `{"razon_social", "cuit", "email_contacto", "telefono"?, "password", "categorias": [{"tipo_recurso": "PARAMEDICO", "cantidad_maxima": 12}]}` | `201` con la ONG (`HABILITADA`) y sus categorías. Errores: `409 CUIT_DUPLICADO`, `409 USUARIO_DUPLICADO`, `422 TIPO_RECURSO_DESCONOCIDO` (igual que en I-3.3) y `422 VALIDACION`. |
| `GET /api/v1/ongs/yo` | Rol `ONG` | — | La ONG del token, con sus categorías y lo disponible en cada una. |
| `PUT /api/v1/ongs/yo/categorias` | Rol `ONG` | `{"categorias": [...]}` | Reemplaza sus categorías y topes. No se puede bajar un tope por debajo de lo ya reservado más lo comprometido (`409 TOPE_MENOR_A_LO_COMPROMETIDO`, el mismo límite que el `CHECK` de la base), ni quitar una categoría con recursos reservados o comprometidos. |

Detalles que decido yo y quedan anotados:

- **CUIT:** formato `XX-XXXXXXXX-X` y dígito verificador, para que no entren CUITs inventados. Las ONGs del seed tienen CUITs ficticios que no lo cumplen, así que la verificación aplica solo al registro, no a la tabla.
- **Contraseña:** mínimo 8 caracteres, y nunca aparece en una respuesta ni en un log.
- **El token de una ONG** lleva `rol: ONG` y `ong_cuit`. El token de servicio sigue igual que hoy, así que lo que ya hicieron Bianca y Ruyy7 no cambia.
- **El token de una ONG no da acceso a I-3.3 ni a I-3.4** (`403`): las reservas y la validación las llaman sistemas, no ONGs.
- **`flask token-servicio`** sigue existiendo para desarrollo.
- **Cuentas de servicio:** `flask cuentas-servicio` crea o actualiza las tres (webapp, Bonita y auditor) con las contraseñas de las variables de entorno `CUENTA_WEBAPP_PASSWORD`, `CUENTA_BONITA_PASSWORD` y `CUENTA_AUDITOR_PASSWORD`. Ningún secreto queda en el repo.

### 4.3 Patrones

- **Service Layer:** `AuthService.login` y `OnboardingService.registrar`.
- **Repository:** `CuentaRepository`.
- **DTO/Schema:** los schemas de entrada y salida, que además generan el Swagger.
- **Decorator:** `@roles_required(RolSistema.ONG)`, que ya existe.

El registro crea la ONG, su cuenta y sus categorías en **una sola transacción**: si algo falla, no queda nada a medias.

### 4.4 Despliegue en Render

Lo que preparo en el repo:

1. **`gunicorn` en `requirements.txt`** (única dependencia nueva): el servidor de producción. Hoy el Dockerfile corre `flask run --debug`, que no sirve para producción.
2. **`render.yaml` (Blueprint):** un servicio web desde `backend/Dockerfile` y una base PostgreSQL. `JWT_SECRET_KEY` la genera Render; las contraseñas de las cuentas de servicio se cargan a mano en el panel. El comando de arranque está en el `render.yaml`, así el Dockerfile y el `docker compose` de desarrollo **no cambian**.
3. **Arranque en Render:** `flask db upgrade && flask seed --si-vacia && flask cuentas-servicio && gunicorn ...`. El plan gratuito no tiene consola ni comando previo al despliegue, así que migraciones, catálogo y cuentas tienen que correr al arrancar. `--si-vacia` evita que el seed de demo pise los datos reales en cada reinicio (el servicio gratuito se reinicia seguido).
4. **`config.py`:** Render entrega la URL de la base como `postgres://…`, y SQLAlchemy con psycopg 3 necesita `postgresql+psycopg://…`. Agrego esa conversión en `_database_url`.
5. **Verificación:** después de desplegar, pruebo el Swagger publicado, un `/login` y un registro.

**Lo que tenés que hacer vos** (yo no tengo acceso a tu cuenta de Render):

1. Entrar a https://render.com con la cuenta de GitHub del repo.
2. *New → Blueprint*, elegir el repo y la rama `feature/login-onboarding`. Render lee el `render.yaml` y crea el servicio y la base.
3. Cargar las tres contraseñas de las cuentas de servicio cuando lo pida.
4. Pasarme la URL que te da Render, así verifico el despliegue.

### 4.5 Cambios sobre código de tus compañeros (para aprobar)

| Archivo | Cambio | Riesgo |
|---|---|---|
| `controllers/ongs.py` (Agustina) | Suma `POST /ongs` y las rutas `/ongs/yo`. Los `GET` no cambian. | Bajo. |
| `security.py` (Bianca) | Suma `RolSistema.ONG` y el claim `ong_cuit`. Lo existente no cambia. | Bajo. |
| `cli.py` (Agustina) | Suma la opción `--si-vacia` a `seed` y el comando `cuentas-servicio`. `flask seed` sigue haciendo lo de hoy. | Bajo. |
| `config.py` (Agustina) | Conversión de la URL de Render. | Bajo: solo actúa si la URL empieza con `postgres://`. |
| `requirements.txt` | Suma `gunicorn`. | Bajo. |
| `conftest.py` | Suma `cuenta` al `TRUNCATE`. | Ninguno. |

## 5. Tests

- **Login:** credenciales correctas devuelven un token que sirve en un endpoint protegido. Usuario inexistente y contraseña incorrecta dan el mismo `401`. Una cuenta inactiva no entra.
- **Registro:** crea la ONG `HABILITADA`, su cuenta y sus categorías. CUIT duplicado, CUIT con dígito inválido, tipo de recurso desconocido y contraseña corta dan error. Si falla una categoría, no queda nada guardado.
- **Integración con I-3.3:** una ONG recién registrada con 10 paramédicos sale `TOTAL` al validar 10 y `NO_INSCRIPTA` en una categoría que no declaró.
- **Categorías:** no se puede bajar un tope por debajo de lo reservado ni quitar una categoría con reservas.
- **Roles:** el token de una ONG recibe `403` en compromisos y validaciones, y un token de servicio recibe `403` en `/ongs/yo`.
- **Config:** la URL `postgres://` se convierte a `postgresql+psycopg://`.

Los 63 tests que hoy pasan tienen que seguir pasando. Los 2 que ya fallaban siguen fallando hasta que sus autores los corrijan.

## 6. Entregables para la E3

- Swagger publicado en `https://<servicio>.onrender.com/api/v1/docs`.
- Colección de Postman de I-3.1 (`docs/postman/`), con variables para la URL y el token, siguiendo el formato de la de I-3.4.
- `docs/06-login-y-registro.md` con el contrato, las decisiones y cómo probarlo, y una sección "Despliegue" en el README.

## 7. Estimación

| # | Tarea | Plan E3 (h-p) | Est. (h-p) |
|---|---|---|---|
| A0 | Inventario y este plan | — | 1,5 |
| S4 | Login, cuentas y roles, con tests | 4 | 3,5 |
| S5 | Registro y categorías, con tests | 5 | 4,5 |
| S3 | Despliegue en Render: gunicorn, `render.yaml`, arranque, configuración y verificación | 5 | 3,5 |
| — | Postman y documentación | (en S11 y S13) | 1,5 |
| | **Total** | **14** | **14,5** |

Va en línea con el plan. El riesgo está en Render: es el primer despliegue del equipo, y en la E2 el setup llevó tres veces lo estimado.

## 8. Fuera de alcance

- La liberación (I-3.5): no está hecha y no es de este punto.
- Corregir las 2 fallas y el lint de la sección 1.
- Integrar la webapp con el registro (`ONG.id_sistema_nacional`).
- Mergear las ramas a `main`.
