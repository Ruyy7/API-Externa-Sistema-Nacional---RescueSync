# Casos de prueba de I-3.4 en Postman

Bloqueo y compromiso de recursos con locking en PostgreSQL. Todos los casos se generaron ejecutándolos contra la API: las respuestas de abajo son las reales. Lo que cambia en cada corrida se muestra así: las fechas como `<fecha y hora>`, los ids de la ONG y de los compromisos como `<id>`, los tokens como `<token>`, y el CUIT, el email y el sufijo de las referencias con el nombre de su variable (`{{ong_cuit}}`, `{{ong_email}}` y `{{corrida}}`).

Los recursos se bloquean en dos momentos:

| Momento | Endpoint | Inventario de la ONG |
|---|---|---|
| La ONG presenta la oferta | `POST /api/v1/compromisos` | `cantidad_bloqueada += n` |
| El municipio adjudica la oferta | `POST /api/v1/compromisos/{id}/confirmacion` | lo adjudicado pasa de bloqueado a comprometido; la diferencia se libera |

## Preparación

**1. Importar la colección en Postman.** *Import* (arriba a la izquierda) → elegir `docs/postman/RescueSync-I-3.4.postman_collection.json` → *Import*.

**2. Elegir contra qué API se prueba.** La variable `base_url` ya apunta a la API publicada en Render:

```text
https://rescuesync-sistema-nacional-41pb.onrender.com/api/v1
```

Para probar en local, cambiarla a `http://localhost:5001/api/v1` y levantar la API con las cuentas de servicio creadas (las contraseñas salen de `CUENTA_WEBAPP_PASSWORD`, `CUENTA_BONITA_PASSWORD` y `CUENTA_AUDITOR_PASSWORD` del `.env`):

```bash
docker compose up -d
docker compose exec api flask db upgrade
docker compose exec api flask seed
docker compose exec api flask cuentas-servicio
```

**3. Cargar las contraseñas de las cuentas de servicio.** Clic en la colección *RescueSync · Sistema Nacional · I-3.4…* → pestaña **Variables** → completar la columna *Current value* (o *Value*, según la versión) de `password_webapp`, `password_bonita` y `password_auditor` → guardar con **Ctrl+S**. Las contraseñas no están en el repositorio: en Render son las variables `CUENTA_*_PASSWORD` del servicio, y en local, las del `.env`.

| Cuenta | Rol del token | Puede |
|---|---|---|
| `webapp` | `SISTEMA_WEBAPP` | Verificar, reservar, ajustar, cancelar, adjudicar y cambiar fechas de convocatorias |
| `bonita` | `SISTEMA_BONITA` | Verificar, adjudicar y cambiar fechas de convocatorias |
| `auditor` | `AUDITOR` | Solo consultar |

**4. Ejecutar.**
- **Todos juntos:** clic derecho en la colección → **Run collection** → **Run**. El resumen muestra cuántas pruebas pasaron.
- **Uno por uno:** abrir cada pedido en orden, empezando por la carpeta 0, y apretar **Send**. Abajo, la pestaña **Test Results** muestra en verde cada valor esperado que se cumplió.

No hace falta pegar tokens ni tocar la pestaña *Authorization* de cada pedido: los logins de la carpeta 0 guardan los tokens en `token_webapp`, `token_bonita` y `token_auditor`, y cada pedido ya está configurado como *Bearer Token* con el que corresponde. Los ids de la ONG y de los compromisos también se guardan solos (`ong_id`, `compromiso_101`, `compromiso_202`…) y los pedidos siguientes los usan.

**Se puede repetir sin limpiar la base.** Cada corrida registra su propia ONG, *Rescatistas de Prueba (Postman I-3.4)*, con un CUIT válido y un email nuevos, y agrega a las referencias de ofertas, convocatorias y emergencias un sufijo propio (`{{corrida}}`, por ejemplo `OF-101-{{corrida}}`). Así las cuentas del inventario dan siempre lo mismo, sin importar qué haya en la base. Las fechas (`{{cierre_futuro}}`, `{{limite_futuro}}`, `{{cierre_pasado}}` y `{{limite_pasado}}`) se calculan solas antes de cada pedido, relativas al día en que se prueba.

**Inventario de partida** de la ONG de prueba, como bloqueada / comprometida / disponible:
- `PARAMEDICO`: 0 / 0 / 10
- `RESCATISTA`: 0 / 0 / 15
- `FRAZADA`: 0 / 0 / 250
- `RACION_ALIMENTO`: no está inscripta

Los casos 1.2 y 2.6 usan *Ayuda en Registro* (CUIT `30-33333333-3`), la ONG pendiente de habilitación que cargan los datos de demostración, porque el registro de I-3.1 deja a las ONGs habilitadas en el acto.

**Concurrencia.** No se puede probar con Postman, porque hacen falta pedidos realmente simultáneos. Se prueba con los tests automáticos: `docker compose run --rm api pytest tests/test_concurrencia.py -v` (5 pruebas, incluida una donde dos reservas compiten por la misma fila).


## 0. Preparación: login y ONG de prueba

### 0.1 Login de la cuenta webapp

- **Pedido:** `POST {{base_url}}/login`
- **Token (pestaña Authorization):** ninguno (*No Auth*)
- **Qué hace el endpoint:** Inicio de sesión (punto I-3.1). Devuelve un JWT con el rol de la cuenta en el claim `rol`. No pide token.
- **Qué prueba este caso:** Guarda el token en `token_webapp`. Si responde 401, falta la contraseña en la variable `password_webapp` o no es la correcta.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "usuario": "webapp",
  "password": "{{password_webapp}}"
}
```

**Respuesta esperada: `200 OK`**

```json
{
  "access_token": "<token>",
  "expira_en_segundos": 28800,
  "rol": "SISTEMA_WEBAPP",
  "token_type": "Bearer"
}
```

### 0.2 Login de la cuenta bonita

- **Pedido:** `POST {{base_url}}/login`
- **Token (pestaña Authorization):** ninguno (*No Auth*)
- **Qué hace el endpoint:** Inicio de sesión (punto I-3.1). Devuelve un JWT con el rol de la cuenta en el claim `rol`. No pide token.
- **Qué prueba este caso:** Guarda el token en `token_bonita`. Si responde 401, falta la contraseña en la variable `password_bonita` o no es la correcta.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "usuario": "bonita",
  "password": "{{password_bonita}}"
}
```

**Respuesta esperada: `200 OK`**

```json
{
  "access_token": "<token>",
  "expira_en_segundos": 28800,
  "rol": "SISTEMA_BONITA",
  "token_type": "Bearer"
}
```

### 0.3 Login de la cuenta auditor

- **Pedido:** `POST {{base_url}}/login`
- **Token (pestaña Authorization):** ninguno (*No Auth*)
- **Qué hace el endpoint:** Inicio de sesión (punto I-3.1). Devuelve un JWT con el rol de la cuenta en el claim `rol`. No pide token.
- **Qué prueba este caso:** Guarda el token en `token_auditor`. Si responde 401, falta la contraseña en la variable `password_auditor` o no es la correcta.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "usuario": "auditor",
  "password": "{{password_auditor}}"
}
```

**Respuesta esperada: `200 OK`**

```json
{
  "access_token": "<token>",
  "expira_en_segundos": 28800,
  "rol": "AUDITOR",
  "token_type": "Bearer"
}
```

### 0.4 Registrar la ONG de prueba de esta corrida

- **Pedido:** `POST {{base_url}}/ongs`
- **Token (pestaña Authorization):** ninguno (*No Auth*)
- **Qué hace el endpoint:** Registro directo de una ONG (punto I-3.1): queda `HABILITADA` en el acto y cada categoría es una fila de su inventario, con el máximo como total. No pide token.
- **Qué prueba este caso:** Cada corrida registra una ONG nueva, con un CUIT válido y un email que se generan solos (`ong_cuit` y `ong_email`), así las cuentas del inventario siempre dan lo mismo. Se inscribe en tres categorías: 10 paramédicos, 15 rescatistas y 250 frazadas. No se inscribe en RACION_ALIMENTO. Guarda el id en `ong_id`.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "razon_social": "Rescatistas de Prueba (Postman I-3.4)",
  "cuit": "{{ong_cuit}}",
  "email_contacto": "{{ong_email}}",
  "telefono": "221 555-0134",
  "password": "{{password_ong}}",
  "categorias": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad_maxima": 10
    },
    {
      "tipo_recurso": "RESCATISTA",
      "cantidad_maxima": 15
    },
    {
      "tipo_recurso": "FRAZADA",
      "cantidad_maxima": 250
    }
  ]
}
```

**Respuesta esperada: `201 CREATED`**

```json
{
  "actualizado_en": "<fecha y hora>",
  "categorias": [
    {
      "cantidad_bloqueada": "0.00",
      "cantidad_comprometida": "0.00",
      "cantidad_disponible": "10.00",
      "cantidad_total": "10.00",
      "tipo_recurso": {
        "categoria": "PERSONAL",
        "codigo": "PARAMEDICO",
        "id": 1,
        "nombre": "Paramédico",
        "reutilizable": true,
        "unidad_medida": {
          "admite_decimales": false,
          "codigo": "PERSONA",
          "id": 1,
          "nombre": "Personas"
        }
      }
    },
    {
      "cantidad_bloqueada": "0.00",
      "cantidad_comprometida": "0.00",
      "cantidad_disponible": "15.00",
      "cantidad_total": "15.00",
      "tipo_recurso": {
        "categoria": "PERSONAL",
        "codigo": "RESCATISTA",
        "id": 5,
        "nombre": "Rescatista",
        "reutilizable": true,
        "unidad_medida": {
          "admite_decimales": false,
          "codigo": "PERSONA",
          "id": 1,
          "nombre": "Personas"
        }
      }
    },
    {
      "cantidad_bloqueada": "0.00",
      "cantidad_comprometida": "0.00",
      "cantidad_disponible": "250.00",
      "cantidad_total": "250.00",
      "tipo_recurso": {
        "categoria": "MATERIAL",
        "codigo": "FRAZADA",
        "id": 12,
        "nombre": "Frazada",
        "reutilizable": true,
        "unidad_medida": {
          "admite_decimales": false,
          "codigo": "UNIDAD",
          "id": 6,
          "nombre": "Unidades"
        }
      }
    }
  ],
  "creado_en": "<fecha y hora>",
  "cuit": "{{ong_cuit}}",
  "email_contacto": "{{ong_email}}",
  "estado": "HABILITADA",
  "habilitada": true,
  "id": "<id>",
  "razon_social": "Rescatistas de Prueba (Postman I-3.4)",
  "telefono": "221 555-0134"
}
```

### 0.5 Inventario inicial de la ONG de prueba

- **Pedido:** `GET {{base_url}}/ongs/{{ong_id}}/recursos`
- **Token (pestaña Authorization):** ninguno (*No Auth*)
- **Qué hace el endpoint:** Inventario de una ONG por categoría (punto I-3.2): total, bloqueado, comprometido y disponible. Sirve para ver el efecto de cada operación. No pide token.
- **Qué prueba este caso:** Punto de partida: nada bloqueado ni comprometido.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cantidad_bloqueada": "0.00",
    "cantidad_comprometida": "0.00",
    "cantidad_disponible": "250.00",
    "cantidad_total": "250.00",
    "tipo_recurso": {
      "categoria": "MATERIAL",
      "codigo": "FRAZADA",
      "id": 12,
      "nombre": "Frazada",
      "reutilizable": true,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "UNIDAD",
        "id": 6,
        "nombre": "Unidades"
      }
    }
  },
  {
    "cantidad_bloqueada": "0.00",
    "cantidad_comprometida": "0.00",
    "cantidad_disponible": "10.00",
    "cantidad_total": "10.00",
    "tipo_recurso": {
      "categoria": "PERSONAL",
      "codigo": "PARAMEDICO",
      "id": 1,
      "nombre": "Paramédico",
      "reutilizable": true,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "PERSONA",
        "id": 1,
        "nombre": "Personas"
      }
    }
  },
  {
    "cantidad_bloqueada": "0.00",
    "cantidad_comprometida": "0.00",
    "cantidad_disponible": "15.00",
    "cantidad_total": "15.00",
    "tipo_recurso": {
      "categoria": "PERSONAL",
      "codigo": "RESCATISTA",
      "id": 5,
      "nombre": "Rescatista",
      "reutilizable": true,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "PERSONA",
        "id": 1,
        "nombre": "Personas"
      }
    }
  }
]
```


## 1. Validar restricciones sin bloquear

### 1.1 Verificar un pedido con resultados distintos por ítem

- **Pedido:** `POST {{base_url}}/compromisos/verificacion`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** Valida las restricciones de un pedido **sin bloquear nada**: ONG registrada y habilitada, categorías del catálogo, cantidades enteras cuando la unidad no admite decimales y disponibilidad por ítem (`DISPONIBLE`, `PARCIAL` o `SIN_DISPONIBILIDAD`).
- **Qué prueba este caso:** Respuesta no binaria: un ítem alcanza, otro alcanza en parte y otro no tiene disponibilidad. No bloquea nada.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "ong_cuit": "{{ong_cuit}}",
  "items": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 8
    },
    {
      "tipo_recurso": "RESCATISTA",
      "cantidad": 20
    },
    {
      "tipo_recurso": "RACION_ALIMENTO",
      "cantidad": 10
    }
  ]
}
```

