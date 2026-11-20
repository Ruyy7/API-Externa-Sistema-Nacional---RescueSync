# Casos de prueba de I-3.6 en Postman: orquestación por Bonita

Las operaciones que invoca Bonita en cada tarea del proceso, en el orden en que las invoca. La cátedra fijó que la validación de competencias, el bloqueo y compromiso de recursos y la liberación los invoque **solo Bonita**, como orquestador: la aplicación web no llama a la API en el proceso. Esta colección hace con la cuenta `bonita` lo que hacen los conectores del proceso (`docs/rescue-sync_e5.bos` del repositorio de la webapp), y muestra que la API rechaza a la cuenta `webapp`. El contrato de cada operación está en `docs/08-orquestacion-bonita.md`.

Todos los casos se generaron ejecutándolos contra la API: las respuestas de abajo son las reales. Lo que cambia en cada corrida se muestra así: las fechas como `<fecha y hora>`, los ids como `<id>`, los tokens como `<token>`, y el CUIT, el email y el sufijo de la corrida como `{{ong_cuit}}`, `{{ong_email}}` y `{{corrida}}`.

| Tarea de Bonita | Operación de la API | Carpeta |
|---|---|---|
| *Validar ofertas* | `POST /emergencias/{ref}/bloqueo` | 1 |
| *Reabrir convocatoria* y *Reformular lotes* | `POST /emergencias/{ref}/desbloqueo` | 2 |
| *Comprometer recursos* | `POST /emergencias/{ref}/adjudicacion` | 3 |
| *Marcar actividad como finalizada* | `POST /emergencias/{ref}/actividades` | 4 |
| *Liberar recursos* | `POST /emergencias/{ref}/liberacion` | 5 |
| *Cerrar proyecto* | `POST /emergencias/{ref}/cierre` | 6 |

## Preparación

**1. Importar la colección en Postman.** *Import* (arriba a la izquierda) → elegir `docs/postman/RescueSync-I-3.6.postman_collection.json` → *Import*.

**2. Elegir contra qué API se prueba.** La variable `base_url` ya apunta a la API publicada en Render:

```text
https://rescuesync-sistema-nacional-41pb.onrender.com/api/v1
```

Para probar en local, cambiarla a `http://localhost:5001/api/v1` y levantar la API con las cuentas de servicio creadas (las contraseñas salen de `CUENTA_BONITA_PASSWORD` y `CUENTA_WEBAPP_PASSWORD` del `.env`):

```bash
docker compose up -d
docker compose exec api flask db upgrade
docker compose exec api flask seed
docker compose exec api flask cuentas-servicio
```

**3. Cargar las contraseñas de las cuentas de servicio.** Clic en la colección *RescueSync · Sistema Nacional · I-3.6…* → pestaña **Variables** → completar la columna *Current value* de `password_bonita` y `password_webapp` → guardar con **Ctrl+S**.

| Cuenta | Rol del token | Puede |
|---|---|---|
| `bonita` | `SISTEMA_BONITA` | Todas las operaciones del proceso, y consultar |
| `webapp` | `SISTEMA_WEBAPP` | Solo consultar (y el inventario de la ONG por CUIT) |

**4. Ejecutar.**
- **Todos juntos:** clic derecho en la colección → **Run collection** → **Run**. El resumen muestra cuántas pruebas pasaron.
- **Uno por uno:** abrir cada pedido en orden, empezando por la carpeta 0, y apretar **Send**. Abajo, la pestaña **Test Results** muestra en verde cada valor esperado que se cumplió.

No hace falta pegar tokens: los logins de la carpeta 0 los guardan solos y cada pedido ya está configurado con el que corresponde. **Se puede repetir sin limpiar la base:** cada corrida registra su propia ONG de prueba y usa referencias con un sufijo propio.

**Inventario de partida** de la ONG de prueba, como bloqueada / comprometida / disponible: `PARAMEDICO` 0 / 0 / 10 y `RACION_ALIMENTO` 0 / 0 / 2000.

## 0. Preparación: logins y ONG de prueba

Inicia sesión con las cuentas `bonita` y `webapp` (los tokens se guardan solos) y registra una ONG de prueba nueva.

### 0.1 Login de la cuenta bonita

- **Pedido:** `POST {{base_url}}/login`
- **Token (pestaña Authorization):** ninguno
- **Qué hace el endpoint:** Inicio de sesión (I-3.1). Devuelve un JWT con el rol de la cuenta en el claim `rol`. No pide token.
- **Qué prueba este caso:** Es la cuenta con la que Bonita invoca todas las operaciones del proceso. Guarda el token en `token_bonita`. Si responde 401, falta la contraseña en la variable `password_bonita` o no es la correcta.

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

### 0.2 Login de la cuenta webapp

- **Pedido:** `POST {{base_url}}/login`
- **Token (pestaña Authorization):** ninguno
- **Qué hace el endpoint:** Inicio de sesión (I-3.1). Devuelve un JWT con el rol de la cuenta en el claim `rol`. No pide token.
- **Qué prueba este caso:** Solo para la carpeta 7: mostrar que la API rechaza a la webapp en las operaciones del proceso. Guarda el token en `token_webapp`.

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

### 0.3 Registrar la ONG de prueba de esta corrida

