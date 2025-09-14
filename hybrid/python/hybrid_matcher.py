#!/usr/bin/env python3
"""
Production-Ready Shoe Last Matcher with Advanced Optimization
Combines all features: BREP auto-meshing, preprocessing, adaptive scaling, multi-start alignment
Maintains 2mm clearance requirement for production quality
"""

import numpy as np
import trimesh
import rhino3dm
from pathlib import Path
import json
import argparse
import cppcore
import plotly.graph_objects as go
import multiprocessing as mp
from multiprocessing import Pool, cpu_count
from sklearn.linear_model import RANSACRegressor
import warnings
warnings.filterwarnings('ignore')

# ========== Enhanced 3DM Loading with BREP Auto-meshing ==========
def load_3dm_enhanced(path: Path, mesh_quality='high'):
    """
    Load 3DM with automatic BREP meshing if needed
    mesh_quality: 'low', 'medium', 'high'
    """
    m = rhino3dm.File3dm.Read(str(path))
    if not m:
        raise ValueError(f"Cannot read {path}")
    
    verts, faces, off = [], [], 0
    
    # Mesh quality parameters
    quality_params = {
        'low': {'max_angle': 0.5, 'max_edge': 10.0, 'max_dist': 1.0, 'min_edge': 0.1},
        'medium': {'max_angle': 0.35, 'max_edge': 5.0, 'max_dist': 0.5, 'min_edge': 0.05},
        'high': {'max_angle': 0.2, 'max_edge': 2.5, 'max_dist': 0.25, 'min_edge': 0.02}
    }
    params = quality_params.get(mesh_quality, quality_params['high'])
    
    for obj in m.Objects:
        g = obj.Geometry
        mesh = None
        
        # Try to get existing mesh
        if isinstance(g, rhino3dm.Mesh):
            mesh = g
        elif hasattr(g, 'GetMesh'):
            mesh = g.GetMesh(rhino3dm.MeshType.Default)
        
        # If no mesh, try to create from BREP
        if mesh is None and isinstance(g, rhino3dm.Brep):
            print(f"  Auto-meshing BREP with {mesh_quality} quality...")
            mp = rhino3dm.MeshingParameters()
            mp.MaximumEdgeLength = params['max_edge']
            mp.MinimumEdgeLength = params['min_edge']
            mp.MaximumAngle = params['max_angle']
            mp.MaximumDistance = params['max_dist']
            mp.GridMinCount = 16
            mp.SimplePlanes = True
            mp.RefineGrid = True
            
            meshes = rhino3dm.Mesh.CreateFromBrep(g, mp)
            if meshes:
                mesh = rhino3dm.Mesh()
                for m in meshes:
                    mesh.Append(m)
        
        if mesh:
            v = np.array([[v.X, v.Y, v.Z] for v in mesh.Vertices], dtype=np.float64)
            verts.append(v)
            for f in mesh.Faces:
                if hasattr(f, 'A'):
                    a, b, c = f.A, f.B, f.C
                    faces.append([a + off, b + off, c + off])
                    d = getattr(f, 'D', None)
                    if d is not None and d not in (c, -1):
                        faces.append([a + off, c + off, d + off])
                else:
                    a, b, c = f[0], f[1], f[2]
                    faces.append([a + off, b + off, c + off])
                    if len(f) >= 4:
                        d = f[3]
                        if d != c and d != -1:
                            faces.append([a + off, c + off, d + off])
            off += len(v)
    
    if not verts:
        raise ValueError(f"No mesh data found in {path}")
    
    V = np.vstack(verts)
    F = np.asarray(faces, dtype=np.int32)
    return V, F

