#!/bin/sh
# Preparação do banco antes de subir o processo web, em todo boot e ambiente.
#
# `createcachetable` cria a tabela do cache `throttle`: é comando, não migration,
# e sem ela todo endpoint com rate limit devolve 500. Os dois passos ficavam
# duplicados no `command:` dos composes, fáceis de sair de sincronia.
#
# O `exec` final substitui o shell pelo processo web, para ele receber os sinais do
# Docker direto e o container parar sem esperar timeout.
set -e

echo "==> Aplicando migrations"
python manage.py migrate --noinput

echo "==> Garantindo a tabela de cache do throttle"
python manage.py createcachetable

echo "==> Iniciando: $*"
exec "$@"
