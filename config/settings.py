from pathlib import Path

from celery.schedules import crontab
from decouple import Csv, config
from kombu import Exchange, Queue  # noqa: F401

# -------------------------------
# Diretórios base
# -------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# -------------------------------
# Segurança e debug
# -------------------------------
PIPEDRIVE_WRITE_ENABLED = config("PIPEDRIVE_WRITE_ENABLED", "false").lower() == "true"
SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='', cast=Csv())

# -------------------------------
# Cookies & CSRF
# -------------------------------
SESSION_COOKIE_SECURE   = config('SESSION_COOKIE_SECURE', default=False, cast=bool) # Desenvolvido para HTTPS
SESSION_COOKIE_HTTPONLY = config('SESSION_COOKIE_HTTPONLY', default=True, cast=bool)
SESSION_COOKIE_SAMESITE = config('SESSION_COOKIE_SAMESITE', default='Lax')
CSRF_COOKIE_SECURE      = config('CSRF_COOKIE_SECURE', default=False, cast=bool) # Desenvolvido para HTTPS
CSRF_COOKIE_HTTPONLY    = config('CSRF_COOKIE_HTTPONLY', default=True, cast=bool)
CSRF_COOKIE_SAMESITE    = config('CSRF_COOKIE_SAMESITE', default='Lax')

AUTH_COOKIE_NAME     = config('AUTH_COOKIE_NAME', default='authToken') 
AUTH_COOKIE_SECURE   = config('AUTH_COOKIE_SECURE', default=False, cast=bool) # Desenvolvido para HTTPS
AUTH_COOKIE_HTTPONLY = config('AUTH_COOKIE_HTTPONLY', default=True, cast=bool)
AUTH_COOKIE_SAMESITE = config('AUTH_COOKIE_SAMESITE', default='Lax')

SECURE_SSL_REDIRECT          = config('SECURE_SSL_REDIRECT', default=False, cast=bool)
SECURE_HSTS_SECONDS          = config('SECURE_HSTS_SECONDS', default=31536000, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=True, cast=bool)
SECURE_HSTS_PRELOAD          = config('SECURE_HSTS_PRELOAD', default=True, cast=bool)
SECURE_PROXY_SSL_HEADER      = ('HTTP_X_FORWARDED_PROTO', 'https')

# -------------------------------
# CORS
# -------------------------------
CORS_ALLOW_ALL_ORIGINS = config('CORS_ALLOW_ALL_ORIGINS', default=False, cast=bool)
CORS_ALLOW_CREDENTIALS = config('CORS_ALLOW_CREDENTIALS', default=True, cast=bool)
CSRF_TRUSTED_ORIGINS  = config('CSRF_TRUSTED_ORIGINS', default='http://localhost:3001', cast=Csv())
CORS_ALLOWED_ORIGINS   = config('CORS_ALLOWED_ORIGINS',   default='http://localhost:3001', cast=Csv())
CORS_ALLOW_METHODS     = config('CORS_ALLOW_METHODS',     default='GET,POST,PUT,PATCH,DELETE,OPTIONS', cast=Csv())
CORS_ALLOW_HEADERS     = config('CORS_ALLOW_HEADERS',     default='Authorization,Content-Type,X-CSRFToken', cast=Csv())

# -------------------------------
# Celery
# -------------------------------
CELERY_BROKER_URL                 = config("CELERY_BROKER_URL")
RABBITMQ_URL                      = config("RABBITMQ_URL")
CELERY_RESULT_BACKEND             = config('CELERY_RESULT_BACKEND')
CELERY_TASK_ACKS_LATE             = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ALWAYS_EAGER          = config('CELERY_TASK_ALWAYS_EAGER', default=False, cast=bool)
CELERY_ACCEPT_CONTENT             = ["json"]
CELERY_TASK_SERIALIZER            = "json"
CELERY_TASK_QUEUES = {
    "default":      {"exchange": "default",      "routing_key": "default"},
    "dead_letter":  {"exchange": "dead_letter",  "routing_key": "dead_letter"},
    "email":        {"exchange": "email",        "routing_key": "email"},
    "sms":          {"exchange": "sms",          "routing_key": "sms"},
    "whatsapp":     {"exchange": "whatsapp",     "routing_key": "whatsapp"},
    "payment":      {"exchange": "payment",      "routing_key": "payment"},
    "metrics":      {"exchange": "metrics",      "routing_key": "metrics"},
    "sync_notify":  {"exchange": "sync_notify",  "routing_key": "sync_notify"},
    "sync_process": {"exchange": "sync_process", "routing_key": "sync_process"},
}
CELERY_TASK_DEFAULT_QUEUE = 'default'
CELERY_TASK_DEFAULT_EXCHANGE = 'default'
CELERY_TASK_DEFAULT_ROUTING_KEY = 'default'
CELERY_TASK_ROUTES = { 
                      "oralsin_core.adapters.message_broker.tasks.seed_data_task": {"queue": "sync_process"}, 
                      "oralsin_core.adapters.message_broker.tasks.post_seed_setup_task": {"queue": "sync_process"}, 
                      "oralsin_core.adapters.message_broker.tasks.run_sync_command_task": {"queue": "sync_process"}, 
}

