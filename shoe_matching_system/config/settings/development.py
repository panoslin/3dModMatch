"""
开发环境设置
"""

from .base import *

# 调试模式
DEBUG = True
ALLOWED_HOSTS = ['*']

# 开发工具
INSTALLED_APPS += [
    'django_extensions',
    'debug_toolbar',
]

MIDDLEWARE += [
    'debug_toolbar.middleware.DebugToolbarMiddleware',
]

# Debug Toolbar设置
INTERNAL_IPS = [
    '127.0.0.1',
    'localhost',
]

# 数据库设置（开发环境可以使用SQLite简化开发）
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# 邮件后端设置（开发环境）
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# 日志级别调整
LOGGING['root']['level'] = 'DEBUG'
LOGGING['loggers']['apps']['level'] = 'DEBUG'

# 静态文件服务（开发环境）
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

# 安全设置（开发环境宽松）
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

print("🚀 Django开发环境已启动")