**Respuesta esperada: `200 OK`**

```json
{
  "items": [
    {
      "disponible": "10.00",
      "resultado": "DISPONIBLE",
      "solicitado": "8.00",
      "tipo_recurso": "PARAMEDICO"
    },
    {
      "disponible": "15.00",
      "resultado": "PARCIAL",
      "solicitado": "20.00",
      "tipo_recurso": "RESCATISTA"
    },
    {
      "disponible": "0",
      "resultado": "SIN_DISPONIBILIDAD",
      "solicitado": "10.00",
      "tipo_recurso": "RACION_ALIMENTO"
    }
  ],
  "ong_cuit": "{{ong_cuit}}",
  "ong_habilitada": true,
  "se_puede_reservar": false
}
```

### 1.2 Verificar con una ONG pendiente de habilitación

- **Pedido:** `POST {{base_url}}/compromisos/verificacion`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** Valida las restricciones de un pedido **sin bloquear nada**: ONG registrada y habilitada, categorías del catálogo, cantidades enteras cuando la unidad no admite decimales y disponibilidad por ítem (`DISPONIBLE`, `PARCIAL` o `SIN_DISPONIBILIDAD`).
- **Qué prueba este caso:** Usa Ayuda en Registro (CUIT 30-33333333-3), que los datos de demostración cargan como pendiente. La verificación informa que la ONG no está habilitada (no es un error).

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "ong_cuit": "30-33333333-3",
  "items": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 1
    }
  ]
}
```

**Respuesta esperada: `200 OK`**

```json
{
  "items": [
    {
      "disponible": "100.00",
      "resultado": "DISPONIBLE",
      "solicitado": "1.00",
      "tipo_recurso": "PARAMEDICO"
    }
  ],
  "ong_cuit": "30-33333333-3",
  "ong_habilitada": false,
  "se_puede_reservar": false
}
```

### 1.3 Verificar con un CUIT que no está registrado

- **Pedido:** `POST {{base_url}}/compromisos/verificacion`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** Valida las restricciones de un pedido **sin bloquear nada**: ONG registrada y habilitada, categorías del catálogo, cantidades enteras cuando la unidad no admite decimales y disponibilidad por ítem (`DISPONIBLE`, `PARCIAL` o `SIN_DISPONIBILIDAD`).

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "ong_cuit": "30-99999999-9",
  "items": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 1
    }
  ]
}
```

**Respuesta esperada: `422 UNPROCESSABLE ENTITY`**

```json
{
  "codigo": "ONG_INEXISTENTE",
  "detalles": {
    "json": {
      "ong_cuit": [
        "No hay una ONG registrada con ese CUIT."
      ]
    }
  },
  "mensaje": "La ONG no está registrada en el Sistema Nacional."
}
```

### 1.4 Verificar una categoría que no existe en el catálogo

- **Pedido:** `POST {{base_url}}/compromisos/verificacion`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** Valida las restricciones de un pedido **sin bloquear nada**: ONG registrada y habilitada, categorías del catálogo, cantidades enteras cuando la unidad no admite decimales y disponibilidad por ítem (`DISPONIBLE`, `PARCIAL` o `SIN_DISPONIBILIDAD`).

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "ong_cuit": "{{ong_cuit}}",
  "items": [
    {
      "tipo_recurso": "DRON",
      "cantidad": 1
    }
  ]
}
```

**Respuesta esperada: `422 UNPROCESSABLE ENTITY`**

```json
{
  "codigo": "VALIDACION",
  "detalles": {
    "json": {
      "items": {
        "0": {
          "tipo_recurso": [
            "No existe en el catálogo."
          ]
        }
      }
    }
  },
  "mensaje": "Hay ítems con errores."
}
```

### 1.5 El inventario no cambió

- **Pedido:** `GET {{base_url}}/ongs/{{ong_id}}/recursos`
- **Token (pestaña Authorization):** ninguno (*No Auth*)
- **Qué hace el endpoint:** Inventario de una ONG por categoría (punto I-3.2): total, bloqueado, comprometido y disponible. Sirve para ver el efecto de cada operación. No pide token.
- **Qué prueba este caso:** La verificación no bloquea: el inventario sigue igual.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cantidad_bloqueada": "0.00",
    "cantidad_comprometida": "0.00",
    "cantidad_disponible": "250.00",
    "cantidad_total": "250.00",
    "tipo_recurso": {
      "categoria": "MATERIAL",
      "codigo": "FRAZADA",
      "id": 12,
      "nombre": "Frazada",
      "reutilizable": true,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "UNIDAD",
        "id": 6,
        "nombre": "Unidades"
      }
    }
  },
  {
    "cantidad_bloqueada": "0.00",
    "cantidad_comprometida": "0.00",
    "cantidad_disponible": "10.00",
    "cantidad_total": "10.00",
    "tipo_recurso": {
      "categoria": "PERSONAL",
      "codigo": "PARAMEDICO",
      "id": 1,
      "nombre": "Paramédico",
      "reutilizable": true,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "PERSONA",
        "id": 1,
        "nombre": "Personas"
      }
    }
  },
  {
    "cantidad_bloqueada": "0.00",
    "cantidad_comprometida": "0.00",
    "cantidad_disponible": "15.00",
    "cantidad_total": "15.00",
    "tipo_recurso": {
      "categoria": "PERSONAL",
      "codigo": "RESCATISTA",
      "id": 5,
      "nombre": "Rescatista",
      "reutilizable": true,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "PERSONA",
        "id": 1,
        "nombre": "Personas"
      }
    }
  }
]
```


## 2. Bloqueo al ofertar (reserva)

### 2.1 La ONG presenta la oferta 101: reservar 8 paramédicos y 4 rescatistas

- **Pedido:** `POST {{base_url}}/compromisos`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** **Bloqueo al ofertar.** La webapp lo llama cuando la ONG presenta la oferta. Bloquea las filas del inventario con `SELECT … FOR UPDATE`, valida la disponibilidad y la descuenta, todo en una transacción: si un ítem no alcanza, no se reserva nada. Es idempotente por oferta + ONG.
- **Qué prueba este caso:** Se bloquean los recursos. Guarda el id en `compromiso_101`.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "oferta_referencia": "OF-101-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "convocatoria": {
    "referencia": "CONV-1-{{corrida}}",
    "emergencia_referencia": "EMG-1-{{corrida}}",
    "fecha_cierre": "{{cierre_futuro}}",
    "fecha_limite_adjudicacion": "{{limite_futuro}}"
  },
  "items": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 8
    },
    {
      "tipo_recurso": "RESCATISTA",
      "cantidad": 4
    }
  ]
}
```

**Respuesta esperada: `201 CREATED`**

```json
{
  "cancelado_en": null,
  "confirmado_en": null,
  "convocatoria": {
    "emergencia_referencia": "EMG-1-{{corrida}}",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "CONV-1-{{corrida}}"
  },
  "creado_en": "<fecha y hora>",
  "creado_por": "1",
  "estado": "RESERVADO",
  "finalizado_en": null,
  "id": "<id>",
  "items": [
    {
      "cantidad_comprometida": "0.00",
      "cantidad_reservada": "8.00",
      "tipo_recurso": {
        "codigo": "PARAMEDICO",
        "nombre": "Paramédico"
      }
    },
    {
      "cantidad_comprometida": "0.00",
      "cantidad_reservada": "4.00",
      "tipo_recurso": {
        "codigo": "RESCATISTA",
        "nombre": "Rescatista"
      }
    }
  ],
  "oferta_referencia": "OF-101-{{corrida}}",
  "ong": {
    "cuit": "{{ong_cuit}}",
    "id": "<id>",
    "razon_social": "Rescatistas de Prueba (Postman I-3.4)"
  },
  "vencido_en": null
}
```

### 2.2 Inventario después de reservar

- **Pedido:** `GET {{base_url}}/ongs/{{ong_id}}/recursos`
- **Token (pestaña Authorization):** ninguno (*No Auth*)
- **Qué hace el endpoint:** Inventario de una ONG por categoría (punto I-3.2): total, bloqueado, comprometido y disponible. Sirve para ver el efecto de cada operación. No pide token.
- **Qué prueba este caso:** Los paramédicos bloqueados pasan de 0 a 8: quedan 2 disponibles.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cantidad_bloqueada": "0.00",
    "cantidad_comprometida": "0.00",
    "cantidad_disponible": "250.00",
    "cantidad_total": "250.00",
    "tipo_recurso": {
      "categoria": "MATERIAL",
      "codigo": "FRAZADA",
      "id": 12,
      "nombre": "Frazada",
      "reutilizable": true,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "UNIDAD",
        "id": 6,
        "nombre": "Unidades"
      }
    }
  },
  {
    "cantidad_bloqueada": "8.00",
    "cantidad_comprometida": "0.00",
    "cantidad_disponible": "2.00",
    "cantidad_total": "10.00",
    "tipo_recurso": {
      "categoria": "PERSONAL",
      "codigo": "PARAMEDICO",
      "id": 1,
      "nombre": "Paramédico",
      "reutilizable": true,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "PERSONA",
        "id": 1,
        "nombre": "Personas"
      }
    }
  },
  {
    "cantidad_bloqueada": "4.00",
    "cantidad_comprometida": "0.00",
    "cantidad_disponible": "11.00",
    "cantidad_total": "15.00",
    "tipo_recurso": {
      "categoria": "PERSONAL",
      "codigo": "RESCATISTA",
      "id": 5,
      "nombre": "Rescatista",
      "reutilizable": true,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "PERSONA",
        "id": 1,
        "nombre": "Personas"
      }
    }
  }
]
```

### 2.3 Reintento: la misma oferta con el mismo pedido

- **Pedido:** `POST {{base_url}}/compromisos`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** **Bloqueo al ofertar.** La webapp lo llama cuando la ONG presenta la oferta. Bloquea las filas del inventario con `SELECT … FOR UPDATE`, valida la disponibilidad y la descuenta, todo en una transacción: si un ítem no alcanza, no se reserva nada. Es idempotente por oferta + ONG.
- **Qué prueba este caso:** Idempotencia: responde 200 (no 201) con el mismo compromiso y no reserva dos veces.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "oferta_referencia": "OF-101-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "convocatoria": {
    "referencia": "CONV-1-{{corrida}}",
    "emergencia_referencia": "EMG-1-{{corrida}}",
    "fecha_cierre": "{{cierre_futuro}}",
    "fecha_limite_adjudicacion": "{{limite_futuro}}"
  },
  "items": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 8
    },
    {
      "tipo_recurso": "RESCATISTA",
      "cantidad": 4
    }
  ]
}
```

**Respuesta esperada: `200 OK`**

```json
{
  "cancelado_en": null,
  "confirmado_en": null,
  "convocatoria": {
    "emergencia_referencia": "EMG-1-{{corrida}}",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "CONV-1-{{corrida}}"
  },
  "creado_en": "<fecha y hora>",
  "creado_por": "1",
  "estado": "RESERVADO",
  "finalizado_en": null,
  "id": "<id>",
  "items": [
    {
      "cantidad_comprometida": "0.00",
      "cantidad_reservada": "8.00",
      "tipo_recurso": {
        "codigo": "PARAMEDICO",
        "nombre": "Paramédico"
      }
    },
    {
      "cantidad_comprometida": "0.00",
      "cantidad_reservada": "4.00",
      "tipo_recurso": {
        "codigo": "RESCATISTA",
        "nombre": "Rescatista"
      }
    }
  ],
  "oferta_referencia": "OF-101-{{corrida}}",
  "ong": {
    "cuit": "{{ong_cuit}}",
    "id": "<id>",
    "razon_social": "Rescatistas de Prueba (Postman I-3.4)"
  },
  "vencido_en": null
}
```

### 2.4 La misma oferta con otro pedido

- **Pedido:** `POST {{base_url}}/compromisos`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** **Bloqueo al ofertar.** La webapp lo llama cuando la ONG presenta la oferta. Bloquea las filas del inventario con `SELECT … FOR UPDATE`, valida la disponibilidad y la descuenta, todo en una transacción: si un ítem no alcanza, no se reserva nada. Es idempotente por oferta + ONG.
- **Qué prueba este caso:** Para cambiar una reserva se usa el PUT del paso 3.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "oferta_referencia": "OF-101-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "convocatoria": {
    "referencia": "CONV-1-{{corrida}}",
    "emergencia_referencia": "EMG-1-{{corrida}}",
    "fecha_cierre": "{{cierre_futuro}}",
    "fecha_limite_adjudicacion": "{{limite_futuro}}"
  },
  "items": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 9
    }
  ]
}
```

