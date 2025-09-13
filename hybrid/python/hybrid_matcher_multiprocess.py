#!/usr/bin/env python3
"""
Multi-Process Shoe Last Matcher
使用多进程并行处理候选模型，避免OpenMP线程问题
每个候选模型在独立进程中处理
"""

import numpy as np
import multiprocessing as mp
from multiprocessing import Pool, cpu_count
from functools import partial
import os
import sys
from pathlib import Path
import json
import argparse
import time
import traceback

# 确保能导入cppcore
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['OMP_NUM_THREADS'] = '1'  # 每个进程内禁用OpenMP

# 导入主matcher的功能
from hybrid_matcher import (
    load_mesh_enhanced,
    filter_by_volume,
    multi_start_alignment,
    compute_detailed_clearance_metrics,
    export_ply,
    export_glb,
    generate_clearance_heatmap
)
import cppcore


def process_single_candidate(args):
    """
    处理单个候选模型的工作函数
    在独立进程中运行
    """
    (cand_path, target_data, params) = args
    
    try:
        # 解包参数
        Vt, Ft, target_features = target_data
        
        # 设置进程内环境
        os.environ['OMP_NUM_THREADS'] = '1'
        
        # 打印进程信息
        pid = os.getpid()
        print(f"  [PID {pid}] Processing: {cand_path.name}")
        
        # 加载候选模型
        is_rough = 'B00' in cand_path.name or '113' in cand_path.name
        Vc, Fc = load_mesh_enhanced(
            str(cand_path), 
            preprocess=params['preprocess'],
            remove_base=is_rough and params['remove_base']
        )
        
        # 计算特征
        cand_features = cppcore.coarse_features(Vc, Fc)
        
        # 体积过滤
        if params['use_volume_filter'] and not filter_by_volume(target_features, cand_features):
            print(f"  [PID {pid}] ✗ Skipped: insufficient volume")
            return None
        
        print(f"  [PID {pid}] Volume: {cand_features['volume']:.0f} mm³ "
              f"({cand_features['volume']/target_features['volume']:.2f}x)")
        
        # 尝试多个缩放比例
        best_result = None
        best_metric = -float('inf')
        
        scales_to_try = params.get('scales', [1.0])
        
        for scale in scales_to_try:
            # 缩放候选模型
            center = Vc.mean(axis=0)
            Vc_scaled = (Vc - center) * scale + center
            
            # 对齐
            if params['enable_multi_start']:
                align_result = multi_start_alignment(
                    Vc_scaled, Fc, Vt, Ft, 
                    n_starts=3,
                    voxel=params['voxel'],
                    fpfh_radius=params['fpfh_radius'],
                    icp_thr=params['icp_thr']
                )
            else:
                align_result = cppcore.align_icp_with_mirror(
                    Vc_scaled, Fc, Vt, Ft,
                    params['voxel'],
                    params['fpfh_radius'],
                    params['icp_thr']
                )
            
            # 变换
            T = np.asarray(align_result['T'])
            Vc_aligned = (np.c_[Vc_scaled, np.ones((Vc_scaled.shape[0], 1))] @ T.T)[:, :3]
            
            # 计算间隙指标
            clear_result = compute_detailed_clearance_metrics(Vt, Ft, Vc_aligned, Fc)
            
            # 选择评价指标
            threshold = params['use_adaptive_threshold']
            if threshold == 'min':
                metric = clear_result['min_clearance']
            elif threshold == 'p10':
                metric = clear_result['p10_clearance']
            elif threshold == 'p15':
                metric = clear_result['p15_clearance']
            elif threshold == 'p20':
                metric = clear_result['p20_clearance']
            else:
                metric = clear_result['p15_clearance']
            
            # 更新最佳结果
            if metric > best_metric:
                best_metric = metric
                best_result = {
                    'scale': scale,
                    'align': align_result,
                    'clearance': clear_result,
                    'metric': metric,
                    'Vc_final': Vc_aligned,
                    'Fc': Fc
                }
            
            # 如果满足要求，提前退出
            if metric >= params['clearance']:
                print(f"  [PID {pid}] ✓ Scale {scale:.3f}: "
                      f"{threshold}={metric:.2f}mm - PASS!")
                break
        
        # 构建结果
        if best_result:
            result = {
                'path': str(cand_path),
                'name': cand_path.name,
                'pid': pid,
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
                'inside_ratio': float(best_result['clearance'].get('inside_ratio', 0.0)),
                'pass_strict': best_result['clearance']['pass_strict'],
                'pass_p10': best_result['clearance']['pass_p10'],
                'pass_p15': best_result['clearance']['pass_p15'],
                'pass_p20': best_result['clearance']['pass_p20'],
                'selected_metric': params['use_adaptive_threshold'],
                'metric_value': best_metric,
                'transform': best_result['align']['T'].tolist(),
                'volume': cand_features['volume'],
                'volume_ratio': cand_features['volume'] / target_features['volume'],
                # 保存对齐后的网格用于导出
                '_mesh_data': (best_result['Vc_final'], best_result['Fc']) if best_metric >= params['clearance'] else None
            }
            
            status = "✅ PASS" if best_metric >= params['clearance'] else "❌ FAIL"
            print(f"  [PID {pid}] Result: {status} - "
                  f"Best scale: {best_result['scale']:.3f}, "
                  f"{params['use_adaptive_threshold']}={best_metric:.2f}mm")
            
            return result
        
        return None
        
    except Exception as e:
        print(f"  [PID {os.getpid()}] ✗ Error processing {cand_path.name}: {e}")
        traceback.print_exc()
        return {'path': str(cand_path), 'name': cand_path.name, 'error': str(e)}


