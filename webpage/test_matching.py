#!/usr/bin/env python3
"""
匹配功能测试脚本
"""

import requests
import json
import time
import sys
from pathlib import Path


def test_api_health():
    """测试API健康状态"""
    print("🩺 测试API健康状态...")
    try:
        response = requests.get("http://localhost:8000/api/health/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print("   ✅ API健康检查通过")
                return True
        print(f"   ❌ API健康检查失败: {response.status_code}")
        return False
    except Exception as e:
        print(f"   ❌ API连接失败: {e}")
        return False


def test_categories_api():
    """测试分类API"""
    print("🏷️ 测试分类API...")
    try:
        response = requests.get("http://localhost:8000/api/blanks/categories/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('success') and data.get('data'):
                categories = data['data']
                print(f"   ✅ 分类API正常，找到 {len(categories)} 个分类")
                return categories
        print(f"   ❌ 分类API失败: {response.status_code}")
        return []
    except Exception as e:
        print(f"   ❌ 分类API连接失败: {e}")
        return []


def test_blanks_api():
    """测试粗胚API"""
    print("🗃️ 测试粗胚API...")
    try:
        response = requests.get("http://localhost:8000/api/blanks/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                blanks = data.get('data', [])
                print(f"   ✅ 粗胚API正常，找到 {len(blanks)} 个粗胚")
                return blanks
        print(f"   ❌ 粗胚API失败: {response.status_code}")
        return []
    except Exception as e:
        print(f"   ❌ 粗胚API连接失败: {e}")
        return []


def test_shoes_api():
    """测试鞋模API"""
    print("👠 测试鞋模API...")
    try:
        response = requests.get("http://localhost:8000/api/shoes/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                shoes = data.get('data', [])
                print(f"   ✅ 鞋模API正常，找到 {len(shoes)} 个鞋模")
                return shoes
        print(f"   ❌ 鞋模API失败: {response.status_code}")
        return []
    except Exception as e:
        print(f"   ❌ 鞋模API连接失败: {e}")
        return []


def test_matching_workflow(categories, shoes):
    """测试完整匹配流程"""
    print("🔄 测试匹配流程...")
    
    if not categories:
        print("   ❌ 没有可用分类，无法测试匹配")
        return False
    
    if not shoes:
        print("   ❌ 没有可用鞋模，无法测试匹配")
        return False
    
    try:
        # 选择第一个鞋模和第一个分类
        shoe = shoes[0]
        category = categories[0]
        
        print(f"   🎯 使用鞋模: {shoe['name']}")
        print(f"   🏷️ 使用分类: {category['name']}")
        
        # 开始匹配
        match_data = {
            'shoe_model_id': shoe['id'],
            'category_ids': [category['id']],
            'clearance': 2.0,
            'threshold': 'p15',
            'enable_scaling': True,
            'enable_multi_start': True,
            'max_scale': 1.03
        }
        
        print("   📤 发起匹配请求...")
        response = requests.post(
            "http://localhost:8000/api/matching/start/",
            json=match_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        if response.status_code != 201:
            print(f"   ❌ 匹配请求失败: {response.status_code}")
            print(f"   响应: {response.text}")
            return False
        
        result = response.json()
        if not result.get('success'):
            print(f"   ❌ 匹配启动失败: {result.get('message')}")
            return False
        
        task_id = result['data']['task_id']
        print(f"   ✅ 匹配任务已启动: {task_id}")
        
        # 监控匹配进度
        print("   ⏳ 监控匹配进度...")
        max_wait = 300  # 最多等待5分钟
        wait_time = 0
        
        while wait_time < max_wait:
            time.sleep(5)
            wait_time += 5
            
            try:
                status_response = requests.get(
                    f"http://localhost:8000/api/matching/{task_id}/status/",
                    timeout=10
                )
                
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    if status_data.get('success'):
                        task_status = status_data['data']
                        progress = task_status.get('progress', 0)
                        current_step = task_status.get('current_step', '')
                        status = task_status.get('status', '')
                        
                        print(f"   📊 进度: {progress}% - {current_step}")
                        
                        if status == 'completed':
                            print("   ✅ 匹配完成!")
                            break
                        elif status == 'failed':
                            print("   ❌ 匹配失败")
                            return False
                    
            except Exception as e:
                print(f"   ⚠️ 状态查询失败: {e}")
        
        if wait_time >= max_wait:
            print("   ⏰ 匹配超时")
            return False
        
        # 获取匹配结果
        print("   📊 获取匹配结果...")
        try:
            result_response = requests.get(
                f"http://localhost:8000/api/matching/{task_id}/result/",
                timeout=10
            )
            
            if result_response.status_code == 200:
                result_data = result_response.json()
                if result_data.get('success'):
                    results = result_data['data']['results']
                    summary = result_data['data']['summary']
                    
                    print(f"   ✅ 匹配结果获取成功")
                    print(f"   📈 总候选数: {summary.get('total_candidates', 0)}")
                    print(f"   🎯 P15通过数: {summary.get('passed_p15', 0)}")
                    
                    if results:
                        best = results[0]
                        print(f"   🏆 最佳匹配: {best.get('blank_name', 'N/A')}")
                        print(f"   📊 覆盖率: {best.get('inside_ratio', 0)*100:.1f}%")
                        print(f"   📐 P15间隙: {best.get('p15_clearance', 0):.2f}mm")
                    
                    return True
            
            print(f"   ❌ 结果获取失败: {result_response.status_code}")
            return False
            
        except Exception as e:
            print(f"   ❌ 结果获取出错: {e}")
            return False
        
    except Exception as e:
        print(f"   ❌ 匹配流程出错: {e}")
        return False


def main():
    """主测试函数"""
    print("🧪 3D鞋模智能匹配系统 - 完整功能测试")
    print("=" * 60)
    
    tests = [
        ("API健康检查", test_api_health),
        ("分类API", test_categories_api),
        ("粗胚API", test_blanks_api),
        ("鞋模API", test_shoes_api),
    ]
    
    # 运行基础测试
    categories = []
    shoes = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            if test_name == "分类API":
                categories = result or []
            elif test_name == "鞋模API":
                shoes = result or []
            elif not result:
                print(f"⚠️ {test_name} 测试失败")
        except Exception as e:
            print(f"❌ {test_name} 测试出错: {e}")
    
    # 测试匹配流程
    if categories and shoes:
        print("\n🔄 开始测试匹配流程...")
        if test_matching_workflow(categories, shoes):
            print("\n🎉 所有测试通过！系统完全正常！")
            return True
        else:
            print("\n⚠️ 匹配流程测试失败")
            return False
    else:
        print("\n⚠️ 缺少测试数据，无法测试匹配流程")
        return False


if __name__ == '__main__':
    success = main()
    if success:
        print("\n✨ 系统已完全就绪，可以开始使用！")
        print("🌐 访问: http://localhost:8000")
    else:
        print("\n❌ 测试未完全通过，请检查系统配置")
    
    sys.exit(0 if success else 1)
