"""
生产环境设置
"""

from .base import *

# 安全设置
DEBUG = False
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=lambda v: [s.strip() for s in v.split(',')])

# 数据库设置已在base.py中配置

# 静态文件设置
STATIC_ROOT = '/app/staticfiles'
MEDIA_ROOT = '/app/media'

# 安全设置
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = False  # 由Nginx处理SSL
USE_TZ = True

# 会话安全
SESSION_COOKIE_SECURE = False  # 如果使用HTTPS则设为True
CSRF_COOKIE_SECURE = False     # 如果使用HTTPS则设为True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

# 日志设置（生产环境）
LOGGING['handlers']['file']['filename'] = '/app/logs/django.log'

# 创建日志目录
import os
os.makedirs('/app/logs', exist_ok=True)

# 邮件设置（生产环境）
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')

# 管理员邮箱
ADMINS = [
    ('Admin', config('ADMIN_EMAIL', default='admin@example.com')),
]

print("🔒 Django生产环境已启动")
