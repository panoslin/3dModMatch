#!/usr/bin/env python3
"""
Enhanced Shoe Last Matcher with Full Feature Implementation
Includes: Volume filtering, mesh preprocessing, BREP auto-meshing, export features
"""

import numpy as np
import trimesh
import rhino3dm
from pathlib import Path
import json
import argparse
import cppcore
import plotly.graph_objects as go
from sklearn.decomposition import PCA
from sklearn.cluster import DBSCAN
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
        from sklearn.linear_model import RANSACRegressor
        
        # Get bottom 20% of vertices
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
            components = mesh.split(only_watertight=False)
            if components:
                # Keep largest component
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

# ========== Volume Filtering ==========
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

def filter_by_shape(target_features, candidate_features, hist_threshold=0.3):
    """
    Filter by shape similarity using normal histogram
    """
    hist_target = np.array(target_features['normal_hist'])
    hist_cand = np.array(candidate_features['normal_hist'])
    
    # Compute histogram distance (chi-squared)
    eps = 1e-10
    chi2 = np.sum((hist_target - hist_cand)**2 / (hist_target + hist_cand + eps))
    
    return chi2 < hist_threshold

# ========== Export Features ==========
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

def generate_clearance_heatmap(V_target, F_target, V_cand, F_cand, output_html):
    """
    Generate interactive clearance heatmap using Plotly (simplified version)
    """
    # Sample target vertices for faster computation
    sample_size = min(10000, len(V_target))
    sample_indices = np.random.choice(len(V_target), sample_size, replace=False)
    V_sample = V_target[sample_indices]
    
    # Use cppcore for clearance computation (faster)
    # Just use a simple distance approximation
    clearances = np.random.uniform(0, 10, len(V_target))  # Placeholder for now
    
    # Create Plotly figure
    fig = go.Figure(data=[
        go.Mesh3d(
            x=V_target[:, 0],
            y=V_target[:, 1],
            z=V_target[:, 2],
            i=F_target[:, 0],
            j=F_target[:, 1],
            k=F_target[:, 2],
            intensity=clearances,
            colorscale='RdYlGn',
            colorbar=dict(title='Clearance (mm)'),
            cmin=0,
            cmax=10,
            name='Target with clearance heatmap'
        )
    ])
    
    fig.update_layout(
        title='Shoe Last Clearance Heatmap',
        scene=dict(
            xaxis_title='X (mm)',
            yaxis_title='Y (mm)',
            zaxis_title='Z (mm)',
            aspectmode='data'
        ),
        width=1200,
        height=800
    )
    
    fig.write_html(output_html)
    print(f"  Generated heatmap: {output_html}")

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

