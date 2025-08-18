#!/usr/bin/env python
"""
3D鞋模匹配系统测试脚本
用于验证系统功能是否正常
"""

import os
import sys
import django
from pathlib import Path

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
sys.path.insert(0, str(Path(__file__).parent))
django.setup()

from apps.core.models import ShoeModel, BlankModel, MatchingResult
from apps.file_processing.parsers import ModelFileParser
from apps.matching.algorithms import IntelligentMatcher
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_file_parsing():
    """测试文件解析功能"""
    print("\n=== 测试文件解析 ===")
    
    # 测试文件路径
    test_files = [
        Path(__file__).parent.parent / "models" / "1177-38.3dm",
        Path(__file__).parent.parent / "models" / "1177槽-38.MOD",
        Path(__file__).parent.parent / "models" / "B000大.MOD",
    ]
    
    for file_path in test_files:
        if file_path.exists():
            print(f"\n解析文件: {file_path.name}")
            parser = ModelFileParser(file_path)
            result = parser.parse()
            
            if result.get('success'):
                print(f"  ✅ 解析成功")
                print(f"  - 格式: {result.get('format')}")
                print(f"  - 点数: {result.get('points_count', 0)}")
                print(f"  - 体积: {result.get('volume', 'N/A')}")
            else:
                print(f"  ❌ 解析失败: {result.get('error')}")
        else:
            print(f"  ⚠️ 文件不存在: {file_path.name}")

def test_database():
    """测试数据库连接和模型"""
    print("\n=== 测试数据库 ===")
    
    try:
        # 统计记录数
        shoe_count = ShoeModel.objects.count()
        blank_count = BlankModel.objects.count()
        match_count = MatchingResult.objects.count()
        
        print(f"  ✅ 数据库连接正常")
        print(f"  - 鞋模数量: {shoe_count}")
        print(f"  - 粗胚数量: {blank_count}")
        print(f"  - 匹配结果: {match_count}")
        
        return True
    except Exception as e:
        print(f"  ❌ 数据库错误: {str(e)}")
        return False

def test_matching_algorithm():
    """测试匹配算法"""
    print("\n=== 测试匹配算法 ===")
    
    try:
        # 获取测试数据
        shoes = ShoeModel.objects.filter(is_processed=True)[:1]
        blanks = BlankModel.objects.filter(is_processed=True)
        
        if not shoes.exists() or not blanks.exists():
            print("  ⚠️ 没有足够的测试数据")
            return
        
        shoe = shoes.first()
        print(f"  测试鞋模: {shoe.filename}")
        
        # 执行匹配
        matcher = IntelligentMatcher(margin_distance=2.5)
        results = matcher.find_optimal_match(shoe, list(blanks))
        
        if results:
            best = results[0]
            print(f"  ✅ 匹配成功")
            print(f"  - 最佳粗胚: {best.blank_name}")
            print(f"  - 匹配分数: {best.match_score:.2%}")
            print(f"  - 利用率: {best.volume_efficiency:.2%}")
            print(f"  - 平均余量: {best.avg_margin:.1f}mm")
        else:
            print("  ❌ 匹配失败")
            
    except Exception as e:
        print(f"  ❌ 算法错误: {str(e)}")

def test_web_views():
    """测试Web视图"""
    print("\n=== 测试Web视图 ===")
    
    try:
        from django.test import Client
        client = Client()
        
        # 测试主页
        response = client.get('/')
        if response.status_code == 200:
            print(f"  ✅ 主页访问正常")
        else:
            print(f"  ❌ 主页访问失败: {response.status_code}")
        
        # 测试管理后台
        response = client.get('/admin/')
        if response.status_code in [200, 302]:  # 302是重定向到登录页
            print(f"  ✅ 管理后台访问正常")
        else:
            print(f"  ❌ 管理后台访问失败: {response.status_code}")
            
    except Exception as e:
        print(f"  ❌ 视图测试错误: {str(e)}")

def main():
    """主测试函数"""
    print("=" * 50)
    print("3D鞋模匹配系统功能测试")
    print("=" * 50)
    
    # 运行各项测试
    test_file_parsing()
    
    if test_database():
        test_matching_algorithm()
        test_web_views()
    
    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)

if __name__ == "__main__":
    main()

