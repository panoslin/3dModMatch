#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LOD系统API视图
支持多精度模型数据获取和Three.js渲染

功能特性：
1. 获取指定LOD级别的模型文件
2. 返回Three.js兼容的GLB数据
3. LOD处理状态查询和控制
4. 渲染引擎切换管理
5. 系统健康状态检查

作者：AI Assistant
创建时间：2024-09-25  
版本：v1.0
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.http import FileResponse, Http404, HttpResponseNotModified
from django.core.cache import cache
from django.conf import settings
from django.utils.http import http_date
from django.views.decorators.http import condition
from django.views.decorators.cache import cache_control
from django.utils.decorators import method_decorator

# 导入模型
from apps.shoes.models import ShoeModel
from apps.blanks.models import BlankModel
from apps.shoes.serializers import ShoeModelSerializer
from apps.blanks.serializers import BlankModelSerializer

# 导入LOD处理工具
try:
    from utils.lod_processing_tasks import (
        process_model_lod, 
        get_lod_processing_status,
        check_lod_system_health
    )
    LOD_TASKS_AVAILABLE = True
except ImportError:
    LOD_TASKS_AVAILABLE = False

logger = logging.getLogger(__name__)


# ========================== 工具函数 ========================== #

def get_model_and_class(model_type: str, model_id: int):
    """获取模型对象和类"""
    if model_type == 'shoe':
        return ShoeModel.objects.get(id=model_id), ShoeModel, ShoeModelSerializer
    elif model_type == 'blank':
        return BlankModel.objects.get(id=model_id), BlankModel, BlankModelSerializer
    else:
        raise ValueError(f"不支持的模型类型: {model_type}")


def get_glb_file_path(model, lod_level: str) -> Optional[str]:
    """获取GLB文件的绝对路径"""
    if not model.lod_files or lod_level not in model.lod_files:
        return None
    
    relative_path = model.lod_files[lod_level]
    absolute_path = os.path.join(settings.MEDIA_ROOT, relative_path)
    
    if os.path.exists(absolute_path):
        return absolute_path
    return None


def get_file_etag(file_path: str) -> str:
    """生成文件的ETag"""
    import hashlib
    stat = os.stat(file_path)
    return hashlib.md5(f"{file_path}:{stat.st_mtime}:{stat.st_size}".encode()).hexdigest()



