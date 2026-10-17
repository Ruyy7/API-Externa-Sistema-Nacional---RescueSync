# Casos de prueba de I-3.4 en Postman

Bloqueo y compromiso de recursos con locking en PostgreSQL. Todos los casos se generaron ejecutándolos contra la API: las respuestas de abajo son las reales. Las fechas y horas cambian en cada corrida y se muestran como `<fecha y hora>`.

Los recursos se bloquean en dos momentos:

| Momento | Endpoint | Inventario de la ONG |
|---|---|---|
| La ONG presenta la oferta | `POST /api/v1/compromisos` | `cantidad_bloqueada += n` |
| El municipio adjudica la oferta | `POST /api/v1/compromisos/{id}/confirmacion` | lo adjudicado pasa de bloqueado a comprometido; la diferencia se libera |

## Preparación

**1. Levantar la API y dejar los datos de demostración limpios.** En una terminal, en la carpeta del repo:

```bash
docker compose up -d
docker compose exec db psql -U sistema_nacional -d sistema_nacional -c "TRUNCATE compromiso_item, compromiso, convocatoria RESTART IDENTITY CASCADE;"
docker compose exec api flask seed
```

Hay que repetir los dos últimos comandos cada vez que se quiera correr la colección desde cero: los casos dependen del orden.

**2. Generar los tres tokens.** Cada comando imprime un token largo, válido por 8 horas:

```bash
docker compose exec api flask token-servicio SISTEMA_WEBAPP
docker compose exec api flask token-servicio SISTEMA_BONITA
docker compose exec api flask token-servicio AUDITOR
```

| Token | Representa a | Puede |
|---|---|---|
| `SISTEMA_WEBAPP` | La webapp RescueSync | Verificar, reservar, ajustar, cancelar, adjudicar y cambiar fechas de convocatorias |
| `SISTEMA_BONITA` | El proceso de Bonita | Verificar, adjudicar y cambiar fechas de convocatorias |
| `AUDITOR` | El perfil Auditor / Directivo | Solo consultar |

**3. Importar la colección en Postman.** *Import* (arriba a la izquierda) → elegir `docs/postman/RescueSync-I-3.4.postman_collection.json` → *Import*.

**4. Cargar los tokens.** Clic en la colección *RescueSync · Sistema Nacional · I-3.4…* → pestaña **Variables** → pegar cada token en la columna *Current value* (o *Value*, según la versión) de `token_webapp`, `token_bonita` y `token_auditor` → guardar con **Ctrl+S**. `base_url` ya viene cargada con `http://localhost:5001/api/v1`.

No hace falta tocar la pestaña *Authorization* de cada pedido: ya está configurada como *Bearer Token* con la variable que corresponde. Las fechas (`{{cierre_futuro}}`, `{{limite_futuro}}`, `{{cierre_pasado}}` y `{{limite_pasado}}`) se calculan solas antes de cada pedido, relativas al día en que se prueba.

**5. Ejecutar.**
- **Uno por uno:** abrir cada pedido en orden y apretar **Send**. Abajo, la pestaña **Test Results** muestra en verde cada valor esperado que se cumplió.
- **Todos juntos:** clic derecho en la colección → **Run collection** → **Run**. El resumen muestra cuántas pruebas pasaron.

Los ids de los compromisos se guardan solos en variables (`compromiso_101`, `compromiso_202`…) cuando se crean, y los pedidos siguientes los usan.

**Inventario de partida** de Rescatistas del Río (CUIT `30-11111111-1`), como bloqueada / comprometida / disponible:
- `PARAMEDICO`: 2 / 0 / 10
- `RESCATISTA`: 3 / 2 / 15
- `FRAZADA`: 20 / 30 / 250
- `RACION_ALIMENTO`: no está inscripta

**Concurrencia.** No se puede probar con Postman, porque hacen falta pedidos realmente simultáneos. Se prueba con los tests automáticos: `docker compose run --rm api pytest tests/test_concurrencia.py -v` (5 pruebas, incluida una donde dos reservas compiten por la misma fila).


## 0. Preparación

### 0.1 Obtener el id de Rescatistas del Río