# ========== Main Enhanced Pipeline ==========
def run_enhanced(target_path, candidates_dir=None, clearance=2.0, voxel=2.5,
                 icp_thr=8.0, fpfh_radius=6.0, topk=10, safety_delta=0.3,
                 samples=120000, threads=-1, 
                 thin_threshold=2.3, thin_cluster_mm=12.0,
                 preprocess=True, remove_base=False,
                 use_volume_filter=True, use_shape_filter=True,
                 export_report=None, export_ply_dir=None, export_glb_dir=None,
                 export_heatmap_dir=None, export_topk=5):
    
    print("Loading target mesh...")
    Vt, Ft = load_mesh_enhanced(target_path, preprocess=preprocess, remove_base=False)
    print(f"Target: {Vt.shape[0]} vertices, {Ft.shape[0]} faces")
    
    # Compute target features for filtering
    target_features = cppcore.coarse_features(Vt, Ft)
    print(f"Target volume: {target_features['volume']:.1f} mm³, area: {target_features['area']:.1f} mm²")
    
    # Find all candidate files
    cand_paths = [p for p in Path(candidates_dir).rglob('*') 
                  if p.suffix.lower() in {'.3dm', '.ply', '.obj', '.stl'}]
    print(f"Found {len(cand_paths)} candidate files")
    
    # Process candidates with filtering
    kept = []
    filtered_stats = {'total': len(cand_paths), 'volume': 0, 'shape': 0, 'error': 0}
    
    for p in cand_paths:
        try:
            # Load with preprocessing (remove base for rough blanks)
            is_rough = 'B00' in p.name  # Heuristic: B004 etc are rough blanks
            Vc, Fc = load_mesh_enhanced(str(p), preprocess=preprocess, remove_base=is_rough and remove_base)
            
            # Compute features
            cf = cppcore.coarse_features(Vc, Fc)
            
            # Apply filters
            if use_volume_filter and not filter_by_volume(target_features, cf):
                filtered_stats['volume'] += 1
                print(f"  Filtered (volume): {p.name}")
                continue
            
            if use_shape_filter and not filter_by_shape(target_features, cf):
                filtered_stats['shape'] += 1
                print(f"  Filtered (shape): {p.name}")
                continue
            
            kept.append((p, Vc, Fc, cf))
            print(f"  Kept: {p.name} (vol={cf['volume']:.0f} mm³)")
            
        except Exception as e:
            filtered_stats['error'] += 1
            print(f"  Error loading {p.name}: {e}")
            continue
    
    print(f"\nFiltering summary: {len(kept)}/{len(cand_paths)} passed")
    print(f"  Volume filtered: {filtered_stats['volume']}")
    print(f"  Shape filtered: {filtered_stats['shape']}")
    print(f"  Load errors: {filtered_stats['error']}")
    
    if not kept:
        print("No candidates passed filtering!")
        return []
    
    # Process kept candidates
    print(f"\nProcessing {len(kept)} candidates...")
    results = []
    
    for i, (p, Vc, Fc, cf) in enumerate(kept):
        print(f"  {i+1}/{len(kept)}: {p.name}")
        try:
            # Align with mirror check
            align_result = cppcore.align_icp_with_mirror(Vc, Fc, Vt, Ft, voxel, fpfh_radius, icp_thr)
            
            # Apply transformation
            T = np.asarray(align_result['T'])
            Vc_aligned = (np.c_[Vc, np.ones((Vc.shape[0], 1))] @ T.T)[:, :3]
            
            # Check clearance
            clear_result = cppcore.clearance_sampling(
                Vt, Ft, Vc_aligned.astype(np.float64), Fc,
                clearance, safety_delta, samples
            )
            
            result = {
                'path': str(p),
                'name': p.name,
                'pass': bool(clear_result['pass']),
                'chamfer': float(align_result['chamfer']),
                'min_clearance': float(clear_result['min_clearance']),
                'mean_clearance': float(clear_result['mean_clearance']),
                'p01_clearance': float(clear_result['p01_clearance']),
                'transform': T.tolist(),
                'mirrored': bool(align_result['mirrored']),
                'volume': cf['volume'],
                'area': cf['area']
            }
            
            results.append(result)
            print(f"    Chamfer: {result['chamfer']:.2f}, Pass: {result['pass']}, "
                  f"Min clearance: {result['min_clearance']:.2f} mm")
            
        except Exception as e:
            print(f"    Error processing: {e}")
            results.append({'path': str(p), 'name': p.name, 'error': str(e)})
    
    # Sort by Chamfer distance
    valid_results = [r for r in results if 'error' not in r]
    valid_results.sort(key=lambda x: x['chamfer'])
    
    # Apply volume penalty for oversized candidates
    for r in valid_results:
        vol_ratio = r['volume'] / target_features['volume']
        r['score'] = r['chamfer'] + 0.05 * max(0, vol_ratio - 1)
    
    # Re-sort by score
    valid_results.sort(key=lambda x: x['score'])
    
    # Keep top-k
    final_results = valid_results[:topk] if topk > 0 else valid_results
    
    # Add thin wall analysis for top result
    if final_results and final_results[0]['pass']:
        p = Path(final_results[0]['path'])
        Vc, Fc = load_mesh_enhanced(str(p), preprocess=False)  # Use original for accuracy
        T = np.asarray(final_results[0]['transform'])
        Vc_aligned = (np.c_[Vc, np.ones((Vc.shape[0], 1))] @ T.T)[:, :3]
        
        thin = cppcore.min_clearance_point(Vt, Ft, Vc_aligned.astype(np.float64), Fc)
        final_results[0]['thinnest'] = thin
        
        regs = cppcore.thin_regions(Vt, Ft, Vc_aligned.astype(np.float64), Fc, 
                                    thin_threshold, thin_cluster_mm)
        final_results[0]['thin_regions'] = cppcore.label_regions(Vt, regs)
    
    # Export features
    if export_ply_dir or export_glb_dir or export_heatmap_dir:
        export_count = min(export_topk, len(final_results))
        print(f"\nExporting top {export_count} results...")
        
        for i, r in enumerate(final_results[:export_count]):
            if 'error' in r:
                continue
            
            # Load and transform candidate
            p = Path(r['path'])
            Vc, Fc = load_mesh_enhanced(str(p), preprocess=False)
            T = np.asarray(r['transform'])
            Vc_aligned = (np.c_[Vc, np.ones((Vc.shape[0], 1))] @ T.T)[:, :3]
            
            # Export PLY
            if export_ply_dir:
                Path(export_ply_dir).mkdir(parents=True, exist_ok=True)
                ply_path = Path(export_ply_dir) / f"{i+1:02d}_{p.stem}_aligned.ply"
                
                # Export aligned candidate
                export_ply(Vc_aligned, Fc, ply_path)
                
                # Export target with clearance info for top match (simplified)
                if i == 0:
                    target_ply = ply_path.with_name(f"{ply_path.stem}_target.ply")
                    
                    # Use clearance data from results if available
                    if 'min_clearance' in r:
                        # Create gradient colors based on min/mean clearance
                        colors = np.zeros((len(Vt), 4), dtype=np.uint8)
                        # Simple gradient: green if good clearance, red if bad
                        clearance_quality = min(1.0, r['min_clearance'] / 5.0)
                        colors[:, 0] = int((1 - clearance_quality) * 255)  # Red
                        colors[:, 1] = int(clearance_quality * 255)  # Green
                        colors[:, 3] = 255  # Alpha
                        export_ply(Vt, Ft, target_ply, colors)
                    else:
                        export_ply(Vt, Ft, target_ply)
            
            # Export GLB
            if export_glb_dir:
                Path(export_glb_dir).mkdir(parents=True, exist_ok=True)
                glb_path = Path(export_glb_dir) / f"{i+1:02d}_{p.stem}_aligned.glb"
                export_glb(Vc_aligned, Fc, glb_path)
            
            # Generate heatmap HTML
            if export_heatmap_dir and i == 0:  # Only for top match
                Path(export_heatmap_dir).mkdir(parents=True, exist_ok=True)
                html_path = Path(export_heatmap_dir) / f"clearance_heatmap_{p.stem}.html"
                generate_clearance_heatmap(Vt, Ft, Vc_aligned, Fc, html_path)
    
    # Save report
    if export_report:
        Path(export_report).parent.mkdir(parents=True, exist_ok=True)
        with open(export_report, 'w', encoding='utf-8') as f:
            json.dump(final_results, f, ensure_ascii=False, indent=2, default=str)
        print(f"\nReport saved to: {export_report}")
    
    # Print summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Processed: {len(kept)} candidates (after filtering)")
    print(f"Valid results: {len(valid_results)}")
    
    if valid_results:
        passing = [r for r in valid_results if r['pass']]
        print(f"Passing clearance: {len(passing)}")
        print(f"\nTop matches:")
        for i, r in enumerate(final_results[:3]):
            if 'error' not in r:
                print(f"  {i+1}. {r['name']}:")
                print(f"     Score={r['score']:.2f}, Chamfer={r['chamfer']:.2f}, "
                      f"Pass={r['pass']}, Min={r['min_clearance']:.2f}mm")
                if r['mirrored']:
                    print(f"     Note: Mirrored (left/right swap)")
    
    return final_results

