"""
API应用配置
"""

from django.apps import AppConfig


class ApiConfig(AppConfig):
    """API应用配置类"""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.api'
    verbose_name = 'API系统'
    
    def ready(self):
        """应用准备就绪时的初始化"""
        print(f"✅ {self.verbose_name} 应用已加载")



