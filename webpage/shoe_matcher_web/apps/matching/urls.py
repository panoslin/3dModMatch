"""
匹配功能URL配置
"""

from django.urls import path
from . import views

app_name = 'matching'

urlpatterns = [
    path('start/', views.StartMatchingAPIView.as_view(), name='start_matching'),
    path('<str:task_id>/status/', views.matching_status_api, name='matching_status'),
    path('<str:task_id>/result/', views.matching_result_api, name='matching_result'),
    path('history/', views.MatchingHistoryAPIView.as_view(), name='matching_history'),
]