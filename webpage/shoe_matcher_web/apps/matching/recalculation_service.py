"""
匹配指标重新计算服务

用于在用户手动调整鞋模位置/角度后，重新计算准确的匹配指标
"""

import logging
import numpy as np
from pathlib import Path
from django.conf import settings

logger = logging.getLogger(__name__)


def recalculate_metrics_with_transform(task, result_index, target_transform, candidate_transform=None):
    """
    基于新的变换矩阵重新计算匹配指标
    
    Args:
        task: MatchingTask对象
        result_index: 结果索引
        target_transform: 鞋模的4x4变换矩阵（二维列表）
        candidate_transform: 粗胚的4x4变换矩阵（二维列表，可选）
        
    Returns:
        dict: 重新计算的指标
    """
    try:
        logger.info(f"开始重新计算指标: 任务{task.task_id}, 结果{result_index}")
        
        # 1. 获取结果数据
        if not task.result_data or 'results' not in task.result_data:
            raise ValueError("任务没有结果数据")
        
        results = task.result_data['results']
        if result_index < 0 or result_index >= len(results):
            raise ValueError(f"结果索引超出范围: {result_index}")
        
        result = results[result_index]
        
        # 2. 加载鞋模和粗胚的3D文件
        shoe_vertices, shoe_faces = load_shoe_model(task)
        blank_vertices, blank_faces = load_blank_model(result)
        
        logger.info(f"模型已加载: 鞋模{len(shoe_vertices)}顶点, 粗胚{len(blank_vertices)}顶点")
        
        # 3. 应用变换矩阵到两个模型
        target_matrix = np.array(target_transform, dtype=np.float64)
        transformed_shoe_vertices = apply_transform_to_vertices(shoe_vertices, target_matrix)
        
        # 同时应用粗胚的变换（如果提供）
        if candidate_transform:
            candidate_matrix = np.array(candidate_transform, dtype=np.float64)
            transformed_blank_vertices = apply_transform_to_vertices(blank_vertices, candidate_matrix)
            logger.info("已应用粗胚变换矩阵")
        else:
            transformed_blank_vertices = blank_vertices
            logger.info("粗胚使用原始顶点（未变换）")
        
        # 记录变换后的范围
        blank_min = transformed_blank_vertices.min(axis=0)
        blank_max = transformed_blank_vertices.max(axis=0)
        blank_center = transformed_blank_vertices.mean(axis=0)
        logger.info(f"粗胚范围: 中心={blank_center}, min={blank_min}, max={blank_max}")
        
        logger.info(f"变换已应用，检查鞋模和粗胚的位置关系...")
        
        # 检查是否有重叠（快速检查）
        shoe_min = transformed_shoe_vertices.min(axis=0)
        shoe_max = transformed_shoe_vertices.max(axis=0)
        shoe_center = transformed_shoe_vertices.mean(axis=0)
        
        logger.info(f"鞋模范围: 中心={shoe_center}, min={shoe_min}, max={shoe_max}")
        
        overlap_x = not (shoe_max[0] < blank_min[0] or shoe_min[0] > blank_max[0])
        overlap_y = not (shoe_max[1] < blank_min[1] or shoe_min[1] > blank_max[1])
        overlap_z = not (shoe_max[2] < blank_min[2] or shoe_min[2] > blank_max[2])
        
        if not (overlap_x and overlap_y and overlap_z):
            logger.warning(f"⚠️ 鞋模和粗胚可能没有重叠！")
            logger.warning(f"   鞋模范围: [{shoe_min}, {shoe_max}]")
            logger.warning(f"   粗胚范围: [{blank_min}, {blank_max}]")
        else:
            logger.info(f"✓ 鞋模和粗胚有重叠，中心距离: {np.linalg.norm(shoe_center - blank_center):.2f}mm")
        
        # 4. 重新计算匹配指标
        new_metrics = compute_metrics(
            transformed_shoe_vertices, shoe_faces,
            transformed_blank_vertices, blank_faces,
            clearance_threshold=task.clearance
        )
        
        logger.info(f"指标重新计算完成: {new_metrics}")
        
        return new_metrics
        
    except Exception as e:
        logger.error(f"重新计算指标失败: {e}")
        import traceback
        traceback.print_exc()
        raise


