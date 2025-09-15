"""
3D鞋模智能匹配系统 URL配置
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.core.urls')),
    path('api/blanks/', include('apps.blanks.urls')),
    path('api/shoes/', include('apps.shoes.urls')),
    path('api/matching/', include('apps.matching.urls')),
    path('api/visualization/', include('apps.visualization.urls')),
]

# 开发环境静态文件服务
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
