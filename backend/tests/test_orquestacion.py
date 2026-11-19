"""Operaciones que invoca Bonita como orquestador: validar y bloquear, liberar los bloqueos,
comprometer la adjudicación e informar actividades (docs/08-orquestacion-bonita.md).

Datos del seed que usan estos tests (disponible = total - bloqueada - comprometida):
- Rescatistas del Río (30-11111111-1, HABILITADA): PARAMEDICO 12-2-0 = 10, RESCATISTA 20-3-2 = 15.
- Alimentos Solidarios (30-22222222-2, HABILITADA): RACION_ALIMENTO 5000-700-300 = 4000,
  AGUA_POTABLE 2500-300-200 = 2000.
- Ayuda en Registro (30-33333333-3, PENDIENTE): PARAMEDICO 100.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest

from app.models.comun import ahora
from app.security import RolSistema
from tests.test_concurrencia import _esperar_sesiones_bloqueadas, _retener_fila
from tests.utiles import PENDIENTE, RIO, headers, inventario, mover_fechas

ALIMENTOS = "30-22222222-2"
URL = "/api/v1/emergencias"
# Fecha de cumplimiento de las actividades. Es fija: un reintento es el mismo pedido, con la
# misma fecha (la webapp manda la que guardó al registrar la actividad).
HACE_UNA_HORA = (ahora() - timedelta(hours=1)).isoformat()


def bonita() -> dict:
    return headers(RolSistema.BONITA)


def pedido_de_bloqueo(
    ofertas: dict,
    *,
    convocatoria: str = "conv-1",
    cierre: timedelta = timedelta(minutes=-1),
    limite: timedelta = timedelta(days=7),
) -> dict:
    """El JSON de ofertas que Bonita le pide a la webapp al vencer la ventana.
    ofertas: {referencia: [(cuit, tipo, ofrecida, requerida)]}."""
    return {
        "convocatoria_referencia": convocatoria,
        "fecha_cierre": (ahora() + cierre).isoformat(),
        "fecha_limite_adjudicacion": (ahora() + limite).isoformat(),
        "ofertas": [
            {
                "oferta_referencia": referencia,
                "items": [
                    {
                        "lote_referencia": f"lote-{tipo}",
                        "ong_cuit": cuit,
                        "tipo_recurso": tipo,
                        "cantidad_ofrecida": str(ofrecida),
                        "cantidad_requerida": str(requerida),
                    }
                    for cuit, tipo, ofrecida, requerida in lineas
                ],
            }
            for referencia, lineas in ofertas.items()
        ],
    }


def bloquear(client, ofertas: dict, emergencia: str = "emergencia-1", **kwargs):
    return client.post(
        f"{URL}/{emergencia}/bloqueo", json=pedido_de_bloqueo(ofertas, **kwargs), headers=bonita()
    )


def bloqueado(client, ofertas: dict, emergencia: str = "emergencia-1", **kwargs) -> dict:
    respuesta = bloquear(client, ofertas, emergencia, **kwargs)
    assert respuesta.status_code == 200, respuesta.json
    return respuesta.json


def adjudicar(
    client, adjudicaciones: list, emergencia: str = "emergencia-1", convocatoria: str = "conv-1"
):
    """adjudicaciones: [(oferta, cuit, [(tipo, cantidad)])]."""
    cuerpo = {
        "convocatoria_referencia": convocatoria,
        "adjudicaciones": [
            {
                "oferta_referencia": oferta,
                "ong_cuit": cuit,
                "items": [{"tipo_recurso": tipo, "cantidad": cantidad} for tipo, cantidad in items],
            }
            for oferta, cuit, items in adjudicaciones
        ],
    }
    return client.post(f"{URL}/{emergencia}/adjudicacion", json=cuerpo, headers=bonita())


def informar(client, actividades: list, emergencia: str = "emergencia-1"):
    """actividades: [(referencia, cuit, tipo, cantidad)]."""
    cuerpo = {
        "actividades": [
            {
                "actividad_referencia": referencia,
                "ong_cuit": cuit,
                "tipo_recurso": tipo,
                "cantidad": cantidad,
                "fecha": HACE_UNA_HORA,
                "observaciones": "Tarea cumplida",
            }
            for referencia, cuit, tipo, cantidad in actividades
        ]
    }
    return client.post(f"{URL}/{emergencia}/actividades", json=cuerpo, headers=bonita())


def compromisos(client, emergencia: str = "emergencia-1") -> dict:
    """{oferta: compromiso} de la emergencia, como los ve el auditor."""
    respuesta = client.get(
        "/api/v1/compromisos",
        query_string={"emergencia": emergencia},
        headers=headers(RolSistema.AUDITOR),
    )
    assert respuesta.status_code == 200, respuesta.json
    return {compromiso["oferta_referencia"]: compromiso for compromiso in respuesta.json}


def reservado(compromiso: dict) -> dict:
    return {i["tipo_recurso"]["codigo"]: i["cantidad_reservada"] for i in compromiso["items"]}


UNA_OFERTA = {"oferta-1": [(RIO, "PARAMEDICO", 5, 5)]}


# --- Validar ofertas: validación y bloqueo -----------------------------------------------------


def test_valida_y_bloquea_lo_aceptado(client):
    respuesta = bloquear(client, UNA_OFERTA)

    assert respuesta.status_code == 200, respuesta.json
    assert respuesta.json["convocatoria_referencia"] == "conv-1"
    assert respuesta.json["emergencia_referencia"] == "emergencia-1"
    assert respuesta.json["reservas"] == 1
    oferta = respuesta.json["ofertas"][0]
    assert oferta["nivel"] == "TOTAL"
    linea = oferta["items"][0]
    assert (linea["cantidad_aceptada"], linea["nivel"], linea["rol_sugerido"]) == (
        "5.00",
        "TOTAL",
        "PRINCIPAL",
    )
    assert inventario("PARAMEDICO").cantidad_bloqueada == 2 + 5
    compromiso = compromisos(client)["oferta-1"]
    assert (compromiso["estado"], compromiso["creado_por"]) == ("RESERVADO", "tests")
    assert reservado(compromiso) == {"PARAMEDICO": "5.00"}


def test_acepta_en_parte_y_bloquea_solo_lo_disponible(client):
    respuesta = bloqueado(client, {"oferta-1": [(RIO, "PARAMEDICO", 14, 14)]})

    linea = respuesta["ofertas"][0]["items"][0]
    assert (linea["cantidad_aceptada"], linea["nivel"], linea["motivo"]) == (
        "10.00",
        "PARCIAL",
        "EXCEDE_DISPONIBLE",
    )
    assert inventario("PARAMEDICO").cantidad_bloqueada == 2 + 10


def test_una_ong_no_habilitada_no_bloquea_nada(client):
    respuesta = bloqueado(client, {"oferta-1": [(PENDIENTE, "PARAMEDICO", 5, 5)]})

    linea = respuesta["ofertas"][0]["items"][0]
    assert (linea["nivel"], linea["motivo"]) == ("NO_HABILITADO", "ONG_NO_HABILITADA")
    assert respuesta["reservas"] == 0
    assert inventario("PARAMEDICO", PENDIENTE).cantidad_bloqueada == 0
    assert compromisos(client) == {}


def test_lo_bloqueado_por_una_emergencia_no_esta_disponible_para_otra(client):
    """El caso de sobre-asignación: la ONG ofrece los mismos paramédicos en dos emergencias."""
    bloqueado(client, {"oferta-1": [(RIO, "PARAMEDICO", 8, 8)]})

    otra = bloqueado(
        client,
        {"oferta-2": [(RIO, "PARAMEDICO", 5, 5)]},
        emergencia="emergencia-2",
        convocatoria="conv-2",
    )

    linea = otra["ofertas"][0]["items"][0]
    assert (linea["cantidad_habilitada"], linea["cantidad_aceptada"]) == ("2.00", "2.00")
    assert (linea["nivel"], linea["motivo"]) == ("PARCIAL", "EXCEDE_DISPONIBLE")
    assert inventario("PARAMEDICO").cantidad_disponible == 0


def test_dos_ofertas_de_la_misma_ong_se_evaluan_en_orden(client):
    respuesta = bloqueado(
        client,
        {"oferta-1": [(RIO, "PARAMEDICO", 8, 8)], "oferta-2": [(RIO, "PARAMEDICO", 5, 8)]},
    )

    aceptado = [oferta["items"][0]["cantidad_aceptada"] for oferta in respuesta["ofertas"]]
    assert aceptado == ["8.00", "2.00"]
    assert inventario("PARAMEDICO").cantidad_bloqueada == 2 + 10


def test_repetir_el_bloqueo_no_bloquea_dos_veces(client):
    primera = bloqueado(client, UNA_OFERTA)
    id_original = compromisos(client)["oferta-1"]["id"]

    segunda = bloqueado(client, UNA_OFERTA)

    assert segunda["ofertas"] == primera["ofertas"]
    assert inventario("PARAMEDICO").cantidad_bloqueada == 2 + 5
    assert compromisos(client)["oferta-1"]["id"] == id_original


def test_validar_de_nuevo_reemplaza_los_bloqueos_de_la_convocatoria(client):
    bloqueado(
        client,
        {
            "oferta-1": [(RIO, "PARAMEDICO", 5, 5), (RIO, "RESCATISTA", 4, 4)],
            "oferta-2": [(ALIMENTOS, "RACION_ALIMENTO", 100, 100)],
        },
    )

    # La ONG achicó su oferta, otra se retiró y entró una nueva
    bloqueado(
        client,
        {
            "oferta-1": [(RIO, "PARAMEDICO", 3, 5)],
            "oferta-3": [(ALIMENTOS, "AGUA_POTABLE", 50, 50)],
        },
    )

    assert inventario("PARAMEDICO").cantidad_bloqueada == 2 + 3
    assert inventario("RESCATISTA").cantidad_bloqueada == 3
    assert inventario("RACION_ALIMENTO", ALIMENTOS).cantidad_bloqueada == 700
    assert inventario("AGUA_POTABLE", ALIMENTOS).cantidad_bloqueada == 300 + 50
    actuales = compromisos(client)
    assert {oferta: c["estado"] for oferta, c in actuales.items()} == {
        "oferta-1": "RESERVADO",
        "oferta-2": "CANCELADO",
        "oferta-3": "RESERVADO",
    }
    assert reservado(actuales["oferta-1"]) == {"PARAMEDICO": "3.00"}


def test_una_convocatoria_sin_ofertas_tambien_se_valida(client):
    respuesta = bloqueado(client, {})

    assert (respuesta["ofertas"], respuesta["reservas"]) == ([], 0)
    # La emergencia queda registrada: después se puede liberar y cerrar
    estado = client.get(f"{URL}/emergencia-1/liberacion", headers=bonita())
    assert estado.status_code == 200


def test_un_tipo_de_recurso_desconocido_rechaza_todo_el_pedido(client):
    respuesta = bloquear(
        client, {"oferta-1": [(RIO, "PARAMEDICO", 5, 5), (RIO, "NO_EXISTE", 1, 1)]}
    )

    assert respuesta.status_code == 422
    assert respuesta.json["codigo"] == "TIPO_RECURSO_DESCONOCIDO"
    assert inventario("PARAMEDICO").cantidad_bloqueada == 2


def test_el_limite_de_adjudicacion_no_puede_ser_anterior_al_cierre(client):
    respuesta = bloquear(client, UNA_OFERTA, limite=timedelta(days=-1))

    assert respuesta.status_code == 422


def test_no_se_valida_de_nuevo_una_convocatoria_ya_adjudicada(client):
    bloqueado(client, UNA_OFERTA)
    assert adjudicar(client, [("oferta-1", RIO, [("PARAMEDICO", 5)])]).status_code == 200

    respuesta = bloquear(client, UNA_OFERTA)

    assert respuesta.status_code == 409
    assert respuesta.json["codigo"] == "CONVOCATORIA_ADJUDICADA"
    assert inventario("PARAMEDICO").cantidad_comprometida == 5


# --- Reabrir o reformular: liberar los bloqueos ------------------------------------------------


def test_reabrir_libera_los_bloqueos_y_la_nueva_validacion_bloquea_otra_vez(client):
    bloqueado(client, UNA_OFERTA)
    id_original = compromisos(client)["oferta-1"]["id"]

    liberado = client.post(f"{URL}/emergencia-1/desbloqueo", headers=bonita())

    assert liberado.status_code == 200, liberado.json
    assert liberado.json == {"emergencia_referencia": "emergencia-1", "reservas_canceladas": 1}
    assert inventario("PARAMEDICO").cantidad_bloqueada == 2
    assert compromisos(client)["oferta-1"]["estado"] == "CANCELADO"

    # Vence la nueva ventana: la misma oferta se valida de nuevo, ahora con más paramédicos
    bloqueado(client, {"oferta-1": [(RIO, "PARAMEDICO", 7, 7)]})

    compromiso = compromisos(client)["oferta-1"]
    assert (compromiso["id"], compromiso["estado"]) == (id_original, "RESERVADO")
    assert reservado(compromiso) == {"PARAMEDICO": "7.00"}
    assert inventario("PARAMEDICO").cantidad_bloqueada == 2 + 7


def test_desbloquear_sin_bloqueos_no_cambia_nada(client):
    respuesta = client.post(f"{URL}/emergencia-desconocida/desbloqueo", headers=bonita())

    assert respuesta.status_code == 200
    assert respuesta.json["reservas_canceladas"] == 0


def test_desbloquear_no_toca_lo_comprometido(client):
    bloqueado(client, UNA_OFERTA)
    adjudicar(client, [("oferta-1", RIO, [("PARAMEDICO", 5)])])

    respuesta = client.post(f"{URL}/emergencia-1/desbloqueo", headers=bonita())

    assert respuesta.json["reservas_canceladas"] == 0
    assert inventario("PARAMEDICO").cantidad_comprometida == 5


# --- Comprometer recursos ----------------------------------------------------------------------

DOS_OFERTAS = {
    "oferta-1": [(RIO, "PARAMEDICO", 5, 5)],
    "oferta-2": [(ALIMENTOS, "RACION_ALIMENTO", 100, 100)],
}


def test_compromete_lo_adjudicado_y_libera_el_resto(client):
    bloqueado(client, DOS_OFERTAS)

    respuesta = adjudicar(client, [("oferta-1", RIO, [("PARAMEDICO", 3)])])

    assert respuesta.status_code == 200, respuesta.json
    assert respuesta.json["reservas_canceladas"] == 1
    assert [c["oferta_referencia"] for c in respuesta.json["compromisos"]] == ["oferta-1"]
    paramedicos = inventario("PARAMEDICO")
    # De los 5 bloqueados se adjudicaron 3: los otros 2 vuelven a estar disponibles
    assert (paramedicos.cantidad_bloqueada, paramedicos.cantidad_comprometida) == (2, 3)
    assert inventario("RACION_ALIMENTO", ALIMENTOS).cantidad_bloqueada == 700
    actuales = compromisos(client)
    assert actuales["oferta-1"]["estado"] == "COMPROMETIDO"
    assert actuales["oferta-2"]["estado"] == "CANCELADO"


def test_repetir_la_misma_adjudicacion_no_cambia_nada(client):
    bloqueado(client, DOS_OFERTAS)
    adjudicacion = [("oferta-1", RIO, [("PARAMEDICO", 3)])]
    assert adjudicar(client, adjudicacion).status_code == 200

    respuesta = adjudicar(client, adjudicacion)

    assert respuesta.status_code == 200, respuesta.json
    assert respuesta.json["reservas_canceladas"] == 0
    assert inventario("PARAMEDICO").cantidad_comprometida == 3


def test_si_una_adjudicacion_no_es_valida_no_se_compromete_ninguna(client):
    bloqueado(client, DOS_OFERTAS)

    respuesta = adjudicar(
        client,
        [
            ("oferta-1", RIO, [("PARAMEDICO", 3)]),
            ("oferta-2", ALIMENTOS, [("RACION_ALIMENTO", 101)]),  # supera lo bloqueado
        ],
    )

    assert respuesta.status_code == 422
    assert respuesta.json["codigo"] == "ADJUDICACION_INVALIDA"
    assert [e["oferta_referencia"] for e in respuesta.json["detalles"]["adjudicaciones"]] == [
        "oferta-2"
    ]
    assert inventario("PARAMEDICO").cantidad_comprometida == 0
    assert {c["estado"] for c in compromisos(client).values()} == {"RESERVADO"}


def test_no_se_adjudica_una_oferta_sin_recursos_bloqueados(client):
    bloqueado(client, UNA_OFERTA)

    respuesta = adjudicar(client, [("oferta-9", RIO, [("PARAMEDICO", 1)])])

    assert respuesta.status_code == 422
    assert (
        "No tiene recursos bloqueados" in respuesta.json["detalles"]["adjudicaciones"][0]["error"]
    )


def test_no_adjudicar_nada_libera_todos_los_bloqueos(client):
    bloqueado(client, DOS_OFERTAS)

    respuesta = adjudicar(client, [])

    assert respuesta.status_code == 200, respuesta.json
    assert (respuesta.json["compromisos"], respuesta.json["reservas_canceladas"]) == ([], 2)
    assert inventario("PARAMEDICO").cantidad_bloqueada == 2


def test_con_los_bloqueos_vencidos_no_se_compromete(client):
    bloqueado(client, UNA_OFERTA)
    mover_fechas("conv-1", cierre=timedelta(days=-8), limite=timedelta(minutes=-1))

    respuesta = adjudicar(client, [("oferta-1", RIO, [("PARAMEDICO", 5)])])

    assert respuesta.status_code == 409
    assert respuesta.json["codigo"] == "RESERVA_VENCIDA"
    assert inventario("PARAMEDICO").cantidad_comprometida == 0


def test_la_adjudicacion_es_de_una_convocatoria_de_la_emergencia(client):
    bloqueado(client, UNA_OFERTA)

    respuesta = adjudicar(
        client, [("oferta-1", RIO, [("PARAMEDICO", 5)])], emergencia="emergencia-2"
    )

    assert respuesta.status_code == 404


# --- Marcar actividad como finalizada ----------------------------------------------------------


def test_las_actividades_liberan_lo_comprometido_sin_repetir(client):
    bloqueado(client, UNA_OFERTA)
    adjudicar(client, [("oferta-1", RIO, [("PARAMEDICO", 5)])])

    primera = informar(client, [("ACT-1", RIO, "PARAMEDICO", 2)])
    # Bonita reintenta con la anterior y suma una nueva: solo la nueva libera
    segunda = informar(client, [("ACT-1", RIO, "PARAMEDICO", 2), ("ACT-2", RIO, "PARAMEDICO", 3)])

    assert primera.status_code == 200, primera.json
    assert (primera.json["nuevas"], segunda.json["nuevas"]) == (1, 1)
    assert [a["actividad_referencia"] for a in segunda.json["actividades"]] == ["ACT-1", "ACT-2"]
    assert inventario("PARAMEDICO").cantidad_comprometida == 0
    assert compromisos(client)["oferta-1"]["estado"] == "FINALIZADO"


def test_sin_actividades_nuevas_no_cambia_nada(client):
    bloqueado(client, UNA_OFERTA)

    respuesta = informar(client, [])

    assert respuesta.status_code == 200
    assert (respuesta.json["nuevas"], respuesta.json["actividades"]) == (0, [])


def test_una_actividad_que_supera_lo_pendiente_se_rechaza(client):
    bloqueado(client, UNA_OFERTA)
    adjudicar(client, [("oferta-1", RIO, [("PARAMEDICO", 5)])])

    respuesta = informar(client, [("ACT-1", RIO, "PARAMEDICO", 6)])

    assert respuesta.status_code == 409
    assert inventario("PARAMEDICO").cantidad_comprometida == 5


# --- El proceso completo, solo con la cuenta de Bonita -----------------------------------------


def test_el_proceso_completo_lo_recorre_solo_bonita(client):
    """Validar y bloquear, comprometer, informar actividades, liberar y cerrar: ningún paso
    necesita la cuenta de la webapp."""
    bloqueado(client, DOS_OFERTAS)
    adjudicar(
        client,
        [
            ("oferta-1", RIO, [("PARAMEDICO", 5)]),
            ("oferta-2", ALIMENTOS, [("RACION_ALIMENTO", 100)]),
        ],
    )
    informar(client, [("ACT-1", RIO, "PARAMEDICO", 5)])

    liberacion = client.post(f"{URL}/emergencia-1/liberacion", json={}, headers=bonita())
    cierre = client.post(
        f"{URL}/emergencia-1/cierre", json={"observaciones": "Fin"}, headers=bonita()
    )

    assert liberacion.status_code == 200, liberacion.json
    assert cierre.status_code == 201, cierre.json
    # Los paramédicos volvieron al stock; las raciones que no se informaron se consumieron al cerrar
    paramedicos = inventario("PARAMEDICO")
    assert (paramedicos.cantidad_bloqueada, paramedicos.cantidad_comprometida) == (2, 0)
    raciones = inventario("RACION_ALIMENTO", ALIMENTOS)
    assert (raciones.cantidad_total, raciones.cantidad_comprometida) == (5000 - 100, 300)
    assert bloquear(client, UNA_OFERTA).json["codigo"] == "PROYECTO_CERRADO"


# --- Seguridad: solo el orquestador ------------------------------------------------------------

OPERACIONES = ["bloqueo", "desbloqueo", "adjudicacion", "actividades"]


@pytest.mark.parametrize("operacion", OPERACIONES)
@pytest.mark.parametrize("rol", [RolSistema.WEBAPP, RolSistema.AUDITOR, RolSistema.ONG])
def test_solo_la_cuenta_de_bonita_puede_invocarlas(client, operacion, rol):
    respuesta = client.post(f"{URL}/emergencia-1/{operacion}", json={}, headers=headers(rol))

    assert respuesta.status_code == 403
    assert respuesta.json["codigo"] == "PROHIBIDO"


@pytest.mark.parametrize("operacion", OPERACIONES)
def test_sin_token_no_se_invocan(client, operacion):
    assert client.post(f"{URL}/emergencia-1/{operacion}", json={}).status_code == 401


# --- Concurrencia ------------------------------------------------------------------------------


def test_dos_validaciones_simultaneas_no_sobreasignan(app):
    """Dos emergencias validan a la vez ofertas por 8 paramédicos de la misma ONG, que tiene 10
    disponibles. Las dos esperan en el FOR UPDATE: una se queda con 8 y la otra con los 2 que
    quedan. Nunca se bloquea más de lo que hay."""
    cuerpos = {
        f"emergencia-{n}": pedido_de_bloqueo(
            {f"oferta-{n}": [(RIO, "PARAMEDICO", 8, 8)]}, convocatoria=f"conv-{n}"
        )
        for n in (1, 2)
    }
    encabezados = bonita()

    def validar(emergencia: str):
        return app.test_client().post(
            f"{URL}/{emergencia}/bloqueo", json=cuerpos[emergencia], headers=encabezados
        )

    conexion, transaccion = _retener_fila(inventario("PARAMEDICO").id)
    try:
        with ThreadPoolExecutor(max_workers=2) as hilos:
            futuros = [hilos.submit(validar, emergencia) for emergencia in cuerpos]
            _esperar_sesiones_bloqueadas(2)
            transaccion.commit()  # suelta la fila: las dos compiten de verdad
            respuestas = [futuro.result() for futuro in futuros]
    finally:
        conexion.close()

    assert [respuesta.status_code for respuesta in respuestas] == [200, 200]
    aceptado = sorted(r.json["ofertas"][0]["items"][0]["cantidad_aceptada"] for r in respuestas)
    assert aceptado == ["2.00", "8.00"]
    paramedicos = inventario("PARAMEDICO")
    assert (paramedicos.cantidad_bloqueada, paramedicos.cantidad_disponible) == (2 + 10, 0)