- **Pedido:** `GET {{base_url}}/ongs?habilitada=true`
- **Token (pestaña Authorization):** ninguno (*No Auth*)
- **Qué hace el endpoint:** Lista las ONGs registradas (punto I-3.2). Con `habilitada=true` devuelve solo las habilitadas. Lo usamos para obtener el id de Rescatistas del Río.
- **Qué prueba este caso:** Guarda en la variable `ong_rio_id` el id de la ONG con CUIT 30-11111111-1.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "actualizado_en": "<fecha y hora>",
    "creado_en": "<fecha y hora>",
    "cuit": "30-22222222-2",
    "email_contacto": null,
    "estado": "HABILITADA",
    "habilitada": true,
    "id": 2,
    "razon_social": "Alimentos Solidarios",
    "telefono": null
  },
  {
    "actualizado_en": "<fecha y hora>",
    "creado_en": "<fecha y hora>",
    "cuit": "30-11111111-1",
    "email_contacto": null,
    "estado": "HABILITADA",
    "habilitada": true,
    "id": 1,
    "razon_social": "Rescatistas del Río",
    "telefono": null
  }
]
```

### 0.2 Inventario inicial de Rescatistas del Río

- **Pedido:** `GET {{base_url}}/ongs/{{ong_rio_id}}/recursos`
- **Token (pestaña Authorization):** ninguno (*No Auth*)
- **Qué hace el endpoint:** Inventario de una ONG por categoría (punto I-3.2): total, bloqueado, comprometido y disponible. Sirve para ver el efecto de cada operación. No pide token.
- **Qué prueba este caso:** Punto de partida: 10 paramédicos, 15 rescatistas y 250 frazadas disponibles. No está inscripta en RACION_ALIMENTO.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cantidad_bloqueada": "20.00",
    "cantidad_comprometida": "30.00",
    "cantidad_disponible": "250.00",
    "cantidad_total": "300.00",
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
    "cantidad_bloqueada": "2.00",
    "cantidad_comprometida": "0.00",
    "cantidad_disponible": "10.00",
    "cantidad_total": "12.00",
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
    "cantidad_bloqueada": "3.00",
    "cantidad_comprometida": "2.00",
    "cantidad_disponible": "15.00",
    "cantidad_total": "20.00",
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
  "ong_cuit": "30-11111111-1",
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
  "ong_cuit": "30-11111111-1",
  "ong_habilitada": true,
  "se_puede_reservar": false
}
```

### 1.2 Verificar con una ONG pendiente de habilitación

- **Pedido:** `POST {{base_url}}/compromisos/verificacion`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** Valida las restricciones de un pedido **sin bloquear nada**: ONG registrada y habilitada, categorías del catálogo, cantidades enteras cuando la unidad no admite decimales y disponibilidad por ítem (`DISPONIBLE`, `PARCIAL` o `SIN_DISPONIBILIDAD`).
- **Qué prueba este caso:** La verificación informa que la ONG no está habilitada (no es un error).

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
  "ong_cuit": "30-11111111-1",
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

