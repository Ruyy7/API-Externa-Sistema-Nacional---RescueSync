# Casos de prueba de I-3.5 en Postman

Liberación y cierre: las actividades cumplidas liberan lo comprometido a medida que la ONG las informa, y por emergencia se libera lo que quede y se cierra el proyecto. Todos los casos se generaron ejecutándolos contra la API: las respuestas de abajo son las reales. Lo que cambia en cada corrida se muestra así: las fechas como `<fecha y hora>`, los ids como `<id>`, los tokens como `<token>`, y el CUIT, el email y el sufijo de las referencias con el nombre de su variable (`{{ong_cuit}}`, `{{ong_email}}` y `{{corrida}}`).

Los recursos se liberan en tres momentos:

| Momento | Endpoint | Inventario de la ONG |
|---|---|---|
| La ONG informa una actividad cumplida | `POST /api/v1/actividades` | reutilizable: `cantidad_comprometida -= n`; consumible: además `cantidad_total -= n` |
| Bonita libera lo que quede en la emergencia (*Liberar recursos*) | `POST /api/v1/emergencias/{ref}/liberacion` | lo mismo, para todo lo pendiente |
| Bonita cierra el proyecto (*Cerrar proyecto*) | `POST /api/v1/emergencias/{ref}/cierre` | sin cambios: exige que no quede nada comprometido |

## Preparación

**1. Importar la colección en Postman.** *Import* (arriba a la izquierda) → elegir `docs/postman/RescueSync-I-3.5.postman_collection.json` → *Import*.

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

**3. Cargar las contraseñas de las cuentas de servicio.** Clic en la colección *RescueSync · Sistema Nacional · I-3.5…* → pestaña **Variables** → completar la columna *Current value* de `password_webapp`, `password_bonita` y `password_auditor` → guardar con **Ctrl+S**. Las contraseñas no están en el repositorio: en Render son las variables `CUENTA_*_PASSWORD` del servicio, y en local, las del `.env`.

| Cuenta | Rol del token | Puede |
|---|---|---|
| `webapp` | `SISTEMA_WEBAPP` | Informar actividades, liberar la emergencia, cerrar el proyecto y consultar |
| `bonita` | `SISTEMA_BONITA` | Lo mismo: *Liberar recursos* y *Cerrar proyecto* son tareas de servicio del proceso |
| `auditor` | `AUDITOR` | Solo consultar |

**4. Ejecutar.**
- **Todos juntos:** clic derecho en la colección → **Run collection** → **Run**. El resumen muestra cuántas pruebas pasaron.
- **Uno por uno:** abrir cada pedido en orden, empezando por la carpeta 0, y apretar **Send**. Abajo, la pestaña **Test Results** muestra en verde cada valor esperado que se cumplió.

No hace falta pegar tokens ni tocar la pestaña *Authorization* de cada pedido: los logins de la carpeta 0 guardan los tokens en `token_webapp`, `token_bonita` y `token_auditor`, y cada pedido ya está configurado como *Bearer Token* con el que corresponde. Los ids de la ONG, de los compromisos y de la actividad también se guardan solos (`ong_id`, `compromiso_1`, `compromiso_2`, `compromiso_consorcio` y `actividad_1`).

**Se puede repetir sin limpiar la base.** Cada corrida registra su propia ONG, *Rescatistas de Prueba (Postman I-3.5)*, con un CUIT válido y un email nuevos, y agrega a las referencias de ofertas, convocatorias, emergencia y actividades un sufijo propio (`{{corrida}}`, por ejemplo `EMG-1-{{corrida}}`). Las fechas se calculan solas antes de cada pedido: `{{fecha_cumplida}}` es hace una hora, `{{fecha_futura}}` es mañana, y `{{cierre_futuro}}` y `{{limite_futuro}}` son las de la convocatoria.

**Inventario de partida** de la ONG de prueba, como total / bloqueada / comprometida:
- `PARAMEDICO` (reutilizable): 10 / 0 / 0
- `RESCATISTA` (reutilizable): 15 / 0 / 0
- `RACION_ALIMENTO` (consumible): 2000 / 0 / 0

La carpeta 0 deja, con los endpoints de I-3.4, un compromiso COMPROMETIDO de 5 paramédicos y 800 raciones: es lo que el punto 4 le entrega al punto 5.

**Concurrencia.** No se puede probar con Postman, porque hacen falta pedidos realmente simultáneos. Se prueba con los tests automáticos: `docker compose run --rm api pytest tests/test_concurrencia_liberacion.py -v` (dos actividades sobre el mismo pendiente, el mismo pedido en paralelo, liberar y reservar a la vez, y el cierre contra una actividad en curso).


## 0. Preparación: login, ONG de prueba y adjudicación

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
- **Qué prueba este caso:** Cada corrida registra una ONG nueva, con un CUIT válido y un email que se generan solos (`ong_cuit` y `ong_email`), así las cuentas del inventario siempre dan lo mismo. Se inscribe en 10 paramédicos y 15 rescatistas (reutilizables) y 2000 raciones (consumibles). Guarda el id en `ong_id`.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "razon_social": "Rescatistas de Prueba (Postman I-3.5)",
  "cuit": "{{ong_cuit}}",
  "email_contacto": "{{ong_email}}",
  "telefono": "221 555-0105",
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
      "tipo_recurso": "RACION_ALIMENTO",
      "cantidad_maxima": 2000
    }
  ]
}
```

**Respuesta esperada: `201 Created`**

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
        "id": "<id>",
        "nombre": "Paramédico",
        "reutilizable": true,
        "unidad_medida": {
          "admite_decimales": false,
          "codigo": "PERSONA",
          "id": "<id>",
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
        "id": "<id>",
        "nombre": "Rescatista",
        "reutilizable": true,
        "unidad_medida": {
          "admite_decimales": false,
          "codigo": "PERSONA",
          "id": "<id>",
          "nombre": "Personas"
        }
      }
    },
    {
      "cantidad_bloqueada": "0.00",
      "cantidad_comprometida": "0.00",
      "cantidad_disponible": "2000.00",
      "cantidad_total": "2000.00",
      "tipo_recurso": {
        "categoria": "MATERIAL",
        "codigo": "RACION_ALIMENTO",
        "id": "<id>",
        "nombre": "Ración de alimento",
        "reutilizable": false,
        "unidad_medida": {
          "admite_decimales": false,
          "codigo": "RACION",
          "id": "<id>",
          "nombre": "Raciones"
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
  "razon_social": "Rescatistas de Prueba (Postman I-3.5)",
  "telefono": "221 555-0105"
}
```

### 0.5 La ONG presenta la oferta 1: 5 paramédicos y 1000 raciones

- **Pedido:** `POST {{base_url}}/compromisos`
- **Token (pestaña Authorization):** `{{token_webapp}}` (*Bearer Token*)
- **Qué hace el endpoint:** Reserva (bloquea) los recursos de una oferta presentada (punto I-3.4).
- **Qué prueba este caso:** Es el punto 4. Deja la reserva de la oferta 1 en la convocatoria 1 de la emergencia 1 y guarda su id en `compromiso_1`. Lo que sigue en esta colección parte de acá.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "oferta_referencia": "OF-1-{{corrida}}",
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
      "cantidad": 5
    },
    {
      "tipo_recurso": "RACION_ALIMENTO",
      "cantidad": 1000
    }
  ]
}
```

**Respuesta esperada: `201 Created`**

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
  "creado_por": "<id de la cuenta>",
  "estado": "RESERVADO",
  "finalizado_en": null,
  "id": "<id>",
  "items": [
    {
      "cantidad_comprometida": "0.00",
      "cantidad_liberada": "0.00",
      "cantidad_pendiente": "0.00",
      "cantidad_reservada": "5.00",
      "tipo_recurso": {
        "codigo": "PARAMEDICO",
        "nombre": "Paramédico"
      }
    },
    {
      "cantidad_comprometida": "0.00",
      "cantidad_liberada": "0.00",
      "cantidad_pendiente": "0.00",
      "cantidad_reservada": "1000.00",
      "tipo_recurso": {
        "codigo": "RACION_ALIMENTO",
        "nombre": "Ración de alimento"
      }
    }
  ],
  "oferta_referencia": "OF-1-{{corrida}}",
  "ong": {
    "cuit": "{{ong_cuit}}",
    "id": "<id>",
    "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
  },
  "vencido_en": null
}
```

### 0.6 El municipio adjudica 5 paramédicos y 800 raciones (adjudicación parcial)

- **Pedido:** `POST {{base_url}}/compromisos/{{compromiso_1}}/confirmacion`
- **Token (pestaña Authorization):** `{{token_bonita}}` (*Bearer Token*)
- **Qué hace el endpoint:** Compromete lo adjudicado por el municipio (punto I-3.4): lo adjudicado pasa de bloqueado a comprometido y la diferencia se libera en ese momento.
- **Qué prueba este caso:** También es el punto 4. El compromiso queda COMPROMETIDO con 5 paramédicos y 800 raciones; las 200 raciones no adjudicadas se liberan de la reserva. Desde acá actúa el punto 5. Cada ítem ya muestra `cantidad_liberada` 0 y `cantidad_pendiente` igual a lo comprometido.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "items": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 5
    },
    {
      "tipo_recurso": "RACION_ALIMENTO",
      "cantidad": 800
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
  "creado_por": "<id de la cuenta>",
  "estado": "COMPROMETIDO",
  "finalizado_en": null,
  "id": "<id>",
  "items": [
    {
      "cantidad_comprometida": "5.00",
      "cantidad_liberada": "0.00",
      "cantidad_pendiente": "5.00",
      "cantidad_reservada": "5.00",
      "tipo_recurso": {
        "codigo": "PARAMEDICO",
        "nombre": "Paramédico"
      }
    },
    {
      "cantidad_comprometida": "800.00",
      "cantidad_liberada": "0.00",
      "cantidad_pendiente": "800.00",
      "cantidad_reservada": "1000.00",
      "tipo_recurso": {
        "codigo": "RACION_ALIMENTO",
        "nombre": "Ración de alimento"
      }
    }
  ],
  "oferta_referencia": "OF-1-{{corrida}}",
  "ong": {
    "cuit": "{{ong_cuit}}",
    "id": "<id>",
    "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
  },
  "vencido_en": null
}
```

### 0.7 Inventario después de adjudicar

- **Pedido:** `GET {{base_url}}/ongs/{{ong_id}}/recursos`
- **Token (pestaña Authorization):** `{{token_auditor}}` (*Bearer Token*)
- **Qué hace el endpoint:** Inventario y disponibilidad de la ONG (punto I-3.2): `cantidad_total`, `cantidad_bloqueada` (reservas), `cantidad_comprometida` (adjudicado en ejecución) y `cantidad_disponible = total - bloqueada - comprometida`.
- **Qué prueba este caso:** Punto de partida del punto 5: 5 paramédicos y 800 raciones comprometidos, nada bloqueado.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cantidad_bloqueada": "0.00",
    "cantidad_comprometida": "5.00",
    "cantidad_disponible": "5.00",
    "cantidad_total": "10.00",
    "tipo_recurso": {
      "categoria": "PERSONAL",
      "codigo": "PARAMEDICO",
      "id": "<id>",
      "nombre": "Paramédico",
      "reutilizable": true,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "PERSONA",
        "id": "<id>",
        "nombre": "Personas"
      }
    }
  },
  {
    "cantidad_bloqueada": "0.00",
    "cantidad_comprometida": "800.00",
    "cantidad_disponible": "1200.00",
    "cantidad_total": "2000.00",
    "tipo_recurso": {
      "categoria": "MATERIAL",
      "codigo": "RACION_ALIMENTO",
      "id": "<id>",
      "nombre": "Ración de alimento",
      "reutilizable": false,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "RACION",
        "id": "<id>",
        "nombre": "Raciones"
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
      "id": "<id>",
      "nombre": "Rescatista",
      "reutilizable": true,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "PERSONA",
        "id": "<id>",
        "nombre": "Personas"
      }
    }
  }
]
```