- **Pedido:** `POST {{base_url}}/ongs`
- **Token (pestaña Authorization):** ninguno
- **Qué hace el endpoint:** Registro directo de una ONG (I-3.1): queda `HABILITADA` en el acto y cada categoría es una fila de su inventario, con el máximo como total. No pide token.
- **Qué prueba este caso:** Cada corrida registra una ONG nueva, con un CUIT válido y un email que se generan solos, así las cuentas del inventario siempre dan lo mismo. Se inscribe en 10 paramédicos (reutilizables) y 2000 raciones (consumibles). Guarda el id en `ong_id`.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "razon_social": "Rescatistas de Prueba (Postman I-3.6)",
  "cuit": "{{ong_cuit}}",
  "email_contacto": "{{ong_email}}",
  "telefono": "221 555-0106",
  "password": "{{password_ong}}",
  "categorias": [
    {
      "tipo_recurso": "PARAMEDICO",
      "cantidad_maxima": 10
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
  "razon_social": "Rescatistas de Prueba (Postman I-3.6)",
  "telefono": "221 555-0106"
}
```

### 0.4 Inventario inicial de la ONG de prueba

- **Pedido:** `GET {{base_url}}/ongs/{{ong_id}}/recursos`
- **Token (pestaña Authorization):** ninguno
- **Qué hace el endpoint:** Inventario de una ONG por tipo de recurso: total, bloqueado, comprometido y disponible. Es público.
- **Qué prueba este caso:** Punto de partida: nada bloqueado ni comprometido.

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
]
```

## 1. Validar ofertas: validar y bloquear

Vence la ventana de la convocatoria: Bonita valida las ofertas y la API bloquea lo que acepta.

### 1.1 Bonita valida y bloquea las ofertas de la convocatoria 1

- **Pedido:** `POST {{base_url}}/emergencias/EMG-1-{{corrida}}/bloqueo`
- **Token (pestaña Authorization):** `{{token_bonita}}` (*Bearer Token*)
- **Qué hace el endpoint:** *Validar ofertas*, la tarea de servicio que corre cuando vence la ventana de la convocatoria. Bonita le pide a la webapp el JSON de ofertas y lo manda tal cual: la API valida cada línea por niveles de competencia (total, parcial o no habilitada, con su motivo y el rol sugerido) y **bloquea lo que acepta**, todo en una transacción con `SELECT … FOR UPDATE`. Repetirlo reemplaza los bloqueos de la convocatoria.
- **Qué prueba este caso:** Dos ofertas: la de la ONG de prueba (6 paramédicos y 800 raciones) y una de una ONG pendiente de habilitación. Respuesta no binaria: la primera se acepta y queda bloqueada; la segunda sale NO_HABILITADO con su motivo y no bloquea nada.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "convocatoria_referencia": "CONV-1-{{corrida}}",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "fecha_cierre": "{{cierre_vencido}}",
  "fecha_limite_adjudicacion": "{{limite_futuro}}",
  "ofertas": [
    {
      "oferta_referencia": "OF-1-{{corrida}}",
      "items": [
        {
          "lote_referencia": "LOTE-1",
          "ong_cuit": "{{ong_cuit}}",
          "tipo_recurso": "PARAMEDICO",
          "cantidad_requerida": "8",
          "cantidad_ofrecida": "6"
        },
        {
          "lote_referencia": "LOTE-2",
          "ong_cuit": "{{ong_cuit}}",
          "tipo_recurso": "RACION_ALIMENTO",
          "cantidad_requerida": "1000",
          "cantidad_ofrecida": "800"
        }
      ]
    },
    {
      "oferta_referencia": "OF-2-{{corrida}}",
      "items": [
        {
          "lote_referencia": "LOTE-1",
          "ong_cuit": "30-33333333-3",
          "tipo_recurso": "PARAMEDICO",
          "cantidad_requerida": "8",
          "cantidad_ofrecida": "2"
        }
      ]
    }
  ]
}
```

**Respuesta esperada: `200 OK`**

```json
{
  "convocatoria_referencia": "CONV-1-{{corrida}}",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "ofertas": [
    {
      "items": [
        {
          "cantidad_aceptada": "6.00",
          "cantidad_habilitada": "10.00",
          "cantidad_ofrecida": "6.00",
          "cantidad_requerida": "8.00",
          "lote_referencia": "LOTE-1",
          "motivo": null,
          "nivel": "TOTAL",
          "ong_cuit": "{{ong_cuit}}",
          "rol_sugerido": "APOYO",
          "tipo_recurso": "PARAMEDICO"
        },
        {
          "cantidad_aceptada": "800.00",
          "cantidad_habilitada": "2000.00",
          "cantidad_ofrecida": "800.00",
          "cantidad_requerida": "1000.00",
          "lote_referencia": "LOTE-2",
          "motivo": null,
          "nivel": "TOTAL",
          "ong_cuit": "{{ong_cuit}}",
          "rol_sugerido": "APOYO",
          "tipo_recurso": "RACION_ALIMENTO"
        }
      ],
      "nivel": "TOTAL",
      "oferta_referencia": "OF-1-{{corrida}}"
    },
    {
      "items": [
        {
          "cantidad_aceptada": "0.00",
          "cantidad_habilitada": "0.00",
          "cantidad_ofrecida": "2.00",
          "cantidad_requerida": "8.00",
          "lote_referencia": "LOTE-1",
          "motivo": "ONG_NO_HABILITADA",
          "nivel": "NO_HABILITADO",
          "ong_cuit": "30-33333333-3",
          "rol_sugerido": null,
          "tipo_recurso": "PARAMEDICO"
        }
      ],
      "nivel": "NO_HABILITADO",
      "oferta_referencia": "OF-2-{{corrida}}"
    }
  ],
  "reservas": 1
}
```

### 1.2 Inventario después de validar: quedó bloqueado lo aceptado

- **Pedido:** `GET {{base_url}}/ongs/{{ong_id}}/recursos`
- **Token (pestaña Authorization):** ninguno
- **Qué hace el endpoint:** Inventario de una ONG por tipo de recurso: total, bloqueado, comprometido y disponible. Es público.
- **Qué prueba este caso:** Lo aceptado quedó bloqueado: ya no está disponible para otra emergencia.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cantidad_bloqueada": "6.00",
    "cantidad_comprometida": "0.00",
    "cantidad_disponible": "4.00",
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
    "cantidad_bloqueada": "800.00",
    "cantidad_comprometida": "0.00",
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
  }
]
```

### 1.3 Reintento del conector: el mismo pedido