# ========================== LOD管理API ========================== #

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def batch_trigger_lod_api(request):
    """
    批量触发LOD处理
    
    Body参数：
    - models: 模型列表 [{'type': 'shoe', 'id': 1}, ...]
    - force_regenerate: 是否强制重新生成
    
    Returns:
        批量任务状态
    """
    if not LOD_TASKS_AVAILABLE:
        return Response({
            'success': False,
            'error': 'service_unavailable',
            'message': 'LOD处理服务不可用'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    
    try:
        models_data = request.data.get('models', [])
        force_regenerate = request.data.get('force_regenerate', False)
        
        if not models_data:
            return Response({
                'success': False,
                'error': 'no_models',
                'message': '未指定要处理的模型'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 限制批量处理数量
        if len(models_data) > 50:
            return Response({
                'success': False,
                'error': 'too_many_models',
                'message': '单次最多可处理50个模型'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        results = []
        for model_data in models_data:
            model_type = model_data.get('type')
            model_id = model_data.get('id')
            
            if not model_type or not model_id:
                results.append({
                    'model_data': model_data,
                    'success': False,
                    'error': 'invalid_model_data'
                })
                continue
            
            try:
                # 验证模型存在
                model, ModelClass, SerializerClass = get_model_and_class(model_type, model_id)
                
                # 启动任务
                task = process_model_lod.delay(model_id, model_type, force_regenerate)
                
                results.append({
                    'model_id': model_id,
                    'model_type': model_type,
                    'model_name': model.name,
                    'success': True,
                    'task_id': task.id
                })
                
            except Exception as e:
                results.append({
                    'model_id': model_id,
                    'model_type': model_type,
                    'success': False,
                    'error': str(e)
                })
        
        success_count = sum(1 for r in results if r.get('success', False))
        
        return Response({
            'success': True,
            'data': {
                'total': len(results),
                'success': success_count,
                'failed': len(results) - success_count,
                'results': results
            }
        }, status=status.HTTP_202_ACCEPTED)
        
    except Exception as e:
        logger.error(f"批量触发LOD处理失败: {e}")
        return Response({
            'success': False,
            'error': 'server_error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ========================== 渲染引擎切换API ========================== #

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def switch_render_engine_api(request, model_type: str, model_id: int):
    """
    切换模型的渲染引擎
    
    Body参数：
    - engine: 渲染引擎 ('plotly' 或 'threejs')
    
    Returns:
        切换结果
    """
    try:
        # 获取模型
        model, ModelClass, SerializerClass = get_model_and_class(model_type, model_id)
        
        # 获取参数
        engine = request.data.get('engine')
        
        if engine not in ['plotly', 'threejs']:
            return Response({
                'success': False,
                'error': 'invalid_engine',
                'message': '渲染引擎必须是 plotly 或 threejs'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 检查Three.js支持
        if engine == 'threejs' and not model.is_ready_for_threejs():
            return Response({
                'success': False,
                'error': 'threejs_not_ready',
                'message': '模型尚未准备好Three.js渲染',
                'optimization_status': model.optimization_status,
                'recommendations': [
                    '等待LOD处理完成',
                    '确保WebGL数据已生成'
                ]
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 更新渲染引擎
        old_engine = model.render_engine
        model.render_engine = engine
        model.save(update_fields=['render_engine'])
        
        return Response({
            'success': True,
            'data': {
                'model_id': model_id,
                'model_type': model_type,
                'old_engine': old_engine,
                'new_engine': engine,
                'optimization_status': model.optimization_status
            }
        })
        
    except (ShoeModel.DoesNotExist, BlankModel.DoesNotExist):
        return Response({
            'success': False,
            'error': 'model_not_found',
            'message': f'{model_type} #{model_id} 不存在'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"切换渲染引擎失败: {model_type} #{model_id}: {e}")
        return Response({
            'success': False,
            'error': 'server_error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ========================== 系统状态API ========================== #

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def lod_system_health_api(request):
    """
    检查LOD系统健康状态
    
    Returns:
        系统健康状态报告
    """
    try:
        if not LOD_TASKS_AVAILABLE:
            return Response({
                'success': True,
                'data': {
                    'overall_healthy': False,
                    'lod_tasks_available': False,
                    'message': 'LOD处理任务不可用'
                }
            })
        
        health_status = check_lod_system_health()
        
        return Response({
            'success': True,
            'data': health_status
        })
        
    except Exception as e:
        logger.error(f"检查LOD系统健康失败: {e}")
        return Response({
            'success': False,
            'error': 'health_check_failed',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def lod_system_stats_api(request):
    """
    获取LOD系统统计信息
    
    Returns:
        系统使用统计
    """
    try:
        # 统计各类模型的LOD状态
        shoe_stats = {
            'total': ShoeModel.objects.count(),
            'lod_ready': ShoeModel.objects.filter(geometry_simplified=True).count(),
            'webgl_ready': ShoeModel.objects.filter(supports_webgl=True).count(),
            'threejs_engine': ShoeModel.objects.filter(render_engine='threejs').count()
        }
        
        blank_stats = {
            'total': BlankModel.objects.count(),
            'lod_ready': BlankModel.objects.filter(geometry_simplified=True).count(),
            'webgl_ready': BlankModel.objects.filter(supports_webgl=True).count(),
            'threejs_engine': BlankModel.objects.filter(render_engine='threejs').count()
        }
        
        # 计算总体优化率
        total_models = shoe_stats['total'] + blank_stats['total']
        total_optimized = shoe_stats['lod_ready'] + blank_stats['lod_ready']
        optimization_rate = (total_optimized / total_models * 100) if total_models > 0 else 0
        
        return Response({
            'success': True,
            'data': {
                'overview': {
                    'total_models': total_models,
                    'optimized_models': total_optimized,
                    'optimization_rate': round(optimization_rate, 1)
                },
                'shoes': shoe_stats,
                'blanks': blank_stats,
                'lod_system': {
                    'available': LOD_TASKS_AVAILABLE,
                    'supported_levels': ['preview', 'detail', 'full'],
                    'supported_engines': ['plotly', 'threejs']
                }
            }
        })
        
    except Exception as e:
        logger.error(f"获取LOD统计失败: {e}")
        return Response({
            'success': False,
            'error': 'stats_failed',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])  # 暂时允许无认证访问
def trigger_lod_processing_api(request, model_type: str, model_id: int):
    """
    触发指定模型的LOD处理任务
    
    Args:
        model_type: 模型类型 ('shoe' 或 'blank')
        model_id: 模型ID
        
    Returns:
        JSON响应包含任务状态
    """
    try:
        # 验证模型类型
        if model_type not in ['shoe', 'blank']:
            return Response({
                'success': False,
                'error': 'invalid_model_type',
                'message': f'不支持的模型类型: {model_type}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 获取模型对象
        if model_type == 'shoe':
            from apps.shoes.models import ShoeModel
            try:
                model = ShoeModel.objects.get(id=model_id)
            except ShoeModel.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'model_not_found',
                    'message': f'未找到鞋模 ID: {model_id}'
                }, status=status.HTTP_404_NOT_FOUND)
        else:  # blank
            from apps.blanks.models import BlankModel
            try:
                model = BlankModel.objects.get(id=model_id)
            except BlankModel.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'model_not_found',
                    'message': f'未找到粗胚 ID: {model_id}'
                }, status=status.HTTP_404_NOT_FOUND)
        
        # 检查模型是否有3DM文件
        if not model.file:
            return Response({
                'success': False,
                'error': 'no_source_file',
                'message': '模型缺少源文件，无法进行LOD处理'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 触发LOD处理任务
        force_regenerate = request.data.get('force_regenerate', False)
        
        try:
            # 统一使用process_model_lod处理所有模型类型
            from utils.lod_processing_tasks import process_model_lod
            task = process_model_lod.delay(model_id, model_type, force_regenerate)
            
            return Response({
                'success': True,
                'message': 'LOD处理任务已启动',
                'data': {
                    'task_id': task.id,
                    'model_id': model_id,
                    'model_type': model_type,
                    'force_regenerate': force_regenerate,
                    'status_url': f'/api/lod/{model_type}/{model_id}/status/'
                }
            }, status=status.HTTP_202_ACCEPTED)
            
        except Exception as task_error:
            logger.error(f"启动LOD处理任务失败: {task_error}")
            return Response({
                'success': False,
                'error': 'task_start_failed',
                'message': f'无法启动LOD处理任务: {str(task_error)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Exception as e:
        logger.error(f"触发LOD处理失败 {model_type}/{model_id}: {e}")
        return Response({
            'success': False,
            'error': 'trigger_failed',
            'message': f'触发LOD处理失败: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_lod_status_api(request, model_type: str, model_id: int):
    """
    获取指定模型的LOD状态
    
    基于数据库模型字段返回完整状态信息
    """
    try:
        logger.info(f"获取LOD状态: {model_type}/{model_id}")
        
        # 获取模型对象
        model, ModelClass, SerializerClass = get_model_and_class(model_type, model_id)
        
        # 获取LOD文件信息
        lod_files = getattr(model, 'lod_files', {}) or {}
        lod_levels = list(lod_files.keys()) if lod_files else []
        
        # 检查文件系统中的实际文件
        existing_files = {}
        for level, relative_path in lod_files.items():
            file_path = os.path.join(settings.MEDIA_ROOT, relative_path)
            existing_files[level] = {
                'path': relative_path,
                'exists': os.path.exists(file_path),
                'size': os.path.getsize(file_path) if os.path.exists(file_path) else 0
            }
        
        # 构建完整的状态信息
        status_data = {
            'model_id': model_id,
            'model_type': model_type,
            'model_name': model.name,
            'has_3dm_file': bool(model.file and os.path.exists(model.file.path) if hasattr(model, 'file') else False),
            'has_glb_files': bool(lod_levels),
            'lod_levels': lod_levels,
            'lod_files': existing_files,
            'webgl_ready': bool(getattr(model, 'supports_webgl', False)) and bool(lod_levels),
            'processing_status': getattr(model, 'processing_status', 'unknown'),
            'optimization_status': {
                'geometry_simplified': bool(getattr(model, 'geometry_simplified', False)),
                'compression_ratio': getattr(model, 'compression_ratio', None),
                'supports_webgl': bool(getattr(model, 'supports_webgl', False)),
                'render_engine': getattr(model, 'render_engine', 'plotly')
            }
        }
        
        logger.info(f"LOD状态查询成功: {model_type}/{model_id}, LOD级别: {lod_levels}")
        return Response({
            'success': True,
            'data': status_data
        })
        
    except (ShoeModel.DoesNotExist, BlankModel.DoesNotExist):
        return Response({
            'success': False,
            'error': 'model_not_found',
            'message': f'{model_type} #{model_id} 不存在'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"获取LOD状态失败 {model_type}/{model_id}: {e}")
        return Response({
            'success': False,
            'error': 'status_failed',
            'message': f'状态查询失败: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def get_lod_data_api(request, model_type: str, model_id: int):
    """
    获取指定模型的LOD数据文件
    
    基于数据库模型的lod_files字段获取文件路径
    使用普通Django视图（解决DRF装饰器问题）
    """
    from django.http import JsonResponse, FileResponse
    
    try:
        logger.info(f"获取LOD数据: {model_type}/{model_id}")
        
        # 获取请求参数
        lod_level = request.GET.get('lod', 'preview')
        file_format = request.GET.get('format', 'glb')
        
        # 验证文件格式
        if file_format not in ['glb', 'metadata']:
            return JsonResponse({
                'success': False,
                'error': 'unsupported_format',
                'message': f'不支持的文件格式: {file_format}，支持的格式: glb, metadata'
            }, status=400)
        
        # 获取模型对象
        model, ModelClass, SerializerClass = get_model_and_class(model_type, model_id)
        
        # 检查模型是否有LOD文件
        if not hasattr(model, 'lod_files') or not model.lod_files:
            logger.warning(f"模型 {model_type}/{model_id} 没有LOD文件")
            return JsonResponse({
                'success': False,
                'error': 'no_lod_files',
                'message': 'LOD文件未生成，请先触发LOD处理'
            }, status=404)
        
        # 检查指定LOD级别是否存在
        if lod_level not in model.lod_files:
            available_levels = list(model.lod_files.keys())
            logger.warning(f"LOD级别 {lod_level} 不存在，可用级别: {available_levels}")
            return JsonResponse({
                'success': False,
                'error': 'lod_level_not_found',
                'message': f'LOD级别 {lod_level} 未找到，可用级别: {available_levels}'
            }, status=404)
        
        # 处理元数据请求
        if file_format == 'metadata':
            logger.info(f"返回模型元数据: {model_type}/{model_id}")
            
            # 构建元数据响应
            metadata_response = {
                'success': True,
                'data': {
                    'model': {
                        'vertex_count': model.vertex_count or 0,
                        'face_count': model.face_count or 0,
                        'file_size_mb': model.file_size_mb
                    },
                    'lod_info': {
                        'compression_ratio': model.compression_ratio or 0.0
                    }
                }
            }
            
            return JsonResponse(metadata_response)
        
        # 获取GLB文件路径（从数据库模型的lod_files字段）
        relative_path = model.lod_files[lod_level]
        file_path = os.path.join(settings.MEDIA_ROOT, relative_path)
        
        # 检查文件是否实际存在于文件系统
        if not os.path.exists(file_path):
            logger.error(f"GLB文件不存在于文件系统: {file_path}")
            return JsonResponse({
                'success': False,
                'error': 'file_not_found',
                'message': f'GLB文件不存在: {relative_path}'
            }, status=404)
        
        # 返回文件响应
        response = FileResponse(
            open(file_path, 'rb'),
            content_type='model/gltf-binary'
        )
        response['Content-Disposition'] = f'inline; filename="{model_type}_{model_id}_{lod_level}.glb"'
        
        logger.info(f"成功返回GLB文件: {model_type}/{model_id}/{lod_level}")
        return response
        
    except Exception as e:
        if 'DoesNotExist' in str(type(e)):
            return JsonResponse({
                'success': False,
                'error': 'model_not_found',
                'message': f'{model_type} #{model_id} 不存在'
            }, status=404)
        
        logger.error(f"获取LOD数据失败: {model_type}/{model_id}: {e}")
        return JsonResponse({
            'success': False,
            'error': 'server_error',
            'message': f'服务器错误: {str(e)}'
        }, status=500)