### 0.8 Estado de la emergencia antes de liberar

- **Pedido:** `GET {{base_url}}/emergencias/EMG-1-{{corrida}}/liberacion`
- **Token (pestaña Authorization):** `{{token_bonita}}` (*Bearer Token*)
- **Qué hace el endpoint:** Qué queda por liberar en la emergencia, por compromiso e ítem, con `todo_liberado` (lo que Bonita necesita para *Finalizaron todas las tareas?*), las reservas vigentes y el cierre, si existe.
- **Qué prueba este caso:** Nada liberado todavía: `todo_liberado` es false y el único compromiso tiene 5 paramédicos y 800 raciones pendientes. Es lo que Bonita ve en *Monitorear recursos*.

**Respuesta esperada: `200 OK`**

```json
{
  "cerrado": false,
  "cierre": null,
  "compromisos": [
    {
      "estado": "COMPROMETIDO",
      "finalizado_en": null,
      "id": "<id>",
      "items": [
        {
          "cantidad_comprometida": "5.00",
          "cantidad_liberada": "0.00",
          "cantidad_pendiente": "5.00",
          "tipo_recurso": {
            "codigo": "PARAMEDICO",
            "nombre": "Paramédico"
          }
        },
        {
          "cantidad_comprometida": "800.00",
          "cantidad_liberada": "0.00",
          "cantidad_pendiente": "800.00",
          "tipo_recurso": {
            "codigo": "RACION_ALIMENTO",
            "nombre": "Ración de alimento"
          }
        }
      ],
      "oferta_referencia": "OF-1-{{corrida}}",
      "ong": {
        "cuit": "{{ong_cuit}}",
        "id": "<id>",
        "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
      }
    }
  ],
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "reservas_vigentes": 0,
  "todo_liberado": false
}
```


## 1. La ONG informa actividades cumplidas

### 1.1 Terminaron 3 de los 5 paramédicos

- **Pedido:** `POST {{base_url}}/actividades`
- **Token (pestaña Authorization):** `{{token_webapp}}` (*Bearer Token*)
- **Qué hace el endpoint:** Registra una actividad cumplida y libera sus recursos. Con el compromiso y la fila de inventario bloqueados (`SELECT ... FOR UPDATE`), descuenta la cantidad de lo comprometido: lo reutilizable vuelve a estar disponible y lo consumible sale del stock. Es idempotente por `actividad_referencia`. Cuando al compromiso no le queda nada pendiente, pasa a FINALIZADO.
- **Qué prueba este caso:** La webapp informa la actividad cuando la ONG la marca como finalizada [E-7]. Como el paramédico es reutilizable, la acción es LIBERADO: vuelven 3 al stock. Quedan 2 pendientes y el compromiso sigue COMPROMETIDO (todavía hay raciones en ejecución). Guarda el id en `actividad_1`.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "actividad_referencia": "ACT-1-{{corrida}}",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "tipo_recurso": "PARAMEDICO",
  "cantidad": 3,
  "fecha": "{{fecha_cumplida}}",
  "observaciones": "Evacuación del barrio Norte terminada"
}
```

**Respuesta esperada: `201 Created`**

```json
{
  "accion": "LIBERADO",
  "actividad_referencia": "ACT-1-{{corrida}}",
  "cantidad": "3.00",
  "compromiso_id": "<id>",
  "creado_en": "<fecha y hora>",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "estado_compromiso": "COMPROMETIDO",
  "fecha": "<fecha y hora>",
  "id": "<id>",
  "item": {
    "cantidad_comprometida": "5.00",
    "cantidad_liberada": "3.00",
    "cantidad_pendiente": "2.00",
    "tipo_recurso": {
      "codigo": "PARAMEDICO",
      "nombre": "Paramédico"
    }
  },
  "observaciones": "Evacuación del barrio Norte terminada",
  "oferta_referencia": "OF-1-{{corrida}}",
  "ong": {
    "cuit": "{{ong_cuit}}",
    "id": "<id>",
    "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
  },
  "origen": "INFORMADA",
  "registrada_por": "<id de la cuenta>",
  "tipo_recurso": {
    "codigo": "PARAMEDICO",
    "nombre": "Paramédico"
  }
}
```

### 1.2 Inventario después de la actividad: los 3 paramédicos están disponibles

- **Pedido:** `GET {{base_url}}/ongs/{{ong_id}}/recursos`
- **Token (pestaña Authorization):** `{{token_auditor}}` (*Bearer Token*)
- **Qué hace el endpoint:** Inventario y disponibilidad de la ONG (punto I-3.2): `cantidad_total`, `cantidad_bloqueada` (reservas), `cantidad_comprometida` (adjudicado en ejecución) y `cantidad_disponible = total - bloqueada - comprometida`.
- **Qué prueba este caso:** `cantidad_comprometida` de paramédicos bajó de 5 a 2 y `cantidad_total` no cambió: lo reutilizable vuelve al stock.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cantidad_bloqueada": "0.00",
    "cantidad_comprometida": "2.00",
    "cantidad_disponible": "8.00",
    "cantidad_total": "10.00",
    "tipo_recurso": {
      "categoria": "PERSONAL",
      "codigo": "PARAMEDICO",
      "id": "<id>",
      "nombre": "Paramédico",
      "reutilizable": true,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "PERSONA",
        "id": "<id>",
        "nombre": "Personas"
      }
    }
  },
  {
    "cantidad_bloqueada": "0.00",
    "cantidad_comprometida": "800.00",
    "cantidad_disponible": "1200.00",
    "cantidad_total": "2000.00",
    "tipo_recurso": {
      "categoria": "MATERIAL",
      "codigo": "RACION_ALIMENTO",
      "id": "<id>",
      "nombre": "Ración de alimento",
      "reutilizable": false,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "RACION",
        "id": "<id>",
        "nombre": "Raciones"
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
      "id": "<id>",
      "nombre": "Rescatista",
      "reutilizable": true,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "PERSONA",
        "id": "<id>",
        "nombre": "Personas"
      }
    }
  }
]
```

### 1.3 Reintento: la webapp repite el mismo pedido

- **Pedido:** `POST {{base_url}}/actividades`
- **Token (pestaña Authorization):** `{{token_webapp}}` (*Bearer Token*)
- **Qué hace el endpoint:** Registra una actividad cumplida y libera sus recursos. Con el compromiso y la fila de inventario bloqueados (`SELECT ... FOR UPDATE`), descuenta la cantidad de lo comprometido: lo reutilizable vuelve a estar disponible y lo consumible sale del stock. Es idempotente por `actividad_referencia`. Cuando al compromiso no le queda nada pendiente, pasa a FINALIZADO.
- **Qué prueba este caso:** La misma `actividad_referencia` con los mismos datos es un reintento (por ejemplo, después de un timeout): responde 200 con la actividad ya registrada y no libera de nuevo.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "actividad_referencia": "ACT-1-{{corrida}}",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "tipo_recurso": "PARAMEDICO",
  "cantidad": 3,
  "fecha": "{{fecha_cumplida}}",
  "observaciones": "Evacuación del barrio Norte terminada"
}
```

**Respuesta esperada: `200 OK`**

```json
{
  "accion": "LIBERADO",
  "actividad_referencia": "ACT-1-{{corrida}}",
  "cantidad": "3.00",
  "compromiso_id": "<id>",
  "creado_en": "<fecha y hora>",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "estado_compromiso": "COMPROMETIDO",
  "fecha": "<fecha y hora>",
  "id": "<id>",
  "item": {
    "cantidad_comprometida": "5.00",
    "cantidad_liberada": "3.00",
    "cantidad_pendiente": "2.00",
    "tipo_recurso": {
      "codigo": "PARAMEDICO",
      "nombre": "Paramédico"
    }
  },
  "observaciones": "Evacuación del barrio Norte terminada",
  "oferta_referencia": "OF-1-{{corrida}}",
  "ong": {
    "cuit": "{{ong_cuit}}",
    "id": "<id>",
    "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
  },
  "origen": "INFORMADA",
  "registrada_por": "<id de la cuenta>",
  "tipo_recurso": {
    "codigo": "PARAMEDICO",
    "nombre": "Paramédico"
  }
}
```

### 1.4 La misma referencia con otra cantidad

- **Pedido:** `POST {{base_url}}/actividades`
- **Token (pestaña Authorization):** `{{token_webapp}}` (*Bearer Token*)
- **Qué hace el endpoint:** Registra una actividad cumplida y libera sus recursos. Con el compromiso y la fila de inventario bloqueados (`SELECT ... FOR UPDATE`), descuenta la cantidad de lo comprometido: lo reutilizable vuelve a estar disponible y lo consumible sale del stock. Es idempotente por `actividad_referencia`. Cuando al compromiso no le queda nada pendiente, pasa a FINALIZADO.
- **Qué prueba este caso:** No es un reintento: la referencia ya se usó con otros datos. Nada cambia.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "actividad_referencia": "ACT-1-{{corrida}}",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "tipo_recurso": "PARAMEDICO",
  "cantidad": 2,
  "fecha": "{{fecha_cumplida}}",
  "observaciones": "Tarea cumplida"
}
```

**Respuesta esperada: `409 Conflict`**

```json
{
  "codigo": "ACTIVIDAD_DUPLICADA",
  "detalles": {
    "actividad_id": "<id>"
  },
  "mensaje": "Ya existe una actividad con esa referencia y otros datos."
}
```

### 1.5 Más paramédicos de los que quedan pendientes

- **Pedido:** `POST {{base_url}}/actividades`
- **Token (pestaña Authorization):** `{{token_webapp}}` (*Bearer Token*)
- **Qué hace el endpoint:** Registra una actividad cumplida y libera sus recursos. Con el compromiso y la fila de inventario bloqueados (`SELECT ... FOR UPDATE`), descuenta la cantidad de lo comprometido: lo reutilizable vuelve a estar disponible y lo consumible sale del stock. Es idempotente por `actividad_referencia`. Cuando al compromiso no le queda nada pendiente, pasa a FINALIZADO.
- **Qué prueba este caso:** Quedan 2 pendientes y se informan 3. Se rechaza con el detalle y no se libera nada; la base lo frenaría igual con el CHECK `cantidad_liberada <= cantidad_comprometida`.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "actividad_referencia": "ACT-2-{{corrida}}",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "tipo_recurso": "PARAMEDICO",
  "cantidad": 3,
  "fecha": "{{fecha_cumplida}}",
  "observaciones": "Tarea cumplida"
}
```

**Respuesta esperada: `409 Conflict`**

```json
{
  "codigo": "EXCEDE_PENDIENTE",
  "detalles": {
    "pedida": "3.00",
    "pendiente": "2.00",
    "tipo_recurso": "PARAMEDICO"
  },
  "mensaje": "La cantidad supera lo comprometido que falta liberar."
}
```

### 1.6 Se entregaron 500 raciones

- **Pedido:** `POST {{base_url}}/actividades`
- **Token (pestaña Authorization):** `{{token_webapp}}` (*Bearer Token*)
- **Qué hace el endpoint:** Registra una actividad cumplida y libera sus recursos. Con el compromiso y la fila de inventario bloqueados (`SELECT ... FOR UPDATE`), descuenta la cantidad de lo comprometido: lo reutilizable vuelve a estar disponible y lo consumible sale del stock. Es idempotente por `actividad_referencia`. Cuando al compromiso no le queda nada pendiente, pasa a FINALIZADO.
- **Qué prueba este caso:** La ración es consumible: la acción es CONSUMIDO. Quedan 300 pendientes.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "actividad_referencia": "ACT-2-{{corrida}}",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "tipo_recurso": "RACION_ALIMENTO",
  "cantidad": 500,
  "fecha": "{{fecha_cumplida}}",
  "observaciones": "Entregadas en el centro de evacuados"
}
```

