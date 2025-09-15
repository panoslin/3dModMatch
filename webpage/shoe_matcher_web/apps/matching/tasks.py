"""
匹配任务异步处理
"""

from celery import shared_task
from django.conf import settings
from django.utils import timezone
import os
import sys
import subprocess
import json
import tempfile
import shutil
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


@shared_task
def run_matching_task(task_id):
    """运行匹配任务"""
    from .models import MatchingTask
    from apps.blanks.models import BlankModel
    
    try:
        task = MatchingTask.objects.get(id=task_id)
        task.status = 'processing'
        task.progress = 5
        task.current_step = '准备匹配环境...'
        task.save()
        
        # 获取鞋模文件
        shoe_file = task.shoe_model.file.path
        if not os.path.exists(shoe_file):
            raise FileNotFoundError(f"鞋模文件不存在: {shoe_file}")
        
        # 获取候选粗胚文件
        candidates = BlankModel.objects.filter(
            categories__in=task.selected_categories.all(),
            is_active=True,
            is_processed=True
        ).distinct()
        
        if not candidates.exists():
            raise ValueError("没有找到符合条件的粗胚文件")
        
        task.progress = 10
        task.current_step = f'找到 {candidates.count()} 个候选粗胚...'
        task.save()
        
        # 创建临时目录结构
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            candidates_dir = temp_path / 'candidates'
            output_dir = temp_path / 'output'
            candidates_dir.mkdir()
            output_dir.mkdir()
            
            # 复制候选文件到临时目录
            task.progress = 20
            task.current_step = '准备候选文件...'
            task.save()
            
            for candidate in candidates:
                if candidate.file and os.path.exists(candidate.file.path):
                    src_file = Path(candidate.file.path)
                    dst_file = candidates_dir / src_file.name
                    shutil.copy2(src_file, dst_file)
            
            # 使用集成服务执行匹配
            task.progress = 30
            task.current_step = '启动匹配算法...'
            task.save()
            
            from utils.hybrid_integration import hybrid_service
            
            # 检查hybrid系统
            if not hybrid_service.check_hybrid_system():
                # 尝试构建C++模块
                if not hybrid_service.build_cpp_core():
                    raise RuntimeError("Hybrid系统不可用，且C++模块构建失败")
            
            # 准备匹配参数
            match_params = {
                'clearance': task.clearance,
                'threshold': task.threshold,
                'enable_scaling': task.enable_scaling,
                'enable_multi_start': task.enable_multi_start,
                'max_scale': task.max_scale
            }
            
            # 执行匹配
            result = hybrid_service.run_matching(
                target_file=shoe_file,
                candidates_dir=str(candidates_dir),
                output_dir=str(output_dir),
                params=match_params
            )
            
            if result['success']:
                # 处理匹配结果
                task.progress = 90
                task.current_step = '处理匹配结果...'
                task.save()
                
                # 使用集成服务解析结果
                parse_result = hybrid_service.parse_results(str(output_dir))
                if parse_result['success']:
                    task.result_data = {'results': parse_result['results']}
                    task.summary_data = parse_result['summary']
                else:
                    raise RuntimeError(f"结果解析失败: {parse_result['error']}")
                
                task.status = 'completed'
                task.progress = 100
                task.current_step = '匹配完成'
                task.completed_at = timezone.now()
                
                if task.started_at:
                    task.processing_time = (
                        task.completed_at - task.started_at
                    ).total_seconds()
                
                logger.info(f"Matching task {task.task_id} completed successfully")
                
            else:
                task.status = 'failed'
                task.current_step = f'匹配失败: {result["error"]}'
                logger.error(f"Matching task {task.task_id} failed: {result['error']}")
        
        task.save()
        return {'success': task.status == 'completed', 'task_id': task.task_id}
        
    except MatchingTask.DoesNotExist:
        logger.error(f"Matching task {task_id} does not exist")
        return {'success': False, 'error': 'Task not found'}
    except Exception as e:
        logger.error(f"Error in matching task {task_id}: {e}")
        try:
            task = MatchingTask.objects.get(id=task_id)
            task.status = 'failed'
            task.current_step = f'处理错误: {str(e)}'
            task.save()
        except:
            pass
        return {'success': False, 'error': str(e)}


