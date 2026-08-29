"""Módulo de Configurações Centrais do Projeto FreeCash.

Este arquivo carrega dinamicamente as variáveis de ambiente usando `dotenv` do
diretório raiz ou do backend, configura o driver PostgreSQL (`psycopg`), habilita
cabeçalhos CORS para integração com o frontend React em localhost ou produção,
e define as políticas de segurança e tokens JWT com expiração rotativa.

Configurações Principais:
    BASE_DIR: Resolvido dinamicamente para a pasta raiz do backend (/app no Docker).
    DATABASES: Conexão PostgreSQL com healthcheck no docker-compose.
    SIMPLE_JWT: Autenticação stateless segura com rotação de chaves.
    CORS_ALLOWED_ORIGINS: Permissões de cross-origin baseadas na porta do frontend.
"""


from pathlib import Path
from decouple import Csv, config
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# Valor sentinela: aceito apenas em desenvolvimento. Ver `validar_config_producao()`.
SECRET_KEY_INSEGURA = "django-insecure-CHANGE-ME-local-dev-only"

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config("DJANGO_SECRET_KEY", default=SECRET_KEY_INSEGURA)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config("DJANGO_DEBUG", default=False, cast=bool)

ALLOWED_HOSTS = config(
    "DJANGO_ALLOWED_HOSTS",
    default="localhost,127.0.0.1,0.0.0.0",
    cast=Csv(),
)


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "corsheaders",
    "rest_framework",
    # Necessário para que BLACKLIST_AFTER_ROTATION e o logout revoguem de fato o
    # refresh token. Sem este app, a blacklist do SimpleJWT é silenciosamente inerte.
    "rest_framework_simplejwt.token_blacklist",
    "widget_tweaks",
    "core",
    "investimento",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "freecash.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "core" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "freecash.wsgi.application"


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME", default=""),
        "USER": config("DB_USER", default=""),
        "PASSWORD": config("DB_PASS", default=""),
        "HOST": config("DB_HOST", default=""),
        "PORT": config("DB_PORT", default=""),
    }
}


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = "pt-br"

TIME_ZONE = "America/Sao_Paulo"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "core" / "static",
]

# O WhiteNoiseMiddleware já está na pilha, mas sozinho ele apenas serve os
# arquivos de STATIC_ROOT. O storage abaixo é o que faz o resto do trabalho:
# gera versões comprimidas (.gz/.br) no collectstatic e renomeia cada arquivo com
# um hash do conteúdo, registrado num manifesto. Isso permite servir os estáticos
# com cache longo sem risco de o navegador segurar uma versão velha — quando o
# conteúdo muda, o nome muda.
#
# Em desenvolvimento o Django usa o finder e ignora o STATIC_ROOT, então o
# manifesto não interfere no auto-reload.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_REDIRECT_URL = "/dashboard/"
LOGIN_URL = "/"

# Autenticação
# O backend customizado aceita e-mail ou nome de usuário como identificador de
# login. O ModelBackend padrão segue na lista para não quebrar nada que dependa
# dele (o admin do Django, por exemplo) — e é redundante, não conflitante: ambos
# recusam credenciais inválidas da mesma forma.
AUTHENTICATION_BACKENDS = [
    "core.auth_backends.EmailOuUsernameBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# CORS Configuration
# Em produção, defina DJANGO_CORS_ALLOWED_ORIGINS com as origens reais do frontend.
# O fallback abaixo reproduz o comportamento histórico de desenvolvimento.
frontend_port = config("FRONTEND_PORT", default="5173")
CORS_ALLOWED_ORIGINS = config(
    "DJANGO_CORS_ALLOWED_ORIGINS",
    default=f"http://localhost:{frontend_port},http://127.0.0.1:{frontend_port}",
    cast=Csv(),
)
CORS_ALLOW_CREDENTIALS = True

# URL base do SPA. Usada para montar os links enviados por e-mail (verificação de
# conta e redefinição de senha), que apontam para o frontend e não para a API.
FRONTEND_BASE_URL = config(
    "FRONTEND_BASE_URL",
    default=f"http://localhost:{frontend_port}",
).rstrip("/")

# Cache
# O alias "throttle" é dedicado ao rate limiting de autenticação. LocMemCache não
# serve: é por processo, então com N workers do gunicorn o limite efetivo viraria N×
# e zeraria a cada reload. DatabaseCache é compartilhado entre workers e não exige
# infraestrutura nova — mas depende de `manage.py createcachetable` no deploy.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "freecash-default",
    },
    "throttle": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "cache_throttle",
    },
}

# Configuração do cookie HttpOnly que transporta o refresh token.
# O path cobre /api/token/, /api/token/refresh/ e /api/token/clear/ por prefixo —
# necessário para que o logout receba o cookie e consiga revogar o token — e continua
# não expondo o refresh token às rotas de dados.
AUTH_COOKIE_NAME = "refresh_token"
AUTH_COOKIE_PATH = "/api/token/"
AUTH_COOKIE_SECURE = config("DJANGO_AUTH_COOKIE_SECURE", default=not DEBUG, cast=bool)
# Use "None" (com AUTH_COOKIE_SECURE=True) se o frontend for servido de outro domínio.
AUTH_COOKIE_SAMESITE = config("DJANGO_AUTH_COOKIE_SAMESITE", default="Lax")