**Respuesta esperada: `201 Created`**

```json
{
  "accion": "CONSUMIDO",
  "actividad_referencia": "ACT-2-{{corrida}}",
  "cantidad": "500.00",
  "compromiso_id": "<id>",
  "creado_en": "<fecha y hora>",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "estado_compromiso": "COMPROMETIDO",
  "fecha": "<fecha y hora>",
  "id": "<id>",
  "item": {
    "cantidad_comprometida": "800.00",
    "cantidad_liberada": "500.00",
    "cantidad_pendiente": "300.00",
    "tipo_recurso": {
      "codigo": "RACION_ALIMENTO",
      "nombre": "Ración de alimento"
    }
  },
  "observaciones": "Entregadas en el centro de evacuados",
  "oferta_referencia": "OF-1-{{corrida}}",
  "ong": {
    "cuit": "{{ong_cuit}}",
    "id": "<id>",
    "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
  },
  "origen": "INFORMADA",
  "registrada_por": "<id de la cuenta>",
  "tipo_recurso": {
    "codigo": "RACION_ALIMENTO",
    "nombre": "Ración de alimento"
  }
}
```

### 1.7 Inventario después de consumir: bajan comprometido y total, lo disponible no cambia

- **Pedido:** `GET {{base_url}}/ongs/{{ong_id}}/recursos`
- **Token (pestaña Authorization):** `{{token_auditor}}` (*Bearer Token*)
- **Qué hace el endpoint:** Inventario y disponibilidad de la ONG (punto I-3.2): `cantidad_total`, `cantidad_bloqueada` (reservas), `cantidad_comprometida` (adjudicado en ejecución) y `cantidad_disponible = total - bloqueada - comprometida`.
- **Qué prueba este caso:** Las raciones pasaron de 2000 a 1500 en total y de 800 a 300 comprometidas; las 1200 disponibles son las mismas, porque las que se consumieron ya no estaban disponibles. El total es el tope que la ONG declaró: lo vuelve a subir con `PUT /ongs/yo/categorias` cuando repone.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cantidad_bloqueada": "0.00",
    "cantidad_comprometida": "2.00",
    "cantidad_disponible": "8.00",
    "cantidad_total": "10.00",
    "tipo_recurso": {
      "categoria": "PERSONAL",
      "codigo": "PARAMEDICO",
      "id": "<id>",
      "nombre": "Paramédico",
      "reutilizable": true,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "PERSONA",
        "id": "<id>",
        "nombre": "Personas"
      }
    }
  },
  {
    "cantidad_bloqueada": "0.00",
    "cantidad_comprometida": "300.00",
    "cantidad_disponible": "1200.00",
    "cantidad_total": "1500.00",
    "tipo_recurso": {
      "categoria": "MATERIAL",
      "codigo": "RACION_ALIMENTO",
      "id": "<id>",
      "nombre": "Ración de alimento",
      "reutilizable": false,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "RACION",
        "id": "<id>",
        "nombre": "Raciones"
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
      "id": "<id>",
      "nombre": "Rescatista",
      "reutilizable": true,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "PERSONA",
        "id": "<id>",
        "nombre": "Personas"
      }
    }
  }
]
```

### 1.8 Terminaron los 2 paramédicos restantes

- **Pedido:** `POST {{base_url}}/actividades`
- **Token (pestaña Authorization):** `{{token_webapp}}` (*Bearer Token*)
- **Qué hace el endpoint:** Registra una actividad cumplida y libera sus recursos. Con el compromiso y la fila de inventario bloqueados (`SELECT ... FOR UPDATE`), descuenta la cantidad de lo comprometido: lo reutilizable vuelve a estar disponible y lo consumible sale del stock. Es idempotente por `actividad_referencia`. Cuando al compromiso no le queda nada pendiente, pasa a FINALIZADO.
- **Qué prueba este caso:** El ítem de paramédicos queda sin pendiente, pero el compromiso sigue COMPROMETIDO porque todavía tiene 300 raciones en ejecución: pasa a FINALIZADO recién cuando ningún ítem tiene pendiente.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "actividad_referencia": "ACT-3-{{corrida}}",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "tipo_recurso": "PARAMEDICO",
  "cantidad": 2,
  "fecha": "{{fecha_cumplida}}",
  "observaciones": "Tarea cumplida"
}
```

**Respuesta esperada: `201 Created`**

```json
{
  "accion": "LIBERADO",
  "actividad_referencia": "ACT-3-{{corrida}}",
  "cantidad": "2.00",
  "compromiso_id": "<id>",
  "creado_en": "<fecha y hora>",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "estado_compromiso": "COMPROMETIDO",
  "fecha": "<fecha y hora>",
  "id": "<id>",
  "item": {
    "cantidad_comprometida": "5.00",
    "cantidad_liberada": "5.00",
    "cantidad_pendiente": "0.00",
    "tipo_recurso": {
      "codigo": "PARAMEDICO",
      "nombre": "Paramédico"
    }
  },
  "observaciones": "Tarea cumplida",
  "oferta_referencia": "OF-1-{{corrida}}",
  "ong": {
    "cuit": "{{ong_cuit}}",
    "id": "<id>",
    "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
  },
  "origen": "INFORMADA",
  "registrada_por": "<id de la cuenta>",
  "tipo_recurso": {
    "codigo": "PARAMEDICO",
    "nombre": "Paramédico"
  }
}
```

### 1.9 El compromiso con el avance de la liberación por ítem

- **Pedido:** `GET {{base_url}}/compromisos/{{compromiso_1}}`
- **Token (pestaña Authorization):** `{{token_auditor}}` (*Bearer Token*)
- **Qué hace el endpoint:** Detalle de una reserva o compromiso (punto I-3.4). Desde I-3.5 cada ítem trae `cantidad_liberada` y `cantidad_pendiente`.
- **Qué prueba este caso:** Paramédicos: 5 comprometidos, 5 liberados, 0 pendientes. Raciones: 800, 500 y 300.

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
  "creado_por": "<id de la cuenta>",
  "estado": "COMPROMETIDO",
  "finalizado_en": null,
  "id": "<id>",
  "items": [
    {
      "cantidad_comprometida": "5.00",
      "cantidad_liberada": "5.00",
      "cantidad_pendiente": "0.00",
      "cantidad_reservada": "5.00",
      "tipo_recurso": {
        "codigo": "PARAMEDICO",
        "nombre": "Paramédico"
      }
    },
    {
      "cantidad_comprometida": "800.00",
      "cantidad_liberada": "500.00",
      "cantidad_pendiente": "300.00",
      "cantidad_reservada": "1000.00",
      "tipo_recurso": {
        "codigo": "RACION_ALIMENTO",
        "nombre": "Ración de alimento"
      }
    }
  ],
  "oferta_referencia": "OF-1-{{corrida}}",
  "ong": {
    "cuit": "{{ong_cuit}}",
    "id": "<id>",
    "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
  },
  "vencido_en": null
}
```


## 2. Reglas del registro de actividades

### 2.1 Medio paramédico

- **Pedido:** `POST {{base_url}}/actividades`
- **Token (pestaña Authorization):** `{{token_webapp}}` (*Bearer Token*)
- **Qué hace el endpoint:** Registra una actividad cumplida y libera sus recursos. Con el compromiso y la fila de inventario bloqueados (`SELECT ... FOR UPDATE`), descuenta la cantidad de lo comprometido: lo reutilizable vuelve a estar disponible y lo consumible sale del stock. Es idempotente por `actividad_referencia`. Cuando al compromiso no le queda nada pendiente, pasa a FINALIZADO.
- **Qué prueba este caso:** Las personas se cuentan en unidades enteras (la unidad de medida no admite decimales).

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "actividad_referencia": "ACT-4-{{corrida}}",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "tipo_recurso": "PARAMEDICO",
  "cantidad": 0.5,
  "fecha": "{{fecha_cumplida}}",
  "observaciones": "Tarea cumplida"
}
```

**Respuesta esperada: `422 Unprocessable Entity`**

```json
{
  "codigo": "VALIDACION",
  "detalles": {
    "json": {
      "cantidad": [
        "Tiene que ser un número entero."
      ]
    }
  },
  "mensaje": "Hay campos con errores."
}
```

### 2.2 Una fecha futura

- **Pedido:** `POST {{base_url}}/actividades`
- **Token (pestaña Authorization):** `{{token_webapp}}` (*Bearer Token*)
- **Qué hace el endpoint:** Registra una actividad cumplida y libera sus recursos. Con el compromiso y la fila de inventario bloqueados (`SELECT ... FOR UPDATE`), descuenta la cantidad de lo comprometido: lo reutilizable vuelve a estar disponible y lo consumible sale del stock. Es idempotente por `actividad_referencia`. Cuando al compromiso no le queda nada pendiente, pasa a FINALIZADO.
- **Qué prueba este caso:** La fecha de cumplimiento no puede ser posterior a ahora (hay 5 minutos de tolerancia de reloj). `fecha_futura` es mañana.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "actividad_referencia": "ACT-4-{{corrida}}",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "tipo_recurso": "PARAMEDICO",
  "cantidad": 1,
  "fecha": "{{fecha_futura}}",
  "observaciones": "Tarea cumplida"
}
```

**Respuesta esperada: `422 Unprocessable Entity`**

```json
{
  "codigo": "FECHA_FUTURA",
  "detalles": {
    "fecha": "<fecha y hora>"
  },
  "mensaje": "La fecha no puede ser futura."
}
```

### 2.3 Una categoría que no existe en el catálogo

- **Pedido:** `POST {{base_url}}/actividades`
- **Token (pestaña Authorization):** `{{token_webapp}}` (*Bearer Token*)
- **Qué hace el endpoint:** Registra una actividad cumplida y libera sus recursos. Con el compromiso y la fila de inventario bloqueados (`SELECT ... FOR UPDATE`), descuenta la cantidad de lo comprometido: lo reutilizable vuelve a estar disponible y lo consumible sale del stock. Es idempotente por `actividad_referencia`. Cuando al compromiso no le queda nada pendiente, pasa a FINALIZADO.
- **Qué prueba este caso:** Un código fuera del catálogo nacional indica un catálogo desalineado con la webapp, igual que en I-3.3.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "actividad_referencia": "ACT-4-{{corrida}}",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "tipo_recurso": "DRON",
  "cantidad": 1,
  "fecha": "{{fecha_cumplida}}",
  "observaciones": "Tarea cumplida"
}
```

**Respuesta esperada: `422 Unprocessable Entity`**

```json
{
  "codigo": "TIPO_RECURSO_DESCONOCIDO",
  "detalles": {
    "tipos_recurso": [
      "DRON"
    ]
  },
  "mensaje": "El tipo de recurso no existe en el catálogo nacional."
}
```

### 2.4 Una categoría sin compromiso en la emergencia

