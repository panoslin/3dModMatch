#!/usr/bin/env python
"""Django的命令行实用程序，用于管理任务。"""
import os
import sys


def main():
    """运行管理任务。"""
    # 开发环境默认使用development设置
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "无法导入Django。您确定它已安装且"
            "在PYTHONPATH环境变量中可用？您是否"
            "忘记激活虚拟环境？"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
