"""
3D鞋模智能匹配系统的WSGI配置

它作为WSGI可调用对象向Web服务器公开，用于部署。
"""

import os
from django.core.wsgi import get_wsgi_application

# 设置默认的Django设置模块
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')

application = get_wsgi_application()