- **Pedido:** `POST {{base_url}}/emergencias/EMG-1-{{corrida}}/bloqueo`
- **Token (pestaña Authorization):** `{{token_bonita}}` (*Bearer Token*)
- **Qué hace el endpoint:** *Validar ofertas*, la tarea de servicio que corre cuando vence la ventana de la convocatoria. Bonita le pide a la webapp el JSON de ofertas y lo manda tal cual: la API valida cada línea por niveles de competencia (total, parcial o no habilitada, con su motivo y el rol sugerido) y **bloquea lo que acepta**, todo en una transacción con `SELECT … FOR UPDATE`. Repetirlo reemplaza los bloqueos de la convocatoria.
- **Qué prueba este caso:** Si Bonita reintenta la tarea, el pedido reemplaza los bloqueos de la convocatoria: no bloquea dos veces.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "convocatoria_referencia": "CONV-1-{{corrida}}",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "fecha_cierre": "{{cierre_vencido}}",
  "fecha_limite_adjudicacion": "{{limite_futuro}}",
  "ofertas": [
    {
      "oferta_referencia": "OF-1-{{corrida}}",
      "items": [
        {
          "lote_referencia": "LOTE-1",
          "ong_cuit": "{{ong_cuit}}",
          "tipo_recurso": "PARAMEDICO",
          "cantidad_requerida": "8",
          "cantidad_ofrecida": "6"
        },
        {
          "lote_referencia": "LOTE-2",
          "ong_cuit": "{{ong_cuit}}",
          "tipo_recurso": "RACION_ALIMENTO",
          "cantidad_requerida": "1000",
          "cantidad_ofrecida": "800"
        }
      ]
    },
    {
      "oferta_referencia": "OF-2-{{corrida}}",
      "items": [
        {
          "lote_referencia": "LOTE-1",
          "ong_cuit": "30-33333333-3",
          "tipo_recurso": "PARAMEDICO",
          "cantidad_requerida": "8",
          "cantidad_ofrecida": "2"
        }
      ]
    }
  ]
}
```

**Respuesta esperada: `200 OK`**

```json
{
  "convocatoria_referencia": "CONV-1-{{corrida}}",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "ofertas": [
    {
      "items": [
        {
          "cantidad_aceptada": "6.00",
          "cantidad_habilitada": "10.00",
          "cantidad_ofrecida": "6.00",
          "cantidad_requerida": "8.00",
          "lote_referencia": "LOTE-1",
          "motivo": null,
          "nivel": "TOTAL",
          "ong_cuit": "{{ong_cuit}}",
          "rol_sugerido": "APOYO",
          "tipo_recurso": "PARAMEDICO"
        },
        {
          "cantidad_aceptada": "800.00",
          "cantidad_habilitada": "2000.00",
          "cantidad_ofrecida": "800.00",
          "cantidad_requerida": "1000.00",
          "lote_referencia": "LOTE-2",
          "motivo": null,
          "nivel": "TOTAL",
          "ong_cuit": "{{ong_cuit}}",
          "rol_sugerido": "APOYO",
          "tipo_recurso": "RACION_ALIMENTO"
        }
      ],
      "nivel": "TOTAL",
      "oferta_referencia": "OF-1-{{corrida}}"
    },
    {
      "items": [
        {
          "cantidad_aceptada": "0.00",
          "cantidad_habilitada": "0.00",
          "cantidad_ofrecida": "2.00",
          "cantidad_requerida": "8.00",
          "lote_referencia": "LOTE-1",
          "motivo": "ONG_NO_HABILITADA",
          "nivel": "NO_HABILITADO",
          "ong_cuit": "30-33333333-3",
          "rol_sugerido": null,
          "tipo_recurso": "PARAMEDICO"
        }
      ],
      "nivel": "NO_HABILITADO",
      "oferta_referencia": "OF-2-{{corrida}}"
    }
  ],
  "reservas": 1
}
```

### 1.4 El inventario no cambió con el reintento

- **Pedido:** `GET {{base_url}}/ongs/{{ong_id}}/recursos`
- **Token (pestaña Authorization):** ninguno
- **Qué hace el endpoint:** Inventario de una ONG por tipo de recurso: total, bloqueado, comprometido y disponible. Es público.
- **Qué prueba este caso:** Sigue igual que en 1.2.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cantidad_bloqueada": "6.00",
    "cantidad_comprometida": "0.00",
    "cantidad_disponible": "4.00",
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
    "cantidad_bloqueada": "800.00",
    "cantidad_comprometida": "0.00",
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
  }
]
```

### 1.5 Una convocatoria sin ofertas también se valida

- **Pedido:** `POST {{base_url}}/emergencias/EMG-2-{{corrida}}/bloqueo`
- **Token (pestaña Authorization):** `{{token_bonita}}` (*Bearer Token*)
- **Qué hace el endpoint:** *Validar ofertas*, la tarea de servicio que corre cuando vence la ventana de la convocatoria. Bonita le pide a la webapp el JSON de ofertas y lo manda tal cual: la API valida cada línea por niveles de competencia (total, parcial o no habilitada, con su motivo y el rol sugerido) y **bloquea lo que acepta**, todo en una transacción con `SELECT … FOR UPDATE`. Repetirlo reemplaza los bloqueos de la convocatoria.
- **Qué prueba este caso:** Si nadie ofertó, *Validar ofertas* corre igual: la lista vacía no bloquea nada.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "convocatoria_referencia": "CONV-2-{{corrida}}",
  "emergencia_referencia": "EMG-2-{{corrida}}",
  "fecha_cierre": "{{cierre_vencido}}",
  "fecha_limite_adjudicacion": "{{limite_futuro}}",
  "ofertas": []
}
```

**Respuesta esperada: `200 OK`**

```json
{
  "convocatoria_referencia": "CONV-2-{{corrida}}",
  "emergencia_referencia": "EMG-2-{{corrida}}",
  "ofertas": [],
  "reservas": 0
}
```

### 1.6 Un tipo de recurso que no está en el catálogo

- **Pedido:** `POST {{base_url}}/emergencias/EMG-2-{{corrida}}/bloqueo`
- **Token (pestaña Authorization):** `{{token_bonita}}` (*Bearer Token*)
- **Qué hace el endpoint:** *Validar ofertas*, la tarea de servicio que corre cuando vence la ventana de la convocatoria. Bonita le pide a la webapp el JSON de ofertas y lo manda tal cual: la API valida cada línea por niveles de competencia (total, parcial o no habilitada, con su motivo y el rol sugerido) y **bloquea lo que acepta**, todo en una transacción con `SELECT … FOR UPDATE`. Repetirlo reemplaza los bloqueos de la convocatoria.
- **Qué prueba este caso:** Un código fuera del catálogo nacional indica un catálogo desalineado con la webapp: la API rechaza el pedido entero y no bloquea nada.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "convocatoria_referencia": "CONV-2-{{corrida}}",
  "emergencia_referencia": "EMG-2-{{corrida}}",
  "fecha_cierre": "{{cierre_vencido}}",
  "fecha_limite_adjudicacion": "{{limite_futuro}}",
  "ofertas": [
    {
      "oferta_referencia": "OF-3-{{corrida}}",
      "items": [
        {
          "lote_referencia": "LOTE-9",
          "ong_cuit": "{{ong_cuit}}",
          "tipo_recurso": "DRON",
          "cantidad_requerida": "1",
          "cantidad_ofrecida": "1"
        }
      ]
    }
  ]
}
```

**Respuesta esperada: `422 UNPROCESSABLE ENTITY`**

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

## 2. Reabrir convocatoria: liberar los bloqueos y validar de nuevo

La cobertura no alcanzó y el coordinador reabre (o reformula): Bonita libera los bloqueos y, cuando vence la nueva ventana, valida de nuevo.

### 2.1 Bonita libera los bloqueos al reabrir

- **Pedido:** `POST {{base_url}}/emergencias/EMG-1-{{corrida}}/desbloqueo`
- **Token (pestaña Authorization):** `{{token_bonita}}` (*Bearer Token*)
- **Qué hace el endpoint:** Conector de *Reabrir convocatoria* y de *Reformular lotes*: libera los bloqueos que dejó la validación, porque las ofertas pueden cambiar. No toca lo comprometido. Si no hay nada bloqueado, responde 200 con 0.
- **Qué prueba este caso:** La reserva de la oferta 1 se cancela y sus recursos vuelven a estar disponibles.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{}
```

**Respuesta esperada: `200 OK`**

```json
{
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "reservas_canceladas": 1
}
```

### 2.2 Inventario después de liberar los bloqueos

- **Pedido:** `GET {{base_url}}/ongs/{{ong_id}}/recursos`
- **Token (pestaña Authorization):** ninguno
- **Qué hace el endpoint:** Inventario de una ONG por tipo de recurso: total, bloqueado, comprometido y disponible. Es público.
- **Qué prueba este caso:** Todo vuelve a estar disponible.

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
]
```