- **Pedido:** `POST {{base_url}}/actividades`
- **Token (pestaña Authorization):** `{{token_webapp}}` (*Bearer Token*)
- **Qué hace el endpoint:** Registra una actividad cumplida y libera sus recursos. Con el compromiso y la fila de inventario bloqueados (`SELECT ... FOR UPDATE`), descuenta la cantidad de lo comprometido: lo reutilizable vuelve a estar disponible y lo consumible sale del stock. Es idempotente por `actividad_referencia`. Cuando al compromiso no le queda nada pendiente, pasa a FINALIZADO.
- **Qué prueba este caso:** La ONG está inscripta en rescatistas, pero no comprometió ninguno en esta emergencia.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "actividad_referencia": "ACT-4-{{corrida}}",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "tipo_recurso": "RESCATISTA",
  "cantidad": 1,
  "fecha": "{{fecha_cumplida}}",
  "observaciones": "Tarea cumplida"
}
```

**Respuesta esperada: `404 Not Found`**

```json
{
  "codigo": "NO_ENCONTRADO",
  "detalles": {
    "emergencia_referencia": "EMG-1-{{corrida}}",
    "ong_cuit": "{{ong_cuit}}",
    "tipo_recurso": "RESCATISTA"
  },
  "mensaje": "La ONG no tiene un compromiso con esa categoría en esa emergencia."
}
```

### 2.5 Un CUIT que no está registrado

- **Pedido:** `POST {{base_url}}/actividades`
- **Token (pestaña Authorization):** `{{token_webapp}}` (*Bearer Token*)
- **Qué hace el endpoint:** Registra una actividad cumplida y libera sus recursos. Con el compromiso y la fila de inventario bloqueados (`SELECT ... FOR UPDATE`), descuenta la cantidad de lo comprometido: lo reutilizable vuelve a estar disponible y lo consumible sale del stock. Es idempotente por `actividad_referencia`. Cuando al compromiso no le queda nada pendiente, pasa a FINALIZADO.
- **Qué prueba este caso:** La ONG se identifica por CUIT en toda la API; uno desconocido es 422 ONG_INEXISTENTE, como en I-3.4.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "actividad_referencia": "ACT-4-{{corrida}}",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "ong_cuit": "30-99999999-9",
  "tipo_recurso": "PARAMEDICO",
  "cantidad": 1,
  "fecha": "{{fecha_cumplida}}",
  "observaciones": "Tarea cumplida"
}
```

**Respuesta esperada: `422 Unprocessable Entity`**

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

### 2.6 La ONG presenta la oferta 2: 4 rescatistas (queda reservada, sin adjudicar)

- **Pedido:** `POST {{base_url}}/compromisos`
- **Token (pestaña Authorization):** `{{token_webapp}}` (*Bearer Token*)
- **Qué hace el endpoint:** Reserva (bloquea) los recursos de una oferta presentada (punto I-3.4).
- **Qué prueba este caso:** Prepara el caso siguiente: una reserva en la convocatoria 2 de la misma emergencia que el municipio no adjudica. Guarda el id en `compromiso_2`.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "oferta_referencia": "OF-2-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "convocatoria": {
    "referencia": "CONV-2-{{corrida}}",
    "emergencia_referencia": "EMG-1-{{corrida}}",
    "fecha_cierre": "{{cierre_futuro}}",
    "fecha_limite_adjudicacion": "{{limite_futuro}}"
  },
  "items": [
    {
      "tipo_recurso": "RESCATISTA",
      "cantidad": 4
    }
  ]
}
```

**Respuesta esperada: `201 Created`**

```json
{
  "cancelado_en": null,
  "confirmado_en": null,
  "convocatoria": {
    "emergencia_referencia": "EMG-1-{{corrida}}",
    "fecha_cierre": "<fecha y hora>",
    "fecha_limite_adjudicacion": "<fecha y hora>",
    "referencia": "CONV-2-{{corrida}}"
  },
  "creado_en": "<fecha y hora>",
  "creado_por": "<id de la cuenta>",
  "estado": "RESERVADO",
  "finalizado_en": null,
  "id": "<id>",
  "items": [
    {
      "cantidad_comprometida": "0.00",
      "cantidad_liberada": "0.00",
      "cantidad_pendiente": "0.00",
      "cantidad_reservada": "4.00",
      "tipo_recurso": {
        "codigo": "RESCATISTA",
        "nombre": "Rescatista"
      }
    }
  ],
  "oferta_referencia": "OF-2-{{corrida}}",
  "ong": {
    "cuit": "{{ong_cuit}}",
    "id": "<id>",
    "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
  },
  "vencido_en": null
}
```

### 2.7 Una actividad sobre una reserva sin adjudicar

- **Pedido:** `POST {{base_url}}/actividades`
- **Token (pestaña Authorization):** `{{token_webapp}}` (*Bearer Token*)
- **Qué hace el endpoint:** Registra una actividad cumplida y libera sus recursos. Con el compromiso y la fila de inventario bloqueados (`SELECT ... FOR UPDATE`), descuenta la cantidad de lo comprometido: lo reutilizable vuelve a estar disponible y lo consumible sale del stock. Es idempotente por `actividad_referencia`. Cuando al compromiso no le queda nada pendiente, pasa a FINALIZADO.
- **Qué prueba este caso:** Solo se liberan recursos de un compromiso COMPROMETIDO. La reserva sigue RESERVADO y `cantidad_bloqueada` no se toca: eso es del punto 4.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "actividad_referencia": "ACT-4-{{corrida}}",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "tipo_recurso": "RESCATISTA",
  "cantidad": 1,
  "fecha": "{{fecha_cumplida}}",
  "observaciones": "Tarea cumplida"
}
```

**Respuesta esperada: `409 Conflict`**

```json
{
  "codigo": "TRANSICION_INVALIDA",
  "detalles": {
    "compromisos": [
      {
        "estado": "RESERVADO",
        "id": "<id>",
        "oferta_referencia": "OF-2-{{corrida}}"
      }
    ]
  },
  "mensaje": "Solo se liberan recursos de un compromiso COMPROMETIDO."
}
```

### 2.8 La ONG también va en un consorcio: oferta 3 con 2 paramédicos

- **Pedido:** `POST {{base_url}}/compromisos`
- **Token (pestaña Authorization):** `{{token_webapp}}` (*Bearer Token*)
- **Qué hace el endpoint:** Reserva (bloquea) los recursos de una oferta presentada (punto I-3.4).
- **Qué prueba este caso:** Prepara la ambigüedad: la misma ONG, la misma emergencia y la misma categoría en otra oferta. Guarda el id en `compromiso_consorcio`.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "oferta_referencia": "OF-CONSORCIO-{{corrida}}",
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
      "cantidad": 2
    }
  ]
}
```

**Respuesta esperada: `201 Created`**

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
  "creado_por": "<id de la cuenta>",
  "estado": "RESERVADO",
  "finalizado_en": null,
  "id": "<id>",
  "items": [
    {
      "cantidad_comprometida": "0.00",
      "cantidad_liberada": "0.00",
      "cantidad_pendiente": "0.00",
      "cantidad_reservada": "2.00",
      "tipo_recurso": {
        "codigo": "PARAMEDICO",
        "nombre": "Paramédico"
      }
    }
  ],
  "oferta_referencia": "OF-CONSORCIO-{{corrida}}",
  "ong": {
    "cuit": "{{ong_cuit}}",
    "id": "<id>",
    "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
  },
  "vencido_en": null
}
```

### 2.9 El municipio adjudica la oferta del consorcio

- **Pedido:** `POST {{base_url}}/compromisos/{{compromiso_consorcio}}/confirmacion`
- **Token (pestaña Authorization):** `{{token_webapp}}` (*Bearer Token*)
- **Qué hace el endpoint:** Compromete lo adjudicado por el municipio (punto I-3.4): lo adjudicado pasa de bloqueado a comprometido y la diferencia se libera en ese momento.
- **Qué prueba este caso:** Ahora la ONG tiene dos compromisos COMPROMETIDO con paramédicos en la emergencia.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "items": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 2
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
  "creado_por": "<id de la cuenta>",
  "estado": "COMPROMETIDO",
  "finalizado_en": null,
  "id": "<id>",
  "items": [
    {
      "cantidad_comprometida": "2.00",
      "cantidad_liberada": "0.00",
      "cantidad_pendiente": "2.00",
      "cantidad_reservada": "2.00",
      "tipo_recurso": {
        "codigo": "PARAMEDICO",
        "nombre": "Paramédico"
      }
    }
  ],
  "oferta_referencia": "OF-CONSORCIO-{{corrida}}",
  "ong": {
    "cuit": "{{ong_cuit}}",
    "id": "<id>",
    "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
  },
  "vencido_en": null
}
```

### 2.10 Una actividad de paramédicos sin decir de qué oferta

- **Pedido:** `POST {{base_url}}/actividades`
- **Token (pestaña Authorization):** `{{token_webapp}}` (*Bearer Token*)
- **Qué hace el endpoint:** Registra una actividad cumplida y libera sus recursos. Con el compromiso y la fila de inventario bloqueados (`SELECT ... FOR UPDATE`), descuenta la cantidad de lo comprometido: lo reutilizable vuelve a estar disponible y lo consumible sale del stock. Es idempotente por `actividad_referencia`. Cuando al compromiso no le queda nada pendiente, pasa a FINALIZADO.
- **Qué prueba este caso:** Hay dos compromisos posibles (la oferta 1 y la del consorcio): la API no adivina y lista las ofertas candidatas para reenviar el pedido con `oferta_referencia`.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "actividad_referencia": "ACT-4-{{corrida}}",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "tipo_recurso": "PARAMEDICO",
  "cantidad": 1,
  "fecha": "{{fecha_cumplida}}",
  "observaciones": "Tarea cumplida"
}
```

**Respuesta esperada: `422 Unprocessable Entity`**

```json
{
  "codigo": "COMPROMISO_AMBIGUO",
  "detalles": {
    "ofertas": [
      "OF-1-{{corrida}}",
      "OF-CONSORCIO-{{corrida}}"
    ]
  },
  "mensaje": "La ONG tiene más de un compromiso con esa categoría en la emergencia: indicá oferta_referencia."
}
```

### 2.11 Con oferta_referencia de la oferta 1, que ya no tiene paramédicos pendientes

- **Pedido:** `POST {{base_url}}/actividades`
- **Token (pestaña Authorization):** `{{token_webapp}}` (*Bearer Token*)
- **Qué hace el endpoint:** Registra una actividad cumplida y libera sus recursos. Con el compromiso y la fila de inventario bloqueados (`SELECT ... FOR UPDATE`), descuenta la cantidad de lo comprometido: lo reutilizable vuelve a estar disponible y lo consumible sale del stock. Es idempotente por `actividad_referencia`. Cuando al compromiso no le queda nada pendiente, pasa a FINALIZADO.
- **Qué prueba este caso:** Desambiguar funciona, pero en la oferta 1 los 5 paramédicos ya se liberaron.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "actividad_referencia": "ACT-4-{{corrida}}",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "tipo_recurso": "PARAMEDICO",
  "cantidad": 1,
  "fecha": "{{fecha_cumplida}}",
  "observaciones": "Tarea cumplida",
  "oferta_referencia": "OF-1-{{corrida}}"
}
```

**Respuesta esperada: `409 Conflict`**

```json
{
  "codigo": "EXCEDE_PENDIENTE",
  "detalles": {
    "pedida": "1.00",
    "pendiente": "0.00",
    "tipo_recurso": "PARAMEDICO"
  },
  "mensaje": "La cantidad supera lo comprometido que falta liberar."
}
```

### 2.12 Con oferta_referencia del consorcio: terminó 1 de los 2 paramédicos

- **Pedido:** `POST {{base_url}}/actividades`
- **Token (pestaña Authorization):** `{{token_webapp}}` (*Bearer Token*)
- **Qué hace el endpoint:** Registra una actividad cumplida y libera sus recursos. Con el compromiso y la fila de inventario bloqueados (`SELECT ... FOR UPDATE`), descuenta la cantidad de lo comprometido: lo reutilizable vuelve a estar disponible y lo consumible sale del stock. Es idempotente por `actividad_referencia`. Cuando al compromiso no le queda nada pendiente, pasa a FINALIZADO.
- **Qué prueba este caso:** Se libera del compromiso correcto. Queda 1 paramédico pendiente en el consorcio.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "actividad_referencia": "ACT-4-{{corrida}}",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "tipo_recurso": "PARAMEDICO",
  "cantidad": 1,
  "fecha": "{{fecha_cumplida}}",
  "observaciones": "Tarea cumplida",
  "oferta_referencia": "OF-CONSORCIO-{{corrida}}"
}
```