# --- AGENDADOR (CELERY BEAT) ---
# Define a execução periódica das tarefas orquestradoras.
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

CELERY_BEAT_SCHEDULE = {
    # Executa a garantia de agendamentos para novos inadimplentes diariamente às 2 da manhã.
    'ensure-schedules-daily': {
        'task': 'cobranca_inteligente_api.tasks.run_maintenance_command',
        'schedule': crontab(minute=0, hour=2),
        'args': ('ensure_schedules',), # Nome do novo management command
    },
    # Inicia o resync diário de inadimplência para todas as clínicas às 3 da manhã.
    'schedule-daily-resync': {
        'task': 'cobranca_inteligente_api.tasks.schedule_daily_resync',
        'schedule': crontab(minute=0, hour=3),
    },
    # Agenda a atualização de deals no Pipedrive a cada 2 horas.
    'schedule-pipedrive-updates': {
        'task': 'cobranca_inteligente_api.tasks.schedule_pipedrive_updates',
        'schedule': crontab(minute=0, hour='*/2'),
    },
    # Agenda o envio de notificações e cartas toda TERÇA-FEIRA.
    'schedule-notifications-and-letters': {
        'task': 'cobranca_inteligente_api.tasks.schedule_daily_notifications',
        'schedule': crontab(minute=30, hour=8, day_of_week=2), # 0=Dom, 1=Seg, 2=Ter...
    },
    # Agenda a sincronização de acordos e dívidas antigas.
    'schedule-sync-tasks': {
        'task': 'cobranca_inteligente_api.tasks.schedule_daily_syncs',
        'schedule': crontab(minute=0, hour=4),
    },
}

# -------------------------------
# Redis
# -------------------------------
REDIS_HOST = config('REDIS_HOST')
REDIS_PORT = config('REDIS_PORT', default=6379, cast=int)
REDIS_DB   = config('REDIS_DB', default=0, cast=int)
REDIS_PASSWORD = config('REDIS_PASSWORD')

# -------------------------------
# Oralsin API
# -------------------------------
ORALSIN_API_BASE  = config('ORALSIN_API_BASE')
ORALSIN_API_TOKEN = config('ORALSIN_API_TOKEN')
ORALSIN_TIMEOUT  = int(config('ORALSIN_TIMEOUT'))

# -------------------------------
# Pipedrive API
# -------------------------------
PIPEDRIVE_API_BASE  = config('PIPEDRIVE_API_BASE', default='')
PIPEDRIVE_API_TOKEN = config('PIPEDRIVE_API_TOKEN', default='')
# settings.py
PIPEDRIVE_CF_MAP: dict[str, str] = {
    # ─── Clínica ──────────────────────────────────────────
    "clinic_name":            "f95891793f9e919fa9d29be3a6c82edd2ff6400f",  # Nome da Clínica
    "clinic_city":            "756c57e4a6e7df5ca8d01a73160b9199ccfe35ab",  # Clínica - Cidade
    "clinic_cnpj":            "",  # ➜ crie um campo “CNPJ da Clínica” e cole aqui a key
    "clinic_address":         "",  # ➜ idem endereço completo da clínica
    "clinic_phone":           "",  # ➜ telefone fixo da clínica

    # ─── Paciente / Deal tipo “Paciente” ─────────────────
    "patient_type":           "2c754a784e3114a5d9b69cf8851837ddcd5ccbba",  # enum Tipo (id 28 = Paciente)
    "patient_first_name":     "",  # ➜ crie “Primeiro nome” (varchar)   e cole a key
    "patient_last_name":      "",  # ➜ crie “Sobrenome”
    "patient_cpf":            "",  # ➜ crie “CPF”
    "patient_address":        "",  # ➜ crie “Endereço do Paciente”
    "patient_payment_method": "39c2c93a9a020b1f515557bb4faa9efdccfed474",  # Paciente – Forma de Pagamento
    "patient_status":         "e037f6d531c01dc45fb26fc6563ae1df46cd95fe",  # Paciente – Status Tratamento

    # ─── Contrato / Parcelas ─────────────────────────────
    "contract_numbers":       "df11fb8b42382035e521de220bf2503a1b85a0a7",  # Contratos
    "oldest_due_date":        "286dd062f81694d085b197db7deb3b8ebf7b06ed",  # Vencimento mais antigo
    "newest_due_date":        "f57b985a8cb239495d04c7ff30a17785a958bc59",  # Vencimento mais recente
    "overdue_count":          "91359d6aae291631544a6c2c6b477ab1c5c2317b",  # Qtde parcelas vencidas
    "future_count":           "14f3c3fe363ed953a35c3b43ddbb3b8a2083abc0",  # Qtde parcelas a vencer
    "total_debt":             "eca89462dc3083e721c3ae1f3fe8ff59d05c950b",  # Total da dívida
    "future_value":           "4c59ca4ea36cdf0d786cdf5dbaf55803241ab432",  # Valor a vencer
    "overdue_value_plain":    "04595b98f37c393d084afc861f547874e741a1b5",  # Soma vencidas s/ juros
    # "overdue_value_interest": "58a42c02721f74c122a4c4bb959d2d1403c5613e",  # Soma vencidas c/ juros

    # ─── Operações internas ──────────────────────────────
    "processing_date":        "246fb3d2ad2655a764181818155cc20b511b8cc4",  # Data de Processamento
    "cleaned_flag":           "1a7fcd19468cf0876c1632d1e5eec0e795f6a8aa",  # Higienizado (enum 46/47)
}