- **Pedido:** `GET {{base_url}}/ongs/{{ong_rio_id}}/recursos`
- **Token (pestaña Authorization):** ninguno (*No Auth*)
- **Qué hace el endpoint:** Inventario de una ONG por categoría (punto I-3.2): total, bloqueado, comprometido y disponible. Sirve para ver el efecto de cada operación. No pide token.
- **Qué prueba este caso:** La verificación no bloquea: el inventario sigue igual.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cantidad_bloqueada": "20.00",
    "cantidad_comprometida": "30.00",
    "cantidad_disponible": "250.00",
    "cantidad_total": "300.00",
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
    "cantidad_bloqueada": "2.00",
    "cantidad_comprometida": "0.00",
    "cantidad_disponible": "10.00",
    "cantidad_total": "12.00",
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
    "cantidad_bloqueada": "3.00",
    "cantidad_comprometida": "2.00",
    "cantidad_disponible": "15.00",
    "cantidad_total": "20.00",
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
  "oferta_referencia": "101",
  "ong_cuit": "30-11111111-1",
  "convocatoria": {
    "referencia": "conv-1",
    "emergencia_referencia": "emg-1",
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
    "emergencia_referencia": "emg-1",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "conv-1"
  },
  "creado_en": "<fecha y hora>",
  "creado_por": "sistema_webapp",
  "estado": "RESERVADO",
  "finalizado_en": null,
  "id": 1,
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
  "oferta_referencia": "101",
  "ong": {
    "cuit": "30-11111111-1",
    "id": 1,
    "razon_social": "Rescatistas del Río"
  },
  "vencido_en": null
}
```

### 2.2 Inventario después de reservar

- **Pedido:** `GET {{base_url}}/ongs/{{ong_rio_id}}/recursos`
- **Token (pestaña Authorization):** ninguno (*No Auth*)
- **Qué hace el endpoint:** Inventario de una ONG por categoría (punto I-3.2): total, bloqueado, comprometido y disponible. Sirve para ver el efecto de cada operación. No pide token.
- **Qué prueba este caso:** Los paramédicos bloqueados pasan de 2 a 10: quedan 2 disponibles.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cantidad_bloqueada": "20.00",
    "cantidad_comprometida": "30.00",
    "cantidad_disponible": "250.00",
    "cantidad_total": "300.00",
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
    "cantidad_bloqueada": "10.00",
    "cantidad_comprometida": "0.00",
    "cantidad_disponible": "2.00",
    "cantidad_total": "12.00",
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
    "cantidad_bloqueada": "7.00",
    "cantidad_comprometida": "2.00",
    "cantidad_disponible": "11.00",
    "cantidad_total": "20.00",
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
  "oferta_referencia": "101",
  "ong_cuit": "30-11111111-1",
  "convocatoria": {
    "referencia": "conv-1",
    "emergencia_referencia": "emg-1",
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
    "emergencia_referencia": "emg-1",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "conv-1"
  },
  "creado_en": "<fecha y hora>",
  "creado_por": "sistema_webapp",
  "estado": "RESERVADO",
  "finalizado_en": null,
  "id": 1,
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
  "oferta_referencia": "101",
  "ong": {
    "cuit": "30-11111111-1",
    "id": 1,
    "razon_social": "Rescatistas del Río"
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
  "oferta_referencia": "101",
  "ong_cuit": "30-11111111-1",
  "convocatoria": {
    "referencia": "conv-1",
    "emergencia_referencia": "emg-1",
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
  "oferta_referencia": "202",
  "ong_cuit": "30-11111111-1",
  "convocatoria": {
    "referencia": "conv-2",
    "emergencia_referencia": "emg-2",
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

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "oferta_referencia": "301",
  "ong_cuit": "30-33333333-3",
  "convocatoria": {
    "referencia": "conv-9",
    "emergencia_referencia": "emg-9",
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
  "oferta_referencia": "302",
  "ong_cuit": "30-99999999-9",
  "convocatoria": {
    "referencia": "conv-9",
    "emergencia_referencia": "emg-9",
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
  "oferta_referencia": "303",
  "ong_cuit": "30-11111111-1",
  "convocatoria": {
    "referencia": "conv-9",
    "emergencia_referencia": "emg-9",
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
  "oferta_referencia": "304",
  "ong_cuit": "30-11111111-1",
  "convocatoria": {
    "referencia": "conv-8",
    "emergencia_referencia": "emg-8",
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
  "oferta_referencia": "305",
  "ong_cuit": "30-11111111-1",
  "convocatoria": {
    "referencia": "conv-9",
    "emergencia_referencia": "emg-9",
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
  "oferta_referencia": "306",
  "ong_cuit": "30-11111111-1",
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
  "oferta_referencia": "307",
  "ong_cuit": "30-11111111-1",
  "convocatoria": {
    "referencia": "conv-9",
    "emergencia_referencia": "emg-9",
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
    "emergencia_referencia": "emg-1",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "conv-1"
  },
  "creado_en": "<fecha y hora>",
  "creado_por": "sistema_webapp",
  "estado": "RESERVADO",
  "finalizado_en": null,
  "id": 1,
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
  "oferta_referencia": "101",
  "ong": {
    "cuit": "30-11111111-1",
    "id": 1,
    "razon_social": "Rescatistas del Río"
  },
  "vencido_en": null
}
```

### 3.2 Inventario después de modificar