**Respuesta esperada: `201 Created`**

```json
{
  "accion": "LIBERADO",
  "actividad_referencia": "ACT-4-{{corrida}}",
  "cantidad": "1.00",
  "compromiso_id": "<id>",
  "creado_en": "<fecha y hora>",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "estado_compromiso": "COMPROMETIDO",
  "fecha": "<fecha y hora>",
  "id": "<id>",
  "item": {
    "cantidad_comprometida": "2.00",
    "cantidad_liberada": "1.00",
    "cantidad_pendiente": "1.00",
    "tipo_recurso": {
      "codigo": "PARAMEDICO",
      "nombre": "Paramédico"
    }
  },
  "observaciones": "Tarea cumplida",
  "oferta_referencia": "OF-CONSORCIO-{{corrida}}",
  "ong": {
    "cuit": "{{ong_cuit}}",
    "id": "<id>",
    "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
  },
  "origen": "INFORMADA",
  "registrada_por": "<id de la cuenta>",
  "tipo_recurso": {
    "codigo": "PARAMEDICO",
    "nombre": "Paramédico"
  }
}
```


## 3. Liberación de los recursos de la emergencia (Liberar recursos)

### 3.1 Estado de la emergencia: quedan 300 raciones y 1 paramédico

- **Pedido:** `GET {{base_url}}/emergencias/EMG-1-{{corrida}}/liberacion`
- **Token (pestaña Authorization):** `{{token_bonita}}` (*Bearer Token*)
- **Qué hace el endpoint:** Qué queda por liberar en la emergencia, por compromiso e ítem, con `todo_liberado` (lo que Bonita necesita para *Finalizaron todas las tareas?*), las reservas vigentes y el cierre, si existe.
- **Qué prueba este caso:** Dos compromisos COMPROMETIDO con pendiente y una reserva vigente (la oferta 2). `todo_liberado` sigue en false: Bonita vuelve a *Monitorear recursos*.

**Respuesta esperada: `200 OK`**

```json
{
  "cerrado": false,
  "cierre": null,
  "compromisos": [
    {
      "estado": "COMPROMETIDO",
      "finalizado_en": null,
      "id": "<id>",
      "items": [
        {
          "cantidad_comprometida": "5.00",
          "cantidad_liberada": "5.00",
          "cantidad_pendiente": "0.00",
          "tipo_recurso": {
            "codigo": "PARAMEDICO",
            "nombre": "Paramédico"
          }
        },
        {
          "cantidad_comprometida": "800.00",
          "cantidad_liberada": "500.00",
          "cantidad_pendiente": "300.00",
          "tipo_recurso": {
            "codigo": "RACION_ALIMENTO",
            "nombre": "Ración de alimento"
          }
        }
      ],
      "oferta_referencia": "OF-1-{{corrida}}",
      "ong": {
        "cuit": "{{ong_cuit}}",
        "id": "<id>",
        "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
      }
    },
    {
      "estado": "RESERVADO",
      "finalizado_en": null,
      "id": "<id>",
      "items": [
        {
          "cantidad_comprometida": "0.00",
          "cantidad_liberada": "0.00",
          "cantidad_pendiente": "0.00",
          "tipo_recurso": {
            "codigo": "RESCATISTA",
            "nombre": "Rescatista"
          }
        }
      ],
      "oferta_referencia": "OF-2-{{corrida}}",
      "ong": {
        "cuit": "{{ong_cuit}}",
        "id": "<id>",
        "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
      }
    },
    {
      "estado": "COMPROMETIDO",
      "finalizado_en": null,
      "id": "<id>",
      "items": [
        {
          "cantidad_comprometida": "2.00",
          "cantidad_liberada": "1.00",
          "cantidad_pendiente": "1.00",
          "tipo_recurso": {
            "codigo": "PARAMEDICO",
            "nombre": "Paramédico"
          }
        }
      ],
      "oferta_referencia": "OF-CONSORCIO-{{corrida}}",
      "ong": {
        "cuit": "{{ong_cuit}}",
        "id": "<id>",
        "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
      }
    }
  ],
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "reservas_vigentes": 1,
  "todo_liberado": false
}
```

### 3.2 Cerrar el proyecto antes de liberar

- **Pedido:** `POST {{base_url}}/emergencias/EMG-1-{{corrida}}/cierre`
- **Token (pestaña Authorization):** `{{token_bonita}}` (*Bearer Token*)
- **Qué hace el endpoint:** *Cerrar proyecto* (tarea de servicio del proceso): registra el cierre solo si no queda nada comprometido; si queda, responde 409 RECURSOS_SIN_LIBERAR. Repetirlo devuelve el mismo cierre con 200.
- **Qué prueba este caso:** El cierre no libera nada: con recursos comprometidos responde 409 y dice cuáles son. Hay que informar las actividades o liberar la emergencia primero.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "observaciones": "Fin del operativo"
}
```

**Respuesta esperada: `409 Conflict`**

```json
{
  "codigo": "RECURSOS_SIN_LIBERAR",
  "detalles": {
    "compromisos": [
      {
        "id": "<id>",
        "oferta_referencia": "OF-1-{{corrida}}",
        "ong_cuit": "{{ong_cuit}}",
        "pendiente": {
          "RACION_ALIMENTO": "300.00"
        }
      },
      {
        "id": "<id>",
        "oferta_referencia": "OF-CONSORCIO-{{corrida}}",
        "ong_cuit": "{{ong_cuit}}",
        "pendiente": {
          "PARAMEDICO": "1.00"
        }
      }
    ]
  },
  "mensaje": "Quedan recursos comprometidos sin liberar: informá las actividades o liberá la emergencia antes de cerrarla."
}
```

### 3.3 Bonita libera los recursos de la emergencia

- **Pedido:** `POST {{base_url}}/emergencias/EMG-1-{{corrida}}/liberacion`
- **Token (pestaña Authorization):** `{{token_bonita}}` (*Bearer Token*)
- **Qué hace el endpoint:** *Liberar recursos* (tarea de servicio del proceso): libera todo lo que siga comprometido en la emergencia, con origen CIERRE, y finaliza esos compromisos. Es idempotente y no toca las reservas sin adjudicar.
- **Qué prueba este caso:** Lo que las ONGs no informaron se libera igual: 300 raciones (CONSUMIDO) y 1 paramédico (LIBERADO), las dos con origen CIERRE y sin `actividad_referencia`. Los dos compromisos pasan a FINALIZADO. La reserva de la oferta 2 no se toca.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "observaciones": "Informe relevado por el Centro Coordinador"
}
```

**Respuesta esperada: `200 OK`**

```json
{
  "cerrado": false,
  "cierre": null,
  "compromisos": [
    {
      "estado": "FINALIZADO",
      "finalizado_en": "<fecha y hora>",
      "id": "<id>",
      "items": [
        {
          "cantidad_comprometida": "5.00",
          "cantidad_liberada": "5.00",
          "cantidad_pendiente": "0.00",
          "tipo_recurso": {
            "codigo": "PARAMEDICO",
            "nombre": "Paramédico"
          }
        },
        {
          "cantidad_comprometida": "800.00",
          "cantidad_liberada": "800.00",
          "cantidad_pendiente": "0.00",
          "tipo_recurso": {
            "codigo": "RACION_ALIMENTO",
            "nombre": "Ración de alimento"
          }
        }
      ],
      "oferta_referencia": "OF-1-{{corrida}}",
      "ong": {
        "cuit": "{{ong_cuit}}",
        "id": "<id>",
        "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
      }
    },
    {
      "estado": "RESERVADO",
      "finalizado_en": null,
      "id": "<id>",
      "items": [
        {
          "cantidad_comprometida": "0.00",
          "cantidad_liberada": "0.00",
          "cantidad_pendiente": "0.00",
          "tipo_recurso": {
            "codigo": "RESCATISTA",
            "nombre": "Rescatista"
          }
        }
      ],
      "oferta_referencia": "OF-2-{{corrida}}",
      "ong": {
        "cuit": "{{ong_cuit}}",
        "id": "<id>",
        "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
      }
    },
    {
      "estado": "FINALIZADO",
      "finalizado_en": "<fecha y hora>",
      "id": "<id>",
      "items": [
        {
          "cantidad_comprometida": "2.00",
          "cantidad_liberada": "2.00",
          "cantidad_pendiente": "0.00",
          "tipo_recurso": {
            "codigo": "PARAMEDICO",
            "nombre": "Paramédico"
          }
        }
      ],
      "oferta_referencia": "OF-CONSORCIO-{{corrida}}",
      "ong": {
        "cuit": "{{ong_cuit}}",
        "id": "<id>",
        "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
      }
    }
  ],
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "liberaciones": [
    {
      "accion": "CONSUMIDO",
      "actividad_referencia": null,
      "cantidad": "300.00",
      "compromiso_id": "<id>",
      "creado_en": "<fecha y hora>",
      "emergencia_referencia": "EMG-1-{{corrida}}",
      "estado_compromiso": "FINALIZADO",
      "fecha": "<fecha y hora>",
      "id": "<id>",
      "item": {
        "cantidad_comprometida": "800.00",
        "cantidad_liberada": "800.00",
        "cantidad_pendiente": "0.00",
        "tipo_recurso": {
          "codigo": "RACION_ALIMENTO",
          "nombre": "Ración de alimento"
        }
      },
      "observaciones": "Informe relevado por el Centro Coordinador",
      "oferta_referencia": "OF-1-{{corrida}}",
      "ong": {
        "cuit": "{{ong_cuit}}",
        "id": "<id>",
        "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
      },
      "origen": "CIERRE",
      "registrada_por": "<id de la cuenta>",
      "tipo_recurso": {
        "codigo": "RACION_ALIMENTO",
        "nombre": "Ración de alimento"
      }
    },
    {
      "accion": "LIBERADO",
      "actividad_referencia": null,
      "cantidad": "1.00",
      "compromiso_id": "<id>",
      "creado_en": "<fecha y hora>",
      "emergencia_referencia": "EMG-1-{{corrida}}",
      "estado_compromiso": "FINALIZADO",
      "fecha": "<fecha y hora>",
      "id": "<id>",
      "item": {
        "cantidad_comprometida": "2.00",
        "cantidad_liberada": "2.00",
        "cantidad_pendiente": "0.00",
        "tipo_recurso": {
          "codigo": "PARAMEDICO",
          "nombre": "Paramédico"
        }
      },
      "observaciones": "Informe relevado por el Centro Coordinador",
      "oferta_referencia": "OF-CONSORCIO-{{corrida}}",
      "ong": {
        "cuit": "{{ong_cuit}}",
        "id": "<id>",
        "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
      },
      "origen": "CIERRE",
      "registrada_por": "<id de la cuenta>",
      "tipo_recurso": {
        "codigo": "PARAMEDICO",
        "nombre": "Paramédico"
      }
    }
  ],
  "reservas_vigentes": 1,
  "todo_liberado": true
}
```

