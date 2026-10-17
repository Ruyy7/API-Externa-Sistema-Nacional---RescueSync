"""I-3.1: registro directo de ONGs con sus categorías, login con JWT y cuentas de servicio."""

import pytest
from flask_jwt_extended import decode_token

from app.config import _con_driver_psycopg
from app.extensions import db
from app.models import ONG, Cuenta
from app.schemas.cuentas import cuit_valido
from app.security import RolSistema
from tests.utiles import URL, headers, pedido

CUIT = "30-71234567-1"  # dígito verificador válido
EMAIL = "contacto@brigada.org.ar"
PASSWORD = "clave-segura-1"


def registro(**cambios) -> dict:
    datos = {
        "razon_social": "Brigada Solidaria Sur",
        "cuit": CUIT,
        "email_contacto": EMAIL,
        "telefono": "221 555-0101",
        "password": PASSWORD,
        "categorias": [
            {"tipo_recurso": "PARAMEDICO", "cantidad_maxima": 10},
            {"tipo_recurso": "AGUA_POTABLE", "cantidad_maxima": "1500.5"},
        ],
    }
    return datos | cambios


def registrar(client, **cambios):
    return client.post("/api/v1/ongs", json=registro(**cambios))


def login(client, usuario: str = EMAIL, password: str = PASSWORD):
    return client.post("/api/v1/login", json={"usuario": usuario, "password": password})


def token_de_la_ong(client) -> dict:
    assert registrar(client).status_code == 201
    respuesta = login(client)
    assert respuesta.status_code == 200, respuesta.json
    return {"Authorization": f"Bearer {respuesta.json['access_token']}"}


def cuenta_de_servicio(usuario: str, rol: RolSistema, password: str = "servicio-1234") -> None:
    cuenta = Cuenta(usuario=usuario, rol=rol)
    cuenta.definir_password(password)
    db.session.add(cuenta)
    db.session.commit()


# --- Registro ---


def test_la_ong_se_registra_sola_y_queda_habilitada_con_sus_categorias(client):
    respuesta = registrar(client)

    assert respuesta.status_code == 201
    ong = respuesta.json
    assert (ong["cuit"], ong["estado"], ong["habilitada"]) == (CUIT, "HABILITADA", True)
    maximos = {c["tipo_recurso"]["codigo"]: c["cantidad_total"] for c in ong["categorias"]}
    assert maximos == {"PARAMEDICO": "10.00", "AGUA_POTABLE": "1500.50"}
    assert "password" not in ong and "password_hash" not in ong


@pytest.mark.parametrize(
    ("cambios", "codigo"),
    [
        ({"cuit": "30-71234567-2"}, "VALIDACION"),  # dígito verificador incorrecto
        ({"cuit": "30712345671"}, "VALIDACION"),  # sin guiones
        ({"password": "corta"}, "VALIDACION"),
        ({"categorias": []}, "VALIDACION"),
        (
            {"categorias": [{"tipo_recurso": "DRON", "cantidad_maxima": 2}]},
            "TIPO_RECURSO_DESCONOCIDO",
        ),
        ({"categorias": [{"tipo_recurso": "PARAMEDICO", "cantidad_maxima": "2.5"}]}, "VALIDACION"),
        (
            {"categorias": [{"tipo_recurso": "CARPA", "cantidad_maxima": 1}] * 2},
            "VALIDACION",
        ),
    ],
    ids=[
        "dv-incorrecto",
        "formato",
        "password-corta",
        "sin-categorias",
        "tipo-desconocido",
        "personas-con-decimales",
        "categoria-repetida",
    ],
)
def test_el_registro_valida_los_datos(client, cambios, codigo):
    respuesta = registrar(client, **cambios)

    assert respuesta.status_code == 422
    assert respuesta.json["codigo"] == codigo
    assert db.session.query(ONG).filter_by(razon_social="Brigada Solidaria Sur").count() == 0


