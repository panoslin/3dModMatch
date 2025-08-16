"""
匹配任务处理模块
"""

import logging
import time
from django.utils import timezone
from typing import List, Optional

from .algorithms import MatchingEngine, MatchingResultsProcessor
from .models import MatchingTask
from apps.core.models import ShoeModel, BlankModel, ProcessingLog

logger = logging.getLogger(__name__)


class MockCeleryTask:
    """模拟Celery任务类"""
    def __init__(self, func):
        self.func = func
        self.id = f"matching_task_{int(time.time())}"
    
    def delay(self, *args, **kwargs):
        """模拟异步执行"""
        try:
            return self.func(*args, **kwargs)
        except Exception as e:
            logger.error(f"匹配任务执行失败: {e}")
            return None


def celery_task(func):
    """装饰器：模拟Celery任务"""
    return MockCeleryTask(func)


@celery_task
def perform_matching_analysis(
    shoe_id: int, 
    margin_distance: float = 2.5,
    target_blank_ids: Optional[List[int]] = None
):
    """
    执行匹配分析任务
    
    Args:
        shoe_id: 鞋模ID
        margin_distance: 余量距离（毫米）
        target_blank_ids: 指定的粗胚ID列表，为None时使用所有已处理的粗胚
        
    Returns:
        dict: 匹配分析结果
    """
    logger.info(f"开始执行匹配分析任务: 鞋模ID={shoe_id}, 余量={margin_distance}mm")
    
    # 创建匹配任务记录
    task = MatchingTask.objects.create(
        task_type='single_matching',
        status='processing',
        shoe_model_id=shoe_id,
        margin_distance=margin_distance,
        target_blank_ids=target_blank_ids or []
    )
    
    try:
        # 获取鞋模
        try:
            shoe_model = ShoeModel.objects.get(id=shoe_id, is_processed=True)
        except ShoeModel.DoesNotExist:
            raise ValueError(f"鞋模 ID={shoe_id} 不存在或未处理")
        
        # 获取目标粗胚列表
        if target_blank_ids:
            blank_models = BlankModel.objects.filter(
                id__in=target_blank_ids, 
                is_processed=True
            )
        else:
            blank_models = BlankModel.objects.filter(is_processed=True)
        
        blank_list = list(blank_models)
        
        if not blank_list:
            raise ValueError("没有找到可用的粗胚模型")
        
        logger.info(f"找到 {len(blank_list)} 个可用粗胚模型")
        
        # 初始化匹配引擎
        matching_engine = MatchingEngine(margin_distance=margin_distance)
        
        # 执行匹配分析
        matching_scores = matching_engine.perform_matching(shoe_model, blank_list)
        
        # 保存匹配结果到数据库
        saved_results = MatchingResultsProcessor.save_matching_results(
            shoe_model, matching_scores, margin_distance
        )
        
        # 更新任务状态
        task.status = 'completed'
        task.completed_at = timezone.now()
        task.results_count = len(saved_results)
        
        # 找到最优匹配
        optimal_result = next((r for r in saved_results if r.is_optimal), None)
        if optimal_result:
            task.optimal_blank_model = optimal_result.blank_model
            task.optimal_score = optimal_result.total_score
        
        task.save()
        
        # 记录处理日志
        ProcessingLog.objects.create(
            operation='matching',
            level='info',
            message=f'完成匹配分析: 鞋模={shoe_model.filename}, '
                   f'分析了{len(blank_list)}个粗胚, 找到{len(saved_results)}个结果',
            shoe_model=shoe_model
        )
        
        # 准备返回结果
        result_summary = {
            'success': True,
            'task_id': task.id,
            'shoe_model': {
                'id': shoe_model.id,
                'filename': shoe_model.filename
            },
            'analysis_results': {
                'total_analyzed': len(blank_list),
                'feasible_matches': len([r for r in saved_results if r.is_feasible]),
                'optimal_match': {
                    'blank_id': optimal_result.blank_model.id,
                    'blank_filename': optimal_result.blank_model.filename,
                    'total_score': optimal_result.total_score,
                    'material_utilization': optimal_result.material_utilization,
                    'cost_savings': optimal_result.cost_savings,
                } if optimal_result else None
            },
            'margin_distance': margin_distance,
            'processing_time': (task.completed_at - task.created_at).total_seconds()
        }
        
        logger.info(f"匹配分析任务完成: {result_summary}")
        return result_summary
        
    except Exception as e:
        logger.error(f"匹配分析任务失败: {e}")
        
        # 更新任务状态为失败
        task.status = 'failed'
        task.error_message = str(e)
        task.completed_at = timezone.now()
        task.save()
        
        # 记录错误日志
        ProcessingLog.objects.create(
            operation='matching',
            level='error',
            message=f'匹配分析失败: {str(e)}',
            shoe_model_id=shoe_id
        )
        
        return {
            'success': False,
            'task_id': task.id,
            'error': str(e),
            'shoe_id': shoe_id
        }


