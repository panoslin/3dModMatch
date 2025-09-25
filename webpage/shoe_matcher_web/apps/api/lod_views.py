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


# ========================== LOD数据API ========================== #
# 第一个get_lod_data_api函数已删除，使用下方完整实现


@api_view(['GET'])
@permission_classes([AllowAny])
def get_lod_status_api(request, model_type: str, model_id: int):
    """
    获取模型的LOD处理状态
    
    Returns:
        LOD处理状态和可用信息
    """
    try:
        # 获取模型
        model, ModelClass, SerializerClass = get_model_and_class(model_type, model_id)
        
        # 获取处理状态
        if LOD_TASKS_AVAILABLE:
            processing_status = get_lod_processing_status(model_id, model_type)
        else:
            processing_status = {'status': 'unavailable', 'message': 'LOD处理服务不可用'}
        
        return Response({
            'success': True,
            'data': {
                'model_id': model_id,
                'model_type': model_type,
                'model_name': model.name,
                'processing_status': processing_status,
                'optimization_status': model.optimization_status,
                'lod_files': model.lod_files,
                'available_levels': model.available_lod_levels,
                'preferred_engine': model.preferred_render_engine,
                'file_info': {
                    'original_size_mb': model.file_size_mb,
                    'compression_ratio': model.compression_ratio,
                    'supports_webgl': model.supports_webgl
                }
            }
        })
        
    except (ShoeModel.DoesNotExist, BlankModel.DoesNotExist):
        return Response({
            'success': False,
            'error': 'model_not_found',
            'message': f'{model_type} #{model_id} 不存在'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"获取LOD状态失败: {model_type} #{model_id}: {e}")
        return Response({
            'success': False,
            'error': 'server_error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ========================== LOD管理API ========================== #

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def trigger_lod_processing_api(request, model_type: str, model_id: int):
    """
    手动触发LOD处理
    
    Body参数：
    - force_regenerate: 是否强制重新生成（默认false）
    - lod_levels: 要生成的LOD级别列表（可选）
    
    Returns:
        任务状态信息
    """
    if not LOD_TASKS_AVAILABLE:
        return Response({
            'success': False,
            'error': 'service_unavailable',
            'message': 'LOD处理服务不可用'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    
    try:
        # 验证模型存在
        model, ModelClass, SerializerClass = get_model_and_class(model_type, model_id)
        
        # 获取参数
        force_regenerate = request.data.get('force_regenerate', False)
        
        # 检查权限（可以添加更细粒度的权限控制）
        if not request.user.is_staff and hasattr(model, 'uploaded_by') and model.uploaded_by != request.user:
            return Response({
                'success': False,
                'error': 'permission_denied',
                'message': '无权限处理此模型'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # 启动异步任务
        task = process_model_lod.delay(model_id, model_type, force_regenerate)
        
        return Response({
            'success': True,
            'data': {
                'task_id': task.id,
                'model_id': model_id,
                'model_type': model_type,
                'force_regenerate': force_regenerate,
                'message': 'LOD处理任务已启动',
                'status_url': f'/api/lod/{model_type}/{model_id}/status/'
            }
        }, status=status.HTTP_202_ACCEPTED)
        
    except (ShoeModel.DoesNotExist, BlankModel.DoesNotExist):
        return Response({
            'success': False,
            'error': 'model_not_found',
            'message': f'{model_type} #{model_id} 不存在'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"触发LOD处理失败: {model_type} #{model_id}: {e}")
        return Response({
            'success': False,
            'error': 'server_error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
            if model_type == 'shoe':
                from apps.shoes.tasks import process_shoe_lod
                task = process_shoe_lod.delay(model_id, force_regenerate)
            else:
                # 创建类似的blank任务或直接调用
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
    """
    try:
        # 获取模型对象
        if model_type == 'shoe':
            from apps.shoes.models import ShoeModel
            try:
                model = ShoeModel.objects.get(id=model_id)
            except ShoeModel.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'model_not_found'
                }, status=status.HTTP_404_NOT_FOUND)
        elif model_type == 'blank':
            from apps.blanks.models import BlankModel
            try:
                model = BlankModel.objects.get(id=model_id)
            except BlankModel.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'model_not_found'
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({
                'success': False,
                'error': 'invalid_model_type'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 构建状态信息
        status_data = {
            'model_id': model_id,
            'model_type': model_type,
            'model_name': model.name,
            'has_glb_files': bool(getattr(model, 'geometry_simplified', False)),
            'lod_levels': getattr(model, 'lod_files', {}).keys() if hasattr(model, 'lod_files') else [],
            'webgl_ready': bool(getattr(model, 'supports_webgl', False)),
            'optimization_status': {
                'geometry_simplified': bool(getattr(model, 'geometry_simplified', False)),
                'compression_ratio': getattr(model, 'compression_ratio', None),
                'supports_webgl': bool(getattr(model, 'supports_webgl', False)),
                'render_engine': getattr(model, 'render_engine', 'plotly')
            }
        }
        
        return Response({
            'success': True,
            'data': status_data
        })
        
    except Exception as e:
        logger.error(f"获取LOD状态失败 {model_type}/{model_id}: {e}")
        return Response({
            'success': False,
            'error': 'status_failed',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_lod_data_api(request, model_type: str, model_id: int):
    """
    获取指定模型的LOD数据文件
    """
    lod_level = request.GET.get('lod', 'preview')
    file_format = request.GET.get('format', 'glb')
    
    # 添加详细日志
    logger.info(f"GLB数据API调用: model_type={model_type}, model_id={model_id}, lod_level={lod_level}, file_format={file_format}")
    logger.info(f"请求查询参数: {dict(request.GET)}")
    
    if file_format != 'glb':
        logger.warning(f"不支持的文件格式: {file_format}")
        return Response({
            'success': False,
            'error': 'unsupported_format',
            'message': f'不支持的文件格式: {file_format}'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        logger.info(f"开始处理GLB数据请求")
        
        # 获取模型对象
        if model_type == 'shoe':
            from apps.shoes.models import ShoeModel
            try:
                model = ShoeModel.objects.get(id=model_id)
                logger.info(f"成功获取鞋模: {model.name}")
            except ShoeModel.DoesNotExist:
                logger.error(f"鞋模不存在: {model_id}")
                return Response({
                    'success': False,
                    'error': 'model_not_found'
                }, status=status.HTTP_404_NOT_FOUND)
        elif model_type == 'blank':
            from apps.blanks.models import BlankModel
            try:
                model = BlankModel.objects.get(id=model_id)
                logger.info(f"成功获取粗胚: {model.name}")
            except BlankModel.DoesNotExist:
                logger.error(f"粗胚不存在: {model_id}")
                return Response({
                    'success': False,
                    'error': 'model_not_found'
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            logger.error(f"无效的模型类型: {model_type}")
            return Response({
                'success': False,
                'error': 'invalid_model_type'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 检查是否有LOD文件
        logger.info(f"检查LOD文件: hasattr={hasattr(model, 'lod_files')}, lod_files={getattr(model, 'lod_files', None)}")
        if not hasattr(model, 'lod_files') or not model.lod_files:
            logger.error("模型没有LOD文件")
            return Response({
                'success': False,
                'error': 'no_lod_files',
                'message': 'GLB文件未找到，请先触发LOD处理'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # 检查指定LOD级别
        logger.info(f"检查LOD级别: 请求={lod_level}, 可用={list(model.lod_files.keys())}")
        if lod_level not in model.lod_files:
            available_levels = list(model.lod_files.keys())
            logger.error(f"LOD级别不存在: {lod_level}")
            return Response({
                'success': False,
                'error': 'lod_level_not_found',
                'message': f'LOD级别 {lod_level} 未找到，可用级别: {available_levels}'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # 获取文件路径
        relative_path = model.lod_files[lod_level]
        file_path = os.path.join(settings.MEDIA_ROOT, relative_path)
        logger.info(f"文件路径: {file_path}")
        
        # 检查文件是否存在
        file_exists = os.path.exists(file_path)
        logger.info(f"文件存在性检查: {file_exists}")
        if not file_exists:
            logger.error(f"GLB文件不存在: {relative_path}")
            return Response({
                'success': False,
                'error': 'file_not_found',
                'message': f'GLB文件不存在: {relative_path}'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # 返回文件响应
        logger.info("创建FileResponse")
        from django.http import FileResponse
        response = FileResponse(
            open(file_path, 'rb'),
            content_type='model/gltf-binary'
        )
        response['Content-Disposition'] = f'inline; filename="{model_type}_{model_id}_{lod_level}.glb"'
        logger.info(f"返回GLB文件响应，状态码: {response.status_code}")
        return response
        
    except Exception as e:
        logger.error(f"获取GLB数据失败 {model_type}/{model_id}: {e}")
        return Response({
            'success': False,
            'error': 'data_retrieval_failed',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
