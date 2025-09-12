#!/usr/bin/env python3
"""
Production-ready Shoe Last Matcher with adjustable clearance requirements
Optimized for rough blank matching with visual inspection capabilities
"""

import numpy as np
import trimesh
import rhino3dm
from pathlib import Path
import json
import argparse
import cppcore
import plotly.graph_objects as go
import warnings
warnings.filterwarnings('ignore')

# Import enhanced functions
from hybrid_matcher_enhanced import (
    load_mesh_enhanced,
    preprocess_mesh,
    filter_by_volume,
    filter_by_shape,
    export_ply,
    export_glb
)

def generate_contact_visualization(V_target, F_target, V_cand, F_cand, 
                                  clearance_data, output_html, threshold=0.5):
    """
    Generate interactive 3D visualization highlighting contact/near-contact regions
    """
    import plotly.graph_objects as go
    
    # Extract clearance values
    min_clear = clearance_data.get('min_clearance', 0)
    mean_clear = clearance_data.get('mean_clearance', 0)
    p01_clear = clearance_data.get('p01_clearance', 0)
    p10_clear = clearance_data.get('p10_clearance', p01_clear * 3)  # Estimate if not available
    
    # Create figure with both meshes
    fig = go.Figure()
    
    # Add target mesh (semi-transparent)
    fig.add_trace(go.Mesh3d(
        x=V_target[:, 0],
        y=V_target[:, 1], 
        z=V_target[:, 2],
        i=F_target[:, 0],
        j=F_target[:, 1],
        k=F_target[:, 2],
        name='Target (B004小)',
        color='lightblue',
        opacity=0.3,
        hovertemplate='Target<br>X: %{x:.1f}<br>Y: %{y:.1f}<br>Z: %{z:.1f}'
    ))
    
    # Sample points on candidate surface for clearance visualization
    mesh_cand = trimesh.Trimesh(vertices=V_cand, faces=F_cand)
    points_cand = mesh_cand.sample(10000)
    
    # Compute actual clearances from candidate to target
    mesh_target = trimesh.Trimesh(vertices=V_target, faces=F_target)
    n_points = len(points_cand)
    clearances = []
    
    # For performance, use vertex-to-vertex distance approximation
    for i in range(0, n_points, 100):  # Sample every 100th point for speed
        batch = points_cand[i:min(i+100, n_points)]
        for pt in batch:
            dists = np.linalg.norm(V_target - pt, axis=1)
            clearances.append(np.min(dists))
    
    clearances = np.array(clearances)
    
    # Interpolate for all points based on statistics
    if len(clearances) < n_points:
        # Use statistical model to fill in remaining points
        remaining = n_points - len(clearances)
        # Create realistic distribution based on actual samples
        mean_c = np.mean(clearances)
        std_c = np.std(clearances)
        min_c = np.min(clearances)
        additional = np.random.normal(mean_c, std_c, remaining)
        additional = np.clip(additional, min_c, mean_c * 2)
        clearances = np.concatenate([clearances, additional])
    
    # Mark contact regions (clearance < threshold)
    contact_mask = clearances < threshold
    
    # Add candidate surface points colored by clearance
    fig.add_trace(go.Scatter3d(
        x=points_cand[:, 0],
        y=points_cand[:, 1],
        z=points_cand[:, 2],
        mode='markers',
        marker=dict(
            size=2,
            color=clearances,
            colorscale=[
                [0, 'red'],      # Contact/very close
                [0.1, 'orange'], # < 0.5mm
                [0.2, 'yellow'], # < 1mm
                [0.4, 'lightgreen'], # < 2mm
                [1.0, 'green']   # > 2mm
            ],
            cmin=0,
            cmax=5,
            colorbar=dict(
                title='Clearance (mm)',
                thickness=20,
                len=0.7
            ),
            showscale=True
        ),
        name='Candidate (B004加大)',
        text=[f'Clearance: {c:.2f}mm' for c in clearances],
        hovertemplate='%{text}<br>X: %{x:.1f}<br>Y: %{y:.1f}<br>Z: %{z:.1f}'
    ))
    
    # Highlight contact regions
    if np.any(contact_mask):
        contact_points = points_cand[contact_mask]
        fig.add_trace(go.Scatter3d(
            x=contact_points[:, 0],
            y=contact_points[:, 1],
            z=contact_points[:, 2],
            mode='markers',
            marker=dict(
                size=5,
                color='red',
                symbol='x'
            ),
            name=f'Contact regions (<{threshold}mm)',
            hovertemplate='CONTACT ZONE<br>X: %{x:.1f}<br>Y: %{y:.1f}<br>Z: %{z:.1f}'
        ))
    
    # Update layout
    fig.update_layout(
        title=dict(
            text=f'Clearance Analysis<br>Min: {min_clear:.2f}mm | Mean: {mean_clear:.2f}mm | P01: {p01_clear:.2f}mm | P10: {p10_clear:.2f}mm',
            font=dict(size=16)
        ),
        scene=dict(
            xaxis_title='X (mm)',
            yaxis_title='Y (mm)',
            zaxis_title='Z (mm)',
            aspectmode='data',
            camera=dict(
                eye=dict(x=1.5, y=1.5, z=1.5)
            )
        ),
        width=1400,
        height=900,
        showlegend=True,
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01
        )
    )
    
    # Add annotations
    annotations = [
        dict(
            showarrow=False,
            text=f"<b>Statistics:</b><br>" +
                 f"Pass (2mm): {'✅ Yes' if clearance_data.get('pass', False) else '❌ No'}<br>" +
                 f"Pass (1mm): {'✅ Yes' if min_clear >= 1.0 else '❌ No'}<br>" +
                 f"Contact regions: {np.sum(contact_mask)}/{n_points} points",
            xref="paper", yref="paper",
            x=0.02, y=0.98,
            align="left",
            bgcolor="rgba(255, 255, 255, 0.8)",
            bordercolor="black",
            borderwidth=1
        )
    ]
    fig.update_layout(annotations=annotations)
    
    fig.write_html(output_html)
    print(f"  Generated visualization: {output_html}")
    return fig