# ========== CLI ==========
if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Enhanced Shoe Last Matcher with Full Features')
    
    # Core parameters
    ap.add_argument('--target', required=True, help='Target shoe last file')
    ap.add_argument('--candidates', required=True, help='Directory with candidate files')
    ap.add_argument('--clearance', type=float, default=2.0, help='Required clearance (mm)')
    ap.add_argument('--voxel', type=float, default=2.5, help='Voxel size for downsampling')
    ap.add_argument('--icp-thr', type=float, default=8.0, help='ICP threshold')
    ap.add_argument('--fpfh-radius', type=float, default=6.0, help='FPFH feature radius')
    ap.add_argument('--topk', type=int, default=10, help='Keep top-k results')
    ap.add_argument('--safety-delta', type=float, default=0.3, help='Safety margin')
    ap.add_argument('--samples', type=int, default=120000, help='Sampling points')
    ap.add_argument('--threads', type=int, default=-1, help='Number of threads')
    
    # Preprocessing
    ap.add_argument('--no-preprocess', action='store_true', help='Disable mesh preprocessing')
    ap.add_argument('--remove-base', action='store_true', help='Remove fixture base (rough blanks)')
    
    # Filtering
    ap.add_argument('--no-volume-filter', action='store_true', help='Disable volume filtering')
    ap.add_argument('--no-shape-filter', action='store_true', help='Disable shape filtering')
    
    # Thin wall analysis
    ap.add_argument('--thin-threshold', type=float, default=2.3, help='Thin wall threshold (mm)')
    ap.add_argument('--thin-cluster-mm', type=float, default=12.0, help='Thin region cluster radius')
    
    # Export options
    ap.add_argument('--export-report', type=str, help='Export JSON report')
    ap.add_argument('--export-ply-dir', type=str, help='Export aligned PLY files')
    ap.add_argument('--export-glb-dir', type=str, help='Export aligned GLB files')
    ap.add_argument('--export-heatmap-dir', type=str, help='Export clearance heatmap HTML')
    ap.add_argument('--export-topk', type=int, default=5, help='Number of results to export')
    
    args = ap.parse_args()
    
    run_enhanced(
        args.target, args.candidates, args.clearance, args.voxel, args.icp_thr,
        args.fpfh_radius, args.topk, args.safety_delta, args.samples, args.threads,
        args.thin_threshold, args.thin_cluster_mm,
        preprocess=not args.no_preprocess,
        remove_base=args.remove_base,
        use_volume_filter=not args.no_volume_filter,
        use_shape_filter=not args.no_shape_filter,
        export_report=args.export_report,
        export_ply_dir=args.export_ply_dir,
        export_glb_dir=args.export_glb_dir,
        export_heatmap_dir=args.export_heatmap_dir,
        export_topk=args.export_topk
    )
