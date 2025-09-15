"""
鞋模管理URL配置
"""

from django.urls import path
from . import views

app_name = 'shoes'

urlpatterns = [
    path('upload/', views.ShoeUploadAPIView.as_view(), name='shoe_upload'),
    path('', views.ShoeListAPIView.as_view(), name='shoe_list'),
    path('<int:pk>/', views.ShoeDetailAPIView.as_view(), name='shoe_detail'),
    path('<int:shoe_id>/preview/', views.shoe_preview_api, name='shoe_preview'),
]