**Respuesta esperada: `409 CONFLICT`**

```json
{
  "codigo": "COMPROMISO_EXISTENTE",
  "detalles": {
    "compromiso_id": 1,
    "estado": "RESERVADO"
  },
  "mensaje": "Ya existe un compromiso para esta oferta y ONG con otros datos. Para cambiar la reserva, usá PUT /compromisos/{id}."
}
```

### 2.5 La misma ONG ofrece los mismos paramédicos en otra emergencia

- **Pedido:** `POST {{base_url}}/compromisos`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** **Bloqueo al ofertar.** La webapp lo llama cuando la ONG presenta la oferta. Bloquea las filas del inventario con `SELECT … FOR UPDATE`, valida la disponibilidad y la descuenta, todo en una transacción: si un ítem no alcanza, no se reserva nada. Es idempotente por oferta + ONG.
- **Qué prueba este caso:** El caso central del punto 4: quedan 2 paramédicos libres y se piden 5. No se reserva nada.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "oferta_referencia": "OF-202-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "convocatoria": {
    "referencia": "CONV-2-{{corrida}}",
    "emergencia_referencia": "EMG-2-{{corrida}}",
    "fecha_cierre": "{{cierre_futuro}}",
    "fecha_limite_adjudicacion": "{{limite_futuro}}"
  },
  "items": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 5
    }
  ]
}
```

**Respuesta esperada: `409 CONFLICT`**

```json
{
  "codigo": "RECURSOS_INSUFICIENTES",
  "detalles": {
    "items": [
      {
        "disponible": "2.00",
        "solicitado": "5.00",
        "tipo_recurso": "PARAMEDICO"
      }
    ]
  },
  "mensaje": "La ONG no tiene disponible lo que se pide reservar."
}
```

### 2.6 Una ONG pendiente de habilitación no puede reservar

- **Pedido:** `POST {{base_url}}/compromisos`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** **Bloqueo al ofertar.** La webapp lo llama cuando la ONG presenta la oferta. Bloquea las filas del inventario con `SELECT … FOR UPDATE`, valida la disponibilidad y la descuenta, todo en una transacción: si un ítem no alcanza, no se reserva nada. Es idempotente por oferta + ONG.
- **Qué prueba este caso:** Ayuda en Registro, la ONG pendiente de los datos de demostración.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "oferta_referencia": "OF-301-{{corrida}}",
  "ong_cuit": "30-33333333-3",
  "convocatoria": {
    "referencia": "CONV-9-{{corrida}}",
    "emergencia_referencia": "EMG-9-{{corrida}}",
    "fecha_cierre": "{{cierre_futuro}}",
    "fecha_limite_adjudicacion": "{{limite_futuro}}"
  },
  "items": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 1
    }
  ]
}
```

**Respuesta esperada: `422 UNPROCESSABLE ENTITY`**

```json
{
  "codigo": "ONG_NO_HABILITADA",
  "detalles": {
    "estado": "PENDIENTE"
  },
  "mensaje": "La ONG no está habilitada para comprometer recursos."
}
```

### 2.7 Un CUIT que no está registrado

- **Pedido:** `POST {{base_url}}/compromisos`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** **Bloqueo al ofertar.** La webapp lo llama cuando la ONG presenta la oferta. Bloquea las filas del inventario con `SELECT … FOR UPDATE`, valida la disponibilidad y la descuenta, todo en una transacción: si un ítem no alcanza, no se reserva nada. Es idempotente por oferta + ONG.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "oferta_referencia": "OF-302-{{corrida}}",
  "ong_cuit": "30-99999999-9",
  "convocatoria": {
    "referencia": "CONV-9-{{corrida}}",
    "emergencia_referencia": "EMG-9-{{corrida}}",
    "fecha_cierre": "{{cierre_futuro}}",
    "fecha_limite_adjudicacion": "{{limite_futuro}}"
  },
  "items": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 1
    }
  ]
}
```

**Respuesta esperada: `422 UNPROCESSABLE ENTITY`**

```json
{
  "codigo": "ONG_INEXISTENTE",
  "detalles": {
    "json": {
      "ong_cuit": [
        "No hay una ONG registrada con ese CUIT."
      ]
    }
  },
  "mensaje": "La ONG no está registrada en el Sistema Nacional."
}
```

### 2.8 Medio paramédico

- **Pedido:** `POST {{base_url}}/compromisos`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** **Bloqueo al ofertar.** La webapp lo llama cuando la ONG presenta la oferta. Bloquea las filas del inventario con `SELECT … FOR UPDATE`, valida la disponibilidad y la descuenta, todo en una transacción: si un ítem no alcanza, no se reserva nada. Es idempotente por oferta + ONG.
- **Qué prueba este caso:** Las personas no se fraccionan: la unidad PERSONA no admite decimales.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "oferta_referencia": "OF-303-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "convocatoria": {
    "referencia": "CONV-9-{{corrida}}",
    "emergencia_referencia": "EMG-9-{{corrida}}",
    "fecha_cierre": "{{cierre_futuro}}",
    "fecha_limite_adjudicacion": "{{limite_futuro}}"
  },
  "items": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 1.5
    }
  ]
}
```

**Respuesta esperada: `422 UNPROCESSABLE ENTITY`**

```json
{
  "codigo": "VALIDACION",
  "detalles": {
    "json": {
      "items": {
        "0": {
          "cantidad": [
            "Tiene que ser un número entero."
          ]
        }
      }
    }
  },
  "mensaje": "Hay ítems con errores."
}
```

### 2.9 Una convocatoria con la ventana de ofertas ya cerrada

- **Pedido:** `POST {{base_url}}/compromisos`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** **Bloqueo al ofertar.** La webapp lo llama cuando la ONG presenta la oferta. Bloquea las filas del inventario con `SELECT … FOR UPDATE`, valida la disponibilidad y la descuenta, todo en una transacción: si un ítem no alcanza, no se reserva nada. Es idempotente por oferta + ONG.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "oferta_referencia": "OF-304-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "convocatoria": {
    "referencia": "CONV-8-{{corrida}}",
    "emergencia_referencia": "EMG-8-{{corrida}}",
    "fecha_cierre": "{{cierre_pasado}}",
    "fecha_limite_adjudicacion": "{{limite_futuro}}"
  },
  "items": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 1
    }
  ]
}
```

**Respuesta esperada: `409 CONFLICT`**

```json
{
  "codigo": "VENTANA_CERRADA",
  "detalles": {
    "fecha_cierre": "<fecha y hora>"
  },
  "mensaje": "La convocatoria ya no recibe ofertas: no se puede reservar ni modificar recursos."
}
```

### 2.10 Una categoría en la que la ONG no está inscripta

- **Pedido:** `POST {{base_url}}/compromisos`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** **Bloqueo al ofertar.** La webapp lo llama cuando la ONG presenta la oferta. Bloquea las filas del inventario con `SELECT … FOR UPDATE`, valida la disponibilidad y la descuenta, todo en una transacción: si un ítem no alcanza, no se reserva nada. Es idempotente por oferta + ONG.
- **Qué prueba este caso:** La ONG no tiene raciones registradas: su disponible es 0.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "oferta_referencia": "OF-305-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "convocatoria": {
    "referencia": "CONV-9-{{corrida}}",
    "emergencia_referencia": "EMG-9-{{corrida}}",
    "fecha_cierre": "{{cierre_futuro}}",
    "fecha_limite_adjudicacion": "{{limite_futuro}}"
  },
  "items": [
    {
      "tipo_recurso": "RACION_ALIMENTO",
      "cantidad": 1
    }
  ]
}
```

**Respuesta esperada: `409 CONFLICT`**

```json
{
  "codigo": "RECURSOS_INSUFICIENTES",
  "detalles": {
    "items": [
      {
        "disponible": "0",
        "solicitado": "1.00",
        "tipo_recurso": "RACION_ALIMENTO"
      }
    ]
  },
  "mensaje": "La ONG no tiene disponible lo que se pide reservar."
}
```

### 2.11 Falta un campo obligatorio

- **Pedido:** `POST {{base_url}}/compromisos`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** **Bloqueo al ofertar.** La webapp lo llama cuando la ONG presenta la oferta. Bloquea las filas del inventario con `SELECT … FOR UPDATE`, valida la disponibilidad y la descuenta, todo en una transacción: si un ítem no alcanza, no se reserva nada. Es idempotente por oferta + ONG.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "oferta_referencia": "OF-306-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "items": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 1
    }
  ]
}
```

**Respuesta esperada: `422 UNPROCESSABLE ENTITY`**

```json
{
  "codigo": "VALIDACION",
  "detalles": {
    "json": {
      "convocatoria": [
        "Missing data for required field."
      ]
    }
  },
  "mensaje": "Hay campos con errores."
}
```

### 2.12 La fecha límite de adjudicación es anterior al cierre

- **Pedido:** `POST {{base_url}}/compromisos`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** **Bloqueo al ofertar.** La webapp lo llama cuando la ONG presenta la oferta. Bloquea las filas del inventario con `SELECT … FOR UPDATE`, valida la disponibilidad y la descuenta, todo en una transacción: si un ítem no alcanza, no se reserva nada. Es idempotente por oferta + ONG.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "oferta_referencia": "OF-307-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "convocatoria": {
    "referencia": "CONV-9-{{corrida}}",
    "emergencia_referencia": "EMG-9-{{corrida}}",
    "fecha_cierre": "{{limite_futuro}}",
    "fecha_limite_adjudicacion": "{{cierre_futuro}}"
  },
  "items": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 1
    }
  ]
}
```

**Respuesta esperada: `422 UNPROCESSABLE ENTITY`**

```json
{
  "codigo": "VALIDACION",
  "detalles": {
    "json": {
      "convocatoria": {
        "fecha_limite_adjudicacion": [
          "No puede ser anterior a la fecha de cierre."
        ]
      }
    }
  },
  "mensaje": "Hay campos con errores."
}
```


## 3. La ONG modifica o retira la oferta

### 3.1 La ONG modifica la oferta 101: 6 paramédicos y 50 frazadas

- **Pedido:** `PUT {{base_url}}/compromisos/{{compromiso_101}}`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** La ONG modifica la oferta dentro de la ventana: la reserva pasa a ser la nueva. Lo que aumenta necesita disponibilidad; lo que baja o desaparece se libera.
- **Qué prueba este caso:** Bajan los paramédicos, se agregan frazadas y desaparecen los rescatistas.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "items": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 6
    },
    {
      "tipo_recurso": "FRAZADA",
      "cantidad": 50
    }
  ]
}
```

**Respuesta esperada: `200 OK`**

```json
{
  "cancelado_en": null,
  "confirmado_en": null,
  "convocatoria": {
    "emergencia_referencia": "EMG-1-{{corrida}}",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "CONV-1-{{corrida}}"
  },
  "creado_en": "<fecha y hora>",
  "creado_por": "1",
  "estado": "RESERVADO",
  "finalizado_en": null,
  "id": "<id>",
  "items": [
    {
      "cantidad_comprometida": "0.00",
      "cantidad_reservada": "6.00",
      "tipo_recurso": {
        "codigo": "PARAMEDICO",
        "nombre": "Paramédico"
      }
    },
    {
      "cantidad_comprometida": "0.00",
      "cantidad_reservada": "50.00",
      "tipo_recurso": {
        "codigo": "FRAZADA",
        "nombre": "Frazada"
      }
    }
  ],
  "oferta_referencia": "OF-101-{{corrida}}",
  "ong": {
    "cuit": "{{ong_cuit}}",
    "id": "<id>",
    "razon_social": "Rescatistas de Prueba (Postman I-3.4)"
  },
  "vencido_en": null
}
```

### 3.2 Inventario después de modificar

- **Pedido:** `GET {{base_url}}/ongs/{{ong_id}}/recursos`
- **Token (pestaña Authorization):** ninguno (*No Auth*)
- **Qué hace el endpoint:** Inventario de una ONG por categoría (punto I-3.2): total, bloqueado, comprometido y disponible. Sirve para ver el efecto de cada operación. No pide token.
- **Qué prueba este caso:** Se liberaron 2 paramédicos y los 4 rescatistas; se bloquearon 50 frazadas.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cantidad_bloqueada": "50.00",
    "cantidad_comprometida": "0.00",
    "cantidad_disponible": "200.00",
    "cantidad_total": "250.00",
    "tipo_recurso": {
      "categoria": "MATERIAL",
      "codigo": "FRAZADA",
      "id": 12,
      "nombre": "Frazada",
      "reutilizable": true,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "UNIDAD",
        "id": 6,
        "nombre": "Unidades"
      }
    }
  },
  {
    "cantidad_bloqueada": "6.00",
    "cantidad_comprometida": "0.00",
    "cantidad_disponible": "4.00",
    "cantidad_total": "10.00",
    "tipo_recurso": {
      "categoria": "PERSONAL",
      "codigo": "PARAMEDICO",
      "id": 1,
      "nombre": "Paramédico",
      "reutilizable": true,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "PERSONA",
        "id": 1,
        "nombre": "Personas"
      }
    }
  },
  {
    "cantidad_bloqueada": "0.00",
    "cantidad_comprometida": "0.00",
    "cantidad_disponible": "15.00",
    "cantidad_total": "15.00",
    "tipo_recurso": {
      "categoria": "PERSONAL",
      "codigo": "RESCATISTA",
      "id": 5,
      "nombre": "Rescatista",
      "reutilizable": true,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "PERSONA",
        "id": 1,
        "nombre": "Personas"
      }
    }
  }
]
```