@celery_task
def batch_matching_analysis(
    shoe_ids: List[int], 
    margin_distance: float = 2.5
):
    """
    批量匹配分析任务
    
    Args:
        shoe_ids: 鞋模ID列表
        margin_distance: 余量距离（毫米）
        
    Returns:
        dict: 批量分析结果
    """
    logger.info(f"开始批量匹配分析: {len(shoe_ids)}个鞋模, 余量={margin_distance}mm")
    
    # 创建批量任务记录
    task = MatchingTask.objects.create(
        task_type='batch_matching',
        status='processing',
        margin_distance=margin_distance,
        target_shoe_ids=shoe_ids
    )
    
    results = []
    successful_count = 0
    failed_count = 0
    
    try:
        for shoe_id in shoe_ids:
            try:
                # 调用单个匹配分析
                result = perform_matching_analysis.func(shoe_id, margin_distance)
                results.append(result)
                
                if result.get('success'):
                    successful_count += 1
                else:
                    failed_count += 1
                    
            except Exception as e:
                logger.error(f"批量匹配中鞋模 {shoe_id} 处理失败: {e}")
                failed_count += 1
                results.append({
                    'success': False,
                    'shoe_id': shoe_id,
                    'error': str(e)
                })
        
        # 更新批量任务状态
        task.status = 'completed'
        task.completed_at = timezone.now()
        task.results_count = successful_count
        task.save()
        
        summary = {
            'success': True,
            'task_id': task.id,
            'summary': {
                'total_shoes': len(shoe_ids),
                'successful': successful_count,
                'failed': failed_count,
                'success_rate': (successful_count / len(shoe_ids)) * 100 if shoe_ids else 0
            },
            'results': results,
            'processing_time': (task.completed_at - task.created_at).total_seconds()
        }
        
        logger.info(f"批量匹配分析完成: 成功{successful_count}/{len(shoe_ids)}")
        return summary
        
    except Exception as e:
        logger.error(f"批量匹配分析任务失败: {e}")
        
        task.status = 'failed'
        task.error_message = str(e)
        task.completed_at = timezone.now()
        task.save()
        
        return {
            'success': False,
            'task_id': task.id,
            'error': str(e),
            'partial_results': results
        }


@celery_task
def optimize_matching_parameters(shoe_id: int):
    """
    优化匹配参数任务
    
    Args:
        shoe_id: 鞋模ID
        
    Returns:
        dict: 优化结果
    """
    logger.info(f"开始参数优化: 鞋模ID={shoe_id}")
    
    try:
        shoe_model = ShoeModel.objects.get(id=shoe_id, is_processed=True)
        blank_models = list(BlankModel.objects.filter(is_processed=True))
        
        if not blank_models:
            raise ValueError("没有可用的粗胚模型进行参数优化")
        
        # 测试不同余量距离的效果
        margin_distances = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
        optimization_results = []
        
        for margin in margin_distances:
            matching_engine = MatchingEngine(margin_distance=margin)
            matching_scores = matching_engine.perform_matching(shoe_model, blank_models)
            
            # 统计结果
            feasible_count = sum(1 for score in matching_scores if score.details.get('is_feasible'))
            avg_utilization = sum(score.volume_efficiency for score in matching_scores) / len(matching_scores) if matching_scores else 0
            
            best_score = matching_scores[0] if matching_scores else None
            
            optimization_results.append({
                'margin_distance': margin,
                'feasible_matches': feasible_count,
                'average_utilization': avg_utilization,
                'best_total_score': best_score.total_score if best_score else 0,
                'best_blank': best_score.details.get('blank_filename') if best_score else None
            })
        
        # 找到最优参数配置
        best_config = max(
            optimization_results, 
            key=lambda x: x['feasible_matches'] * 100 + x['average_utilization']
        )
        
        logger.info(f"参数优化完成，最优余量距离: {best_config['margin_distance']}mm")
        
        return {
            'success': True,
            'shoe_model': {
                'id': shoe_model.id,
                'filename': shoe_model.filename
            },
            'optimization_results': optimization_results,
            'recommended_margin': best_config['margin_distance'],
            'best_configuration': best_config
        }
        
    except Exception as e:
        logger.error(f"参数优化失败: {e}")
        return {
            'success': False,
            'error': str(e),
            'shoe_id': shoe_id
        }


def get_matching_task_status(task_id: int) -> dict:
    """
    获取匹配任务状态
    
    Args:
        task_id: 任务ID
        
    Returns:
        dict: 任务状态信息
    """
    try:
        task = MatchingTask.objects.get(id=task_id)
        
        status_info = {
            'task_id': task.id,
            'status': task.status,
            'task_type': task.task_type,
            'created_at': task.created_at,
            'completed_at': task.completed_at,
            'margin_distance': task.margin_distance,
            'results_count': task.results_count,
            'error_message': task.error_message,
        }
        
        if task.shoe_model:
            status_info['shoe_model'] = {
                'id': task.shoe_model.id,
                'filename': task.shoe_model.filename
            }
        
        if task.optimal_blank_model:
            status_info['optimal_match'] = {
                'blank_id': task.optimal_blank_model.id,
                'blank_filename': task.optimal_blank_model.filename,
                'optimal_score': task.optimal_score
            }
        
        return status_info
        
    except MatchingTask.DoesNotExist:
        return {
            'error': f'任务ID {task_id} 不存在'
        }
    except Exception as e:
        logger.error(f"获取任务状态失败: {e}")
        return {
            'error': str(e)
        }


def cleanup_old_matching_results(days: int = 30):
    """
    清理旧的匹配结果
    
    Args:
        days: 保留天数
    """
    from django.utils import timezone
    from datetime import timedelta
    from apps.core.models import MatchingResult
    
    cutoff_date = timezone.now() - timedelta(days=days)
    
    # 清理旧的匹配结果（保留最优结果）
    old_results = MatchingResult.objects.filter(
        created_at__lt=cutoff_date,
        is_optimal=False
    )
    
    deleted_count = old_results.count()
    old_results.delete()
    
    # 清理旧的匹配任务
    old_tasks = MatchingTask.objects.filter(
        created_at__lt=cutoff_date,
        status__in=['completed', 'failed']
    )
    
    task_count = old_tasks.count()
    old_tasks.delete()
    
    logger.info(f"清理完成: 删除了 {deleted_count} 个旧匹配结果和 {task_count} 个旧任务")
    
    return {
        'deleted_results': deleted_count,
        'deleted_tasks': task_count
    }
