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
    """
    运行3D鞋模匹配任务
    
    这是Celery异步任务，负责执行完整的鞋模匹配流程：
    1. 验证任务和文件
    2. 准备候选粗胚文件
    3. 调用Hybrid匹配算法
    4. 解析和保存结果
    5. 触发热力图生成
    
    Args:
        task_id: MatchingTask模型的主键ID
        
    Returns:
        dict: 包含任务执行结果的字典
    """
    from .models import MatchingTask
    from apps.blanks.models import BlankModel
    
    try:
        # ==================== 第一步：任务初始化和验证 ====================
        # 从数据库获取匹配任务实例
        task = MatchingTask.objects.get(id=task_id)
        
        # 更新任务状态为处理中，设置初始进度
        task.status = 'processing'
        task.progress = 5
        task.current_step = '准备匹配环境...'
        task.save()
        
        # 验证目标鞋模文件是否存在
        shoe_file = task.shoe_model.file.path
        if not os.path.exists(shoe_file):
            raise FileNotFoundError(f"鞋模文件不存在: {shoe_file}")
        
        # ==================== 第二步：获取候选粗胚文件 ====================
        # 根据任务选择的类别筛选符合条件的粗胚文件
        candidates = BlankModel.objects.filter(
            categories__in=task.selected_categories.all(),
            is_active=True,        # 只选择激活的粗胚
            is_processed=True      # 只选择已处理的粗胚
        ).distinct()
        
        # 检查是否有候选文件
        if not candidates.exists():
            raise ValueError("没有找到符合条件的粗胚文件")
        
        # 更新任务进度，记录找到的候选数量
        task.progress = 10
        task.current_step = f'找到 {candidates.count()} 个候选粗胚...'
        task.save()
        
        # ==================== 第三步：创建临时工作目录 ====================
        # 生成唯一的临时目录ID，避免多任务冲突
        import uuid
        temp_id = uuid.uuid4().hex[:12]
        
        logger.info(f"匹配任务 {task.task_id}: 开始创建临时目录，temp_id={temp_id}")
        
        # 根据运行环境选择不同的临时目录路径
        if os.environ.get('DJANGO_ENVIRONMENT') == 'docker':
            # Docker环境：使用挂载的temp目录（./temp:/app/temp）
            temp_dir = f'/app/temp/match_{temp_id}'                    # 容器内路径
            host_temp_dir = f'/root/3dModMatch/webpage/temp/match_{temp_id}'  # 主机路径
            logger.info(f"Docker环境: 容器内路径={temp_dir}, 主机路径={host_temp_dir}")
        else:
            # 本地环境：使用系统临时目录
            temp_dir = f'/tmp/match_{temp_id}'
            host_temp_dir = temp_dir
            logger.info(f"本地环境: 使用路径={temp_dir}")
        
        # 定义子目录结构
        temp_path = Path(temp_dir)
        candidates_dir = temp_path / 'candidates'  # 候选文件目录
        output_dir = temp_path / 'output'          # 输出结果目录
        
        # 创建完整的目录结构
        logger.info(f"创建目录结构: {temp_path}")
        temp_path.mkdir(parents=True, exist_ok=True)
        candidates_dir.mkdir()
        output_dir.mkdir()
        logger.info(f"目录创建完成: candidates={candidates_dir}, output={output_dir}")
        
        try:
            # ==================== 第四步：复制候选文件到临时目录 ====================
            task.progress = 20
            task.current_step = '准备候选文件...'
            task.save()
            
            # 复制所有候选粗胚文件到临时目录，供匹配算法使用
            logger.info(f"开始复制 {candidates.count()} 个候选文件到 {candidates_dir}")
            copied_count = 0
            for candidate in candidates:
                if candidate.file and os.path.exists(candidate.file.path):
                    src_file = Path(candidate.file.path)
                    dst_file = candidates_dir / src_file.name
                    try:
                        shutil.copy2(src_file, dst_file)  # 复制文件并保持元数据
                        copied_count += 1
                        logger.debug(f"复制文件: {src_file.name} -> {dst_file}")
                    except Exception as e:
                        logger.error(f"复制文件失败: {src_file} -> {dst_file}, 错误: {e}")
                else:
                    logger.warning(f"跳过无效候选文件: {candidate.id}, file={candidate.file}")
            
            logger.info(f"文件复制完成: 成功复制 {copied_count}/{candidates.count()} 个文件")
            
            # 验证复制的文件数量，确保文件系统操作成功
            actual_files = list(candidates_dir.glob('*.3dm'))
            logger.info(f"验证: 候选目录中实际有 {len(actual_files)} 个.3dm文件")
            
            # ==================== 第五步：执行Hybrid匹配算法 ====================
            task.progress = 30
            task.current_step = '启动匹配算法...'
            task.save()
            
            # 导入Hybrid集成服务
            from utils.hybrid_integration import hybrid_service
            
            # 检查Hybrid系统是否可用，如果不可用则尝试构建C++模块
            if not hybrid_service.check_hybrid_system():
                # 尝试构建C++核心模块
                if not hybrid_service.build_cpp_core():
                    raise RuntimeError("Hybrid系统不可用，且C++模块构建失败")
            
            # 准备匹配算法参数，从任务配置中获取
            match_params = {
                'clearance': task.clearance,           # 间隙参数
                'threshold': task.threshold,           # 阈值参数
                'enable_scaling': task.enable_scaling, # 是否启用缩放
                'enable_multi_start': task.enable_multi_start,  # 是否启用多起点
                'max_scale': task.max_scale            # 最大缩放比例
            }
            
            # 根据运行环境选择正确的路径传递给Docker命令
            docker_candidates_dir = host_temp_dir + '/candidates' if os.environ.get('DJANGO_ENVIRONMENT') == 'docker' else str(candidates_dir)
            docker_output_dir = host_temp_dir + '/output' if os.environ.get('DJANGO_ENVIRONMENT') == 'docker' else str(output_dir)
            
            # 记录匹配算法执行参数
            logger.info(f"执行匹配算法:")
            logger.info(f"  - 目标文件: {shoe_file}")
            logger.info(f"  - 候选目录: {docker_candidates_dir}")
            logger.info(f"  - 输出目录: {docker_output_dir}")
            logger.info(f"  - 匹配参数: {match_params}")
            
            # 调用Hybrid服务执行实际的3D匹配算法
            result = hybrid_service.run_matching(
                target_file=shoe_file,
                candidates_dir=docker_candidates_dir,
                output_dir=docker_output_dir,
                params=match_params
            )
            
            # ==================== 第六步：处理匹配结果 ====================
            logger.info(f"匹配算法执行完成: success={result.get('success')}")
            if not result.get('success'):
                logger.error(f"匹配失败: {result.get('error')}")
            else:
                logger.info("匹配执行成功，开始解析结果")
                
                # 等待文件系统同步，确保输出文件已完全写入
                import time
                time.sleep(2)
                logger.info("等待文件系统同步完成")
                
                # 使用容器内的输出目录路径进行检查和解析
                # 因为我们在容器内运行，需要使用容器内的路径
                result_output_dir = str(output_dir)  # 使用容器内路径
                logger.info(f"使用输出目录进行解析: {result_output_dir}")
                
                # 检查输出目录状态，记录生成的文件
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
                
                # 解析匹配结果文件，提取匹配数据
                parse_result = hybrid_service.parse_results(result_output_dir)
                if parse_result['success']:
                    result['results'] = parse_result['results']    # 详细匹配结果
                    result['summary'] = parse_result['summary']    # 匹配摘要
                    logger.info("任务中结果解析成功")
                else:
                    logger.error(f"任务中结果解析失败: {parse_result['error']}")
                    result['success'] = False
                    result['error'] = f"匹配成功但结果解析失败: {parse_result['error']}"
            
            # ==================== 第七步：保存结果和更新任务状态 ====================
            if result['success']:
                # 处理匹配结果，更新任务进度
                task.progress = 90
                task.current_step = '处理匹配结果...'
                task.save()
                
                # 确保结果数据存在并保存到数据库
                if 'results' in result and 'summary' in result:
                    task.result_data = {'results': result['results']}  # 保存详细结果
                    task.summary_data = result['summary']              # 保存摘要数据
                    logger.info(f"成功保存匹配结果: {len(result['results'])} 个结果")
                else:
                    raise RuntimeError("匹配成功但缺少结果数据")
                
                # 标记任务为完成状态
                task.status = 'completed'
                task.progress = 100
                task.current_step = '匹配完成'
                task.completed_at = timezone.now()
                
                # 计算任务处理时间
                if task.started_at:
                    task.processing_time = (
                        task.completed_at - task.started_at
                    ).total_seconds()
                
                logger.info(f"Matching task {task.task_id} completed successfully")
                
                # # ==================== 第八步：触发热力图生成任务 ====================
                # # 异步触发热力图生成，不阻塞主任务完成
                # try:
                #     # 使用当前文件中定义的任务
                #     generate_heatmaps_task.delay(task.task_id, top_k=4)
                #     logger.info(f"已触发热力图生成任务: {task.task_id}")
                # except Exception as e:
                #     logger.error(f"触发热力图生成任务失败: {e}")
                
            else:
                # 匹配失败，更新任务状态
                task.status = 'failed'
                task.current_step = f'匹配失败: {result["error"]}'
                logger.error(f"Matching task {task.task_id} failed: {result['error']}")
        
            # 保存最终任务状态
            task.save()
            return {'success': task.status == 'completed', 'task_id': task.task_id}
        
        finally:
            # ==================== 第九步：清理临时文件 ====================
            # 只有在任务成功完成时才清理临时目录，失败时保留用于调试
            try:
                import time
                # 给文件系统一些时间确保所有写入操作完成
                time.sleep(3)
                
                # 检查任务是否成功完成
                task.refresh_from_db()
                should_cleanup = task.status == 'completed'
                
                if should_cleanup:
                    # 任务成功完成，清理临时目录
                    logger.info("任务成功完成，开始清理临时目录")
                    if 'temp_dir' in locals() and os.path.exists(temp_dir):
                        logger.info(f"清理容器内临时目录: {temp_dir}")
                        shutil.rmtree(temp_dir)
                    if os.environ.get('DJANGO_ENVIRONMENT') == 'docker' and 'host_temp_dir' in locals():
                        logger.info(f"清理主机临时目录: {host_temp_dir}")
                        subprocess.run(['rm', '-rf', host_temp_dir], check=False)
                else:
                    # 任务失败，保留临时目录用于调试
                    logger.info(f"任务状态为 {task.status}，保留临时目录用于调试")
                    if 'host_temp_dir' in locals():
                        logger.info(f"调试目录位置: {host_temp_dir}")
                        
            except Exception as e:
                logger.warning(f"清理临时目录失败: {e}")
        
    except MatchingTask.DoesNotExist:
        # 任务不存在异常处理
        logger.error(f"Matching task {task_id} does not exist")
        return {'success': False, 'error': 'Task not found'}
    except Exception as e:
        # 其他异常处理，更新任务状态为失败
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
    异步生成3D匹配结果热力图任务
    
    这个Celery任务负责为匹配结果生成可视化热力图：
    1. 验证匹配任务是否完成
    2. 准备热力图输出目录
    3. 为前K个最佳匹配结果生成热力图
    4. 使用Plotly生成交互式3D可视化
    
    Args:
        task_id: 匹配任务的唯一标识符
        top_k: 生成前K个结果的热力图，默认4个
        
    Returns:
        dict: 包含热力图生成结果的字典
    """
    # 直接在这里实现，避免参数传递问题
    from apps.matching.models import MatchingTask
    # from apps.matching.heatmap_tasks import generate_heatmap_locally  # 已删除
    from django.conf import settings
    from pathlib import Path
    import logging
    
    logger = logging.getLogger(__name__)
    
    # 热力图功能已被透明叠加视图取代
    logger.warning(f"generate_heatmaps_task is deprecated: task_id={task_id}")
    try:
        task = MatchingTask.objects.get(task_id=task_id)
        task.heatmap_status = 'failed'
        task.heatmap_data = {'error': '热力图功能已被透明叠加视图取代'}
        task.save()
    except Exception as e:
        logger.error(f"Error updating task status: {e}")
    return {'success': False, 'message': '热力图功能已被透明叠加视图取代'}
    
    # 以下代码已弃用 - 原热力图生成代码已移除
    # try:
        # ==================== 第一步：验证匹配任务状态 ====================
        # 获取匹配任务实例
#         task = MatchingTask.objects.get(task_id=task_id)
        
#         # 检查匹配任务是否已完成，只有完成的匹配才能生成热力图
#         if task.status != 'completed':
#             logger.warning(f"任务 {task_id} 未完成，无法生成热力图")
#             return {'success': False, 'message': '匹配任务未完成'}
        
#         # 获取匹配结果数据
#         results = task.result_data.get('results', [])
#         if not results:
#             return {'success': False, 'message': '没有匹配结果'}
        
#         # ==================== 第二步：初始化热力图生成状态 ====================
#         # 更新任务的热力图状态为生成中
#         task.heatmap_status = 'generating'
#         task.heatmap_data = {'progress': 0, 'message': '开始生成热力图...'}
#         task.save()
        
#         # ==================== 第三步：准备热力图输出目录 ====================
#         # 在媒体根目录下创建热力图专用目录
#         heatmap_dir = Path(settings.MEDIA_ROOT) / 'heatmaps' / task_id
#         heatmap_dir.mkdir(parents=True, exist_ok=True)
        
#         # 获取目标鞋模文件路径，用于热力图生成
#         target_path = Path(settings.MEDIA_ROOT) / task.shoe_model.file.name
        
#         # ==================== 第四步：生成热力图 ====================
#         # 初始化热力图生成结果列表
#         generated_heatmaps = []
#         # 计算实际需要生成的热力图数量（不超过结果总数）
#         total_to_generate = min(top_k, len(results))
        
#         # 遍历前K个最佳匹配结果，为每个结果生成热力图
#         for i, result in enumerate(results[:total_to_generate]):
#             try:
#                 # ==================== 第五步：更新热力图生成进度 ====================
#                 # 计算当前进度百分比
#                 progress = int((i / total_to_generate) * 100)
#                 # 更新任务状态，显示当前生成进度
#                 task.heatmap_data = {
#                     'progress': progress,
#                     'message': f'正在生成第 {i+1}/{total_to_generate} 个热力图...'
#                 }
#                 task.save()
                
#                 # ==================== 第六步：处理粗胚文件路径 ====================
#                 # 获取粗胚文件路径（支持多种路径字段名）
#                 blank_path = result.get('blank_path') or result.get('path')
#                 if not blank_path:
#                     continue
                    
#                 # 处理Docker环境中的路径映射问题
#                 if '/app/candidates/' in str(blank_path):
#                     blank_name = Path(blank_path).name
#                     # 在Celery容器中查找实际的粗胚文件位置
#                     possible_paths = [
#                         Path('/app/media/blanks/2025/09') / blank_name,  # 2025年9月上传的文件
#                         Path('/app/media/blanks/2025/01') / blank_name,  # 2025年1月上传的文件
#                         Path('/app/media/blanks') / blank_name,         # 默认位置
#                     ]
#                     blank_path = None
#                     # 尝试在可能的路径中找到文件
#                     for p in possible_paths:
#                         if p.exists():
#                             blank_path = p
#                             break
#                     if not blank_path:
#                         logger.warning(f"找不到粗胚文件: {blank_name}")
#                         continue
                
#                 # ==================== 第七步：准备热力图文件 ====================
#                 # 生成热力图文件名和路径
#                 blank_name = result.get('blank_name', f'result_{i+1}')
#                 # 清理文件名中的.3dm后缀，避免重复
#                 if blank_name.endswith('.3dm'):
#                     blank_name = blank_name[:-4]
#                 # 生成格式化的热力图文件名：01_result1_heatmap.html
#                 heatmap_filename = f"{i+1:02d}_{blank_name}_heatmap.html"
#                 heatmap_path = heatmap_dir / heatmap_filename
                
#                 # 记录热力图生成开始
#                 logger.info(f"生成热力图: {heatmap_filename}")
#                 success = False
                
#                 try:
#                     import subprocess
#                     import json
                    
#                     # ==================== 第八步：生成热力图可视化脚本 ====================
#                     # 创建临时Python脚本来生成交互式3D热力图
#                     # 使用Plotly和rhino3dm库处理3D模型数据
#                     script_content = f'''
# import sys
# import json
# import numpy as np
# import plotly.graph_objects as go
# from pathlib import Path
# import rhino3dm

# def generate_simple_heatmap():
#     """生成3D匹配结果热力图"""
#     target_path = "{target_path}"      # 目标鞋模文件路径
#     blank_path = "{blank_path}"        # 候选粗胚文件路径
#     output_path = "{heatmap_path}"     # 输出热力图文件路径
    
#     try:
#         # ==================== 加载3DM文件 ====================
#         # 使用rhino3dm库加载目标鞋模和候选粗胚的3DM文件
#         target_model = rhino3dm.File3dm.Read(target_path)
#         blank_model = rhino3dm.File3dm.Read(blank_path)
        
#         if not target_model or not blank_model:
#             print("无法加载3DM文件")
#             return False
            
#         # ==================== 提取网格数据 ====================
#         # 从3DM文件中提取第一个网格对象（假设每个文件只有一个主要网格）
#         target_mesh = None
#         blank_mesh = None
        
#         # 遍历目标模型中的所有对象，找到网格类型
#         for obj in target_model.Objects:
#             if obj.Geometry.ObjectType == rhino3dm.ObjectType.Mesh:
#                 target_mesh = obj.Geometry
#                 break
                
#         # 遍历粗胚模型中的所有对象，找到网格类型
#         for obj in blank_model.Objects:
#             if obj.Geometry.ObjectType == rhino3dm.ObjectType.Mesh:
#                 blank_mesh = obj.Geometry
#                 break
                
#         if not target_mesh or not blank_mesh:
#             print("未找到网格数据")
#             return False
            
#         # ==================== 提取几何数据 ====================
#         # 获取网格的顶点坐标（X, Y, Z）
#         target_vertices = [[v.X, v.Y, v.Z] for v in target_mesh.Vertices]
#         blank_vertices = [[v.X, v.Y, v.Z] for v in blank_mesh.Vertices]
        
#         # 获取网格的面索引（三角形面的顶点索引）
#         target_faces = [[f.A, f.B, f.C] for f in target_mesh.Faces]
#         blank_faces = [[f.A, f.B, f.C] for f in blank_mesh.Faces]
        
#         # ==================== 计算热力图数据 ====================
#         # 创建基于高度的简单热力图（实际应用中应该使用匹配算法计算的间隙数据）
#         blank_z_values = [v[2] for v in blank_vertices]  # 提取Z坐标（高度）
#         min_z = min(blank_z_values)                      # 最小高度
#         max_z = max(blank_z_values)                      # 最大高度
#         # 将高度值归一化到0-10范围，用于颜色映射
#         normalized_z = [(z - min_z) / (max_z - min_z) * 10 for z in blank_z_values]
        
#         # ==================== 创建Plotly 3D图形 ====================
#         fig = go.Figure()
        
#         # 添加目标鞋模网格（半透明灰色，作为参考）
#         fig.add_trace(go.Mesh3d(
#             x=[v[0] for v in target_vertices],           # X坐标
#             y=[v[1] for v in target_vertices],           # Y坐标
#             z=[v[2] for v in target_vertices],           # Z坐标
#             i=[f[0] for f in target_faces],              # 面的第一个顶点索引
#             j=[f[1] for f in target_faces],              # 面的第二个顶点索引
#             k=[f[2] for f in target_faces],              # 面的第三个顶点索引
#             name='目标鞋楦',                              # 图例名称
#             color='lightgray',                           # 固定颜色
#             opacity=0.3                                  # 透明度
#         ))
        
#         # 添加候选粗胚网格（带热力图颜色映射）
#         fig.add_trace(go.Mesh3d(
#             x=[v[0] for v in blank_vertices],           # X坐标
#             y=[v[1] for v in blank_vertices],           # Y坐标
#             z=[v[2] for v in blank_vertices],           # Z坐标
#             i=[f[0] for f in blank_faces],              # 面的第一个顶点索引
#             j=[f[1] for f in blank_faces],              # 面的第二个顶点索引
#             k=[f[2] for f in blank_faces],              # 面的第三个顶点索引
#             intensity=normalized_z,                     # 颜色强度数据（基于高度）
#             colorscale='RdYlGn',                        # 红-黄-绿颜色映射
#             cmin=0,                                     # 颜色映射最小值
#             cmax=10,                                    # 颜色映射最大值
#             colorbar=dict(title='间隙 (mm)'),           # 颜色条标题
#             name='匹配粗胚',                              # 图例名称
#             opacity=0.9                                 # 透明度
#         ))
        
#         # ==================== 配置图形布局 ====================
#         # 设置3D图形的标题、坐标轴标签和尺寸
#         fig.update_layout(
#             title='间隙热力图',                           # 图形标题
#             scene=dict(
#                 xaxis_title='X (mm)',                   # X轴标签
#                 yaxis_title='Y (mm)',                   # Y轴标签
#                 zaxis_title='Z (mm)',                   # Z轴标签
#                 aspectmode='data'                       # 保持数据比例
#             ),
#             width=1400,                                 # 图形宽度
#             height=900                                  # 图形高度
#         )
        
#         # ==================== 保存HTML文件 ====================
#         # 确保输出目录存在，然后保存交互式HTML热力图
#         Path(output_path).parent.mkdir(parents=True, exist_ok=True)
#         fig.write_html(output_path)
#         print(f"热力图已保存: {{output_path}}")
#         return True
        
#     except Exception as e:
#         print(f"生成热力图失败: {{e}}")
#         return False

# if __name__ == "__main__":
#     success = generate_simple_heatmap()
#     sys.exit(0 if success else 1)
# '''
                    
#                     # ==================== 第九步：执行热力图生成脚本 ====================
#                     # 将脚本内容保存为临时Python文件
#                     script_path = heatmap_dir / f'temp_heatmap_{i}.py'
#                     script_path.write_text(script_content)
                    
#                     # 在子进程中执行热力图生成脚本，设置60秒超时
#                     result_proc = subprocess.run([
#                         'python3', str(script_path)
#                     ], capture_output=True, text=True, timeout=60)
                    
#                     # 检查脚本执行是否成功且输出文件存在
#                     success = result_proc.returncode == 0 and heatmap_path.exists()
                    
#                     # 清理临时脚本文件
#                     if script_path.exists():
#                         script_path.unlink()
                        
#                     if not success:
#                         logger.error(f"热力图生成失败: {result_proc.stderr}")
                        
#                 except Exception as e:
#                     logger.error(f"热力图生成异常: {e}")
#                     success = False
                
#                 # ==================== 第十步：记录成功生成的热力图 ====================
#                 # 如果热力图生成成功，记录到结果列表中
#                 if success and heatmap_path.exists():
#                     relative_path = f'heatmaps/{task_id}/{heatmap_filename}'
#                     generated_heatmaps.append({
#                         'index': i,                                    # 结果索引
#                         'blank_name': blank_name,                     # 粗胚名称
#                         'filename': heatmap_filename,                 # 文件名
#                         'path': relative_path,                        # 相对路径
#                         'url': f'/media/{relative_path}'              # 访问URL
#                     })
#                     logger.info(f"热力图生成成功: {heatmap_filename}")
                    
#             except Exception as e:
#                 # 单个热力图生成失败，记录错误但继续处理其他结果
#                 logger.error(f"生成热力图 {i+1} 时出错: {e}")
#                 continue
        
#         # ==================== 第十一步：更新任务最终状态 ====================
#         # 根据热力图生成结果更新任务状态
#         if generated_heatmaps:
#             # 热力图生成成功，更新任务状态为完成
#             task.heatmap_status = 'completed'
#             task.heatmap_data = {
#                 'progress': 100,                                           # 进度100%
#                 'message': f'成功生成 {len(generated_heatmaps)} 个热力图',  # 成功消息
#                 'heatmaps': generated_heatmaps                             # 热力图列表
#             }
#             task.heatmap_dir = str(heatmap_dir)                            # 保存热力图目录路径
#             task.save()
#             return {'success': True, 'heatmaps': generated_heatmaps}
#         else:
#             # 没有成功生成任何热力图，标记为失败
#             task.heatmap_status = 'failed'
#             task.heatmap_data = {'error': '无法生成热力图'}
#             task.save()
#             return {'success': False, 'message': '热力图生成失败'}
            
#     except Exception as e:
#         # ==================== 异常处理 ====================
#         # 捕获所有未处理的异常，记录错误并返回失败状态
#         logger.error(f"热力图生成任务失败: {e}")
#         return {'success': False, 'error': str(e)}