### 3.3 Modificar pidiendo más de lo disponible

- **Pedido:** `PUT {{base_url}}/compromisos/{{compromiso_101}}`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** La ONG modifica la oferta dentro de la ventana: la reserva pasa a ser la nueva. Lo que aumenta necesita disponibilidad; lo que baja o desaparece se libera.
- **Qué prueba este caso:** Aumentar de 6 a 11 necesita 5 más y hay 4 libres. La reserva queda como estaba.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "items": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 11
    }
  ]
}
```

**Respuesta esperada: `409 CONFLICT`**

```json
{
  "codigo": "RECURSOS_INSUFICIENTES",
  "detalles": {
    "items": [
      {
        "disponible": "4.00",
        "solicitado": "5.00",
        "tipo_recurso": "PARAMEDICO"
      }
    ]
  },
  "mensaje": "La ONG no tiene disponible lo que se pide reservar."
}
```

### 3.4 La oferta 202 de la otra emergencia ahora sí entra (4 paramédicos)

- **Pedido:** `POST {{base_url}}/compromisos`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** **Bloqueo al ofertar.** La webapp lo llama cuando la ONG presenta la oferta. Bloquea las filas del inventario con `SELECT … FOR UPDATE`, valida la disponibilidad y la descuenta, todo en una transacción: si un ítem no alcanza, no se reserva nada. Es idempotente por oferta + ONG.
- **Qué prueba este caso:** Guarda el id en `compromiso_202`.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "oferta_referencia": "OF-202-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "convocatoria": {
    "referencia": "CONV-2-{{corrida}}",
    "emergencia_referencia": "EMG-2-{{corrida}}",
    "fecha_cierre": "{{cierre_futuro}}",
    "fecha_limite_adjudicacion": "{{limite_futuro}}"
  },
  "items": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 4
    }
  ]
}
```

**Respuesta esperada: `201 CREATED`**

```json
{
  "cancelado_en": null,
  "confirmado_en": null,
  "convocatoria": {
    "emergencia_referencia": "EMG-2-{{corrida}}",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "CONV-2-{{corrida}}"
  },
  "creado_en": "<fecha y hora>",
  "creado_por": "1",
  "estado": "RESERVADO",
  "finalizado_en": null,
  "id": "<id>",
  "items": [
    {
      "cantidad_comprometida": "0.00",
      "cantidad_reservada": "4.00",
      "tipo_recurso": {
        "codigo": "PARAMEDICO",
        "nombre": "Paramédico"
      }
    }
  ],
  "oferta_referencia": "OF-202-{{corrida}}",
  "ong": {
    "cuit": "{{ong_cuit}}",
    "id": "<id>",
    "razon_social": "Rescatistas de Prueba (Postman I-3.4)"
  },
  "vencido_en": null
}
```

### 3.5 La ONG retira la oferta 202

- **Pedido:** `POST {{base_url}}/compromisos/{{compromiso_202}}/cancelacion`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** La ONG retira la oferta: la reserva se cancela y los recursos vuelven a estar disponibles.

**Respuesta esperada: `200 OK`**

```json
{
  "cancelado_en": "<fecha y hora>",
  "confirmado_en": null,
  "convocatoria": {
    "emergencia_referencia": "EMG-2-{{corrida}}",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "CONV-2-{{corrida}}"
  },
  "creado_en": "<fecha y hora>",
  "creado_por": "1",
  "estado": "CANCELADO",
  "finalizado_en": null,
  "id": "<id>",
  "items": [
    {
      "cantidad_comprometida": "0.00",
      "cantidad_reservada": "4.00",
      "tipo_recurso": {
        "codigo": "PARAMEDICO",
        "nombre": "Paramédico"
      }
    }
  ],
  "oferta_referencia": "OF-202-{{corrida}}",
  "ong": {
    "cuit": "{{ong_cuit}}",
    "id": "<id>",
    "razon_social": "Rescatistas de Prueba (Postman I-3.4)"
  },
  "vencido_en": null
}
```

### 3.6 Retirarla otra vez

- **Pedido:** `POST {{base_url}}/compromisos/{{compromiso_202}}/cancelacion`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** La ONG retira la oferta: la reserva se cancela y los recursos vuelven a estar disponibles.
- **Qué prueba este caso:** Idempotencia: un reintento responde 200 y no libera dos veces.

**Respuesta esperada: `200 OK`**

```json
{
  "cancelado_en": "<fecha y hora>",
  "confirmado_en": null,
  "convocatoria": {
    "emergencia_referencia": "EMG-2-{{corrida}}",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "CONV-2-{{corrida}}"
  },
  "creado_en": "<fecha y hora>",
  "creado_por": "1",
  "estado": "CANCELADO",
  "finalizado_en": null,
  "id": "<id>",
  "items": [
    {
      "cantidad_comprometida": "0.00",
      "cantidad_reservada": "4.00",
      "tipo_recurso": {
        "codigo": "PARAMEDICO",
        "nombre": "Paramédico"
      }
    }
  ],
  "oferta_referencia": "OF-202-{{corrida}}",
  "ong": {
    "cuit": "{{ong_cuit}}",
    "id": "<id>",
    "razon_social": "Rescatistas de Prueba (Postman I-3.4)"
  },
  "vencido_en": null
}
```

### 3.7 Inventario después de retirar la oferta 202

- **Pedido:** `GET {{base_url}}/ongs/{{ong_id}}/recursos`
- **Token (pestaña Authorization):** ninguno (*No Auth*)
- **Qué hace el endpoint:** Inventario de una ONG por categoría (punto I-3.2): total, bloqueado, comprometido y disponible. Sirve para ver el efecto de cada operación. No pide token.
- **Qué prueba este caso:** Los 4 paramédicos de la oferta 202 volvieron a estar disponibles.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cantidad_bloqueada": "50.00",
    "cantidad_comprometida": "0.00",
    "cantidad_disponible": "200.00",
    "cantidad_total": "250.00",
    "tipo_recurso": {
      "categoria": "MATERIAL",
      "codigo": "FRAZADA",
      "id": 12,
      "nombre": "Frazada",
      "reutilizable": true,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "UNIDAD",
        "id": 6,
        "nombre": "Unidades"
      }
    }
  },
  {
    "cantidad_bloqueada": "6.00",
    "cantidad_comprometida": "0.00",
    "cantidad_disponible": "4.00",
    "cantidad_total": "10.00",
    "tipo_recurso": {
      "categoria": "PERSONAL",
      "codigo": "PARAMEDICO",
      "id": 1,
      "nombre": "Paramédico",
      "reutilizable": true,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "PERSONA",
        "id": 1,
        "nombre": "Personas"
      }
    }
  },
  {
    "cantidad_bloqueada": "0.00",
    "cantidad_comprometida": "0.00",
    "cantidad_disponible": "15.00",
    "cantidad_total": "15.00",
    "tipo_recurso": {
      "categoria": "PERSONAL",
      "codigo": "RESCATISTA",
      "id": 5,
      "nombre": "Rescatista",
      "reutilizable": true,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "PERSONA",
        "id": 1,
        "nombre": "Personas"
      }
    }
  }
]
```

### 3.8 Modificar un compromiso que no existe

- **Pedido:** `PUT {{base_url}}/compromisos/999999`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** La ONG modifica la oferta dentro de la ventana: la reserva pasa a ser la nueva. Lo que aumenta necesita disponibilidad; lo que baja o desaparece se libera.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "items": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 1
    }
  ]
}
```

**Respuesta esperada: `404 NOT FOUND`**

```json
{
  "codigo": "NO_ENCONTRADO",
  "detalles": {},
  "mensaje": "El compromiso no existe."
}
```


## 4. Adjudicación: compromiso de los recursos

### 4.1 Ofertas de la convocatoria 1 (lo que ve quien adjudica)

- **Pedido:** `GET {{base_url}}/compromisos?convocatoria=CONV-1-{{corrida}}`
- **Token (pestaña Authorization):** `{{token_bonita}}` (SISTEMA_BONITA)
- **Qué hace el endpoint:** Lista reservas y compromisos. Filtros: `emergencia`, `convocatoria`, `ong_cuit`, `estado` y `oferta_referencia`.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cancelado_en": null,
    "confirmado_en": null,
    "convocatoria": {
      "emergencia_referencia": "EMG-1-{{corrida}}",
      "fecha_cierre": "<fecha y hora>",
      "fecha_limite_adjudicacion": "<fecha y hora>",
      "referencia": "CONV-1-{{corrida}}"
    },
    "creado_en": "<fecha y hora>",
    "creado_por": "1",
    "estado": "RESERVADO",
    "finalizado_en": null,
    "id": "<id>",
    "items": [
      {
        "cantidad_comprometida": "0.00",
        "cantidad_reservada": "6.00",
        "tipo_recurso": {
          "codigo": "PARAMEDICO",
          "nombre": "Paramédico"
        }
      },
      {
        "cantidad_comprometida": "0.00",
        "cantidad_reservada": "50.00",
        "tipo_recurso": {
          "codigo": "FRAZADA",
          "nombre": "Frazada"
        }
      }
    ],
    "oferta_referencia": "OF-101-{{corrida}}",
    "ong": {
      "cuit": "{{ong_cuit}}",
      "id": "<id>",
      "razon_social": "Rescatistas de Prueba (Postman I-3.4)"
    },
    "vencido_en": null
  }
]
```

### 4.2 El auditor no puede adjudicar

- **Pedido:** `POST {{base_url}}/compromisos/{{compromiso_101}}/confirmacion`
- **Token (pestaña Authorization):** `{{token_auditor}}` (AUDITOR)
- **Qué hace el endpoint:** **Adjudicación (compromiso nacional).** El municipio adjudicó la oferta: lo adjudicado pasa de bloqueado a comprometido y la diferencia de una adjudicación parcial se libera en ese momento. Lo llama la webapp (pantalla de adjudicación) o Bonita (tarea *Comprometer recursos*).

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "items": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 5
    }
  ]
}
```

**Respuesta esperada: `403 FORBIDDEN`**

```json
{
  "codigo": "PROHIBIDO",
  "detalles": {},
  "mensaje": "El rol del token no permite esta operación."
}
```

### 4.3 Adjudicar más de lo reservado

- **Pedido:** `POST {{base_url}}/compromisos/{{compromiso_101}}/confirmacion`
- **Token (pestaña Authorization):** `{{token_bonita}}` (SISTEMA_BONITA)
- **Qué hace el endpoint:** **Adjudicación (compromiso nacional).** El municipio adjudicó la oferta: lo adjudicado pasa de bloqueado a comprometido y la diferencia de una adjudicación parcial se libera en ese momento. Lo llama la webapp (pantalla de adjudicación) o Bonita (tarea *Comprometer recursos*).

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "items": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 7
    }
  ]
}
```

**Respuesta esperada: `422 UNPROCESSABLE ENTITY`**

```json
{
  "codigo": "VALIDACION",
  "detalles": {
    "json": {
      "items": {
        "0": {
          "cantidad": [
            "No puede superar lo reservado (6.00)."
          ]
        }
      }
    }
  },
  "mensaje": "Hay ítems con errores."
}
```

### 4.4 Adjudicar una categoría que no está en la reserva

- **Pedido:** `POST {{base_url}}/compromisos/{{compromiso_101}}/confirmacion`
- **Token (pestaña Authorization):** `{{token_bonita}}` (SISTEMA_BONITA)
- **Qué hace el endpoint:** **Adjudicación (compromiso nacional).** El municipio adjudicó la oferta: lo adjudicado pasa de bloqueado a comprometido y la diferencia de una adjudicación parcial se libera en ese momento. Lo llama la webapp (pantalla de adjudicación) o Bonita (tarea *Comprometer recursos*).

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "items": [
    {
      "tipo_recurso": "RESCATISTA",
      "cantidad": 1
    }
  ]
}
```