- **Pedido:** `GET {{base_url}}/ongs/{{ong_rio_id}}/recursos`
- **Token (pestaña Authorization):** ninguno (*No Auth*)
- **Qué hace el endpoint:** Inventario de una ONG por categoría (punto I-3.2): total, bloqueado, comprometido y disponible. Sirve para ver el efecto de cada operación. No pide token.
- **Qué prueba este caso:** Se liberaron 2 paramédicos y los 4 rescatistas; se bloquearon 50 frazadas.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cantidad_bloqueada": "70.00",
    "cantidad_comprometida": "30.00",
    "cantidad_disponible": "200.00",
    "cantidad_total": "300.00",
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
    "cantidad_disponible": "4.00",
    "cantidad_total": "12.00",
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
    "cantidad_bloqueada": "3.00",
    "cantidad_comprometida": "2.00",
    "cantidad_disponible": "15.00",
    "cantidad_total": "20.00",
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
  "oferta_referencia": "202",
  "ong_cuit": "30-11111111-1",
  "convocatoria": {
    "referencia": "conv-2",
    "emergencia_referencia": "emg-2",
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
    "emergencia_referencia": "emg-2",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "conv-2"
  },
  "creado_en": "<fecha y hora>",
  "creado_por": "sistema_webapp",
  "estado": "RESERVADO",
  "finalizado_en": null,
  "id": 2,
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
  "oferta_referencia": "202",
  "ong": {
    "cuit": "30-11111111-1",
    "id": 1,
    "razon_social": "Rescatistas del Río"
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
    "emergencia_referencia": "emg-2",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "conv-2"
  },
  "creado_en": "<fecha y hora>",
  "creado_por": "sistema_webapp",
  "estado": "CANCELADO",
  "finalizado_en": null,
  "id": 2,
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
  "oferta_referencia": "202",
  "ong": {
    "cuit": "30-11111111-1",
    "id": 1,
    "razon_social": "Rescatistas del Río"
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
    "emergencia_referencia": "emg-2",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "conv-2"
  },
  "creado_en": "<fecha y hora>",
  "creado_por": "sistema_webapp",
  "estado": "CANCELADO",
  "finalizado_en": null,
  "id": 2,
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
  "oferta_referencia": "202",
  "ong": {
    "cuit": "30-11111111-1",
    "id": 1,
    "razon_social": "Rescatistas del Río"
  },
  "vencido_en": null
}
```

### 3.7 Inventario después de retirar la oferta 202

- **Pedido:** `GET {{base_url}}/ongs/{{ong_rio_id}}/recursos`
- **Token (pestaña Authorization):** ninguno (*No Auth*)
- **Qué hace el endpoint:** Inventario de una ONG por categoría (punto I-3.2): total, bloqueado, comprometido y disponible. Sirve para ver el efecto de cada operación. No pide token.
- **Qué prueba este caso:** Los 4 paramédicos de la oferta 202 volvieron a estar disponibles.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cantidad_bloqueada": "70.00",
    "cantidad_comprometida": "30.00",
    "cantidad_disponible": "200.00",
    "cantidad_total": "300.00",
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
    "cantidad_disponible": "4.00",
    "cantidad_total": "12.00",
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
    "cantidad_bloqueada": "3.00",
    "cantidad_comprometida": "2.00",
    "cantidad_disponible": "15.00",
    "cantidad_total": "20.00",
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

### 4.1 Ofertas de la convocatoria conv-1 (lo que ve quien adjudica)

- **Pedido:** `GET {{base_url}}/compromisos?convocatoria=conv-1`
- **Token (pestaña Authorization):** `{{token_bonita}}` (SISTEMA_BONITA)
- **Qué hace el endpoint:** Lista reservas y compromisos. Filtros: `emergencia`, `convocatoria`, `ong_cuit`, `estado` y `oferta_referencia`.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cancelado_en": null,
    "confirmado_en": null,
    "convocatoria": {
      "emergencia_referencia": "emg-1",
      "fecha_cierre": "<fecha y hora>",
      "fecha_limite_adjudicacion": "<fecha y hora>",
      "referencia": "conv-1"
    },
    "creado_en": "<fecha y hora>",
    "creado_por": "sistema_webapp",
    "estado": "RESERVADO",
    "finalizado_en": null,
    "id": 1,
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
    "oferta_referencia": "101",
    "ong": {
      "cuit": "30-11111111-1",
      "id": 1,
      "razon_social": "Rescatistas del Río"
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
    "emergencia_referencia": "emg-1",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "conv-1"
  },
  "creado_en": "<fecha y hora>",
  "creado_por": "sistema_webapp",
  "estado": "COMPROMETIDO",
  "finalizado_en": null,
  "id": 1,
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
  "oferta_referencia": "101",
  "ong": {
    "cuit": "30-11111111-1",
    "id": 1,
    "razon_social": "Rescatistas del Río"
  },
  "vencido_en": null
}
```

### 4.7 Inventario después de adjudicar

