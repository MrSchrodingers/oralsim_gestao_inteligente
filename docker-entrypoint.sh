#!/bin/sh
set -e

# -----------------------------------------------------------------------------
# Este script aguarda o PostgreSQL ficar pronto, executa as migrations do Django
# e, em seguida, inicia Uvicorn (para métricas) e Daphne (para a API).
# -----------------------------------------------------------------------------

# Função para aguardar PostgreSQL
# wait_for_postgres() {
#   echo "⏳ Aguardando PostgreSQL em ${DB_HOST}:${DB_PORT} (database: ${DB_NAME}, user: ${DB_USER})…"
#   until PGPASSWORD="${DB_PASS}" \
#         psql -h 127.0.0.1 -p 5432 -U oralsim_user -d oralsim_db -c  > /dev/null 2>&1; do
#     sleep 2
#   done
#   echo "✅ PostgreSQL pronto."
# }

# Aguarda RabbitMQ
# wait_for_rabbitmq() {
#   echo "⏳ Aguardando RabbitMQ em ${RABBITMQ_HOST:-rabbitmq}:${RABBITMQ_AMQP_PORT:-5672}…"
#   until rabbitmq-diagnostics -q ping > /dev/null 2>&1; do
#     sleep 2
#   done
#   echo "✅ RabbitMQ pronto."
# }

# Aguarda Redis
# wait_for_redis() {
#   echo "⏳ Aguardando Redis em ${REDIS_HOST:-redis}:${REDIS_PORT:-6379}…"
#   until redis-cli -h "${REDIS_HOST:-redis}" -p "${REDIS_PORT:-6379}" -a "${REDIS_PASSWORD}" ping > /dev/null 2>&1; do
#     sleep 2
#   done
#   echo "✅ Redis pronto."
# }

# Iniciar a sequência de preparação
echo "===== ENTRYPOINT: Iniciando processos de inicialização ====="

# 1) Aguardar o banco de dados PostgreSQL
# wait_for_postgres

# 2) Opcional: aguardar RabbitMQ
# wait_for_rabbitmq

# 3) Opcional: aguardar Redis
# wait_for_redis

# 4) Executar migrations do Django
echo "🚀 Executando migrations do Django…"
python manage.py makemigrations --no-input
python manage.py migrate --no-input

# 5) Executar eventuais comandos de collectstatic (se necessário):
echo "🚀 Coletando arquivos estáticos…"
python manage.py collectstatic --no-input

# 6) Iniciar Uvicorn (métricas) em background e, em seguida, Daphne (API)
echo "🚀 Iniciando Daphne para a API na porta 8000…"
daphne -b 0.0.0.0 -p 8000 cobranca_inteligente_api.asgi:application
