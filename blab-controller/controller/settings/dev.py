"""Settings for development environment."""
from .base import *

DEBUG = True

INSTALLED_APPS += [
    'chat.apps.ChatConfig',
]

SECRET_KEY = (
    SECRET_KEY
    or 'django-insecure-ait%p*y_nubshw2pc&svhllvjpxeyss@e+i$tk+u9z70@-zy)(')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [('127.0.0.1', 6379)],
        },
    }
}

CORS_ORIGIN_WHITELIST = [
    'http://localhost:3000',
]
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:3000',
]

INSTALLED_BOTS = {
    'ECHO': ('chat.bots', 'UpperCaseEchoBot', []),
    'Calculator': ('chat.bots', 'CalculatorBot', []),
}
