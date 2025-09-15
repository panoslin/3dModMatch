"""
3D可视化视图
"""

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.cache import cache
import hashlib
import os
import sys
from pathlib import Path

# 添加enhanced_3dm_renderer路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent.parent / 'hybrid'))


@api_view(['GET'])
def preview_3d_api(request, model_id):
    """生成3D预览API"""
    try:
        model_type = request.query_params.get('type', 'shoe')  # 'shoe' or 'blank'
        format_type = request.query_params.get('format', 'html')  # 'html' or 'json'
        
        if model_type == 'shoe':
            from apps.shoes.models import ShoeModel
            model = get_object_or_404(ShoeModel, id=model_id)
        elif model_type == 'blank':
            from apps.blanks.models import BlankModel
            model = get_object_or_404(BlankModel, id=model_id)
        else:
            return Response({
                'success': False,
                'error': 'invalid_type',
                'message': '无效的模型类型'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 检查文件是否存在
        if not model.file or not os.path.exists(model.file.path):
            return Response({
                'success': False,
                'error': 'file_not_found',
                'message': '模型文件不存在'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # 检查缓存
        cache_key = f"preview_{model_type}_{model_id}_{format_type}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return Response({
                'success': True,
                'data': cached_result,
                'cached': True
            })
        
        # 生成预览
        try:
            from utils.enhanced_3dm_renderer import Enhanced3DRenderer
            
            renderer = Enhanced3DRenderer()
            data = renderer.read_3dm(model.file.path)
            
            if not data.success:
                return Response({
                    'success': False,
                    'error': 'render_failed',
                    'message': '3DM文件解析失败'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 生成图形
            fig = renderer.create_figure(data)
            if not fig:
                return Response({
                    'success': False,
                    'error': 'figure_failed',
                    'message': '图形生成失败'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # 根据格式返回数据
            if format_type == 'html':
                html_content = fig.to_html(
                    include_plotlyjs='cdn',
                    div_id=f'{model_type}_preview_{model_id}'
                )
                
                result_data = {
                    'html': html_content,
                    'metadata': {
                        'name': model.name,
                        'volume': data.stats.get('volume', 0),
                        'vertex_count': data.stats.get('vertex_count', 0),
                        'face_count': data.stats.get('face_count', 0),
                        'bounds': data.stats.get('bounds', {}),
                        'size': data.stats.get('size', [0, 0, 0])
                    }
                }
            else:
                # JSON格式返回原始数据
                result_data = {
                    'vertices': data.vertices.tolist() if data.vertices.size > 0 else [],
                    'faces': data.faces,
                    'metadata': data.stats
                }
            
            # 缓存结果 (1小时)
            cache.set(cache_key, result_data, 3600)
            
            return Response({
                'success': True,
                'data': result_data,
                'cached': False
            })
            
        except ImportError:
            return Response({
                'success': False,
                'error': 'renderer_unavailable',
                'message': '3D渲染器不可用'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
    except Exception as e:
        return Response({
            'success': False,
            'error': 'preview_error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def heatmap_api(request, task_id, result_index):
    """获取匹配热图API"""
    try:
        from apps.matching.models import MatchingTask
        task = get_object_or_404(MatchingTask, task_id=task_id)
        
        if task.status != 'completed':
            return Response({
                'success': False,
                'error': 'task_not_completed',
                'message': '任务尚未完成'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 检查结果索引
        results = task.result_data.get('results', [])
        if result_index >= len(results):
            return Response({
                'success': False,
                'error': 'invalid_index',
                'message': '无效的结果索引'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 检查热图文件
        if not task.heatmap_dir:
            return Response({
                'success': False,
                'error': 'heatmap_not_found',
                'message': '热图文件不存在'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # 查找对应的热图文件
        heatmap_dir = Path(task.heatmap_dir)
        result = results[result_index]
        blank_name = Path(result['blank_path']).stem
        
        # 可能的热图文件名格式
        possible_names = [
            f"{result_index+1:02d}_{blank_name}_heatmap.html",
            f"{blank_name}_heatmap.html",
            f"heatmap_{result_index}.html"
        ]
        
        heatmap_file = None
        for name in possible_names:
            potential_file = heatmap_dir / name
            if potential_file.exists():
                heatmap_file = potential_file
                break
        
        if not heatmap_file:
            return Response({
                'success': False,
                'error': 'heatmap_file_not_found',
                'message': '热图文件未找到'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # 读取热图HTML
        with open(heatmap_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        return Response({
            'success': True,
            'data': {
                'html': html_content,
                'result_info': result,
                'file_path': str(heatmap_file)
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': 'heatmap_error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
