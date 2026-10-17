# I-3.3 — Validación por niveles de competencia

> "Servicios que retornen objetos estructurados con capacidades habilitadas y niveles de riesgo
> permitidos (evitando rechazos punitivos binarios)." [Enunciado, ítem 3.3]

Después de que vence la ventana de ofertas, Bonita le pide a la webapp el JSON con las ofertas de
la convocatoria y se lo envía a este endpoint [Directivas 3 y 4]. Para cada línea, la API responde
cuánto se acepta, con qué nivel y qué rol puede cumplir en su lote. El municipio decide después
con esa información [E-5].

## Decisiones

| Tema | Decisión | Por qué |
|---|---|---|
| "Categoría" y "máximo" (correo del profesor, 08/10) | La categoría es una fila de `inventario_recurso` (ONG × tipo de recurso) y el máximo es su `cantidad_total`. Si la fila no existe, la ONG no está inscripta en esa categoría. | El modelo de I-3.2 ya lo representa. No se usa `CategoriaRecurso` (PERSONAL/MATERIAL), porque un máximo que sume litros y kits no tiene sentido. |
| Otros compromisos simultáneos | Disponible = `total − bloqueada − comprometida`, más lo que **esta misma oferta** ya tenga reservado (`compromiso` en estado RESERVADO). | Es la lectura literal del profesor: "que no tenga otras ofertas en el mismo tiempo". Sumar la reserva propia evita que una oferta compita contra sí misma al revalidarse. |
| Nivel por línea | Solo por cobertura: `TOTAL`, `PARCIAL` o `NO_HABILITADO`, con un `motivo`. | Es lo que describió el profesor. Las certificaciones y la gravedad quedan afuera: requerirían datos nuevos del registro (I-3.1). |
| Principal o apoyo [E-4] | `PRINCIPAL` si lo aceptado cubre `cantidad_requerida` del lote; `APOYO` si cubre una parte; `null` si no se acepta nada. | Responsable principal es quien puede cubrir el lote solo. |
| Persistencia | Ninguna: el endpoint calcula y responde, sin tablas nuevas. | La API no guarda ofertas [Directiva 1], y I-3.4 vuelve a validar bajo lock al adjudicar. |
| Bloqueo | No escribe en `inventario_recurso` ni en `compromiso`. | El bloqueo ocurre "al ser adjudicados" [ítem 3.4]. |

Detalles de menor peso:

- Un pedido por convocatoria con todas sus ofertas, así Bonita hace una sola llamada.
- La ONG se identifica por **CUIT** en cada línea. Es único en las dos bases, y en un consorcio cada ONG declara su parte.
- Las líneas de la misma ONG y la misma categoría **dentro de una oferta** comparten lo disponible.
- **Ofertas distintas** se evalúan por separado, porque son alternativas para el municipio. Si se adjudican dos que juntas no entran, el lock de I-3.4 frena la segunda.
- Un código de tipo de recurso desconocido devuelve **422** para todo el pedido, porque indica un catálogo desalineado con la webapp.
- Una ONG desconocida, no habilitada o no inscripta **no** es un error HTTP: esa línea queda en 0 y el resto de la oferta sigue en pie.
- El pedido ignora campos extra (*Tolerant Reader*): Bonita puede reenviar el JSON de la webapp tal cual.

## Contrato: `POST /api/v1/validaciones`

Requiere `Authorization: Bearer <JWT>`. Responde 200, porque no crea ningún recurso.

Pedido. Las cantidades pueden viajar como número o como texto y se redondean a 2 decimales.

```json
{
  "convocatoria_referencia": "CONV-7",
  "ofertas": [
    {
      "oferta_referencia": "OF-15",
      "items": [
        {
          "lote_referencia": "LOTE-3",
          "ong_cuit": "30-11111111-1",
          "tipo_recurso": "PARAMEDICO",
          "cantidad_requerida": "5",
          "cantidad_ofrecida": "14"
        }
      ]
    }
  ]
}
```

Respuesta. Con el seed, esa ONG tiene 12 paramédicos y 2 bloqueados, así que le quedan 10 disponibles.

