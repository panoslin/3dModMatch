"""
3D可视化URL配置
"""

from django.urls import path
from . import views

app_name = 'visualization'

urlpatterns = [
    path('preview/<int:model_id>/', views.preview_3d_api, name='preview_3d'),
    path('heatmap/<str:task_id>/<int:result_index>/', views.heatmap_api, name='heatmap'),
]