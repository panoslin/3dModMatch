"""
核心应用URL配置
"""

from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # 基础页面
    path('', views.HomeView.as_view(), name='home'),
    path('upload/', views.FileUploadView.as_view(), name='upload'),
    path('files/', views.FileListView.as_view(), name='file_list'),
    
    # 匹配功能
    path('matching/', views.MatchingView.as_view(), name='matching'),
    path('matching/results/<str:task_id>/', views.MatchingResultsView.as_view(), name='matching_results'),
    
    # 3D预览功能
    path('files/<int:pk>/preview/', views.FilePreviewView.as_view(), name='file_preview'),
    path('files/<int:pk>/3d/', views.File3DView.as_view(), name='file_3d'),
    path('3d-comparison/', views.Model3DComparisonView.as_view(), name='3d_comparison'),
    
    # API端点
    path('api/upload/', views.FileUploadAPIView.as_view(), name='api_upload'),
    path('api/files/', views.FileListAPIView.as_view(), name='api_files'),
]
