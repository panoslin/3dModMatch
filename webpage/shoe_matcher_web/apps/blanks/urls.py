"""
粗胚管理URL配置
"""

from django.urls import path
from . import views

app_name = 'blanks'

urlpatterns = [
    path('', views.BlankListCreateAPIView.as_view(), name='blank_list_create'),
    path('<int:pk>/', views.BlankDetailAPIView.as_view(), name='blank_detail'),
    path('categories/', views.CategoryListCreateAPIView.as_view(), name='category_list_create'),
]


