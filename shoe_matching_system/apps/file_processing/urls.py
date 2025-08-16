"""
文件处理应用URL配置
"""

from django.urls import path
from . import views

app_name = 'file_processing'

urlpatterns = [
    # 文件解析API
    path('parse/', views.ParseFileView.as_view(), name='parse_file'),
    path('batch-parse/', views.BatchParseView.as_view(), name='batch_parse'),
    
    # 任务状态查询
    path('task/<str:task_id>/', views.TaskStatusView.as_view(), name='task_status'),
]
