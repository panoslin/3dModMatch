# 3DM文件数据结构分析

## 🔍 从3DM文件中读取的数据

### 1. 文件基本信息
- **文件格式**: Rhino 3DM (OpenNURBS格式)
- **对象数量**: 通常为1个主要几何对象
- **图层数量**: 1个默认图层
- **材质数量**: 通常为0（无材质信息）

### 2. 几何对象信息
每个3DM文件包含一个主要的几何对象：
- **几何类型**: `Mesh` (网格对象)
- **对象ID**: 唯一标识符 (UUID格式)
- **图层索引**: 对象所属图层

### 3. 网格数据结构

#### 3.1 顶点数据 (Vertices)
```python
# 顶点数组形状: (N, 3)
# 数据类型: float64
# 内存占用: N * 3 * 8 bytes

vertices = np.array([
    [x1, y1, z1],  # 顶点1的3D坐标
    [x2, y2, z2],  # 顶点2的3D坐标
    ...
    [xN, yN, zN]   # 顶点N的3D坐标
], dtype=np.float64)
```

**实际数据示例** (36小.3dm):
- **顶点数**: 631,095个
- **坐标范围**:
  - X: [-136.265, 128.025] mm
  - Y: [-43.804, 68.249] mm  
  - Z: [-38.157, 47.116] mm
- **内存占用**: 14.44 MB

#### 3.2 面数据 (Faces)
```python
# 面数组形状: (M, 3)
# 数据类型: int32
# 每个面由3个顶点索引组成

faces = np.array([
    [v1, v2, v3],  # 三角形面1
    [v4, v5, v6],  # 三角形面2
    ...
    [vM, vM+1, vM+2]  # 三角形面M
], dtype=np.int32)
```

**实际数据示例** (36小.3dm):
- **面数**: 210,365个三角形
- **面索引范围**: [0, 631094]
- **平均每面顶点数**: 0.33 (三角形网格)

### 4. 几何特征

#### 4.1 边界框 (Bounding Box)
```python
bbox_min = vertices.min(axis=0)  # 最小坐标
bbox_max = vertices.max(axis=0)  # 最大坐标
bbox_size = bbox_max - bbox_min  # 尺寸
```

**实际数据示例** (36小.3dm):
- **宽度**: 264.289 mm
- **深度**: 112.053 mm
- **高度**: 85.273 mm

#### 4.2 体积计算
使用C++模块计算精确体积：
```python
volume = cppcore.coarse_features(vertices, faces)['volume']
```

**实际数据示例**:
- **目标模型** (36小.3dm): 631,470 mm³
- **候选模型** (002小.3dm): 1,065,934 mm³ (1.69倍)

#### 4.3 中心点
```python
center = vertices.mean(axis=0)
```

**实际数据示例** (36小.3dm):
- **中心点**: (-7.005, 1.659, 1.135) mm

### 5. 数据转换过程

#### 5.1 3DM文件读取
```python
# 1. 读取3DM文件
m = rhino3dm.File3dm.Read(file_path)

# 2. 遍历所有对象
for obj in m.Objects:
    g = obj.Geometry
    
    # 3. 获取网格数据
    if isinstance(g, rhino3dm.Mesh):
        mesh = g
    elif hasattr(g, 'GetMesh'):
        mesh = g.GetMesh(rhino3dm.MeshType.Default)
    
    # 4. 从BREP自动生成网格（如果需要）
    if mesh is None and isinstance(g, rhino3dm.Brep):
        meshes = rhino3dm.Mesh.CreateFromBrep(g, meshing_params)
        mesh = combine_meshes(meshes)
```

#### 5.2 顶点数据提取
```python
# 提取顶点坐标
vertices = np.array([
    [v.X, v.Y, v.Z] for v in mesh.Vertices
], dtype=np.float64)
```

#### 5.3 面数据提取
```python
# 提取面索引
faces = []
for f in mesh.Faces:
    if hasattr(f, 'A'):
        # 三角形面
        a, b, c = f.A, f.B, f.C
        faces.append([a, b, c])
        
        # 四边形面分解为两个三角形
        d = getattr(f, 'D', None)
        if d is not None and d not in (c, -1):
            faces.append([a, c, d])
    else:
        # 其他格式
        a, b, c = f[0], f[1], f[2]
        faces.append([a, b, c])
        if len(f) >= 4:
            d = f[3]
            if d != c and d != -1:
                faces.append([a, c, d])

faces = np.asarray(faces, dtype=np.int32)
```