### 2.3 Repetir el desbloqueo

- **Pedido:** `POST {{base_url}}/emergencias/EMG-1-{{corrida}}/desbloqueo`
- **Token (pestaña Authorization):** `{{token_bonita}}` (*Bearer Token*)
- **Qué hace el endpoint:** Conector de *Reabrir convocatoria* y de *Reformular lotes*: libera los bloqueos que dejó la validación, porque las ofertas pueden cambiar. No toca lo comprometido. Si no hay nada bloqueado, responde 200 con 0.
- **Qué prueba este caso:** No queda nada bloqueado: responde 200 con 0. El conector nunca falla por eso.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{}
```

**Respuesta esperada: `200 OK`**

```json
{
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "reservas_canceladas": 0
}
```

### 2.4 Una emergencia que la API todavía no conoce

- **Pedido:** `POST {{base_url}}/emergencias/EMG-NUEVA-{{corrida}}/desbloqueo`
- **Token (pestaña Authorization):** `{{token_bonita}}` (*Bearer Token*)
- **Qué hace el endpoint:** Conector de *Reabrir convocatoria* y de *Reformular lotes*: libera los bloqueos que dejó la validación, porque las ofertas pueden cambiar. No toca lo comprometido. Si no hay nada bloqueado, responde 200 con 0.
- **Qué prueba este caso:** Si la convocatoria se reformuló antes de la primera validación, la API no la conoce: también responde 200 con 0.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{}
```

**Respuesta esperada: `200 OK`**

```json
{
  "emergencia_referencia": "EMG-NUEVA-{{corrida}}",
  "reservas_canceladas": 0
}
```

### 2.5 Vence la nueva ventana: Bonita valida la oferta modificada

- **Pedido:** `POST {{base_url}}/emergencias/EMG-1-{{corrida}}/bloqueo`
- **Token (pestaña Authorization):** `{{token_bonita}}` (*Bearer Token*)
- **Qué hace el endpoint:** *Validar ofertas*, la tarea de servicio que corre cuando vence la ventana de la convocatoria. Bonita le pide a la webapp el JSON de ofertas y lo manda tal cual: la API valida cada línea por niveles de competencia (total, parcial o no habilitada, con su motivo y el rol sugerido) y **bloquea lo que acepta**, todo en una transacción con `SELECT … FOR UPDATE`. Repetirlo reemplaza los bloqueos de la convocatoria.
- **Qué prueba este caso:** Durante la nueva ventana la ONG bajó su oferta a 5 paramédicos. La misma reserva vuelve a RESERVADO con lo nuevo.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "convocatoria_referencia": "CONV-1-{{corrida}}",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "fecha_cierre": "{{cierre_vencido}}",
  "fecha_limite_adjudicacion": "{{limite_futuro}}",
  "ofertas": [
    {
      "oferta_referencia": "OF-1-{{corrida}}",
      "items": [
        {
          "lote_referencia": "LOTE-1",
          "ong_cuit": "{{ong_cuit}}",
          "tipo_recurso": "PARAMEDICO",
          "cantidad_requerida": "8",
          "cantidad_ofrecida": "5"
        },
        {
          "lote_referencia": "LOTE-2",
          "ong_cuit": "{{ong_cuit}}",
          "tipo_recurso": "RACION_ALIMENTO",
          "cantidad_requerida": "1000",
          "cantidad_ofrecida": "800"
        }
      ]
    }
  ]
}
```

**Respuesta esperada: `200 OK`**

```json
{
  "convocatoria_referencia": "CONV-1-{{corrida}}",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "ofertas": [
    {
      "items": [
        {
          "cantidad_aceptada": "5.00",
          "cantidad_habilitada": "10.00",
          "cantidad_ofrecida": "5.00",
          "cantidad_requerida": "8.00",
          "lote_referencia": "LOTE-1",
          "motivo": null,
          "nivel": "TOTAL",
          "ong_cuit": "{{ong_cuit}}",
          "rol_sugerido": "APOYO",
          "tipo_recurso": "PARAMEDICO"
        },
        {
          "cantidad_aceptada": "800.00",
          "cantidad_habilitada": "2000.00",
          "cantidad_ofrecida": "800.00",
          "cantidad_requerida": "1000.00",
          "lote_referencia": "LOTE-2",
          "motivo": null,
          "nivel": "TOTAL",
          "ong_cuit": "{{ong_cuit}}",
          "rol_sugerido": "APOYO",
          "tipo_recurso": "RACION_ALIMENTO"
        }
      ],
      "nivel": "TOTAL",
      "oferta_referencia": "OF-1-{{corrida}}"
    }
  ],
  "reservas": 1
}
```

## 3. Comprometer recursos

El municipio adjudicó en la webapp: Bonita compromete lo adjudicado.

### 3.1 Adjudicar más de lo bloqueado

- **Pedido:** `POST {{base_url}}/emergencias/EMG-1-{{corrida}}/adjudicacion`
- **Token (pestaña Authorization):** `{{token_bonita}}` (*Bearer Token*)
- **Qué hace el endpoint:** *Comprometer recursos*, tarea de servicio: Bonita le pide a la webapp lo que adjudicó el municipio y lo manda tal cual. La API compromete lo adjudicado y libera los bloqueos del resto, todo o nada. Repetir la misma adjudicación no cambia nada.
- **Qué prueba este caso:** Solo hay 5 paramédicos bloqueados: la adjudicación entera se rechaza, con el detalle por oferta y ONG, y no se compromete nada.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "convocatoria_referencia": "CONV-1-{{corrida}}",
  "adjudicaciones": [
    {
      "oferta_referencia": "OF-1-{{corrida}}",
      "ong_cuit": "{{ong_cuit}}",
      "items": [
        {
          "tipo_recurso": "PARAMEDICO",
          "cantidad": 6
        },
        {
          "tipo_recurso": "RACION_ALIMENTO",
          "cantidad": 600
        }
      ]
    }
  ]
}
```

**Respuesta esperada: `422 UNPROCESSABLE ENTITY`**

```json
{
  "codigo": "ADJUDICACION_INVALIDA",
  "detalles": {
    "adjudicaciones": [
      {
        "error": "PARAMEDICO: no puede superar lo bloqueado (5.00).",
        "oferta_referencia": "OF-1-{{corrida}}",
        "ong_cuit": "{{ong_cuit}}"
      }
    ]
  },
  "mensaje": "Hay adjudicaciones que no se pueden comprometer."
}
```

### 3.2 Bonita compromete lo adjudicado: 5 paramédicos y 600 raciones

