#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LOD处理异步任务
集成GLB处理器到Django Celery任务系统

功能：
1. 异步处理3DM文件生成多精度GLB
2. 更新数据库模型的LOD字段
3. 管理文件存储和清理
4. 错误处理和状态追踪

作者：AI Assistant
创建时间：2024-09-25
版本：v1.0
"""

import os
import sys
import logging
import tempfile
import gc
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from celery import shared_task
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.cache import cache

# 添加项目路径
sys.path.insert(0, os.path.join(settings.BASE_DIR.parent.parent, 'hybrid'))

# 导入GLB处理器
try:
    from .glb_processor import GLBProcessor, create_glb_processor, validate_dependencies
    GLB_AVAILABLE = True
except ImportError as e:
    GLB_AVAILABLE = False
    GLB_IMPORT_ERROR = str(e)

logger = logging.getLogger(__name__)


# ========================== 配置和常量 ========================== #

class LODConfig:
    """LOD处理配置"""
    
    # 输出目录配置
    GLB_OUTPUT_DIR = os.path.join(settings.MEDIA_ROOT, 'glb_models')
    CACHE_DIR = os.path.join(settings.MEDIA_ROOT, 'glb_cache')
    
    # LOD级别配置
    DEFAULT_LOD_LEVELS = ['preview', 'detail', 'full']
    
    # 文件大小限制 (字节)
    MAX_INPUT_SIZE = 100 * 1024 * 1024  # 100MB
    
    # 处理超时 (秒)
    PROCESSING_TIMEOUT = 1800  # 30分钟
    
    # 并发配置
    MAX_WORKERS = 4
    
    @classmethod
    def ensure_directories(cls):
        """确保必要的目录存在"""
        for dir_path in [cls.GLB_OUTPUT_DIR, cls.CACHE_DIR]:
            os.makedirs(dir_path, exist_ok=True)


# ========================== 工具函数 ========================== #

def get_model_class(model_type: str):
    """动态获取模型类"""
    if model_type == 'shoe':
        from apps.shoes.models import ShoeModel
        return ShoeModel
    elif model_type == 'blank':
        from apps.blanks.models import BlankModel
        return BlankModel
    else:
        raise ValueError(f"不支持的模型类型: {model_type}")


def get_relative_media_path(absolute_path: str) -> str:
    """获取相对于MEDIA_ROOT的路径"""
    media_root = Path(settings.MEDIA_ROOT)
    abs_path = Path(absolute_path)
    try:
        return str(abs_path.relative_to(media_root))
    except ValueError:
        # 如果路径不在MEDIA_ROOT下，返回绝对路径
        return str(abs_path)


def cleanup_temp_files(file_paths: List[str]):
    """清理临时文件"""
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"已清理临时文件: {file_path}")
        except Exception as e:
            logger.warning(f"清理临时文件失败 {file_path}: {e}")


# ========================== 主要任务 ========================== #

@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def process_model_lod(self, model_id: int, model_type: str = 'shoe', force_regenerate: bool = False):
    """
    处理模型的LOD多精度文件生成
    
    Args:
        model_id: 模型ID
        model_type: 模型类型 ('shoe' 或 'blank')
        force_regenerate: 是否强制重新生成
        
    Returns:
        dict: 处理结果
    """
    task_id = self.request.id
    logger.info(f"开始处理LOD任务 {task_id}: {model_type} #{model_id}")
    
    # 检查GLB处理器是否可用
    if not GLB_AVAILABLE:
        error_msg = f"GLB处理器不可用: {GLB_IMPORT_ERROR}"
        logger.error(error_msg)
        return {
            'success': False, 
            'error': 'glb_processor_unavailable',
            'message': error_msg
        }
    
    try:
        # 1. 获取模型对象
        ModelClass = get_model_class(model_type)
        model = ModelClass.objects.get(id=model_id)
        
        logger.info(f"处理模型: {model.name} (ID: {model_id})")
        
        # 2. 检查是否需要处理
        if not force_regenerate and model.geometry_simplified and model.lod_files:
            logger.info("模型已经处理过，跳过")
            return {
                'success': True,
                'skipped': True,
                'message': '模型已经生成LOD文件'
            }
        
        # 3. 验证输入文件
        if not model.file or not os.path.exists(model.file.path):
            raise FileNotFoundError(f"模型文件不存在: {model.file}")
        
        # 3.5. 检查文件格式并执行STL转3DM转换（如果需要）
        file_path = model.file.path
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext == '.stl':
            logger.info(f"检测到STL文件，需要转换为3DM: {file_path}")
            try:
                from utils.file_conversion_service import FileConversionService
                
                # 打开文件进行转换
                with open(file_path, 'rb') as f:
                    from django.core.files.uploadedfile import InMemoryUploadedFile
                    import io
                    
                    # 读取文件内容
                    content = f.read()
                    file_obj = InMemoryUploadedFile(
                        io.BytesIO(content),
                        None,
                        os.path.basename(file_path),
                        'application/octet-stream',
                        len(content),
                        None
                    )
                    
                    # 执行转换
                    conversion_result = FileConversionService.convert_if_needed(file_obj)
                    
                    if not conversion_result['success']:
                        raise ValueError(f"STL转换失败: {conversion_result.get('error', '未知错误')}")
                    
                    # 保存转换后的3DM文件
                    converted_file = conversion_result['converted_file']
                    
                    # 确定保存路径
                    original_dir = os.path.dirname(file_path)
                    base_name = os.path.splitext(os.path.basename(file_path))[0]
                    converted_filename = f"{base_name}_converted.3dm"
                    converted_path = os.path.join(original_dir, converted_filename)
                    
                    # 保存到文件系统
                    with open(converted_path, 'wb') as out_f:
                        out_f.write(converted_file.read())
                    
                    # 更新模型的文件路径指向转换后的3DM文件
                    # 保存相对路径到数据库
                    from django.conf import settings
                    relative_path = os.path.relpath(converted_path, settings.MEDIA_ROOT)
                    model.file.name = relative_path
                    model.save(update_fields=['file'])
                    
                    logger.info(f"STL转换成功: {converted_path}")
                    file_path = converted_path  # 更新处理路径
                    
            except Exception as conv_error:
                logger.error(f"STL转换失败: {conv_error}", exc_info=True)
                raise ValueError(f"STL文件转换失败: {str(conv_error)}")
        
        file_size = os.path.getsize(file_path)
        if file_size > LODConfig.MAX_INPUT_SIZE:
            raise ValueError(f"文件过大: {file_size / 1024 / 1024:.1f}MB > {LODConfig.MAX_INPUT_SIZE / 1024 / 1024}MB")
        
        # 4. 更新处理状态
        model.processing_status = 'processing'
        model.save(update_fields=['processing_status'])
        
        # 5. 设置缓存状态
        cache_key = f"lod_processing_{model_type}_{model_id}"
        cache.set(cache_key, {
            'status': 'processing',
            'task_id': task_id,
            'started_at': datetime.now().isoformat(),
            'progress': 10
        }, timeout=LODConfig.PROCESSING_TIMEOUT)
        
        # 6. 确保目录存在
        LODConfig.ensure_directories()
        
        # 7. 创建GLB处理器
        processor = create_glb_processor(
            cache_dir=LODConfig.CACHE_DIR,
            max_workers=LODConfig.MAX_WORKERS
        )
        
        if not processor:
            raise RuntimeError("无法创建GLB处理器")
        
        # 8. 设置输出路径
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_subdir = f"{model_type}s/{timestamp}_{model_id}"
        output_dir = Path(LODConfig.GLB_OUTPUT_DIR) / output_subdir
        
        # 更新进度
        cache.set(cache_key, {
            'status': 'processing',
            'task_id': task_id,
            'started_at': datetime.now().isoformat(),
            'progress': 30,
            'stage': 'converting'
        }, timeout=LODConfig.PROCESSING_TIMEOUT)
        
        # 9. 执行转换
        logger.info(f"开始转换: {model.file.path} -> {output_dir}")
        
        conversion_result = processor.convert_3dm_to_glb(
            input_path=model.file.path,
            output_dir=output_dir,
            lod_levels=LODConfig.DEFAULT_LOD_LEVELS,
            base_name=f"{model_type}_{model_id}"
        )
        
        if not conversion_result.success:
            raise RuntimeError(f"GLB转换失败: {conversion_result.error_message}")
        
        # 更新进度
        cache.set(cache_key, {
            'status': 'processing',
            'task_id': task_id,
            'started_at': datetime.now().isoformat(),
            'progress': 80,
            'stage': 'updating_database'
        }, timeout=LODConfig.PROCESSING_TIMEOUT)
        
        # 10. 更新数据库
        lod_files = {}
        for level, file_path in conversion_result.output_files.items():
            # 存储相对路径
            relative_path = get_relative_media_path(file_path)
            lod_files[level] = relative_path
            logger.info(f"LOD {level}: {relative_path}")
        
        # 计算压缩比（使用preview级别作为参考）
        compression_ratio = None
        if 'preview' in conversion_result.stats:
            preview_stats = conversion_result.stats['preview']
            if isinstance(preview_stats, dict):
                compression_ratio = preview_stats.get('compression_ratio')
            else:
                compression_ratio = getattr(preview_stats, 'compression_ratio', None)
        
        # 更新模型字段
        model.lod_files = lod_files
        model.geometry_simplified = True
        model.supports_webgl = True
        model.render_engine = 'threejs'
        model.compression_ratio = compression_ratio
        model.processing_status = 'completed'
        model.save(update_fields=[
            'lod_files', 'geometry_simplified', 'supports_webgl', 
            'render_engine', 'compression_ratio', 'processing_status'
        ])
        
        # 11. 完成处理
        result = {
            'success': True,
            'model_id': model_id,
            'model_type': model_type,
            'lod_files': lod_files,
            'stats': {level: stat if isinstance(stat, dict) else {'success': False} for level, stat in conversion_result.stats.items()},
            'metadata': conversion_result.metadata
        }
        
        # 更新缓存状态
        cache.set(cache_key, {
            'status': 'completed',
            'task_id': task_id,
            'completed_at': datetime.now().isoformat(),
            'progress': 100,
            'result': result
        }, timeout=3600)  # 保留1小时
        
        logger.info(f"LOD处理完成: {model_type} #{model_id}")
        
        # 清理对象引用
        del processor
        del conversion_result
        gc.collect()  # 强制垃圾回收
        
        return result
        
    except Exception as e:
        logger.error(f"LOD处理失败: {model_type} #{model_id}: {e}")
        
        # 更新模型状态
        try:
            ModelClass = get_model_class(model_type)
            model = ModelClass.objects.get(id=model_id)
            model.processing_status = 'failed'
            model.save(update_fields=['processing_status'])
        except:
            pass
        
        # 更新缓存状态
        cache_key = f"lod_processing_{model_type}_{model_id}"
        cache.set(cache_key, {
            'status': 'failed',
            'task_id': task_id,
            'error': str(e),
            'failed_at': datetime.now().isoformat()
        }, timeout=3600)
        
        # Celery重试机制
        if self.request.retries < self.max_retries:
            logger.info(f"任务重试 {self.request.retries + 1}/{self.max_retries}")
            raise self.retry(countdown=60 * (self.request.retries + 1))
        
        return {
            'success': False,
            'error': 'processing_failed',
            'message': str(e),
            'model_id': model_id,
            'model_type': model_type
        }
    finally:
        # 最终清理
        gc.collect()


@shared_task
def batch_process_models_lod(model_ids: List[int], model_type: str = 'shoe'):
    """
    批量处理模型LOD
    
    Args:
        model_ids: 模型ID列表
        model_type: 模型类型
        
    Returns:
        dict: 批量处理结果
    """
    logger.info(f"开始批量处理LOD: {model_type}s {model_ids}")
    
    results = {
        'total': len(model_ids),
        'success': 0,
        'failed': 0,
        'skipped': 0,
        'details': []
    }
    
    for model_id in model_ids:
        try:
            # 调用单个处理任务
            result = process_model_lod.delay(model_id, model_type)
            task_result = result.get(timeout=LODConfig.PROCESSING_TIMEOUT)
            
            if task_result.get('success', False):
                if task_result.get('skipped', False):
                    results['skipped'] += 1
                else:
                    results['success'] += 1
            else:
                results['failed'] += 1
            
            results['details'].append({
                'model_id': model_id,
                'result': task_result
            })
            
        except Exception as e:
            logger.error(f"批量处理模型 {model_id} 失败: {e}")
            results['failed'] += 1
            results['details'].append({
                'model_id': model_id,
                'result': {
                    'success': False,
                    'error': str(e)
                }
            })
    
    logger.info(f"批量LOD处理完成: 成功 {results['success']}, 失败 {results['failed']}, 跳过 {results['skipped']}")
    return results


@shared_task
def cleanup_old_lod_files(days_old: int = 30):
    """
    清理旧的LOD文件
    
    Args:
        days_old: 删除多少天前的文件
        
    Returns:
        dict: 清理结果
    """
    logger.info(f"开始清理 {days_old} 天前的LOD文件")
    
    import time
    from pathlib import Path
    
    cutoff_time = time.time() - (days_old * 24 * 60 * 60)
    glb_dir = Path(LODConfig.GLB_OUTPUT_DIR)
    
    if not glb_dir.exists():
        return {'success': True, 'deleted': 0, 'message': 'GLB目录不存在'}
    
    deleted_count = 0
    total_size = 0
    
    try:
        for file_path in glb_dir.rglob('*.glb'):
            if file_path.stat().st_mtime < cutoff_time:
                file_size = file_path.stat().st_size
                file_path.unlink()
                deleted_count += 1
                total_size += file_size
                logger.info(f"已删除旧文件: {file_path}")
        
        logger.info(f"清理完成: 删除 {deleted_count} 个文件, 释放 {total_size / 1024 / 1024:.1f} MB")
        
        return {
            'success': True,
            'deleted': deleted_count,
            'size_freed_mb': total_size / 1024 / 1024
        }
        
    except Exception as e:
        logger.error(f"清理失败: {e}")
        return {
            'success': False,
            'error': str(e)
        }


# ========================== 状态查询函数 ========================== #

def get_lod_processing_status(model_id: int, model_type: str) -> Dict:
    """
    获取LOD处理状态
    
    Args:
        model_id: 模型ID
        model_type: 模型类型
        
    Returns:
        dict: 状态信息
    """
    cache_key = f"lod_processing_{model_type}_{model_id}"
    status = cache.get(cache_key)
    
    if status:
        return status
    
    # 检查数据库状态
    try:
        ModelClass = get_model_class(model_type)
        model = ModelClass.objects.get(id=model_id)
        
        if model.geometry_simplified:
            return {
                'status': 'completed',
                'progress': 100,
                'lod_files': model.lod_files,
                'compression_ratio': model.compression_ratio
            }
        else:
            return {
                'status': model.processing_status,
                'progress': 0
            }
            
    except Exception:
        return {
            'status': 'unknown',
            'progress': 0
        }


def check_lod_system_health() -> Dict:
    """
    检查LOD系统健康状态
    
    Returns:
        dict: 系统健康状态
    """
    health_status = {
        'overall_healthy': True,
        'components': {},
        'recommendations': []
    }
    
    # 检查GLB处理器依赖
    available, missing = validate_dependencies()
    health_status['components']['glb_processor'] = {
        'status': 'healthy' if available else 'error',
        'dependencies_available': available,
        'missing_dependencies': missing
    }
    
    if not available:
        health_status['overall_healthy'] = False
        health_status['recommendations'].append(
            f"请安装缺失的依赖: pip install {' '.join(missing)}"
        )
    
    # 检查目录权限
    try:
        LODConfig.ensure_directories()
        test_file = Path(LODConfig.GLB_OUTPUT_DIR) / '.test'
        test_file.touch()
        test_file.unlink()
        
        health_status['components']['file_system'] = {
            'status': 'healthy',
            'glb_output_dir': LODConfig.GLB_OUTPUT_DIR,
            'writable': True
        }
        
    except Exception as e:
        health_status['overall_healthy'] = False
        health_status['components']['file_system'] = {
            'status': 'error',
            'error': str(e)
        }
        health_status['recommendations'].append(
            "检查GLB输出目录的写入权限"
        )
    
    # 检查磁盘空间
    import shutil
    try:
        total, used, free = shutil.disk_usage(LODConfig.GLB_OUTPUT_DIR)
        free_gb = free / (1024 ** 3)
        
        health_status['components']['disk_space'] = {
            'status': 'healthy' if free_gb > 1.0 else 'warning',
            'free_gb': round(free_gb, 2),
            'total_gb': round(total / (1024 ** 3), 2)
        }
        
        if free_gb < 1.0:
            health_status['recommendations'].append(
                f"磁盘空间不足，剩余 {free_gb:.2f} GB"
            )
            
    except Exception as e:
        health_status['components']['disk_space'] = {
            'status': 'error',
            'error': str(e)
        }
    
    return health_status