def test_no_se_registra_dos_veces_el_mismo_cuit_ni_el_mismo_email(client):
    registrar(client)

    mismo_cuit = registrar(client, email_contacto="otro@brigada.org.ar")
    mismo_email = registrar(client, cuit="30-70123456-8", email_contacto=EMAIL.upper())

    assert mismo_cuit.status_code == mismo_email.status_code == 409
    assert mismo_cuit.json["codigo"] == "CUIT_DUPLICADO"
    assert mismo_email.json["codigo"] == "USUARIO_DUPLICADO"


def test_una_ong_recien_registrada_ya_se_puede_validar(client):
    """Integración con I-3.3: las categorías del registro son lo que lee la validación."""
    registrar(client)
    lineas = [
        {"lote_referencia": "L1", "ong_cuit": CUIT, "tipo_recurso": "PARAMEDICO",
         "cantidad_ofrecida": "10", "cantidad_requerida": "10"},
        {"lote_referencia": "L2", "ong_cuit": CUIT, "tipo_recurso": "BOMBERO",
         "cantidad_ofrecida": "3", "cantidad_requerida": "3"},
    ]  # fmt: skip
    cuerpo = {"convocatoria_referencia": "C-1", "ofertas": [{"oferta_referencia": "O-1",
                                                               "items": lineas}]}  # fmt: skip

    respuesta = client.post("/api/v1/validaciones", json=cuerpo, headers=headers())

    paramedicos, bomberos = respuesta.json["ofertas"][0]["items"]
    assert (paramedicos["nivel"], paramedicos["cantidad_aceptada"]) == ("TOTAL", "10.00")
    assert (bomberos["nivel"], bomberos["motivo"]) == ("NO_HABILITADO", "NO_INSCRIPTA")


# --- Login ---


def test_la_ong_inicia_sesion_con_su_email(client):
    registrar(client)

    respuesta = login(client, usuario=f"  {EMAIL.upper()} ")

    assert respuesta.status_code == 200
    assert (respuesta.json["token_type"], respuesta.json["rol"]) == ("Bearer", "ONG")
    assert respuesta.json["expira_en_segundos"] == 8 * 3600
    claims = decode_token(respuesta.json["access_token"])
    assert (claims["rol"], claims["ong_cuit"]) == ("ONG", CUIT)


def test_las_credenciales_invalidas_dan_el_mismo_401(client):
    registrar(client)

    sin_usuario = login(client, usuario="nadie@ejemplo.org")
    mala_clave = login(client, password="otra-clave-123")

    assert sin_usuario.status_code == mala_clave.status_code == 401
    assert sin_usuario.json == mala_clave.json
    assert sin_usuario.json["codigo"] == "CREDENCIALES_INVALIDAS"


def test_una_cuenta_inactiva_no_entra(client):
    registrar(client)
    db.session.query(Cuenta).filter_by(usuario=EMAIL).update({"activa": False})
    db.session.commit()

    assert login(client).status_code == 401


def test_la_cuenta_de_servicio_entra_y_usa_los_endpoints_de_i_3_4(client):
    cuenta_de_servicio("webapp", RolSistema.WEBAPP)

    token = login(client, "webapp", "servicio-1234").json
    reserva = client.post(
        URL, json=pedido(), headers={"Authorization": f"Bearer {token['access_token']}"}
    )

    assert token["rol"] == "SISTEMA_WEBAPP"
    assert reserva.status_code == 201


# --- Roles ---


def test_el_token_de_una_ong_no_reserva_ni_compromete(client):
    ong = token_de_la_ong(client)

    assert client.post(URL, json=pedido(), headers=ong).status_code == 403
    assert client.get(URL, headers=ong).status_code == 403


def test_un_token_de_servicio_no_tiene_ong(client):
    respuesta = client.get("/api/v1/ongs/yo", headers=headers(RolSistema.WEBAPP))

    assert respuesta.status_code == 403
    assert client.get("/api/v1/ongs/yo").status_code == 401


# --- Categorías de la propia ONG ---