- **Pedido:** `POST {{base_url}}/emergencias/EMG-1-{{corrida}}/adjudicacion`
- **Token (pestaña Authorization):** `{{token_bonita}}` (*Bearer Token*)
- **Qué hace el endpoint:** *Comprometer recursos*, tarea de servicio: Bonita le pide a la webapp lo que adjudicó el municipio y lo manda tal cual. La API compromete lo adjudicado y libera los bloqueos del resto, todo o nada. Repetir la misma adjudicación no cambia nada.
- **Qué prueba este caso:** Adjudicación parcial de las raciones: se comprometen 600 y las otras 200 bloqueadas se liberan en el momento.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "convocatoria_referencia": "CONV-1-{{corrida}}",
  "adjudicaciones": [
    {
      "oferta_referencia": "OF-1-{{corrida}}",
      "ong_cuit": "{{ong_cuit}}",
      "items": [
        {
          "tipo_recurso": "PARAMEDICO",
          "cantidad": 5
        },
        {
          "tipo_recurso": "RACION_ALIMENTO",
          "cantidad": 600
        }
      ]
    }
  ]
}
```

**Respuesta esperada: `200 OK`**

```json
{
  "compromisos": [
    {
      "cancelado_en": "<fecha y hora>",
      "confirmado_en": "<fecha y hora>",
      "convocatoria": {
        "emergencia_referencia": "EMG-1-{{corrida}}",
        "fecha_cierre": "<fecha y hora>",
        "fecha_limite_adjudicacion": "<fecha y hora>",
        "referencia": "CONV-1-{{corrida}}"
      },
      "creado_en": "<fecha y hora>",
      "creado_por": "2",
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
          "cantidad_comprometida": "600.00",
          "cantidad_liberada": "0.00",
          "cantidad_pendiente": "600.00",
          "cantidad_reservada": "800.00",
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
        "razon_social": "Rescatistas de Prueba (Postman I-3.6)"
      },
      "vencido_en": null
    }
  ],
  "convocatoria_referencia": "CONV-1-{{corrida}}",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "reservas_canceladas": 0
}
```

### 3.3 Inventario después de comprometer

- **Pedido:** `GET {{base_url}}/ongs/{{ong_id}}/recursos`
- **Token (pestaña Authorization):** ninguno
- **Qué hace el endpoint:** Inventario de una ONG por tipo de recurso: total, bloqueado, comprometido y disponible. Es público.
- **Qué prueba este caso:** Lo adjudicado pasó de bloqueado a comprometido; las 200 raciones no adjudicadas volvieron a estar disponibles.

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
    "cantidad_comprometida": "600.00",
    "cantidad_disponible": "1400.00",
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
]
```

### 3.4 Reintento del conector: la misma adjudicación

- **Pedido:** `POST {{base_url}}/emergencias/EMG-1-{{corrida}}/adjudicacion`
- **Token (pestaña Authorization):** `{{token_bonita}}` (*Bearer Token*)
- **Qué hace el endpoint:** *Comprometer recursos*, tarea de servicio: Bonita le pide a la webapp lo que adjudicó el municipio y lo manda tal cual. La API compromete lo adjudicado y libera los bloqueos del resto, todo o nada. Repetir la misma adjudicación no cambia nada.
- **Qué prueba este caso:** Repetir la misma adjudicación no cambia nada: el compromiso sigue igual y no hay más reservas que cancelar.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "convocatoria_referencia": "CONV-1-{{corrida}}",
  "adjudicaciones": [
    {
      "oferta_referencia": "OF-1-{{corrida}}",
      "ong_cuit": "{{ong_cuit}}",
      "items": [
        {
          "tipo_recurso": "PARAMEDICO",
          "cantidad": 5
        },
        {
          "tipo_recurso": "RACION_ALIMENTO",
          "cantidad": 600
        }
      ]
    }
  ]
}
```

**Respuesta esperada: `200 OK`**

```json
{
  "compromisos": [
    {
      "cancelado_en": "<fecha y hora>",
      "confirmado_en": "<fecha y hora>",
      "convocatoria": {
        "emergencia_referencia": "EMG-1-{{corrida}}",
        "fecha_cierre": "<fecha y hora>",
        "fecha_limite_adjudicacion": "<fecha y hora>",
        "referencia": "CONV-1-{{corrida}}"
      },
      "creado_en": "<fecha y hora>",
      "creado_por": "2",
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
          "cantidad_comprometida": "600.00",
          "cantidad_liberada": "0.00",
          "cantidad_pendiente": "600.00",
          "cantidad_reservada": "800.00",
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
        "razon_social": "Rescatistas de Prueba (Postman I-3.6)"
      },
      "vencido_en": null
    }
  ],
  "convocatoria_referencia": "CONV-1-{{corrida}}",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "reservas_canceladas": 0
}
```

## 4. Marcar actividad como finalizada

Las ONGs informan actividades en la webapp: Bonita se las lleva a la API, que libera lo cumplido.

### 4.1 Bonita informa dos actividades

- **Pedido:** `POST {{base_url}}/emergencias/EMG-1-{{corrida}}/actividades`
- **Token (pestaña Authorization):** `{{token_bonita}}` (*Bearer Token*)
- **Qué hace el endpoint:** Conectores de salida de *Marcar actividad como finalizada*: Bonita le pide a la webapp las actividades que la API todavía no le confirmó y las manda juntas. Cada una libera lo cumplido (lo reutilizable vuelve al stock, lo consumible se da de baja) y es idempotente por `actividad_referencia`.
- **Qué prueba este caso:** Terminaron 3 paramédicos (reutilizables: vuelven al stock) y se entregaron 600 raciones (consumibles: se dan de baja).

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "actividades": [
    {
      "actividad_referencia": "ACT-1-{{corrida}}",
      "ong_cuit": "{{ong_cuit}}",
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 3,
      "fecha": "{{fecha_cumplida}}",
      "observaciones": "Evacuación del barrio Norte terminada"
    },
    {
      "actividad_referencia": "ACT-2-{{corrida}}",
      "ong_cuit": "{{ong_cuit}}",
      "tipo_recurso": "RACION_ALIMENTO",
      "cantidad": 600,
      "fecha": "{{fecha_cumplida}}",
      "observaciones": "Raciones entregadas en el centro de evacuados"
    }
  ]
}
```

**Respuesta esperada: `200 OK`**

