#!/usr/bin/env python3
"""
简单匹配测试脚本
"""

import requests
import json
import time

def test_matching():
    """测试匹配功能"""
    print("🔄 测试匹配功能...")
    
    # 1. 获取鞋模列表
    print("  📋 获取鞋模列表...")
    shoes_response = requests.get("http://localhost:8000/api/shoes/")
    if not shoes_response.ok:
        print(f"  ❌ 获取鞋模失败: {shoes_response.status_code}")
        return False
    
    shoes_data = shoes_response.json()
    if not shoes_data.get('success') or not shoes_data.get('data'):
        print("  ❌ 鞋模数据为空")
        return False
    
    shoes = shoes_data['data']
    print(f"  ✅ 找到 {len(shoes)} 个鞋模")
    
    # 选择34鞋模
    target_shoe = None
    for shoe in shoes:
        if '34鞋模' in shoe['name']:
            target_shoe = shoe
            break
    
    if not target_shoe:
        print("  ❌ 未找到34鞋模")
        return False
    
    print(f"  🎯 选择鞋模: {target_shoe['name']} (ID: {target_shoe['id']})")
    
    # 2. 获取分类列表
    print("  🏷️ 获取分类列表...")
    categories_response = requests.get("http://localhost:8000/api/blanks/categories/")
    if not categories_response.ok:
        print(f"  ❌ 获取分类失败: {categories_response.status_code}")
        return False
    
    categories_data = categories_response.json()
    if not categories_data.get('success') or not categories_data.get('data'):
        print("  ❌ 分类数据为空")
        return False
    
    categories = categories_data['data']
    print(f"  ✅ 找到 {len(categories)} 个分类")
    
    # 选择测试分类
    test_category = categories[0]  # 选择第一个分类
    print(f"  🏷️ 选择分类: {test_category['name']} (ID: {test_category['id']})")
    
    # 3. 开始匹配
    print("  🚀 开始匹配...")
    match_data = {
        'shoe_model_id': target_shoe['id'],
        'category_ids': [test_category['id']],
        'clearance': 2.0,
        'threshold': 'p15',
        'enable_scaling': True,
        'enable_multi_start': True,
        'max_scale': 1.03
    }
    
    match_response = requests.post(
        "http://localhost:8000/api/matching/start/",
        json=match_data,
        headers={'Content-Type': 'application/json'}
    )
    
    if not match_response.ok:
        print(f"  ❌ 匹配请求失败: {match_response.status_code}")
        print(f"  响应: {match_response.text}")
        return False
    
    match_result = match_response.json()
    if not match_result.get('success'):
        print(f"  ❌ 匹配启动失败: {match_result.get('message')}")
        return False
    
    task_id = match_result['data']['task_id']
    print(f"  ✅ 匹配任务已启动: {task_id}")
    
    # 4. 监控匹配进度
    print("  ⏳ 监控匹配进度...")
    max_wait = 300  # 最多等待5分钟
    wait_time = 0
    
    while wait_time < max_wait:
        time.sleep(10)
        wait_time += 10
        
        try:
            status_response = requests.get(f"http://localhost:8000/api/matching/{task_id}/status/")
            
            if status_response.ok:
                status_data = status_response.json()
                if status_data.get('success'):
                    task_status = status_data['data']
                    progress = task_status.get('progress', 0)
                    current_step = task_status.get('current_step', '')
                    status = task_status.get('status', '')
                    
                    print(f"    📊 进度: {progress}% - {current_step}")
                    
                    if status == 'completed':
                        print("  ✅ 匹配完成!")
                        break
                    elif status == 'failed':
                        print("  ❌ 匹配失败")
                        return False
                
        except Exception as e:
            print(f"    ⚠️ 状态查询失败: {e}")
    
    if wait_time >= max_wait:
        print("  ⏰ 匹配超时")
        return False
    
    # 5. 获取匹配结果
    print("  📊 获取匹配结果...")
    result_response = requests.get(f"http://localhost:8000/api/matching/{task_id}/result/")
    
    if not result_response.ok:
        print(f"  ❌ 结果获取失败: {result_response.status_code}")
        return False
    
    result_data = result_response.json()
    if not result_data.get('success'):
        print(f"  ❌ 结果数据无效: {result_data.get('message')}")
        return False
    
    results = result_data['data']['results']
    summary = result_data['data']['summary']
    
    print(f"  ✅ 匹配结果获取成功")
    print(f"  📈 总候选数: {summary.get('total_candidates', 0)}")
    print(f"  🎯 P15通过数: {summary.get('passed_p15', 0)}")
    print(f"  ⏱️ 处理时间: {summary.get('processing_time', 0):.1f}秒")
    
    if results:
        best = results[0]
        print(f"  🏆 最佳匹配: {best.get('blank_name', 'N/A')}")
        print(f"  📊 覆盖率: {best.get('inside_ratio', 0)*100:.1f}%")
        print(f"  📐 P15间隙: {best.get('p15_clearance', 0):.2f}mm")
        print(f"  📏 体积比: {best.get('volume_ratio', 0):.2f}x")
    
    return True

if __name__ == '__main__':
    print("🧪 3D鞋模智能匹配系统 - 匹配功能测试")
    print("=" * 50)
    
    if test_matching():
        print("\n🎉 匹配测试成功！")
        print("✨ 系统完全正常，所有API都正常工作！")
    else:
        print("\n❌ 匹配测试失败")
        print("📋 请检查容器日志:")
        print("   docker logs shoe_matcher_web")
        print("   docker logs shoe_matcher_celery")
