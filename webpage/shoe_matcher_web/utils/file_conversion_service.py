#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件转换服务
统一处理各种3D文件格式的转换需求
"""

import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
import logging

logger = logging.getLogger(__name__)

# 导入 C++ 转换模块
try:
    import cppcore
    CPP_AVAILABLE = True
except ImportError as e:
    logger.warning(f"C++ conversion module not available: {e}")
    CPP_AVAILABLE = False


class FileConversionService:
    """文件转换服务类"""
    
    SUPPORTED_INPUT_FORMATS = ['.stl']
    TARGET_FORMAT = '.3dm'
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    
    @classmethod
    def is_conversion_needed(cls, file_obj) -> bool:
        """检查文件是否需要转换"""
        filename = file_obj.name.lower()
        return any(filename.endswith(ext) for ext in cls.SUPPORTED_INPUT_FORMATS)
    
    @classmethod
    def get_file_format(cls, file_obj) -> str:
        """获取文件格式"""
        filename = file_obj.name.lower()
        return Path(filename).suffix
    
    @classmethod
    def convert_if_needed(cls, uploaded_file, user=None) -> Dict[str, Any]:
        """
        根据文件类型自动转换
        
        Args:
            uploaded_file: Django UploadedFile对象
            user: 上传用户（可选）
            
        Returns:
            dict: {
                'success': bool,
                'converted_file': File对象或None,
                'original_format': str,
                'conversion_info': dict,
                'error': str (如果失败)
            }
        """
        result = {
            'success': False,
            'converted_file': None,
            'original_format': cls.get_file_format(uploaded_file),
            'conversion_info': {},
            'error': None
        }
        
        try:
            # 检查是否需要转换
            if not cls.is_conversion_needed(uploaded_file):
                result.update({
                    'success': True,
                    'converted_file': uploaded_file,
                    'conversion_info': {'type': 'no_conversion_needed'}
                })
                return result
            
            # 检查转换器可用性
            if not CPP_AVAILABLE:
                result['error'] = 'C++ conversion module not available'
                return result
            
            # 执行转换
            if uploaded_file.name.lower().endswith('.stl'):
                conversion_result = cls._convert_stl_to_3dm(uploaded_file)
                if conversion_result['success']:
                    result.update({
                        'success': True,
                        'converted_file': conversion_result['converted_file'],
                        'conversion_info': conversion_result['info']
                    })
                else:
                    result['error'] = conversion_result['error']
            else:
                result['error'] = f"Unsupported format for conversion: {result['original_format']}"
                
        except Exception as e:
            logger.error(f"File conversion failed: {e}")
            result['error'] = str(e)
            
        return result
    
    @classmethod
    def _convert_stl_to_3dm(cls, stl_file) -> Dict[str, Any]:
        """
        STL转3DM的具体实现
        
        Args:
            stl_file: STL文件对象
            
        Returns:
            dict: 转换结果
        """
        temp_files_to_cleanup = []
        
        try:
            # 生成唯一文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            unique_id = str(uuid.uuid4())[:8]
            base_name = os.path.splitext(stl_file.name)[0]
            
            # 保存临时STL文件
            temp_dir = tempfile.gettempdir()
            stl_filename = f"{base_name}_{timestamp}_{unique_id}.stl"
            temp_stl_path = os.path.join(temp_dir, stl_filename)
            temp_files_to_cleanup.append(temp_stl_path)
            
            with open(temp_stl_path, 'wb') as f:
                for chunk in stl_file.chunks():
                    f.write(chunk)
            
            # 生成输出3DM文件路径
            output_filename = f"{base_name}_{timestamp}_{unique_id}.3dm"
            temp_3dm_path = os.path.join(temp_dir, output_filename)
            temp_files_to_cleanup.append(temp_3dm_path)
            
            # 调用C++转换引擎
            conversion_result = cppcore.stl_to_3dm(temp_stl_path, temp_3dm_path)
            
            if not conversion_result.get('success', False):
                return {
                    'success': False,
                    'error': conversion_result.get('error', 'STL conversion failed'),
                    'converted_file': None,
                    'info': {}
                }
            
            # 读取转换后的3DM文件
            with open(temp_3dm_path, 'rb') as f:
                content = f.read()
            
            # 创建Django File对象 - 使用正确的命名策略
            # 确保文件名有正确的3DM扩展名，避免后续重命名
            base_name_clean = os.path.splitext(os.path.basename(stl_file.name))[0]
            converted_filename = f"{base_name_clean}_converted.3dm"
            converted_file = ContentFile(content, name=converted_filename)
            
            # 计算文件统计信息
            file_size_mb = len(content) / (1024 * 1024)
            
            return {
                'success': True,
                'converted_file': converted_file,
                'error': None,
                'info': {
                    'type': 'stl_to_3dm',
                    'original_filename': stl_file.name,
                    'converted_filename': converted_filename,
                    'triangle_count': conversion_result.get('triangle_count', 0),
                    'vertex_count': conversion_result.get('vertex_count', 0),
                    'file_size_mb': round(file_size_mb, 2),
                    'converted_at': datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"STL to 3DM conversion failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'converted_file': None,
                'info': {}
            }
        finally:
            # 清理临时文件
            cls._cleanup_temp_files(temp_files_to_cleanup)
    
    @classmethod
    def _cleanup_temp_files(cls, file_paths):
        """清理临时文件"""
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.debug(f"Cleaned up temp file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp file {file_path}: {e}")
    
    @classmethod
    def get_conversion_stats(cls, conversion_info: Dict) -> Dict[str, Any]:
        """获取转换统计信息"""
        if not conversion_info or conversion_info.get('type') == 'no_conversion_needed':
            return {}
        
        return {
            'conversion_type': conversion_info.get('type'),
            'original_filename': conversion_info.get('original_filename'),
            'triangle_count': conversion_info.get('triangle_count', 0),
            'vertex_count': conversion_info.get('vertex_count', 0),
            'file_size_mb': conversion_info.get('file_size_mb', 0),
            'converted_at': conversion_info.get('converted_at')
        }


class ConversionError(Exception):
    """转换错误异常"""
    pass


class UnsupportedFormatError(ConversionError):
    """不支持的格式错误"""
    pass