### 3.4 Repetir la liberación

- **Pedido:** `POST {{base_url}}/emergencias/EMG-1-{{corrida}}/liberacion`
- **Token (pestaña Authorization):** `{{token_bonita}}` (*Bearer Token*)
- **Qué hace el endpoint:** *Liberar recursos* (tarea de servicio del proceso): libera todo lo que siga comprometido en la emergencia, con origen CIERRE, y finaliza esos compromisos. Es idempotente y no toca las reservas sin adjudicar.
- **Qué prueba este caso:** Es idempotente: no quedaba nada pendiente, así que `liberaciones` viene vacío y nada cambia.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{}
```

**Respuesta esperada: `200 OK`**

```json
{
  "cerrado": false,
  "cierre": null,
  "compromisos": [
    {
      "estado": "FINALIZADO",
      "finalizado_en": "<fecha y hora>",
      "id": "<id>",
      "items": [
        {
          "cantidad_comprometida": "5.00",
          "cantidad_liberada": "5.00",
          "cantidad_pendiente": "0.00",
          "tipo_recurso": {
            "codigo": "PARAMEDICO",
            "nombre": "Paramédico"
          }
        },
        {
          "cantidad_comprometida": "800.00",
          "cantidad_liberada": "800.00",
          "cantidad_pendiente": "0.00",
          "tipo_recurso": {
            "codigo": "RACION_ALIMENTO",
            "nombre": "Ración de alimento"
          }
        }
      ],
      "oferta_referencia": "OF-1-{{corrida}}",
      "ong": {
        "cuit": "{{ong_cuit}}",
        "id": "<id>",
        "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
      }
    },
    {
      "estado": "RESERVADO",
      "finalizado_en": null,
      "id": "<id>",
      "items": [
        {
          "cantidad_comprometida": "0.00",
          "cantidad_liberada": "0.00",
          "cantidad_pendiente": "0.00",
          "tipo_recurso": {
            "codigo": "RESCATISTA",
            "nombre": "Rescatista"
          }
        }
      ],
      "oferta_referencia": "OF-2-{{corrida}}",
      "ong": {
        "cuit": "{{ong_cuit}}",
        "id": "<id>",
        "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
      }
    },
    {
      "estado": "FINALIZADO",
      "finalizado_en": "<fecha y hora>",
      "id": "<id>",
      "items": [
        {
          "cantidad_comprometida": "2.00",
          "cantidad_liberada": "2.00",
          "cantidad_pendiente": "0.00",
          "tipo_recurso": {
            "codigo": "PARAMEDICO",
            "nombre": "Paramédico"
          }
        }
      ],
      "oferta_referencia": "OF-CONSORCIO-{{corrida}}",
      "ong": {
        "cuit": "{{ong_cuit}}",
        "id": "<id>",
        "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
      }
    }
  ],
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "liberaciones": [],
  "reservas_vigentes": 1,
  "todo_liberado": true
}
```

### 3.5 Inventario después de liberar la emergencia

- **Pedido:** `GET {{base_url}}/ongs/{{ong_id}}/recursos`
- **Token (pestaña Authorization):** `{{token_auditor}}` (*Bearer Token*)
- **Qué hace el endpoint:** Inventario y disponibilidad de la ONG (punto I-3.2): `cantidad_total`, `cantidad_bloqueada` (reservas), `cantidad_comprometida` (adjudicado en ejecución) y `cantidad_disponible = total - bloqueada - comprometida`.
- **Qué prueba este caso:** Nada comprometido. Las raciones quedaron en 1200 (se consumieron 800 en total) y los 4 rescatistas de la oferta 2 siguen bloqueados por su reserva.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cantidad_bloqueada": "0.00",
    "cantidad_comprometida": "0.00",
    "cantidad_disponible": "10.00",
    "cantidad_total": "10.00",
    "tipo_recurso": {
      "categoria": "PERSONAL",
      "codigo": "PARAMEDICO",
      "id": "<id>",
      "nombre": "Paramédico",
      "reutilizable": true,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "PERSONA",
        "id": "<id>",
        "nombre": "Personas"
      }
    }
  },
  {
    "cantidad_bloqueada": "0.00",
    "cantidad_comprometida": "0.00",
    "cantidad_disponible": "1200.00",
    "cantidad_total": "1200.00",
    "tipo_recurso": {
      "categoria": "MATERIAL",
      "codigo": "RACION_ALIMENTO",
      "id": "<id>",
      "nombre": "Ración de alimento",
      "reutilizable": false,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "RACION",
        "id": "<id>",
        "nombre": "Raciones"
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
      "id": "<id>",
      "nombre": "Rescatista",
      "reutilizable": true,
      "unidad_medida": {
        "admite_decimales": false,
        "codigo": "PERSONA",
        "id": "<id>",
        "nombre": "Personas"
      }
    }
  }
]
```


## 4. Cierre del proyecto (Cerrar proyecto)

### 4.1 Bonita cierra el proyecto

- **Pedido:** `POST {{base_url}}/emergencias/EMG-1-{{corrida}}/cierre`
- **Token (pestaña Authorization):** `{{token_bonita}}` (*Bearer Token*)
- **Qué hace el endpoint:** *Cerrar proyecto* (tarea de servicio del proceso): registra el cierre solo si no queda nada comprometido; si queda, responde 409 RECURSOS_SIN_LIBERAR. Repetirlo devuelve el mismo cierre con 200.
- **Qué prueba este caso:** Ya no queda nada comprometido. Guarda la fecha de cierre en `fecha_cierre` para compararla en el reintento.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "observaciones": "Fin del operativo"
}
```

**Respuesta esperada: `201 Created`**

```json
{
  "cerrado_por": "<id de la cuenta>",
  "creado_en": "<fecha y hora>",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "fecha_cierre": "<fecha y hora>",
  "observaciones": "Fin del operativo"
}
```

### 4.2 Repetir el cierre

- **Pedido:** `POST {{base_url}}/emergencias/EMG-1-{{corrida}}/cierre`
- **Token (pestaña Authorization):** `{{token_webapp}}` (*Bearer Token*)
- **Qué hace el endpoint:** *Cerrar proyecto* (tarea de servicio del proceso): registra el cierre solo si no queda nada comprometido; si queda, responde 409 RECURSOS_SIN_LIBERAR. Repetirlo devuelve el mismo cierre con 200.
- **Qué prueba este caso:** Devuelve el mismo cierre con 200: la fecha es la de la primera llamada.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{}
```

**Respuesta esperada: `200 OK`**

```json
{
  "cerrado_por": "<id de la cuenta>",
  "creado_en": "<fecha y hora>",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "fecha_cierre": "<fecha y hora>",
  "observaciones": "Fin del operativo"
}
```

### 4.3 Estado de la emergencia cerrada

- **Pedido:** `GET {{base_url}}/emergencias/EMG-1-{{corrida}}/liberacion`
- **Token (pestaña Authorization):** `{{token_auditor}}` (*Bearer Token*)
- **Qué hace el endpoint:** Qué queda por liberar en la emergencia, por compromiso e ítem, con `todo_liberado` (lo que Bonita necesita para *Finalizaron todas las tareas?*), las reservas vigentes y el cierre, si existe.
- **Qué prueba este caso:** `cerrado` en true y el cierre con sus datos.

**Respuesta esperada: `200 OK`**

```json
{
  "cerrado": true,
  "cierre": {
    "cerrado_por": "<id de la cuenta>",
    "creado_en": "<fecha y hora>",
    "emergencia_referencia": "EMG-1-{{corrida}}",
    "fecha_cierre": "<fecha y hora>",
    "observaciones": "Fin del operativo"
  },
  "compromisos": [
    {
      "estado": "FINALIZADO",
      "finalizado_en": "<fecha y hora>",
      "id": "<id>",
      "items": [
        {
          "cantidad_comprometida": "5.00",
          "cantidad_liberada": "5.00",
          "cantidad_pendiente": "0.00",
          "tipo_recurso": {
            "codigo": "PARAMEDICO",
            "nombre": "Paramédico"
          }
        },
        {
          "cantidad_comprometida": "800.00",
          "cantidad_liberada": "800.00",
          "cantidad_pendiente": "0.00",
          "tipo_recurso": {
            "codigo": "RACION_ALIMENTO",
            "nombre": "Ración de alimento"
          }
        }
      ],
      "oferta_referencia": "OF-1-{{corrida}}",
      "ong": {
        "cuit": "{{ong_cuit}}",
        "id": "<id>",
        "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
      }
    },
    {
      "estado": "RESERVADO",
      "finalizado_en": null,
      "id": "<id>",
      "items": [
        {
          "cantidad_comprometida": "0.00",
          "cantidad_liberada": "0.00",
          "cantidad_pendiente": "0.00",
          "tipo_recurso": {
            "codigo": "RESCATISTA",
            "nombre": "Rescatista"
          }
        }
      ],
      "oferta_referencia": "OF-2-{{corrida}}",
      "ong": {
        "cuit": "{{ong_cuit}}",
        "id": "<id>",
        "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
      }
    },
    {
      "estado": "FINALIZADO",
      "finalizado_en": "<fecha y hora>",
      "id": "<id>",
      "items": [
        {
          "cantidad_comprometida": "2.00",
          "cantidad_liberada": "2.00",
          "cantidad_pendiente": "0.00",
          "tipo_recurso": {
            "codigo": "PARAMEDICO",
            "nombre": "Paramédico"
          }
        }
      ],
      "oferta_referencia": "OF-CONSORCIO-{{corrida}}",
      "ong": {
        "cuit": "{{ong_cuit}}",
        "id": "<id>",
        "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
      }
    }
  ],
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "reservas_vigentes": 1,
  "todo_liberado": true
}
```

### 4.4 Una actividad después del cierre

- **Pedido:** `POST {{base_url}}/actividades`
- **Token (pestaña Authorization):** `{{token_webapp}}` (*Bearer Token*)
- **Qué hace el endpoint:** Registra una actividad cumplida y libera sus recursos. Con el compromiso y la fila de inventario bloqueados (`SELECT ... FOR UPDATE`), descuenta la cantidad de lo comprometido: lo reutilizable vuelve a estar disponible y lo consumible sale del stock. Es idempotente por `actividad_referencia`. Cuando al compromiso no le queda nada pendiente, pasa a FINALIZADO.
- **Qué prueba este caso:** El proyecto terminó: no se aceptan más actividades para la emergencia.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "actividad_referencia": "ACT-5-{{corrida}}",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "tipo_recurso": "PARAMEDICO",
  "cantidad": 1,
  "fecha": "{{fecha_cumplida}}",
  "observaciones": "Tarea cumplida"
}
```

**Respuesta esperada: `409 Conflict`**

```json
{
  "codigo": "PROYECTO_CERRADO",
  "detalles": {
    "fecha_cierre": "<fecha y hora>"
  },
  "mensaje": "El proyecto de la emergencia ya está cerrado."
}
```

### 4.5 Liberar después del cierre

- **Pedido:** `POST {{base_url}}/emergencias/EMG-1-{{corrida}}/liberacion`
- **Token (pestaña Authorization):** `{{token_bonita}}` (*Bearer Token*)
- **Qué hace el endpoint:** *Liberar recursos* (tarea de servicio del proceso): libera todo lo que siga comprometido en la emergencia, con origen CIERRE, y finaliza esos compromisos. Es idempotente y no toca las reservas sin adjudicar.
- **Qué prueba este caso:** Tampoco se libera: el orden del proceso es liberar y después cerrar.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{}
```