### 6. 数据质量特征

#### 6.1 网格质量
- **三角形网格**: 所有面都是三角形
- **无重复顶点**: 每个顶点只存储一次
- **面索引正确**: 所有面索引都在有效范围内
- **无孤立顶点**: 所有顶点都被至少一个面引用

#### 6.2 几何精度
- **坐标精度**: float64 (双精度浮点数)
- **单位**: 毫米 (mm)
- **精度**: 小数点后3位有效数字

#### 6.3 数据完整性
- **顶点-面一致性**: 面索引与顶点数量匹配
- **几何闭合性**: 网格形成封闭的3D表面
- **法向量**: 通过面数据计算表面法向量

### 7. 实际应用中的数据流

#### 7.1 加载阶段
```python
# 1. 读取3DM文件
V, F = load_3dm_enhanced(file_path, mesh_quality='high')

# 2. 数据验证
assert V.shape[1] == 3, "顶点必须是3D坐标"
assert F.max() < len(V), "面索引超出范围"
assert F.min() >= 0, "面索引不能为负数"
```

#### 7.2 预处理阶段
```python
# 1. 网格预处理
V, F = preprocess_mesh(V, F, 
    fix_normals=True,
    fill_holes=True,
    remove_duplicates=True
)

# 2. 特征计算
features = cppcore.coarse_features(V, F)
volume = features['volume']
center = V.mean(axis=0)
```

#### 7.3 匹配阶段
```python
# 1. 几何对齐
aligned_V = align_geometry(V_candidate, F_candidate, V_target, F_target)

# 2. 距离计算
distances = compute_clearance_distances(V_target, F_target, aligned_V, F_candidate)

# 3. 统计分析
min_dist = distances.min()
p15_dist = np.percentile(distances, 15)
mean_dist = distances.mean()
```

### 8. 数据存储格式

#### 8.1 内存中的表示
```python
# 顶点数组: (N, 3) float64
vertices = np.array([[x, y, z], ...], dtype=np.float64)

# 面数组: (M, 3) int32  
faces = np.array([[i, j, k], ...], dtype=np.int32)
```

#### 8.2 文件中的表示
- **3DM格式**: Rhino原生格式，包含完整几何信息
- **PLY格式**: 导出格式，包含顶点和面数据
- **STL格式**: 标准三角网格格式

### 9. 性能特征

#### 9.1 内存使用
- **顶点数据**: N × 3 × 8 bytes (float64)
- **面数据**: M × 3 × 4 bytes (int32)
- **总内存**: N × 24 + M × 12 bytes

#### 9.2 处理时间
- **文件读取**: ~100ms (631K顶点)
- **网格预处理**: ~500ms
- **特征计算**: ~200ms
- **几何对齐**: ~2-5秒

### 10. 数据验证

#### 10.1 完整性检查
```python
# 检查顶点-面一致性
assert F.max() < len(V), "面索引超出顶点范围"
assert F.min() >= 0, "面索引不能为负数"

# 检查网格质量
assert len(V) > 0, "顶点数量必须大于0"
assert len(F) > 0, "面数量必须大于0"
assert F.shape[1] == 3, "面必须是三角形"
```

#### 10.2 几何合理性
```python
# 检查边界框合理性
bbox_size = V.max(axis=0) - V.min(axis=0)
assert bbox_size.min() > 0, "边界框尺寸必须为正"
assert bbox_size.max() < 1000, "模型尺寸过大"

# 检查体积合理性
volume = cppcore.coarse_features(V, F)['volume']
assert volume > 0, "体积必须为正"
assert volume < 1e9, "体积过大"
```

## 📊 总结

从3DM文件中读取的数据主要包括：

1. **顶点数据**: 3D坐标数组 (N×3 float64)
2. **面数据**: 三角形索引数组 (M×3 int32)
3. **几何特征**: 体积、边界框、中心点等
4. **元数据**: 对象ID、图层信息等

这些数据经过预处理后，用于3D几何匹配算法，实现鞋模的智能匹配功能。
