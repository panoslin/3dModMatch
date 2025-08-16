"""
文件处理任务
"""

import logging
import time
from pathlib import Path
from django.utils import timezone

from .parsers import ModelFileParser
from .models import FileProcessingTask
from apps.core.models import ShoeModel, BlankModel, ProcessingLog

logger = logging.getLogger(__name__)


class MockCeleryTask:
    """模拟Celery任务类，用于开发阶段"""
    def __init__(self, func):
        self.func = func
        self.id = f"mock_task_{int(time.time())}"
    
    def delay(self, *args, **kwargs):
        """模拟异步执行"""
        try:
            return self.func(*args, **kwargs)
        except Exception as e:
            logger.error(f"任务执行失败: {e}")
            return None


def celery_task(func):
    """装饰器：模拟Celery任务"""
    return MockCeleryTask(func)


@celery_task
def process_uploaded_files(shoe_ids=None, blank_ids=None, margin_distance=2.5):
    """
    处理上传的文件
    
    Args:
        shoe_ids: 鞋模文件ID列表
        blank_ids: 粗胚文件ID列表  
        margin_distance: 余量距离
    """
    if not shoe_ids:
        shoe_ids = []
    if not blank_ids:
        blank_ids = []
        
    logger.info(f"开始处理文件 - 鞋模: {len(shoe_ids)}, 粗胚: {len(blank_ids)}")
    
    # 创建处理任务记录
    task = FileProcessingTask.objects.create(
        task_type='batch_upload',
        status='processing',
        total_files=len(shoe_ids) + len(blank_ids),
        processed_files=0
    )
    
    try:
        processed_count = 0
        
        # 处理鞋模文件
        for shoe_id in shoe_ids:
            try:
                shoe_model = ShoeModel.objects.get(id=shoe_id)
                success = process_single_file(shoe_model, 'shoe')
                
                if success:
                    processed_count += 1
                    shoe_model.is_processed = True
                    shoe_model.processing_status = 'completed'
                    shoe_model.processed_at = timezone.now()
                else:
                    shoe_model.processing_status = 'failed'
                
                shoe_model.save()
                
                # 更新任务进度
                task.processed_files = processed_count
                task.save()
                
            except Exception as e:
                logger.error(f"处理鞋模文件 {shoe_id} 失败: {e}")
                ProcessingLog.objects.create(
                    operation='process',
                    level='error',
                    message=f'处理鞋模文件失败: {e}',
                    shoe_model_id=shoe_id
                )
        
        # 处理粗胚文件
        for blank_id in blank_ids:
            try:
                blank_model = BlankModel.objects.get(id=blank_id)
                success = process_single_file(blank_model, 'blank')
                
                if success:
                    processed_count += 1
                    blank_model.is_processed = True
                    blank_model.processing_status = 'completed'
                    blank_model.processed_at = timezone.now()
                else:
                    blank_model.processing_status = 'failed'
                    
                blank_model.save()
                
                # 更新任务进度
                task.processed_files = processed_count
                task.save()
                
            except Exception as e:
                logger.error(f"处理粗胚文件 {blank_id} 失败: {e}")
                ProcessingLog.objects.create(
                    operation='process',
                    level='error',
                    message=f'处理粗胚文件失败: {e}',
                    blank_model_id=blank_id
                )
        
        # 更新任务状态
        task.status = 'completed'
        task.completed_at = timezone.now()
        task.save()
        
        logger.info(f"文件处理完成 - 成功处理 {processed_count}/{task.total_files} 个文件")
        
        return {
            'success': True,
            'processed_count': processed_count,
            'total_count': task.total_files
        }
        
    except Exception as e:
        logger.error(f"批量文件处理失败: {e}")
        task.status = 'failed'
        task.error_message = str(e)
        task.save()
        
        return {
            'success': False,
            'error': str(e)
        }


