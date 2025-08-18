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
    
    # 核心应用（主工作台）
    path('', include('apps.core.urls')),
    path('core/', include('apps.core.urls')),  # 兼容/core/路径
    
    # API根路径（DRF）
    path('api-auth/', include('rest_framework.urls')),
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
