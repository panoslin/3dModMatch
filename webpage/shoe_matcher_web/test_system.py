#!/usr/bin/env python3
"""
系统测试脚本
"""

import os
import sys
import django
import requests
import time

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.core.models import SystemLog
from apps.blanks.models import BlankCategory, BlankModel
from apps.shoes.models import ShoeModel
from apps.matching.models import MatchingTask
from utils.hybrid_integration import hybrid_service


def test_database():
    """测试数据库连接"""
    print("🗄️  测试数据库连接...")
    try:
        # 测试基本查询
        log_count = SystemLog.objects.count()
        blank_count = BlankModel.objects.count()
        shoe_count = ShoeModel.objects.count()
        task_count = MatchingTask.objects.count()
        
        print(f"   ✅ 数据库连接正常")
        print(f"   📊 数据统计: 日志({log_count}) 粗胚({blank_count}) 鞋模({shoe_count}) 任务({task_count})")
        return True
    except Exception as e:
        print(f"   ❌ 数据库连接失败: {e}")
        return False


def test_api_endpoints():
    """测试API端点"""
    print("\n🌐 测试API端点...")
    
    base_url = "http://localhost:8000"
    endpoints = [
        ("/api/health/", "健康检查"),
        ("/api/blanks/", "粗胚列表"),
        ("/api/blanks/categories/", "分类列表"),
        ("/api/matching/history/", "匹配历史"),
    ]
    
    all_passed = True
    for endpoint, name in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            if response.status_code == 200:
                print(f"   ✅ {name}: {response.status_code}")
            else:
                print(f"   ⚠️  {name}: {response.status_code}")
                all_passed = False
        except requests.exceptions.ConnectionError:
            print(f"   ❌ {name}: 连接失败 (服务器未启动?)")
            all_passed = False
        except Exception as e:
            print(f"   ❌ {name}: {e}")
            all_passed = False
    
    return all_passed


def test_hybrid_integration():
    """测试Hybrid系统集成"""
    print("\n🔧 测试Hybrid系统集成...")
    
    try:
        # 检查hybrid系统
        is_available = hybrid_service.check_hybrid_system()
        
        if is_available:
            print("   ✅ Hybrid系统可用")
            print(f"   📦 Docker镜像: {hybrid_service.docker_image}")
            print(f"   📁 Hybrid路径: {hybrid_service.hybrid_path}")
        else:
            print("   ⚠️  Hybrid系统不可用")
            print("   🔨 尝试构建C++模块...")
            
            if hybrid_service.build_cpp_core():
                print("   ✅ C++模块构建成功")
                return True
            else:
                print("   ❌ C++模块构建失败")
                return False
        
        return is_available
        
    except Exception as e:
        print(f"   ❌ Hybrid集成测试失败: {e}")
        return False


def test_file_processing():
    """测试文件处理功能"""
    print("\n📁 测试文件处理功能...")
    
    try:
        # 检查enhanced_3dm_renderer是否可用
        sys.path.insert(0, str(hybrid_service.hybrid_path))
        
        try:
            from utils.enhanced_3dm_renderer import Enhanced3DRenderer
            renderer = Enhanced3DRenderer()
            print("   ✅ 3D渲染器导入成功")
            return True
        except ImportError as e:
            print(f"   ❌ 3D渲染器导入失败: {e}")
            return False
            
    except Exception as e:
        print(f"   ❌ 文件处理测试失败: {e}")
        return False


def test_celery_setup():
    """测试Celery配置"""
    print("\n⚡ 测试Celery配置...")
    
    try:
        from config.celery import app as celery_app
        
        # 检查Celery配置
        broker_url = celery_app.conf.broker_url
        result_backend = celery_app.conf.result_backend
        
        print(f"   📡 Broker URL: {broker_url}")
        print(f"   💾 Result Backend: {result_backend}")
        print("   ✅ Celery配置正常")
        
        # 测试简单任务
        from apps.blanks.tasks import process_blank_file
        print("   ✅ 任务导入成功")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Celery测试失败: {e}")
        return False


def create_sample_data():
    """创建示例数据"""
    print("\n📋 创建示例数据...")
    
    try:
        # 创建示例分类
        category, created = BlankCategory.objects.get_or_create(
            name="女鞋",
            defaults={'description': '女性鞋类粗胚'}
        )
        
        if created:
            print("   ✅ 创建女鞋分类")
        
        subcategory, created = BlankCategory.objects.get_or_create(
            name="尖头高跟",
            parent=category,
            defaults={'description': '尖头高跟鞋粗胚'}
        )
        
        if created:
            print("   ✅ 创建尖头高跟子分类")
        
        print(f"   📊 总分类数: {BlankCategory.objects.count()}")
        return True
        
    except Exception as e:
        print(f"   ❌ 创建示例数据失败: {e}")
        return False


def main():
    """主测试函数"""
    print("🧪 3D鞋模智能匹配系统 - 系统测试")
    print("=" * 50)
    
    tests = [
        ("数据库连接", test_database),
        ("API端点", test_api_endpoints),
        ("Hybrid集成", test_hybrid_integration),
        ("文件处理", test_file_processing),
        ("Celery配置", test_celery_setup),
        ("示例数据", create_sample_data),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                print(f"⚠️  {test_name} 测试未完全通过")
        except Exception as e:
            print(f"❌ {test_name} 测试出错: {e}")
    
    print("\n" + "=" * 50)
    print(f"🎯 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！系统已就绪。")
        print("\n🚀 启动应用:")
        print("   ./start_dev.sh")
        print("\n🌐 访问地址:")
        print("   http://localhost:8000")
    else:
        print("⚠️  部分测试未通过，请检查相关配置。")
    
    return passed == total


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