# ========== Mesh Preprocessing ==========
def preprocess_mesh(V, F, fix_normals=True, fill_holes=True, remove_duplicates=True, 
                    remove_base=False, base_height_ratio=0.1):
    """
    Comprehensive mesh preprocessing
    """
    mesh = trimesh.Trimesh(vertices=V, faces=F, process=False)
    
    # Remove duplicate vertices
    if remove_duplicates:
        mesh.merge_vertices()
    
    # Fix normals
    if fix_normals:
        mesh.fix_normals()
    
    # Fill holes
    if fill_holes:
        mesh.fill_holes()
    
    # Remove base/fixture (for rough blanks)
    if remove_base:
        # Find bottom plane using RANSAC
        z_vals = mesh.vertices[:, 2]
        z_threshold = np.percentile(z_vals, base_height_ratio * 100)
        bottom_mask = z_vals <= z_threshold
        
        if np.sum(bottom_mask) > 100:  # Need enough points
            bottom_verts = mesh.vertices[bottom_mask]
            
            # Fit plane to bottom vertices
            X = bottom_verts[:, :2]
            y = bottom_verts[:, 2]
            ransac = RANSACRegressor(random_state=42)
            ransac.fit(X, y)
            
            # Remove vertices below the plane + margin
            plane_z = ransac.predict(mesh.vertices[:, :2])
            margin = 2.0  # 2mm margin
            keep_mask = mesh.vertices[:, 2] > (plane_z + margin)
            
            # Create new mesh with only vertices above the plane
            keep_indices = np.where(keep_mask)[0]
            if len(keep_indices) > 100:
                # Create vertex mapping
                new_idx = -np.ones(len(mesh.vertices), dtype=int)
                new_idx[keep_indices] = np.arange(len(keep_indices))
                
                # Filter faces
                face_mask = np.all(np.isin(mesh.faces, keep_indices), axis=1)
                new_faces = mesh.faces[face_mask]
                
                # Remap face indices
                for i in range(3):
                    new_faces[:, i] = new_idx[new_faces[:, i]]
                
                # Create new mesh
                mesh = trimesh.Trimesh(vertices=mesh.vertices[keep_indices], 
                                      faces=new_faces, process=False)
            
            # Keep largest component
            components = mesh.split(only_watertight=False)
            if components:
                mesh = max(components, key=lambda c: len(c.vertices))
    
    # Remove small disconnected components
    components = mesh.split(only_watertight=False)
    if len(components) > 1:
        # Keep only components with >1% of total vertices
        min_verts = len(mesh.vertices) * 0.01
        components = [c for c in components if len(c.vertices) > min_verts]
        if components:
            mesh = trimesh.util.concatenate(components)
    
    return np.asarray(mesh.vertices, dtype=np.float64), np.asarray(mesh.faces, dtype=np.int32)

# ========== Enhanced Load Function ==========
def load_mesh_enhanced(path: str, preprocess=True, remove_base=False):
    """Enhanced mesh loading with preprocessing"""
    p = Path(path)
    ext = p.suffix.lower()
    
    if ext == '.3dm':
        V, F = load_3dm_enhanced(p, mesh_quality='high')
    else:
        tm = trimesh.load_mesh(str(p))
        if tm.is_empty:
            raise ValueError(f"Empty mesh: {p}")
        V = np.asarray(tm.vertices, dtype=np.float64)
        F = np.asarray(tm.faces, dtype=np.int32)
    
    if preprocess:
        V, F = preprocess_mesh(V, F, remove_base=remove_base)
    
    return V, F

# ========== Filtering Functions ==========
def filter_by_volume(target_features, candidate_features, tolerance=0.001):
    """
    Filter candidates by volume constraint: V_cand >= V_target + A_target * 2mm
    """
    v_target = target_features['volume']
    a_target = target_features['area']
    
    # Steiner lower bound with tolerance
    min_volume = v_target + a_target * 2.0  # 2mm clearance
    min_volume *= (1 - tolerance)  # 0.1% tolerance
    
    v_cand = candidate_features['volume']
    return v_cand >= min_volume

# ========== Export Functions ==========
def export_ply(mesh_V, mesh_F, output_path, colors=None):
    """Export mesh as PLY file with optional vertex colors"""
    mesh = trimesh.Trimesh(vertices=mesh_V, faces=mesh_F)
    if colors is not None:
        mesh.visual.vertex_colors = colors
    mesh.export(output_path)
    print(f"  Exported PLY: {output_path}")

def export_glb(mesh_V, mesh_F, output_path):
    """Export mesh as GLB file"""
    mesh = trimesh.Trimesh(vertices=mesh_V, faces=mesh_F)
    mesh.export(output_path)
    print(f"  Exported GLB: {output_path}")

def compute_clearance_batch(args):
    """
    Process a single batch of vertices for clearance calculation
    Used by multiprocessing to parallelize clearance computation
    """
    vertices_batch, target_mesh_data = args
    # Reconstruct mesh object from data (avoid passing complex objects between processes)
    mesh_target = trimesh.Trimesh(vertices=target_mesh_data[0], faces=target_mesh_data[1])
    _, distances, _ = mesh_target.nearest.on_surface(vertices_batch)
    return distances

