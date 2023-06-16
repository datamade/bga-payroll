#!/bin/sh
set -e
apt-get install libffi-dev
pip install -e /django-salsa-auth

if [ "$DJANGO_MANAGEPY_MIGRATE" = 'on' ]; then
    python manage.py migrate --noinput
fi

exec "$@"
