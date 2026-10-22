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

- **401 `NO_AUTENTICADO`:** sin token o con token inválido o vencido.
- **422 `VALIDACION`:** pedido mal formado, por ejemplo una cantidad menor o igual a 0 o un campo faltante.
- **422 `TIPO_RECURSO_DESCONOCIDO`:** código de tipo de recurso fuera del catálogo.

## Patrones

- **Service Layer:** `ValidacionService.validar` es el caso de uso. Arma los datos con 4 consultas fijas, sin importar el tamaño del pedido.
- **Repository:** `RecursoRepository` (`codigos_existentes`, `disponible_por_ong_y_tipo` y `reservado_por_ofertas`) y `ONGRepository.por_cuits`.
- **Función pura:** `evaluar_linea` clasifica una línea sin acceder a la base, así que se testea con una tabla de casos.
- **DTO/Schema:** los schemas de `schemas/validaciones.py` validan el pedido y generan el Swagger.
- **Dependency Injection:** el servicio recibe sus repositorios en `crear_servicios`.

## Dependencias con otros ítems

- **I-3.1 (login y registro):** el registro de una ONG crea sus filas de `inventario_recurso` (categoría y máximo); una ONG sin esa fila sale `NO_INSCRIPTA`. El token se pide en `POST /api/v1/login`.
- **I-3.4 (bloqueo):** reserva al presentar la oferta (`cantidad_bloqueada`) y compromete al adjudicar (`cantidad_comprometida`). Este endpoint descuenta las dos y suma de vuelta lo que reservó la misma oferta (`compromiso` en estado `RESERVADO` con su `oferta_referencia`).

## Cómo probarlo

- **API publicada:** https://rescuesync-sistema-nacional-41pb.onrender.com/api/v1 (Swagger en https://rescuesync-sistema-nacional-41pb.onrender.com/api/v1/docs). En el plan gratuito de Render, el primer pedido después de 15 minutos sin uso tarda cerca de un minuto.
- **Token:** `POST /api/v1/login` con la cuenta de servicio `webapp` (`{"usuario": "webapp", "password": "..."}`; la contraseña es la de `CUENTA_WEBAPP_PASSWORD`). El `access_token` se pega en **Authorize** del Swagger o como *Bearer Token* en Postman, y dura 8 horas.
- **En local:**

  ```bash
  docker compose up -d --build
  docker compose exec api flask seed
  docker compose exec api flask cuentas-servicio   # contraseñas de CUENTA_*_PASSWORD en .env
  ```

  La base es `http://localhost:5001/api/v1`. Para desarrollo, `docker compose exec api flask token-servicio SISTEMA_WEBAPP` emite un token sin pasar por el login.
- **Tests:** `docker compose run --rm api pytest tests/test_validaciones.py`.

## Casos de ejemplo

Usan las ONGs de demostración, que son las mismas en local y en Render (verificado el 22/10/2026 con `GET /api/v1/ongs/{id}/recursos`, que es público):

| ONG | CUIT | Estado | Disponible por categoría |
|---|---|---|---|
| Rescatistas del Río | `30-11111111-1` | HABILITADA | `PARAMEDICO` 10, `RESCATISTA` 15, `FRAZADA` 250 |
| Alimentos Solidarios | `30-22222222-2` | HABILITADA | `RACION_ALIMENTO` 4000, `AGUA_POTABLE` 2000, `ALIMENTO_SECO` 1000 |
| Ayuda en Registro | `30-33333333-3` | PENDIENTE | `PARAMEDICO` 100 |

Los resultados se obtuvieron ejecutando cada caso contra la API. Como el endpoint solo lee, se pueden repetir y dan lo mismo, mientras nadie reserve recursos de estas ONGs con I-3.4. Todos van a `POST /api/v1/validaciones` con el token de `webapp`, salvo el último.

### 1. Aceptación total como responsable principal

La ONG está inscripta en la categoría, le alcanza lo disponible y cubre todo el lote.