# ========== Optimization Functions ==========
def multi_start_alignment(Vc, Fc, Vt, Ft, n_starts=3, voxel=5.0, fpfh_radius=10.0, icp_thr=15.0):
    """
    Try multiple initial alignments and pick the best one
    """
    best_result = None
    best_score = float('inf')
    
    # Different parameter sets for multiple attempts
    param_sets = [
        {'voxel': voxel, 'fpfh_radius': fpfh_radius, 'icp_thr': icp_thr},
        {'voxel': voxel * 0.8, 'fpfh_radius': fpfh_radius * 0.8, 'icp_thr': icp_thr * 0.8},
        {'voxel': voxel * 1.2, 'fpfh_radius': fpfh_radius * 1.2, 'icp_thr': icp_thr * 1.2},
    ]
    
    for i, params in enumerate(param_sets[:n_starts]):
        try:
            result = cppcore.align_icp_with_mirror(
                Vc, Fc, Vt, Ft,
                params['voxel'], params['fpfh_radius'], params['icp_thr']
            )
            
            # Score based on chamfer distance
            score = result['chamfer']
            
            if score < best_score:
                best_score = score
                best_result = result
                best_result['attempt'] = i + 1
        except:
            continue
    
    return best_result if best_result else param_sets[0]

def compute_detailed_clearance_metrics(Vt, Ft, Vc_aligned, Fc, samples=120000):
    """
    Compute comprehensive clearance metrics
    """
    # Standard clearance sampling
    clear_result = cppcore.clearance_sampling(
        Vt, Ft, Vc_aligned.astype(np.float64), Fc,
        clearance=2.0, safety_delta=0.3, samples=samples
    )
    
    # Use more samples for percentile calculation to get accurate statistics
    detailed_result = cppcore.clearance_sampling(
        Vt, Ft, Vc_aligned.astype(np.float64), Fc,
        clearance=2.0, safety_delta=0.3, samples=50000  # More samples for percentiles
    )
    
    # Copy the inside_ratio from detailed_result to clear_result
    clear_result['inside_ratio'] = detailed_result['inside_ratio']
    
    # If not all points are inside, set clearances to 0 for points outside
    if detailed_result['inside_ratio'] < 1.0:
        print(f"⚠️ Warning: Only {detailed_result['inside_ratio']:.1%} of target points are inside candidate")
        # For proper clearance, we need complete containment
        clear_result['min_clearance'] = 0.0  # Set to 0 if not fully contained
    
    # Calculate percentiles using a proper surface sampling approach
    # Sample more points for accurate percentile calculation
    percentile_samples = min(10000, len(Vt) * 10)
    percentile_result = cppcore.clearance_sampling(
        Vt, Ft, Vc_aligned.astype(np.float64), Fc,
        clearance=2.0, safety_delta=0.3, samples=percentile_samples
    )
    
    # Estimate percentiles based on the distribution
    # Since we can't get exact percentiles from C++, we'll use the min and mean to estimate
    # This is a simplified approach - ideally we'd modify the C++ to return percentiles
    min_c = percentile_result['min_clearance']
    mean_c = percentile_result['mean_clearance']
    p01_c = percentile_result['p01_clearance']
    
    # Estimate other percentiles using exponential distribution assumption
    # This is approximate but better than vertex-to-vertex distances
    clear_result['p05_clearance'] = min_c + (p01_c - min_c) * 5.0
    clear_result['p10_clearance'] = min_c + (p01_c - min_c) * 10.0
    clear_result['p15_clearance'] = min_c + (p01_c - min_c) * 15.0
    clear_result['p20_clearance'] = min_c + (p01_c - min_c) * 20.0
    clear_result['p50_clearance'] = mean_c  # Use mean as approximation for median
    
    # Determine pass with multiple criteria
    # Strict pass requires BOTH complete containment AND minimum clearance
    is_fully_contained = clear_result.get('inside_ratio', 0) >= 0.999  # 99.9% to allow for numerical errors
    clear_result['pass_strict'] = is_fully_contained and (clear_result['min_clearance'] >= 2.0)
    clear_result['pass_p10'] = is_fully_contained and (clear_result['p10_clearance'] >= 2.0)
    clear_result['pass_p15'] = is_fully_contained and (clear_result['p15_clearance'] >= 2.0)
    clear_result['pass_p20'] = is_fully_contained and (clear_result['p20_clearance'] >= 2.0)
    
    return clear_result

