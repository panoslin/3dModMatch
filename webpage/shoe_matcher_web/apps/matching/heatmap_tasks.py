"""
热力图生成任务
"""

import os
import json
import time
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.matching.models import MatchingTask
from apps.shoes.models import ShoeModel

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def generate_heatmaps_task(self, task_id: str, top_k: int = 4):
    """
    异步生成热力图任务
    
    Args:
        task_id: 匹配任务ID
        top_k: 生成前K个结果的热力图，默认4个
    """
    try:
        # 获取任务
        task = MatchingTask.objects.get(task_id=task_id)
        
        # 检查任务状态
        if task.status != 'completed':
            logger.warning(f"任务 {task_id} 未完成，无法生成热力图")
            return {
                'success': False,
                'message': '匹配任务未完成'
            }
        
        # 检查是否有结果
        if not task.result_data or 'results' not in task.result_data:
            logger.warning(f"任务 {task_id} 没有匹配结果")
            return {
                'success': False,
                'message': '没有匹配结果'
            }
        
        results = task.result_data['results']
        if not results:
            logger.warning(f"任务 {task_id} 结果为空")
            return {
                'success': False,
                'message': '匹配结果为空'
            }
        
        # 更新状态为生成中
        task.heatmap_status = 'generating'
        task.heatmap_data = {'progress': 0, 'message': '开始生成热力图...'}
        task.save()
        
        # 准备输出目录
        heatmap_dir = Path(settings.MEDIA_ROOT) / 'heatmaps' / task_id
        heatmap_dir.mkdir(parents=True, exist_ok=True)
        
        # 获取鞋模文件路径
        shoe_model = task.shoe_model
        target_path = Path(settings.MEDIA_ROOT) / shoe_model.file.name
        
        # 生成前K个结果的热力图
        generated_heatmaps = []
        total_to_generate = min(top_k, len(results))
        
        for i, result in enumerate(results[:total_to_generate]):
            try:
                # 更新进度
                progress = int((i / total_to_generate) * 100)
                task.heatmap_data = {
                    'progress': progress,
                    'message': f'正在生成第 {i+1}/{total_to_generate} 个热力图...',
                    'current': i + 1,
                    'total': total_to_generate
                }
                task.save()
                
                # 获取粗胚文件路径
                blank_path = result.get('blank_path') or result.get('path')
                if not blank_path:
                    logger.warning(f"结果 {i} 缺少文件路径")
                    continue
                
                # 处理路径映射（容器内路径转换为实际路径）
                if '/app/candidates/' in str(blank_path):
                    # 从容器路径转换为媒体路径
                    blank_name = Path(blank_path).name
                    # 在媒体目录中查找文件
                    possible_paths = [
                        Path(settings.MEDIA_ROOT) / 'blanks' / blank_name,
                        Path(settings.MEDIA_ROOT) / 'blanks' / '2025' / '09' / blank_name,
                        Path('/root/3dModMatch/candidates') / blank_name,  # 原始候选目录
                    ]
                    blank_path = None
                    for p in possible_paths:
                        if p.exists():
                            blank_path = p
                            break
                    
                    if not blank_path:
                        logger.warning(f"找不到粗胚文件: {blank_name}")
                        continue
                elif not Path(blank_path).is_absolute():
                    blank_path = Path(settings.MEDIA_ROOT) / blank_path
                
                # 生成热力图文件名
                blank_name = result.get('blank_name', f'result_{i+1}')
                heatmap_filename = f"{i+1:02d}_{blank_name}_heatmap.html"
                heatmap_path = heatmap_dir / heatmap_filename
                
                # 使用本地函数生成热力图（与 heatmap_worker.py 相同的逻辑）
                logger.info(f"生成热力图 {i+1}/{total_to_generate}: {heatmap_filename}")
                
                # 调用本地生成函数
                success = generate_heatmap_locally(
                    target_path=str(target_path),
                    blank_path=str(blank_path),
                    output_path=str(heatmap_path),
                    clearance_data=result
                )
                
                if success and heatmap_path.exists():
                    # 热力图生成成功
                    relative_path = f'heatmaps/{task_id}/{heatmap_filename}'
                    generated_heatmaps.append({
                        'index': i,
                        'blank_name': blank_name,
                        'filename': heatmap_filename,
                        'path': relative_path,
                        'url': f'/media/{relative_path}',
                        'clearance_data': {
                            'min_clearance': result.get('min_clearance', 0),
                            'p15_clearance': result.get('p15_clearance', 0),
                            'inside_ratio': result.get('inside_ratio', 0)
                        }
                    })
                    logger.info(f"热力图生成成功: {heatmap_filename}")
                else:
                    logger.error(f"热力图生成失败")
                
            except Exception as e:
                logger.error(f"生成热力图 {i+1} 时出错: {str(e)}")
                continue
        
        # 更新任务状态
        if generated_heatmaps:
            task.heatmap_status = 'completed'
            task.heatmap_data = {
                'progress': 100,
                'message': f'成功生成 {len(generated_heatmaps)} 个热力图',
                'heatmaps': generated_heatmaps,
                'completed_at': timezone.now().isoformat()
            }
            task.heatmap_dir = str(heatmap_dir)
            task.save()
            
            logger.info(f"任务 {task_id} 热力图生成完成，共生成 {len(generated_heatmaps)} 个")
            
            return {
                'success': True,
                'message': f'成功生成 {len(generated_heatmaps)} 个热力图',
                'heatmaps': generated_heatmaps
            }
        else:
            task.heatmap_status = 'failed'
            task.heatmap_data = {
                'progress': 0,
                'message': '热力图生成失败',
                'error': '无法生成任何热力图'
            }
            task.save()
            
            logger.error(f"任务 {task_id} 热力图生成失败")
            
            return {
                'success': False,
                'message': '热力图生成失败'
            }
            
    except MatchingTask.DoesNotExist:
        logger.error(f"任务 {task_id} 不存在")
        return {
            'success': False,
            'message': '匹配任务不存在'
        }
    except Exception as e:
        logger.error(f"生成热力图时发生错误: {str(e)}")
        
        # 更新任务状态为失败
        try:
            task = MatchingTask.objects.get(task_id=task_id)
            task.heatmap_status = 'failed'
            task.heatmap_data = {
                'progress': 0,
                'message': '热力图生成失败',
                'error': str(e)
            }
            task.save()
        except:
            pass
        
        return {
            'success': False,
            'message': f'生成热力图时发生错误: {str(e)}'
        }