```json
{
  "actividades": [
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
        "razon_social": "Rescatistas de Prueba (Postman I-3.6)"
      },
      "origen": "INFORMADA",
      "registrada_por": "2",
      "tipo_recurso": {
        "codigo": "PARAMEDICO",
        "nombre": "Paramédico"
      }
    },
    {
      "accion": "CONSUMIDO",
      "actividad_referencia": "ACT-2-{{corrida}}",
      "cantidad": "600.00",
      "compromiso_id": "<id>",
      "creado_en": "<fecha y hora>",
      "emergencia_referencia": "EMG-1-{{corrida}}",
      "estado_compromiso": "COMPROMETIDO",
      "fecha": "<fecha y hora>",
      "id": "<id>",
      "item": {
        "cantidad_comprometida": "600.00",
        "cantidad_liberada": "600.00",
        "cantidad_pendiente": "0.00",
        "tipo_recurso": {
          "codigo": "RACION_ALIMENTO",
          "nombre": "Ración de alimento"
        }
      },
      "observaciones": "Raciones entregadas en el centro de evacuados",
      "oferta_referencia": "OF-1-{{corrida}}",
      "ong": {
        "cuit": "{{ong_cuit}}",
        "id": "<id>",
        "razon_social": "Rescatistas de Prueba (Postman I-3.6)"
      },
      "origen": "INFORMADA",
      "registrada_por": "2",
      "tipo_recurso": {
        "codigo": "RACION_ALIMENTO",
        "nombre": "Ración de alimento"
      }
    }
  ],
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "nuevas": 2
}
```

### 4.2 Reintento del conector: las mismas actividades

- **Pedido:** `POST {{base_url}}/emergencias/EMG-1-{{corrida}}/actividades`
- **Token (pestaña Authorization):** `{{token_bonita}}` (*Bearer Token*)
- **Qué hace el endpoint:** Conectores de salida de *Marcar actividad como finalizada*: Bonita le pide a la webapp las actividades que la API todavía no le confirmó y las manda juntas. Cada una libera lo cumplido (lo reutilizable vuelve al stock, lo consumible se da de baja) y es idempotente por `actividad_referencia`.
- **Qué prueba este caso:** Las actividades ya registradas no liberan dos veces: `nuevas` es 0.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "actividades": [
    {
      "actividad_referencia": "ACT-1-{{corrida}}",
      "ong_cuit": "{{ong_cuit}}",
      "tipo_recurso": "PARAMEDICO",
      "cantidad": 3,
      "fecha": "{{fecha_cumplida}}",
      "observaciones": "Evacuación del barrio Norte terminada"
    },
    {
      "actividad_referencia": "ACT-2-{{corrida}}",
      "ong_cuit": "{{ong_cuit}}",
      "tipo_recurso": "RACION_ALIMENTO",
      "cantidad": 600,
      "fecha": "{{fecha_cumplida}}",
      "observaciones": "Raciones entregadas en el centro de evacuados"
    }
  ]
}
```

**Respuesta esperada: `200 OK`**

```json
{
  "actividades": [
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
        "razon_social": "Rescatistas de Prueba (Postman I-3.6)"
      },
      "origen": "INFORMADA",
      "registrada_por": "2",
      "tipo_recurso": {
        "codigo": "PARAMEDICO",
        "nombre": "Paramédico"
      }
    },
    {
      "accion": "CONSUMIDO",
      "actividad_referencia": "ACT-2-{{corrida}}",
      "cantidad": "600.00",
      "compromiso_id": "<id>",
      "creado_en": "<fecha y hora>",
      "emergencia_referencia": "EMG-1-{{corrida}}",
      "estado_compromiso": "COMPROMETIDO",
      "fecha": "<fecha y hora>",
      "id": "<id>",
      "item": {
        "cantidad_comprometida": "600.00",
        "cantidad_liberada": "600.00",
        "cantidad_pendiente": "0.00",
        "tipo_recurso": {
          "codigo": "RACION_ALIMENTO",
          "nombre": "Ración de alimento"
        }
      },
      "observaciones": "Raciones entregadas en el centro de evacuados",
      "oferta_referencia": "OF-1-{{corrida}}",
      "ong": {
        "cuit": "{{ong_cuit}}",
        "id": "<id>",
        "razon_social": "Rescatistas de Prueba (Postman I-3.6)"
      },
      "origen": "INFORMADA",
      "registrada_por": "2",
      "tipo_recurso": {
        "codigo": "RACION_ALIMENTO",
        "nombre": "Ración de alimento"
      }
    }
  ],
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "nuevas": 0
}
```

### 4.3 Sin actividades nuevas

- **Pedido:** `POST {{base_url}}/emergencias/EMG-1-{{corrida}}/actividades`
- **Token (pestaña Authorization):** `{{token_bonita}}` (*Bearer Token*)
- **Qué hace el endpoint:** Conectores de salida de *Marcar actividad como finalizada*: Bonita le pide a la webapp las actividades que la API todavía no le confirmó y las manda juntas. Cada una libera lo cumplido (lo reutilizable vuelve al stock, lo consumible se da de baja) y es idempotente por `actividad_referencia`.
- **Qué prueba este caso:** Cuando la webapp no tiene nada sin confirmar, la lista va vacía y no cambia nada.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "actividades": []
}
```

**Respuesta esperada: `200 OK`**

```json
{
  "actividades": [],
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "nuevas": 0
}
```

### 4.4 Inventario después de las actividades

- **Pedido:** `GET {{base_url}}/ongs/{{ong_id}}/recursos`
- **Token (pestaña Authorization):** ninguno
- **Qué hace el endpoint:** Inventario de una ONG por tipo de recurso: total, bloqueado, comprometido y disponible. Es público.
- **Qué prueba este caso:** 3 paramédicos volvieron al stock y las 600 raciones se dieron de baja (bajan el comprometido y el total).

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
    "cantidad_comprometida": "0.00",
    "cantidad_disponible": "1400.00",
    "cantidad_total": "1400.00",
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
]
```

## 5. Liberar recursos

Corroborados los lotes, Bonita libera lo que siga comprometido.

### 5.1 Bonita libera lo que quedó comprometido

- **Pedido:** `POST {{base_url}}/emergencias/EMG-1-{{corrida}}/liberacion`
- **Token (pestaña Authorization):** `{{token_bonita}}` (*Bearer Token*)
- **Qué hace el endpoint:** *Liberar recursos*, tarea de servicio: libera todo lo que siga comprometido en la emergencia (origen CIERRE) y finaliza esos compromisos. Es idempotente.
- **Qué prueba este caso:** Quedaban 2 paramédicos sin informar: se liberan igual, con origen CIERRE.

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
          "cantidad_comprometida": "600.00",
          "cantidad_liberada": "600.00",
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
        "razon_social": "Rescatistas de Prueba (Postman I-3.6)"
      }
    }
  ],
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "liberaciones": [
    {
      "accion": "LIBERADO",
      "actividad_referencia": null,
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
      "observaciones": null,
      "oferta_referencia": "OF-1-{{corrida}}",
      "ong": {
        "cuit": "{{ong_cuit}}",
        "id": "<id>",
        "razon_social": "Rescatistas de Prueba (Postman I-3.6)"
      },
      "origen": "CIERRE",
      "registrada_por": "2",
      "tipo_recurso": {
        "codigo": "PARAMEDICO",
        "nombre": "Paramédico"
      }
    }
  ],
  "reservas_vigentes": 0,
  "todo_liberado": true
}
```

### 5.2 Repetir la liberación

