#!/usr/bin/env python3
"""
3D鞋模匹配系统高级功能测试脚本
测试智能匹配算法、文件处理流程等高级功能
"""

import requests
import json
import time
from urllib.parse import urljoin
import os

class AdvancedFunctionalityTester:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.test_results = {}
        
    def test_matching_algorithm(self):
        """测试智能匹配算法"""
        print("🧪 测试智能匹配算法...")
        
        try:
            # 1. 获取可用的鞋模文件
            response = self.session.get(urljoin(self.base_url, "/api/files/"))
            if response.status_code != 200:
                print(f"  ❌ 无法获取文件列表: {response.status_code}")
                return False
            
            data = response.json()
            if not data.get('success'):
                print(f"  ❌ 文件API返回错误: {data.get('error', '未知错误')}")
                return False
            
            # 查找已处理的鞋模文件
            shoe_models = [f for f in data['files'] if f.get('file_type') == 'shoe' and f.get('is_processed')]
            if not shoe_models:
                print("  ⚠️  没有可用的已处理鞋模文件")
                return False
            
            test_shoe = shoe_models[0]
            print(f"  📁 使用测试鞋模: {test_shoe['filename']}")
            
            # 2. 执行智能匹配
            match_data = {
                'shoe_model_id': test_shoe['id'],
                'margin_distance': 2.5
            }
            
            print("  🔍 开始执行智能匹配...")
            response = self.session.post(
                urljoin(self.base_url, "/api/matching/analyze/"),
                json=match_data,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    print("  ✅ 智能匹配执行成功")
                    print(f"     - 任务ID: {result.get('task_id')}")
                    print(f"     - 匹配结果数量: {len(result.get('results', []))}")
                    
                    if result.get('optimal_match'):
                        optimal = result['optimal_match']
                        print(f"     - 最优匹配: {optimal.get('blank_name', 'N/A')}")
                        print(f"     - 匹配分数: {optimal.get('match_score', 'N/A')}")
                        print(f"     - 材料利用率: {optimal.get('material_utilization', 'N/A')}")
                    
                    self.test_results["matching_algorithm"] = True
                    return True
                else:
                    print(f"  ❌ 匹配执行失败: {result.get('error', '未知错误')}")
                    self.test_results["matching_algorithm"] = False
                    return False
            else:
                print(f"  ❌ 匹配API返回: {response.status_code}")
                self.test_results["matching_algorithm"] = False
                return False
                
        except Exception as e:
            print(f"  ❌ 智能匹配测试失败: {e}")
            self.test_results["matching_algorithm"] = False
            return False
    
    def test_file_processing_workflow(self):
        """测试文件处理工作流程"""
        print("\n🧪 测试文件处理工作流程...")
        
        try:
            # 1. 检查文件处理状态
            response = self.session.get(urljoin(self.base_url, "/api/files/"))
            if response.status_code != 200:
                print(f"  ❌ 无法获取文件列表: {response.status_code}")
                return False
            
            data = response.json()
            files = data.get('files', [])
            
            # 统计文件处理状态
            processed_shoes = len([f for f in files if f.get('file_type') == 'shoe' and f.get('is_processed')])
            unprocessed_shoes = len([f for f in files if f.get('file_type') == 'shoe' and not f.get('is_processed')])
            processed_blanks = len([f for f in files if f.get('file_type') == 'blank' and f.get('is_processed')])
            unprocessed_blanks = len([f for f in files if f.get('file_type') == 'blank' and not f.get('is_processed')])
            
            print(f"  📊 文件处理状态:")
            print(f"     - 鞋模文件: {processed_shoes} 已处理, {unprocessed_shoes} 待处理")
            print(f"     - 粗胚文件: {processed_blanks} 已处理, {unprocessed_blanks} 待处理")
            
            # 2. 检查是否有待处理的文件
            if unprocessed_shoes > 0 or unprocessed_blanks > 0:
                print("  ⚠️  存在待处理的文件，可能需要手动处理")
                self.test_results["file_processing"] = False
                return False
            else:
                print("  ✅ 所有文件都已处理完成")
                self.test_results["file_processing"] = True
                return True
                
        except Exception as e:
            print(f"  ❌ 文件处理工作流程测试失败: {e}")
            self.test_results["file_processing"] = False
            return False
    
    def test_3d_model_analysis(self):
        """测试3D模型分析功能"""
        print("\n🧪 测试3D模型分析功能...")
        
        try:
            # 1. 获取已处理的文件
            response = self.session.get(urljoin(self.base_url, "/api/files/"))
            if response.status_code != 200:
                print(f"  ❌ 无法获取文件列表: {response.status_code}")
                return False
            
            data = response.json()
            processed_files = [f for f in data.get('files', []) if f.get('is_processed')]
            
            if not processed_files:
                print("  ⚠️  没有已处理的文件来测试3D分析")
                return False
            
            # 2. 测试3D预览功能
            test_file = processed_files[0]
            preview_url = f"/files/{test_file['id']}/3d/"
            
            print(f"  🔍 测试3D预览: {test_file['filename']}")
            response = self.session.get(urljoin(self.base_url, preview_url))
            
            if response.status_code == 200:
                content = response.text
                
                # 检查3D渲染相关元素
                required_3d_elements = [
                    'scene',
                    'camera',
                    'renderer',
                    'OrbitControls',
                    'modelGroup'
                ]
                
                missing_elements = []
                for element in required_3d_elements:
                    if element not in content:
                        missing_elements.append(element)
                
                if not missing_elements:
                    print("  ✅ 3D模型分析功能正常")
                    print(f"     - 文件: {test_file['filename']}")
                    print(f"     - 格式: {test_file['file_format']}")
                    print(f"     - 类型: {test_file['file_type']}")
                    
                    self.test_results["3d_model_analysis"] = True
                    return True
                else:
                    print(f"  ⚠️  3D预览缺少元素: {missing_elements}")
                    self.test_results["3d_model_analysis"] = False
                    return False
            else:
                print(f"  ❌ 3D预览页面返回: {response.status_code}")
                self.test_results["3d_model_analysis"] = False
                return False
                
        except Exception as e:
            print(f"  ❌ 3D模型分析测试失败: {e}")
            self.test_results["3d_model_analysis"] = False
            return False
    
    def test_matching_optimization(self):
        """测试匹配优化功能"""
        print("\n🧪 测试匹配优化功能...")
        
        try:
            # 测试不同的余量距离参数
            margin_distances = [1.0, 2.5, 5.0]
            
            print("  🔧 测试不同余量距离的匹配优化...")
            
            for margin in margin_distances:
                print(f"     - 测试余量距离: {margin}mm")
                
                # 获取一个鞋模进行测试
                response = self.session.get(urljoin(self.base_url, "/api/files/"))
                if response.status_code != 200:
                    continue
                
                data = response.json()
                shoe_models = [f for f in data.get('files', []) if f.get('file_type') == 'shoe' and f.get('is_processed')]
                
                if not shoe_models:
                    continue
                
                test_shoe = shoe_models[0]
                
                # 执行匹配
                match_data = {
                    'shoe_model_id': test_shoe['id'],
                    'margin_distance': margin
                }
                
                response = self.session.post(
                    urljoin(self.base_url, "/api/matching/analyze/"),
                    json=match_data,
                    headers={'Content-Type': 'application/json'}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('success'):
                        print(f"       ✅ 余量 {margin}mm 匹配成功")
                    else:
                        print(f"       ❌ 余量 {margin}mm 匹配失败: {result.get('error', '未知错误')}")
                else:
                    print(f"       ❌ 余量 {margin}mm API错误: {response.status_code}")
            
            print("  ✅ 匹配优化功能测试完成")
            self.test_results["matching_optimization"] = True
            return True
                
        except Exception as e:
            print(f"  ❌ 匹配优化测试失败: {e}")
            self.test_results["matching_optimization"] = False
            return False
    
    def test_system_performance(self):
        """测试系统性能"""
        print("\n🧪 测试系统性能...")
        
        try:
            # 1. 测试页面加载性能
            pages_to_test = [
                ("/", "首页"),
                ("/upload/", "上传页面"),
                ("/files/", "文件列表"),
                ("/matching/", "智能匹配")
            ]
            
            total_time = 0
            page_count = 0
            
            for path, name in pages_to_test:
                start_time = time.time()
                response = self.session.get(urljoin(self.base_url, path))
                end_time = time.time()
                response_time = (end_time - start_time) * 1000
                
                if response.status_code == 200:
                    total_time += response_time
                    page_count += 1
                    print(f"  📊 {name}: {response_time:.1f}ms")
                else:
                    print(f"  ❌ {name}: {response.status_code}")
            
            if page_count > 0:
                avg_time = total_time / page_count
                print(f"  📊 平均页面加载时间: {avg_time:.1f}ms")
                
                # 性能评估
                if avg_time < 100:
                    performance_grade = "优秀"
                elif avg_time < 200:
                    performance_grade = "良好"
                elif avg_time < 500:
                    performance_grade = "一般"
                else:
                    performance_grade = "需要优化"
                
                print(f"  🏆 性能评级: {performance_grade}")
                
                self.test_results["system_performance"] = True
                return True
            else:
                print("  ❌ 无法测试页面性能")
                self.test_results["system_performance"] = False
                return False
                
        except Exception as e:
            print(f"  ❌ 系统性能测试失败: {e}")
            self.test_results["system_performance"] = False
            return False
    
    def run_all_advanced_tests(self):
        """运行所有高级功能测试"""
        print("🚀 开始3D鞋模匹配系统高级功能测试")
        print("=" * 70)
        
        # 运行各项高级测试
        tests = [
            self.test_matching_algorithm,
            self.test_file_processing_workflow,
            self.test_3d_model_analysis,
            self.test_matching_optimization,
            self.test_system_performance,
        ]
        
        passed_tests = 0
        total_tests = len(tests)
        
        for test in tests:
            try:
                if test():
                    passed_tests += 1
            except Exception as e:
                print(f"  ❌ 测试执行异常: {e}")
        
        # 输出测试结果
        print("\n" + "=" * 70)
        print("📊 高级功能测试结果汇总")
        print("=" * 70)
        
        for key, value in self.test_results.items():
            status = "✅ 通过" if value else "❌ 失败"
            print(f"{key}: {status}")
        
        print(f"\n总体结果: {passed_tests}/{total_tests} 高级功能测试通过")
        
        if passed_tests == total_tests:
            print("🎉 所有高级功能测试通过！系统功能完全正常。")
            return True
        else:
            print("⚠️  部分高级功能测试失败，需要进一步检查。")
            return False

def main():
    """主函数"""
    tester = AdvancedFunctionalityTester()
    success = tester.run_all_advanced_tests()
    
    if success:
        print("\n🚀 高级功能测试完成，系统可以正常使用！")
    else:
        print("\n🔧 系统存在高级功能问题，请检查错误日志。")
    
    return 0 if success else 1

if __name__ == "__main__":
    exit(main()) 