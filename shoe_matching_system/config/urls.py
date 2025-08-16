"""
3D鞋模智能匹配系统 URL配置
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    # 管理后台
    path('admin/', admin.site.urls),
    
    # 核心应用
    path('', include('apps.core.urls')),
    
    # 文件处理API
    path('api/files/', include('apps.file_processing.urls')),
    
    # 匹配算法API  
    path('api/matching/', include('apps.matching.urls')),
    
    # API根路径
    path('api/', include('rest_framework.urls')),
    
    # 根路径重定向到首页
    path('', RedirectView.as_view(url='/', permanent=False)),
]

# 静态文件和媒体文件服务
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# 开发环境下的调试工具
if settings.DEBUG:
    # Debug Toolbar (开发环境)
    if 'debug_toolbar' in settings.INSTALLED_APPS:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns

# 管理后台标题设置
admin.site.site_header = "3D鞋模智能匹配系统"
admin.site.site_title = "鞋模匹配管理"
admin.site.index_title = "系统管理"
