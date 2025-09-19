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
        
        # 创建临时目录结构 - 使用挂载的temp目录
        import uuid
        temp_id = uuid.uuid4().hex[:12]
        
        logger.info(f"匹配任务 {task.task_id}: 开始创建临时目录，temp_id={temp_id}")
        
        if os.environ.get('DJANGO_ENVIRONMENT') == 'docker':
            # 在Docker环境中，使用挂载的temp目录（./temp:/app/temp）
            temp_dir = f'/app/temp/match_{temp_id}'
            host_temp_dir = f'/root/3dModMatch/webpage/temp/match_{temp_id}'
            logger.info(f"Docker环境: 容器内路径={temp_dir}, 主机路径={host_temp_dir}")
        else:
            temp_dir = f'/tmp/match_{temp_id}'
            host_temp_dir = temp_dir
            logger.info(f"本地环境: 使用路径={temp_dir}")
        
        temp_path = Path(temp_dir)
        candidates_dir = temp_path / 'candidates'
        output_dir = temp_path / 'output'
        
        # 创建目录结构
        logger.info(f"创建目录结构: {temp_path}")
        temp_path.mkdir(parents=True, exist_ok=True)
        candidates_dir.mkdir()
        output_dir.mkdir()
        logger.info(f"目录创建完成: candidates={candidates_dir}, output={output_dir}")
        
        try:
            
            # 复制候选文件到临时目录
            task.progress = 20
            task.current_step = '准备候选文件...'
            task.save()
            
            logger.info(f"开始复制 {candidates.count()} 个候选文件到 {candidates_dir}")
            copied_count = 0
            for candidate in candidates:
                if candidate.file and os.path.exists(candidate.file.path):
                    src_file = Path(candidate.file.path)
                    dst_file = candidates_dir / src_file.name
                    try:
                        shutil.copy2(src_file, dst_file)
                        copied_count += 1
                        logger.debug(f"复制文件: {src_file.name} -> {dst_file}")
                    except Exception as e:
                        logger.error(f"复制文件失败: {src_file} -> {dst_file}, 错误: {e}")
                else:
                    logger.warning(f"跳过无效候选文件: {candidate.id}, file={candidate.file}")
            
            logger.info(f"文件复制完成: 成功复制 {copied_count}/{candidates.count()} 个文件")
            
            # 验证复制的文件
            actual_files = list(candidates_dir.glob('*.3dm'))
            logger.info(f"验证: 候选目录中实际有 {len(actual_files)} 个.3dm文件")
            
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
            
            # 执行匹配 - 传递正确路径给Docker命令
            docker_candidates_dir = host_temp_dir + '/candidates' if os.environ.get('DJANGO_ENVIRONMENT') == 'docker' else str(candidates_dir)
            docker_output_dir = host_temp_dir + '/output' if os.environ.get('DJANGO_ENVIRONMENT') == 'docker' else str(output_dir)
            
            logger.info(f"执行匹配算法:")
            logger.info(f"  - 目标文件: {shoe_file}")
            logger.info(f"  - 候选目录: {docker_candidates_dir}")
            logger.info(f"  - 输出目录: {docker_output_dir}")
            logger.info(f"  - 匹配参数: {match_params}")
            
            result = hybrid_service.run_matching(
                target_file=shoe_file,
                candidates_dir=docker_candidates_dir,
                output_dir=docker_output_dir,
                params=match_params
            )
            
            logger.info(f"匹配算法执行完成: success={result.get('success')}")
            if not result.get('success'):
                logger.error(f"匹配失败: {result.get('error')}")
            else:
                logger.info("匹配执行成功，开始解析结果")
                
                # 等待文件系统同步
                import time
                time.sleep(2)
                logger.info("等待文件系统同步完成")
                
                # 使用容器内的输出目录路径进行检查和解析
                # 因为我们在容器内运行，需要使用容器内的路径
                result_output_dir = str(output_dir)  # 使用容器内路径
                logger.info(f"使用输出目录进行解析: {result_output_dir}")
                
                # 检查输出目录状态
                if Path(result_output_dir).exists():
                    output_files = list(Path(result_output_dir).iterdir())
                    logger.info(f"输出目录内容 ({len(output_files)} 个项目):")
                    for item in output_files:
                        if item.is_file():
                            logger.info(f"  文件: {item.name} ({item.stat().st_size} bytes)")
                        else:
                            logger.info(f"  目录: {item.name}")
                else:
                    logger.error(f"输出目录不存在: {result_output_dir}")
                
                # 解析结果
                parse_result = hybrid_service.parse_results(result_output_dir)
                if parse_result['success']:
                    result['results'] = parse_result['results']
                    result['summary'] = parse_result['summary']
                    logger.info("任务中结果解析成功")
                else:
                    logger.error(f"任务中结果解析失败: {parse_result['error']}")
                    result['success'] = False
                    result['error'] = f"匹配成功但结果解析失败: {parse_result['error']}"
            
            if result['success']:
                # 处理匹配结果
                task.progress = 90
                task.current_step = '处理匹配结果...'
                task.save()
                
                # 确保结果数据存在
                if 'results' in result and 'summary' in result:
                    task.result_data = {'results': result['results']}
                    task.summary_data = result['summary']
                    logger.info(f"成功保存匹配结果: {len(result['results'])} 个结果")
                else:
                    raise RuntimeError("匹配成功但缺少结果数据")
                
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
        
        finally:
            # 只有在任务成功完成时才清理临时目录
            try:
                import time
                # 给文件系统一些时间确保所有写入操作完成
                time.sleep(3)
                
                # 检查任务是否成功完成
                task.refresh_from_db()
                should_cleanup = task.status == 'completed'
                
                if should_cleanup:
                    logger.info("任务成功完成，开始清理临时目录")
                    if 'temp_dir' in locals() and os.path.exists(temp_dir):
                        logger.info(f"清理容器内临时目录: {temp_dir}")
                        shutil.rmtree(temp_dir)
                    if os.environ.get('DJANGO_ENVIRONMENT') == 'docker' and 'host_temp_dir' in locals():
                        logger.info(f"清理主机临时目录: {host_temp_dir}")
                        subprocess.run(['rm', '-rf', host_temp_dir], check=False)
                else:
                    logger.info(f"任务状态为 {task.status}，保留临时目录用于调试")
                    if 'host_temp_dir' in locals():
                        logger.info(f"调试目录位置: {host_temp_dir}")
                        
            except Exception as e:
                logger.warning(f"清理临时目录失败: {e}")
        
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


