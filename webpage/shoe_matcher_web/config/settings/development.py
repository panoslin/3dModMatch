"""
开发环境配置
"""

from .base import *

# Debug settings
DEBUG = True

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Email backend for development
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Additional development apps
INSTALLED_APPS = INSTALLED_APPS + [
    'django_extensions',
]

# Development middleware
MIDDLEWARE = MIDDLEWARE + [
    # 'django.middleware.debug.DebugMiddleware',  # 这个中间件不存在，注释掉
]

# Disable security middleware in development
SECURE_SSL_REDIRECT = False
SECURE_BROWSER_XSS_FILTER = False
SECURE_CONTENT_TYPE_NOSNIFF = False

# Allow all hosts in development
ALLOWED_HOSTS = ['*']

# Development logging
LOGGING['handlers']['console']['level'] = 'DEBUG'
LOGGING['loggers']['apps']['level'] = 'DEBUG'