def run_multiprocess_matcher(
    target_path,
    candidates_dir,
    clearance=2.0,
    enable_scaling=True,
    enable_multi_start=True,
    use_adaptive_threshold='p15',
    max_scale=1.03,
    preprocess=True,
    remove_base=False,
    use_volume_filter=True,
    num_processes=None,
    export_report=None,
    export_ply_dir=None,
    export_glb_dir=None,
    export_heatmap_dir=None,
    export_topk=3
):
    """
    使用多进程运行匹配器
    """
    
    # 计算进程数
    if num_processes is None:
        num_processes = cpu_count() * 2  # 默认使用2倍CPU核心数
    
    print("="*70)
    print("MULTI-PROCESS SHOE LAST MATCHER")
    print("="*70)
    print(f"System Info:")
    print(f"  • CPU cores: {cpu_count()}")
    print(f"  • Process pool size: {num_processes}")
    print(f"Configuration:")
    print(f"  ✓ Clearance requirement: {clearance}mm")
    print(f"  ✓ Multi-start alignment: {'Enabled' if enable_multi_start else 'Disabled'}")
    print(f"  ✓ Adaptive scaling: {'Enabled (max {:.1%})'.format(max_scale-1) if enable_scaling else 'Disabled'}")
    print(f"  ✓ Pass threshold: {use_adaptive_threshold.upper()}")
    print(f"  ✓ Preprocessing: {'Enabled' if preprocess else 'Disabled'}")
    print(f"  ✓ Volume filter: {'Enabled' if use_volume_filter else 'Disabled'}")
    print()
    
    start_time = time.time()
    
    # 加载目标模型
    print(f"Loading target: {target_path}")
    Vt, Ft = load_mesh_enhanced(target_path, preprocess=preprocess, remove_base=False)
    target_features = cppcore.coarse_features(Vt, Ft)
    print(f"  {Vt.shape[0]} vertices, Volume: {target_features['volume']:.0f} mm³")
    
    # 查找候选文件
    cand_paths = [p for p in Path(candidates_dir).rglob('*') 
                  if p.suffix.lower() in {'.3dm', '.ply', '.obj', '.stl'}]
    print(f"\nFound {len(cand_paths)} candidate files")
    
    # 准备参数
    if enable_scaling:
        scales = np.arange(1.0, max_scale + 0.001, 0.002).tolist()
    else:
        scales = [1.0]
    
    params = {
        'clearance': clearance,
        'enable_multi_start': enable_multi_start,
        'use_adaptive_threshold': use_adaptive_threshold,
        'scales': scales,
        'preprocess': preprocess,
        'remove_base': remove_base,
        'use_volume_filter': use_volume_filter,
        'voxel': 5.0,
        'fpfh_radius': 10.0,
        'icp_thr': 15.0
    }
    
    # 准备目标数据（将在所有进程间共享）
    target_data = (Vt, Ft, target_features)
    
    # 创建任务列表
    tasks = [(cand_path, target_data, params) for cand_path in cand_paths]
    
    print(f"\nStarting parallel processing with {num_processes} processes...")
    print("-"*70)
    
    # 使用进程池并行处理
    with Pool(processes=num_processes) as pool:
        results = pool.map(process_single_candidate, tasks)
    
    # 过滤None结果
    results = [r for r in results if r is not None]
    
    # 按指标值排序
    results.sort(key=lambda x: x.get('metric_value', -float('inf')), reverse=True)
    
    # 导出通过的结果
    if export_ply_dir or export_glb_dir:
        passing_results = [r for r in results if r.get(f'pass_{use_adaptive_threshold}', False)]
        
        for r in passing_results[:export_topk]:
            if '_mesh_data' in r and r['_mesh_data']:
                Vc_final, Fc = r['_mesh_data']
                base_name = f"PASS_{Path(r['path']).stem}_scale{r['scale_used']:.3f}"
                
                if export_ply_dir:
                    Path(export_ply_dir).mkdir(parents=True, exist_ok=True)
                    ply_path = Path(export_ply_dir) / f"{base_name}.ply"
                    export_ply(Vc_final, Fc, ply_path)
                
                if export_glb_dir:
                    Path(export_glb_dir).mkdir(parents=True, exist_ok=True)
                    glb_path = Path(export_glb_dir) / f"{base_name}.glb"
                    export_glb(Vc_final, Fc, glb_path)
    
    # 生成热图
    if export_heatmap_dir and results:
        Path(export_heatmap_dir).mkdir(parents=True, exist_ok=True)
        for i, r in enumerate(results[:min(export_topk, len(results))]):
            if r.get(f'pass_{use_adaptive_threshold}', False) and '_mesh_data' in r:
                Vc_final, Fc = r['_mesh_data']
                html_path = Path(export_heatmap_dir) / f"{i+1:02d}_{Path(r['path']).stem}_heatmap.html"
                generate_clearance_heatmap(Vt, Ft, Vc_final, Fc, r, html_path)
    
    # 清理内部数据
    for r in results:
        if '_mesh_data' in r:
            del r['_mesh_data']
    
    # 保存报告
    if export_report:
        Path(export_report).parent.mkdir(parents=True, exist_ok=True)
        with open(export_report, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n📊 Report saved: {export_report}")
    
    # 统计和总结
    elapsed_time = time.time() - start_time
    
    print("\n" + "="*70)
    print("FINAL SUMMARY")
    print("="*70)
    
    passing_strict = [r for r in results if r.get('pass_strict', False)]
    passing_p10 = [r for r in results if r.get('pass_p10', False)]
    passing_p15 = [r for r in results if r.get('pass_p15', False)]
    passing_p20 = [r for r in results if r.get('pass_p20', False)]
    
    print(f"Processing time: {elapsed_time:.2f} seconds")
    print(f"Average time per candidate: {elapsed_time/max(1, len(cand_paths)):.2f} seconds")
    print(f"Total candidates processed: {len(results)}")
    print(f"Passing criteria:")
    print(f"  • Strict (Min ≥ {clearance}mm): {len(passing_strict)}")
    print(f"  • P10 ≥ {clearance}mm: {len(passing_p10)}")
    print(f"  • P15 ≥ {clearance}mm: {len(passing_p15)}")
    print(f"  • P20 ≥ {clearance}mm: {len(passing_p20)}")
    
    if results:
        print(f"\nTop matches:")
        for i, r in enumerate(results[:3]):
            status = "✅" if r.get(f'pass_{use_adaptive_threshold}', False) else "❌"
            print(f"{i+1}. {r['name']}: {status}")
            print(f"   Scale: {r['scale_used']:.3f}, Chamfer: {r['chamfer']:.1f}mm")
            print(f"   Min={r['min_clearance']:.2f}, P10={r['p10_clearance']:.2f}, "
                  f"P15={r['p15_clearance']:.2f}, P20={r['p20_clearance']:.2f}mm")
            print(f"   Processed by PID: {r.get('pid', 'N/A')}")
    
    print(f"\n✨ Multi-process execution completed successfully!")
    print(f"   Speedup: ~{num_processes}x theoretical maximum")
    
    return results


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Multi-Process Shoe Last Matcher')
    
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
    
    # Multiprocessing
    ap.add_argument('--processes', type=int, default=None, 
                    help='Number of processes (default: 2*CPU_count)')
    
    # Export
    ap.add_argument('--export-report', type=str, help='Export JSON report')
    ap.add_argument('--export-ply-dir', type=str, help='Export passing candidates as PLY')
    ap.add_argument('--export-glb-dir', type=str, help='Export passing candidates as GLB')
    ap.add_argument('--export-heatmap-dir', type=str, help='Export clearance heatmap HTML')
    ap.add_argument('--export-topk', type=int, default=3, help='Number of results to export')
    
    args = ap.parse_args()
    
    # 设置进程数
    if args.processes is None:
        args.processes = cpu_count() * 2
    
    run_multiprocess_matcher(
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
        num_processes=args.processes,
        export_report=args.export_report,
        export_ply_dir=args.export_ply_dir,
        export_glb_dir=args.export_glb_dir,
        export_heatmap_dir=args.export_heatmap_dir,
        export_topk=args.export_topk
    )
