"""Extensiones de Flask inicializadas por la Application Factory."""

from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_smorest import Api
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import BigInteger, MetaData
from sqlalchemy.orm import DeclarativeBase, registry

CONVENCION_DE_NOMBRES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    registry = registry(
        metadata=MetaData(naming_convention=CONVENCION_DE_NOMBRES),
        type_annotation_map={int: BigInteger},
    )


db = SQLAlchemy(model_class=Base)
migrate = Migrate()
api = Api()
jwt = JWTManager()