- **Pedido:** `GET {{base_url}}/ongs/{{ong_rio_id}}/recursos`
- **Token (pestaña Authorization):** ninguno (*No Auth*)
- **Qué hace el endpoint:** Inventario de una ONG por categoría (punto I-3.2): total, bloqueado, comprometido y disponible. Sirve para ver el efecto de cada operación. No pide token.
- **Qué prueba este caso:** 5 paramédicos pasan de bloqueados a comprometidos y el sexto se libera. Las 50 frazadas no adjudicadas vuelven a estar disponibles.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cantidad_bloqueada": "20.00",
    "cantidad_comprometida": "30.00",
    "cantidad_disponible": "250.00",
    "cantidad_total": "300.00",
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
    "cantidad_bloqueada": "2.00",
    "cantidad_comprometida": "5.00",
    "cantidad_disponible": "5.00",
    "cantidad_total": "12.00",
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
    "cantidad_bloqueada": "3.00",
    "cantidad_comprometida": "2.00",
    "cantidad_disponible": "15.00",
    "cantidad_total": "20.00",
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
    "emergencia_referencia": "emg-1",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "conv-1"
  },
  "creado_en": "<fecha y hora>",
  "creado_por": "sistema_webapp",
  "estado": "COMPROMETIDO",
  "finalizado_en": null,
  "id": 1,
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
  "oferta_referencia": "101",
  "ong": {
    "cuit": "30-11111111-1",
    "id": 1,
    "razon_social": "Rescatistas del Río"
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

### 5.1 Oferta 404: reservar 1 rescatista en conv-4

- **Pedido:** `POST {{base_url}}/compromisos`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** **Bloqueo al ofertar.** La webapp lo llama cuando la ONG presenta la oferta. Bloquea las filas del inventario con `SELECT … FOR UPDATE`, valida la disponibilidad y la descuenta, todo en una transacción: si un ítem no alcanza, no se reserva nada. Es idempotente por oferta + ONG.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "oferta_referencia": "404",
  "ong_cuit": "30-11111111-1",
  "convocatoria": {
    "referencia": "conv-4",
    "emergencia_referencia": "emg-4",
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
    "emergencia_referencia": "emg-4",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "conv-4"
  },
  "creado_en": "<fecha y hora>",
  "creado_por": "sistema_webapp",
  "estado": "RESERVADO",
  "finalizado_en": null,
  "id": 3,
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
  "oferta_referencia": "404",
  "ong": {
    "cuit": "30-11111111-1",
    "id": 1,
    "razon_social": "Rescatistas del Río"
  },
  "vencido_en": null
}
```

### 5.2 Cierra la ventana de ofertas de conv-4 (la de adjudicación sigue abierta)

- **Pedido:** `PUT {{base_url}}/convocatorias/conv-4`
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
  "emergencia_referencia": "emg-4",
  "fecha_cierre": "<fecha y hora>",
  "fecha_limite_adjudicacion": "<fecha y hora>",
  "referencia": "conv-4"
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
    "emergencia_referencia": "emg-4",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "conv-4"
  },
  "creado_en": "<fecha y hora>",
  "creado_por": "sistema_webapp",
  "estado": "COMPROMETIDO",
  "finalizado_en": null,
  "id": 3,
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
  "oferta_referencia": "404",
  "ong": {
    "cuit": "30-11111111-1",
    "id": 1,
    "razon_social": "Rescatistas del Río"
  },
  "vencido_en": null
}
```

### 5.5 Oferta 303: reservar 2 rescatistas en conv-3

- **Pedido:** `POST {{base_url}}/compromisos`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** **Bloqueo al ofertar.** La webapp lo llama cuando la ONG presenta la oferta. Bloquea las filas del inventario con `SELECT … FOR UPDATE`, valida la disponibilidad y la descuenta, todo en una transacción: si un ítem no alcanza, no se reserva nada. Es idempotente por oferta + ONG.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "oferta_referencia": "303",
  "ong_cuit": "30-11111111-1",
  "convocatoria": {
    "referencia": "conv-3",
    "emergencia_referencia": "emg-3",
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
    "emergencia_referencia": "emg-3",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "conv-3"
  },
  "creado_en": "<fecha y hora>",
  "creado_por": "sistema_webapp",
  "estado": "RESERVADO",
  "finalizado_en": null,
  "id": 4,
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
  "oferta_referencia": "303",
  "ong": {
    "cuit": "30-11111111-1",
    "id": 1,
    "razon_social": "Rescatistas del Río"
  },
  "vencido_en": null
}
```

### 5.6 Termina también la ventana de adjudicación de conv-3

- **Pedido:** `PUT {{base_url}}/convocatorias/conv-3`
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
  "emergencia_referencia": "emg-3",
  "fecha_cierre": "<fecha y hora>",
  "fecha_limite_adjudicacion": "<fecha y hora>",
  "referencia": "conv-3"
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
    "emergencia_referencia": "emg-3",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "conv-3"
  },
  "creado_en": "<fecha y hora>",
  "creado_por": "sistema_webapp",
  "estado": "VENCIDO",
  "finalizado_en": null,
  "id": 4,
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
  "oferta_referencia": "303",
  "ong": {
    "cuit": "30-11111111-1",
    "id": 1,
    "razon_social": "Rescatistas del Río"
  },
  "vencido_en": "<fecha y hora>"
}
```

### 5.9 Inventario después del vencimiento

- **Pedido:** `GET {{base_url}}/ongs/{{ong_rio_id}}/recursos`
- **Token (pestaña Authorization):** ninguno (*No Auth*)
- **Qué hace el endpoint:** Inventario de una ONG por categoría (punto I-3.2): total, bloqueado, comprometido y disponible. Sirve para ver el efecto de cada operación. No pide token.
- **Qué prueba este caso:** Rescatistas: 1 comprometido por la oferta 404 (más los 2 del seed) y los 2 de la oferta 303 liberados.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cantidad_bloqueada": "20.00",
    "cantidad_comprometida": "30.00",
    "cantidad_disponible": "250.00",
    "cantidad_total": "300.00",
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
    "cantidad_bloqueada": "2.00",
    "cantidad_comprometida": "5.00",
    "cantidad_disponible": "5.00",
    "cantidad_total": "12.00",
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
    "cantidad_bloqueada": "3.00",
    "cantidad_comprometida": "3.00",
    "cantidad_disponible": "14.00",
    "cantidad_total": "20.00",
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

