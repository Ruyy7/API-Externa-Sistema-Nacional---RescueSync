"""Service Layer y composición de dependencias por constructor."""

from dataclasses import dataclass

from flask import current_app

from app.repositories.certificaciones import CertificacionRepository
from app.repositories.ongs import ONGRepository
from app.repositories.recursos import RecursoRepository
from app.services.certificaciones import CertificacionService
from app.services.ongs import ONGService
from app.services.recursos import RecursoService
from app.services.validaciones import ValidacionService


@dataclass
class Servicios:
    ongs: ONGService
    certificaciones: CertificacionService
    recursos: RecursoService
    validaciones: ValidacionService


def crear_servicios() -> Servicios:
    ongs = ONGService(ONGRepository())
    return Servicios(
        ongs=ongs,
        certificaciones=CertificacionService(CertificacionRepository(), ongs),
        recursos=RecursoService(RecursoRepository(), ongs),
        validaciones=ValidacionService(RecursoRepository(), ONGRepository()),
    )


def servicios() -> Servicios:
    return current_app.extensions["servicios"]