def load_shoe_model(task):
    """
    加载鞋模的顶点和面数据
    """
    try:
        import rhino3dm
        
        # 获取鞋模文件路径
        shoe_file_path = task.shoe_model.file.path
        
        if not Path(shoe_file_path).exists():
            # 尝试转换后的文件
            converted_path = Path(str(shoe_file_path).replace('.stl', '_converted.3dm'))
            if converted_path.exists():
                shoe_file_path = str(converted_path)
            else:
                raise FileNotFoundError(f"鞋模文件不存在: {shoe_file_path}")
        
        logger.info(f"加载鞋模文件: {shoe_file_path}")
        
        # 读取3DM文件
        file_3dm = rhino3dm.File3dm.Read(str(shoe_file_path))
        
        # 提取第一个网格
        for obj in file_3dm.Objects:
            geom = obj.Geometry
            if isinstance(geom, rhino3dm.Mesh):
                # 提取顶点
                vertices = np.array([[v.X, v.Y, v.Z] for v in geom.Vertices], dtype=np.float64)
                
                # 提取面
                faces = []
                for i in range(geom.Faces.Count):
                    face = geom.Faces[i]
                    # 检查是否是四边形（通过检查D索引）
                    if face[3] != face[2]:  # 四边形
                        # 四边形分解为两个三角形
                        faces.append([face[0], face[1], face[2]])
                        faces.append([face[0], face[2], face[3]])
                    else:  # 三角形
                        faces.append([face[0], face[1], face[2]])
                
                faces = np.array(faces, dtype=np.int32)
                
                logger.info(f"鞋模已加载: {len(vertices)}顶点, {len(faces)}面")
                return vertices, faces
        
        raise ValueError("鞋模文件中没有找到网格数据")
        
    except Exception as e:
        logger.error(f"加载鞋模失败: {e}")
        raise


def load_blank_model(result):
    """
    加载粗胚的顶点和面数据
    """
    try:
        import rhino3dm
        
        # 获取粗胚文件路径
        blank_path = result.get('blank_path', result.get('path', ''))
        blank_name = result.get('blank_name', '')
        
        if not blank_path:
            raise ValueError("结果中没有粗胚文件路径")
        
        logger.info(f"原始粗胚路径: {blank_path}")
        
        # 转换容器内路径到主机路径
        if blank_path.startswith('/app/candidates/'):
            # Docker容器内的路径 -> 主机路径
            # /app/candidates/xxx.3dm -> /root/3dModMatch/webpage/temp/match_xxx/candidates/xxx.3dm
            # 但这个路径可能已被清理，需要从blanks目录查找
            filename = Path(blank_path).name
            
            # 尝试从blanks目录查找
            from apps.blanks.models import BlankModel
            try:
                blank = BlankModel.objects.filter(file__icontains=filename.replace('.3dm', '')).first()
                if blank and blank.file:
                    blank_path = blank.file.path
                    logger.info(f"从BlankModel找到文件: {blank_path}")
            except Exception as e:
                logger.warning(f"从数据库查找失败: {e}")
        
        elif blank_path.startswith('/app/'):
            blank_path = blank_path.replace('/app/', str(Path(settings.MEDIA_ROOT).parent) + '/')
        
        # 如果路径仍然不存在，尝试通过名称搜索
        if not Path(blank_path).exists():
            logger.warning(f"路径不存在: {blank_path}, 尝试搜索...")
            
            # 搜索可能的目录
            search_dirs = [
                Path(settings.MEDIA_ROOT) / 'blanks',
                Path(settings.MEDIA_ROOT).parent / 'temp',
            ]
            
            filename_base = blank_name.replace('.3dm', '') if blank_name else Path(blank_path).stem
            
            for search_dir in search_dirs:
                if search_dir.exists():
                    # 递归搜索
                    for found_file in search_dir.rglob(f"*{filename_base}*.3dm"):
                        logger.info(f"找到文件: {found_file}")
                        blank_path = str(found_file)
                        break
                    if Path(blank_path).exists():
                        break
        
        if not Path(blank_path).exists():
            raise FileNotFoundError(f"粗胚文件不存在: {blank_path} (原始: {result.get('blank_path')})")
        
        logger.info(f"加载粗胚文件: {blank_path}")
        
        # 读取3DM文件
        file_3dm = rhino3dm.File3dm.Read(str(blank_path))
        
        # 提取第一个网格
        for obj in file_3dm.Objects:
            geom = obj.Geometry
            if isinstance(geom, rhino3dm.Mesh):
                # 提取顶点
                vertices = np.array([[v.X, v.Y, v.Z] for v in geom.Vertices], dtype=np.float64)
                
                # 提取面
                faces = []
                for i in range(geom.Faces.Count):
                    face = geom.Faces[i]
                    # 检查是否是四边形
                    if face[3] != face[2]:  # 四边形
                        faces.append([face[0], face[1], face[2]])
                        faces.append([face[0], face[2], face[3]])
                    else:  # 三角形
                        faces.append([face[0], face[1], face[2]])
                
                faces = np.array(faces, dtype=np.int32)
                
                logger.info(f"粗胚已加载: {len(vertices)}顶点, {len(faces)}面")
                return vertices, faces
        
        raise ValueError("粗胚文件中没有找到网格数据")
        
    except Exception as e:
        logger.error(f"加载粗胚失败: {e}")
        raise