- **Pedido:** `PUT {{base_url}}/convocatorias/conv-3`
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

### 5.11 Consultar la convocatoria conv-4

- **Pedido:** `GET {{base_url}}/convocatorias/conv-4`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** Fechas de una convocatoria. La convocatoria se registra sola con la primera reserva que la nombra.

**Respuesta esperada: `200 OK`**

```json
{
  "emergencia_referencia": "emg-4",
  "fecha_cierre": "<fecha y hora>",
  "fecha_limite_adjudicacion": "<fecha y hora>",
  "referencia": "conv-4"
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

### 6.1 Oferta 505: reservar 10 frazadas en conv-5

- **Pedido:** `POST {{base_url}}/compromisos`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** **Bloqueo al ofertar.** La webapp lo llama cuando la ONG presenta la oferta. Bloquea las filas del inventario con `SELECT … FOR UPDATE`, valida la disponibilidad y la descuenta, todo en una transacción: si un ítem no alcanza, no se reserva nada. Es idempotente por oferta + ONG.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "oferta_referencia": "505",
  "ong_cuit": "30-11111111-1",
  "convocatoria": {
    "referencia": "conv-5",
    "emergencia_referencia": "emg-5",
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
    "emergencia_referencia": "emg-5",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "conv-5"
  },
  "creado_en": "<fecha y hora>",
  "creado_por": "sistema_webapp",
  "estado": "RESERVADO",
  "finalizado_en": null,
  "id": 5,
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
  "oferta_referencia": "505",
  "ong": {
    "cuit": "30-11111111-1",
    "id": 1,
    "razon_social": "Rescatistas del Río"
  },
  "vencido_en": null
}
```

### 6.2 Reformular conv-5: sus reservas pasan a conv-5b

- **Pedido:** `POST {{base_url}}/convocatorias/conv-5/reformulacion`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** Reformular la convocatoria: sus reservas vigentes pasan a la convocatoria nueva, que hereda la emergencia.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "nueva": {
    "referencia": "conv-5b",
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
    "emergencia_referencia": "emg-5",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "conv-5b"
  }
}
```

### 6.3 La oferta 505 ahora pertenece a conv-5b

- **Pedido:** `GET {{base_url}}/compromisos/{{compromiso_505}}`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** Detalle de una reserva o compromiso.

**Respuesta esperada: `200 OK`**

```json
{
  "cancelado_en": null,
  "confirmado_en": null,
  "convocatoria": {
    "emergencia_referencia": "emg-5",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "conv-5b"
  },
  "creado_en": "<fecha y hora>",
  "creado_por": "sistema_webapp",
  "estado": "RESERVADO",
  "finalizado_en": null,
  "id": 5,
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
  "oferta_referencia": "505",
  "ong": {
    "cuit": "30-11111111-1",
    "id": 1,
    "razon_social": "Rescatistas del Río"
  },
  "vencido_en": null
}
```

### 6.4 Repetir la reformulación

- **Pedido:** `POST {{base_url}}/convocatorias/conv-5/reformulacion`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** Reformular la convocatoria: sus reservas vigentes pasan a la convocatoria nueva, que hereda la emergencia.
- **Qué prueba este caso:** Idempotencia: ya no queda nada por mover.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "nueva": {
    "referencia": "conv-5b",
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
    "emergencia_referencia": "emg-5",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "conv-5b"
  }
}
```

### 6.5 Reformular hacia la misma convocatoria

- **Pedido:** `POST {{base_url}}/convocatorias/conv-5b/reformulacion`
- **Token (pestaña Authorization):** `{{token_webapp}}` (SISTEMA_WEBAPP)
- **Qué hace el endpoint:** Reformular la convocatoria: sus reservas vigentes pasan a la convocatoria nueva, que hereda la emergencia.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "nueva": {
    "referencia": "conv-5b",
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

### 7.1 Compromisos de la emergencia emg-1

- **Pedido:** `GET {{base_url}}/compromisos?emergencia=emg-1`
- **Token (pestaña Authorization):** `{{token_auditor}}` (AUDITOR)
- **Qué hace el endpoint:** Lista reservas y compromisos. Filtros: `emergencia`, `convocatoria`, `ong_cuit`, `estado` y `oferta_referencia`.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cancelado_en": null,
    "confirmado_en": "<fecha y hora>",
    "convocatoria": {
      "emergencia_referencia": "emg-1",
      "fecha_cierre": "<fecha y hora>",
      "fecha_limite_adjudicacion": "<fecha y hora>",
      "referencia": "conv-1"
    },
    "creado_en": "<fecha y hora>",
    "creado_por": "sistema_webapp",
    "estado": "COMPROMETIDO",
    "finalizado_en": null,
    "id": 1,
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
    "oferta_referencia": "101",
    "ong": {
      "cuit": "30-11111111-1",
      "id": 1,
      "razon_social": "Rescatistas del Río"
    },
    "vencido_en": null
  }
]
```

### 7.2 Compromisos vencidos

- **Pedido:** `GET {{base_url}}/compromisos?estado=VENCIDO`
- **Token (pestaña Authorization):** `{{token_auditor}}` (AUDITOR)
- **Qué hace el endpoint:** Lista reservas y compromisos. Filtros: `emergencia`, `convocatoria`, `ong_cuit`, `estado` y `oferta_referencia`.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cancelado_en": null,
    "confirmado_en": null,
    "convocatoria": {
      "emergencia_referencia": "emg-3",
      "fecha_cierre": "<fecha y hora>",
      "fecha_limite_adjudicacion": "<fecha y hora>",
      "referencia": "conv-3"
    },
    "creado_en": "<fecha y hora>",
    "creado_por": "sistema_webapp",
    "estado": "VENCIDO",
    "finalizado_en": null,
    "id": 4,
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
    "oferta_referencia": "303",
    "ong": {
      "cuit": "30-11111111-1",
      "id": 1,
      "razon_social": "Rescatistas del Río"
    },
    "vencido_en": "<fecha y hora>"
  }
]
```