**Respuesta esperada: `422 UNPROCESSABLE ENTITY`**

```json
{
  "codigo": "VALIDACION",
  "detalles": {
    "json": {
      "items": {
        "0": {
          "tipo_recurso": [
            "No forma parte de la reserva."
          ]
        }
      }
    }
  },
  "mensaje": "Hay ítems con errores."
}
```

### 4.5 Adjudicar todo en cero

- **Pedido:** `POST {{base_url}}/compromisos/{{compromiso_101}}/confirmacion`
- **Token (pestaña Authorization):** `{{token_bonita}}` (SISTEMA_BONITA)
- **Qué hace el endpoint:** **Adjudicación (compromiso nacional).** El municipio adjudicó la oferta: lo adjudicado pasa de bloqueado a comprometido y la diferencia de una adjudicación parcial se libera en ese momento. Lo llama la webapp (pantalla de adjudicación) o Bonita (tarea *Comprometer recursos*).
- **Qué prueba este caso:** Si una oferta no se adjudica, su reserva vence sola al terminar la ventana.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "items": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 0
    }
  ]
}
```

**Respuesta esperada: `422 UNPROCESSABLE ENTITY`**

```json
{
  "codigo": "VALIDACION",
  "detalles": {},
  "mensaje": "La adjudicación no incluye ningún recurso. Si la oferta no se adjudica, su reserva vence sola al terminar la ventana de adjudicación."
}
```

### 4.6 El municipio adjudica 5 de los 6 paramédicos (adjudicación parcial)

- **Pedido:** `POST {{base_url}}/compromisos/{{compromiso_101}}/confirmacion`
- **Token (pestaña Authorization):** `{{token_bonita}}` (SISTEMA_BONITA)
- **Qué hace el endpoint:** **Adjudicación (compromiso nacional).** El municipio adjudicó la oferta: lo adjudicado pasa de bloqueado a comprometido y la diferencia de una adjudicación parcial se libera en ese momento. Lo llama la webapp (pantalla de adjudicación) o Bonita (tarea *Comprometer recursos*).
- **Qué prueba este caso:** Las frazadas no se nombran: se adjudican en 0 y se liberan.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "items": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 5
    }
  ]
}
```

**Respuesta esperada: `200 OK`**

```json
{
  "cancelado_en": null,
  "confirmado_en": "<fecha y hora>",
  "convocatoria": {
    "emergencia_referencia": "EMG-1-{{corrida}}",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "CONV-1-{{corrida}}"
  },
  "creado_en": "<fecha y hora>",
  "creado_por": "1",
  "estado": "COMPROMETIDO",
  "finalizado_en": null,
  "id": "<id>",
  "items": [
    {
      "cantidad_comprometida": "5.00",
      "cantidad_reservada": "6.00",
      "tipo_recurso": {
        "codigo": "PARAMEDICO",
        "nombre": "Paramédico"
      }
    },
    {
      "cantidad_comprometida": "0.00",
      "cantidad_reservada": "50.00",
      "tipo_recurso": {
        "codigo": "FRAZADA",
        "nombre": "Frazada"
      }
    }
  ],
  "oferta_referencia": "OF-101-{{corrida}}",
  "ong": {
    "cuit": "{{ong_cuit}}",
    "id": "<id>",
    "razon_social": "Rescatistas de Prueba (Postman I-3.4)"
  },
  "vencido_en": null
}
```

### 4.7 Inventario después de adjudicar

- **Pedido:** `GET {{base_url}}/ongs/{{ong_id}}/recursos`
- **Token (pestaña Authorization):** ninguno (*No Auth*)
- **Qué hace el endpoint:** Inventario de una ONG por categoría (punto I-3.2): total, bloqueado, comprometido y disponible. Sirve para ver el efecto de cada operación. No pide token.
- **Qué prueba este caso:** 5 paramédicos pasan de bloqueados a comprometidos y el sexto se libera. Las 50 frazadas no adjudicadas vuelven a estar disponibles.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cantidad_bloqueada": "0.00",
    "cantidad_comprometida": "0.00",
    "cantidad_disponible": "250.00",
    "cantidad_total": "250.00",
    "tipo_recurso": {
      "categoria": "MATERIAL",
      "codigo": "FRAZADA",
      "id": 12,
      "nombre": "Frazada",
      "reutilizable": true,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "UNIDAD",
        "id": 6,
        "nombre": "Unidades"
      }
    }
  },
  {
    "cantidad_bloqueada": "0.00",
    "cantidad_comprometida": "5.00",
    "cantidad_disponible": "5.00",
    "cantidad_total": "10.00",
    "tipo_recurso": {
      "categoria": "PERSONAL",
      "codigo": "PARAMEDICO",
      "id": 1,
      "nombre": "Paramédico",
      "reutilizable": true,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "PERSONA",
        "id": 1,
        "nombre": "Personas"
      }
    }
  },
  {
    "cantidad_bloqueada": "0.00",
    "cantidad_comprometida": "0.00",
    "cantidad_disponible": "15.00",
    "cantidad_total": "15.00",
    "tipo_recurso": {
      "categoria": "PERSONAL",
      "codigo": "RESCATISTA",
      "id": 5,
      "nombre": "Rescatista",
      "reutilizable": true,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "PERSONA",
        "id": 1,
        "nombre": "Personas"
      }
    }
  }
]
```

### 4.8 La webapp repite la misma adjudicación

- **Pedido:** `POST {{base_url}}/compromisos/{{compromiso_101}}/confirmacion`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** **Adjudicación (compromiso nacional).** El municipio adjudicó la oferta: lo adjudicado pasa de bloqueado a comprometido y la diferencia de una adjudicación parcial se libera en ese momento. Lo llama la webapp (pantalla de adjudicación) o Bonita (tarea *Comprometer recursos*).
- **Qué prueba este caso:** Idempotencia: la webapp o Bonita pueden reintentar sin comprometer dos veces.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "items": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 5
    }
  ]
}
```

**Respuesta esperada: `200 OK`**

```json
{
  "cancelado_en": null,
  "confirmado_en": "<fecha y hora>",
  "convocatoria": {
    "emergencia_referencia": "EMG-1-{{corrida}}",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "CONV-1-{{corrida}}"
  },
  "creado_en": "<fecha y hora>",
  "creado_por": "1",
  "estado": "COMPROMETIDO",
  "finalizado_en": null,
  "id": "<id>",
  "items": [
    {
      "cantidad_comprometida": "5.00",
      "cantidad_reservada": "6.00",
      "tipo_recurso": {
        "codigo": "PARAMEDICO",
        "nombre": "Paramédico"
      }
    },
    {
      "cantidad_comprometida": "0.00",
      "cantidad_reservada": "50.00",
      "tipo_recurso": {
        "codigo": "FRAZADA",
        "nombre": "Frazada"
      }
    }
  ],
  "oferta_referencia": "OF-101-{{corrida}}",
  "ong": {
    "cuit": "{{ong_cuit}}",
    "id": "<id>",
    "razon_social": "Rescatistas de Prueba (Postman I-3.4)"
  },
  "vencido_en": null
}
```

### 4.9 Adjudicar otra cantidad sobre lo ya adjudicado

- **Pedido:** `POST {{base_url}}/compromisos/{{compromiso_101}}/confirmacion`
- **Token (pestaña Authorization):** `{{token_bonita}}` (SISTEMA_BONITA)
- **Qué hace el endpoint:** **Adjudicación (compromiso nacional).** El municipio adjudicó la oferta: lo adjudicado pasa de bloqueado a comprometido y la diferencia de una adjudicación parcial se libera en ese momento. Lo llama la webapp (pantalla de adjudicación) o Bonita (tarea *Comprometer recursos*).

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "items": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 4
    }
  ]
}
```

**Respuesta esperada: `409 CONFLICT`**

```json
{
  "codigo": "TRANSICION_INVALIDA",
  "detalles": {
    "estado_actual": "COMPROMETIDO",
    "estado_pedido": "COMPROMETIDO"
  },
  "mensaje": "No se puede pasar el compromiso de COMPROMETIDO a COMPROMETIDO."
}
```

### 4.10 La ONG intenta retirar una oferta ya adjudicada

- **Pedido:** `POST {{base_url}}/compromisos/{{compromiso_101}}/cancelacion`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** La ONG retira la oferta: la reserva se cancela y los recursos vuelven a estar disponibles.

**Respuesta esperada: `409 CONFLICT`**

```json
{
  "codigo": "TRANSICION_INVALIDA",
  "detalles": {
    "estado_actual": "COMPROMETIDO",
    "estado_pedido": "CANCELADO"
  },
  "mensaje": "No se puede pasar el compromiso de COMPROMETIDO a CANCELADO."
}
```

### 4.11 La ONG intenta modificar una oferta ya adjudicada

- **Pedido:** `PUT {{base_url}}/compromisos/{{compromiso_101}}`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** La ONG modifica la oferta dentro de la ventana: la reserva pasa a ser la nueva. Lo que aumenta necesita disponibilidad; lo que baja o desaparece se libera.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "items": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 1
    }
  ]
}
```

**Respuesta esperada: `409 CONFLICT`**

```json
{
  "codigo": "COMPROMISO_NO_MODIFICABLE",
  "detalles": {
    "estado": "COMPROMETIDO"
  },
  "mensaje": "Solo se puede modificar una reserva vigente."
}
```


## 5. Ventana de adjudicación y vencimiento

### 5.1 Oferta 404: reservar 1 rescatista en la convocatoria 4

- **Pedido:** `POST {{base_url}}/compromisos`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** **Bloqueo al ofertar.** La webapp lo llama cuando la ONG presenta la oferta. Bloquea las filas del inventario con `SELECT … FOR UPDATE`, valida la disponibilidad y la descuenta, todo en una transacción: si un ítem no alcanza, no se reserva nada. Es idempotente por oferta + ONG.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "oferta_referencia": "OF-404-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "convocatoria": {
    "referencia": "CONV-4-{{corrida}}",
    "emergencia_referencia": "EMG-4-{{corrida}}",
    "fecha_cierre": "{{cierre_futuro}}",
    "fecha_limite_adjudicacion": "{{limite_futuro}}"
  },
  "items": [
    {
      "tipo_recurso": "RESCATISTA",
      "cantidad": 1
    }
  ]
}
```

**Respuesta esperada: `201 CREATED`**

```json
{
  "cancelado_en": null,
  "confirmado_en": null,
  "convocatoria": {
    "emergencia_referencia": "EMG-4-{{corrida}}",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "CONV-4-{{corrida}}"
  },
  "creado_en": "<fecha y hora>",
  "creado_por": "1",
  "estado": "RESERVADO",
  "finalizado_en": null,
  "id": "<id>",
  "items": [
    {
      "cantidad_comprometida": "0.00",
      "cantidad_reservada": "1.00",
      "tipo_recurso": {
        "codigo": "RESCATISTA",
        "nombre": "Rescatista"
      }
    }
  ],
  "oferta_referencia": "OF-404-{{corrida}}",
  "ong": {
    "cuit": "{{ong_cuit}}",
    "id": "<id>",
    "razon_social": "Rescatistas de Prueba (Postman I-3.4)"
  },
  "vencido_en": null
}
```

### 5.2 Cierra la ventana de ofertas de la convocatoria 4 (la de adjudicación sigue abierta)

- **Pedido:** `PUT {{base_url}}/convocatorias/CONV-4-{{corrida}}`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** Reabrir la convocatoria con fechas nuevas: las reservas vigentes pasan a vencer con la nueva fecha límite de adjudicación.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "fecha_cierre": "{{cierre_pasado}}",
  "fecha_limite_adjudicacion": "{{limite_futuro}}"
}
```

**Respuesta esperada: `200 OK`**

```json
{
  "emergencia_referencia": "EMG-4-{{corrida}}",
  "fecha_cierre": "<fecha y hora>",
  "fecha_limite_adjudicacion": "<fecha y hora>",
  "referencia": "CONV-4-{{corrida}}"
}
```

### 5.3 Ya no se puede modificar la oferta

- **Pedido:** `PUT {{base_url}}/compromisos/{{compromiso_404}}`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** La ONG modifica la oferta dentro de la ventana: la reserva pasa a ser la nueva. Lo que aumenta necesita disponibilidad; lo que baja o desaparece se libera.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "items": [
    {
      "tipo_recurso": "RESCATISTA",
      "cantidad": 2
    }
  ]
}
```

**Respuesta esperada: `409 CONFLICT`**

```json
{
  "codigo": "VENTANA_CERRADA",
  "detalles": {
    "fecha_cierre": "<fecha y hora>"
  },
  "mensaje": "La convocatoria ya no recibe ofertas: no se puede reservar ni modificar recursos."
}
```

### 5.4 Pero sí se puede adjudicar: la reserva sigue bloqueada hasta el límite

- **Pedido:** `POST {{base_url}}/compromisos/{{compromiso_404}}/confirmacion`
- **Token (pestaña Authorization):** `{{token_bonita}}` (SISTEMA_BONITA)
- **Qué hace el endpoint:** **Adjudicación (compromiso nacional).** El municipio adjudicó la oferta: lo adjudicado pasa de bloqueado a comprometido y la diferencia de una adjudicación parcial se libera en ese momento. Lo llama la webapp (pantalla de adjudicación) o Bonita (tarea *Comprometer recursos*).

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "items": [
    {
      "tipo_recurso": "RESCATISTA",
      "cantidad": 1
    }
  ]
}
```

