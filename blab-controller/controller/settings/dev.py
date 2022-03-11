"""Settings for development environment."""
from .base import *

DEBUG = True

INSTALLED_APPS += [
    'chat.apps.ChatConfig',
]

INSTALLED_BOTS = {
    'ECHO': ('chat.bots', 'UpperCaseEchoBot', []),
    'Calculator': ('chat.bots', 'CalculatorBot', []),
}

CHAT_LIMITS = {
    'MAX_ATTACHMENT_SIZE': 15 * 2**20,
    # maximum size of an attachment (in bytes)
    'MAX_IMAGE_SIZE': 15 * 2**20,
    # maximum size of an image (in bytes)
    'MAX_VIDEO_SIZE': 15 * 2**20,
    # maximum size of an image (in bytes)
    'MAX_AUDIO_SIZE': 15 * 2**20,
    # maximum size of an audio file (in bytes)
    'MAX_VOICE_SIZE': 30 * 60,
    # maximum size of any voice recording file (in bytes)
    'MAX_IMAGE_RESOLUTION': 1280,
    # maximum width and height of any image (in pixels)
    # (clients may optionally downscale images before the upload)
    'MAX_VIDEO_RESOLUTION': 1280,
    # maximum width and height of any video (in pixels)
    'MAX_VIDEO_LENGTH': 10 * 60,
    # maximum length of any video (in seconds)
    'MAX_AUDIO_LENGTH': 30 * 60,
    # maximum length of any audio file (in seconds)
    'MAX_VOICE_LENGTH': 30 * 60,
    # maximum length of any voice recording file (in seconds)
}

CHAT_LIMITS = {k: 0 for k in CHAT_LIMITS}
# Disabling message attachments for now, because we haven't implemented
# file sending yet

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