```json
{
  "convocatoria_referencia": "CONV-7",
  "ofertas": [
    {
      "oferta_referencia": "OF-15",
      "nivel": "PARCIAL",
      "items": [
        {
          "lote_referencia": "LOTE-3",
          "ong_cuit": "30-11111111-1",
          "tipo_recurso": "PARAMEDICO",
          "cantidad_requerida": "5.00",
          "cantidad_ofrecida": "14.00",
          "cantidad_habilitada": "10.00",
          "cantidad_aceptada": "10.00",
          "nivel": "PARCIAL",
          "motivo": "EXCEDE_DISPONIBLE",
          "rol_sugerido": "PRINCIPAL"
        }
      ]
    }
  ]
}
```

| Campo | Significado |
|---|---|
| `cantidad_habilitada` | Lo que la ONG todavía puede aportar en esa categoría, al evaluar esa línea |
| `cantidad_aceptada` | `min(ofrecida, habilitada)` |
| `nivel` (línea) | `TOTAL` si se acepta todo; `PARCIAL` si se acepta una parte; `NO_HABILITADO` si se acepta 0 |
| `nivel` (oferta) | `TOTAL` si todas las líneas lo son; `NO_HABILITADO` si ninguna aporta; si no, `PARCIAL` |
| `motivo` | `EXCEDE_DISPONIBLE`, `SIN_DISPONIBILIDAD`, `NO_INSCRIPTA`, `ONG_NO_HABILITADA` u `ONG_NO_REGISTRADA`. Es `null` cuando el nivel es `TOTAL` |
| `rol_sugerido` | `PRINCIPAL`, `APOYO` o `null` |

Errores (formato uniforme `{codigo, mensaje, detalles}`):

- **401:** sin token o con token inválido.
- **422 `VALIDACION`:** pedido mal formado, por ejemplo una cantidad menor o igual a 0 o un campo faltante.
- **422 `TIPO_RECURSO_DESCONOCIDO`:** código de tipo de recurso fuera del catálogo.

## Patrones

- **Service Layer:** `ValidacionService.validar` es el caso de uso. Arma los datos con 4 consultas fijas, sin importar el tamaño del pedido.
- **Repository:** `RecursoRepository` (`codigos_existentes`, `disponible_por_ong_y_tipo` y `reservado_por_ofertas`) y `ONGRepository.por_cuits`.
- **Función pura:** `evaluar_linea` clasifica una línea sin acceder a la base, así que se testea con una tabla de casos.
- **DTO/Schema:** los schemas de `schemas/validaciones.py` validan el pedido y generan el Swagger.
- **Dependency Injection:** el servicio recibe sus repositorios en `crear_servicios`.

## Dependencias con otros ítems

- **I-3.1 (registro):** al registrar una ONG hay que crear sus filas de `inventario_recurso` (categoría y máximo); sin ellas, todas sus líneas salen `NO_INSCRIPTA`. Además, I-3.1 aporta `/login`. Hoy el 401 lo responde Flask-JWT-Extended como `{"msg": ...}`, así que conviene que I-3.1 registre los *loaders* de error de JWT para que use el formato uniforme.
- **I-3.4 (bloqueo):** este endpoint lee `cantidad_bloqueada`. Si I-3.4 decide reservar solo al adjudicar, `bloqueada` queda en 0 y el cálculo se reduce a `total − comprometida`, sin cambiar este código.

## Cómo probarlo (Swagger o Postman)

1. Levantar la API y cargar datos de demo:

   ```bash
   docker compose up -d --build
   docker compose exec api flask seed
   ```

2. Obtener un token. **Mientras no exista `/login` (I-3.1)**, se genera uno con la clave de `.env`:

   ```bash
   docker compose exec api python -c "from app import create_app; from flask_jwt_extended import create_access_token; app = create_app(); app.app_context().push(); print(create_access_token(identity='demo'))"
   ```

3. En Swagger (`http://localhost:5001/api/v1/docs`), pegar el token en **Authorize** y probar `POST /api/v1/validaciones`. En Postman, hacer un `POST http://localhost:5001/api/v1/validaciones` con *Auth → Bearer Token* y el JSON de arriba como *raw body*.

Casos útiles con el seed:

- CUIT `30-11111111-1`: `PARAMEDICO` (10 disponibles) y `RESCATISTA` (15). No está inscripta en `BOMBERO`.
- CUIT `30-33333333-3`: estado PENDIENTE, así que sale `ONG_NO_HABILITADA`.
- CUIT `30-99999999-9`: no existe, así que sale `ONG_NO_REGISTRADA`.
- Tipo de recurso `DRON`: devuelve 422 `TIPO_RECURSO_DESCONOCIDO`.
