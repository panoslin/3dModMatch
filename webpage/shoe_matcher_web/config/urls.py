"""
3D鞋模智能匹配系统 URL配置
"""
import os
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Favicon路由
    path('favicon.ico', RedirectView.as_view(url='/static/favicon.ico', permanent=True)),
    
    # API路由 - 必须在其他应用之前
    path('api/', include('apps.api.urls')),
    
    # 其他应用路由
    path('api/blanks/', include('apps.blanks.urls')),
    path('api/shoes/', include('apps.shoes.urls')),
    path('api/matching/', include('apps.matching.urls')),
    path('api/visualization/', include('apps.visualization.urls')),
    
    # 核心应用 - 放在最后（包含通配符模式）
    path('', include('apps.core.urls')),
]

# 静态文件服务（Docker环境中总是启用）
if settings.DEBUG or os.environ.get('DJANGO_ENVIRONMENT') == 'docker':
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