**Respuesta esperada: `200 OK`**

```json
{
  "cancelado_en": null,
  "confirmado_en": "<fecha y hora>",
  "convocatoria": {
    "emergencia_referencia": "EMG-4-{{corrida}}",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "CONV-4-{{corrida}}"
  },
  "creado_en": "<fecha y hora>",
  "creado_por": "1",
  "estado": "COMPROMETIDO",
  "finalizado_en": null,
  "id": "<id>",
  "items": [
    {
      "cantidad_comprometida": "1.00",
      "cantidad_reservada": "1.00",
      "tipo_recurso": {
        "codigo": "RESCATISTA",
        "nombre": "Rescatista"
      }
    }
  ],
  "oferta_referencia": "OF-404-{{corrida}}",
  "ong": {
    "cuit": "{{ong_cuit}}",
    "id": "<id>",
    "razon_social": "Rescatistas de Prueba (Postman I-3.4)"
  },
  "vencido_en": null
}
```

### 5.5 Oferta 303: reservar 2 rescatistas en la convocatoria 3

- **Pedido:** `POST {{base_url}}/compromisos`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** **Bloqueo al ofertar.** La webapp lo llama cuando la ONG presenta la oferta. Bloquea las filas del inventario con `SELECT … FOR UPDATE`, valida la disponibilidad y la descuenta, todo en una transacción: si un ítem no alcanza, no se reserva nada. Es idempotente por oferta + ONG.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "oferta_referencia": "OF-303-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "convocatoria": {
    "referencia": "CONV-3-{{corrida}}",
    "emergencia_referencia": "EMG-3-{{corrida}}",
    "fecha_cierre": "{{cierre_futuro}}",
    "fecha_limite_adjudicacion": "{{limite_futuro}}"
  },
  "items": [
    {
      "tipo_recurso": "RESCATISTA",
      "cantidad": 2
    }
  ]
}
```

**Respuesta esperada: `201 CREATED`**

```json
{
  "cancelado_en": null,
  "confirmado_en": null,
  "convocatoria": {
    "emergencia_referencia": "EMG-3-{{corrida}}",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "CONV-3-{{corrida}}"
  },
  "creado_en": "<fecha y hora>",
  "creado_por": "1",
  "estado": "RESERVADO",
  "finalizado_en": null,
  "id": "<id>",
  "items": [
    {
      "cantidad_comprometida": "0.00",
      "cantidad_reservada": "2.00",
      "tipo_recurso": {
        "codigo": "RESCATISTA",
        "nombre": "Rescatista"
      }
    }
  ],
  "oferta_referencia": "OF-303-{{corrida}}",
  "ong": {
    "cuit": "{{ong_cuit}}",
    "id": "<id>",
    "razon_social": "Rescatistas de Prueba (Postman I-3.4)"
  },
  "vencido_en": null
}
```

### 5.6 Termina también la ventana de adjudicación de la convocatoria 3

- **Pedido:** `PUT {{base_url}}/convocatorias/CONV-3-{{corrida}}`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** Reabrir la convocatoria con fechas nuevas: las reservas vigentes pasan a vencer con la nueva fecha límite de adjudicación.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "fecha_cierre": "{{cierre_pasado}}",
  "fecha_limite_adjudicacion": "{{limite_pasado}}"
}
```

**Respuesta esperada: `200 OK`**

```json
{
  "emergencia_referencia": "EMG-3-{{corrida}}",
  "fecha_cierre": "<fecha y hora>",
  "fecha_limite_adjudicacion": "<fecha y hora>",
  "referencia": "CONV-3-{{corrida}}"
}
```

### 5.7 Adjudicar después del límite

- **Pedido:** `POST {{base_url}}/compromisos/{{compromiso_303}}/confirmacion`
- **Token (pestaña Authorization):** `{{token_bonita}}` (SISTEMA_BONITA)
- **Qué hace el endpoint:** **Adjudicación (compromiso nacional).** El municipio adjudicó la oferta: lo adjudicado pasa de bloqueado a comprometido y la diferencia de una adjudicación parcial se libera en ese momento. Lo llama la webapp (pantalla de adjudicación) o Bonita (tarea *Comprometer recursos*).
- **Qué prueba este caso:** La reserva vence en ese momento y sus recursos se liberan.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "items": [
    {
      "tipo_recurso": "RESCATISTA",
      "cantidad": 2
    }
  ]
}
```

**Respuesta esperada: `409 CONFLICT`**

```json
{
  "codigo": "RESERVA_VENCIDA",
  "detalles": {
    "fecha_limite_adjudicacion": "<fecha y hora>"
  },
  "mensaje": "Terminó la ventana de adjudicación: la reserva venció y liberó sus recursos."
}
```

### 5.8 La oferta 303 quedó vencida

- **Pedido:** `GET {{base_url}}/compromisos/{{compromiso_303}}`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** Detalle de una reserva o compromiso.

**Respuesta esperada: `200 OK`**

```json
{
  "cancelado_en": null,
  "confirmado_en": null,
  "convocatoria": {
    "emergencia_referencia": "EMG-3-{{corrida}}",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "CONV-3-{{corrida}}"
  },
  "creado_en": "<fecha y hora>",
  "creado_por": "1",
  "estado": "VENCIDO",
  "finalizado_en": null,
  "id": "<id>",
  "items": [
    {
      "cantidad_comprometida": "0.00",
      "cantidad_reservada": "2.00",
      "tipo_recurso": {
        "codigo": "RESCATISTA",
        "nombre": "Rescatista"
      }
    }
  ],
  "oferta_referencia": "OF-303-{{corrida}}",
  "ong": {
    "cuit": "{{ong_cuit}}",
    "id": "<id>",
    "razon_social": "Rescatistas de Prueba (Postman I-3.4)"
  },
  "vencido_en": "<fecha y hora>"
}
```

### 5.9 Inventario después del vencimiento

- **Pedido:** `GET {{base_url}}/ongs/{{ong_id}}/recursos`
- **Token (pestaña Authorization):** ninguno (*No Auth*)
- **Qué hace el endpoint:** Inventario de una ONG por categoría (punto I-3.2): total, bloqueado, comprometido y disponible. Sirve para ver el efecto de cada operación. No pide token.
- **Qué prueba este caso:** Rescatistas: 1 comprometido por la oferta 404 y los 2 de la oferta 303 liberados.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cantidad_bloqueada": "0.00",
    "cantidad_comprometida": "0.00",
    "cantidad_disponible": "250.00",
    "cantidad_total": "250.00",
    "tipo_recurso": {
      "categoria": "MATERIAL",
      "codigo": "FRAZADA",
      "id": 12,
      "nombre": "Frazada",
      "reutilizable": true,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "UNIDAD",
        "id": 6,
        "nombre": "Unidades"
      }
    }
  },
  {
    "cantidad_bloqueada": "0.00",
    "cantidad_comprometida": "5.00",
    "cantidad_disponible": "5.00",
    "cantidad_total": "10.00",
    "tipo_recurso": {
      "categoria": "PERSONAL",
      "codigo": "PARAMEDICO",
      "id": 1,
      "nombre": "Paramédico",
      "reutilizable": true,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "PERSONA",
        "id": 1,
        "nombre": "Personas"
      }
    }
  },
  {
    "cantidad_bloqueada": "0.00",
    "cantidad_comprometida": "1.00",
    "cantidad_disponible": "14.00",
    "cantidad_total": "15.00",
    "tipo_recurso": {
      "categoria": "PERSONAL",
      "codigo": "RESCATISTA",
      "id": 5,
      "nombre": "Rescatista",
      "reutilizable": true,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "PERSONA",
        "id": 1,
        "nombre": "Personas"
      }
    }
  }
]
```

### 5.10 Fechas incoherentes al reabrir

- **Pedido:** `PUT {{base_url}}/convocatorias/CONV-3-{{corrida}}`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** Reabrir la convocatoria con fechas nuevas: las reservas vigentes pasan a vencer con la nueva fecha límite de adjudicación.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "fecha_cierre": "{{limite_futuro}}",
  "fecha_limite_adjudicacion": "{{cierre_futuro}}"
}
```

**Respuesta esperada: `422 UNPROCESSABLE ENTITY`**

```json
{
  "codigo": "VALIDACION",
  "detalles": {
    "json": {
      "fecha_limite_adjudicacion": [
        "No puede ser anterior a la fecha de cierre."
      ]
    }
  },
  "mensaje": "Hay campos con errores."
}
```

### 5.11 Consultar la convocatoria 4

- **Pedido:** `GET {{base_url}}/convocatorias/CONV-4-{{corrida}}`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** Fechas de una convocatoria. La convocatoria se registra sola con la primera reserva que la nombra.

**Respuesta esperada: `200 OK`**

```json
{
  "emergencia_referencia": "EMG-4-{{corrida}}",
  "fecha_cierre": "<fecha y hora>",
  "fecha_limite_adjudicacion": "<fecha y hora>",
  "referencia": "CONV-4-{{corrida}}"
}
```

### 5.12 Una convocatoria que no existe

- **Pedido:** `GET {{base_url}}/convocatorias/no-existe`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** Fechas de una convocatoria. La convocatoria se registra sola con la primera reserva que la nombra.

**Respuesta esperada: `404 NOT FOUND`**

```json
{
  "codigo": "NO_ENCONTRADO",
  "detalles": {},
  "mensaje": "La convocatoria no existe."
}
```


## 6. Reformulación de la convocatoria

### 6.1 Oferta 505: reservar 10 frazadas en la convocatoria 5

- **Pedido:** `POST {{base_url}}/compromisos`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** **Bloqueo al ofertar.** La webapp lo llama cuando la ONG presenta la oferta. Bloquea las filas del inventario con `SELECT … FOR UPDATE`, valida la disponibilidad y la descuenta, todo en una transacción: si un ítem no alcanza, no se reserva nada. Es idempotente por oferta + ONG.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "oferta_referencia": "OF-505-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "convocatoria": {
    "referencia": "CONV-5-{{corrida}}",
    "emergencia_referencia": "EMG-5-{{corrida}}",
    "fecha_cierre": "{{cierre_futuro}}",
    "fecha_limite_adjudicacion": "{{limite_futuro}}"
  },
  "items": [
    {
      "tipo_recurso": "FRAZADA",
      "cantidad": 10
    }
  ]
}
```

**Respuesta esperada: `201 CREATED`**

```json
{
  "cancelado_en": null,
  "confirmado_en": null,
  "convocatoria": {
    "emergencia_referencia": "EMG-5-{{corrida}}",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "CONV-5-{{corrida}}"
  },
  "creado_en": "<fecha y hora>",
  "creado_por": "1",
  "estado": "RESERVADO",
  "finalizado_en": null,
  "id": "<id>",
  "items": [
    {
      "cantidad_comprometida": "0.00",
      "cantidad_reservada": "10.00",
      "tipo_recurso": {
        "codigo": "FRAZADA",
        "nombre": "Frazada"
      }
    }
  ],
  "oferta_referencia": "OF-505-{{corrida}}",
  "ong": {
    "cuit": "{{ong_cuit}}",
    "id": "<id>",
    "razon_social": "Rescatistas de Prueba (Postman I-3.4)"
  },
  "vencido_en": null
}
```

### 6.2 Reformular la convocatoria 5: sus reservas pasan a la 5B

