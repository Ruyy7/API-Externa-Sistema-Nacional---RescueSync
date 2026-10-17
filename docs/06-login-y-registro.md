# I-3.1 — Login y registro de ONGs

> "Inicio de sesión (/login) con JWT y servicio de registro/onboarding de ONGs." [Enunciado, ítem 3.1]

El plan y las opciones descartadas están en `docs/05-plan-login-registro-despliegue.md`.

## Decisiones

| Tema | Decisión | Por qué |
|---|---|---|
| Aprobación | La ONG se registra sola y queda `HABILITADA` en el acto. `PENDIENTE` deja de usarse; `SUSPENDIDA` queda para una baja administrativa. | Aclaración del docente: el alta es un registro directo, sin aprobación posterior. Así siguen funcionando sin cambios la validación (I-3.3) y las reservas (I-3.4), que exigen `HABILITADA`. |
| Categorías y topes | Cada categoría del registro es una fila de `inventario_recurso` (ONG × tipo de recurso) y el máximo es su `cantidad_total`. | Es la interpretación que el equipo ya acordó (correo del profesor del 08/10, `docs/03`). Una ONG recién registrada ya puede validar y reservar. |
| Quién inicia sesión | Las cuentas de servicio (webapp, Bonita y auditor) y las ONGs, que entran con su email. | El ítem es "Autenticación y **Gestión de Cuentas**", y sin cuenta la ONG no podría corregir sus topes. |
| Registro público | `POST /ongs` no pide token. | Lo pide el docente ("registro directo"), y la E3 se prueba con Postman. Lo frenan el CUIT con dígito verificador y la unicidad de CUIT y email. |
| Contraseñas | Solo se guarda el hash (`werkzeug.security`, sin dependencias nuevas). Nunca salen en respuestas ni en logs. Las de las cuentas de servicio vienen del entorno. | 12-factor: ningún secreto en el repo. |
| Credenciales inválidas | Mismo `401 CREDENCIALES_INVALIDAS` y mismo tiempo de respuesta si el usuario no existe, la contraseña está mal o la cuenta está inactiva. | No revela qué cuentas existen. |

## Contrato

### `POST /api/v1/login` (público)

```json
{"usuario": "contacto@brigada.org.ar", "password": "clave-segura-1"}
```

Respuesta `200`:

```json
{"access_token": "eyJ...", "token_type": "Bearer", "expira_en_segundos": 28800, "rol": "ONG"}
```

El token se manda como `Authorization: Bearer <token>`. Lleva el rol en el claim `rol` y, si es de una ONG, su CUIT en `ong_cuit`. Las cuentas de servicio entran con usuario `webapp`, `bonita` o `auditor`.

### `POST /api/v1/ongs` (público)

```json
{
  "razon_social": "Brigada Solidaria Sur",
  "cuit": "30-71234567-1",
  "email_contacto": "contacto@brigada.org.ar",
  "telefono": "221 555-0101",
  "password": "clave-segura-1",
  "categorias": [
    {"tipo_recurso": "PARAMEDICO", "cantidad_maxima": 10},
    {"tipo_recurso": "AGUA_POTABLE", "cantidad_maxima": 1500}
  ]
}
```

Responde `201` con la ONG (`estado: HABILITADA`) y sus `categorias`, cada una con `tipo_recurso` y las cantidades `total` (el máximo), `bloqueada`, `comprometida` y `disponible`. Todo se guarda en una transacción: si algo falla, no queda nada a medias.

### `GET /api/v1/ongs/yo` y `PUT /api/v1/ongs/yo/categorias` (token de ONG)

El `GET` devuelve la ONG del token con sus categorías. El `PUT` recibe `{"categorias": [...]}` con el mismo formato del registro y **reemplaza** las categorías: actualiza topes, suma categorías nuevas y quita las que no vienen. Bloquea el inventario de la ONG como I-3.4, así una reserva simultánea nunca queda con un tope menor al que reservó.

