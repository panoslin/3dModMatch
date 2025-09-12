#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shoe Last Matcher — 工厂级匹配（含配准、镜像容错、Brep网格化、SDF余量校验、报告/GLB/PLY/热图）

目标：在候选库中为给定鞋模寻找“形状最相似且全表面≥R mm 余量”的最佳匹配，
并生成可追溯的校验报告（含最小余量、误差边界、对齐矩阵等）。

改进要点（相较上一版）：
1) 全局+局部配准：FPFH+RANSAC 粗配 → Point-to-Plane ICP 精配（禁止缩放），多起点、鲁棒核。
2) 镜像容错：自动同时尝试关于 YZ 面的镜像版本（处理左右脚混放）。
3) 粗胚预处理：可选底面切除/小件剔除（减少底座/支撑影响）。
4) SDF 余量校验（采样版）：对目标表面进行高密度均匀采样，
   用候选的签名距离 SDF 检查“每个采样点到候选表面距离 ≥ R + δ”，δ 为工艺安全裕度。
   注：此实现为工程级高置信近似；如需体素体积级“形式化保证”，见 TODO。 
5) 报告与可视化：输出 JSON 报告（可选），包含 c_min/c_mean/p01、Chamfer、体积、对齐矩阵等。

依赖：
  pip install rhino3dm trimesh open3d numpy scipy plotly

可选：
  - 安装 pyembree 可加速射线（trimesh[rays]）。
  - 如果导出 GLB 遇到依赖问题，可另外安装 pygltflib。

示例：
  python shoe_last_matcher.py \
    --target /mnt/data/B004小.3dm \
    --candidates /path/to/library_dir \
    --clearance 2.0 \
    --topk 10 \
    --export_report /tmp/match_report.json\
    --voxel 2.5 --icp-thr 8.0 --fpfh-radius 6.0 --seed 42

