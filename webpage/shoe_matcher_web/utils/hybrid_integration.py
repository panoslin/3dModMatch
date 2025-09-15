"""
Hybrid匹配系统集成工具
"""

import os
import subprocess
import json
import tempfile
import shutil
import logging
from pathlib import Path
from django.conf import settings

logger = logging.getLogger(__name__)


class HybridMatcherService:
    """Hybrid匹配服务"""
    
    def __init__(self):
        self.docker_image = getattr(settings, 'MATCHER_DOCKER_IMAGE', 'panoslin/shoe_matcher_hybrid:latest')
        # 在Docker环境中，hybrid路径不同
        if os.environ.get('DJANGO_ENVIRONMENT') == 'docker':
            self.hybrid_path = Path('/app')  # 在Docker容器中
        else:
            self.hybrid_path = Path(settings.BASE_DIR).parent.parent / 'hybrid'
    
    def check_hybrid_system(self):
        """检查hybrid系统是否可用"""
        try:
            # 检查Docker镜像是否存在
            result = subprocess.run(
                ['docker', 'images', '-q', self.docker_image],
                capture_output=True, text=True, timeout=10
            )
            
            if not result.stdout.strip():
                logger.warning(f"Docker镜像 {self.docker_image} 不存在")
                return False
            
            # 在Docker环境中，我们依赖hybrid容器内的C++模块，不需要检查本地
            if os.environ.get('DJANGO_ENVIRONMENT') == 'docker':
                logger.info("Docker环境中，跳过本地C++模块检查")
                return True
            
            # 非Docker环境才检查本地C++模块
            cppcore_so = self.hybrid_path / 'build' / 'cppcore.cpython-310-x86_64-linux-gnu.so'
            if not cppcore_so.exists():
                logger.warning("C++模块未构建")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"检查hybrid系统失败: {e}")
            return False
    
    def build_cpp_core(self):
        """构建C++核心模块"""
        # 在Docker环境中，不需要构建本地C++模块
        if os.environ.get('DJANGO_ENVIRONMENT') == 'docker':
            logger.info("Docker环境中，跳过C++模块构建")
            return True
            
        try:
            logger.info("开始构建C++核心模块...")
            
            # 执行构建脚本
            build_script = self.hybrid_path / 'build_cpp.sh'
            if not build_script.exists():
                raise FileNotFoundError("构建脚本不存在")
            
            result = subprocess.run(
                ['bash', str(build_script)],
                cwd=str(self.hybrid_path),
                capture_output=True,
                text=True,
                timeout=600  # 10分钟超时
            )
            
            if result.returncode == 0:
                logger.info("C++模块构建成功")
                return True
            else:
                logger.error(f"C++模块构建失败: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"构建C++模块时出错: {e}")
            return False
    
    def run_matching(self, target_file, candidates_dir, output_dir, params):
        """运行匹配算法"""
        try:
            # 构建Docker命令
            cmd = self.build_docker_command(
                target_file, candidates_dir, output_dir, params
            )
            
            logger.info(f"执行匹配命令: {' '.join(cmd)}")
            
            # 执行命令
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1800  # 30分钟超时
            )
            
            if result.returncode == 0:
                logger.info("匹配执行成功")
                return {
                    'success': True,
                    'stdout': result.stdout,
                    'stderr': result.stderr
                }
            else:
                logger.error(f"匹配执行失败: {result.stderr}")
                return {
                    'success': False,
                    'error': result.stderr,
                    'stdout': result.stdout
                }
                
        except subprocess.TimeoutExpired:
            logger.error("匹配执行超时")
            return {
                'success': False,
                'error': '匹配执行超时'
            }
        except Exception as e:
            logger.error(f"执行匹配时出错: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def build_docker_command(self, target_file, candidates_dir, output_dir, params):
        """构建Docker命令"""
        cmd = [
            'docker', 'run', '--rm',
            '-v', f'{target_file}:/app/target.3dm:ro',
            '-v', f'{candidates_dir}:/app/candidates:ro',
            '-v', f'{output_dir}:/app/output',
            '--network', 'webpage_shoe_matcher_network',  # 使用同一网络
            '--entrypoint', '',  # 跳过entrypoint脚本
            '-e', 'LD_LIBRARY_PATH=/usr/local/lib',
            '-e', 'LD_PRELOAD=/usr/local/lib/libOpen3D.so',
            '-e', 'PYTHONPATH=/app/python',
            '-e', 'OMP_NUM_THREADS=1',
            self.docker_image,
            'python3', 'python/hybrid_matcher_multiprocess.py',
            '--target', '/app/target.3dm',
            '--candidates', '/app/candidates',
            '--clearance', str(params.get('clearance', 2.0)),
            '--threshold', params.get('threshold', 'p15'),
            '--export-report', '/app/output/report.json',
            '--export-ply-dir', '/app/output/ply'
            # 暂时不生成热图
            # '--export-heatmap-dir', '/app/output/heatmaps'
        ]
        
        # 添加可选参数
        if params.get('enable_scaling', True):
            cmd.extend([
                '--enable-scaling', 
                '--max-scale', str(params.get('max_scale', 1.03))
            ])
        else:
            cmd.append('--no-scaling')
        
        if params.get('enable_multi_start', True):
            cmd.append('--enable-multi-start')
        else:
            cmd.append('--no-multi-start')
        
        return cmd
    
    def parse_results(self, output_dir):
        """解析匹配结果"""
        try:
            report_file = Path(output_dir) / 'report.json'
            
            if not report_file.exists():
                raise FileNotFoundError("匹配报告文件不存在")
            
            with open(report_file, 'r', encoding='utf-8') as f:
                results = json.load(f)
            
            # 处理结果数据
            processed_results = []
            for result in results:
                processed_result = {
                    'blank_name': result.get('name', ''),
                    'blank_path': result.get('path', ''),
                    'inside_ratio': result.get('inside_ratio', 0.0),
                    'volume_ratio': result.get('volume_ratio', 0.0),
                    'min_clearance': result.get('min_clearance', 0.0),
                    'p15_clearance': result.get('p15_clearance', 0.0),
                    'chamfer': result.get('chamfer', 0.0),
                    'scale_used': result.get('scale_used', 1.0),
                    'mirrored': result.get('mirrored', False),
                    'pass_p15': result.get('pass_p15', False),
                    # 添加所有其他指标
                    **{k: v for k, v in result.items() if k.startswith('p') and k.endswith('_clearance')},
                    **{k: v for k, v in result.items() if k.startswith('pass_')}
                }
                processed_results.append(processed_result)
            
            # 计算汇总统计
            total = len(processed_results)
            summary = {
                'total_candidates': total,
                'passed_strict': sum(1 for r in processed_results if r.get('pass_strict', False)),
                'passed_p10': sum(1 for r in processed_results if r.get('pass_p10', False)),
                'passed_p15': sum(1 for r in processed_results if r.get('pass_p15', False)),
                'passed_p20': sum(1 for r in processed_results if r.get('pass_p20', False)),
            }
            
            return {
                'success': True,
                'results': processed_results,
                'summary': summary
            }
            
        except Exception as e:
            logger.error(f"解析结果失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# 全局服务实例
hybrid_service = HybridMatcherService()