**Respuesta esperada: `409 Conflict`**

```json
{
  "codigo": "PROYECTO_CERRADO",
  "detalles": {
    "fecha_cierre": "<fecha y hora>"
  },
  "mensaje": "El proyecto de la emergencia ya está cerrado."
}
```

### 4.6 Una emergencia que el Sistema Nacional no conoce

- **Pedido:** `POST {{base_url}}/emergencias/no-existe/cierre`
- **Token (pestaña Authorization):** `{{token_bonita}}` (*Bearer Token*)
- **Qué hace el endpoint:** *Cerrar proyecto* (tarea de servicio del proceso): registra el cierre solo si no queda nada comprometido; si queda, responde 409 RECURSOS_SIN_LIBERAR. Repetirlo devuelve el mismo cierre con 200.
- **Qué prueba este caso:** Ninguna convocatoria nombra esa emergencia.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{}
```

**Respuesta esperada: `404 Not Found`**

```json
{
  "codigo": "NO_ENCONTRADO",
  "detalles": {
    "emergencia_referencia": "no-existe"
  },
  "mensaje": "El Sistema Nacional no conoce esa emergencia: ninguna convocatoria la nombra."
}
```


## 5. Historial de actividades y liberaciones

### 5.1 Todo lo liberado en la emergencia

- **Pedido:** `GET {{base_url}}/actividades?emergencia=EMG-1-{{corrida}}`
- **Token (pestaña Authorization):** `{{token_auditor}}` (*Bearer Token*)
- **Qué hace el endpoint:** Historial paginado de actividades y liberaciones, de la más reciente a la más antigua. Filtros: `emergencia`, `ong_cuit`, `tipo_recurso`, `origen` y `compromiso_id`.
- **Qué prueba este caso:** Cuatro actividades informadas por la ONG y dos liberaciones del cierre, de la más reciente a la más antigua.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "accion": "LIBERADO",
    "actividad_referencia": null,
    "cantidad": "1.00",
    "compromiso_id": "<id>",
    "creado_en": "<fecha y hora>",
    "emergencia_referencia": "EMG-1-{{corrida}}",
    "estado_compromiso": "FINALIZADO",
    "fecha": "<fecha y hora>",
    "id": "<id>",
    "item": {
      "cantidad_comprometida": "2.00",
      "cantidad_liberada": "2.00",
      "cantidad_pendiente": "0.00",
      "tipo_recurso": {
        "codigo": "PARAMEDICO",
        "nombre": "Paramédico"
      }
    },
    "observaciones": "Informe relevado por el Centro Coordinador",
    "oferta_referencia": "OF-CONSORCIO-{{corrida}}",
    "ong": {
      "cuit": "{{ong_cuit}}",
      "id": "<id>",
      "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
    },
    "origen": "CIERRE",
    "registrada_por": "<id de la cuenta>",
    "tipo_recurso": {
      "codigo": "PARAMEDICO",
      "nombre": "Paramédico"
    }
  },
  {
    "accion": "CONSUMIDO",
    "actividad_referencia": null,
    "cantidad": "300.00",
    "compromiso_id": "<id>",
    "creado_en": "<fecha y hora>",
    "emergencia_referencia": "EMG-1-{{corrida}}",
    "estado_compromiso": "FINALIZADO",
    "fecha": "<fecha y hora>",
    "id": "<id>",
    "item": {
      "cantidad_comprometida": "800.00",
      "cantidad_liberada": "800.00",
      "cantidad_pendiente": "0.00",
      "tipo_recurso": {
        "codigo": "RACION_ALIMENTO",
        "nombre": "Ración de alimento"
      }
    },
    "observaciones": "Informe relevado por el Centro Coordinador",
    "oferta_referencia": "OF-1-{{corrida}}",
    "ong": {
      "cuit": "{{ong_cuit}}",
      "id": "<id>",
      "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
    },
    "origen": "CIERRE",
    "registrada_por": "<id de la cuenta>",
    "tipo_recurso": {
      "codigo": "RACION_ALIMENTO",
      "nombre": "Ración de alimento"
    }
  },
  {
    "accion": "LIBERADO",
    "actividad_referencia": "ACT-4-{{corrida}}",
    "cantidad": "1.00",
    "compromiso_id": "<id>",
    "creado_en": "<fecha y hora>",
    "emergencia_referencia": "EMG-1-{{corrida}}",
    "estado_compromiso": "FINALIZADO",
    "fecha": "<fecha y hora>",
    "id": "<id>",
    "item": {
      "cantidad_comprometida": "2.00",
      "cantidad_liberada": "2.00",
      "cantidad_pendiente": "0.00",
      "tipo_recurso": {
        "codigo": "PARAMEDICO",
        "nombre": "Paramédico"
      }
    },
    "observaciones": "Tarea cumplida",
    "oferta_referencia": "OF-CONSORCIO-{{corrida}}",
    "ong": {
      "cuit": "{{ong_cuit}}",
      "id": "<id>",
      "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
    },
    "origen": "INFORMADA",
    "registrada_por": "<id de la cuenta>",
    "tipo_recurso": {
      "codigo": "PARAMEDICO",
      "nombre": "Paramédico"
    }
  },
  {
    "accion": "LIBERADO",
    "actividad_referencia": "ACT-3-{{corrida}}",
    "cantidad": "2.00",
    "compromiso_id": "<id>",
    "creado_en": "<fecha y hora>",
    "emergencia_referencia": "EMG-1-{{corrida}}",
    "estado_compromiso": "FINALIZADO",
    "fecha": "<fecha y hora>",
    "id": "<id>",
    "item": {
      "cantidad_comprometida": "5.00",
      "cantidad_liberada": "5.00",
      "cantidad_pendiente": "0.00",
      "tipo_recurso": {
        "codigo": "PARAMEDICO",
        "nombre": "Paramédico"
      }
    },
    "observaciones": "Tarea cumplida",
    "oferta_referencia": "OF-1-{{corrida}}",
    "ong": {
      "cuit": "{{ong_cuit}}",
      "id": "<id>",
      "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
    },
    "origen": "INFORMADA",
    "registrada_por": "<id de la cuenta>",
    "tipo_recurso": {
      "codigo": "PARAMEDICO",
      "nombre": "Paramédico"
    }
  },
  {
    "accion": "CONSUMIDO",
    "actividad_referencia": "ACT-2-{{corrida}}",
    "cantidad": "500.00",
    "compromiso_id": "<id>",
    "creado_en": "<fecha y hora>",
    "emergencia_referencia": "EMG-1-{{corrida}}",
    "estado_compromiso": "FINALIZADO",
    "fecha": "<fecha y hora>",
    "id": "<id>",
    "item": {
      "cantidad_comprometida": "800.00",
      "cantidad_liberada": "800.00",
      "cantidad_pendiente": "0.00",
      "tipo_recurso": {
        "codigo": "RACION_ALIMENTO",
        "nombre": "Ración de alimento"
      }
    },
    "observaciones": "Entregadas en el centro de evacuados",
    "oferta_referencia": "OF-1-{{corrida}}",
    "ong": {
      "cuit": "{{ong_cuit}}",
      "id": "<id>",
      "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
    },
    "origen": "INFORMADA",
    "registrada_por": "<id de la cuenta>",
    "tipo_recurso": {
      "codigo": "RACION_ALIMENTO",
      "nombre": "Ración de alimento"
    }
  },
  {
    "accion": "LIBERADO",
    "actividad_referencia": "ACT-1-{{corrida}}",
    "cantidad": "3.00",
    "compromiso_id": "<id>",
    "creado_en": "<fecha y hora>",
    "emergencia_referencia": "EMG-1-{{corrida}}",
    "estado_compromiso": "FINALIZADO",
    "fecha": "<fecha y hora>",
    "id": "<id>",
    "item": {
      "cantidad_comprometida": "5.00",
      "cantidad_liberada": "5.00",
      "cantidad_pendiente": "0.00",
      "tipo_recurso": {
        "codigo": "PARAMEDICO",
        "nombre": "Paramédico"
      }
    },
    "observaciones": "Evacuación del barrio Norte terminada",
    "oferta_referencia": "OF-1-{{corrida}}",
    "ong": {
      "cuit": "{{ong_cuit}}",
      "id": "<id>",
      "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
    },
    "origen": "INFORMADA",
    "registrada_por": "<id de la cuenta>",
    "tipo_recurso": {
      "codigo": "PARAMEDICO",
      "nombre": "Paramédico"
    }
  }
]
```

### 5.2 Solo lo que liberó el cierre

