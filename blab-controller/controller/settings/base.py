"""Settings for all environments."""

# DO NOT EDIT THIS FILE TO CHANGE LOCAL SETTINGS.
# OVERRIDE ANY VALUES ON dev.py OR prod.py INSTEAD
# (use dev_TEMPLATE.py or prod_TEMPLATE.py as a starting point).


import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
from typing import Any

import structlog

BASE_DIR = Path(__file__).resolve().parent.parent.parent
# BASE_DIR is the directory that contains manage.py

DEBUG = False

ALLOWED_HOSTS: list[str] = []

SECRET_KEY = os.getenv("SECRET_KEY") or ""

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "channels",
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
    "drf_spectacular_sidecar",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_structlog.middlewares.RequestMiddleware",
]

ROOT_URLCONF = "controller.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "controller.wsgi.application"

# Password validation
# https://docs.djangoproject.com/en/4.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation"
        ".UserAttributeSimilarityValidator",
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
# https://docs.djangoproject.com/en/4.0/topics/i18n/

LANGUAGES = (
    ("en", "English"),
    ("pt-BR", "Brazilian Portuguese"),
)

LANGUAGE_CODE = "en"

TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.0/howto/static-files/

STATIC_URL = "/blabcontrollerstatic/"
STATIC_ROOT = BASE_DIR / ".static"

ASGI_APPLICATION = "controller.routing.application"

# Media files (uploaded by users)
MEDIA_URL = "/media/"

# Default primary key field type
# https://docs.djangoproject.com/en/4.0/ref/settings/#default-auto-field

# Channels
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CHANNEL_LAYERS: dict[str, dict[str, Any]] = {}

# Pagination
REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 100,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# Logging

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json_formatter": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.processors.JSONRenderer(),
        },
        "plain_console": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.dev.ConsoleRenderer(sort_keys=False),
        },
        "key_value": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.processors.KeyValueRenderer(
                key_order=[
                    "timestamp",
                    "filename",
                    "lineno",
                    "func_name",
                    "level",
                    "event",
                    "logger",
                ]
            ),
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "plain_console",
        },
        "json_file": {
            "class": "logging.handlers.WatchedFileHandler",
            "filename": str(BASE_DIR / ".logs" / "django_json.log"),
            "formatter": "json_formatter",
        },
        "flat_line_file": {
            "class": "logging.handlers.WatchedFileHandler",
            "filename": str(BASE_DIR / ".logs" / "django_flat.log"),
            "formatter": "key_value",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["flat_line_file", "json_file"],
            "level": "INFO",
            "propagate": True,
        },
        "django_structlog": {
            "handlers": ["flat_line_file", "json_file"],
            "level": "INFO",
        },
        "blab_controller": {
            "handlers": ["console", "flat_line_file", "json_file"],
            "level": "INFO",
        },
    },
}

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.CallsiteParameterAdder(
            [
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            ],
        ),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    context_class=structlog.threadlocal.wrap_dict(dict),
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Celery

CHAT_ENABLE_QUEUE = True
_celery_port = 6379
CELERY_BROKER_URL = f"redis://localhost:{_celery_port}"
CELERY_RESULT_BACKEND = f"redis://localhost:{_celery_port}"
CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"


def internal_bot(
    *,
    package: str,
    class_name: str,
    args: list[Any] | None = None,
    kwargs: dict[str, Any] | None = None,
) -> tuple[str, str, list[Any], dict[str, Any]]:
    """Return a tuple with the given arguments.

    This is a convenience method.

    Args:
    ----
        package: the package that contains the bot class
        class_name: the bot class that extends Bot (bots.py)
        args: positional arguments to be passed to the bot's constructor
            after conversation_info
        kwargs: keyword arguments to be passed to the bot's constructor

    Returns:
    -------
        a tuple: (package, class_name, args, kwargs)
    """
    return package, class_name, args or [], kwargs or {}


def websocket_external_bot(*, url: str) -> tuple[str, str, list[Any], dict[str, Any]]:
    """Return a tuple with information to run a WebSocketExternalBot.

    Args:
    ----
        url: a full HTTP/HTTPS address (with protocol, hostname, optional port and path,
            e.g. "https://www.example.com:8080/path") at which the external bot will
            be listening to POST requests

    Returns:
    -------
        a tuple (package, class_name, args, kwargs)
    """
    return "chat.bots", "WebSocketExternalBot", [url], {}


# Chat limits


CHAT_LIMITS = {
    "MAX_ATTACHMENT_SIZE": 0,
    "MAX_IMAGE_SIZE": 0,
    "MAX_VIDEO_SIZE": 0,
    "MAX_AUDIO_SIZE": 0,
    "MAX_VOICE_SIZE": 0,
}

# API docs

SPECTACULAR_SETTINGS = {
    "TITLE": "BLAB Controller API",
    "DESCRIPTION": (
        "REST API to access BLAB chat. "
        "It is used by clients such as user browsers and answerer bots."
    ),
    "SERVE_INCLUDE_SCHEMA": False,
    "AUTHENTICATION_WHITELIST": [],
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.hooks.postprocess_schema_enums",
    ],
    "SWAGGER_UI_SETTINGS": """{
        "deepLinking": true,
        "displayOperationId": true,
        "defaultModelsExpandDepth": 9999,
        "defaultModelExpandDepth": 9999,
        "docExpansion": "full",
        "onComplete": () => {  // expand models
            const selector = '#swagger-ui section.models .model-toggle.collapsed';
            const expand = () => document.querySelectorAll(selector).forEach(
                b => b.click()
            );
            setTimeout(expand, 100);
            setTimeout(expand, 500);
        },
    }""",
    "REDOC_UI_SETTINGS": {
        "schemaExpansionLevel": 9,
        "jsonSampleExpandLevel": 9,
        "expandSingleSchemaField": True,
    },
}
