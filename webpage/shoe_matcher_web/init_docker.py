#!/usr/bin/env python3
"""
Docker环境初始化脚本
"""

import os
import django

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.docker')
django.setup()

from django.contrib.auth.models import User
from apps.blanks.models import BlankCategory


def create_superuser():
    """创建超级用户"""
    print("创建超级用户...")
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
        print("✅ 超级用户创建成功: admin/admin123")
    else:
        print("✅ 超级用户已存在")


def create_test_categories():
    """创建测试分类"""
    print("创建测试分类...")
    
    # 主分类
    main_category, created = BlankCategory.objects.get_or_create(
        name='测试粗胚',
        defaults={
            'description': '用于测试的粗胚分类',
            'sort_order': 1
        }
    )
    
    if created:
        print(f"✅ 创建主分类: {main_category.name}")
    else:
        print(f"✅ 主分类已存在: {main_category.name}")


def main():
    """主函数"""
    print("=== Docker环境初始化 ===")
    
    try:
        create_superuser()
        create_test_categories()
        print("=== 初始化完成 ===")
        return True
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        return False


if __name__ == '__main__':
    import sys
    success = main()
    sys.exit(0 if success else 1)
