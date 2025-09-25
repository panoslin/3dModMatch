#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GLB格式处理器 - 高性能3D模型转换和优化

功能特性：
1. 3DM到GLB格式转换
2. 多精度级别(LOD)模型生成
3. 几何简化和压缩
4. WebGL优化处理

依赖库：
- rhino3dm: 3DM文件读取
- trimesh: 几何处理和简化
- pygltflib: GLTF/GLB文件生成
- numpy: 数值计算

安装：
pip install rhino3dm trimesh pygltflib numpy pillow

作者：AI Assistant
创建时间：2024-09-25
版本：v1.0
"""
from __future__ import annotations

import os
import sys
import json
import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
import hashlib
import time as import_time

import numpy as np
from django.conf import settings

# 3D处理相关库导入
try:
    import rhino3dm
    import trimesh
    import pygltflib
    from pygltflib import GLTF2, Scene, Node, Mesh, Primitive, Accessor, BufferView, Buffer
    from pygltflib import Material, PbrMetallicRoughness, TextureInfo, Image, Sampler, Texture
    
    # 在pygltflib 1.16.2中，常量直接在主模块中
    from pygltflib import ARRAY_BUFFER, ELEMENT_ARRAY_BUFFER, FLOAT, UNSIGNED_INT, TRIANGLES
    
    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    DEPENDENCIES_AVAILABLE = False
    MISSING_DEPENDENCY = str(e)

# 日志配置
logger = logging.getLogger('glb_processor')
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(levelname)s] %(name)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# ========================== 常量定义 ========================== #

# LOD级别预设配置
LOD_PRESETS = {
    'preview': {
        'simplify_ratio': 0.1,  # 简化到10%
        'max_faces': 1000,
        'priority': 1,
        'description': '预览级别 - 快速加载'
    },
    'detail': {
        'simplify_ratio': 0.5,  # 简化到50%
        'max_faces': 5000,
        'priority': 2,
        'description': '详细级别 - 平衡质量'
    },
    'full': {
        'simplify_ratio': 1.0,  # 不简化
        'max_faces': 50000,
        'priority': 3,
        'description': '完整级别 - 最高质量'
    }
}


# ========================== 数据类型定义 ========================== #

@dataclass
class LODLevel:
    """LOD级别配置"""
    name: str
    target_faces: int
    compression_level: float
    description: str

# LOD级别预设配置已在上方定义

@dataclass 
class ProcessingStats:
    """处理统计信息"""
    original_vertices: int = 0
    original_faces: int = 0
    processed_vertices: int = 0
    processed_faces: int = 0
    compression_ratio: float = 0.0
    processing_time: float = 0.0
    file_size_original: int = 0
    file_size_compressed: int = 0

@dataclass
class ConversionResult:
    """转换结果"""
    success: bool = False
    error_message: str = ""
    output_files: Dict[str, str] = field(default_factory=dict)
    stats: Dict[str, ProcessingStats] = field(default_factory=dict)
    metadata: Dict = field(default_factory=dict)


# ========================== 几何简化算法 ========================== #

class GeometrySimplifier:
    """几何体简化器 - 使用多种算法优化网格"""
    
    def __init__(self):
        self.logger = logging.getLogger(f'{logger.name}.simplifier')
    
    def simplify_mesh(self, mesh: trimesh.Trimesh, target_faces: int) -> trimesh.Trimesh:
        """
        简化网格到目标面数
        
        Args:
            mesh: 原始网格
            target_faces: 目标面数
            
        Returns:
            trimesh.Trimesh: 简化后的网格
        """
        if mesh.faces.shape[0] <= target_faces:
            self.logger.info(f"网格面数 {mesh.faces.shape[0]} 已小于目标 {target_faces}，跳过简化")
            return mesh
            
        try:
            # 方法1: 使用trimesh的简化算法
            simplified = mesh.simplify_quadric_decimation(target_faces)
            
            if simplified.faces.shape[0] > target_faces * 1.2:
                # 如果简化不够，尝试更激进的简化
                simplified = self._aggressive_simplify(mesh, target_faces)
                
            self.logger.info(f"网格简化：{mesh.faces.shape[0]} -> {simplified.faces.shape[0]} 面")
            return simplified
            
        except Exception as e:
            self.logger.warning(f"简化失败，使用原始网格: {e}")
            return mesh
    
    def _aggressive_simplify(self, mesh: trimesh.Trimesh, target_faces: int) -> trimesh.Trimesh:
        """激进简化算法"""
        try:
            # 计算简化比例
            ratio = target_faces / mesh.faces.shape[0]
            ratio = min(ratio, 0.95)  # 最多保留95%
            
            # 使用顶点聚类简化
            simplified = mesh.simplify_quadric_decimation(int(mesh.faces.shape[0] * ratio))
            
            return simplified
        except:
            return mesh
    
    def optimize_for_webgl(self, mesh: trimesh.Trimesh) -> trimesh.Trimesh:
        """
        针对WebGL进行优化
        
        Args:
            mesh: 输入网格
            
        Returns:
            trimesh.Trimesh: 优化后的网格
        """
        try:
            # 1. 移除重复顶点
            mesh.merge_vertices()
            
            # 2. 移除退化面
            mesh.remove_degenerate_faces()
            
            # 3. 修复法线
            mesh.fix_normals()
            
            # 4. 计算顶点法线（如果没有的话）
            if not hasattr(mesh.visual, 'vertex_normals'):
                mesh.vertex_normals
            
            self.logger.info(f"WebGL优化完成：顶点 {len(mesh.vertices)}, 面 {len(mesh.faces)}")
            return mesh
            
        except Exception as e:
            self.logger.warning(f"WebGL优化失败: {e}")
            return mesh


# ========================== GLB处理器主类 ========================== #

class GLBProcessor:
    """
    GLB格式处理器主类
    
    主要功能：
    1. 3DM文件读取和解析
    2. 几何数据提取和处理 
    3. 多精度LOD模型生成
    4. GLB文件生成和压缩
    5. 元数据管理
    """
    
    def __init__(self, cache_dir: Optional[str] = None, max_workers: int = 4):
        """
        初始化GLB处理器
        
        Args:
            cache_dir: 缓存目录路径，默认使用临时目录
            max_workers: 并发处理的最大工作线程数
        """
        # 依赖检查
        if not DEPENDENCIES_AVAILABLE:
            logger.warning(f"GLB处理器依赖不完整: {MISSING_DEPENDENCY}")
            # 不抛出异常，允许创建对象但标记为不可用
        
        self.simplifier = GeometrySimplifier()
        self.cache_dir = Path(cache_dir or tempfile.gettempdir()) / 'glb_cache'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_workers = max_workers
        
        self.logger = logging.getLogger(f'{logger.name}.processor')
        self.logger.info(f"GLB处理器已初始化，缓存目录: {self.cache_dir}")
    
    def get_dependency_status(self) -> Dict[str, Any]:
        """
        获取GLB处理器的依赖状态
        
        Returns:
            Dict包含依赖状态信息
        """
        try:
            version_info = {}
            if DEPENDENCIES_AVAILABLE:
                try:
                    import trimesh
                    version_info['trimesh'] = getattr(trimesh, '__version__', 'unknown')
                except ImportError:
                    pass
                    
                try:
                    import pygltflib
                    version_info['pygltflib'] = getattr(pygltflib, '__version__', 'unknown')
                except ImportError:
                    pass
                    
                try:
                    import rhino3dm
                    version_info['rhino3dm'] = 'installed'
                except ImportError:
                    pass
            
            return {
                'available': DEPENDENCIES_AVAILABLE,
                'missing': [MISSING_DEPENDENCY] if not DEPENDENCIES_AVAILABLE else [],
                'needs_install': [MISSING_DEPENDENCY] if not DEPENDENCIES_AVAILABLE else [],
                'version_info': version_info
            }
        except Exception as e:
            return {
                'available': False,
                'missing': [str(e)],
                'needs_install': [str(e)],
                'version_info': {}
            }
    
    def convert_3dm_to_glb(
        self, 
        input_path: Union[str, Path],
        output_dir: Union[str, Path],
        lod_levels: Optional[List[str]] = None,
        base_name: Optional[str] = None
    ) -> ConversionResult:
        """
        将3DM文件转换为多精度GLB文件
        
        Args:
            input_path: 输入3DM文件路径
            output_dir: 输出目录
            lod_levels: 要生成的LOD级别列表，默认['preview', 'detail', 'full']
            base_name: 输出文件基础名称，默认使用输入文件名
            
        Returns:
            ConversionResult: 转换结果
        """
        input_path = Path(input_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if not input_path.exists():
            return ConversionResult(
                success=False, 
                error_message=f"输入文件不存在: {input_path}"
            )
        
        if lod_levels is None:
            lod_levels = ['preview', 'detail', 'full']
            
        base_name = base_name or input_path.stem
        
        self.logger.info(f"开始处理文件: {input_path}")
        self.logger.info(f"输出目录: {output_dir}")
        self.logger.info(f"LOD级别: {lod_levels}")
        
        try:
            # 1. 读取3DM文件
            mesh_data = self._read_3dm_file(input_path)
            if not mesh_data:
                return ConversionResult(
                    success=False,
                    error_message="无法读取3DM文件或文件格式不支持"
                )
            
            # 2. 并行生成多个LOD级别
            result = ConversionResult(success=True)
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {}
                
                for lod_level in lod_levels:
                    if lod_level not in LOD_PRESETS:
                        self.logger.warning(f"未知LOD级别: {lod_level}")
                        continue
                        
                    output_file = output_dir / f"{base_name}_{lod_level}.glb"
                    future = executor.submit(
                        self._process_lod_level,
                        mesh_data, 
                        lod_level,
                        output_file
                    )
                    futures[lod_level] = future
                
                # 收集结果
                for lod_level, future in futures.items():
                    try:
                        stats = future.result(timeout=300)  # 5分钟超时
                        result.output_files[lod_level] = str(output_dir / f"{base_name}_{lod_level}.glb")
                        result.stats[lod_level] = stats
                        
                    except Exception as e:
                        self.logger.error(f"处理LOD级别 {lod_level} 失败: {e}")
                        result.success = False
                        result.error_message = f"处理LOD级别 {lod_level} 失败: {e}"
            
            # 3. 生成元数据
            result.metadata = self._generate_metadata(mesh_data, result.stats)
            
            self.logger.info(f"转换完成，生成 {len(result.output_files)} 个文件")
            return result
            
        except Exception as e:
            self.logger.error(f"转换过程发生错误: {e}")
            return ConversionResult(
                success=False,
                error_message=f"转换失败: {str(e)}"
            )
    
    def _read_3dm_file(self, file_path: Path) -> Optional[trimesh.Trimesh]:
        """读取3DM文件并转换为trimesh格式"""
        try:
            self.logger.info(f"读取3DM文件: {file_path}")
            
            # 使用rhino3dm读取文件
            model = rhino3dm.File3dm.Read(str(file_path))
            if not model:
                self.logger.error("无法读取3DM文件")
                return None
            
            # 提取所有网格数据
            vertices_list = []
            faces_list = []
            vertex_offset = 0
            
            for obj in model.Objects:
                geom = obj.Geometry
                if isinstance(geom, rhino3dm.Mesh):
                    # 提取顶点
                    vertices = np.array([[v.X, v.Y, v.Z] for v in geom.Vertices])
                    vertices_list.append(vertices)
                    
                    # 提取面（转换为三角形）
                    faces = []
                    for face in geom.Faces:
                        if face.IsTriangle:
                            faces.append([face.A + vertex_offset, face.B + vertex_offset, face.C + vertex_offset])
                        else:  # 四边形，拆分为两个三角形
                            faces.append([face.A + vertex_offset, face.B + vertex_offset, face.C + vertex_offset])
                            faces.append([face.A + vertex_offset, face.C + vertex_offset, face.D + vertex_offset])
                    
                    faces_list.extend(faces)
                    vertex_offset += len(vertices)
            
            if not vertices_list:
                self.logger.error("3DM文件中未找到网格数据")
                return None
            
            # 合并所有顶点和面
            all_vertices = np.vstack(vertices_list)
            all_faces = np.array(faces_list)
            
            # 创建trimesh对象
            mesh = trimesh.Trimesh(vertices=all_vertices, faces=all_faces)
            
            self.logger.info(f"成功读取网格：顶点 {len(mesh.vertices)}, 面 {len(mesh.faces)}")
            return mesh
            
        except Exception as e:
            self.logger.error(f"读取3DM文件失败: {e}")
            return None
    
    def _process_lod_level(self, mesh: trimesh.Trimesh, lod_level: str, output_file: Path) -> ProcessingStats:
        """处理单个LOD级别"""
        import time
        start_time = time.time()
        
        lod_config = LOD_PRESETS[lod_level]
        self.logger.info(f"处理LOD级别: {lod_level} (目标面数: {lod_config.target_faces})")
        
        # 统计信息
        stats = ProcessingStats(
            original_vertices=len(mesh.vertices),
            original_faces=len(mesh.faces)
        )
        
        try:
            # 1. 简化网格
            if lod_config.target_faces < len(mesh.faces):
                processed_mesh = self.simplifier.simplify_mesh(mesh, lod_config.target_faces)
            else:
                processed_mesh = mesh.copy()
            
            # 2. WebGL优化
            processed_mesh = self.simplifier.optimize_for_webgl(processed_mesh)
            
            # 3. 生成GLB文件
            self._export_glb(processed_mesh, output_file)
            
            # 4. 更新统计信息
            stats.processed_vertices = len(processed_mesh.vertices)
            stats.processed_faces = len(processed_mesh.faces)
            stats.compression_ratio = stats.processed_faces / stats.original_faces if stats.original_faces > 0 else 0
            stats.processing_time = time.time() - start_time
            
            if output_file.exists():
                stats.file_size_compressed = output_file.stat().st_size
            
            self.logger.info(
                f"LOD {lod_level} 处理完成：{stats.original_faces} -> {stats.processed_faces} 面 "
                f"(压缩比: {stats.compression_ratio:.2f}, 用时: {stats.processing_time:.1f}s)"
            )
            
            return stats
            
        except Exception as e:
            self.logger.error(f"处理LOD {lod_level} 失败: {e}")
            raise
    
    def _export_glb(self, mesh: trimesh.Trimesh, output_file: Path):
        """导出trimesh为GLB格式"""
        try:
            # 使用trimesh的内置导出功能
            mesh.export(str(output_file), file_type='glb')
            self.logger.info(f"GLB文件已保存: {output_file}")
            
        except Exception as e:
            self.logger.error(f"导出GLB失败: {e}")
            raise
    
    def _generate_metadata(self, original_mesh: trimesh.Trimesh, stats: Dict[str, ProcessingStats]) -> Dict:
        """生成处理元数据"""
        metadata = {
            'processor_version': '1.0',
            'original_stats': {
                'vertices': len(original_mesh.vertices),
                'faces': len(original_mesh.faces),
                'bounds': original_mesh.bounds.tolist(),
                'volume': float(original_mesh.volume) if original_mesh.is_watertight else 0.0
            },
            'lod_levels': {},
            'processing_summary': {
                'total_levels': len(stats),
                'total_processing_time': sum(s.processing_time for s in stats.values()),
                'best_compression': min((s.compression_ratio for s in stats.values()), default=1.0)
            }
        }
        
        for level, stat in stats.items():
            metadata['lod_levels'][level] = {
                'vertices': stat.processed_vertices,
                'faces': stat.processed_faces,
                'compression_ratio': stat.compression_ratio,
                'file_size': stat.file_size_compressed,
                'processing_time': stat.processing_time
            }
        
        return metadata

    def get_cache_key(self, input_path: Union[str, Path]) -> str:
        """生成文件的缓存键"""
        path = Path(input_path)
        if not path.exists():
            return ""
            
        # 基于文件路径和修改时间生成hash
        mtime = path.stat().st_mtime
        content = f"{path.absolute()}_{mtime}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _read_3dm_file(self, input_path: Union[str, Path]) -> Optional[Dict[str, Any]]:
        """
        读取3DM文件并提取mesh数据
        
        Args:
            input_path: 3DM文件路径
            
        Returns:
            包含顶点、面、法向量等数据的字典，失败时返回None
        """
        self.logger.info(f"读取3DM文件: {input_path}")
        
        try:
            # 使用rhino3dm读取文件
            model = rhino3dm.File3dm.Read(str(input_path))
            if not model:
                self.logger.error("无法读取3DM文件")
                return None
                
            # 收集所有mesh数据
            all_vertices = []
            all_faces = []
            all_normals = []
            vertex_offset = 0
            
            # 遍历所有对象
            for obj in model.Objects:
                geometry = obj.Geometry
                
                # 检查是否为mesh
                if hasattr(geometry, 'Vertices') and hasattr(geometry, 'Faces'):
                    mesh = geometry
                    
                    # 提取顶点 - Vertices用len()
                    vertices = []
                    for i in range(len(mesh.Vertices)):
                        vertex = mesh.Vertices[i]
                        vertices.extend([vertex.X, vertex.Y, vertex.Z])
                    all_vertices.extend(vertices)
                    
                    # 提取面（三角化） - Faces用Count
                    faces = []
                    for i in range(mesh.Faces.Count):
                        face = mesh.Faces[i]  # 这是一个tuple (A, B, C, D)
                        
                        # 检查是否为三角形：C==D表示三角形
                        if face[2] == face[3]:  # 三角形
                            faces.extend([
                                face[0] + vertex_offset,  # A
                                face[1] + vertex_offset,  # B
                                face[2] + vertex_offset   # C
                            ])
                        else:  # 四边形，分割为两个三角形
                            faces.extend([
                                face[0] + vertex_offset,  # A
                                face[1] + vertex_offset,  # B
                                face[2] + vertex_offset   # C
                            ])
                            faces.extend([
                                face[0] + vertex_offset,  # A
                                face[2] + vertex_offset,  # C
                                face[3] + vertex_offset   # D
                            ])
                    
                    all_faces.extend(faces)
                    
                    # 提取法向量（如果存在） - Normals用len()
                    normals = []
                    if hasattr(mesh, 'Normals') and len(mesh.Normals) > 0:
                        for i in range(len(mesh.Normals)):
                            normal = mesh.Normals[i]
                            normals.extend([normal.X, normal.Y, normal.Z])
                    else:
                        # 如果没有法向量，生成默认法向量
                        vertex_count = len(vertices) // 3
                        normals = [0.0, 0.0, 1.0] * vertex_count
                    
                    all_normals.extend(normals)
                    vertex_offset += len(vertices) // 3
                    
                # 处理其他几何体类型（如Brep）
                elif hasattr(geometry, 'TryGetMesh'):
                    try:
                        # 尝试将Brep转换为mesh
                        mesh_params = rhino3dm.MeshingParameters.Default
                        mesh = rhino3dm.Mesh.CreateFromBrep(geometry, mesh_params)
                        
                        if mesh and len(mesh.Vertices) > 0:
                            # 处理转换后的mesh（同上面的逻辑）
                            vertices = []
                            for i in range(len(mesh.Vertices)):
                                vertex = mesh.Vertices[i]
                                vertices.extend([vertex.X, vertex.Y, vertex.Z])
                            all_vertices.extend(vertices)
                            
                            faces = []
                            for i in range(mesh.Faces.Count):  # Faces用Count
                                face = mesh.Faces[i]  # tuple (A, B, C, D)
                                if face[2] == face[3]:  # 三角形
                                    faces.extend([
                                        face[0] + vertex_offset,
                                        face[1] + vertex_offset,
                                        face[2] + vertex_offset
                                    ])
                                else:  # 四边形
                                    faces.extend([
                                        face[0] + vertex_offset,
                                        face[1] + vertex_offset,
                                        face[2] + vertex_offset
                                    ])
                                    faces.extend([
                                        face[0] + vertex_offset,
                                        face[2] + vertex_offset,
                                        face[3] + vertex_offset
                                    ])
                            
                            all_faces.extend(faces)
                            
                            # 生成法向量
                            vertex_count = len(vertices) // 3
                            normals = [0.0, 0.0, 1.0] * vertex_count
                            all_normals.extend(normals)
                            vertex_offset += vertex_count
                            
                    except Exception as e:
                        self.logger.warning(f"无法转换Brep到mesh: {e}")
                        continue
            
            if not all_vertices:
                self.logger.error("3DM文件中未找到有效的mesh数据")
                return None
            
            # 确保法向量数量匹配顶点数量
            vertex_count = len(all_vertices) // 3
            if len(all_normals) != len(all_vertices):
                self.logger.warning("法向量数量不匹配，使用默认法向量")
                all_normals = [0.0, 0.0, 1.0] * vertex_count
            
            mesh_data = {
                'vertices': np.array(all_vertices, dtype=np.float32),
                'faces': np.array(all_faces, dtype=np.uint32),
                'normals': np.array(all_normals, dtype=np.float32),
                'vertex_count': vertex_count,
                'face_count': len(all_faces) // 3,
                'bounds': self._calculate_bounds(all_vertices)
            }
            
            self.logger.info(f"成功读取3DM文件: {vertex_count}个顶点, {len(all_faces)//3}个面")
            return mesh_data
            
        except Exception as e:
            self.logger.error(f"读取3DM文件失败: {e}")
            return None
    
    def _calculate_bounds(self, vertices: List[float]) -> Dict[str, float]:
        """计算mesh的边界框"""
        if not vertices or len(vertices) < 3:
            return {'min_x': 0, 'min_y': 0, 'min_z': 0, 'max_x': 0, 'max_y': 0, 'max_z': 0}
        
        xs = vertices[0::3]
        ys = vertices[1::3]
        zs = vertices[2::3]
        
        return {
            'min_x': min(xs), 'max_x': max(xs),
            'min_y': min(ys), 'max_y': max(ys),
            'min_z': min(zs), 'max_z': max(zs)
        }
    
    def _process_lod_level(self, mesh_data: Dict[str, Any], lod_level: str, output_file: Path) -> Dict[str, Any]:
        """
        处理指定LOD级别的模型
        
        Args:
            mesh_data: 原始mesh数据
            lod_level: LOD级别
            output_file: 输出文件路径
            
        Returns:
            处理统计信息
        """
        try:
            self.logger.info(f"处理LOD级别: {lod_level} -> {output_file}")
            
            # 获取LOD配置
            lod_config = LOD_PRESETS.get(lod_level, LOD_PRESETS['preview'])
            
            # 简化mesh（如果需要）
            vertices = mesh_data['vertices'].copy()
            faces = mesh_data['faces'].copy()  
            normals = mesh_data['normals'].copy()
            
            if lod_config['simplify_ratio'] < 1.0:
                self.logger.info(f"简化mesh到 {lod_config['simplify_ratio']*100:.1f}%")
                vertices, faces, normals = self._simplify_mesh(
                    vertices, faces, normals, lod_config['simplify_ratio']
                )
            
            # 生成GLB文件
            success = self._create_glb_file(vertices, faces, normals, output_file)
            
            if success:
                # 计算统计信息
                stats = {
                    'vertex_count': len(vertices) // 3,
                    'face_count': len(faces) // 3,
                    'file_size': output_file.stat().st_size if output_file.exists() else 0,
                    'compression_ratio': lod_config['simplify_ratio'],
                    'success': True
                }
                self.logger.info(f"LOD级别 {lod_level} 处理成功: {stats['vertex_count']}顶点, {stats['face_count']}面")
                return stats
            else:
                return {'success': False, 'error': 'GLB文件生成失败'}
                
        except Exception as e:
            self.logger.error(f"处理LOD级别 {lod_level} 失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def _simplify_mesh(self, vertices: np.ndarray, faces: np.ndarray, normals: np.ndarray, 
                       ratio: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        简化mesh
        
        Args:
            vertices: 顶点数组
            faces: 面数组
            normals: 法向量数组
            ratio: 简化比例
            
        Returns:
            简化后的顶点、面、法向量
        """
        if not DEPENDENCIES_AVAILABLE:
            self.logger.warning("trimesh不可用，跳过mesh简化")
            return vertices, faces, normals
        
        try:
            # 重构vertices为trimesh格式
            vertex_array = vertices.reshape(-1, 3)
            face_array = faces.reshape(-1, 3)
            
            # 创建trimesh对象
            mesh = trimesh.Trimesh(vertices=vertex_array, faces=face_array)
            
            # 计算目标面数
            target_faces = max(int(len(face_array) * ratio), 4)  # 至少保留4个面
            
            # 使用trimesh简化
            if hasattr(mesh, 'simplify_quadric_decimation'):
                simplified = mesh.simplify_quadric_decimation(target_faces)
            else:
                # 备用方法
                simplified = mesh.simplified(face_count=target_faces)
            
            # 转换回numpy数组
            new_vertices = simplified.vertices.flatten().astype(np.float32)
            new_faces = simplified.faces.flatten().astype(np.uint32)
            
            # 重新计算法向量
            vertex_count = len(new_vertices) // 3
            new_normals = np.tile([0.0, 0.0, 1.0], vertex_count).astype(np.float32)
            
            self.logger.info(f"Mesh简化: {len(vertex_array)} -> {len(simplified.vertices)} 顶点")
            return new_vertices, new_faces, new_normals
            
        except Exception as e:
            self.logger.warning(f"Mesh简化失败，使用原始数据: {e}")
            return vertices, faces, normals
    
    def _create_glb_file(self, vertices: np.ndarray, faces: np.ndarray, 
                         normals: np.ndarray, output_file: Path) -> bool:
        """
        创建GLB文件
        
        Args:
            vertices: 顶点数据
            faces: 面数据  
            normals: 法向量数据
            output_file: 输出文件路径
            
        Returns:
            是否成功
        """
        if not DEPENDENCIES_AVAILABLE:
            self.logger.error("pygltflib不可用，无法创建GLB文件")
            return False
        
        try:
            # 确保输出目录存在
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 创建GLTF对象
            gltf = GLTF2()
            
            # 准备数据缓冲区
            vertices_bytes = vertices.tobytes()
            faces_bytes = faces.tobytes()
            normals_bytes = normals.tobytes()
            
            # 创建buffer
            buffer = Buffer()
            buffer.byteLength = len(vertices_bytes) + len(normals_bytes) + len(faces_bytes)
            gltf.buffers = [buffer]
            
            # 创建buffer views
            vertex_buffer_view = BufferView()
            vertex_buffer_view.buffer = 0
            vertex_buffer_view.byteOffset = 0
            vertex_buffer_view.byteLength = len(vertices_bytes)
            vertex_buffer_view.target = ARRAY_BUFFER
            
            normal_buffer_view = BufferView()
            normal_buffer_view.buffer = 0
            normal_buffer_view.byteOffset = len(vertices_bytes)
            normal_buffer_view.byteLength = len(normals_bytes)
            normal_buffer_view.target = ARRAY_BUFFER
            
            face_buffer_view = BufferView()
            face_buffer_view.buffer = 0
            face_buffer_view.byteOffset = len(vertices_bytes) + len(normals_bytes)
            face_buffer_view.byteLength = len(faces_bytes)
            face_buffer_view.target = ELEMENT_ARRAY_BUFFER
            
            gltf.bufferViews = [vertex_buffer_view, normal_buffer_view, face_buffer_view]
            
            # 创建accessors
            vertex_accessor = Accessor()
            vertex_accessor.bufferView = 0
            vertex_accessor.byteOffset = 0
            vertex_accessor.componentType = FLOAT
            vertex_accessor.count = len(vertices) // 3
            vertex_accessor.type = "VEC3"
            vertex_accessor.min = vertices.reshape(-1, 3).min(axis=0).tolist()
            vertex_accessor.max = vertices.reshape(-1, 3).max(axis=0).tolist()
            
            normal_accessor = Accessor()
            normal_accessor.bufferView = 1
            normal_accessor.byteOffset = 0
            normal_accessor.componentType = FLOAT
            normal_accessor.count = len(normals) // 3
            normal_accessor.type = "VEC3"
            
            face_accessor = Accessor()
            face_accessor.bufferView = 2
            face_accessor.byteOffset = 0
            face_accessor.componentType = UNSIGNED_INT
            face_accessor.count = len(faces)
            face_accessor.type = "SCALAR"
            
            gltf.accessors = [vertex_accessor, normal_accessor, face_accessor]
            
            # 创建材质
            material = Material()
            material.pbrMetallicRoughness = PbrMetallicRoughness()
            material.pbrMetallicRoughness.baseColorFactor = [0.8, 0.8, 0.8, 1.0]
            material.pbrMetallicRoughness.metallicFactor = 0.1
            material.pbrMetallicRoughness.roughnessFactor = 0.8
            gltf.materials = [material]
            
            # 创建mesh
            primitive = Primitive()
            primitive.attributes.POSITION = 0
            primitive.attributes.NORMAL = 1
            primitive.indices = 2
            primitive.material = 0
            
            mesh = Mesh()
            mesh.primitives = [primitive]
            gltf.meshes = [mesh]
            
            # 创建node和scene
            node = Node()
            node.mesh = 0
            gltf.nodes = [node]
            
            scene = Scene()
            scene.nodes = [0]
            gltf.scenes = [scene]
            gltf.scene = 0
            
            # 设置二进制数据
            binary_data = vertices_bytes + normals_bytes + faces_bytes
            gltf.set_binary_blob(binary_data)
            
            # 保存GLB文件
            gltf.save(str(output_file))
            
            self.logger.info(f"GLB文件已保存: {output_file} ({output_file.stat().st_size} bytes)")
            return True
            
        except Exception as e:
            self.logger.error(f"创建GLB文件失败: {e}")
            return False
    
    def _generate_metadata(self, mesh_data: Dict[str, Any], stats: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """生成处理元数据"""
        return {
            'original_stats': {
                'vertex_count': mesh_data['vertex_count'],
                'face_count': mesh_data['face_count'],
                'bounds': mesh_data['bounds']
            },
            'lod_stats': stats,
            'processing_info': {
                'processor_version': '1.0',
                'timestamp': import_time.strftime('%Y-%m-%d %H:%M:%S'),
                'dependencies': {
                    'trimesh_available': DEPENDENCIES_AVAILABLE,
                    'pygltflib_available': DEPENDENCIES_AVAILABLE
                }
            }
        }


# ========================== 工具函数 ========================== #

def validate_dependencies() -> Tuple[bool, List[str]]:
    """
    验证所需依赖是否已安装
    
    Returns:
        Tuple[bool, List[str]]: (是否所有依赖都可用, 缺失的依赖列表)
    """
    missing = []
    
    try:
        import rhino3dm
    except ImportError:
        missing.append('rhino3dm')
    
    try:
        import trimesh
    except ImportError:
        missing.append('trimesh')
        
    try:
        import pygltflib
    except ImportError:
        missing.append('pygltflib')
    
    return len(missing) == 0, missing


def create_glb_processor(**kwargs) -> Optional[GLBProcessor]:
    """
    创建GLB处理器实例（工厂函数）
    
    Returns:
        GLBProcessor: 处理器实例，如果依赖不满足则返回None
    """
    available, missing = validate_dependencies()
    if not available:
        logger.error(f"无法创建GLB处理器，缺少依赖: {missing}")
        return None
    
    return GLBProcessor(**kwargs)


# ========================== 主函数 ========================== #

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="GLB格式转换工具")
    parser.add_argument("input", help="输入3DM文件路径")
    parser.add_argument("output", help="输出目录路径")
    parser.add_argument("--levels", nargs="+", default=['preview', 'detail', 'full'],
                       help="LOD级别列表")
    parser.add_argument("--name", help="输出文件基础名称")
    parser.add_argument("--workers", type=int, default=4, help="并发工作线程数")
    
    args = parser.parse_args()
    
    # 检查依赖
    available, missing = validate_dependencies()
    if not available:
        print(f"错误：缺少必要依赖 {missing}")
        print("请安装：pip install rhino3dm trimesh pygltflib")
        sys.exit(1)
    
    # 创建处理器并执行转换
    processor = GLBProcessor(max_workers=args.workers)
    result = processor.convert_3dm_to_glb(
        args.input, 
        args.output,
        args.levels,
        args.name
    )
    
    if result.success:
        print("转换成功！")
        print(f"生成文件：{list(result.output_files.values())}")
        print(f"处理统计：{json.dumps(result.metadata, indent=2, ensure_ascii=False)}")
    else:
        print(f"转换失败：{result.error_message}")
        sys.exit(1)