- **Pedido:** `GET {{base_url}}/actividades?emergencia=EMG-1-{{corrida}}&origen=CIERRE`
- **Token (pestaña Authorization):** `{{token_auditor}}` (*Bearer Token*)
- **Qué hace el endpoint:** Historial paginado de actividades y liberaciones, de la más reciente a la más antigua. Filtros: `emergencia`, `ong_cuit`, `tipo_recurso`, `origen` y `compromiso_id`.
- **Qué prueba este caso:** Las dos liberaciones de *Liberar recursos*.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "accion": "LIBERADO",
    "actividad_referencia": null,
    "cantidad": "1.00",
    "compromiso_id": "<id>",
    "creado_en": "<fecha y hora>",
    "emergencia_referencia": "EMG-1-{{corrida}}",
    "estado_compromiso": "FINALIZADO",
    "fecha": "<fecha y hora>",
    "id": "<id>",
    "item": {
      "cantidad_comprometida": "2.00",
      "cantidad_liberada": "2.00",
      "cantidad_pendiente": "0.00",
      "tipo_recurso": {
        "codigo": "PARAMEDICO",
        "nombre": "Paramédico"
      }
    },
    "observaciones": "Informe relevado por el Centro Coordinador",
    "oferta_referencia": "OF-CONSORCIO-{{corrida}}",
    "ong": {
      "cuit": "{{ong_cuit}}",
      "id": "<id>",
      "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
    },
    "origen": "CIERRE",
    "registrada_por": "<id de la cuenta>",
    "tipo_recurso": {
      "codigo": "PARAMEDICO",
      "nombre": "Paramédico"
    }
  },
  {
    "accion": "CONSUMIDO",
    "actividad_referencia": null,
    "cantidad": "300.00",
    "compromiso_id": "<id>",
    "creado_en": "<fecha y hora>",
    "emergencia_referencia": "EMG-1-{{corrida}}",
    "estado_compromiso": "FINALIZADO",
    "fecha": "<fecha y hora>",
    "id": "<id>",
    "item": {
      "cantidad_comprometida": "800.00",
      "cantidad_liberada": "800.00",
      "cantidad_pendiente": "0.00",
      "tipo_recurso": {
        "codigo": "RACION_ALIMENTO",
        "nombre": "Ración de alimento"
      }
    },
    "observaciones": "Informe relevado por el Centro Coordinador",
    "oferta_referencia": "OF-1-{{corrida}}",
    "ong": {
      "cuit": "{{ong_cuit}}",
      "id": "<id>",
      "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
    },
    "origen": "CIERRE",
    "registrada_por": "<id de la cuenta>",
    "tipo_recurso": {
      "codigo": "RACION_ALIMENTO",
      "nombre": "Ración de alimento"
    }
  }
]
```

### 5.3 Las raciones de la ONG

- **Pedido:** `GET {{base_url}}/actividades?ong_cuit={{ong_cuit}}&tipo_recurso=RACION_ALIMENTO`
- **Token (pestaña Authorization):** `{{token_auditor}}` (*Bearer Token*)
- **Qué hace el endpoint:** Historial paginado de actividades y liberaciones, de la más reciente a la más antigua. Filtros: `emergencia`, `ong_cuit`, `tipo_recurso`, `origen` y `compromiso_id`.
- **Qué prueba este caso:** Las 500 informadas y las 300 del cierre: 800 raciones consumidas en total.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "accion": "CONSUMIDO",
    "actividad_referencia": null,
    "cantidad": "300.00",
    "compromiso_id": "<id>",
    "creado_en": "<fecha y hora>",
    "emergencia_referencia": "EMG-1-{{corrida}}",
    "estado_compromiso": "FINALIZADO",
    "fecha": "<fecha y hora>",
    "id": "<id>",
    "item": {
      "cantidad_comprometida": "800.00",
      "cantidad_liberada": "800.00",
      "cantidad_pendiente": "0.00",
      "tipo_recurso": {
        "codigo": "RACION_ALIMENTO",
        "nombre": "Ración de alimento"
      }
    },
    "observaciones": "Informe relevado por el Centro Coordinador",
    "oferta_referencia": "OF-1-{{corrida}}",
    "ong": {
      "cuit": "{{ong_cuit}}",
      "id": "<id>",
      "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
    },
    "origen": "CIERRE",
    "registrada_por": "<id de la cuenta>",
    "tipo_recurso": {
      "codigo": "RACION_ALIMENTO",
      "nombre": "Ración de alimento"
    }
  },
  {
    "accion": "CONSUMIDO",
    "actividad_referencia": "ACT-2-{{corrida}}",
    "cantidad": "500.00",
    "compromiso_id": "<id>",
    "creado_en": "<fecha y hora>",
    "emergencia_referencia": "EMG-1-{{corrida}}",
    "estado_compromiso": "FINALIZADO",
    "fecha": "<fecha y hora>",
    "id": "<id>",
    "item": {
      "cantidad_comprometida": "800.00",
      "cantidad_liberada": "800.00",
      "cantidad_pendiente": "0.00",
      "tipo_recurso": {
        "codigo": "RACION_ALIMENTO",
        "nombre": "Ración de alimento"
      }
    },
    "observaciones": "Entregadas en el centro de evacuados",
    "oferta_referencia": "OF-1-{{corrida}}",
    "ong": {
      "cuit": "{{ong_cuit}}",
      "id": "<id>",
      "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
    },
    "origen": "INFORMADA",
    "registrada_por": "<id de la cuenta>",
    "tipo_recurso": {
      "codigo": "RACION_ALIMENTO",
      "nombre": "Ración de alimento"
    }
  }
]
```

### 5.4 Detalle de la primera actividad

- **Pedido:** `GET {{base_url}}/actividades/{{actividad_1}}`
- **Token (pestaña Authorization):** `{{token_auditor}}` (*Bearer Token*)
- **Qué hace el endpoint:** Detalle de una actividad.
- **Qué prueba este caso:** La actividad 1 tal como quedó, con el ítem ya liberado del todo y el compromiso FINALIZADO.

**Respuesta esperada: `200 OK`**

```json
{
  "accion": "LIBERADO",
  "actividad_referencia": "ACT-1-{{corrida}}",
  "cantidad": "3.00",
  "compromiso_id": "<id>",
  "creado_en": "<fecha y hora>",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "estado_compromiso": "FINALIZADO",
  "fecha": "<fecha y hora>",
  "id": "<id>",
  "item": {
    "cantidad_comprometida": "5.00",
    "cantidad_liberada": "5.00",
    "cantidad_pendiente": "0.00",
    "tipo_recurso": {
      "codigo": "PARAMEDICO",
      "nombre": "Paramédico"
    }
  },
  "observaciones": "Evacuación del barrio Norte terminada",
  "oferta_referencia": "OF-1-{{corrida}}",
  "ong": {
    "cuit": "{{ong_cuit}}",
    "id": "<id>",
    "razon_social": "Rescatistas de Prueba (Postman I-3.5)"
  },
  "origen": "INFORMADA",
  "registrada_por": "<id de la cuenta>",
  "tipo_recurso": {
    "codigo": "PARAMEDICO",
    "nombre": "Paramédico"
  }
}
```

### 5.5 Una actividad que no existe

- **Pedido:** `GET {{base_url}}/actividades/999999`
- **Token (pestaña Authorization):** `{{token_auditor}}` (*Bearer Token*)
- **Qué hace el endpoint:** Detalle de una actividad.

**Respuesta esperada: `404 Not Found`**

```json
{
  "codigo": "NO_ENCONTRADO",
  "detalles": {},
  "mensaje": "La actividad no existe."
}
```


## 6. Seguridad

### 6.1 Informar una actividad sin token

- **Pedido:** `POST {{base_url}}/actividades`
- **Token (pestaña Authorization):** ninguno (*No Auth*)
- **Qué hace el endpoint:** Registra una actividad cumplida y libera sus recursos. Con el compromiso y la fila de inventario bloqueados (`SELECT ... FOR UPDATE`), descuenta la cantidad de lo comprometido: lo reutilizable vuelve a estar disponible y lo consumible sale del stock. Es idempotente por `actividad_referencia`. Cuando al compromiso no le queda nada pendiente, pasa a FINALIZADO.
- **Qué prueba este caso:** Todos los endpoints del punto exigen el JWT de una cuenta de servicio.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "actividad_referencia": "ACT-6-{{corrida}}",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "tipo_recurso": "PARAMEDICO",
  "cantidad": 1,
  "fecha": "{{fecha_cumplida}}",
  "observaciones": "Tarea cumplida"
}
```

**Respuesta esperada: `401 Unauthorized`**

```json
{
  "codigo": "NO_AUTENTICADO",
  "detalles": {},
  "mensaje": "Falta el token de acceso (Authorization: Bearer ...)."
}
```

### 6.2 Informar con un token inválido

- **Pedido:** `POST {{base_url}}/actividades`
- **Token (pestaña Authorization):** `no-es-un-token` (*Bearer Token*, un valor cualquiera)
- **Qué hace el endpoint:** Registra una actividad cumplida y libera sus recursos. Con el compromiso y la fila de inventario bloqueados (`SELECT ... FOR UPDATE`), descuenta la cantidad de lo comprometido: lo reutilizable vuelve a estar disponible y lo consumible sale del stock. Es idempotente por `actividad_referencia`. Cuando al compromiso no le queda nada pendiente, pasa a FINALIZADO.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "actividad_referencia": "ACT-6-{{corrida}}",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "tipo_recurso": "PARAMEDICO",
  "cantidad": 1,
  "fecha": "{{fecha_cumplida}}",
  "observaciones": "Tarea cumplida"
}
```

**Respuesta esperada: `401 Unauthorized`**

```json
{
  "codigo": "NO_AUTENTICADO",
  "detalles": {},
  "mensaje": "El token de acceso no es válido."
}
```

### 6.3 El auditor no puede informar actividades

- **Pedido:** `POST {{base_url}}/actividades`
- **Token (pestaña Authorization):** `{{token_auditor}}` (*Bearer Token*)
- **Qué hace el endpoint:** Registra una actividad cumplida y libera sus recursos. Con el compromiso y la fila de inventario bloqueados (`SELECT ... FOR UPDATE`), descuenta la cantidad de lo comprometido: lo reutilizable vuelve a estar disponible y lo consumible sale del stock. Es idempotente por `actividad_referencia`. Cuando al compromiso no le queda nada pendiente, pasa a FINALIZADO.
- **Qué prueba este caso:** El auditor solo consulta.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "actividad_referencia": "ACT-6-{{corrida}}",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "tipo_recurso": "PARAMEDICO",
  "cantidad": 1,
  "fecha": "{{fecha_cumplida}}",
  "observaciones": "Tarea cumplida"
}
```

**Respuesta esperada: `403 Forbidden`**

```json
{
  "codigo": "PROHIBIDO",
  "detalles": {},
  "mensaje": "El rol del token no permite esta operación."
}
```

### 6.4 El auditor no puede cerrar el proyecto

- **Pedido:** `POST {{base_url}}/emergencias/EMG-1-{{corrida}}/cierre`
- **Token (pestaña Authorization):** `{{token_auditor}}` (*Bearer Token*)
- **Qué hace el endpoint:** *Cerrar proyecto* (tarea de servicio del proceso): registra el cierre solo si no queda nada comprometido; si queda, responde 409 RECURSOS_SIN_LIBERAR. Repetirlo devuelve el mismo cierre con 200.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{}
```

**Respuesta esperada: `403 Forbidden`**

```json
{
  "codigo": "PROHIBIDO",
  "detalles": {},
  "mensaje": "El rol del token no permite esta operación."
}
```

### 6.5 Login de la ONG de prueba

- **Pedido:** `POST {{base_url}}/login`
- **Token (pestaña Authorization):** ninguno (*No Auth*)
- **Qué hace el endpoint:** Inicio de sesión (punto I-3.1). Devuelve un JWT con el rol de la cuenta en el claim `rol`. No pide token.
- **Qué prueba este caso:** La ONG registrada en 0.4 entra con su email. Guarda el token en `token_ong`.

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

### 6.6 La ONG no puede informar con su propio token

- **Pedido:** `POST {{base_url}}/actividades`
- **Token (pestaña Authorization):** `{{token_ong}}` (*Bearer Token*)
- **Qué hace el endpoint:** Registra una actividad cumplida y libera sus recursos. Con el compromiso y la fila de inventario bloqueados (`SELECT ... FOR UPDATE`), descuenta la cantidad de lo comprometido: lo reutilizable vuelve a estar disponible y lo consumible sale del stock. Es idempotente por `actividad_referencia`. Cuando al compromiso no le queda nada pendiente, pasa a FINALIZADO.
- **Qué prueba este caso:** La plataforma informa por la ONG [E-7]; un token de ONG no entra en este punto.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "actividad_referencia": "ACT-6-{{corrida}}",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "ong_cuit": "{{ong_cuit}}",
  "tipo_recurso": "PARAMEDICO",
  "cantidad": 1,
  "fecha": "{{fecha_cumplida}}",
  "observaciones": "Tarea cumplida"
}
```

**Respuesta esperada: `403 Forbidden`**

```json
{
  "codigo": "PROHIBIDO",
  "detalles": {},
  "mensaje": "El rol del token no permite esta operación."
}
```

### 6.7 Consultar el estado de la emergencia sin token

- **Pedido:** `GET {{base_url}}/emergencias/EMG-1-{{corrida}}/liberacion`
- **Token (pestaña Authorization):** ninguno (*No Auth*)
- **Qué hace el endpoint:** Qué queda por liberar en la emergencia, por compromiso e ítem, con `todo_liberado` (lo que Bonita necesita para *Finalizaron todas las tareas?*), las reservas vigentes y el cierre, si existe.

**Respuesta esperada: `401 Unauthorized`**

```json
{
  "codigo": "NO_AUTENTICADO",
  "detalles": {},
  "mensaje": "Falta el token de acceso (Authorization: Bearer ...)."
}
```
