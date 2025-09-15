"""
Django settings for shoe_matcher_web project.

根据环境变量DJANGO_SETTINGS_MODULE选择配置文件
"""

import os

# 获取环境变量，默认为开发环境
ENVIRONMENT = os.environ.get('DJANGO_ENVIRONMENT', 'development')

if ENVIRONMENT == 'production':
    from .settings.production import *
elif ENVIRONMENT == 'development':
    from .settings.development import *
elif ENVIRONMENT == 'docker':
    from .settings.docker import *
else:
    from .settings.base import *
