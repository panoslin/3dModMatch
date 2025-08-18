"""
核心应用URL配置 - 简化版
"""

from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # 主工作台
    path('', views.DashboardView.as_view(), name='dashboard'),
    
    # 文件上传 (Ajax)
    path('upload/', views.FileUploadView.as_view(), name='upload'),
    
    # 匹配功能 (Ajax)
    path('quick-match/', views.QuickMatchView.as_view(), name='quick_match'),
    path('batch-process/', views.BatchProcessView.as_view(), name='batch_process'),
    path('matching/<int:matching_id>/detail/', views.MatchingDetailView.as_view(), name='matching_detail'),
    
    # 导出功能
    path('export/<int:matching_id>/', views.ExportResultView.as_view(), name='export_result'),
]