```json
{
  "convocatoria_referencia": "CONV-1",
  "ofertas": [
    {
      "oferta_referencia": "OF-1",
      "items": [
        {
          "lote_referencia": "LOTE-1",
          "ong_cuit": "30-11111111-1",
          "tipo_recurso": "PARAMEDICO",
          "cantidad_requerida": "5",
          "cantidad_ofrecida": "5"
        }
      ]
    }
  ]
}
```

**Esperado:** `200`, con el nivel de la oferta entre paréntesis:

| Oferta | Lote | ONG | Recurso | Habilitada | Aceptada | Nivel | Motivo | Rol |
|---|---|---|---|---|---|---|---|---|
| OF-1 (TOTAL) | LOTE-1 | `30-11111111-1` | `PARAMEDICO` | 10.00 | 5.00 | TOTAL | — | PRINCIPAL |

### 2. Aceptación parcial: la línea excede lo disponible

La ONG ofrece más de lo que tiene disponible. No se rechaza: se acepta lo que alcanza.

```json
{
  "convocatoria_referencia": "CONV-1",
  "ofertas": [
    {
      "oferta_referencia": "OF-2",
      "items": [
        {
          "lote_referencia": "LOTE-1",
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

**Esperado:** `200`, con el nivel de la oferta entre paréntesis:

| Oferta | Lote | ONG | Recurso | Habilitada | Aceptada | Nivel | Motivo | Rol |
|---|---|---|---|---|---|---|---|---|
| OF-2 (PARCIAL) | LOTE-1 | `30-11111111-1` | `PARAMEDICO` | 10.00 | 10.00 | PARCIAL | EXCEDE_DISPONIBLE | PRINCIPAL |

### 3. Apoyo secundario: cubre solo una parte del lote

La ONG tiene disponibilidad para todo lo que ofrece, pero eso no alcanza para el lote.

```json
{
  "convocatoria_referencia": "CONV-2",
  "ofertas": [
    {
      "oferta_referencia": "OF-3",
      "items": [
        {
          "lote_referencia": "LOTE-5",
          "ong_cuit": "30-22222222-2",
          "tipo_recurso": "RACION_ALIMENTO",
          "cantidad_requerida": "5000",
          "cantidad_ofrecida": "1500"
        }
      ]
    }
  ]
}
```

**Esperado:** `200`, con el nivel de la oferta entre paréntesis:

| Oferta | Lote | ONG | Recurso | Habilitada | Aceptada | Nivel | Motivo | Rol |
|---|---|---|---|---|---|---|---|---|
| OF-3 (TOTAL) | LOTE-5 | `30-22222222-2` | `RACION_ALIMENTO` | 4000.00 | 1500.00 | TOTAL | — | APOYO |

### 4. Varias líneas de la misma ONG y categoría comparten lo disponible

Una oferta usa la misma categoría en tres lotes. Las líneas se evalúan en orden y cada una descuenta lo que aceptaron las anteriores.

```json
{
  "convocatoria_referencia": "CONV-3",
  "ofertas": [
    {
      "oferta_referencia": "OF-4",
      "items": [
        {
          "lote_referencia": "LOTE-2",
          "ong_cuit": "30-11111111-1",
          "tipo_recurso": "RESCATISTA",
          "cantidad_requerida": "10",
          "cantidad_ofrecida": "10"
        },
        {
          "lote_referencia": "LOTE-3",
          "ong_cuit": "30-11111111-1",
          "tipo_recurso": "RESCATISTA",
          "cantidad_requerida": "10",
          "cantidad_ofrecida": "10"
        },
        {
          "lote_referencia": "LOTE-4",
          "ong_cuit": "30-11111111-1",
          "tipo_recurso": "RESCATISTA",
          "cantidad_requerida": "5",
          "cantidad_ofrecida": "5"
        }
      ]
    }
  ]
}
```

**Esperado:** `200`, con el nivel de la oferta entre paréntesis:

| Oferta | Lote | ONG | Recurso | Habilitada | Aceptada | Nivel | Motivo | Rol |
|---|---|---|---|---|---|---|---|---|
| OF-4 (PARCIAL) | LOTE-2 | `30-11111111-1` | `RESCATISTA` | 15.00 | 10.00 | TOTAL | — | PRINCIPAL |
| OF-4 (PARCIAL) | LOTE-3 | `30-11111111-1` | `RESCATISTA` | 5.00 | 5.00 | PARCIAL | EXCEDE_DISPONIBLE | APOYO |
| OF-4 (PARCIAL) | LOTE-4 | `30-11111111-1` | `RESCATISTA` | 0.00 | 0.00 | NO_HABILITADO | SIN_DISPONIBILIDAD | — |

### 5. Una categoría no inscripta no rechaza la oferta

La oferta incluye una categoría en la que la ONG no se inscribió al registrarse.

```json
{
  "convocatoria_referencia": "CONV-4",
  "ofertas": [
    {
      "oferta_referencia": "OF-5",
      "items": [
        {
          "lote_referencia": "LOTE-6",
          "ong_cuit": "30-11111111-1",
          "tipo_recurso": "FRAZADA",
          "cantidad_requerida": "100",
          "cantidad_ofrecida": "100"
        },
        {
          "lote_referencia": "LOTE-7",
          "ong_cuit": "30-11111111-1",
          "tipo_recurso": "BOMBERO",
          "cantidad_requerida": "4",
          "cantidad_ofrecida": "4"
        }
      ]
    }
  ]
}
```

**Esperado:** `200`, con el nivel de la oferta entre paréntesis:

| Oferta | Lote | ONG | Recurso | Habilitada | Aceptada | Nivel | Motivo | Rol |
|---|---|---|---|---|---|---|---|---|
| OF-5 (PARCIAL) | LOTE-6 | `30-11111111-1` | `FRAZADA` | 250.00 | 100.00 | TOTAL | — | PRINCIPAL |
| OF-5 (PARCIAL) | LOTE-7 | `30-11111111-1` | `BOMBERO` | 0.00 | 0.00 | NO_HABILITADO | NO_INSCRIPTA | — |

### 6. ONG no habilitada y ONG no registrada

Una línea de una ONG en estado PENDIENTE y otra de un CUIT que el Sistema Nacional no conoce.

```json
{
  "convocatoria_referencia": "CONV-5",
  "ofertas": [
    {
      "oferta_referencia": "OF-6",
      "items": [
        {
          "lote_referencia": "LOTE-8",
          "ong_cuit": "30-33333333-3",
          "tipo_recurso": "PARAMEDICO",
          "cantidad_requerida": "5",
          "cantidad_ofrecida": "5"
        },
        {
          "lote_referencia": "LOTE-9",
          "ong_cuit": "30-99999999-9",
          "tipo_recurso": "MEDICO",
          "cantidad_requerida": "2",
          "cantidad_ofrecida": "2"
        }
      ]
    }
  ]
}
```

**Esperado:** `200`, con el nivel de la oferta entre paréntesis:

| Oferta | Lote | ONG | Recurso | Habilitada | Aceptada | Nivel | Motivo | Rol |
|---|---|---|---|---|---|---|---|---|
| OF-6 (NO_HABILITADO) | LOTE-8 | `30-33333333-3` | `PARAMEDICO` | 0.00 | 0.00 | NO_HABILITADO | ONG_NO_HABILITADA | — |
| OF-6 (NO_HABILITADO) | LOTE-9 | `30-99999999-9` | `MEDICO` | 0.00 | 0.00 | NO_HABILITADO | ONG_NO_REGISTRADA | — |

### 7. Convocatoria con varias ofertas, una de ellas en consorcio

Así llama Bonita al cerrar la ventana: todas las ofertas de la convocatoria en un solo pedido. La segunda oferta es un consorcio de dos ONGs.

```json
{
  "convocatoria_referencia": "CONV-6",
  "ofertas": [
    {
      "oferta_referencia": "OF-10",
      "items": [
        {
          "lote_referencia": "LOTE-1",
          "ong_cuit": "30-11111111-1",
          "tipo_recurso": "PARAMEDICO",
          "cantidad_requerida": "10",
          "cantidad_ofrecida": "10"
        }
      ]
    },
    {
      "oferta_referencia": "OF-11",
      "items": [
        {
          "lote_referencia": "LOTE-1",
          "ong_cuit": "30-11111111-1",
          "tipo_recurso": "PARAMEDICO",
          "cantidad_requerida": "10",
          "cantidad_ofrecida": "6"
        },
        {
          "lote_referencia": "LOTE-2",
          "ong_cuit": "30-22222222-2",
          "tipo_recurso": "AGUA_POTABLE",
          "cantidad_requerida": "2000",
          "cantidad_ofrecida": "2500"
        }
      ]
    }
  ]
}
```

**Esperado:** `200`, con el nivel de la oferta entre paréntesis:

| Oferta | Lote | ONG | Recurso | Habilitada | Aceptada | Nivel | Motivo | Rol |
|---|---|---|---|---|---|---|---|---|
| OF-10 (TOTAL) | LOTE-1 | `30-11111111-1` | `PARAMEDICO` | 10.00 | 10.00 | TOTAL | — | PRINCIPAL |
| OF-11 (PARCIAL) | LOTE-1 | `30-11111111-1` | `PARAMEDICO` | 10.00 | 6.00 | TOTAL | — | APOYO |
| OF-11 (PARCIAL) | LOTE-2 | `30-22222222-2` | `AGUA_POTABLE` | 2000.00 | 2000.00 | PARCIAL | EXCEDE_DISPONIBLE | PRINCIPAL |

### 8. Error: tipo de recurso fuera del catálogo

Un código que no existe en el catálogo nacional indica un catálogo desalineado con la webapp: falla todo el pedido.

```json
{
  "convocatoria_referencia": "CONV-7",
  "ofertas": [
    {
      "oferta_referencia": "OF-12",
      "items": [
        {
          "lote_referencia": "LOTE-1",
          "ong_cuit": "30-11111111-1",
          "tipo_recurso": "DRON",
          "cantidad_requerida": "1",
          "cantidad_ofrecida": "1"
        }
      ]
    }
  ]
}
```

**Esperado:** `422`

```json
{
  "codigo": "TIPO_RECURSO_DESCONOCIDO",
  "detalles": {
    "tipos_recurso": [
      "DRON"
    ]
  },
  "mensaje": "Hay tipos de recurso que no existen en el catálogo nacional."
}
```

### 9. Error: pedido mal formado

Una cantidad que no es positiva y un campo obligatorio faltante.

```json
{
  "convocatoria_referencia": "CONV-8",
  "ofertas": [
    {
      "oferta_referencia": "OF-13",
      "items": [
        {
          "lote_referencia": "LOTE-1",
          "ong_cuit": "30-11111111-1",
          "tipo_recurso": "PARAMEDICO",
          "cantidad_ofrecida": "0"
        }
      ]
    }
  ]
}
```

**Esperado:** `422`

```json
{
  "codigo": "VALIDACION",
  "detalles": {
    "json": {
      "ofertas": {
        "0": {
          "items": {
            "0": {
              "cantidad_ofrecida": [
                "Must be greater than 0."
              ],
              "cantidad_requerida": [
                "Missing data for required field."
              ]
            }
          }
        }
      }
    }
  },
  "mensaje": "Hay campos con errores."
}
```

### 10. Error: pedido sin token

El servicio exige un JWT en el encabezado `Authorization`. Sin token.

```json
{
  "convocatoria_referencia": "CONV-1",
  "ofertas": [
    {
      "oferta_referencia": "OF-1",
      "items": [
        {
          "lote_referencia": "LOTE-1",
          "ong_cuit": "30-11111111-1",
          "tipo_recurso": "PARAMEDICO",
          "cantidad_requerida": "5",
          "cantidad_ofrecida": "5"
        }
      ]
    }
  ]
}
```

**Esperado:** `401`

```json
{
  "codigo": "NO_AUTENTICADO",
  "detalles": {},
  "mensaje": "Falta el token de acceso (Authorization: Bearer ...)."
}
```
