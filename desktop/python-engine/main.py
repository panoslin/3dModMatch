#!/usr/bin/env python3
"""
Python Engine Wrapper for Shoe Last Matcher Desktop App
Handles JSON input/output for communication with Electron
"""

import sys
import json
import argparse
import traceback
from pathlib import Path

# Add engine directory to path
sys.path.insert(0, str(Path(__file__).parent / 'engine'))

# Import the matcher - main entry point is hybrid_matcher_multiprocess.py
try:
    from engine.hybrid_matcher_multiprocess import run_multiprocess_matcher
except ImportError:
    # Fallback if running directly
    from hybrid_matcher_multiprocess import run_multiprocess_matcher

def main():
    parser = argparse.ArgumentParser(description='Shoe Last Matcher Engine')
    parser.add_argument('--json-output', action='store_true', help='Output in JSON format')
    parser.add_argument('--version', action='store_true', help='Show version')
    
    # Matching parameters
    parser.add_argument('--target', type=str, help='Target model path')
    parser.add_argument('--candidates', type=str, help='Candidate paths (comma-separated)')
    parser.add_argument('--clearance', type=float, default=2.0, help='Clearance requirement')
    parser.add_argument('--enable-scaling', action='store_true', help='Enable scaling')
    parser.add_argument('--no-scaling', dest='enable_scaling', action='store_false')
    parser.add_argument('--enable-multi-start', action='store_true', help='Enable multi-start')
    parser.add_argument('--no-multi-start', dest='enable_multi_start', action='store_false')
    parser.add_argument('--threshold', choices=['min', 'p10', 'p15', 'p20'], default='p15')
    parser.add_argument('--max-scale', type=float, default=1.03)
    parser.add_argument('--export-heatmap-dir', type=str)
    parser.add_argument('--export-ply-dir', type=str)
    
    args = parser.parse_args()
    
    if args.version:
        print(json.dumps({'version': '1.0.0', 'engine': 'hybrid_matcher'}))
        return 0
    
    if not args.target or not args.candidates:
        print(json.dumps({'error': '需要提供目标模型和候选模型路径'}))
        return 1
    
    try:
        # Parse candidates
        if Path(args.candidates).is_dir():
            candidates_dir = args.candidates
        else:
            # If it's a comma-separated list of files, use parent directory
            candidate_files = args.candidates.split(',')
            if candidate_files:
                candidates_dir = str(Path(candidate_files[0]).parent)
            else:
                raise ValueError("无效的候选路径")
        
        # Progress callback for JSON output
        def progress_callback(stage, progress, message):
            if args.json_output:
                print(json.dumps({
                    'type': 'progress',
                    'stage': stage,
                    'progress': progress,
                    'message': message
                }, ensure_ascii=False))
                sys.stdout.flush()
        
        # Run the matcher
        progress_callback('preparing', 0, '开始匹配任务...')
        
        results = run_multiprocess_matcher(
            target_path=args.target,
            candidates_dir=candidates_dir,
            clearance=args.clearance,
            enable_scaling=args.enable_scaling,
            enable_multi_start=args.enable_multi_start,
            use_adaptive_threshold=args.threshold,
            max_scale=args.max_scale,
            export_heatmap_dir=args.export_heatmap_dir,
            export_ply_dir=args.export_ply_dir,
            num_processes=4  # Limit processes for desktop app
        )
        
        # Output results
        if args.json_output:
            print(json.dumps({
                'type': 'result',
                'stage': 'complete',
                'progress': 100,
                'message': '匹配完成',
                'details': results
            }, ensure_ascii=False, default=str))
        else:
            print(f"匹配完成，处理了 {len(results)} 个候选")
            for r in results[:3]:
                print(f"- {r['name']}: P15={r.get('p15_clearance', 0):.2f}mm")
        
        return 0
        
    except Exception as e:
        error_msg = str(e)
        if args.json_output:
            print(json.dumps({
                'type': 'error',
                'stage': 'processing',
                'progress': 0,
                'message': f'错误: {error_msg}',
                'details': traceback.format_exc()
            }, ensure_ascii=False))
        else:
            print(f"错误: {error_msg}", file=sys.stderr)
            traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