def generate_heatmap_locally(
    target_path: str,
    blank_path: str,
    output_path: str,
    clearance_data: Dict
) -> bool:
    """
    直接在本地生成热力图，使用与 heatmap_worker.py 相同的逻辑
    """
    try:
        import numpy as np
        import trimesh
        import plotly.graph_objects as go
        from pathlib import Path
        import sys
        import os
        
        # 添加hybrid路径以使用3DM加载器
        sys.path.insert(0, '/root/3dModMatch/hybrid/python')
        
        logger.info(f"生成热力图: {output_path}")
        logger.info(f"  目标: {target_path}")
        logger.info(f"  粗胚: {blank_path}")
        
        # 使用hybrid的加载器加载3DM文件
        try:
            from hybrid_matcher import load_mesh_enhanced
            # 加载并获取顶点和面
            V_target, F_target = load_mesh_enhanced(target_path, preprocess=False)
            V_cand, F_cand = load_mesh_enhanced(blank_path, preprocess=False)
            
            # 创建trimesh对象用于计算
            target_mesh = trimesh.Trimesh(vertices=V_target, faces=F_target)
            blank_mesh = trimesh.Trimesh(vertices=V_cand, faces=F_cand)
            
        except ImportError:
            # 如果无法导入hybrid，尝试直接加载（对于非3DM格式）
            logger.warning("无法导入hybrid加载器，尝试直接加载")
            target_mesh = trimesh.load(target_path)
            blank_mesh = trimesh.load(blank_path)
            V_target = np.array(target_mesh.vertices)
            F_target = np.array(target_mesh.faces)
            V_cand = np.array(blank_mesh.vertices)
            F_cand = np.array(blank_mesh.faces)
        
        # 应用变换（如果有）
        transform = clearance_data.get('transform')
        if transform:
            # 转换为4x4矩阵
            T = np.array(transform)
            if T.shape == (16,):
                T = T.reshape(4, 4)
            elif T.shape == (4, 4):
                pass
            else:
                logger.warning(f"变换矩阵格式不正确: {T.shape}")
                T = np.eye(4)
            
            blank_mesh.apply_transform(T)
            logger.info(f"  应用变换矩阵")
        
        # 应用缩放（如果有）
        scale = clearance_data.get('scale_used', 1.0)
        if scale != 1.0:
            blank_mesh.apply_scale(scale)
            logger.info(f"  应用缩放: {scale}")
        
        # 如果还没有顶点和面数据，获取它们
        if 'V_target' not in locals():
            V_target = np.array(target_mesh.vertices)
            F_target = np.array(target_mesh.faces)
            V_cand = np.array(blank_mesh.vertices)
            F_cand = np.array(blank_mesh.faces)
        
        # 计算间隙（与 heatmap_worker.py 相同）
        logger.info(f"  计算 {len(V_cand)} 个顶点的间隙...")
        _, clearances, _ = target_mesh.nearest.on_surface(V_cand)
        
        logger.info(f"  间隙范围: {clearances.min():.3f}mm - {clearances.max():.3f}mm")
        
        # 创建 Plotly 图形（与 heatmap_worker.py 相同的样式）
        fig = go.Figure()
        
        # 添加目标网格（实心，浅色对比）
        fig.add_trace(go.Mesh3d(
            x=V_target[:, 0],
            y=V_target[:, 1],
            z=V_target[:, 2],
            i=F_target[:, 0],
            j=F_target[:, 1],
            k=F_target[:, 2],
            name='Target',
            color='lightgray',
            opacity=1.0  # 实心，不透明
        ))
        
        # 添加候选网格，带基于间隙的颜色（实心）
        fig.add_trace(go.Mesh3d(
            x=V_cand[:, 0],
            y=V_cand[:, 1],
            z=V_cand[:, 2],
            i=F_cand[:, 0],
            j=F_cand[:, 1],
            k=F_cand[:, 2],
            intensity=clearances,  # 使用顶点间隙值进行着色
            colorscale='RdYlGn',  # 与 heatmap_worker.py 相同的颜色方案
            cmin=0,
            cmax=10,
            colorbar=dict(title='Clearance (mm)'),
            opacity=1.0,  # 实心，不透明以获得更好的可见性
            name='Candidate Clearance',
            showscale=True
        ))
        
        # 更新布局（与 heatmap_worker.py 相同）
        min_clearance = clearance_data.get("min_clearance", clearances.min())
        fig.update_layout(
            title=f'Clearance Heatmap - Min: {min_clearance:.2f}mm',
            scene=dict(
                xaxis_title='X (mm)',
                yaxis_title='Y (mm)',
                zaxis_title='Z (mm)',
                aspectmode='data'
            ),
            width=1400,
            height=900
        )
        
        # 确保输出目录存在
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # 保存HTML
        fig.write_html(output_path)
        logger.info(f"  热力图已生成: {output_path}")
        
        return True
        
    except Exception as e:
        logger.error(f"生成热力图失败: {e}")
        import traceback
        traceback.print_exc()
        return False
