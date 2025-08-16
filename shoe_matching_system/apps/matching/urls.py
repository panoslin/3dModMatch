"""
匹配算法应用URL配置
"""

from django.urls import path
from . import views

app_name = 'matching'

urlpatterns = [
    # 核心匹配API
    path('analyze/', views.AnalyzeMatchView.as_view(), name='analyze_match'),
    path('optimize/', views.OptimizeMatchView.as_view(), name='optimize_match'),
    
    # 匹配历史和统计
    path('history/', views.MatchHistoryView.as_view(), name='match_history'),
    path('statistics/', views.MatchStatisticsView.as_view(), name='match_statistics'),
]
