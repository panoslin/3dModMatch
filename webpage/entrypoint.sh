#!/bin/bash

# 3D鞋模智能匹配系统 - 容器入口脚本

set -e

echo "🚀 启动3D鞋模智能匹配系统..."

# 检查是否为初始化模式
if [ "$1" = "init" ]; then
    echo "🔧 运行系统初始化..."
    
    # 等待数据库
    python manage.py wait_for_db
    
    # 运行迁移
    python manage.py migrate
    
    # 收集静态文件
    python manage.py collectstatic --noinput
    
    # 创建超级用户和初始数据
    python init_docker.py
    
    # 初始化测试数据（如果存在）
    if [ -d "/app/test_data/candidates" ] && [ -d "/app/test_data/models" ]; then
        echo "📋 初始化测试数据..."
        python manage.py init_test_data
    fi
    
    echo "✅ 系统初始化完成"
    exit 0
fi

# 检查是否为Celery模式
if [ "$1" = "celery" ]; then
    echo "⚡ 启动Celery Worker..."
    exec celery -A config worker -l info --concurrency=${CELERY_CONCURRENCY:-4} --max-tasks-per-child=100
fi

# 检查是否为Web模式
if [ "$1" = "web" ] || [ $# -eq 0 ]; then
    echo "🌐 启动Django Web服务..."
    
    # 等待数据库
    python manage.py wait_for_db
    
    # 检查是否需要初始化（首次启动）
    if ! python manage.py shell -c "from django.contrib.auth.models import User; print(User.objects.filter(username='admin').exists())" 2>/dev/null | grep -q "True"; then
        echo "🔧 首次启动，运行初始化..."
        
        # 运行迁移
        python manage.py migrate
        
        # 收集静态文件
        python manage.py collectstatic --noinput
        
        # 创建超级用户和初始数据
        python init_docker.py
        
        # 初始化测试数据（如果存在）
        if [ -d "/app/test_data/candidates" ] && [ -d "/app/test_data/models" ]; then
            echo "📋 初始化测试数据..."
            python manage.py init_test_data
        fi
        
        echo "✅ 初始化完成"
    else
        echo "✅ 系统已初始化，跳过初始化步骤"
        # 仍然运行迁移以防有新的更改
        python manage.py migrate
    fi
    
    # 启动Web服务器
    if [ "${DEBUG:-False}" = "True" ]; then
        echo "🔧 开发模式启动..."
        exec python manage.py runserver 0.0.0.0:8000
    else
        echo "🚀 生产模式启动..."
        exec gunicorn --bind 0.0.0.0:8000 --workers 4 --worker-class sync --timeout 300 config.wsgi:application
    fi
fi

# 默认执行传入的命令
exec "$@"