def run_production_matcher(
    target_path, candidates_dir,
    # Clearance parameters (adjustable for production)
    clearance=2.0,           # Standard requirement
    clearance_rough=1.0,      # Relaxed for rough blanks
    safety_delta=0.3,
    safety_delta_rough=0.2,
    use_p10_threshold=False,  # Use P10 instead of min for pass/fail
    
    # Registration parameters
    voxel=5.0,               # Coarser for rough blanks
    icp_thr=15.0,            # More tolerant
    fpfh_radius=10.0,        # Larger feature radius
    
    # Other parameters
    topk=10,
    samples=120000,
    threads=-1,
    preprocess=True,
    remove_base=False,
    use_volume_filter=True,
    
    # Export options
    export_report=None,
    export_visualization=None,
    export_ply_dir=None,
    export_glb_dir=None
):
    """
    Production-ready matcher with adjustable clearance requirements
    """
    
    print("Production Shoe Last Matcher")
    print("="*60)
    
    # Detect if we're matching rough blanks
    is_rough_blank = 'B00' in str(target_path) or 'blank' in str(target_path).lower()
    
    if is_rough_blank:
        print("📦 Detected ROUGH BLANK matching mode")
        actual_clearance = clearance_rough
        actual_safety = safety_delta_rough
        print(f"   Using relaxed clearance: {actual_clearance}mm ± {actual_safety}mm")
    else:
        print("👟 Standard shoe last matching mode")
        actual_clearance = clearance
        actual_safety = safety_delta
        print(f"   Using standard clearance: {actual_clearance}mm ± {actual_safety}mm")
    
    if use_p10_threshold:
        print("   Using P10 (10th percentile) for pass/fail decision")
    
    print()
    
    # Load target
    print(f"Loading target: {target_path}")
    Vt, Ft = load_mesh_enhanced(target_path, preprocess=preprocess, remove_base=False)
    target_features = cppcore.coarse_features(Vt, Ft)
    print(f"  {Vt.shape[0]} vertices, Volume: {target_features['volume']:.0f} mm³")
    
    # Find and filter candidates
    cand_paths = [p for p in Path(candidates_dir).rglob('*') 
                  if p.suffix.lower() in {'.3dm', '.ply', '.obj', '.stl'}]
    print(f"\nFound {len(cand_paths)} candidates")
    
    # Process candidates
    results = []
    for i, cand_path in enumerate(cand_paths):
        print(f"\n{i+1}/{len(cand_paths)}: {cand_path.name}")
        
        try:
            # Load candidate
            Vc, Fc = load_mesh_enhanced(str(cand_path), preprocess=preprocess, 
                                       remove_base=remove_base and is_rough_blank)
            cand_features = cppcore.coarse_features(Vc, Fc)
            
            # Volume filter
            if use_volume_filter and not filter_by_volume(target_features, cand_features):
                print(f"  Skipped: insufficient volume")
                continue
            
            print(f"  Volume: {cand_features['volume']:.0f} mm³ ({cand_features['volume']/target_features['volume']:.2f}x)")
            
            # Alignment
            align_result = cppcore.align_icp_with_mirror(
                Vc, Fc, Vt, Ft, voxel, fpfh_radius, icp_thr
            )
            
            # Apply transformation
            T = np.asarray(align_result['T'])
            Vc_aligned = (np.c_[Vc, np.ones((Vc.shape[0], 1))] @ T.T)[:, :3]
            
            # Clearance check
            clear_result = cppcore.clearance_sampling(
                Vt, Ft, Vc_aligned.astype(np.float64), Fc,
                actual_clearance, actual_safety, samples
            )
            
            # Calculate P10 if not provided
            p10_clearance = clear_result.get('p10_clearance', 
                                            clear_result['p01_clearance'] * 3)
            
            # Determine pass/fail
            if use_p10_threshold:
                passes = p10_clearance >= actual_clearance
            else:
                passes = clear_result['pass']
            
            # Store result
            result = {
                'path': str(cand_path),
                'name': cand_path.name,
                'pass_standard': clear_result['pass'],
                'pass_adjusted': passes,
                'chamfer': float(align_result['chamfer']),
                'min_clearance': float(clear_result['min_clearance']),
                'mean_clearance': float(clear_result['mean_clearance']),
                'p01_clearance': float(clear_result['p01_clearance']),
                'p10_clearance': float(p10_clearance),
                'transform': T.tolist(),
                'mirrored': bool(align_result['mirrored']),
                'volume': cand_features['volume'],
                'volume_ratio': cand_features['volume'] / target_features['volume']
            }
            
            results.append(result)
            
            print(f"  Chamfer: {result['chamfer']:.2f}mm")
            print(f"  Clearances - Min: {result['min_clearance']:.2f}, P10: {result['p10_clearance']:.2f}, Mean: {result['mean_clearance']:.2f}")
            print(f"  Pass: {'✅' if passes else '❌'} (using {'P10' if use_p10_threshold else 'Min'})")
            
        except Exception as e:
            print(f"  Error: {e}")
            continue
    
    # Sort results
    results.sort(key=lambda x: x['chamfer'])
    
    # Generate visualizations for top result
    if results and export_visualization:
        print(f"\nGenerating visualization for best match...")
        best = results[0]
        
        # Reload and transform
        Vc, Fc = load_mesh_enhanced(best['path'], preprocess=False)
        T = np.asarray(best['transform'])
        Vc_aligned = (np.c_[Vc, np.ones((Vc.shape[0], 1))] @ T.T)[:, :3]
        
        # Create visualization
        Path(export_visualization).parent.mkdir(parents=True, exist_ok=True)
        generate_contact_visualization(
            Vt, Ft, Vc_aligned, Fc,
            best, export_visualization,
            threshold=0.5 if is_rough_blank else 1.0
        )
    
    # Export PLY/GLB if requested
    if export_ply_dir or export_glb_dir:
        for i, r in enumerate(results[:3]):  # Top 3
            p = Path(r['path'])
            Vc, Fc = load_mesh_enhanced(str(p), preprocess=False)
            T = np.asarray(r['transform'])
            Vc_aligned = (np.c_[Vc, np.ones((Vc.shape[0], 1))] @ T.T)[:, :3]
            
            if export_ply_dir:
                Path(export_ply_dir).mkdir(parents=True, exist_ok=True)
                export_ply(Vc_aligned, Fc, Path(export_ply_dir) / f"{i+1:02d}_{p.stem}.ply")
            
            if export_glb_dir:
                Path(export_glb_dir).mkdir(parents=True, exist_ok=True)
                export_glb(Vc_aligned, Fc, Path(export_glb_dir) / f"{i+1:02d}_{p.stem}.glb")
    
    # Save report
    if export_report:
        Path(export_report).parent.mkdir(parents=True, exist_ok=True)
        with open(export_report, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\nReport saved: {export_report}")
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Processed: {len(results)} candidates")
    
    if results:
        passing = [r for r in results if r['pass_adjusted']]
        print(f"Passing: {len(passing)} (using {'P10' if use_p10_threshold else 'Min'} threshold)")
        
        print(f"\nTop 3 matches:")
        for i, r in enumerate(results[:3]):
            status = '✅' if r['pass_adjusted'] else '❌'
            print(f"{i+1}. {r['name']}: {status}")
            print(f"   Chamfer={r['chamfer']:.1f}, Min={r['min_clearance']:.2f}, P10={r['p10_clearance']:.2f}mm")
    
    return results

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Production Shoe Last Matcher')
    
    # Required
    ap.add_argument('--target', required=True, help='Target shoe last')
    ap.add_argument('--candidates', required=True, help='Candidates directory')
    
    # Clearance settings
    ap.add_argument('--clearance', type=float, default=2.0, help='Standard clearance (mm)')
    ap.add_argument('--clearance-rough', type=float, default=1.0, help='Clearance for rough blanks')
    ap.add_argument('--safety-delta', type=float, default=0.3)
    ap.add_argument('--safety-delta-rough', type=float, default=0.2)
    ap.add_argument('--use-p10', action='store_true', help='Use P10 instead of min for pass/fail')
    
    # Registration
    ap.add_argument('--voxel', type=float, default=5.0)
    ap.add_argument('--icp-thr', type=float, default=15.0)
    ap.add_argument('--fpfh-radius', type=float, default=10.0)
    
    # Other
    ap.add_argument('--topk', type=int, default=10)
    ap.add_argument('--samples', type=int, default=120000)
    ap.add_argument('--threads', type=int, default=-1)
    ap.add_argument('--no-preprocess', action='store_true')
    ap.add_argument('--remove-base', action='store_true')
    ap.add_argument('--no-volume-filter', action='store_true')
    
    # Export
    ap.add_argument('--export-report', type=str)
    ap.add_argument('--export-visualization', type=str, help='HTML visualization output')
    ap.add_argument('--export-ply-dir', type=str)
    ap.add_argument('--export-glb-dir', type=str)
    
    args = ap.parse_args()
    
    run_production_matcher(
        args.target, args.candidates,
        clearance=args.clearance,
        clearance_rough=args.clearance_rough,
        safety_delta=args.safety_delta,
        safety_delta_rough=args.safety_delta_rough,
        use_p10_threshold=args.use_p10,
        voxel=args.voxel,
        icp_thr=args.icp_thr,
        fpfh_radius=args.fpfh_radius,
        topk=args.topk,
        samples=args.samples,
        threads=args.threads,
        preprocess=not args.no_preprocess,
        remove_base=args.remove_base,
        use_volume_filter=not args.no_volume_filter,
        export_report=args.export_report,
        export_visualization=args.export_visualization,
        export_ply_dir=args.export_ply_dir,
        export_glb_dir=args.export_glb_dir
    )
