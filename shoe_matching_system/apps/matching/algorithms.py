"""
智能匹配算法核心模块
实现几何特征提取、余量计算和最优匹配算法
"""

import numpy as np
from scipy.spatial import KDTree, ConvexHull
from scipy.spatial.distance import cdist
from scipy.optimize import minimize
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GeometricFeatures:
    """几何特征数据结构"""
    points: np.ndarray  # 3D点云 (N, 3)
    bounding_box: Dict[str, float]  # 包围盒
    volume: float  # 体积
    surface_area: float  # 表面积
    curvature_map: np.ndarray  # 曲率图
    feature_points: np.ndarray  # 特征点
    shape_histogram: np.ndarray  # 形状直方图
    center_of_mass: np.ndarray  # 质心


@dataclass
class MatchingResult:
    """匹配结果数据结构"""
    blank_id: int
    blank_name: str
    match_score: float  # 0-1，越高越好
    margin_coverage: float  # 余量覆盖率 (0-1)
    volume_efficiency: float  # 体积利用率
    geometric_similarity: float  # 几何相似度
    min_margin: float  # 最小余量
    max_margin: float  # 最大余量
    avg_margin: float  # 平均余量
    margin_variance: float  # 余量方差
    processing_time: float  # 处理时间(秒)


class GeometricFeatureExtractor:
    """几何特征提取器"""
    
    def __init__(self, resolution: float = 0.1):
        """
        初始化特征提取器
        
        Args:
            resolution: 点云采样分辨率
        """
        self.resolution = resolution
    
    def extract_features(self, points: np.ndarray) -> GeometricFeatures:
        """提取完整的几何特征"""
        try:
            # 1. 基础几何特征
            bounding_box = self._compute_bounding_box(points)
            volume = self._compute_volume(points, bounding_box)
            surface_area = self._estimate_surface_area(points)
            center_of_mass = self._compute_center_of_mass(points)
            
            # 2. 高级几何特征
            curvature_map = self._compute_curvature(points)
            feature_points = self._extract_feature_points(points, curvature_map)
            shape_histogram = self._compute_shape_histogram(points, bounding_box)
            
            return GeometricFeatures(
                points=points,
                bounding_box=bounding_box,
                volume=volume,
                surface_area=surface_area,
                curvature_map=curvature_map,
                feature_points=feature_points,
                shape_histogram=shape_histogram,
                center_of_mass=center_of_mass
            )
        except Exception as e:
            logger.error(f"特征提取失败: {e}")
            raise
    
    def _compute_bounding_box(self, points: np.ndarray) -> Dict[str, float]:
        """计算包围盒"""
        min_coords = np.min(points, axis=0)
        max_coords = np.max(points, axis=0)
        return {
            'x_min': float(min_coords[0]), 'x_max': float(max_coords[0]),
            'y_min': float(min_coords[1]), 'y_max': float(max_coords[1]),
            'z_min': float(min_coords[2]), 'z_max': float(max_coords[2])
        }
    
    def _compute_volume(self, points: np.ndarray, bounding_box: Dict[str, float]) -> float:
        """计算体积（使用凸包近似）"""
        try:
            # 使用凸包计算体积
            hull = ConvexHull(points)
            return float(hull.volume)
        except:
            # 如果凸包失败，使用包围盒体积
            dx = bounding_box['x_max'] - bounding_box['x_min']
            dy = bounding_box['y_max'] - bounding_box['y_min']
            dz = bounding_box['z_max'] - bounding_box['z_min']
            return float(dx * dy * dz)
    
    def _estimate_surface_area(self, points: np.ndarray) -> float:
        """估算表面积"""
        try:
            hull = ConvexHull(points)
            return float(hull.area)
        except:
            # 如果凸包失败，使用点云密度估算
            return float(len(points) * self.resolution ** 2)
    
    def _compute_center_of_mass(self, points: np.ndarray) -> np.ndarray:
        """计算质心"""
        return np.mean(points, axis=0)
    
    def _compute_curvature(self, points: np.ndarray) -> np.ndarray:
        """计算曲率图"""
        try:
            # 使用KDTree进行近邻搜索
            tree = KDTree(points)
            curvatures = np.zeros(len(points))
            
            for i, point in enumerate(points):
                # 找到k个最近邻
                k = min(10, len(points) - 1)
                distances, indices = tree.query(point, k=k)
                
                if len(indices) > 3:
                    # 使用局部平面拟合计算曲率
                    neighbor_points = points[indices[1:]]  # 排除自身
                    center = np.mean(neighbor_points, axis=0)
                    
                    # 计算到局部平面的距离作为曲率近似
                    if len(neighbor_points) >= 3:
                        # 使用PCA找到主方向
                        centered_points = neighbor_points - center
                        cov_matrix = np.cov(centered_points.T)
                        eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
                        
                        # 最小特征值对应的方向是法向量
                        normal = eigenvectors[:, 0]
                        curvature = np.abs(np.dot(point - center, normal))
                        curvatures[i] = curvature
            
            return curvatures
        except Exception as e:
            logger.warning(f"曲率计算失败，使用默认值: {e}")
            return np.zeros(len(points))
    
    def _extract_feature_points(self, points: np.ndarray, curvature_map: np.ndarray) -> np.ndarray:
        """提取特征点（高曲率点）"""
        try:
            # 选择曲率最高的点作为特征点
            threshold = np.percentile(curvature_map, 90)  # 前10%的高曲率点
            feature_indices = np.where(curvature_map > threshold)[0]
            return points[feature_indices]
        except:
            return points[:min(100, len(points))]  # 如果失败，返回前100个点
    
    def _compute_shape_histogram(self, points: np.ndarray, bounding_box: Dict[str, float]) -> np.ndarray:
        """计算形状直方图"""
        try:
            # 将3D空间划分为网格，统计每个网格中的点数
            grid_size = 20  # 20x20x20网格
            
            # 归一化坐标到[0, grid_size-1]
            normalized_points = np.zeros_like(points)
            for i in range(3):
                min_val = bounding_box[f"{['x', 'y', 'z'][i]}_min"]
                max_val = bounding_box[f"{['x', 'y', 'z'][i]}_max"]
                if max_val > min_val:
                    normalized_points[:, i] = (points[:, i] - min_val) / (max_val - min_val) * (grid_size - 1)
            
            # 创建3D直方图
            histogram = np.zeros((grid_size, grid_size, grid_size))
            
            # 统计每个网格中的点数
            for point in normalized_points:
                x, y, z = point.astype(int)
                x = np.clip(x, 0, grid_size - 1)
                y = np.clip(y, 0, grid_size - 1)
                z = np.clip(z, 0, grid_size - 1)
                histogram[x, y, z] += 1
            
            # 展平为一维数组
            return histogram.flatten()
        except Exception as e:
            logger.warning(f"形状直方图计算失败: {e}")
            return np.zeros(8000)  # 20^3 = 8000


