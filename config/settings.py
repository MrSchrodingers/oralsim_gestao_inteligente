from pathlib import Path

from decouple import Csv, config

# -------------------------------
# Diretórios base
# -------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# -------------------------------
# Segurança e debug
# -------------------------------
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
CSRF_TRUSTED_ORIGINS  = config('CSRF_TRUSTED_ORIGINS', default='', cast=Csv())
CORS_ALLOWED_ORIGINS   = config('CORS_ALLOWED_ORIGINS',   default='', cast=Csv())
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
    "email":      {"exchange": "email",      "routing_key": "email"},
    "sms":        {"exchange": "sms",        "routing_key": "sms"},
    "whatsapp":   {"exchange": "whatsapp",   "routing_key": "whatsapp"},
    "payment":    {"exchange": "payment",    "routing_key": "payment"},
    "metrics":    {"exchange": "metrics",    "routing_key": "metrics"},
    "sync_notify":{"exchange": "sync_notify","routing_key": "sync_notify"},
    "sync_process":{"exchange":"sync_process","routing_key":"sync_process"},
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
# Assertiva SMS
# -------------------------------
ASSERTIVA_BASE_URL   = config('ASSERTIVA_BASE_URL')
ASSERTIVA_AUTH_TOKEN = config('ASSERTIVA_AUTH_TOKEN')
ASSERTIVA_WEBHOOK    = config('ASSERTIVA_WEBHOOK_URL')

# -------------------------------
# Mailchimp / SendGrid
# -------------------------------
SENDGRID_API_KEY   = config('SENDGRID_API_KEY')
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