- **Pedido:** `POST {{base_url}}/convocatorias/CONV-5-{{corrida}}/reformulacion`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** Reformular la convocatoria: sus reservas vigentes pasan a la convocatoria nueva, que hereda la emergencia.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "nueva": {
    "referencia": "CONV-5B-{{corrida}}",
    "fecha_cierre": "{{cierre_futuro}}",
    "fecha_limite_adjudicacion": "{{limite_futuro}}"
  }
}
```

**Respuesta esperada: `200 OK`**

```json
{
  "compromisos_movidos": 1,
  "convocatoria": {
    "emergencia_referencia": "EMG-5-{{corrida}}",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "CONV-5B-{{corrida}}"
  }
}
```

### 6.3 La oferta 505 ahora pertenece a la convocatoria 5B

- **Pedido:** `GET {{base_url}}/compromisos/{{compromiso_505}}`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** Detalle de una reserva o compromiso.

**Respuesta esperada: `200 OK`**

```json
{
  "cancelado_en": null,
  "confirmado_en": null,
  "convocatoria": {
    "emergencia_referencia": "EMG-5-{{corrida}}",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "CONV-5B-{{corrida}}"
  },
  "creado_en": "<fecha y hora>",
  "creado_por": "1",
  "estado": "RESERVADO",
  "finalizado_en": null,
  "id": "<id>",
  "items": [
    {
      "cantidad_comprometida": "0.00",
      "cantidad_reservada": "10.00",
      "tipo_recurso": {
        "codigo": "FRAZADA",
        "nombre": "Frazada"
      }
    }
  ],
  "oferta_referencia": "OF-505-{{corrida}}",
  "ong": {
    "cuit": "{{ong_cuit}}",
    "id": "<id>",
    "razon_social": "Rescatistas de Prueba (Postman I-3.4)"
  },
  "vencido_en": null
}
```

### 6.4 Repetir la reformulación

- **Pedido:** `POST {{base_url}}/convocatorias/CONV-5-{{corrida}}/reformulacion`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** Reformular la convocatoria: sus reservas vigentes pasan a la convocatoria nueva, que hereda la emergencia.
- **Qué prueba este caso:** Idempotencia: ya no queda nada por mover.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "nueva": {
    "referencia": "CONV-5B-{{corrida}}",
    "fecha_cierre": "{{cierre_futuro}}",
    "fecha_limite_adjudicacion": "{{limite_futuro}}"
  }
}
```

**Respuesta esperada: `200 OK`**

```json
{
  "compromisos_movidos": 0,
  "convocatoria": {
    "emergencia_referencia": "EMG-5-{{corrida}}",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "CONV-5B-{{corrida}}"
  }
}
```

### 6.5 Reformular hacia la misma convocatoria

- **Pedido:** `POST {{base_url}}/convocatorias/CONV-5B-{{corrida}}/reformulacion`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** Reformular la convocatoria: sus reservas vigentes pasan a la convocatoria nueva, que hereda la emergencia.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "nueva": {
    "referencia": "CONV-5B-{{corrida}}",
    "fecha_cierre": "{{cierre_futuro}}",
    "fecha_limite_adjudicacion": "{{limite_futuro}}"
  }
}
```

**Respuesta esperada: `422 UNPROCESSABLE ENTITY`**

```json
{
  "codigo": "VALIDACION",
  "detalles": {
    "json": {
      "nueva": {
        "referencia": [
          "Es igual a la original."
        ]
      }
    }
  },
  "mensaje": "La convocatoria nueva tiene que tener otra referencia."
}
```


## 7. Consultas

### 7.1 Compromisos de la emergencia 1

- **Pedido:** `GET {{base_url}}/compromisos?emergencia=EMG-1-{{corrida}}`
- **Token (pestaña Authorization):** `{{token_auditor}}` (AUDITOR)
- **Qué hace el endpoint:** Lista reservas y compromisos. Filtros: `emergencia`, `convocatoria`, `ong_cuit`, `estado` y `oferta_referencia`.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cancelado_en": null,
    "confirmado_en": "<fecha y hora>",
    "convocatoria": {
      "emergencia_referencia": "EMG-1-{{corrida}}",
      "fecha_cierre": "<fecha y hora>",
      "fecha_limite_adjudicacion": "<fecha y hora>",
      "referencia": "CONV-1-{{corrida}}"
    },
    "creado_en": "<fecha y hora>",
    "creado_por": "1",
    "estado": "COMPROMETIDO",
    "finalizado_en": null,
    "id": "<id>",
    "items": [
      {
        "cantidad_comprometida": "5.00",
        "cantidad_reservada": "6.00",
        "tipo_recurso": {
          "codigo": "PARAMEDICO",
          "nombre": "Paramédico"
        }
      },
      {
        "cantidad_comprometida": "0.00",
        "cantidad_reservada": "50.00",
        "tipo_recurso": {
          "codigo": "FRAZADA",
          "nombre": "Frazada"
        }
      }
    ],
    "oferta_referencia": "OF-101-{{corrida}}",
    "ong": {
      "cuit": "{{ong_cuit}}",
      "id": "<id>",
      "razon_social": "Rescatistas de Prueba (Postman I-3.4)"
    },
    "vencido_en": null
  }
]
```

### 7.2 Compromisos vencidos de la ONG

- **Pedido:** `GET {{base_url}}/compromisos?estado=VENCIDO&ong_cuit={{ong_cuit}}`
- **Token (pestaña Authorization):** `{{token_auditor}}` (AUDITOR)
- **Qué hace el endpoint:** Lista reservas y compromisos. Filtros: `emergencia`, `convocatoria`, `ong_cuit`, `estado` y `oferta_referencia`.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cancelado_en": null,
    "confirmado_en": null,
    "convocatoria": {
      "emergencia_referencia": "EMG-3-{{corrida}}",
      "fecha_cierre": "<fecha y hora>",
      "fecha_limite_adjudicacion": "<fecha y hora>",
      "referencia": "CONV-3-{{corrida}}"
    },
    "creado_en": "<fecha y hora>",
    "creado_por": "1",
    "estado": "VENCIDO",
    "finalizado_en": null,
    "id": "<id>",
    "items": [
      {
        "cantidad_comprometida": "0.00",
        "cantidad_reservada": "2.00",
        "tipo_recurso": {
          "codigo": "RESCATISTA",
          "nombre": "Rescatista"
        }
      }
    ],
    "oferta_referencia": "OF-303-{{corrida}}",
    "ong": {
      "cuit": "{{ong_cuit}}",
      "id": "<id>",
      "razon_social": "Rescatistas de Prueba (Postman I-3.4)"
    },
    "vencido_en": "<fecha y hora>"
  }
]
```

### 7.3 Compromisos cancelados de la ONG

- **Pedido:** `GET {{base_url}}/compromisos?estado=CANCELADO&ong_cuit={{ong_cuit}}`
- **Token (pestaña Authorization):** `{{token_auditor}}` (AUDITOR)
- **Qué hace el endpoint:** Lista reservas y compromisos. Filtros: `emergencia`, `convocatoria`, `ong_cuit`, `estado` y `oferta_referencia`.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cancelado_en": "<fecha y hora>",
    "confirmado_en": null,
    "convocatoria": {
      "emergencia_referencia": "EMG-2-{{corrida}}",
      "fecha_cierre": "<fecha y hora>",
      "fecha_limite_adjudicacion": "<fecha y hora>",
      "referencia": "CONV-2-{{corrida}}"
    },
    "creado_en": "<fecha y hora>",
    "creado_por": "1",
    "estado": "CANCELADO",
    "finalizado_en": null,
    "id": "<id>",
    "items": [
      {
        "cantidad_comprometida": "0.00",
        "cantidad_reservada": "4.00",
        "tipo_recurso": {
          "codigo": "PARAMEDICO",
          "nombre": "Paramédico"
        }
      }
    ],
    "oferta_referencia": "OF-202-{{corrida}}",
    "ong": {
      "cuit": "{{ong_cuit}}",
      "id": "<id>",
      "razon_social": "Rescatistas de Prueba (Postman I-3.4)"
    },
    "vencido_en": null
  }
]
```

### 7.4 Compromisos de una oferta

- **Pedido:** `GET {{base_url}}/compromisos?oferta_referencia=OF-101-{{corrida}}`
- **Token (pestaña Authorization):** `{{token_auditor}}` (AUDITOR)
- **Qué hace el endpoint:** Lista reservas y compromisos. Filtros: `emergencia`, `convocatoria`, `ong_cuit`, `estado` y `oferta_referencia`.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cancelado_en": null,
    "confirmado_en": "<fecha y hora>",
    "convocatoria": {
      "emergencia_referencia": "EMG-1-{{corrida}}",
      "fecha_cierre": "<fecha y hora>",
      "fecha_limite_adjudicacion": "<fecha y hora>",
      "referencia": "CONV-1-{{corrida}}"
    },
    "creado_en": "<fecha y hora>",
    "creado_por": "1",
    "estado": "COMPROMETIDO",
    "finalizado_en": null,
    "id": "<id>",
    "items": [
      {
        "cantidad_comprometida": "5.00",
        "cantidad_reservada": "6.00",
        "tipo_recurso": {
          "codigo": "PARAMEDICO",
          "nombre": "Paramédico"
        }
      },
      {
        "cantidad_comprometida": "0.00",
        "cantidad_reservada": "50.00",
        "tipo_recurso": {
          "codigo": "FRAZADA",
          "nombre": "Frazada"
        }
      }
    ],
    "oferta_referencia": "OF-101-{{corrida}}",
    "ong": {
      "cuit": "{{ong_cuit}}",
      "id": "<id>",
      "razon_social": "Rescatistas de Prueba (Postman I-3.4)"
    },
    "vencido_en": null
  }
]
```

### 7.5 Todos los compromisos de la ONG

- **Pedido:** `GET {{base_url}}/compromisos?ong_cuit={{ong_cuit}}`
- **Token (pestaña Authorization):** `{{token_auditor}}` (AUDITOR)
- **Qué hace el endpoint:** Lista reservas y compromisos. Filtros: `emergencia`, `convocatoria`, `ong_cuit`, `estado` y `oferta_referencia`.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cancelado_en": null,
    "confirmado_en": null,
    "convocatoria": {
      "emergencia_referencia": "EMG-5-{{corrida}}",
      "fecha_cierre": "<fecha y hora>",
      "fecha_limite_adjudicacion": "<fecha y hora>",
      "referencia": "CONV-5B-{{corrida}}"
    },
    "creado_en": "<fecha y hora>",
    "creado_por": "1",
    "estado": "RESERVADO",
    "finalizado_en": null,
    "id": "<id>",
    "items": [
      {
        "cantidad_comprometida": "0.00",
        "cantidad_reservada": "10.00",
        "tipo_recurso": {
          "codigo": "FRAZADA",
          "nombre": "Frazada"
        }
      }
    ],
    "oferta_referencia": "OF-505-{{corrida}}",
    "ong": {
      "cuit": "{{ong_cuit}}",
      "id": "<id>",
      "razon_social": "Rescatistas de Prueba (Postman I-3.4)"
    },
    "vencido_en": null
  },
  {
    "cancelado_en": null,
    "confirmado_en": null,
    "convocatoria": {
      "emergencia_referencia": "EMG-3-{{corrida}}",
      "fecha_cierre": "<fecha y hora>",
      "fecha_limite_adjudicacion": "<fecha y hora>",
      "referencia": "CONV-3-{{corrida}}"
    },
    "creado_en": "<fecha y hora>",
    "creado_por": "1",
    "estado": "VENCIDO",
    "finalizado_en": null,
    "id": "<id>",
    "items": [
      {
        "cantidad_comprometida": "0.00",
        "cantidad_reservada": "2.00",
        "tipo_recurso": {
          "codigo": "RESCATISTA",
          "nombre": "Rescatista"
        }
      }
    ],
    "oferta_referencia": "OF-303-{{corrida}}",
    "ong": {
      "cuit": "{{ong_cuit}}",
      "id": "<id>",
      "razon_social": "Rescatistas de Prueba (Postman I-3.4)"
    },
    "vencido_en": "<fecha y hora>"
  },
  {
    "cancelado_en": null,
    "confirmado_en": "<fecha y hora>",
    "convocatoria": {
      "emergencia_referencia": "EMG-4-{{corrida}}",
      "fecha_cierre": "<fecha y hora>",
      "fecha_limite_adjudicacion": "<fecha y hora>",
      "referencia": "CONV-4-{{corrida}}"
    },
    "creado_en": "<fecha y hora>",
    "creado_por": "1",
    "estado": "COMPROMETIDO",
    "finalizado_en": null,
    "id": "<id>",
    "items": [
      {
        "cantidad_comprometida": "1.00",
        "cantidad_reservada": "1.00",
        "tipo_recurso": {
          "codigo": "RESCATISTA",
          "nombre": "Rescatista"
        }
      }
    ],
    "oferta_referencia": "OF-404-{{corrida}}",
    "ong": {
      "cuit": "{{ong_cuit}}",
      "id": "<id>",
      "razon_social": "Rescatistas de Prueba (Postman I-3.4)"
    },
    "vencido_en": null
  },
  {
    "cancelado_en": "<fecha y hora>",
    "confirmado_en": null,
    "convocatoria": {
      "emergencia_referencia": "EMG-2-{{corrida}}",
      "fecha_cierre": "<fecha y hora>",
      "fecha_limite_adjudicacion": "<fecha y hora>",
      "referencia": "CONV-2-{{corrida}}"
    },
    "creado_en": "<fecha y hora>",
    "creado_por": "1",
    "estado": "CANCELADO",
    "finalizado_en": null,
    "id": "<id>",
    "items": [
      {
        "cantidad_comprometida": "0.00",
        "cantidad_reservada": "4.00",
        "tipo_recurso": {
          "codigo": "PARAMEDICO",
          "nombre": "Paramédico"
        }
      }
    ],
    "oferta_referencia": "OF-202-{{corrida}}",
    "ong": {
      "cuit": "{{ong_cuit}}",
      "id": "<id>",
      "razon_social": "Rescatistas de Prueba (Postman I-3.4)"
    },
    "vencido_en": null
  },
  {
    "cancelado_en": null,
    "confirmado_en": "<fecha y hora>",
    "convocatoria": {
      "emergencia_referencia": "EMG-1-{{corrida}}",
      "fecha_cierre": "<fecha y hora>",
      "fecha_limite_adjudicacion": "<fecha y hora>",
      "referencia": "CONV-1-{{corrida}}"
    },
    "creado_en": "<fecha y hora>",
    "creado_por": "1",
    "estado": "COMPROMETIDO",
    "finalizado_en": null,
    "id": "<id>",
    "items": [
      {
        "cantidad_comprometida": "5.00",
        "cantidad_reservada": "6.00",
        "tipo_recurso": {
          "codigo": "PARAMEDICO",
          "nombre": "Paramédico"
        }
      },
      {
        "cantidad_comprometida": "0.00",
        "cantidad_reservada": "50.00",
        "tipo_recurso": {
          "codigo": "FRAZADA",
          "nombre": "Frazada"
        }
      }
    ],
    "oferta_referencia": "OF-101-{{corrida}}",
    "ong": {
      "cuit": "{{ong_cuit}}",
      "id": "<id>",
      "razon_social": "Rescatistas de Prueba (Postman I-3.4)"
    },
    "vencido_en": null
  }
]
```

