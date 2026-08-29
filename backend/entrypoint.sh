#!/bin/sh
# Preparação do banco antes de subir o processo web.
#
# Estes dois passos precisam rodar em todo boot, em qualquer ambiente, e antes de
# qualquer requisição ser aceita:
#
#   migrate            — aplica as migrations versionadas. Idempotente.
#   createcachetable   — cria a tabela do cache `throttle` (DatabaseCache). É um
#                        comando, não uma migration, então não vem no migrate.
#                        Sem ela, todo endpoint com rate limit devolve erro 500.
#
# Ficavam duplicados no `command:` dos dois composes, onde era fácil um sair de
# sincronia com o outro. Aqui existem uma vez, e cada ambiente só decide o
# processo final: runserver em desenvolvimento, gunicorn (CMD da imagem) em
# produção. O `exec` no fim substitui o shell pelo processo web, para que ele
# receba os sinais do Docker diretamente e o container pare sem esperar timeout.
set -e

echo "==> Aplicando migrations"
python manage.py migrate --noinput

echo "==> Garantindo a tabela de cache do throttle"
python manage.py createcachetable

echo "==> Iniciando: $*"
exec "$@"
