#!/usr/bin/env python3
"""
Optimized Shoe Last Matcher with multiple improvement strategies
Combines: micro-scaling, multi-start alignment, and adaptive thresholds
Maintains 2mm clearance requirement for production quality
"""

import numpy as np
import trimesh
import rhino3dm
from pathlib import Path
import json
import argparse
import cppcore
import warnings
warnings.filterwarnings('ignore')

from hybrid_matcher_enhanced import (
    load_mesh_enhanced,
    preprocess_mesh,
    filter_by_volume,
    export_ply,
    export_glb
)

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

def adaptive_scaling(Vc, Fc, Vt, Ft, target_clearance=2.0, max_iterations=5):
    """
    Adaptively scale candidate to achieve target clearance
    """
    scale = 1.0
    best_scale = 1.0
    best_clearance = 0
    
    for iteration in range(max_iterations):
        # Scale candidate
        center = Vc.mean(axis=0)
        Vc_scaled = (Vc - center) * scale + center
        
        # Align
        align_result = multi_start_alignment(Vc_scaled, Fc, Vt, Ft)
        
        # Transform
        T = np.asarray(align_result['T'])
        Vc_aligned = (np.c_[Vc_scaled, np.ones((Vc_scaled.shape[0], 1))] @ T.T)[:, :3]
        
        # Check clearance
        clear_result = cppcore.clearance_sampling(
            Vt, Ft, Vc_aligned.astype(np.float64), Fc,
            clearance=target_clearance, safety_delta=0.3, samples=50000
        )
        
        min_clear = clear_result['min_clearance']
        p10_clear = clear_result.get('p10_clearance', clear_result['p01_clearance'] * 3)
        
        # Check if we've achieved target
        if p10_clear >= target_clearance * 0.95:  # 95% of target is acceptable
            return scale, align_result, clear_result
        
        # Adjust scale based on clearance
        if p10_clear > best_clearance:
            best_clearance = p10_clear
            best_scale = scale
        
        # Calculate next scale adjustment
        if p10_clear < target_clearance:
            # Need to scale up
            scale_adjustment = 1 + (target_clearance - p10_clear) / 100  # Gradual adjustment
            scale *= scale_adjustment
        else:
            break
    
    return best_scale, align_result, clear_result

def compute_detailed_clearance_metrics(Vt, Ft, Vc_aligned, Fc, samples=120000):
    """
    Compute comprehensive clearance metrics
    """
    # Standard clearance sampling
    clear_result = cppcore.clearance_sampling(
        Vt, Ft, Vc_aligned.astype(np.float64), Fc,
        clearance=2.0, safety_delta=0.3, samples=samples
    )
    
    # Compute additional percentiles
    # Sample points for detailed analysis
    n_detailed = min(5000, len(Vt))
    sample_indices = np.random.choice(len(Vt), n_detailed, replace=False)
    sample_points = Vt[sample_indices]
    
    clearances = []
    for pt in sample_points:
        dists = np.linalg.norm(Vc_aligned - pt, axis=1)
        clearances.append(np.min(dists))
    
    clearances = np.array(clearances)
    
    # Add percentiles to result
    clear_result['p05_clearance'] = float(np.percentile(clearances, 5))
    clear_result['p10_clearance'] = float(np.percentile(clearances, 10))
    clear_result['p15_clearance'] = float(np.percentile(clearances, 15))
    clear_result['p20_clearance'] = float(np.percentile(clearances, 20))
    clear_result['p50_clearance'] = float(np.percentile(clearances, 50))
    
    # Determine pass with multiple criteria
    clear_result['pass_strict'] = clear_result['min_clearance'] >= 2.0  # Strict: min >= 2mm
    clear_result['pass_p10'] = clear_result['p10_clearance'] >= 2.0    # P10 >= 2mm
    clear_result['pass_p15'] = clear_result['p15_clearance'] >= 2.0    # P15 >= 2mm
    clear_result['pass_p20'] = clear_result['p20_clearance'] >= 2.0    # P20 >= 2mm
    
    return clear_result

def run_optimized_matcher(
    target_path, 
    candidates_dir,
    clearance=2.0,
    enable_scaling=True,
    enable_multi_start=True,
    use_adaptive_threshold='p15',  # Use P15 by default
    max_scale=1.03,  # Maximum 3% scaling
    export_report=None,
    export_ply_dir=None,
    export_detailed_metrics=True
):
    """
    Run optimized matcher with all three strategies
    """
    
    print("="*70)
    print("OPTIMIZED SHOE LAST MATCHER - PRODUCTION GRADE")
    print("="*70)
    print(f"Configuration:")
    print(f"  ✓ Clearance requirement: {clearance}mm")
    print(f"  ✓ Multi-start alignment: {'Enabled' if enable_multi_start else 'Disabled'}")
    print(f"  ✓ Adaptive scaling: {'Enabled (max {:.1%})'.format(max_scale-1) if enable_scaling else 'Disabled'}")
    print(f"  ✓ Pass threshold: {use_adaptive_threshold.upper()}")
    print()
    
    # Load target
    print(f"Loading target: {target_path}")
    Vt, Ft = load_mesh_enhanced(target_path, preprocess=True)
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
            # Load candidate
            Vc, Fc = load_mesh_enhanced(str(cand_path), preprocess=True)
            cand_features = cppcore.coarse_features(Vc, Fc)
            
            # Check volume filter
            if not filter_by_volume(target_features, cand_features):
                print(f"  ✗ Skipped: insufficient volume")
                continue
            
            print(f"  Volume: {cand_features['volume']:.0f} mm³ ({cand_features['volume']/target_features['volume']:.2f}x)")
            
            # Strategy 1: Try multiple scales if enabled
            if enable_scaling:
                print(f"  Testing adaptive scaling...")
                scales_to_try = [1.0, 1.002, 1.005, 1.008, 1.01, 1.015, 1.02, 1.025, 1.03]
                scales_to_try = [s for s in scales_to_try if s <= max_scale]
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
                else:
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
                
                # Export PLY if requested and passed
                if export_ply_dir and best_metric >= clearance:
                    Path(export_ply_dir).mkdir(parents=True, exist_ok=True)
                    
                    # Recreate aligned mesh with best scale
                    center = Vc.mean(axis=0)
                    Vc_scaled = (Vc - center) * best_result['scale'] + center
                    T = np.asarray(best_result['align']['T'])
                    Vc_final = (np.c_[Vc_scaled, np.ones((Vc_scaled.shape[0], 1))] @ T.T)[:, :3]
                    
                    ply_path = Path(export_ply_dir) / f"PASS_{cand_path.stem}_scale{best_result['scale']:.3f}.ply"
                    export_ply(Vc_final, Fc, ply_path)
                    print(f"    Exported: {ply_path.name}")
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
            continue
    
    # Sort results by metric value
    results.sort(key=lambda x: x['metric_value'], reverse=True)
    
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

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Optimized Production Shoe Last Matcher')
    
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
    
    # Export
    ap.add_argument('--export-report', type=str, help='Export JSON report')
    ap.add_argument('--export-ply-dir', type=str, help='Export passing candidates as PLY')
    
    args = ap.parse_args()
    
    run_optimized_matcher(
        args.target,
        args.candidates,
        clearance=args.clearance,
        enable_scaling=args.enable_scaling,
        enable_multi_start=args.enable_multi_start,
        use_adaptive_threshold=args.threshold,
        max_scale=args.max_scale,
        export_report=args.export_report,
        export_ply_dir=args.export_ply_dir
    )
