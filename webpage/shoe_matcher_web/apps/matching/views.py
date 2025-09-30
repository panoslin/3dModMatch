"""
匹配功能视图
"""

import logging
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import MatchingTask
from .serializers import (
    MatchingTaskSerializer, 
    MatchingTaskListSerializer,
    StartMatchingSerializer,
    MatchingStatusSerializer,
    MatchingResultSerializer
)

logger = logging.getLogger(__name__)


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
        
        # 在summary中添加处理时间
        summary = task.summary_data.copy()
        summary['processing_time'] = task.processing_time
        
        # 获取鞋模信息
        shoe_model_name = task.shoe_model.name if task.shoe_model else '未知鞋模'
        
        # 构建参数信息
        parameters = {
            'clearance': task.clearance,
            'threshold': task.threshold,
            'auto_scale': task.enable_scaling,
            'multi_orientation': task.enable_multi_start,
            'max_results': 10  # 默认值
        }
        
        return Response({
            'success': True,
            'data': {
                'task_id': task.task_id,
                'status': task.status,
                'created_at': task.created_at.isoformat() if task.created_at else None,
                'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                'shoe_model_name': shoe_model_name,
                'clearance': task.clearance,
                'threshold': task.threshold,
                'parameters': parameters,
                'results': task.result_data.get('results', []),
                'summary': summary
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
    serializer_class = MatchingTaskListSerializer  # 使用列表序列化器
    
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


@api_view(['GET'])
def heatmap_status_api(request, task_id):
    """获取热力图生成状态"""
    try:
        task = get_object_or_404(MatchingTask, task_id=task_id)
        
        return Response({
            'success': True,
            'data': {
                'task_id': task.task_id,
                'heatmap_status': task.heatmap_status,
                'heatmap_data': task.heatmap_data
            }
        })
    except Exception as e:
        logger.error(f"获取热力图状态失败: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== 双模型热力图API端点 ==================== #

@api_view(['GET'])
def get_alignment_data_api(request, task_id, result_index):
    """获取cppcore对齐数据"""
    try:
        task = get_object_or_404(MatchingTask, task_id=task_id)
        
        if task.status != 'completed':
            return Response({
                'success': False,
                'error': 'task_not_completed',
                'message': '任务尚未完成'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 获取结果数据
        results = task.result_data.get('results', [])
        if int(result_index) >= len(results):
            return Response({
                'success': False,
                'error': 'result_index_invalid',
                'message': f'结果索引 {result_index} 超出范围'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        result = results[int(result_index)]
        
        # 获取候选模型 ID（如果结果中没有，尝试通过名称查询）
        candidate_id = result.get('blank_id')
        candidate_name = result.get('blank_name', 'Unknown')
        
        if not candidate_id and candidate_name != 'Unknown':
            # 尝试通过文件名查询 BlankModel
            from apps.blanks.models import BlankModel
            try:
                # 移除路径前缀，只保留文件名
                filename = candidate_name.split('/')[-1]
                blank = BlankModel.objects.filter(file__icontains=filename).first()
                if blank:
                    candidate_id = blank.id
                    logger.info(f"通过文件名查找到 blank ID: {candidate_id}")
                else:
                    logger.warning(f"未找到匹配的 blank 模型: {filename}")
            except Exception as e:
                logger.error(f"查询 blank 模型失败: {e}")
        
        # 构建对齐数据
        alignment_data = {
            'target_id': task.shoe_model.id,
            'target_type': 'shoe',
            'candidate_id': candidate_id,
            'candidate_type': 'blank',
            'candidate_name': candidate_name,
            'transform_matrix': result.get('transform', []),  # 4x4矩阵
            'mirrored': result.get('mirrored', False),
            'chamfer_distance': result.get('chamfer', 0),
            'scale_used': result.get('scale_used', 1.0),
            'coordinate_system': {
                'units': 'mm',
                'right_handed': True,
                'y_up': True
            },
            'alignment_quality': _calculate_alignment_quality(result),
            'timestamp': task.completed_at.isoformat() if task.completed_at else None
        }
        
        # 保存对齐数据到缓存
        task.save_alignment_data(int(result_index), alignment_data)
        
        return Response({
            'success': True,
            'data': alignment_data
        })
        
    except Exception as e:
        logger.error(f"获取对齐数据失败 {task_id}/{result_index}: {e}")
        return Response({
            'success': False,
            'error': 'alignment_data_failed',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET']) 
def get_clearance_data_api(request, task_id, result_index):
    """获取轻量级间隙数据"""
    try:
        task = get_object_or_404(MatchingTask, task_id=task_id)
        
        if task.status != 'completed':
            return Response({
                'success': False,
                'error': 'task_not_completed',
                'message': '任务尚未完成'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 获取结果数据
        results = task.result_data.get('results', [])
        if int(result_index) >= len(results):
            return Response({
                'success': False,
                'error': 'result_index_invalid', 
                'message': f'结果索引 {result_index} 超出范围'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        result = results[int(result_index)]
        
        # 检查缓存
        cached_data = task.get_clearance_cache(int(result_index))
        if cached_data and cached_data.get('cached_at'):
            logger.info(f"使用缓存的间隙数据: {task_id}/{result_index}")
            return Response({
                'success': True,
                'data': cached_data,
                'from_cache': True
            })
        
        # 执行轻量级间隙计算
        try:
            from utils.lightweight_clearance import calculate_clearance_lightweight, extract_alignment_metadata
            
            # 获取文件路径
            target_path = task.shoe_model.file.path
            blank_path = _get_blank_file_path(result)
            
            if not blank_path:
                return Response({
                    'success': False,
                    'error': 'blank_file_not_found',
                    'message': '找不到粗胚文件'
                }, status=status.HTTP_404_NOT_FOUND)
            
            logger.info(f"间隙计算: target={target_path}, blank={blank_path}")
            
            # 提取变换数据
            transform_matrix = result.get('transform')
            scale_factor = result.get('scale_used', 1.0)
            
            logger.info(f"变换参数: matrix={type(transform_matrix)}, scale={scale_factor}")
            
            # 计算间隙
            clearance_data = calculate_clearance_lightweight(
                target_path=target_path,
                blank_path=blank_path,
                transform_matrix=transform_matrix,
                scale_factor=scale_factor
            )
            
            # 构建响应数据
            response_data = {
                'clearances': clearance_data['clearances'].tolist(),  # 转换为JSON可序列化
                'sample_indices': clearance_data.get('sample_indices', []).tolist() if hasattr(clearance_data.get('sample_indices', []), 'tolist') else [],
                'min_clearance': clearance_data['min_clearance'],
                'max_clearance': clearance_data['max_clearance'],
                'mean_clearance': clearance_data['mean_clearance'],
                'p15_clearance': clearance_data['p15_clearance'],
                'inside_ratio': clearance_data['inside_ratio'],
                'vertex_count': clearance_data['vertex_count'],
                'total_vertices': clearance_data.get('total_vertices', clearance_data['vertex_count']),
                'computation_time': clearance_data['computation_time'],
                'method': clearance_data.get('method', 'unknown'),
                'coordinate_system': clearance_data['coordinate_system']
            }
            
            # 保存统计信息到缓存（不包含原始数组）
            task.save_clearance_cache(int(result_index), clearance_data)
            
            return Response({
                'success': True,
                'data': response_data,
                'from_cache': False
            })
            
        except ImportError as e:
            logger.error(f"轻量级间隙计算模块导入失败: {e}")
            
            # 在开发/测试模式下提供模拟数据
            if request.GET.get('mock') == 'true':
                logger.info("使用模拟间隙数据进行测试")
                mock_data = _generate_mock_clearance_data()
                return Response({
                    'success': True,
                    'data': mock_data,
                    'from_cache': False,
                    'mock': True
                })
            
            return Response({
                'success': False,
                'error': 'calculation_module_unavailable',
                'message': '间隙计算模块不可用，可以添加 ?mock=true 参数查看模拟数据'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        except Exception as e:
            logger.error(f"间隙计算失败 {task_id}/{result_index}: {e}")
            return Response({
                'success': False,
                'error': 'clearance_calculation_failed',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Exception as e:
        logger.error(f"获取间隙数据失败 {task_id}/{result_index}: {e}")
        return Response({
            'success': False,
            'error': 'clearance_data_failed',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def dual_heatmap_status_api(request, task_id):
    """获取双模型热力图状态"""
    try:
        task = get_object_or_404(MatchingTask, task_id=task_id)
        
        return Response({
            'success': True,
            'data': {
                'task_id': task.task_id,
                'dual_heatmap_status': task.dual_heatmap_status,
                'dual_heatmap_data': task.dual_heatmap_data,
                'alignment_data_available': bool(task.alignment_data),
                'clearance_cache_available': bool(task.clearance_cache)
            }
        })
        
    except Exception as e:
        logger.error(f"获取双模型热力图状态失败: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== 工具函数 ==================== #

def _calculate_alignment_quality(result_data: dict) -> str:
    """计算对齐质量评级"""
    chamfer = result_data.get('chamfer', float('inf'))
    inside_ratio = result_data.get('inside_ratio', 0)
    
    if chamfer < 1.0 and inside_ratio > 0.95:
        return 'excellent'
    elif chamfer < 2.0 and inside_ratio > 0.90:
        return 'good'  
    elif chamfer < 5.0 and inside_ratio > 0.80:
        return 'fair'
    else:
        return 'poor'


def _get_blank_file_path(result_data: dict) -> str:
    """获取粗胚文件路径"""
    import os
    from pathlib import Path
    from django.conf import settings
    
    # 尝试多种路径映射
    blank_path = result_data.get('blank_path') or result_data.get('path')
    blank_name = result_data.get('blank_name', 'unknown')
    
    logger.info(f"查找粗胚文件: path={blank_path}, name={blank_name}")
    
    if not blank_path:
        logger.warning("结果数据中没有粗胚路径信息")
        return None
    
    # 如果是容器路径，转换为实际路径
    if '/app/candidates/' in str(blank_path):
        file_name = Path(blank_path).name
        possible_paths = [
            Path(settings.MEDIA_ROOT) / 'blanks' / file_name,
            Path(settings.MEDIA_ROOT) / 'blanks' / '2025' / '01' / file_name,
            Path(settings.MEDIA_ROOT) / 'blanks' / '2025' / '09' / file_name,
            Path('/root/3dModMatch/candidates') / file_name,
        ]
        
        logger.info(f"容器路径转换，尝试查找: {file_name}")
        for p in possible_paths:
            logger.debug(f"检查路径: {p}")
            if p.exists():
                logger.info(f"找到文件: {p}")
                return str(p)
        
        logger.warning(f"未找到文件，尝试的路径: {[str(p) for p in possible_paths]}")
    
    elif Path(blank_path).exists():
        logger.info(f"直接路径存在: {blank_path}")
        return str(blank_path)
    
    else:
        logger.warning(f"直接路径不存在: {blank_path}")
    
    # 最后尝试基于文件名搜索
    if blank_name and blank_name != 'unknown':
        search_dirs = [
            Path(settings.MEDIA_ROOT) / 'blanks',
            Path('/root/3dModMatch/candidates'),
        ]
        
        for search_dir in search_dirs:
            if search_dir.exists():
                for ext in ['.3dm', '.ply', '.obj', '.stl']:
                    potential_file = search_dir / f"{blank_name.split('.')[0]}{ext}"
                    logger.debug(f"尝试搜索: {potential_file}")
                    if potential_file.exists():
                        logger.info(f"基于名称找到文件: {potential_file}")
                        return str(potential_file)
    
    logger.error("无法找到粗胚文件")
    return None