def process_single_file(model, file_type):
    """
    处理单个文件
    
    Args:
        model: ShoeModel 或 BlankModel 实例
        file_type: 文件类型 ('shoe' 或 'blank')
    
    Returns:
        bool: 处理是否成功
    """
    try:
        logger.info(f"开始处理{file_type}文件: {model.filename}")
        
        # 获取文件路径
        if not model.file:
            logger.error(f"文件不存在: {model.filename}")
            return False
            
        file_path = model.file.path
        
        # 使用解析器分析文件
        parser = ModelFileParser(file_path)
        file_data = parser.parse()
        
        if not file_data:
            logger.error(f"文件解析失败: {model.filename}")
            return False
        
        # 更新模型数据
        model.points_count = file_data.get('points_count', 0)
        model.bounds = file_data.get('bounds', {})
        model.volume = file_data.get('volume', 0)
        model.surface_area = file_data.get('surface_area', 0)
        
        # 提取几何特征
        if file_data.get('points_count', 0) > 0:
            features = extract_geometric_features(file_data)
            model.geometric_features = features
        
        # 记录处理日志
        ProcessingLog.objects.create(
            operation='process',
            level='info',
            message=f'成功处理{file_type}文件: {model.filename} '
                   f'(点数: {model.points_count}, 体积: {model.volume:.2f})',
            shoe_model=model if file_type == 'shoe' else None,
            blank_model=model if file_type == 'blank' else None
        )
        
        logger.info(f"{file_type}文件处理成功: {model.filename}")
        return True
        
    except Exception as e:
        logger.error(f"{file_type}文件处理失败 {model.filename}: {e}")
        
        ProcessingLog.objects.create(
            operation='process',
            level='error',
            message=f'{file_type}文件处理失败: {model.filename} - {str(e)}',
            shoe_model=model if file_type == 'shoe' else None,
            blank_model=model if file_type == 'blank' else None
        )
        
        return False


def extract_geometric_features(file_data):
    """
    提取几何特征
    
    Args:
        file_data: 解析的文件数据
        
    Returns:
        dict: 几何特征数据
    """
    features = {}
    
    try:
        bounds = file_data.get('bounds', {})
        if bounds:
            # 包围盒尺寸
            features['bbox_dimensions'] = {
                'length': bounds.get('x_max', 0) - bounds.get('x_min', 0),
                'width': bounds.get('y_max', 0) - bounds.get('y_min', 0), 
                'height': bounds.get('z_max', 0) - bounds.get('z_min', 0)
            }
            
            # 中心点
            features['center_point'] = {
                'x': (bounds.get('x_max', 0) + bounds.get('x_min', 0)) / 2,
                'y': (bounds.get('y_max', 0) + bounds.get('y_min', 0)) / 2,
                'z': (bounds.get('z_max', 0) + bounds.get('z_min', 0)) / 2
            }
        
        # 基础统计信息
        features['basic_stats'] = {
            'points_count': file_data.get('points_count', 0),
            'volume': file_data.get('volume', 0),
            'surface_area': file_data.get('surface_area', 0)
        }
        
        # 形状复杂度指标（简化版）
        points_count = file_data.get('points_count', 0)
        if points_count > 0:
            features['complexity'] = {
                'point_density': points_count / max(file_data.get('volume', 1), 0.1),
                'shape_factor': file_data.get('surface_area', 0) / max(file_data.get('volume', 1), 0.1)
            }
        
    except Exception as e:
        logger.warning(f"几何特征提取部分失败: {e}")
        features['error'] = str(e)
    
    return features


@celery_task  
def cleanup_old_files(days=30):
    """
    清理旧文件（超过指定天数的未处理文件）
    
    Args:
        days: 保留天数
    """
    from django.utils import timezone
    from datetime import timedelta
    
    cutoff_date = timezone.now() - timedelta(days=days)
    
    # 清理旧的鞋模文件
    old_shoes = ShoeModel.objects.filter(
        created_at__lt=cutoff_date,
        is_processed=False
    )
    
    # 清理旧的粗胚文件 
    old_blanks = BlankModel.objects.filter(
        created_at__lt=cutoff_date,
        is_processed=False
    )
    
    deleted_count = 0
    for model in list(old_shoes) + list(old_blanks):
        try:
            if model.file:
                model.file.delete()
            model.delete()
            deleted_count += 1
        except Exception as e:
            logger.error(f"删除旧文件失败 {model.filename}: {e}")
    
    logger.info(f"清理了 {deleted_count} 个旧文件")
    return deleted_count


@celery_task
def batch_reprocess_files(file_ids, file_type='shoe'):
    """
    批量重新处理文件
    
    Args:
        file_ids: 文件ID列表
        file_type: 文件类型 ('shoe' 或 'blank')
    """
    logger.info(f"开始批量重新处理{file_type}文件: {len(file_ids)}个")
    
    success_count = 0
    for file_id in file_ids:
        try:
            if file_type == 'shoe':
                model = ShoeModel.objects.get(id=file_id)
            else:
                model = BlankModel.objects.get(id=file_id)
            
            # 重置状态
            model.is_processed = False
            model.processing_status = 'processing'
            model.processed_at = None
            model.save()
            
            # 重新处理
            if process_single_file(model, file_type):
                success_count += 1
                model.is_processed = True
                model.processing_status = 'completed'
                model.processed_at = timezone.now()
            else:
                model.processing_status = 'failed'
                
            model.save()
            
        except Exception as e:
            logger.error(f"重新处理文件 {file_id} 失败: {e}")
    
    logger.info(f"批量重新处理完成 - 成功: {success_count}/{len(file_ids)}")
    return success_count