class MarginCalculator:
    """余量计算器"""
    
    def __init__(self, required_margin: float = 2.5):
        """
        初始化余量计算器
        
        Args:
            required_margin: 要求的余量距离(mm)
        """
        self.required_margin = required_margin
    
    def calculate_margin_coverage(self, shoe_points: np.ndarray, blank_points: np.ndarray) -> Dict[str, float]:
        """
        计算余量覆盖率
        
        Args:
            shoe_points: 鞋模点云
            blank_points: 粗胚点云
            
        Returns:
            余量统计信息
        """
        try:
            # 构建粗胚的KDTree用于快速最近邻搜索
            blank_tree = KDTree(blank_points)
            
            # 计算每个鞋模点到粗胚表面的距离
            distances, _ = blank_tree.query(shoe_points)
            
            # 计算余量统计
            margins = distances - self.required_margin
            valid_margins = margins[margins >= 0]  # 只考虑满足余量要求的点
            
            if len(valid_margins) == 0:
                return {
                    'coverage': 0.0,
                    'min_margin': 0.0,
                    'max_margin': 0.0,
                    'avg_margin': 0.0,
                    'margin_variance': 0.0,
                    'satisfied_points': 0,
                    'total_points': len(shoe_points)
                }
            
            coverage = len(valid_margins) / len(shoe_points)
            
            return {
                'coverage': float(coverage),
                'min_margin': float(np.min(valid_margins)),
                'max_margin': float(np.max(valid_margins)),
                'avg_margin': float(np.mean(valid_margins)),
                'margin_variance': float(np.var(valid_margins)),
                'satisfied_points': len(valid_margins),
                'total_points': len(shoe_points)
            }
        except Exception as e:
            logger.error(f"余量计算失败: {e}")
            return {
                'coverage': 0.0,
                'min_margin': 0.0,
                'max_margin': 0.0,
                'avg_margin': 0.0,
                'margin_variance': 0.0,
                'satisfied_points': 0,
                'total_points': len(shoe_points)
            }


