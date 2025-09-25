"""
API URL配置
包括LOD系统的所有API端点

URL模式：
- /api/lod/ - LOD系统相关接口
- /api/three/ - Three.js预览页面
- /api/health/ - 系统健康检查
- /api/stats/ - 统计信息

作者：AI Assistant
创建时间：2024-09-25
版本：v1.0
"""

from django.urls import path, include
from . import lod_views, three_views

app_name = 'api'

# LOD系统URL模式
lod_urlpatterns = [
    # 获取LOD数据
    path(
        '<str:model_type>/<int:model_id>/data/',
        lod_views.get_lod_data_api,
        name='lod_data'
    ),
    
    # 获取LOD状态
    path(
        '<str:model_type>/<int:model_id>/status/',
        lod_views.get_lod_status_api,
        name='lod_status'
    ),
    
    # 触发LOD处理
    path(
        '<str:model_type>/<int:model_id>/process/',
        lod_views.trigger_lod_processing_api,
        name='trigger_lod'
    ),
    
    # 批量处理LOD
    path(
        'batch/process/',
        lod_views.batch_trigger_lod_api,
        name='batch_lod'
    ),
    
    # 切换渲染引擎
    path(
        '<str:model_type>/<int:model_id>/engine/',
        lod_views.switch_render_engine_api,
        name='switch_engine'
    ),
    
    # 系统健康检查
    path(
        'health/',
        lod_views.lod_system_health_api,
        name='lod_health'
    ),
    
    # 系统统计
    path(
        'stats/',
        lod_views.lod_system_stats_api,
        name='lod_stats'
    ),
]

# Three.js预览页面URL模式  
three_urlpatterns = [
    # 完整预览页面
    path(
        '<str:model_type>/<int:model_id>/',
        three_views.three_viewer_page,
        name='three_viewer'
    ),
    
    # 嵌入式预览（用于iframe）
    path(
        '<str:model_type>/<int:model_id>/embed/',
        three_views.three_viewer_embed,
        name='three_viewer_embed'
    ),
    
    # 兼容性检查页面
    path(
        'compatibility/',
        three_views.three_viewer_compatibility_check,
        name='three_compatibility'
    ),
]

urlpatterns = [
    # LOD系统API
    path('lod/', include(lod_urlpatterns)),
    
    # Three.js预览页面
    path('three/', include(three_urlpatterns)),
    
    # 向后兼容的健康检查端点
    path('health/', lod_views.lod_system_stats_api, name='health'),
]
