"""
核心应用URL配置
"""

from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.MatchingPageView.as_view(), name='matching'),
    path('history/', views.HistoryPageView.as_view(), name='history'),
    path('api/health/', views.HealthCheckAPIView.as_view(), name='health_check'),
]