### 7.6 Detalle con el token del auditor

- **Pedido:** `GET {{base_url}}/compromisos/{{compromiso_101}}`
- **Token (pestaña Authorization):** `{{token_auditor}}` (AUDITOR)
- **Qué hace el endpoint:** Detalle de una reserva o compromiso.

**Respuesta esperada: `200 OK`**

```json
{
  "cancelado_en": null,
  "confirmado_en": "<fecha y hora>",
  "convocatoria": {
    "emergencia_referencia": "EMG-1-{{corrida}}",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "CONV-1-{{corrida}}"
  },
  "creado_en": "<fecha y hora>",
  "creado_por": "1",
  "estado": "COMPROMETIDO",
  "finalizado_en": null,
  "id": "<id>",
  "items": [
    {
      "cantidad_comprometida": "5.00",
      "cantidad_reservada": "6.00",
      "tipo_recurso": {
        "codigo": "PARAMEDICO",
        "nombre": "Paramédico"
      }
    },
    {
      "cantidad_comprometida": "0.00",
      "cantidad_reservada": "50.00",
      "tipo_recurso": {
        "codigo": "FRAZADA",
        "nombre": "Frazada"
      }
    }
  ],
  "oferta_referencia": "OF-101-{{corrida}}",
  "ong": {
    "cuit": "{{ong_cuit}}",
    "id": "<id>",
    "razon_social": "Rescatistas de Prueba (Postman I-3.4)"
  },
  "vencido_en": null
}
```

### 7.7 Un estado que no existe

- **Pedido:** `GET {{base_url}}/compromisos?estado=NO_EXISTE`
- **Token (pestaña Authorization):** `{{token_auditor}}` (AUDITOR)
- **Qué hace el endpoint:** Lista reservas y compromisos. Filtros: `emergencia`, `convocatoria`, `ong_cuit`, `estado` y `oferta_referencia`.

**Respuesta esperada: `422 UNPROCESSABLE ENTITY`**

```json
{
  "codigo": "VALIDACION",
  "detalles": {
    "query": {
      "estado": [
        "Must be one of: RESERVADO, COMPROMETIDO, FINALIZADO, CANCELADO, VENCIDO."
      ]
    }
  },
  "mensaje": "Hay campos con errores."
}
```


## 8. Seguridad

### 8.1 Reservar sin token

- **Pedido:** `POST {{base_url}}/compromisos`
- **Token (pestaña Authorization):** ninguno (*No Auth*)
- **Qué hace el endpoint:** **Bloqueo al ofertar.** La webapp lo llama cuando la ONG presenta la oferta. Bloquea las filas del inventario con `SELECT … FOR UPDATE`, valida la disponibilidad y la descuenta, todo en una transacción: si un ítem no alcanza, no se reserva nada. Es idempotente por oferta + ONG.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "oferta_referencia": "OF-801-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "convocatoria": {
    "referencia": "CONV-8-{{corrida}}",
    "emergencia_referencia": "EMG-8-{{corrida}}",
    "fecha_cierre": "{{cierre_futuro}}",
    "fecha_limite_adjudicacion": "{{limite_futuro}}"
  },
  "items": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 1
    }
  ]
}
```

**Respuesta esperada: `401 UNAUTHORIZED`**

```json
{
  "codigo": "NO_AUTENTICADO",
  "detalles": {},
  "mensaje": "Falta el token de acceso (Authorization: Bearer ...)."
}
```

### 8.2 Reservar con un token inválido

- **Pedido:** `POST {{base_url}}/compromisos`
- **Token (pestaña Authorization):** un token inválido (`no-es-un-token`)
- **Qué hace el endpoint:** **Bloqueo al ofertar.** La webapp lo llama cuando la ONG presenta la oferta. Bloquea las filas del inventario con `SELECT … FOR UPDATE`, valida la disponibilidad y la descuenta, todo en una transacción: si un ítem no alcanza, no se reserva nada. Es idempotente por oferta + ONG.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "oferta_referencia": "OF-801-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "convocatoria": {
    "referencia": "CONV-8-{{corrida}}",
    "emergencia_referencia": "EMG-8-{{corrida}}",
    "fecha_cierre": "{{cierre_futuro}}",
    "fecha_limite_adjudicacion": "{{limite_futuro}}"
  },
  "items": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 1
    }
  ]
}
```

**Respuesta esperada: `401 UNAUTHORIZED`**

```json
{
  "codigo": "NO_AUTENTICADO",
  "detalles": {},
  "mensaje": "El token de acceso no es válido."
}
```

### 8.3 Bonita no puede reservar

- **Pedido:** `POST {{base_url}}/compromisos`
- **Token (pestaña Authorization):** `{{token_bonita}}` (SISTEMA_BONITA)
- **Qué hace el endpoint:** **Bloqueo al ofertar.** La webapp lo llama cuando la ONG presenta la oferta. Bloquea las filas del inventario con `SELECT … FOR UPDATE`, valida la disponibilidad y la descuenta, todo en una transacción: si un ítem no alcanza, no se reserva nada. Es idempotente por oferta + ONG.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "oferta_referencia": "OF-801-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "convocatoria": {
    "referencia": "CONV-8-{{corrida}}",
    "emergencia_referencia": "EMG-8-{{corrida}}",
    "fecha_cierre": "{{cierre_futuro}}",
    "fecha_limite_adjudicacion": "{{limite_futuro}}"
  },
  "items": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 1
    }
  ]
}
```

**Respuesta esperada: `403 FORBIDDEN`**

```json
{
  "codigo": "PROHIBIDO",
  "detalles": {},
  "mensaje": "El rol del token no permite esta operación."
}
```

### 8.4 El auditor no puede reservar

- **Pedido:** `POST {{base_url}}/compromisos`
- **Token (pestaña Authorization):** `{{token_auditor}}` (AUDITOR)
- **Qué hace el endpoint:** **Bloqueo al ofertar.** La webapp lo llama cuando la ONG presenta la oferta. Bloquea las filas del inventario con `SELECT … FOR UPDATE`, valida la disponibilidad y la descuenta, todo en una transacción: si un ítem no alcanza, no se reserva nada. Es idempotente por oferta + ONG.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "oferta_referencia": "OF-801-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "convocatoria": {
    "referencia": "CONV-8-{{corrida}}",
    "emergencia_referencia": "EMG-8-{{corrida}}",
    "fecha_cierre": "{{cierre_futuro}}",
    "fecha_limite_adjudicacion": "{{limite_futuro}}"
  },
  "items": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 1
    }
  ]
}
```

**Respuesta esperada: `403 FORBIDDEN`**

```json
{
  "codigo": "PROHIBIDO",
  "detalles": {},
  "mensaje": "El rol del token no permite esta operación."
}
```

### 8.5 Consultar sin token

- **Pedido:** `GET {{base_url}}/compromisos`
- **Token (pestaña Authorization):** ninguno (*No Auth*)
- **Qué hace el endpoint:** Lista reservas y compromisos. Filtros: `emergencia`, `convocatoria`, `ong_cuit`, `estado` y `oferta_referencia`.

**Respuesta esperada: `401 UNAUTHORIZED`**

```json
{
  "codigo": "NO_AUTENTICADO",
  "detalles": {},
  "mensaje": "Falta el token de acceso (Authorization: Bearer ...)."
}
```

### 8.6 Login de la ONG de prueba

- **Pedido:** `POST {{base_url}}/login`
- **Token (pestaña Authorization):** ninguno (*No Auth*)
- **Qué hace el endpoint:** Inicio de sesión (punto I-3.1). Devuelve un JWT con el rol de la cuenta en el claim `rol`. No pide token.
- **Qué prueba este caso:** La ONG entra con su email. Guarda el token en `token_ong`.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "usuario": "{{ong_email}}",
  "password": "{{password_ong}}"
}
```

**Respuesta esperada: `200 OK`**

```json
{
  "access_token": "<token>",
  "expira_en_segundos": 28800,
  "rol": "ONG",
  "token_type": "Bearer"
}
```

### 8.7 La ONG no puede reservar con su propio token

- **Pedido:** `POST {{base_url}}/compromisos`
- **Token (pestaña Authorization):** `{{token_ong}}` (ONG)
- **Qué hace el endpoint:** **Bloqueo al ofertar.** La webapp lo llama cuando la ONG presenta la oferta. Bloquea las filas del inventario con `SELECT … FOR UPDATE`, valida la disponibilidad y la descuenta, todo en una transacción: si un ítem no alcanza, no se reserva nada. Es idempotente por oferta + ONG.
- **Qué prueba este caso:** Las reservas las pide la webapp en nombre de la ONG, no la ONG directamente.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "oferta_referencia": "OF-801-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "convocatoria": {
    "referencia": "CONV-8-{{corrida}}",
    "emergencia_referencia": "EMG-8-{{corrida}}",
    "fecha_cierre": "{{cierre_futuro}}",
    "fecha_limite_adjudicacion": "{{limite_futuro}}"
  },
  "items": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 1
    }
  ]
}
```

**Respuesta esperada: `403 FORBIDDEN`**

```json
{
  "codigo": "PROHIBIDO",
  "detalles": {},
  "mensaje": "El rol del token no permite esta operación."
}
```


## 9. Estado final

### 9.1 Inventario final de la ONG de prueba

- **Pedido:** `GET {{base_url}}/ongs/{{ong_id}}/recursos`
- **Token (pestaña Authorization):** ninguno (*No Auth*)
- **Qué hace el endpoint:** Inventario de una ONG por categoría (punto I-3.2): total, bloqueado, comprometido y disponible. Sirve para ver el efecto de cada operación. No pide token.
- **Qué prueba este caso:** 5 paramédicos y 1 rescatista comprometidos; 10 frazadas reservadas (oferta 505). Nunca se reservó más de lo que había.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cantidad_bloqueada": "10.00",
    "cantidad_comprometida": "0.00",
    "cantidad_disponible": "240.00",
    "cantidad_total": "250.00",
    "tipo_recurso": {
      "categoria": "MATERIAL",
      "codigo": "FRAZADA",
      "id": 12,
      "nombre": "Frazada",
      "reutilizable": true,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "UNIDAD",
        "id": 6,
        "nombre": "Unidades"
      }
    }
  },
  {
    "cantidad_bloqueada": "0.00",
    "cantidad_comprometida": "5.00",
    "cantidad_disponible": "5.00",
    "cantidad_total": "10.00",
    "tipo_recurso": {
      "categoria": "PERSONAL",
      "codigo": "PARAMEDICO",
      "id": 1,
      "nombre": "Paramédico",
      "reutilizable": true,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "PERSONA",
        "id": 1,
        "nombre": "Personas"
      }
    }
  },
  {
    "cantidad_bloqueada": "0.00",
    "cantidad_comprometida": "1.00",
    "cantidad_disponible": "14.00",
    "cantidad_total": "15.00",
    "tipo_recurso": {
      "categoria": "PERSONAL",
      "codigo": "RESCATISTA",
      "id": 5,
      "nombre": "Rescatista",
      "reutilizable": true,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "PERSONA",
        "id": 1,
        "nombre": "Personas"
      }
    }
  }
]
```