### 7.3 Compromisos cancelados

- **Pedido:** `GET {{base_url}}/compromisos?estado=CANCELADO`
- **Token (pestaña Authorization):** `{{token_auditor}}` (AUDITOR)
- **Qué hace el endpoint:** Lista reservas y compromisos. Filtros: `emergencia`, `convocatoria`, `ong_cuit`, `estado` y `oferta_referencia`.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cancelado_en": "<fecha y hora>",
    "confirmado_en": null,
    "convocatoria": {
      "emergencia_referencia": "emg-2",
      "fecha_cierre": "<fecha y hora>",
      "fecha_limite_adjudicacion": "<fecha y hora>",
      "referencia": "conv-2"
    },
    "creado_en": "<fecha y hora>",
    "creado_por": "sistema_webapp",
    "estado": "CANCELADO",
    "finalizado_en": null,
    "id": 2,
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
    "oferta_referencia": "202",
    "ong": {
      "cuit": "30-11111111-1",
      "id": 1,
      "razon_social": "Rescatistas del Río"
    },
    "vencido_en": null
  }
]
```

### 7.4 Compromisos de una oferta

- **Pedido:** `GET {{base_url}}/compromisos?oferta_referencia=101`
- **Token (pestaña Authorization):** `{{token_auditor}}` (AUDITOR)
- **Qué hace el endpoint:** Lista reservas y compromisos. Filtros: `emergencia`, `convocatoria`, `ong_cuit`, `estado` y `oferta_referencia`.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cancelado_en": null,
    "confirmado_en": "<fecha y hora>",
    "convocatoria": {
      "emergencia_referencia": "emg-1",
      "fecha_cierre": "<fecha y hora>",
      "fecha_limite_adjudicacion": "<fecha y hora>",
      "referencia": "conv-1"
    },
    "creado_en": "<fecha y hora>",
    "creado_por": "sistema_webapp",
    "estado": "COMPROMETIDO",
    "finalizado_en": null,
    "id": 1,
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
    "oferta_referencia": "101",
    "ong": {
      "cuit": "30-11111111-1",
      "id": 1,
      "razon_social": "Rescatistas del Río"
    },
    "vencido_en": null
  }
]
```

### 7.5 Todos los compromisos de la ONG