class IntelligentMatcher:
    """智能匹配器"""
    
    def __init__(self, margin_distance: float = 2.5, weight_geometric: float = 0.4, 
                 weight_margin: float = 0.4, weight_efficiency: float = 0.2):
        """
        初始化智能匹配器
        
        Args:
            margin_distance: 要求的余量距离
            weight_geometric: 几何相似度权重
            weight_margin: 余量覆盖率权重
            weight_efficiency: 体积效率权重
        """
        self.margin_distance = margin_distance
        self.weight_geometric = weight_geometric
        self.weight_margin = weight_margin
        self.weight_efficiency = weight_efficiency
        
        self.feature_extractor = GeometricFeatureExtractor()
        self.margin_calculator = MarginCalculator(margin_distance)
    
    def find_optimal_match(self, shoe_model: 'ShoeModel', blank_models: List['BlankModel']) -> List[MatchingResult]:
        """
        找到最优匹配
        
        Args:
            shoe_model: 鞋模模型
            blank_models: 候选粗胚模型列表
            
        Returns:
            按匹配分数排序的匹配结果列表
        """
        try:
            # 1. 提取鞋模特征
            shoe_features = self._extract_model_features(shoe_model)
            
            # 2. 对每个粗胚进行匹配分析
            matching_results = []
            
            for blank in blank_models:
                try:
                    result = self._analyze_single_match(shoe_features, blank)
                    matching_results.append(result)
                except Exception as e:
                    logger.warning(f"分析粗胚 {blank.id} 失败: {e}")
                    continue
            
            # 3. 按匹配分数排序
            matching_results.sort(key=lambda x: x.match_score, reverse=True)
            
            return matching_results
            
        except Exception as e:
            logger.error(f"匹配分析失败: {e}")
            raise
    
    def _extract_model_features(self, model: 'ShoeModel') -> GeometricFeatures:
        """提取模型特征"""
        # 这里需要根据实际的模型数据结构来提取点云数据
        # 假设模型有bounds和points属性
        if hasattr(model, 'bounds') and model.bounds:
            # 从bounds生成点云（简化处理）
            bounds = model.bounds
            x_range = np.linspace(bounds['x_min'], bounds['x_max'], 100)
            y_range = np.linspace(bounds['y_min'], bounds['y_max'], 100)
            z_range = np.linspace(bounds['z_min'], bounds['z_max'], 100)
            
            # 生成网格点
            X, Y, Z = np.meshgrid(x_range, y_range, z_range)
            points = np.column_stack([X.flatten(), Y.flatten(), Z.flatten()])
            
            # 随机采样以减少计算量
            if len(points) > 10000:
                indices = np.random.choice(len(points), 10000, replace=False)
                points = points[indices]
        else:
            # 如果没有bounds，使用默认点云
            points = np.random.rand(1000, 3) * 100  # 100x100x100的随机点
        
        return self.feature_extractor.extract_features(points)
    
    def _analyze_single_match(self, shoe_features: GeometricFeatures, blank: 'BlankModel') -> MatchingResult:
        """分析单个匹配"""
        import time
        start_time = time.time()
        
        # 1. 提取粗胚特征
        blank_features = self._extract_model_features(blank)
        
        # 2. 计算几何相似度
        geometric_similarity = self._calculate_geometric_similarity(shoe_features, blank_features)
        
        # 3. 计算余量覆盖率
        margin_stats = self.margin_calculator.calculate_margin_coverage(
            shoe_features.points, blank_features.points
        )
        
        # 4. 计算体积效率
        volume_efficiency = shoe_features.volume / blank_features.volume if blank_features.volume > 0 else 0
        
        # 5. 计算综合匹配分数
        match_score = (
            self.weight_geometric * geometric_similarity +
            self.weight_margin * margin_stats['coverage'] +
            self.weight_efficiency * volume_efficiency
        )
        
        # 6. 确保余量覆盖率满足要求
        if margin_stats['coverage'] < 0.95:  # 95%的点必须满足余量要求
            match_score *= 0.5  # 严重惩罚
        
        processing_time = time.time() - start_time
        
        return MatchingResult(
            blank_id=blank.id,
            blank_name=blank.filename,
            match_score=float(match_score),
            margin_coverage=float(margin_stats['coverage']),
            volume_efficiency=float(volume_efficiency),
            geometric_similarity=float(geometric_similarity),
            min_margin=float(margin_stats['min_margin']),
            max_margin=float(margin_stats['max_margin']),
            avg_margin=float(margin_stats['avg_margin']),
            margin_variance=float(margin_stats['margin_variance']),
            processing_time=float(processing_time)
        )
    
    def _calculate_geometric_similarity(self, shoe_features: GeometricFeatures, 
                                      blank_features: GeometricFeatures) -> float:
        """计算几何相似度"""
        try:
            # 1. 形状直方图相似度
            hist_similarity = self._calculate_histogram_similarity(
                shoe_features.shape_histogram, blank_features.shape_histogram
            )
            
            # 2. 特征点匹配相似度
            feature_similarity = self._calculate_feature_point_similarity(
                shoe_features.feature_points, blank_features.feature_points
            )
            
            # 3. 体积比例相似度
            volume_similarity = self._calculate_volume_similarity(
                shoe_features.volume, blank_features.volume
            )
            
            # 4. 表面积比例相似度
            area_similarity = self._calculate_area_similarity(
                shoe_features.surface_area, blank_features.surface_area
            )
            
            # 综合相似度
            similarity = (
                0.3 * hist_similarity +
                0.3 * feature_similarity +
                0.2 * volume_similarity +
                0.2 * area_similarity
            )
            
            return float(similarity)
                    
        except Exception as e:
            logger.warning(f"几何相似度计算失败: {e}")
            return 0.5  # 返回中等相似度
    
    def _calculate_histogram_similarity(self, hist1: np.ndarray, hist2: np.ndarray) -> float:
        """计算直方图相似度（使用余弦相似度）"""
        try:
            # 归一化直方图
            hist1_norm = hist1 / (np.linalg.norm(hist1) + 1e-8)
            hist2_norm = hist2 / (np.linalg.norm(hist2) + 1e-8)
            
            # 计算余弦相似度
            similarity = np.dot(hist1_norm, hist2_norm)
            return float(similarity)
        except:
            return 0.5
    
    def _calculate_feature_point_similarity(self, points1: np.ndarray, points2: np.ndarray) -> float:
        """计算特征点相似度"""
        try:
            if len(points1) == 0 or len(points2) == 0:
                return 0.5
            
            # 计算两组特征点之间的最小距离
            distances = cdist(points1, points2)
            min_distances = np.min(distances, axis=1)
            
            # 距离越小，相似度越高
            avg_min_distance = np.mean(min_distances)
            similarity = 1.0 / (1.0 + avg_min_distance)
            
            return float(similarity)
        except:
            return 0.5
    
    def _calculate_volume_similarity(self, volume1: float, volume2: float) -> float:
        """计算体积相似度"""
        try:
            if volume1 <= 0 or volume2 <= 0:
                return 0.5
            
            ratio = min(volume1, volume2) / max(volume1, volume2)
            return float(ratio)
        except:
            return 0.5
    
    def _calculate_area_similarity(self, area1: float, area2: float) -> float:
        """计算表面积相似度"""
        try:
            if area1 <= 0 or area2 <= 0:
                return 0.5
            
            ratio = min(area1, area2) / max(area1, area2)
            return float(ratio)
        except:
            return 0.5