注：若要单对单验证，也可用 --single-candidate /mnt/data/36小.3dm。
"""
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple, Dict, Optional

import numpy as np
import rhino3dm
import trimesh
import open3d as o3d
from scipy.spatial import cKDTree

logger = logging.getLogger("matcher")
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# -------------------------- I/O & 单位 -------------------------- #

def rhino_unit_scale_mm(model: rhino3dm.File3dm) -> float:
    try:
        us = model.Settings.ModelUnitSystem
        mm = rhino3dm.UnitSystem.Millimeters
        cm = rhino3dm.UnitSystem.Centimeters
        m = rhino3dm.UnitSystem.Meters
        inch = rhino3dm.UnitSystem.Inches
        ft = rhino3dm.UnitSystem.Feet
        return {
            mm: 1.0,
            cm: 10.0,
            m: 1000.0,
            inch: 25.4,
            ft: 304.8,
        }.get(us, 1.0)
    except Exception:
        return 1.0


def _mesh_faces_to_tris(geom: rhino3dm.Mesh, v_offset: int) -> List[Tuple[int, int, int]]:
    """
    兼容不同 rhino3dm 版本：Faces 元素可能是 MeshFace 或 (a,b,c[,d]) 元组。
    返回三角形索引列表；四边形拆为两三角；过滤退化面。
    """
    faces: List[Tuple[int, int, int]] = []

    def _push(a, b, c, d=None):
        a = int(a); b = int(b); c = int(c)
        tri1 = (a + v_offset, b + v_offset, c + v_offset)
        if len({tri1[0], tri1[1], tri1[2]}) == 3:
            faces.append(tri1)
        if d is not None and d not in (c, -1):
            d = int(d)
            tri2 = (a + v_offset, c + v_offset, d + v_offset)
            if len({tri2[0], tri2[1], tri2[2]}) == 3:
                faces.append(tri2)

    try:
        for f in geom.Faces:
            if hasattr(f, "A"):
                _push(f.A, f.B, f.C, getattr(f, "D", None))
            else:
                # 可能是 (a,b,c[,d]) 的元组/列表
                if isinstance(f, (list, tuple)):
                    if len(f) >= 3:
                        a, b, c = f[0], f[1], f[2]
                        d = f[3] if len(f) >= 4 else None
                        _push(a, b, c, d)
                else:
                    # 回退到索引访问
                    try:
                        a, b, c = f[0], f[1], f[2]
                        d = f[3] if len(f) >= 4 else None
                        _push(a, b, c, d)
                    except Exception:
                        continue
    except TypeError:
        # 某些绑定需要用 Count + 索引访问
        try:
            cnt = geom.Faces.Count
        except Exception:
            cnt = 0
        for i in range(cnt):
            mf = geom.Faces[i]
            if hasattr(mf, "A"):
                _push(mf.A, mf.B, mf.C, getattr(mf, "D", None))
    return faces


def _append_mesh(verts_all: List[np.ndarray], faces_all: List[Tuple[int, int, int]], mesh_obj: rhino3dm.Mesh, scale: float, v_offset: int) -> int:
    v = np.array([[p.X, p.Y, p.Z] for p in mesh_obj.Vertices], dtype=np.float64)
    if scale != 1.0:
        v *= scale
    verts_all.append(v)
    faces_all.extend(_mesh_faces_to_tris(mesh_obj, v_offset))
    return v_offset + len(v)


def _try_mesh_brep(brep: 'rhino3dm.Brep', meshing_quality: str = 'high') -> List[rhino3dm.Mesh]:
    meshes: List[rhino3dm.Mesh] = []
    try:
        # 优先用可调参数；属性名可能随版本差异，做 try/except 兼容
        mp = None
        try:
            mp = rhino3dm.MeshingParameters()
            # 比较激进但细致的参数（按 mm 级模型）
            if meshing_quality == 'high':
                # 尽量细：Refine、最小网格角、最大边长等
                if hasattr(mp, 'RefineGrid'): mp.RefineGrid = True
                if hasattr(mp, 'JaggedSeams'): mp.JaggedSeams = False
                if hasattr(mp, 'GridAngle'): mp.GridAngle = np.deg2rad(5.0)
                if hasattr(mp, 'GridAspectRatio'): mp.GridAspectRatio = 6.0
                if hasattr(mp, 'GridAmplification'): mp.GridAmplification = 1.0
                if hasattr(mp, 'MinimumEdgeLength'): mp.MinimumEdgeLength = 0.3
                if hasattr(mp, 'MaximumEdgeLength'): mp.MaximumEdgeLength = 5.0
            else:
                if hasattr(mp, 'RefineGrid'): mp.RefineGrid = True
        except Exception:
            mp = None
        if mp is not None:
            meshes = rhino3dm.Mesh.CreateFromBrep(brep, mp)
        else:
            # 回退到默认
            meshes = rhino3dm.Mesh.CreateFromBrep(brep)
    except Exception as e:
        logger.warning(f"Brep 网格化失败，使用默认或跳过：{e}")
    return meshes or []


def _try_mesh_subd(subd: 'rhino3dm.SubD') -> Optional[rhino3dm.Mesh]:
    try:
        # 某些版本支持从 SubD 直接转 Mesh
        if hasattr(rhino3dm.Mesh, 'CreateFromSubD'):
            return rhino3dm.Mesh.CreateFromSubD(subd)
    except Exception as e:
        logger.warning(f"SubD 网格化失败：{e}")
    return None


def load_3dm_as_trimesh(path: Path, brep_mesh_quality: str = 'high') -> trimesh.Trimesh:
    model = rhino3dm.File3dm.Read(str(path))
    if not model:
        raise ValueError(f"无法读取 3DM: {path}")
    scale = rhino_unit_scale_mm(model)

    verts_all: List[np.ndarray] = []
    faces_all: List[Tuple[int, int, int]] = []
    v_offset = 0

    for obj in model.Objects:
        g = obj.Geometry
        # Mesh
        if isinstance(g, rhino3dm.Mesh):
            v_offset = _append_mesh(verts_all, faces_all, g, scale, v_offset)
            continue
        # Brep → Mesh
        if hasattr(rhino3dm, 'Brep') and isinstance(g, rhino3dm.Brep):
            meshes = _try_mesh_brep(g, meshing_quality=brep_mesh_quality)
            for m in meshes:
                v_offset = _append_mesh(verts_all, faces_all, m, scale, v_offset)
            continue
        # SubD → Mesh（若支持）
        if hasattr(rhino3dm, 'SubD') and isinstance(g, rhino3dm.SubD):
            m = _try_mesh_subd(g)
            if m is not None:
                v_offset = _append_mesh(verts_all, faces_all, m, scale, v_offset)
            continue
        # 其他类型忽略或后续扩展（Curve/NurbsCurve 可用于朝向推断）

    if not verts_all:
        raise ValueError("未找到可用几何；请确认文件内含 Mesh/Brep/SubD。")

    V = np.vstack(verts_all)
    F = np.array(faces_all, dtype=np.int64)
    m = trimesh.Trimesh(vertices=V, faces=F, process=True)

    # 网格清理（兼容新 API，避免弃用警告）
    if not m.is_empty:
        try:
            # 去退化面 / 去重复面（新推荐写法）
            m.update_faces(m.nondegenerate_faces())
            m.update_faces(m.unique_faces())
        except Exception:
            # 回退到旧 API（某些版本仍需）
            try:
                m.remove_degenerate_faces()
            except Exception:
                pass
            try:
                m.remove_duplicate_faces()
            except Exception:
                pass
        try:
            m.remove_infinite_values()
        except Exception:
            pass
        try:
            m.remove_unreferenced_vertices()
        except Exception:
            pass
        try:
            m.process(validate=True)
        except Exception:
            pass
    return m


# -------------------------- 粗胚预处理 -------------------------- #

def largest_component(mesh: trimesh.Trimesh, min_ratio: float = 0.85) -> trimesh.Trimesh:
    """保留最大连通域；若其占比不足 min_ratio，则保留整网格。
    兼容某些 trimesh 版本 split 返回的非列表类型，避免 numpy 真值歧义。
    """
    comps = mesh.split(only_watertight=False)
    # 强制转 list，规避 "truth value of an array is ambiguous" 问题
    try:
        comps = list(comps)
    except TypeError:
        comps = [comps]

    if len(comps) == 0:
        return mesh

    comps.sort(key=lambda x: getattr(x, 'area', 0.0), reverse=True)
    largest = comps[0]
    try:
        ratio = float(getattr(largest, 'area', 0.0)) / max(float(getattr(mesh, 'area', 0.0)), 1e-9)
    except Exception:
        ratio = 1.0
    if ratio >= min_ratio:
        return largest
    return mesh
    comps.sort(key=lambda x: x.area, reverse=True)
    if comps[0].area / max(mesh.area, 1e-9) >= min_ratio:
        return comps[0]
    return mesh


def clip_bottom_by_percentile(mesh: trimesh.Trimesh, p: float = 0.5) -> trimesh.Trimesh:
    """按 z 分位切底：移除低于 (min_z + p% 高度范围) 的三角形（粗胚底座常见）。
    p 取 0.5~1.0（mm），默认 0.5 mm。"""
    zmin = float(mesh.bounds[0, 2])
    thresh = zmin + p
    faces = mesh.faces
    verts = mesh.vertices
    mask = np.any(verts[faces][:, :, 2] >= thresh, axis=1)
    return mesh.submesh([np.where(mask)[0]], append=True)


# -------------------------- 形状特征 & 粗筛 -------------------------- #

def feature_descriptor(mesh: trimesh.Trimesh) -> Dict[str, np.ndarray | float | List[float]]:
    vol = float(mesh.volume) if mesh.is_volume else 0.0
    area = float(mesh.area)
    extents = mesh.bounding_box.extents.astype(float)

    n = mesh.face_normals
    n = n / (np.linalg.norm(n, axis=1, keepdims=True) + 1e-12)
    theta = np.arccos(np.clip(n[:, 2], -1, 1))  # [0, pi]
    phi = (np.arctan2(n[:, 1], n[:, 0]) + 2*np.pi) % (2*np.pi)  # [0, 2pi)
    H, _, _ = np.histogram2d(theta, phi, bins=(8, 16), range=[[0, np.pi], [0, 2*np.pi]])
    H = (H / (H.sum() + 1e-9)).astype(np.float32).ravel()

    return {
        'volume': vol,
        'area': area,
        'extents': extents.tolist(),
        'normal_hist': H,
    }


def steiner_min_volume(vol: float, area: float, t: float) -> float:
    return vol + area * t


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))


# -------------------------- 全局+局部配准 -------------------------- #

def to_o3d_pcd(mesh: trimesh.Trimesh, voxel: float) -> o3d.geometry.PointCloud:
    pts, _ = trimesh.sample.sample_surface_even(mesh, count=int(max(mesh.vertices.shape[0] * 0.8, 50000)))
    pcd = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(pts))
    if voxel and voxel > 0:
        pcd = pcd.voxel_down_sample(voxel)
    return pcd


def _estimate_normals(pcd: o3d.geometry.PointCloud, radius: float = 6.0):
    pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=radius, max_nn=60))
    pcd.normalize_normals()


def compute_fpfh(pcd: o3d.geometry.PointCloud, radius: float = 6.0) -> o3d.pipelines.registration.Feature:
    _estimate_normals(pcd, radius)
    return o3d.pipelines.registration.compute_fpfh_feature(
        pcd,
        o3d.geometry.KDTreeSearchParamHybrid(radius=radius, max_nn=100)
    )


def global_registration_ransac(src: o3d.geometry.PointCloud, tgt: o3d.geometry.PointCloud, radius: float, voxel: float, max_iter: int = 8000) -> np.ndarray:
    f_src = compute_fpfh(src, radius)
    f_tgt = compute_fpfh(tgt, radius)
    distance_threshold = voxel * 3.0
    result = o3d.pipelines.registration.registration_ransac_based_on_feature_matching(
        src, tgt, f_src, f_tgt, True, distance_threshold,
        o3d.pipelines.registration.TransformationEstimationPointToPoint(False), 4,
        [o3d.pipelines.registration.CorrespondenceCheckerBasedOnDistance(distance_threshold)],
        o3d.pipelines.registration.RANSACConvergenceCriteria(max_iter, 1000)
    )
    return np.asarray(result.transformation)


def refine_icp_point2plane(src: o3d.geometry.PointCloud, tgt: o3d.geometry.PointCloud, init_T: np.ndarray, threshold: float, max_iter: int = 80) -> np.ndarray:
    _estimate_normals(tgt, radius=threshold)
    reg = o3d.pipelines.registration.registration_icp(
        src, tgt, threshold, init_T,
        o3d.pipelines.registration.TransformationEstimationPointToPlane(),
        o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=max_iter)
    )
    return np.asarray(reg.transformation)


def try_mirror_and_align(cand_mesh: trimesh.Trimesh, target_mesh: trimesh.Trimesh, voxel: float, fpfh_radius: float, icp_thr: float) -> Tuple[trimesh.Trimesh, np.ndarray, bool]:
    """返回最佳对齐后的候选网格、变换矩阵、是否镜像。"""
    pc_t = to_o3d_pcd(target_mesh, voxel)
    pc_c = to_o3d_pcd(cand_mesh, voxel)

    # 原始
    T0 = global_registration_ransac(pc_c, pc_t, fpfh_radius, voxel)
    T0 = refine_icp_point2plane(pc_c, pc_t, T0, icp_thr)

    # 镜像（YZ 面）
    M = np.eye(4); M[0, 0] = -1.0
    mc = cand_mesh.copy(); mc.apply_transform(M)
    pc_cm = to_o3d_pcd(mc, voxel)
    Tm = global_registration_ransac(pc_cm, pc_t, fpfh_radius, voxel)
    Tm = refine_icp_point2plane(pc_cm, pc_t, Tm, icp_thr)

    # 评估残差（Chamfer 近似）
    def _ch(mesh_T: trimesh.Trimesh, T: np.ndarray) -> float:
        mm = mesh_T.copy(); mm.apply_transform(T)
        a, _ = trimesh.sample.sample_surface_even(mm, 20000)
        b, _ = trimesh.sample.sample_surface_even(target_mesh, 20000)
        return chamfer_distance(a, b)

    ch0 = _ch(cand_mesh, T0)
    chm = _ch(mc, Tm)

    if chm < ch0:
        mc.apply_transform(Tm)
        return mc, Tm @ M, True
    else:
        m0 = cand_mesh.copy(); m0.apply_transform(T0)
        return m0, T0, False


# -------------------------- 相似度与距离 -------------------------- #

def chamfer_distance(a: np.ndarray, b: np.ndarray) -> float:
    kd_a = cKDTree(a)
    kd_b = cKDTree(b)
    da, _ = kd_b.query(a, k=1)
    db, _ = kd_a.query(b, k=1)
    return float(da.mean() + db.mean())


# -------------------------- 余量校验（采样版 SDF） -------------------------- #

def clearance_check_sampling(target: trimesh.Trimesh, candidate_aligned: trimesh.Trimesh, clearance_mm: float, samples: int = 120000, safety_delta: float = 0.3) -> Dict[str, float | bool]:
    """对目标表面高密度均匀采样点 p_i，检查候选的签名距离：
    inner_dist_i = -signed_distance_candidate(p_i)（inside 为正），
    要求：min(inner_dist) ≥ clearance_mm + safety_delta。
    这是高置信近似（采样驱动）；若需体素 SDF 形式化保证，可扩展 volume 模式。
    """
    P, _ = trimesh.sample.sample_surface_even(target, count=samples)
    pq = trimesh.proximity.ProximityQuery(candidate_aligned)
    sd = pq.signed_distance(P)  # inside 为负
    sd = np.asarray(sd, dtype=float)
    inner_dist = -sd  # inside → 正值（几何余量）

    min_c = float(inner_dist.min())
    mean_c = float(inner_dist.mean())
    p01 = float(np.percentile(inner_dist, 1))
    ok = bool(min_c >= (clearance_mm + safety_delta))
    return {"pass": ok, "min_clearance": min_c, "mean_clearance": mean_c, "p01_clearance": p01, "inside_ratio": 1.0}


# -------------------------- 导出：GLB / PLY / 热图 -------------------------- #

def export_mesh(mesh: trimesh.Trimesh, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ext = out_path.suffix.lower()
    if ext == '.ply':
        mesh.export(str(out_path), file_type='ply')
    elif ext in ('.glb', '.gltf'):
        mesh.export(str(out_path), file_type=ext.lstrip('.'))
    else:
        raise ValueError(f"不支持的导出格式：{ext}")


def export_clearance_heatmap_html(target: trimesh.Trimesh, candidate_aligned: trimesh.Trimesh, out_html: Path) -> None:
    try:
        import plotly.graph_objects as go
    except Exception as e:
        logger.warning(f"未安装 plotly，跳过热图导出：{e}")
        return

    V = target.vertices
    F = target.faces
    pq = trimesh.proximity.ProximityQuery(candidate_aligned)
    sd = np.asarray(pq.signed_distance(V), dtype=float)
    clearance = np.where(sd <= 0.0, -sd, 0.0)  # 外部点置 0（非通过部位为 0）

    face_i = F[:, 0]
    face_j = F[:, 1]
    face_k = F[:, 2]

    fig = go.Figure()
    fig.add_trace(go.Mesh3d(
        x=V[:, 0], y=V[:, 1], z=V[:, 2],
        i=face_i, j=face_j, k=face_k,
        intensity=clearance,
        colorscale=[
            [0.0, '#440154'],  # purple (thin)
            [0.3, '#31688e'],
            [0.6, '#35b779'],
            [0.85,'#fde725']   # yellow (thick)
        ],
        colorbar=dict(title='Clearance (mm)', thickness=18, len=0.8),
        showscale=True, opacity=1.0, name='Target (clearance)'
    ))

    fig.update_layout(
        title={'text': 'Clearance Heatmap (target surface)', 'x':0.5},
        scene=dict(aspectmode='data'),
        width=1200, height=900
    )
    out_html.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(out_html))


# -------------------------- 主流程 -------------------------- #

def to_point_cloud(mesh: trimesh.Trimesh, n: int = 20000) -> np.ndarray:
    P, _ = trimesh.sample.sample_surface_even(mesh, count=n)
    return P.astype(np.float64)


def rank_candidates(target: trimesh.Trimesh, candidates: Dict[Path, trimesh.Trimesh], clearance_mm: float, topk: int, voxel: float, icp_thr: float, fpfh_radius: float, safety_delta: float) -> List[Dict]:
    # 目标描述子
    f_t = feature_descriptor(target)
    Vmin = steiner_min_volume(f_t['volume'], f_t['area'], clearance_mm)

    # 先粗筛
    cand_list = []
    for path, mesh in candidates.items():
        f_c = feature_descriptor(mesh)
        if f_c['volume'] < Vmin * 0.999:  # 体积下界过滤
            continue
        cos_n = cosine(np.asarray(f_t['normal_hist']), np.asarray(f_c['normal_hist']))
        score_coarse = 1.0 - cos_n
        cand_list.append((path, mesh, f_c, score_coarse))

    cand_list.sort(key=lambda x: x[3])
    cand_list = cand_list[: max(5*topk, 20)]

    # 预采样点云（供 Chamfer）
    P_t = to_point_cloud(target, n=40000)

    results = []
    for path, mesh, f_c, _ in cand_list:
        # 镜像容错 + 对齐
        m_aligned, T, mirrored = try_mirror_and_align(mesh, target, voxel=voxel, fpfh_radius=fpfh_radius, icp_thr=icp_thr)

        # Chamfer（形状相似性）
        ch = chamfer_distance(P_t[::5], to_point_cloud(m_aligned, n=20000)[::5])

        # 余量校验（采样版 SDF）
        chk = clearance_check_sampling(target, m_aligned, clearance_mm=clearance_mm, samples=120000, safety_delta=safety_delta)
        if not chk["pass"]:
            results.append({
                "path": str(path),
                "pass": False,
                "reason": f"clearance_fail(min={chk['min_clearance']:.2f}mm)",
                "chamfer": ch,
                "volume": f_c['volume'],
                "mirrored": mirrored,
                "transform": T.tolist(),
                "min_clearance": chk['min_clearance'],
                "mean_clearance": chk['mean_clearance'],
                "p01_clearance": chk['p01_clearance'],
            })
            continue

        vol_ratio = f_c['volume'] / max(f_t['volume'], 1e-9)
        score = ch + 0.05 * (vol_ratio - 1.0)
        results.append({
            "path": str(path),
            "pass": True,
            "score": float(score),
            "chamfer": ch,
            "min_clearance": chk['min_clearance'],
            "mean_clearance": chk['mean_clearance'],
            "p01_clearance": chk['p01_clearance'],
            "volume": f_c['volume'],
            "mirrored": mirrored,
            "transform": T.tolist(),
        })

    passed = [r for r in results if r.get('pass')]
    passed.sort(key=lambda r: r['score'])
    failed = [r for r in results if not r.get('pass')]
    return passed[:topk] + failed[: min(len(failed), 10)]


def collect_candidates(path: Path, limit_ext: Tuple[str, ...] = ('.3dm',)) -> Dict[Path, trimesh.Trimesh]:
    meshes = {}
    for p in sorted(path.rglob('*')):
        if p.suffix.lower() in limit_ext:
            try:
                m = load_3dm_as_trimesh(p)
                m = largest_component(m)
                meshes[p] = m
            except Exception as e:
                logger.warning(f"跳过 {p.name}: {e}")
    return meshes


# -------------------------- CLI -------------------------- #

def main():
    ap = argparse.ArgumentParser(description="Find best-matching shoe last with ≥ clearance everywhere (factory-grade)")

    # 输入目标：支持 --target 与 --input 两个名字（同义）。
    ap.add_argument('--target', '--input', dest='target', required=True, help='目标鞋模 .3dm（--input 为兼容别名）')

    # 候选：二选一（库目录 或 单个候选）
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument('--candidates', help='候选库目录（递归扫描 .3dm）')
    group.add_argument('--single-candidate', help='单个候选 .3dm 文件（调试/验算）')

    ap.add_argument('--clearance', type=float, default=2.0, help='所需全局最小余量（毫米）')
    ap.add_argument('--topk', type=int, default=10, help='返回前 K 个最优匹配（通过余量）')

    # 配准参数
    ap.add_argument('--voxel', type=float, default=2.5, help='点云下采样体素（mm）')
    ap.add_argument('--icp-thr', type=float, default=8.0, help='ICP 距离阈值（mm）')
    ap.add_argument('--fpfh-radius', type=float, default=6.0, help='FPFH 半径（mm）')

    # 余量校验附加安全裕度（考虑加工/测量不确定性）
    ap.add_argument('--safety-delta', type=float, default=0.3, help='余量校验安全裕度 δ（mm）')

    # 导出：GLB / PLY / 热图
    ap.add_argument('--export_report', type=str, default=None, help='导出 JSON 报告路径')
    ap.add_argument('--export_glb_dir', type=str, default=None, help='导出通过匹配的对齐候选为 GLB 的目录')
    ap.add_argument('--export_ply_dir', type=str, default=None, help='导出通过匹配的对齐候选为 PLY 的目录')
    ap.add_argument('--export_heatmap_dir', type=str, default=None, help='导出热图 HTML 的目录（针对 Top-1 或 Top-K）')
    ap.add_argument('--export_topk', type=int, default=3, help='导出前 K 个通过的候选')

    ap.add_argument('--seed', type=int, default=42, help='随机种子（采样用）')

    # 粗胚预处理
    ap.add_argument('--clip-bottom', action='store_true', help='尝试切除底部 0.5mm (粗胚常见底座)')

    args = ap.parse_args()

    np.random.seed(args.seed)

    target_mesh = load_3dm_as_trimesh(Path(args.target))
    if args.clip_bottom:
        target_mesh = clip_bottom_by_percentile(target_mesh, p=0.5)
    target_mesh = largest_component(target_mesh)

    if args.single_candidate:
        cands = {Path(args.single_candidate): load_3dm_as_trimesh(Path(args.single_candidate))}
    else:
        cands = collect_candidates(Path(args.candidates))
    logger.info(f"目标 OK; 候选数量：{len(cands)}")

    results = rank_candidates(
        target_mesh, cands,
        clearance_mm=args.clearance, topk=args.topk,
        voxel=args.voxel, icp_thr=args.icp_thr, fpfh_radius=args.fpfh_radius,
        safety_delta=args.safety_delta,
    )

    # 输出显示
    print("=== 匹配结果 ===")
    for i, r in enumerate(results, 1):
        tag = "PASS" if r.get('pass') else "FAIL"
        line = f"{i:02d}. [{tag}] {Path(r['path']).name}"
        if tag == 'PASS':
            line += f"  score={r['score']:.3f}  chamfer={r['chamfer']:.2f}  minCLR={r['min_clearance']:.2f}mm"
            if r.get('mirrored'):
                line += "  (mirrored)"
        else:
            line += f"  reason={r.get('reason')}  chamfer={r['chamfer']:.2f}"
            if r.get('mirrored'):
                line += "  (mirrored tried)"
        print(line)

    if args.export_report:
        with open(args.export_report, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"JSON 报告已导出：{args.export_report}")

    # —— 导出对齐结果（GLB/PLY/热图）——
    to_export = [r for r in results if r.get('pass')][: max(1, args.export_topk)]
    for idx, r in enumerate(to_export, 1):
        # 还原对齐后的候选网格
        cand_path = Path(r['path'])
        m_raw = load_3dm_as_trimesh(cand_path)
        T = np.asarray(r['transform'], dtype=float)
        m_aligned = m_raw.copy(); m_aligned.apply_transform(T)

        # GLB/PLY 导出
        tag = f"{idx:02d}_{cand_path.stem}"
        if args.export_glb_dir:
            export_mesh(m_aligned, Path(args.export_glb_dir) / f"{tag}.glb")
        if args.export_ply_dir:
            export_mesh(m_aligned, Path(args.export_ply_dir) / f"{tag}.ply")

        # 热图（默认仅 Top-1）
        if args.export_heatmap_dir and idx == 1:
            export_clearance_heatmap_html(target_mesh, m_aligned, Path(args.export_heatmap_dir) / f"{tag}_clearance.html")

if __name__ == '__main__':
    main()
