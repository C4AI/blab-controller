"""Template for settings used in a production environment.

Create a copy of this file and name it "prod.py".

Fill in the missing values.
A short description is given below each field.

Documentation:
https://docs.djangoproject.com/en/3.2/ref/settings/
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *

##########################################################################

INSTALLED_APPS += [
    'chat.apps.ChatConfig',
]
"""Additional installed apps."""

##########################################################################

INSTALLED_BOTS = {
    'ECHO': ('chat.bots', 'UpperCaseEchoBot', []),
    'Calculator': ('chat.bots', 'CalculatorBot', []),
}
"""Installed bots.

Each key is the bot name, and the value is a 3-tuple
(module, class, additional constructor arguments).
"""

##########################################################################

# Note: 2**20 bytes = 1 MB

# Setting any of the following values to 0 disables that type of file.

CHAT_LIMITS = {
    'MAX_ATTACHMENT_SIZE': 15 * 2**20,
    # maximum size of an attachment (in bytes)
    'MAX_IMAGE_SIZE': 15 * 2**20,
    # maximum size of an image (in bytes)
    'MAX_VIDEO_SIZE': 15 * 2**20,
    # maximum size of an image (in bytes)
    'MAX_AUDIO_SIZE': 15 * 2**20,
    # maximum size of an audio file (in bytes)
    'MAX_VOICE_SIZE': 15 * 2**20,
    # maximum size of any voice recording file (in bytes)
}

CHAT_LIMITS = {k: 0 for k in CHAT_LIMITS}
# Disabling message attachments for now, because we haven't implemented
# file sending yet

##########################################################################

MEDIA_ROOT = BASE_DIR / '.media'
"""Path where files uploaded by users will be saved."""

##########################################################################

ALLOWED_HOSTS = [
    'localhost',  # local connections should be allowed
    # 'example.com',       # domain
    # 'www.example.com',   # subdomain
    # '.example.com',      # all subdomains
]
"""A list of strings representing the host/domain names
that this Django site can serve."""

##########################################################################

_db_engine = ''
"""Database engine.

Should be one of:
    - MySQL
    - Oracle
    - PostgreSQL
    - SQLite3
"""

##########################################################################

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.' + _db_engine.lower(),
        'NAME': '',
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': '',
    }
}
"""Database settings.

Documentation:
https://docs.djangoproject.com/en/4.0/ref/databases/
"""

##########################################################################

CORS_ALLOWED_ORIGINS: list[str] = [
    # 'https://example.com',     # domain
    # 'https://www.example.com', # subdomain
]
"""A list of origins that are authorized to make cross-site HTTP requests.

To use regular expressions, replace it with `CORS_ALLOWED_ORIGIN_REGEXES`.

Documentation: https://github.com/adamchainz/django-cors-headers
"""

##########################################################################

CSRF_TRUSTED_ORIGINS: list[str] = [
    # 'https://example.com',     # domain
    # 'https://www.example.com', # subdomain
    # 'https://*.example.com',   # all subdomains
]
"""A list of trusted origins for unsafe requests (e.g. POST)."""

##########################################################################

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [('127.0.0.1', 6379)],
        },
    }
}
"""
Settings for Django Channels.

Documentation:
https://github.com/django/channels_redis
"""

##########################################################################

_ssl = True
"""Whether SSL should be required.

It should be set to False in temporary servers that cannot be accessed
via HTTPS.
"""

##########################################################################

SECURE_HSTS_SECONDS = 3600
"""
Number of seconds after which the browser should only use HTTPS.

For example: if set to 604800, then any browser that visits the page over HTTPS
will refuse to connect to the website via HTTP, which makes the website
unavailable for previous users if an HTTPS connection is no longer possible
(e.g. expired SSL certificate).

Documentation:
https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Strict-Transport-Security

"""

##########################################################################
# IT IS NOT NECESSARY TO EDIT THE CONTENTS BELOW
##########################################################################

DEBUG = False

CORS_ALLOW_CREDENTIALS = True

if _ssl:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True

if not SECRET_KEY:
    raise ImproperlyConfigured('Environment variable SECRET_KEY not set or empty')