def apply_transform_to_vertices(vertices, transform_matrix):
    """
    应用4x4变换矩阵到顶点
    
    Args:
        vertices: Nx3 numpy数组
        transform_matrix: 4x4 numpy数组
        
    Returns:
        transformed_vertices: Nx3 numpy数组
    """
    logger.info(f"应用变换: 顶点数={len(vertices)}")
    logger.info(f"变换矩阵:\n{transform_matrix}")
    
    # 计算变换前的范围
    pre_min = vertices.min(axis=0)
    pre_max = vertices.max(axis=0)
    pre_center = vertices.mean(axis=0)
    logger.info(f"变换前: 中心={pre_center}, 范围=[{pre_min}, {pre_max}]")
    
    # 转换为齐次坐标（Nx4）
    ones = np.ones((vertices.shape[0], 1), dtype=np.float64)
    homogeneous = np.hstack([vertices, ones])
    
    # 应用变换矩阵（注意：矩阵乘法）
    transformed_homogeneous = homogeneous @ transform_matrix.T
    
    # 转换回3D坐标
    transformed_vertices = transformed_homogeneous[:, :3]
    
    # 计算变换后的范围
    post_min = transformed_vertices.min(axis=0)
    post_max = transformed_vertices.max(axis=0)
    post_center = transformed_vertices.mean(axis=0)
    logger.info(f"变换后: 中心={post_center}, 范围=[{post_min}, {post_max}]")
    
    return transformed_vertices


