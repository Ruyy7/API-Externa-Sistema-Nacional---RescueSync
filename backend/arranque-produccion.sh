#!/bin/sh
# Arranque en Render (render.yaml). El plan gratuito no tiene consola ni comando previo al
# despliegue, así que migraciones, catálogo y cuentas de servicio se preparan en cada arranque.
# Los tres pasos son idempotentes. El desarrollo local sigue usando el CMD del Dockerfile.
set -e

flask db upgrade
# Solo carga el seed si la base está vacía: el servicio gratuito se reinicia seguido
flask seed --si-vacia
flask cuentas-servicio

# Render indica el puerto en $PORT
exec gunicorn --bind "0.0.0.0:${PORT:-10000}" --workers 2 --timeout 60 \
    --access-logfile - "app:create_app()"