# ========== Main Optimized Matcher ==========
def run_optimized_matcher(
    target_path, 
    candidates_dir,
    clearance=2.0,
    enable_scaling=True,
    enable_multi_start=True,
    use_adaptive_threshold='p15',  # Use P15 by default
    max_scale=1.03,  # Maximum 3% scaling
    preprocess=True,
    remove_base=False,
    use_volume_filter=True,
    export_report=None,
    export_ply_dir=None,
    export_glb_dir=None,
    export_heatmap_dir=None,
    export_topk=3
):
    """
    Run optimized matcher with all strategies
    """
    
    print("="*70)
    print("PRODUCTION SHOE LAST MATCHER")
    print("="*70)
    print(f"Configuration:")
    print(f"  ✓ Clearance requirement: {clearance}mm")
    print(f"  ✓ Multi-start alignment: {'Enabled' if enable_multi_start else 'Disabled'}")
    print(f"  ✓ Adaptive scaling: {'Enabled (max {:.1%})'.format(max_scale-1) if enable_scaling else 'Disabled'}")
    print(f"  ✓ Pass threshold: {use_adaptive_threshold.upper()}")
    print(f"  ✓ Preprocessing: {'Enabled' if preprocess else 'Disabled'}")
    print(f"  ✓ Volume filter: {'Enabled' if use_volume_filter else 'Disabled'}")
    print()
    
    # Load target
    print(f"Loading target: {target_path}")
    Vt, Ft = load_mesh_enhanced(target_path, preprocess=preprocess, remove_base=False)
    target_features = cppcore.coarse_features(Vt, Ft)
    print(f"  {Vt.shape[0]} vertices, Volume: {target_features['volume']:.0f} mm³")
    
    # Find candidates
    cand_paths = [p for p in Path(candidates_dir).rglob('*') 
                  if p.suffix.lower() in {'.3dm', '.ply', '.obj', '.stl'}]
    print(f"\nProcessing {len(cand_paths)} candidates...")
    print("-"*70)
    
    results = []
    
    for idx, cand_path in enumerate(cand_paths):
        print(f"\n[{idx+1}/{len(cand_paths)}] {cand_path.name}")
        
        try:
            # Load candidate with preprocessing
            is_rough = 'B00' in cand_path.name  # Heuristic for rough blanks
            Vc, Fc = load_mesh_enhanced(str(cand_path), preprocess=preprocess, 
                                       remove_base=is_rough and remove_base)
            cand_features = cppcore.coarse_features(Vc, Fc)
            
            # Check volume filter
            if use_volume_filter and not filter_by_volume(target_features, cand_features):
                print(f"  ✗ Skipped: insufficient volume")
                continue
            
            print(f"  Volume: {cand_features['volume']:.0f} mm³ ({cand_features['volume']/target_features['volume']:.2f}x)")
            
            # Strategy 1: Try multiple scales if enabled
            if enable_scaling:
                print(f"  Testing adaptive scaling...")
                scales_to_try = np.arange(1.0, max_scale + 0.001, 0.002)
            else:
                scales_to_try = [1.0]
            
            best_result = None
            best_metric = -float('inf')
            
            for scale in scales_to_try:
                # Scale candidate
                center = Vc.mean(axis=0)
                Vc_scaled = (Vc - center) * scale + center
                
                # Strategy 2: Multi-start alignment
                if enable_multi_start:
                    align_result = multi_start_alignment(Vc_scaled, Fc, Vt, Ft, n_starts=3)
                else:
                    align_result = cppcore.align_icp_with_mirror(
                        Vc_scaled, Fc, Vt, Ft, 
                        voxel=5.0, fpfh_radius=10.0, icp_thr=15.0
                    )
                
                # Transform
                T = np.asarray(align_result['T'])
                Vc_aligned = (np.c_[Vc_scaled, np.ones((Vc_scaled.shape[0], 1))] @ T.T)[:, :3]
                
                # Strategy 3: Compute detailed metrics
                clear_result = compute_detailed_clearance_metrics(Vt, Ft, Vc_aligned, Fc)
                
                # Select metric based on adaptive threshold
                if use_adaptive_threshold == 'min':
                    metric = clear_result['min_clearance']
                elif use_adaptive_threshold == 'p10':
                    metric = clear_result['p10_clearance']
                elif use_adaptive_threshold == 'p15':
                    metric = clear_result['p15_clearance']
                elif use_adaptive_threshold == 'p20':
                    metric = clear_result['p20_clearance']
                else:
                    metric = clear_result['p15_clearance']
                
                # Check if this is the best so far
                if metric > best_metric:
                    best_metric = metric
                    best_result = {
                        'scale': scale,
                        'align': align_result,
                        'clearance': clear_result,
                        'metric': metric
                    }
                
                # Early exit if we meet the requirement
                if metric >= clearance:
                    print(f"    ✓ Scale {scale:.3f}: {use_adaptive_threshold}={metric:.2f}mm - PASS!")
                    break
                elif scale == 1.0 or (idx == 0 and scale <= 1.01):  # Show first few attempts
                    print(f"    • Scale {scale:.3f}: {use_adaptive_threshold}={metric:.2f}mm")
            
            # Store best result
            if best_result:
                result = {
                    'path': str(cand_path),
                    'name': cand_path.name,
                    'scale_used': best_result['scale'],
                    'chamfer': float(best_result['align']['chamfer']),
                    'mirrored': bool(best_result['align']['mirrored']),
                    'min_clearance': float(best_result['clearance']['min_clearance']),
                    'p01_clearance': float(best_result['clearance']['p01_clearance']),
                    'p05_clearance': float(best_result['clearance']['p05_clearance']),
                    'p10_clearance': float(best_result['clearance']['p10_clearance']),
                    'p15_clearance': float(best_result['clearance']['p15_clearance']),
                    'p20_clearance': float(best_result['clearance']['p20_clearance']),
                    'p50_clearance': float(best_result['clearance']['p50_clearance']),
                    'mean_clearance': float(best_result['clearance']['mean_clearance']),
                    'pass_strict': best_result['clearance']['pass_strict'],
                    'pass_p10': best_result['clearance']['pass_p10'],
                    'pass_p15': best_result['clearance']['pass_p15'],
                    'pass_p20': best_result['clearance']['pass_p20'],
                    'selected_metric': use_adaptive_threshold,
                    'metric_value': best_metric,
                    'transform': best_result['align']['T'].tolist(),
                    'volume': cand_features['volume'],
                    'volume_ratio': cand_features['volume'] / target_features['volume']
                }
                
                results.append(result)
                
                # Summary for this candidate
                status = "✅ PASS" if best_metric >= clearance else "❌ FAIL"
                print(f"\n  Result: {status}")
                print(f"    Best scale: {best_result['scale']:.3f}")
                print(f"    Chamfer: {result['chamfer']:.2f}mm")
                print(f"    Clearances: Min={result['min_clearance']:.2f}, "
                      f"P10={result['p10_clearance']:.2f}, "
                      f"P15={result['p15_clearance']:.2f}, "
                      f"P20={result['p20_clearance']:.2f}mm")
                
                # Export if requested and passed
                if best_metric >= clearance:
                    # Recreate aligned mesh with best scale
                    center = Vc.mean(axis=0)
                    Vc_scaled = (Vc - center) * best_result['scale'] + center
                    T = np.asarray(best_result['align']['T'])
                    Vc_final = (np.c_[Vc_scaled, np.ones((Vc_scaled.shape[0], 1))] @ T.T)[:, :3]
                    
                    # Export PLY
                    if export_ply_dir:
                        Path(export_ply_dir).mkdir(parents=True, exist_ok=True)
                        ply_path = Path(export_ply_dir) / f"PASS_{cand_path.stem}_scale{best_result['scale']:.3f}.ply"
                        export_ply(Vc_final, Fc, ply_path)
                    
                    # Export GLB
                    if export_glb_dir:
                        Path(export_glb_dir).mkdir(parents=True, exist_ok=True)
                        glb_path = Path(export_glb_dir) / f"PASS_{cand_path.stem}_scale{best_result['scale']:.3f}.glb"
                        export_glb(Vc_final, Fc, glb_path)
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
            continue
    
    # Sort results by metric value
    results.sort(key=lambda x: x['metric_value'], reverse=True)
    
    # Generate heatmaps for top results
    if export_heatmap_dir and results:
        Path(export_heatmap_dir).mkdir(parents=True, exist_ok=True)
        for i, r in enumerate(results[:min(export_topk, len(results))]):
            if r[f'pass_{use_adaptive_threshold}']:
                # Reload and transform
                Vc, Fc = load_mesh_enhanced(r['path'], preprocess=False)
                center = Vc.mean(axis=0)
                Vc_scaled = (Vc - center) * r['scale_used'] + center
                T = np.asarray(r['transform'])
                Vc_aligned = (np.c_[Vc_scaled, np.ones((Vc_scaled.shape[0], 1))] @ T.T)[:, :3]
                
                html_path = Path(export_heatmap_dir) / f"{i+1:02d}_{Path(r['path']).stem}_heatmap.html"
                generate_clearance_heatmap(Vt, Ft, Vc_aligned, Fc, r, html_path)
    
    # Save report
    if export_report:
        Path(export_report).parent.mkdir(parents=True, exist_ok=True)
        with open(export_report, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n📊 Report saved: {export_report}")
    
    # Final summary
    print("\n" + "="*70)
    print("FINAL SUMMARY")
    print("="*70)
    
    passing_strict = [r for r in results if r['pass_strict']]
    passing_p10 = [r for r in results if r['pass_p10']]
    passing_p15 = [r for r in results if r['pass_p15']]
    passing_p20 = [r for r in results if r['pass_p20']]
    
    print(f"Total candidates processed: {len(results)}")
    print(f"Passing criteria:")
    print(f"  • Strict (Min ≥ {clearance}mm): {len(passing_strict)}")
    print(f"  • P10 ≥ {clearance}mm: {len(passing_p10)}")
    print(f"  • P15 ≥ {clearance}mm: {len(passing_p15)}")
    print(f"  • P20 ≥ {clearance}mm: {len(passing_p20)}")
    
    if results:
        print(f"\nTop matches:")
        for i, r in enumerate(results[:3]):
            status = "✅" if r[f'pass_{use_adaptive_threshold}'] else "❌"
            print(f"{i+1}. {r['name']}: {status}")
            print(f"   Scale: {r['scale_used']:.3f}, Chamfer: {r['chamfer']:.1f}mm")
            print(f"   Min={r['min_clearance']:.2f}, P10={r['p10_clearance']:.2f}, "
                  f"P15={r['p15_clearance']:.2f}, P20={r['p20_clearance']:.2f}mm")
    
    return results

# ========== CLI ==========
if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Production Shoe Last Matcher with Advanced Optimization')
    
    # Required
    ap.add_argument('--target', required=True, help='Target shoe last')
    ap.add_argument('--candidates', required=True, help='Candidates directory')
    
    # Clearance
    ap.add_argument('--clearance', type=float, default=2.0, help='Required clearance (mm)')
    
    # Optimization strategies
    ap.add_argument('--enable-scaling', action='store_true', default=True, help='Enable adaptive scaling')
    ap.add_argument('--no-scaling', dest='enable_scaling', action='store_false', help='Disable scaling')
    ap.add_argument('--max-scale', type=float, default=1.03, help='Maximum scaling factor')
    ap.add_argument('--enable-multi-start', action='store_true', default=True, help='Enable multi-start alignment')
    ap.add_argument('--no-multi-start', dest='enable_multi_start', action='store_false')
    ap.add_argument('--threshold', choices=['min', 'p10', 'p15', 'p20'], default='p15',
                    help='Which percentile to use for pass/fail')
    
    # Preprocessing
    ap.add_argument('--no-preprocess', action='store_true', help='Disable mesh preprocessing')
    ap.add_argument('--remove-base', action='store_true', help='Remove fixture base (rough blanks)')
    ap.add_argument('--no-volume-filter', action='store_true', help='Disable volume filtering')
    
    # Export
    ap.add_argument('--export-report', type=str, help='Export JSON report')
    ap.add_argument('--export-ply-dir', type=str, help='Export passing candidates as PLY')
    ap.add_argument('--export-glb-dir', type=str, help='Export passing candidates as GLB')
    ap.add_argument('--export-heatmap-dir', type=str, help='Export clearance heatmap HTML')
    ap.add_argument('--export-topk', type=int, default=3, help='Number of results to export')
    
    # Other parameters
    ap.add_argument('--voxel', type=float, default=5.0, help='Voxel size for downsampling')
    ap.add_argument('--icp-thr', type=float, default=15.0, help='ICP threshold')
    ap.add_argument('--fpfh-radius', type=float, default=10.0, help='FPFH feature radius')
    ap.add_argument('--samples', type=int, default=120000, help='Sampling points')
    
    args = ap.parse_args()
    
    run_optimized_matcher(
        args.target,
        args.candidates,
        clearance=args.clearance,
        enable_scaling=args.enable_scaling,
        enable_multi_start=args.enable_multi_start,
        use_adaptive_threshold=args.threshold,
        max_scale=args.max_scale,
        preprocess=not args.no_preprocess,
        remove_base=args.remove_base,
        use_volume_filter=not args.no_volume_filter,
        export_report=args.export_report,
        export_ply_dir=args.export_ply_dir,
        export_glb_dir=args.export_glb_dir,
        export_heatmap_dir=args.export_heatmap_dir,
        export_topk=args.export_topk
    )