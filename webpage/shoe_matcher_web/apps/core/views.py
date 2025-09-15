"""
核心视图
"""

from django.shortcuts import render
from django.views.generic import TemplateView
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


class MatchingPageView(TemplateView):
    """主页/匹配页面视图"""
    template_name = 'core/matching.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = '3D鞋模智能匹配系统'
        return context


class HistoryPageView(TemplateView):
    """历史记录页面视图"""
    template_name = 'core/history.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = '匹配历史记录'
        return context


class HealthCheckAPIView(APIView):
    """系统健康检查API"""
    
    def get(self, request):
        """获取系统健康状态"""
        try:
            # 检查数据库连接
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            
            health_data = {
                'status': 'healthy',
                'database': 'connected',
                'timestamp': timezone.now().isoformat(),
            }
            
            return Response({
                'success': True,
                'data': health_data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': 'health_check_failed',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
