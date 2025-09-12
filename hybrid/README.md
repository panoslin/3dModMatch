# Shoe Last Matcher — Hybrid Python + C++17 (v0.5)

高性能鞋模匹配与余量校验工具。采用 **Python 调度 + C++17（Open3D）内核** 的混合架构，在保证精度的同时显著提升吞吐。

## ✨ 功能
- **加载**：支持 `.3dm`（建议带渲染网格）、`.ply`、`.obj`、`.stl`
- **配准**：FPFH + RANSAC（全局） → Point-to-Plane ICP（局部）
- **相似度**：Chamfer 距离
- **余量校验（快速）**：采样式 SDF（RaycastingScene）
- **形式化复核（严谨）**：窄带体素 SDF，给出误差上界 `eps ≤ 0.866 × voxel`
- **镜像容错**：自动尝试 YZ 镜像（左右脚）
- **诊断**：最薄点定位、薄壁段聚类与 **toe/heel × medial/lateral** 语义标注
- **剖切**：任意平面与网格相交输出线段，Python 侧生成交互式 HTML
- **并行**：批量候选的对齐与校验

## 📦 目录结构
```
3dModMatch/
├── CMakeLists.txt
├── pyproject.toml
├── cpp/
│   └── bindings.cpp
├── python/
│   └── hybrid_matcher.py
└── README.md
```
> 你还需要配套的 `python/hybrid_matcher.py`（调用 `cppcore` 的 Python 脚本）。若缺失，可按我之前提供的 v0.5 版本放入该路径。

## 🔧 依赖
- Ubuntu（建议 20.04/22.04）
- Open3D ≥ 0.18（含 `t.geometry.RaycastingScene`）
- pybind11、Eigen3、Ninja
- Python 包：`numpy`, `trimesh`, `rhino3dm`, `plotly`, `open3d`

安装示例：
```bash
sudo apt-get update
sudo apt-get install -y libopen3d-dev libeigen3-dev ninja-build
python -m pip install -U scikit-build-core pybind11 numpy trimesh rhino3dm plotly open3d
```

## 🏗️ 构建与安装

在项目根目录执行：

`python -m pip install -v .`

完成后会生成并安装 cppcore Python 扩展模块。

如需开启 OpenMP 并行，确保系统 Open3D 启用了并行后端；CMakeLists.txt 会自动链接。

🚀 使用（示例）

假设你准备了：
- 目标鞋模：models/36小.3dm
- 候选目录：candidates/

运行（示例 CLI 在 python/hybrid_matcher.py 中实现）：
```bash
python python/hybrid_matcher.py \
  --target models/36小.3dm \
  --candidates candidates/ \
  --clearance 2.0 \
  --voxel 2.5 --icp-thr 8.0 --fpfh-radius 6.0 \
  --topk 10 --safety-delta 0.3 --samples 120000 --threads -1 \
  --sdf-volume-check --voxel-size 0.30 --band-mm 8.0 \
  --export_report output/match_report.json
```
📄 输出
- match_report.json：每个候选包含 pass / chamfer / min_clearance / mean_clearance / mirrored / transform；若启用形式化复核，带 eps 与 pass 结果
- 可选：对齐后的 PLY/GLB、余量热图（顶点着色 PLY）、剖切 HTML（由 Python 侧导出）

🧠 参数建议
- 生产校验：--sdf-volume-check --voxel-size 0.30 --band-mm 8.0
- 薄壁诊断：--thin-threshold 2.3 --thin-cluster-mm 12
- 并行：--threads -1（交给 Open3D/OMP 自适应）

⚠️ 注意事项
- .3dm 若只有 Brep 而没有渲染网格，openNURBS 并不自带三角化；建议在 Rhino 导出时附带 Mesh。后续可接入 libigl/CGAL 做曲面网格化（WITH_IGL 预留开关）。
- GLB 导出能力取决于你的 Open3D 构建；不支持时用 PLY/OBJ 替代。

📎 接口速览（cppcore）
- coarse_features(V,F) -> dict
- align_icp(Vs,Fs, Vt,Ft, voxel, fpfh_radius, icp_thr) -> {T, chamfer}
- align_icp_with_mirror(...) -> {T, chamfer, mirrored}
- clearance_sampling(Vt,Ft, Vc,Fc, clearance, safety_delta, samples) -> {...}
- batch_align_and_check(Vt,Ft, [V],[F], voxel, radius, thr, clearance, delta, samples, threads) -> list[dict]
- clearance_sdf_volume(Vt,Ft, Vc,Fc, clearance, voxel, band, threads) -> {...}
- batch_formal_check(...) -> list[dict]
- min_clearance_point(Vt,Ft, Vc,Fc) -> {found, min_clearance, p_target, p_candidate, index}
- mesh_section(V,F, p0(3), nrm(3)) -> {segments:(N,6)}
- thin_regions(Vt,Ft, Vc,Fc, thr_mm, radius_mm) -> list
- label_regions(Vt, regions) -> list