- **Pedido:** `POST {{base_url}}/emergencias/EMG-1-{{corrida}}/liberacion`
- **Token (pestaña Authorization):** `{{token_bonita}}` (*Bearer Token*)
- **Qué hace el endpoint:** *Liberar recursos*, tarea de servicio: libera todo lo que siga comprometido en la emergencia (origen CIERRE) y finaliza esos compromisos. Es idempotente.
- **Qué prueba este caso:** No queda nada comprometido: no libera nada más.

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
          "cantidad_comprometida": "600.00",
          "cantidad_liberada": "600.00",
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
        "razon_social": "Rescatistas de Prueba (Postman I-3.6)"
      }
    }
  ],
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "liberaciones": [],
  "reservas_vigentes": 0,
  "todo_liberado": true
}
```

## 6. Cerrar proyecto

Bonita registra el cierre en la API y se lo confirma a la webapp.

### 6.1 Bonita cierra el proyecto

- **Pedido:** `POST {{base_url}}/emergencias/EMG-1-{{corrida}}/cierre`
- **Token (pestaña Authorization):** `{{token_bonita}}` (*Bearer Token*)
- **Qué hace el endpoint:** *Cerrar proyecto*, tarea de servicio: registra el cierre solo si no queda nada comprometido. Repetirlo devuelve el mismo cierre con 200. Después no se aceptan más operaciones del proceso para la emergencia.
- **Qué prueba este caso:** Ya no queda nada comprometido. Guarda la fecha de cierre en `fecha_cierre`.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{}
```

**Respuesta esperada: `201 Created`**

```json
{
  "cerrado_por": "2",
  "creado_en": "<fecha y hora>",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "fecha_cierre": "<fecha y hora>",
  "observaciones": null
}
```

### 6.2 Reintento del conector: cerrar otra vez

- **Pedido:** `POST {{base_url}}/emergencias/EMG-1-{{corrida}}/cierre`
- **Token (pestaña Authorization):** `{{token_bonita}}` (*Bearer Token*)
- **Qué hace el endpoint:** *Cerrar proyecto*, tarea de servicio: registra el cierre solo si no queda nada comprometido. Repetirlo devuelve el mismo cierre con 200. Después no se aceptan más operaciones del proceso para la emergencia.
- **Qué prueba este caso:** Devuelve el mismo cierre, con la misma fecha.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{}
```

**Respuesta esperada: `200 OK`**

```json
{
  "cerrado_por": "2",
  "creado_en": "<fecha y hora>",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "fecha_cierre": "<fecha y hora>",
  "observaciones": null
}
```

### 6.3 Validar después del cierre

- **Pedido:** `POST {{base_url}}/emergencias/EMG-1-{{corrida}}/bloqueo`
- **Token (pestaña Authorization):** `{{token_bonita}}` (*Bearer Token*)
- **Qué hace el endpoint:** *Validar ofertas*, la tarea de servicio que corre cuando vence la ventana de la convocatoria. Bonita le pide a la webapp el JSON de ofertas y lo manda tal cual: la API valida cada línea por niveles de competencia (total, parcial o no habilitada, con su motivo y el rol sugerido) y **bloquea lo que acepta**, todo en una transacción con `SELECT … FOR UPDATE`. Repetirlo reemplaza los bloqueos de la convocatoria.
- **Qué prueba este caso:** Un proyecto cerrado no acepta más operaciones del proceso.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "convocatoria_referencia": "CONV-1-{{corrida}}",
  "emergencia_referencia": "EMG-1-{{corrida}}",
  "fecha_cierre": "{{cierre_vencido}}",
  "fecha_limite_adjudicacion": "{{limite_futuro}}",
  "ofertas": [
    {
      "oferta_referencia": "OF-1-{{corrida}}",
      "items": [
        {
          "lote_referencia": "LOTE-1",
          "ong_cuit": "{{ong_cuit}}",
          "tipo_recurso": "PARAMEDICO",
          "cantidad_requerida": "8",
          "cantidad_ofrecida": "5"
        },
        {
          "lote_referencia": "LOTE-2",
          "ong_cuit": "{{ong_cuit}}",
          "tipo_recurso": "RACION_ALIMENTO",
          "cantidad_requerida": "1000",
          "cantidad_ofrecida": "800"
        }
      ]
    }
  ]
}
```

**Respuesta esperada: `409 CONFLICT`**

```json
{
  "codigo": "PROYECTO_CERRADO",
  "detalles": {
    "fecha_cierre": "<fecha y hora>"
  },
  "mensaje": "El proyecto de la emergencia ya está cerrado."
}
```

## 7. Seguridad: solo Bonita invoca las operaciones del proceso

Principio de orquestación: la API rechaza a la cuenta de la webapp en todas las operaciones del proceso, aunque el token sea válido. La webapp conserva las consultas.

### 7.1 La webapp no puede validar ni bloquear

- **Pedido:** `POST {{base_url}}/emergencias/EMG-2-{{corrida}}/bloqueo`
- **Token (pestaña Authorization):** `{{token_webapp}}` (*Bearer Token*)
- **Qué hace el endpoint:** *Validar ofertas*, la tarea de servicio que corre cuando vence la ventana de la convocatoria. Bonita le pide a la webapp el JSON de ofertas y lo manda tal cual: la API valida cada línea por niveles de competencia (total, parcial o no habilitada, con su motivo y el rol sugerido) y **bloquea lo que acepta**, todo en una transacción con `SELECT … FOR UPDATE`. Repetirlo reemplaza los bloqueos de la convocatoria.
- **Qué prueba este caso:** Token válido de la webapp, pero la operación es del orquestador: 403.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "convocatoria_referencia": "CONV-2-{{corrida}}",
  "emergencia_referencia": "EMG-2-{{corrida}}",
  "fecha_cierre": "{{cierre_vencido}}",
  "fecha_limite_adjudicacion": "{{limite_futuro}}",
  "ofertas": []
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

### 7.2 La webapp no puede comprometer

