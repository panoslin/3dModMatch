#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版 3DM 鞋模渲染器（优化重构）

改进点：
1) 支持合并多个 Mesh（不再被后一个覆盖）
2) 更稳健的面索引解析（三角面/四边形自动处理）
3) 自动按 Rhino 模型单位换算为毫米（mm）
4) 点云可复现实验（可设随机种子），分层抽样更均匀
5) 结构化日志 & 更清晰的 CLI（输入/输出可配置）
6) 代码裁剪：移除未用依赖，函数化拆分

依赖：rhino3dm, numpy, plotly
安装：
  pip install rhino3dm numpy plotly

示例：
  python enhanced_shoe_renderer_optimized.py \
      --input /path/to/model.3dm \
      --output /path/to/ENHANCED_shoe_model.html
"""
from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import plotly.graph_objects as go
import rhino3dm

# ---------------------------- 日志配置 ---------------------------- #
logger = logging.getLogger("enhanced3d")
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(levelname)s] %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


# ---------------------------- 工具函数 ---------------------------- #

def _unit_to_mm(model: rhino3dm.File3dm) -> float:
    """将 Rhino 模型单位换算为毫米比例因子。
    若无法识别，则返回 1.0。
    """
    try:
        us = model.Settings.ModelUnitSystem
        # rhino3dm.UnitSystem 枚举映射
        # 参考：https://mcneel.github.io/rhino3dm/python/api/File3dmSettings.html
        mm = rhino3dm.UnitSystem.Millimeters
        cm = rhino3dm.UnitSystem.Centimeters
        m = rhino3dm.UnitSystem.Meters
        inch = rhino3dm.UnitSystem.Inches
        ft = rhino3dm.UnitSystem.Feet
        unit_map = {
            mm: 1.0,
            cm: 10.0,
            m: 1000.0,
            inch: 25.4,
            ft: 304.8,
        }
        scale = unit_map.get(us, 1.0)
        if scale != 1.0:
            logger.info(f"单位换算：{us} -> 毫米，尺度因子 {scale}")
        return scale
    except Exception:
        return 1.0


def _mesh_faces_to_triangles(face: rhino3dm.MeshFace) -> List[Tuple[int, int, int]]:
    """将 MeshFace 转换为一个或两个三角形顶点索引三元组。
    优先使用 A/B/C/D 属性；若 D 无效则视为三角形。
    """
    tris: List[Tuple[int, int, int]] = []
    try:
        a, b, c = face.A, face.B, face.C
        tris.append((a, b, c))
        # 某些情况下 D == C（或 -1）意味着三角形
        d = getattr(face, "D", None)
        if d is not None and d not in (c, -1):
            tris.append((a, c, d))
    except Exception:
        # 兜底：尝试索引访问（极少数绑定差异）
        try:
            a, b, c = face[0], face[1], face[2]
            tris.append((a, b, c))
            if len(face) >= 4 and face[3] not in (face[2], -1):
                tris.append((a, face[2], face[3]))
        except Exception:
            pass
    return tris


@dataclass
class ModelData:
    vertices: np.ndarray = field(default_factory=lambda: np.zeros((0, 3), dtype=float))
    faces: List[Tuple[int, int, int]] = field(default_factory=list)  # 三角面索引
    curves: List[np.ndarray] = field(default_factory=list)  # 每条曲线 Nx3
    success: bool = False
    stats: Dict[str, object] = field(default_factory=dict)


class Enhanced3DRenderer:
    """增强的 3D 渲染器（优化版）"""

    def __init__(
        self,
        *,
        min_faces_for_mesh: int = 1000,
        curve_samples: int = 200,
        pointcloud_max_points: int = 20000,
        pointcloud_layers: int = 24,
        rng_seed: int = 42,
    ) -> None:
        self.min_faces_for_mesh = int(min_faces_for_mesh)
        self.curve_samples = int(curve_samples)
        self.pointcloud_max_points = int(pointcloud_max_points)
        self.pointcloud_layers = int(pointcloud_layers)
        self.rng = np.random.default_rng(rng_seed)

    # ---------------------- 数据读取与规整 ---------------------- #
    def read_3dm(self, file_path: str | Path) -> ModelData:
        """读取 .3dm 文件，合并多个 Mesh，并采样 NURBS 曲线。
        返回统一的 ModelData（顶点单位为毫米）。
        """
        p = Path(file_path)
        if not p.exists():
            logger.error(f"文件不存在：{p}")
            return ModelData(success=False)

        logger.info(f"读取 3DM 文件：{p}")
        model = rhino3dm.File3dm.Read(str(p))
        if not model:
            logger.error("无法读取 3dm 文件（返回空模型）")
            return ModelData(success=False)

        unit_scale = _unit_to_mm(model)

        all_vertices: List[np.ndarray] = []
        all_faces: List[Tuple[int, int, int]] = []
        curves: List[np.ndarray] = []

        vertex_offset = 0
        mesh_count = 0
        curve_count = 0

        for i, obj in enumerate(model.Objects):
            geom = obj.Geometry

            # ---- Mesh ----
            if isinstance(geom, rhino3dm.Mesh):
                mesh_count += 1
                v = np.array([[vv.X, vv.Y, vv.Z] for vv in geom.Vertices], dtype=float)
                if unit_scale != 1.0:
                    v *= unit_scale
                all_vertices.append(v)

                # 面索引（统一三角面）
                for f in geom.Faces:
                    tris = _mesh_faces_to_triangles(f)
                    for a, b, c in tris:
                        all_faces.append((a + vertex_offset, b + vertex_offset, c + vertex_offset))

                logger.info(
                    f"Mesh 对象 {i}: 顶点 {len(v):,}，三角形 {sum(1 for _ in geom.Faces)*2:,}（含四边形拆三角的上限估计）"
                )
                vertex_offset += len(v)

            # ---- NurbsCurve ----
            elif isinstance(geom, rhino3dm.NurbsCurve):
                try:
                    dom = geom.Domain
                    t_vals = np.linspace(dom.T0, dom.T1, self.curve_samples)
                    pts = []
                    for t in t_vals:
                        pt = geom.PointAt(t)
                        pts.append([pt.X * unit_scale, pt.Y * unit_scale, pt.Z * unit_scale])
                    curves.append(np.asarray(pts, dtype=float))
                    curve_count += 1
                except Exception as e:
                    logger.warning(f"曲线采样失败（对象 {i}）：{e}")

            else:
                # 可按需扩展：Brep（需要先网格化）、SubD 等
                pass

        if not all_vertices:
            logger.error("未在模型中找到 Mesh 顶点数据。")
            return ModelData(success=False)

        vertices = np.vstack(all_vertices) if len(all_vertices) > 1 else all_vertices[0]

        # 统计信息
        bounds_min = vertices.min(axis=0)
        bounds_max = vertices.max(axis=0)
        size = bounds_max - bounds_min
        stats = {
            "vertex_count": int(len(vertices)),
            "face_count": int(len(all_faces)),
            "bounds": {"x": [float(bounds_min[0]), float(bounds_max[0])],
                        "y": [float(bounds_min[1]), float(bounds_max[1])],
                        "z": [float(bounds_min[2]), float(bounds_max[2])]},
            "center": vertices.mean(axis=0).tolist(),
            "size": size.tolist(),
            "mesh_count": mesh_count,
            "curve_count": curve_count,
        }

        logger.info(
            f"汇总：Mesh={mesh_count} 条，曲线={curve_count} 条，顶点={stats['vertex_count']:,}，三角面={stats['face_count']:,}"
        )

        return ModelData(
            vertices=vertices,
            faces=all_faces,
            curves=curves,
            success=True,
            stats=stats,
        )

    # -------------------------- 可视化 -------------------------- #
    def _build_mesh_trace(self, vertices: np.ndarray, faces: List[Tuple[int, int, int]]) -> go.Mesh3d:
        face_array = np.asarray(faces, dtype=int)
        return go.Mesh3d(
            x=vertices[:, 0],
            y=vertices[:, 1],
            z=vertices[:, 2],
            i=face_array[:, 0],
            j=face_array[:, 1],
            k=face_array[:, 2],
            intensity=vertices[:, 2],  # 按高度着色
            colorscale=[
                [0.0, '#8B4513'],
                [0.3, '#D2691E'],
                [0.5, '#DEB887'],
                [0.7, '#F5DEB3'],
                [0.9, '#FFF8DC'],
                [1.0, '#FFFACD']
            ],
            opacity=0.96,
            name='鞋模表面',
            lighting=dict(ambient=0.3, diffuse=0.8, specular=0.3, roughness=0.22, fresnel=0.08),
            showscale=True,
            colorbar=dict(title="高度 (mm)", thickness=20, len=0.8),
            hovertemplate='<b>鞋模表面</b><br>X: %{x:.1f} mm<br>Y: %{y:.1f} mm<br>Z: %{z:.1f} mm<extra></extra>'
        )

    def _sample_pointcloud(self, vertices: np.ndarray) -> np.ndarray:
        """分层采样点云，保证不同高度层次的均匀性；可重复（受 rng 控制）。"""
        n = len(vertices)
        if n <= self.pointcloud_max_points:
            return vertices

        z = vertices[:, 2]
        z_min, z_max = float(z.min()), float(z.max())
        layers = self.pointcloud_layers
        per_layer = max(1, self.pointcloud_max_points // layers)

        sampled_idx: List[int] = []
        for i in range(layers):
            lo = z_min + (z_max - z_min) * i / layers
            hi = z_min + (z_max - z_min) * (i + 1) / layers
            mask = (z >= lo) & (z < hi) if i < layers - 1 else (z >= lo) & (z <= hi)
            idx = np.nonzero(mask)[0]
            if len(idx) == 0:
                continue
            if len(idx) > per_layer:
                pick = self.rng.choice(idx, size=per_layer, replace=False)
            else:
                pick = idx
            sampled_idx.extend(pick.tolist())
        return vertices[np.asarray(sampled_idx, dtype=int)]

    def _build_point_trace(self, vertices: np.ndarray) -> go.Scatter3d:
        v = self._sample_pointcloud(vertices)
        return go.Scatter3d(
            x=v[:, 0],
            y=v[:, 1],
            z=v[:, 2],
            mode='markers',
            marker=dict(
                size=1.8,
                color=v[:, 2],
                colorscale=[
                    [0.0, '#654321'],
                    [0.2, '#8B4513'],
                    [0.4, '#A0522D'],
                    [0.6, '#CD853F'],
                    [0.8, '#DEB887'],
                    [1.0, '#F5E6D3']
                ],
                opacity=0.85,
                line=dict(width=0),
                colorbar=dict(title="高度 (mm)", thickness=20, len=0.8),
            ),
            name='鞋模点云',
            hovertemplate='<b>鞋模顶点</b><br>X: %{x:.1f} mm<br>Y: %{y:.1f} mm<br>Z: %{z:.1f} mm<extra></extra>'
        )

    def _build_curve_traces(self, curves: List[np.ndarray]) -> List[go.Scatter3d]:
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#C56CF0', '#00C9A7']
        traces: List[go.Scatter3d] = []
        for i, c in enumerate(curves):
            if c.size == 0:
                continue
            traces.append(
                go.Scatter3d(
                    x=c[:, 0], y=c[:, 1], z=c[:, 2],
                    mode='lines',
                    line=dict(color=colors[i % len(colors)], width=6),
                    name=f'轮廓线 {i+1}',
                    hovertemplate='<b>轮廓线</b><br>X: %{x:.1f}<br>Y: %{y:.1f}<br>Z: %{z:.1f}<extra></extra>'
                )
            )
        return traces

    def create_figure(self, data: ModelData) -> Optional[go.Figure]:
        if not data.success or data.vertices.size == 0:
            logger.error("输入数据无效，无法创建图形。")
            return None

        vertices = data.vertices
        faces = data.faces
        stats = data.stats or {}

        fig = go.Figure()
        if faces and len(faces) >= self.min_faces_for_mesh:
            logger.info(f"使用网格渲染：三角面 {len(faces):,}")
            fig.add_trace(self._build_mesh_trace(vertices, faces))
        else:
            logger.info(f"使用点云渲染：顶点 {len(vertices):,}")
            fig.add_trace(self._build_point_trace(vertices))

        if data.curves:
            for t in self._build_curve_traces(data.curves):
                fig.add_trace(t)

        title_text = "高级鞋模 3D 渲染"
        if stats:
            vc = stats.get('vertex_count', 0)
            fc = stats.get('face_count', 0)
            size = stats.get('size', [0, 0, 0])
            title_text += f"<br><sub>顶点: {vc:,} | 面: {fc:,} | 尺寸: {size[0]:.0f}×{size[1]:.0f}×{size[2]:.0f} mm</sub>"

        fig.update_layout(
            title={'text': title_text, 'x': 0.5, 'font': {'size': 20, 'color': '#2C3E50'}},
            scene=dict(
                xaxis=dict(title="长度 X (mm)", backgroundcolor='rgb(245,245,245)', gridcolor='rgb(200,200,200)', showbackground=True, zerolinecolor='rgb(150,150,150)'),
                yaxis=dict(title="宽度 Y (mm)", backgroundcolor='rgb(245,245,245)', gridcolor='rgb(200,200,200)', showbackground=True, zerolinecolor='rgb(150,150,150)'),
                zaxis=dict(title="高度 Z (mm)", backgroundcolor='rgb(245,245,245)', gridcolor='rgb(200,200,200)', showbackground=True, zerolinecolor='rgb(150,150,150)'),
                aspectmode='data',
                camera=dict(eye=dict(x=1.5, y=-1.8, z=1.2), center=dict(x=0, y=0, z=0), up=dict(x=0, y=0, z=1)),
                bgcolor='rgb(248,249,250)'
            ),
            width=1200,
            height=900,
            paper_bgcolor='white',
            font=dict(family="Arial, sans-serif", size=12, color="#2C3E50"),
            showlegend=True,
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor="rgba(255,255,255,0.85)", bordercolor="rgba(0,0,0,0.1)", borderwidth=1),
        )
        return fig


# ---------------------------- CLI 主程序 ---------------------------- #

def main() -> None:
    parser = argparse.ArgumentParser(description="增强的 3DM 鞋模渲染（优化版）")
    parser.add_argument("--input", required=True, help="输入 .3dm 文件路径")
    parser.add_argument("--output", required=False, default=None, help="输出 HTML 文件路径（可选）")
    parser.add_argument("--seed", type=int, default=42, help="点云抽样随机种子（默认 42）")
    parser.add_argument("--min-mesh-faces", type=int, default=1000, help="达到该面数时优先用网格渲染")
    parser.add_argument("--max-points", type=int, default=20000, help="点云渲染的最大点数上限")
    parser.add_argument("--curve-samples", type=int, default=200, help="每条曲线的采样点数量")
    parser.add_argument("--layers", type=int, default=24, help="点云按高度分层数量")
    parser.add_argument("--show", action="store_true", help="渲染完成后在窗口中显示（可能受环境限制）")
    args = parser.parse_args()

    renderer = Enhanced3DRenderer(
        min_faces_for_mesh=args.min_mesh_faces,
        curve_samples=args.curve_samples,
        pointcloud_max_points=args.max_points,
        pointcloud_layers=args.layers,
        rng_seed=args.seed,
    )

    data = renderer.read_3dm(args.input)
    if not data.success:
        logger.error("读取失败，终止。")
        return

    stats = data.stats
    logger.info("读取成功！")
    logger.info(f"  顶点数：{stats.get('vertex_count', 0):,}")
    logger.info(f"  面数：{stats.get('face_count', 0):,}")
    logger.info(f"  尺寸(mm)：{np.array(stats.get('size', [0,0,0])).round(2).tolist()}")

    fig = renderer.create_figure(data)
    if fig is None:
        logger.error("图形创建失败。")
        return

    # 输出
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.write_html(str(out))
        logger.info(f"✅ 渲染结果已保存：{out}")
    else:
        logger.info("未提供 --output，跳过写入 HTML。")

    if args.show:
        try:
            fig.show()
        except Exception as e:
            logger.warning(f"显示窗口失败：{e}")


if __name__ == "__main__":
    main()