def compute_metrics(shoe_vertices, shoe_faces, blank_vertices, blank_faces, clearance_threshold=2.0):
    """
    计算匹配指标（完全按照hybrid matcher的方式）
    
    Args:
        shoe_vertices: 鞋模顶点（已变换）
        shoe_faces: 鞋模面
        blank_vertices: 粗胚顶点（已变换）
        blank_faces: 粗胚面
        clearance_threshold: 间隙阈值
        
    Returns:
        dict: 匹配指标
    """
    try:
        # 导入hybrid matcher的函数（而不是直接调用cppcore）
        import sys
        from pathlib import Path
        
        # 添加hybrid Python路径
        hybrid_python_path = Path('/root/3dModMatch/hybrid/python')
        if str(hybrid_python_path) not in sys.path:
            sys.path.insert(0, str(hybrid_python_path))
        
        from hybrid_matcher import compute_detailed_clearance_metrics
        
        logger.info("开始计算匹配指标（使用hybrid matcher函数）...")
        logger.info(f"鞋模: {len(shoe_vertices)}顶点, {len(shoe_faces)}面")
        logger.info(f"粗胚: {len(blank_vertices)}顶点, {len(blank_faces)}面")
        
        # 确保数据类型正确
        Vt = shoe_vertices.astype(np.float64)
        Ft = shoe_faces.astype(np.int32)
        Vc = blank_vertices.astype(np.float64)
        Fc = blank_faces.astype(np.int32)
        
        # 调用hybrid matcher的函数（use_vertices=False使用采样，更快）
        logger.info(f"调用compute_detailed_clearance_metrics:")
        logger.info(f"  Vt(鞋模): shape={Vt.shape}, 中心={Vt.mean(axis=0)}")
        logger.info(f"  Vc(粗胚): shape={Vc.shape}, 中心={Vc.mean(axis=0)}")
        
        clearance_result = compute_detailed_clearance_metrics(
            Vt, Ft, Vc, Fc,
            samples=120000,
            use_vertices=False  # 使用采样而不是全部顶点
        )
        
        logger.info(f"✓ 间隙计算完成")
        logger.info(f"  inside_ratio: {clearance_result.get('inside_ratio', 0):.3f}")
        logger.info(f"  min_clearance: {clearance_result.get('min_clearance', 0):.2f}mm")
        logger.info(f"  p01_clearance: {clearance_result.get('p01_clearance', 0):.2f}mm")
        logger.info(f"  p05_clearance: {clearance_result.get('p05_clearance', 0):.2f}mm")
        logger.info(f"  p10_clearance: {clearance_result.get('p10_clearance', 0):.2f}mm")
        logger.info(f"  p15_clearance: {clearance_result.get('p15_clearance', 0):.2f}mm")
        logger.info(f"  p20_clearance: {clearance_result.get('p20_clearance', 0):.2f}mm")
        logger.info(f"  mean_clearance: {clearance_result.get('mean_clearance', 0):.2f}mm")
        
        # 2. 计算Chamfer距离（采样点云）
        logger.info("计算Chamfer距离...")
        chamfer_distance = compute_chamfer_distance(
            shoe_vertices, blank_vertices,
            sample_size=20000
        )
        
        # 3. 组装指标
        metrics = {
            'chamfer': float(chamfer_distance),
            'min_clearance': float(clearance_result.get('min_clearance', 0)),
            'mean_clearance': float(clearance_result.get('mean_clearance', 0)),
            'p01_clearance': float(clearance_result.get('p01_clearance', 0)),
            'p05_clearance': float(clearance_result.get('p05_clearance', 0)),
            'p10_clearance': float(clearance_result.get('p10_clearance', 0)),
            'p15_clearance': float(clearance_result.get('p15_clearance', 0)),
            'p20_clearance': float(clearance_result.get('p20_clearance', 0)),
            'p50_clearance': float(clearance_result.get('p50_clearance', 0)),
            'inside_ratio': float(clearance_result.get('inside_ratio', 0)),
            'pass_strict': bool(clearance_result.get('pass', False)),
            'pass_p10': clearance_result.get('inside_ratio', 0) >= 0.999 and clearance_result.get('p10_clearance', 0) >= clearance_threshold,
            'pass_p15': clearance_result.get('inside_ratio', 0) >= 0.999 and clearance_result.get('p15_clearance', 0) >= clearance_threshold,
            'pass_p20': clearance_result.get('inside_ratio', 0) >= 0.999 and clearance_result.get('p20_clearance', 0) >= clearance_threshold,
        }
        
        logger.info(f"指标计算完成: Chamfer={metrics['chamfer']:.2f}, P15={metrics['p15_clearance']:.2f}")
        
        return metrics
        
    except Exception as e:
        logger.error(f"计算指标失败: {e}")
        raise


def compute_chamfer_distance(vertices_a, vertices_b, sample_size=20000):
    """
    计算Chamfer距离（双向最近邻距离）
    
    Args:
        vertices_a: Nx3数组
        vertices_b: Mx3数组
        sample_size: 采样数量
        
    Returns:
        float: Chamfer距离（mm）
    """
    try:
        from scipy.spatial import cKDTree
        
        # 采样（如果顶点太多）
        if len(vertices_a) > sample_size:
            indices_a = np.random.choice(len(vertices_a), sample_size, replace=False)
            sample_a = vertices_a[indices_a]
        else:
            sample_a = vertices_a
        
        if len(vertices_b) > sample_size:
            indices_b = np.random.choice(len(vertices_b), sample_size, replace=False)
            sample_b = vertices_b[indices_b]
        else:
            sample_b = vertices_b
        
        # 构建KD树
        tree_b = cKDTree(sample_b)
        tree_a = cKDTree(sample_a)
        
        # A -> B的距离
        distances_ab, _ = tree_b.query(sample_a)
        
        # B -> A的距离
        distances_ba, _ = tree_a.query(sample_b)
        
        # Chamfer距离 = 双向平均距离
        chamfer = (np.mean(distances_ab) + np.mean(distances_ba)) / 2
        
        return float(chamfer)
        
    except Exception as e:
        logger.error(f"计算Chamfer距离失败: {e}")
        # 返回一个默认值而不是崩溃
        return 0.0