- **Pedido:** `GET {{base_url}}/compromisos?ong_cuit=30-11111111-1`
- **Token (pestaña Authorization):** `{{token_auditor}}` (AUDITOR)
- **Qué hace el endpoint:** Lista reservas y compromisos. Filtros: `emergencia`, `convocatoria`, `ong_cuit`, `estado` y `oferta_referencia`.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cancelado_en": null,
    "confirmado_en": null,
    "convocatoria": {
      "emergencia_referencia": "emg-5",
      "fecha_cierre": "<fecha y hora>",
      "fecha_limite_adjudicacion": "<fecha y hora>",
      "referencia": "conv-5b"
    },
    "creado_en": "<fecha y hora>",
    "creado_por": "sistema_webapp",
    "estado": "RESERVADO",
    "finalizado_en": null,
    "id": 5,
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
    "oferta_referencia": "505",
    "ong": {
      "cuit": "30-11111111-1",
      "id": 1,
      "razon_social": "Rescatistas del Río"
    },
    "vencido_en": null
  },
  {
    "cancelado_en": null,
    "confirmado_en": null,
    "convocatoria": {
      "emergencia_referencia": "emg-3",
      "fecha_cierre": "<fecha y hora>",
      "fecha_limite_adjudicacion": "<fecha y hora>",
      "referencia": "conv-3"
    },
    "creado_en": "<fecha y hora>",
    "creado_por": "sistema_webapp",
    "estado": "VENCIDO",
    "finalizado_en": null,
    "id": 4,
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
    "oferta_referencia": "303",
    "ong": {
      "cuit": "30-11111111-1",
      "id": 1,
      "razon_social": "Rescatistas del Río"
    },
    "vencido_en": "<fecha y hora>"
  },
  {
    "cancelado_en": null,
    "confirmado_en": "<fecha y hora>",
    "convocatoria": {
      "emergencia_referencia": "emg-4",
      "fecha_cierre": "<fecha y hora>",
      "fecha_limite_adjudicacion": "<fecha y hora>",
      "referencia": "conv-4"
    },
    "creado_en": "<fecha y hora>",
    "creado_por": "sistema_webapp",
    "estado": "COMPROMETIDO",
    "finalizado_en": null,
    "id": 3,
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
    "oferta_referencia": "404",
    "ong": {
      "cuit": "30-11111111-1",
      "id": 1,
      "razon_social": "Rescatistas del Río"
    },
    "vencido_en": null
  },
  {
    "cancelado_en": "<fecha y hora>",
    "confirmado_en": null,
    "convocatoria": {
      "emergencia_referencia": "emg-2",
      "fecha_cierre": "<fecha y hora>",
      "fecha_limite_adjudicacion": "<fecha y hora>",
      "referencia": "conv-2"
    },
    "creado_en": "<fecha y hora>",
    "creado_por": "sistema_webapp",
    "estado": "CANCELADO",
    "finalizado_en": null,
    "id": 2,
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
    "oferta_referencia": "202",
    "ong": {
      "cuit": "30-11111111-1",
      "id": 1,
      "razon_social": "Rescatistas del Río"
    },
    "vencido_en": null
  },
  {
    "cancelado_en": null,
    "confirmado_en": "<fecha y hora>",
    "convocatoria": {
      "emergencia_referencia": "emg-1",
      "fecha_cierre": "<fecha y hora>",
      "fecha_limite_adjudicacion": "<fecha y hora>",
      "referencia": "conv-1"
    },
    "creado_en": "<fecha y hora>",
    "creado_por": "sistema_webapp",
    "estado": "COMPROMETIDO",
    "finalizado_en": null,
    "id": 1,
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
    "oferta_referencia": "101",
    "ong": {
      "cuit": "30-11111111-1",
      "id": 1,
      "razon_social": "Rescatistas del Río"
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
    "emergencia_referencia": "emg-1",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "conv-1"
  },
  "creado_en": "<fecha y hora>",
  "creado_por": "sistema_webapp",
  "estado": "COMPROMETIDO",
  "finalizado_en": null,
  "id": 1,
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
  "oferta_referencia": "101",
  "ong": {
    "cuit": "30-11111111-1",
    "id": 1,
    "razon_social": "Rescatistas del Río"
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
  "oferta_referencia": "801",
  "ong_cuit": "30-11111111-1",
  "convocatoria": {
    "referencia": "conv-8",
    "emergencia_referencia": "emg-8",
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
  "oferta_referencia": "801",
  "ong_cuit": "30-11111111-1",
  "convocatoria": {
    "referencia": "conv-8",
    "emergencia_referencia": "emg-8",
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
  "oferta_referencia": "801",
  "ong_cuit": "30-11111111-1",
  "convocatoria": {
    "referencia": "conv-8",
    "emergencia_referencia": "emg-8",
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
  "oferta_referencia": "801",
  "ong_cuit": "30-11111111-1",
  "convocatoria": {
    "referencia": "conv-8",
    "emergencia_referencia": "emg-8",
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


## 9. Estado final

### 9.1 Inventario final de Rescatistas del Río

- **Pedido:** `GET {{base_url}}/ongs/{{ong_rio_id}}/recursos`
- **Token (pestaña Authorization):** ninguno (*No Auth*)
- **Qué hace el endpoint:** Inventario de una ONG por categoría (punto I-3.2): total, bloqueado, comprometido y disponible. Sirve para ver el efecto de cada operación. No pide token.
- **Qué prueba este caso:** 5 paramédicos y 1 rescatista comprometidos; 10 frazadas reservadas (oferta 505). Nunca se reservó más de lo que había.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cantidad_bloqueada": "30.00",
    "cantidad_comprometida": "30.00",
    "cantidad_disponible": "240.00",
    "cantidad_total": "300.00",
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
    "cantidad_bloqueada": "2.00",
    "cantidad_comprometida": "5.00",
    "cantidad_disponible": "5.00",
    "cantidad_total": "12.00",
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
    "cantidad_bloqueada": "3.00",
    "cantidad_comprometida": "3.00",
    "cantidad_disponible": "14.00",
    "cantidad_total": "20.00",
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

