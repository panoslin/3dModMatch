"""
匹配功能视图
"""

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import MatchingTask
from .serializers import (
    MatchingTaskSerializer, 
    StartMatchingSerializer,
    MatchingStatusSerializer,
    MatchingResultSerializer
)


class StartMatchingAPIView(generics.CreateAPIView):
    """开始匹配API"""
    serializer_class = StartMatchingSerializer
    
    def create(self, request, *args, **kwargs):
        """开始新的匹配任务"""
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            # 创建匹配任务
            from apps.shoes.models import ShoeModel
            from apps.blanks.models import BlankCategory
            
            shoe_model = ShoeModel.objects.get(
                id=serializer.validated_data['shoe_model_id']
            )
            categories = BlankCategory.objects.filter(
                id__in=serializer.validated_data['category_ids']
            )
            
            task = MatchingTask.objects.create(
                shoe_model=shoe_model,
                clearance=serializer.validated_data['clearance'],
                threshold=serializer.validated_data['threshold'],
                enable_scaling=serializer.validated_data['enable_scaling'],
                enable_multi_start=serializer.validated_data['enable_multi_start'],
                max_scale=serializer.validated_data['max_scale'],
                started_at=timezone.now()
            )
            task.selected_categories.set(categories)
            
            # 启动异步匹配任务
            from .tasks import run_matching_task
            run_matching_task.delay(task.id)
            
            return Response({
                'success': True,
                'data': {
                    'task_id': task.task_id,
                    'status': task.status,
                    'estimated_time': 120  # 预估2分钟
                },
                'message': '匹配任务已启动'
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': 'start_failed',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def matching_status_api(request, task_id):
    """获取匹配任务状态"""
    try:
        task = get_object_or_404(MatchingTask, task_id=task_id)
        
        # 计算预估剩余时间
        estimated_remaining = None
        if task.status == 'processing' and task.started_at:
            elapsed = (timezone.now() - task.started_at).total_seconds()
            if task.progress > 0:
                total_estimated = elapsed * 100 / task.progress
                estimated_remaining = max(0, int(total_estimated - elapsed))
        
        return Response({
            'success': True,
            'data': {
                'task_id': task.task_id,
                'status': task.status,
                'progress': task.progress,
                'current_step': task.current_step,
                'estimated_remaining': estimated_remaining
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': 'status_failed',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def matching_result_api(request, task_id):
    """获取匹配结果"""
    try:
        task = get_object_or_404(MatchingTask, task_id=task_id)
        
        if task.status != 'completed':
            return Response({
                'success': False,
                'error': 'task_not_completed',
                'message': '任务尚未完成'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'success': True,
            'data': {
                'task_id': task.task_id,
                'status': task.status,
                'results': task.result_data.get('results', []),
                'summary': task.summary_data
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': 'result_failed',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MatchingHistoryAPIView(generics.ListAPIView):
    """匹配历史API"""
    queryset = MatchingTask.objects.all()
    serializer_class = MatchingTaskSerializer
    
    def list(self, request, *args, **kwargs):
        """获取匹配历史列表"""
        queryset = self.get_queryset()
        
        # 过滤参数
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # 日期范围过滤
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                'success': True,
                'data': serializer.data
            })
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'data': serializer.data
        })
