"""Service Layer y composición de dependencias por constructor."""

from dataclasses import dataclass

from flask import current_app

from app.repositories.certificaciones import CertificacionRepository
from app.repositories.compromisos import CompromisoRepository, ConvocatoriaRepository
from app.repositories.cuentas import CategoriaRepository, CuentaRepository
from app.repositories.inventario import InventarioRepository
from app.repositories.ongs import ONGRepository
from app.repositories.recursos import RecursoRepository
from app.services.auth import AuthService
from app.services.certificaciones import CertificacionService
from app.services.compromisos import CompromisoService
from app.services.convocatorias import ConvocatoriaService
from app.services.onboarding import OnboardingService
from app.services.ongs import ONGService
from app.services.recursos import RecursoService
from app.services.validaciones import ValidacionService


@dataclass
class Servicios:
    ongs: ONGService
    certificaciones: CertificacionService
    recursos: RecursoService
    validaciones: ValidacionService
    compromisos: CompromisoService
    convocatorias: ConvocatoriaService
    auth: AuthService
    onboarding: OnboardingService


def crear_servicios(config) -> Servicios:
    ongs_repo = ONGRepository()
    ongs = ONGService(ongs_repo)
    compromisos_repo, convocatorias_repo = CompromisoRepository(), ConvocatoriaRepository()
    cuentas_repo = CuentaRepository()
    lock_timeout_ms = config["LOCK_TIMEOUT_MS"]
    compromisos = CompromisoService(
        compromisos_repo,
        convocatorias_repo,
        InventarioRepository(),
        ongs_repo,
        lock_timeout_ms=lock_timeout_ms,
    )
    return Servicios(
        ongs=ongs,
        certificaciones=CertificacionService(CertificacionRepository(), ongs),
        recursos=RecursoService(RecursoRepository(), ongs),
        validaciones=ValidacionService(RecursoRepository(), ongs_repo),
        compromisos=compromisos,
        convocatorias=ConvocatoriaService(
            convocatorias_repo, compromisos_repo, compromisos, lock_timeout_ms=lock_timeout_ms
        ),
        auth=AuthService(cuentas_repo),
        onboarding=OnboardingService(
            ongs_repo,
            cuentas_repo,
            CategoriaRepository(),
            InventarioRepository(),
            lock_timeout_ms=lock_timeout_ms,
        ),
    )


def servicios() -> Servicios:
    return current_app.extensions["servicios"]