### Errores (formato uniforme `{codigo, mensaje, detalles}`)

| Código | HTTP | Cuándo |
|---|---|---|
| `CREDENCIALES_INVALIDAS` | 401 | Login con usuario o contraseña incorrectos, o con una cuenta inactiva. |
| `VALIDACION` | 422 | Campos con errores (`detalles.json`): CUIT con formato o dígito verificador incorrectos, contraseña de menos de 8 caracteres, email inválido, sin categorías, categoría repetida, o decimales en una categoría que se cuenta en unidades (personas, kits). |
| `TIPO_RECURSO_DESCONOCIDO` | 422 | Un `tipo_recurso` fuera del catálogo nacional (igual que en I-3.3). |
| `CUIT_DUPLICADO`, `USUARIO_DUPLICADO` | 409 | El CUIT o el email ya están registrados. |
| `CATEGORIA_EN_USO` | 409 | Un tope quedaría por debajo de lo reservado más lo comprometido, o se quiere quitar una categoría que ya se usó en reservas. `detalles.categorias` dice cuál y por qué. |
| `PROHIBIDO` | 403 | Un token de ONG en I-3.4, o un token de servicio en `/ongs/yo`. |

## Roles

| Endpoint | Sin token | ONG | Webapp | Bonita | Auditor |
|---|---|---|---|---|---|
| `POST /login`, `POST /ongs`, consultas de I-3.2 | ✓ | ✓ | ✓ | ✓ | ✓ |
| `GET /ongs/yo`, `PUT /ongs/yo/categorias` | 401 | ✓ | 403 | 403 | 403 |
| Compromisos y convocatorias (I-3.4) | 401 | 403 | según I-3.4 | según I-3.4 | según I-3.4 |
| `POST /validaciones` (I-3.3) | 401 | ✓ | ✓ | ✓ | ✓ |

`POST /validaciones` acepta cualquier token válido, incluido el de una ONG. No se cambió para no romper sus tests, que usan tokens sin rol. Como solo lee, no es un riesgo; queda como sugerencia restringirlo a las cuentas de servicio.

## Cuentas de servicio

`flask cuentas-servicio` crea o actualiza `webapp` (`SISTEMA_WEBAPP`), `bonita` (`SISTEMA_BONITA`) y `auditor` (`AUDITOR`) con las contraseñas de `CUENTA_WEBAPP_PASSWORD`, `CUENTA_BONITA_PASSWORD` y `CUENTA_AUDITOR_PASSWORD`. Una cuenta sin contraseña configurada no se toca. En Render corre en cada arranque. `flask token-servicio <ROL>` sigue disponible para desarrollo.

## Patrones

- **Service Layer:** `AuthService.login` y `OnboardingService` (`registrar`, `mi_ong` y `actualizar_categorias`).
- **Repository:** `CuentaRepository` y `CategoriaRepository`. Reutiliza `InventarioRepository` (catálogo y bloqueo de filas) e `iniciar_transaccion_con_bloqueos` de I-3.4.
- **DTO/Schema:** `schemas/cuentas.py` valida en el borde y genera el Swagger.
- **Decorator:** `@roles_required(RolSistema.ONG)`, el mismo de I-3.4.

## Cómo probarlo

- **Postman:** importar `docs/postman/RescueSync-I-3.1.postman_collection.json`, poner la URL en `base_url` y la contraseña de `webapp` en `password_webapp`, y correrla entera. Cada corrida usa un CUIT válido y un email nuevos, así se puede repetir sobre la misma base. Se verificó con Newman: 11 pedidos y 21 verificaciones sin fallas.
- **Swagger:** `/api/v1/docs`. Para los endpoints protegidos, pedir el token en `POST /login` y pegarlo en **Authorize**.
- **Tests:** `docker compose run --rm api pytest tests/test_registro_y_login.py`.
