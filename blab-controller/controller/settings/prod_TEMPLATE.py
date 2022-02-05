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

ALLOWED_HOSTS = [
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

_ssl = True

##########################################################################
# IT IS NOT NECESSARY TO EDIT THE REMAINING CONTENTS OF THIS FILE
##########################################################################

DEBUG = False

if _ssl:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True

if not SECRET_KEY:
    raise ImproperlyConfigured(
        'Environment variable SECRET_KEY not set or empty')