- **Pedido:** `POST {{base_url}}/emergencias/EMG-1-{{corrida}}/adjudicacion`
- **Token (pestaña Authorization):** `{{token_webapp}}` (*Bearer Token*)
- **Qué hace el endpoint:** *Comprometer recursos*, tarea de servicio: Bonita le pide a la webapp lo que adjudicó el municipio y lo manda tal cual. La API compromete lo adjudicado y libera los bloqueos del resto, todo o nada. Repetir la misma adjudicación no cambia nada.
- **Qué prueba este caso:** Lo mismo con el compromiso.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "convocatoria_referencia": "CONV-1-{{corrida}}",
  "adjudicaciones": [
    {
      "oferta_referencia": "OF-1-{{corrida}}",
      "ong_cuit": "{{ong_cuit}}",
      "items": [
        {
          "tipo_recurso": "PARAMEDICO",
          "cantidad": 5
        },
        {
          "tipo_recurso": "RACION_ALIMENTO",
          "cantidad": 600
        }
      ]
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

### 7.3 La webapp no puede informar actividades

- **Pedido:** `POST {{base_url}}/emergencias/EMG-1-{{corrida}}/actividades`
- **Token (pestaña Authorization):** `{{token_webapp}}` (*Bearer Token*)
- **Qué hace el endpoint:** Conectores de salida de *Marcar actividad como finalizada*: Bonita le pide a la webapp las actividades que la API todavía no le confirmó y las manda juntas. Cada una libera lo cumplido (lo reutilizable vuelve al stock, lo consumible se da de baja) y es idempotente por `actividad_referencia`.
- **Qué prueba este caso:** Lo mismo con las actividades.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "actividades": []
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

### 7.4 La webapp no puede liberar recursos

- **Pedido:** `POST {{base_url}}/emergencias/EMG-1-{{corrida}}/liberacion`
- **Token (pestaña Authorization):** `{{token_webapp}}` (*Bearer Token*)
- **Qué hace el endpoint:** *Liberar recursos*, tarea de servicio: libera todo lo que siga comprometido en la emergencia (origen CIERRE) y finaliza esos compromisos. Es idempotente.
- **Qué prueba este caso:** Lo mismo con la liberación.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{}
```

**Respuesta esperada: `403 FORBIDDEN`**

```json
{
  "codigo": "PROHIBIDO",
  "detalles": {},
  "mensaje": "El rol del token no permite esta operación."
}
```

### 7.5 La webapp no puede cerrar el proyecto

- **Pedido:** `POST {{base_url}}/emergencias/EMG-1-{{corrida}}/cierre`
- **Token (pestaña Authorization):** `{{token_webapp}}` (*Bearer Token*)
- **Qué hace el endpoint:** *Cerrar proyecto*, tarea de servicio: registra el cierre solo si no queda nada comprometido. Repetirlo devuelve el mismo cierre con 200. Después no se aceptan más operaciones del proceso para la emergencia.
- **Qué prueba este caso:** Lo mismo con el cierre.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{}
```

**Respuesta esperada: `403 FORBIDDEN`**

```json
{
  "codigo": "PROHIBIDO",
  "detalles": {},
  "mensaje": "El rol del token no permite esta operación."
}
```

### 7.6 La webapp sí puede consultar

- **Pedido:** `GET {{base_url}}/compromisos?emergencia=EMG-1-{{corrida}}`
- **Token (pestaña Authorization):** `{{token_webapp}}` (*Bearer Token*)
- **Qué hace el endpoint:** Consulta de compromisos, con filtros. La aceptan las cuentas de servicio y el auditor.
- **Qué prueba este caso:** Las consultas no son operaciones del proceso: la webapp las conserva. El compromiso de la oferta 1 quedó FINALIZADO.

**Respuesta esperada: `200 OK`**

```json
[
  {
    "cancelado_en": "<fecha y hora>",
    "confirmado_en": "<fecha y hora>",
    "convocatoria": {
      "emergencia_referencia": "EMG-1-{{corrida}}",
      "fecha_cierre": "<fecha y hora>",
      "fecha_limite_adjudicacion": "<fecha y hora>",
      "referencia": "CONV-1-{{corrida}}"
    },
    "creado_en": "<fecha y hora>",
    "creado_por": "2",
    "estado": "FINALIZADO",
    "finalizado_en": "<fecha y hora>",
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
        "cantidad_comprometida": "600.00",
        "cantidad_liberada": "600.00",
        "cantidad_pendiente": "0.00",
        "cantidad_reservada": "800.00",
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
      "razon_social": "Rescatistas de Prueba (Postman I-3.6)"
    },
    "vencido_en": null
  }
]
```

### 7.7 Sin token

- **Pedido:** `POST {{base_url}}/emergencias/EMG-2-{{corrida}}/bloqueo`
- **Token (pestaña Authorization):** ninguno
- **Qué hace el endpoint:** *Validar ofertas*, la tarea de servicio que corre cuando vence la ventana de la convocatoria. Bonita le pide a la webapp el JSON de ofertas y lo manda tal cual: la API valida cada línea por niveles de competencia (total, parcial o no habilitada, con su motivo y el rol sugerido) y **bloquea lo que acepta**, todo en una transacción con `SELECT … FOR UPDATE`. Repetirlo reemplaza los bloqueos de la convocatoria.
- **Qué prueba este caso:** Sin token no se invoca nada.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "convocatoria_referencia": "CONV-2-{{corrida}}",
  "emergencia_referencia": "EMG-2-{{corrida}}",
  "fecha_cierre": "{{cierre_vencido}}",
  "fecha_limite_adjudicacion": "{{limite_futuro}}",
  "ofertas": []
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

### 7.8 Login de la ONG de prueba

- **Pedido:** `POST {{base_url}}/login`
- **Token (pestaña Authorization):** ninguno
- **Qué hace el endpoint:** Inicio de sesión (I-3.1). Devuelve un JWT con el rol de la cuenta en el claim `rol`. No pide token.
- **Qué prueba este caso:** Para el caso siguiente. Guarda el token en `token_ong`.

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

### 7.9 La ONG no puede bloquear con su propio token

- **Pedido:** `POST {{base_url}}/emergencias/EMG-2-{{corrida}}/bloqueo`
- **Token (pestaña Authorization):** `{{token_ong}}` (*Bearer Token*)
- **Qué hace el endpoint:** *Validar ofertas*, la tarea de servicio que corre cuando vence la ventana de la convocatoria. Bonita le pide a la webapp el JSON de ofertas y lo manda tal cual: la API valida cada línea por niveles de competencia (total, parcial o no habilitada, con su motivo y el rol sugerido) y **bloquea lo que acepta**, todo en una transacción con `SELECT … FOR UPDATE`. Repetirlo reemplaza los bloqueos de la convocatoria.
- **Qué prueba este caso:** Las ONGs ofertan en la webapp; las operaciones del proceso las invoca Bonita.

**Body** (pestaña *Body* → *raw* → *JSON*):

```json
{
  "convocatoria_referencia": "CONV-2-{{corrida}}",
  "emergencia_referencia": "EMG-2-{{corrida}}",
  "fecha_cierre": "{{cierre_vencido}}",
  "fecha_limite_adjudicacion": "{{limite_futuro}}",
  "ofertas": []
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

## 8. Estado final

Cómo quedó la ONG de prueba.

### 8.1 Inventario final de la ONG de prueba

- **Pedido:** `GET {{base_url}}/ongs/{{ong_id}}/recursos`
- **Token (pestaña Authorization):** ninguno
- **Qué hace el endpoint:** Inventario de una ONG por tipo de recurso: total, bloqueado, comprometido y disponible. Es público.
- **Qué prueba este caso:** Los paramédicos volvieron todos al stock; de las raciones quedan 1400, porque se consumieron 600.

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
    "cantidad_disponible": "1400.00",
    "cantidad_total": "1400.00",
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
]
```