# E-mail
# Usa o backend SMTP padrão do Django em vez de um SDK de provedor: Resend, Brevo,
# SES e Postmark todos oferecem SMTP, então trocar de fornecedor é mudança de
# variável de ambiente, não de código. Também mantém `mail.outbox` funcionando nos
# testes, sem precisar interceptar chamadas HTTP.
# Entregabilidade (SPF, DKIM, DMARC) se resolve no DNS do domínio, não aqui.
EMAIL_BACKEND = config(
    "DJANGO_EMAIL_BACKEND",
    default=(
        "django.core.mail.backends.console.EmailBackend"
        if DEBUG
        else "django.core.mail.backends.smtp.EmailBackend"
    ),
)
EMAIL_HOST = config("EMAIL_HOST", default="")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_TIMEOUT = config("EMAIL_TIMEOUT", default=10, cast=int)
DEFAULT_FROM_EMAIL = config(
    "DEFAULT_FROM_EMAIL",
    default="FreeCash <nao-responda@localhost>",
)

# Envio em thread separada. O projeto não tem Celery nem Redis — a doutrina vigente,
# documentada em core/services/recorrencia_service.py, é materializar trabalho no
# próprio request. E-mail transacional é o caso mais tolerante a isso: o volume é
# ínfimo e cada fluxo já oferece "reenviar" como recuperação de falha.
# Desligue nos testes para que o envio seja síncrono e `mail.outbox` seja confiável.
EMAIL_ASYNC = config("DJANGO_EMAIL_ASYNC", default=True, cast=bool)

# Validade dos links enviados por e-mail, em segundos.
# PASSWORD_RESET_TIMEOUT é setting do próprio Django e governa o token de
# redefinição de senha; o de verificação de conta usa a janela mais longa abaixo,
# porque confirmar a conta é menos urgente que recuperar o acesso.
PASSWORD_RESET_TIMEOUT = config(
    "DJANGO_PASSWORD_RESET_TIMEOUT",
    default=60 * 60 * 3,
    cast=int,
)
EMAIL_VERIFICATION_TIMEOUT = config(
    "DJANGO_EMAIL_VERIFICATION_TIMEOUT",
    default=60 * 60 * 24 * 3,
    cast=int,
)

# Carência, em dias, antes de exigir e-mail verificado nas ações amplificadoras
# (importação e exportação em massa). O CRUD financeiro nunca é bloqueado: impedir
# o dono de registrar seus próprios lançamentos não protege ninguém.
EMAIL_VERIFICATION_GRACE_DAYS = config(
    "DJANGO_EMAIL_VERIFICATION_GRACE_DAYS",
    default=7,
    cast=int,
)

# REST Framework & JWT Configuration
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "core.pagination.PadraoPageNumberPagination",
    "PAGE_SIZE": 100,
    # Intencionalmente vazio: o throttle é opt-in nas views de autenticação, para não
    # estrangular o aplicativo inteiro.
    "DEFAULT_THROTTLE_CLASSES": (),
    "DEFAULT_THROTTLE_RATES": {
        "register": "10/hour",
        "login": "10/min",
        "senha_reset": "5/hour",
        "senha_reset_email": "3/hour",
        "senha_reset_confirm": "10/hour",
        "email_verify": "10/hour",
        "email_verify_resend": "3/hour",
    },
    "EXCEPTION_HANDLER": "core.exception_handler.freecash_exception_handler",
}

from datetime import timedelta
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
}


# Segurança de transporte e cookies
# Aplicadas somente fora de DEBUG: em desenvolvimento não há HTTPS e um
# SECURE_SSL_REDIRECT ativo tornaria o servidor local inacessível.
if not DEBUG:
    SECURE_SSL_REDIRECT = config("DJANGO_SECURE_SSL_REDIRECT", default=True, cast=bool)
    # Obrigatório atrás de proxy reverso (nginx, Cloudflare, load balancer). Sem isto,
    # o Django não reconhece a requisição como HTTPS e o redirect entra em laço infinito.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = config("DJANGO_SECURE_HSTS_SECONDS", default=31536000, cast=int)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = config("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True, cast=bool)
    SECURE_HSTS_PRELOAD = config("DJANGO_SECURE_HSTS_PRELOAD", default=True, cast=bool)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
CSRF_TRUSTED_ORIGINS = config(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    default="",
    cast=Csv(),
)


# Logging
# Um único handler de console: em contêiner, stdout é o destino correto — quem
# agrega (Docker, systemd, plataforma de deploy) cuida da persistência.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "padrao": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "padrao",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        # Onde caem as falhas de envio de e-mail e as exceções tratadas das views.
        "core": {
            "handlers": ["console"],
            "level": config("DJANGO_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        "investimento": {
            "handlers": ["console"],
            "level": config("DJANGO_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
    },
}


def validar_config_producao() -> None:
    """Falha no boot quando uma configuração obrigatória de produção está ausente.

    Sem esta checagem, `DB_NAME` ausente resulta em `None` silencioso e a
    `SECRET_KEY` sentinela de desenvolvimento seria usada para assinar os tokens
    JWT de produção — os dois casos degradam sem qualquer sinal visível.

    Raises:
        ImproperlyConfigured: Se alguma variável obrigatória faltar ou mantiver o
            valor de exemplo enquanto DEBUG está desligado.
    """
    if DEBUG:
        return

    problemas = []

    if SECRET_KEY == SECRET_KEY_INSEGURA:
        problemas.append("DJANGO_SECRET_KEY ainda é o valor de exemplo")

    for chave in ("DB_NAME", "DB_USER", "DB_PASS", "DB_HOST"):
        if not config(chave, default=""):
            problemas.append(f"{chave} não está definida")

    if not ALLOWED_HOSTS:
        problemas.append("DJANGO_ALLOWED_HOSTS está vazia")

    if problemas:
        raise ImproperlyConfigured(
            "Configuração de produção incompleta (DEBUG=False): "
            + "; ".join(problemas)
        )


validar_config_producao()
