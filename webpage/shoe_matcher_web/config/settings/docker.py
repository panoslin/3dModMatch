"""
Docker环境配置
"""

from .base import *

# Debug settings for Docker testing
DEBUG = True

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'shoe_matcher'),
        'USER': os.environ.get('DB_USER', 'postgres'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'postgres123'),
        'HOST': os.environ.get('DB_HOST', 'db'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'CONN_MAX_AGE': 60,
    }
}

# Cache configuration
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://redis:6379/0'),
        'KEY_PREFIX': 'shoe_matcher',
        'TIMEOUT': 300,
    }
}

# Allow all hosts in Docker
ALLOWED_HOSTS = ['*']

# Email backend for development
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Additional development apps
INSTALLED_APPS = INSTALLED_APPS + [
    'django_extensions',
]

# Docker环境日志配置
LOGGING['handlers']['console']['level'] = 'INFO'
LOGGING['loggers']['apps']['level'] = 'INFO'

# 确保logs目录存在
import os
os.makedirs('/app/logs', exist_ok=True)
