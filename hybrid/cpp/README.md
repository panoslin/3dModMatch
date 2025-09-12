# C++ Core Module for Shoe Last Matcher

## Overview

The `bindings.cpp` file contains the high-performance C++ implementation of core algorithms for the shoe last matching system, exposed to Python via pybind11.

## Dependencies

- **Open3D** >= 0.18 - 3D geometry processing
- **Eigen3** - Linear algebra
- **pybind11** - Python bindings
- **OpenMP** (optional) - Parallel processing

## Key Functions

### 1. Mesh Processing
- `mesh_from_np()` - Convert NumPy arrays to Open3D mesh
- `sample_pcd()` - Sample point cloud from mesh
- `est_normals()` - Estimate point cloud normals

### 2. Registration & Alignment
- `align_icp()` - RANSAC + ICP rigid registration
- `align_icp_with_mirror()` - Registration with YZ-plane mirror option
- `ransac()` - FPFH-based RANSAC alignment
- `icp()` - Point-to-plane ICP refinement

### 3. Distance Metrics
- `chamfer()` - Bidirectional Chamfer distance
- `clearance_sampling()` - Sampling-based SDF clearance check
- `clearance_sdf_volume()` - Voxel narrow-band SDF formal verification

### 4. Feature Extraction
- `coarse_features()` - Volume, area, extents, normal histogram

### 5. Analysis Tools
- `min_clearance_point()` - Find thinnest clearance point
- `thin_regions()` - Cluster thin-wall regions
- `label_regions()` - Semantic labeling (toe/heel, medial/lateral)
- `mesh_section()` - Compute mesh-plane intersection

### 6. Batch Processing
- `batch_align_and_check()` - Parallel batch alignment and checking
- `batch_formal_check()` - Batch narrow-band SDF verification

## Python Interface

```python
import cppcore

# Compute features
features = cppcore.coarse_features(vertices, faces)

# Align with mirror check
result = cppcore.align_icp_with_mirror(
    v_src, f_src, v_tgt, f_tgt,
    voxel=5.0, fpfh_radius=10.0, icp_thr=15.0
)

# Check clearance
clearance = cppcore.clearance_sampling(
    v_target, f_target, v_candidate, f_candidate,
    clearance=2.0, safety_delta=0.3, samples=120000
)

# Find thin regions
regions = cppcore.thin_regions(
    v_target, f_target, v_candidate, f_candidate,
    thr_mm=2.3, radius_mm=12.0
)
```

## Build Instructions

### Using scikit-build-core (Recommended)
```bash
cd hybrid
pip install -v .
```

### Manual CMake Build
```bash
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
```

## Performance Notes

1. **OpenMP Support**: Enabled automatically if available (Linux/Mac)
2. **Voxel Downsampling**: Use 2.5-5.0mm for balance between speed and accuracy
3. **FPFH Radius**: 6-10mm works well for shoe lasts
4. **ICP Threshold**: 8-15mm for initial alignment tolerance

## Algorithm Details

### RANSAC + ICP Pipeline
1. Downsample point clouds to voxel grid
2. Compute FPFH features for correspondence
3. RANSAC for initial rigid transformation
4. Point-to-plane ICP for refinement
5. Optional mirror check (YZ-plane)

### Clearance Verification
- **Sampling Method**: Fast, approximate (120k samples)
- **Narrow-band SDF**: Accurate, formal verification
- **Safety Delta**: Additional margin (0.3mm default)

### Thin Wall Detection
1. Compute signed distance for all target vertices
2. Select vertices with clearance < threshold
3. Cluster using radius-based grouping
4. PCA for skeleton extraction
5. Semantic labeling based on shoe anatomy

## Troubleshooting

### Import Error
```bash
# Use LD_PRELOAD for Open3D library issues
LD_PRELOAD=/usr/local/lib/libOpen3D.so python3 your_script.py
```

### Segmentation Fault
- Disable OpenMP: `export OMP_NUM_THREADS=1`
- Check mesh validity before processing
- Ensure sufficient memory for large meshes

### Performance Issues
- Reduce sampling density
- Increase voxel size
- Use batch processing for multiple candidates

## Version History

- **v0.5** - Current production version
  - Full Open3D 0.18 compatibility
  - Robust error handling
  - Parallel batch processing
  - Comprehensive clearance metrics