def test_la_ong_consulta_sus_categorias(client):
    respuesta = client.get("/api/v1/ongs/yo", headers=token_de_la_ong(client))

    assert respuesta.json["cuit"] == CUIT
    assert {c["tipo_recurso"]["codigo"] for c in respuesta.json["categorias"]} == {
        "PARAMEDICO",
        "AGUA_POTABLE",
    }


def test_la_ong_actualiza_sus_topes_y_categorias(client):
    ong = token_de_la_ong(client)
    nuevas = [
        {"tipo_recurso": "PARAMEDICO", "cantidad_maxima": 6},
        {"tipo_recurso": "CARPA", "cantidad_maxima": 40},
    ]

    respuesta = client.put("/api/v1/ongs/yo/categorias", json={"categorias": nuevas}, headers=ong)

    maximos = {
        c["tipo_recurso"]["codigo"]: c["cantidad_total"] for c in respuesta.json["categorias"]
    }
    assert respuesta.status_code == 200
    assert maximos == {"PARAMEDICO": "6.00", "CARPA": "40.00"}  # el agua se quitó


def test_no_se_baja_un_tope_por_debajo_de_lo_reservado_ni_se_quita_lo_usado(client):
    ong = token_de_la_ong(client)
    reserva = client.post(
        URL, json=pedido(cuit=CUIT, items=(("PARAMEDICO", 4),)), headers=headers()
    )
    assert reserva.status_code == 201, reserva.json

    tope_bajo = client.put(
        "/api/v1/ongs/yo/categorias",
        json={"categorias": [{"tipo_recurso": "PARAMEDICO", "cantidad_maxima": 3},
                             {"tipo_recurso": "AGUA_POTABLE", "cantidad_maxima": 10}]},
        headers=ong,
    )  # fmt: skip
    sin_paramedicos = client.put(
        "/api/v1/ongs/yo/categorias",
        json={"categorias": [{"tipo_recurso": "AGUA_POTABLE", "cantidad_maxima": 10}]},
        headers=ong,
    )
    justo = client.put(
        "/api/v1/ongs/yo/categorias",
        json={"categorias": [{"tipo_recurso": "PARAMEDICO", "cantidad_maxima": 4}]},
        headers=ong,
    )

    assert tope_bajo.status_code == sin_paramedicos.status_code == 409
    assert tope_bajo.json["codigo"] == "CATEGORIA_EN_USO"
    assert "PARAMEDICO" in tope_bajo.json["detalles"]["categorias"]
    assert justo.status_code == 200


# --- Configuración y comandos ---


@pytest.mark.parametrize(
    ("url", "esperada"),
    [
        ("postgres://u:p@h:5432/b", "postgresql+psycopg://u:p@h:5432/b"),
        ("postgresql://u:p@h/b", "postgresql+psycopg://u:p@h/b"),
        ("postgresql+psycopg://u:p@db:5432/b", "postgresql+psycopg://u:p@db:5432/b"),
    ],
)
def test_la_url_de_render_se_convierte_al_driver_psycopg(url, esperada):
    assert _con_driver_psycopg(url) == esperada


def test_cuit_valido():
    assert cuit_valido("30-71234567-1")
    assert not cuit_valido("30-71234567-9")
    assert not cuit_valido("20-1234567-8")


def test_el_comando_crea_las_cuentas_de_servicio_con_las_claves_del_entorno(app, client):
    app.config["CUENTAS_DE_SERVICIO"] = {
        "webapp": ("SISTEMA_WEBAPP", "clave-webapp-1"),
        "bonita": ("SISTEMA_BONITA", None),
    }

    salida = app.test_cli_runner().invoke(args=["cuentas-servicio"]).output

    assert "bonita: sin contraseña configurada" in salida
    assert login(client, "webapp", "clave-webapp-1").json["rol"] == "SISTEMA_WEBAPP"
    assert login(client, "bonita", "cualquiera").status_code == 401


def test_el_seed_si_vacia_no_pisa_los_datos(app):
    salida = app.test_cli_runner().invoke(args=["seed", "--si-vacia"]).output

    assert "ya tiene datos" in salida