# -------------------------------
# Assertiva SMS
# -------------------------------
ASSERTIVA_BASE_URL   = config('ASSERTIVA_BASE_URL')
ASSERTIVA_AUTH_TOKEN = config('ASSERTIVA_AUTH_TOKEN')

# -------------------------------
# Mailchimp / SendGrid
# -------------------------------
SENDGRID_API_KEY   = config('SENDGRID_API_KEY')
BREVO_API_KEY = config('BREVO_API_KEY')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL')

# -------------------------------
# DebtApp WhatsApp
# -------------------------------
DEBTAPP_WHATSAPP_ENDPOINT = config('DEBTAPP_WHATSAPP_ENDPOINT')
DEBTAPP_WHATSAPP_API_KEY  = config('DEBTAPP_WHATSAPP_API_KEY')

# -------------------------------
# Crypto & Hash
# -------------------------------
ENCRYPTION_KEY = config('ENCRYPTION_KEY')
HASH_SECRET    = config('HASH_SECRET')

# -------------------------------
# JWT
# -------------------------------
JWT_SECRET    = config('JWT_SECRET')
JWT_ALGORITHM = config('JWT_ALGORITHM')
JWT_EXPIRES_IN = config('JWT_EXPIRES_IN')
REGISTRATION_KEY = config('REGISTRATION_KEY')

# -------------------------------
# Channels / Redis
# -------------------------------
REDIS_URL = config('REDIS_URL')
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    },
}

# -------------------------------
# Pipeboard
# -------------------------------
PIPEBOARD_DSN = "postgresql+asyncpg://pipedrive_metabase_integration_db:3qnC5kRwaGwYcBx6MOw2NOirm9ytXBH8I4aKE3xXPtAzPvgrfPwqgkq5pMidmZF@172.18.0.1:15432/pipedrive_metabase_integration_db"

# -------------------------------
# Apps, Middleware, URLs
# -------------------------------
INSTALLED_APPS = [
    'corsheaders',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.postgres',
    'rest_framework',
    'drf_yasg',
    'django_prometheus',
    'channels',
    'django_extensions',
    'django_celery_beat',
    'cobranca_inteligente_api.apps.BillingConfig',
    'plugins.django_interface.apps.DjangoInterfaceConfig',
]

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'plugins.django_interface.request_middleware.RequestContextMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]

ROOT_URLCONF = 'cobranca_inteligente_api.urls'
WSGI_APPLICATION = 'cobranca_inteligente_api.wsgi.application'
ASGI_APPLICATION = 'cobranca_inteligente_api.asgi.application'

# -------------------------------
# Templates
# -------------------------------
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# -------------------------------
# REST Framework
# -------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "oralsin_core.adapters.security.jwt_authentication.JWTAuthentication",
        "oralsin_core.adapters.security.jwt_authentication.CookieJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}
SWAGGER_SETTINGS = {
    'SECURITY_DEFINITIONS': {
        'Bearer': {
            'type': 'apiKey', 'name': 'Authorization', 'in': 'header'
        }
    },
}

# -------------------------------
# Banco de Dados
# -------------------------------
DATABASES = {
    'default': {
        'ENGINE':   'django.db.backends.postgresql',
        'NAME':     config('DB_NAME'),
        'USER':     config('DB_USER'),
        'PASSWORD': config('DB_PASS'),
        'HOST':     config('DB_HOST'),
        'PORT':     config('DB_PORT'),
    }
}

# -------------------------------
# Internacionalização
# -------------------------------
LANGUAGE_CODE = 'pt-br'
TIME_ZONE     = 'America/Sao_Paulo'
USE_I18N      = True
USE_L10N      = True
USE_TZ        = True

# -------------------------------
# Arquivos estáticos
# -------------------------------
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
