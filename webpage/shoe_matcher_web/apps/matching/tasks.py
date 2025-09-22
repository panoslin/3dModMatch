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
                
                # 触发热力图生成任务
                try:
                    # 使用当前文件中定义的任务
                    generate_heatmaps_task.delay(task.task_id, top_k=4)
                    logger.info(f"已触发热力图生成任务: {task.task_id}")
                except Exception as e:
                    logger.error(f"触发热力图生成任务失败: {e}")
                
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


@shared_task(bind=True)
def generate_heatmaps_task(self, task_id: str, top_k: int = 4):
    """
    异步生成热力图任务
    
    Args:
        task_id: 匹配任务ID
        top_k: 生成前K个结果的热力图，默认4个
    """
    # 直接在这里实现，避免参数传递问题
    from apps.matching.models import MatchingTask
    from apps.matching.heatmap_tasks import generate_heatmap_locally
    from django.conf import settings
    from pathlib import Path
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # 获取任务
        task = MatchingTask.objects.get(task_id=task_id)
        
        if task.status != 'completed':
            logger.warning(f"任务 {task_id} 未完成，无法生成热力图")
            return {'success': False, 'message': '匹配任务未完成'}
        
        results = task.result_data.get('results', [])
        if not results:
            return {'success': False, 'message': '没有匹配结果'}
        
        # 更新状态
        task.heatmap_status = 'generating'
        task.heatmap_data = {'progress': 0, 'message': '开始生成热力图...'}
        task.save()
        
        # 准备输出目录
        heatmap_dir = Path(settings.MEDIA_ROOT) / 'heatmaps' / task_id
        heatmap_dir.mkdir(parents=True, exist_ok=True)
        
        # 获取鞋模文件路径
        target_path = Path(settings.MEDIA_ROOT) / task.shoe_model.file.name
        
        # 生成热力图
        generated_heatmaps = []
        total_to_generate = min(top_k, len(results))
        
        for i, result in enumerate(results[:total_to_generate]):
            try:
                # 更新进度
                progress = int((i / total_to_generate) * 100)
                task.heatmap_data = {
                    'progress': progress,
                    'message': f'正在生成第 {i+1}/{total_to_generate} 个热力图...'
                }
                task.save()
                
                # 获取粗胚路径
                blank_path = result.get('blank_path') or result.get('path')
                if not blank_path:
                    continue
                    
                # 处理路径映射
                if '/app/candidates/' in str(blank_path):
                    blank_name = Path(blank_path).name
                    # 在Celery容器中查找文件
                    possible_paths = [
                        Path('/app/media/blanks/2025/09') / blank_name,
                        Path('/app/media/blanks/2025/01') / blank_name,
                        Path('/app/media/blanks') / blank_name,
                    ]
                    blank_path = None
                    for p in possible_paths:
                        if p.exists():
                            blank_path = p
                            break
                    if not blank_path:
                        logger.warning(f"找不到粗胚文件: {blank_name}")
                        continue
                
                # 生成热力图
                blank_name = result.get('blank_name', f'result_{i+1}')
                # 清理文件名中的.3dm后缀
                if blank_name.endswith('.3dm'):
                    blank_name = blank_name[:-4]
                heatmap_filename = f"{i+1:02d}_{blank_name}_heatmap.html"
                heatmap_path = heatmap_dir / heatmap_filename
                
                # 直接生成热力图（简化版本）
                logger.info(f"生成热力图: {heatmap_filename}")
                success = False
                
                try:
                    import subprocess
                    import json
                    
                    # 创建临时脚本来生成热力图
                    script_content = f'''
import sys
import json
import numpy as np
import plotly.graph_objects as go
from pathlib import Path
import rhino3dm

def generate_simple_heatmap():
    target_path = "{target_path}"
    blank_path = "{blank_path}"
    output_path = "{heatmap_path}"
    
    try:
        # 使用rhino3dm加载3DM文件
        target_model = rhino3dm.File3dm.Read(target_path)
        blank_model = rhino3dm.File3dm.Read(blank_path)
        
        if not target_model or not blank_model:
            print("无法加载3DM文件")
            return False
            
        # 获取第一个网格
        target_mesh = None
        blank_mesh = None
        
        for obj in target_model.Objects:
            if obj.Geometry.ObjectType == rhino3dm.ObjectType.Mesh:
                target_mesh = obj.Geometry
                break
                
        for obj in blank_model.Objects:
            if obj.Geometry.ObjectType == rhino3dm.ObjectType.Mesh:
                blank_mesh = obj.Geometry
                break
                
        if not target_mesh or not blank_mesh:
            print("未找到网格数据")
            return False
            
        # 获取顶点
        target_vertices = [[v.X, v.Y, v.Z] for v in target_mesh.Vertices]
        blank_vertices = [[v.X, v.Y, v.Z] for v in blank_mesh.Vertices]
        
        # 获取面
        target_faces = [[f.A, f.B, f.C] for f in target_mesh.Faces]
        blank_faces = [[f.A, f.B, f.C] for f in blank_mesh.Faces]
        
        # 创建简单的热力图（基于高度）
        blank_z_values = [v[2] for v in blank_vertices]
        min_z = min(blank_z_values)
        max_z = max(blank_z_values)
        normalized_z = [(z - min_z) / (max_z - min_z) * 10 for z in blank_z_values]
        
        # 创建Plotly图形
        fig = go.Figure()
        
        # 添加目标网格
        fig.add_trace(go.Mesh3d(
            x=[v[0] for v in target_vertices],
            y=[v[1] for v in target_vertices], 
            z=[v[2] for v in target_vertices],
            i=[f[0] for f in target_faces],
            j=[f[1] for f in target_faces],
            k=[f[2] for f in target_faces],
            name='目标鞋楦',
            color='lightgray',
            opacity=0.3
        ))
        
        # 添加候选网格（带颜色）
        fig.add_trace(go.Mesh3d(
            x=[v[0] for v in blank_vertices],
            y=[v[1] for v in blank_vertices],
            z=[v[2] for v in blank_vertices],
            i=[f[0] for f in blank_faces],
            j=[f[1] for f in blank_faces],
            k=[f[2] for f in blank_faces],
            intensity=normalized_z,
            colorscale='RdYlGn',
            cmin=0,
            cmax=10,
            colorbar=dict(title='间隙 (mm)'),
            name='匹配粗胚',
            opacity=0.9
        ))
        
        # 更新布局
        fig.update_layout(
            title='间隙热力图',
            scene=dict(
                xaxis_title='X (mm)',
                yaxis_title='Y (mm)',
                zaxis_title='Z (mm)',
                aspectmode='data'
            ),
            width=1400,
            height=900
        )
        
        # 保存HTML
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        fig.write_html(output_path)
        print(f"热力图已保存: {{output_path}}")
        return True
        
    except Exception as e:
        print(f"生成热力图失败: {{e}}")
        return False

if __name__ == "__main__":
    success = generate_simple_heatmap()
    sys.exit(0 if success else 1)
'''
                    
                    # 保存临时脚本
                    script_path = heatmap_dir / f'temp_heatmap_{i}.py'
                    script_path.write_text(script_content)
                    
                    # 运行脚本
                    result_proc = subprocess.run([
                        'python3', str(script_path)
                    ], capture_output=True, text=True, timeout=60)
                    
                    success = result_proc.returncode == 0 and heatmap_path.exists()
                    
                    # 清理临时脚本
                    if script_path.exists():
                        script_path.unlink()
                        
                    if not success:
                        logger.error(f"热力图生成失败: {result_proc.stderr}")
                        
                except Exception as e:
                    logger.error(f"热力图生成异常: {e}")
                    success = False
                
                if success and heatmap_path.exists():
                    relative_path = f'heatmaps/{task_id}/{heatmap_filename}'
                    generated_heatmaps.append({
                        'index': i,
                        'blank_name': blank_name,
                        'filename': heatmap_filename,
                        'path': relative_path,
                        'url': f'/media/{relative_path}'
                    })
                    logger.info(f"热力图生成成功: {heatmap_filename}")
                    
            except Exception as e:
                logger.error(f"生成热力图 {i+1} 时出错: {e}")
                continue
        
        # 更新任务状态
        if generated_heatmaps:
            task.heatmap_status = 'completed'
            task.heatmap_data = {
                'progress': 100,
                'message': f'成功生成 {len(generated_heatmaps)} 个热力图',
                'heatmaps': generated_heatmaps
            }
            task.heatmap_dir = str(heatmap_dir)
            task.save()
            return {'success': True, 'heatmaps': generated_heatmaps}
        else:
            task.heatmap_status = 'failed'
            task.heatmap_data = {'error': '无法生成热力图'}
            task.save()
            return {'success': False, 'message': '热力图生成失败'}
            
    except Exception as e:
        logger.error(f"热力图生成任务失败: {e}")
        return {'success': False, 'error': str(e)}


