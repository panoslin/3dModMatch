#!/bin/bash

# 3D鞋模智能匹配系统 - 容器入口脚本

set -e

echo "🚀 启动3D鞋模智能匹配系统..."

# 检查是否为初始化模式
if [ "$1" = "init" ]; then
    echo "🔧 运行系统初始化..."
    
    # 等待数据库
    python3 manage.py wait_for_db
    
    # 运行迁移
    python3 manage.py migrate
    
    # 收集静态文件
    python3 manage.py collectstatic --noinput
    
    # 创建超级用户和初始数据
    python3 init_docker.py
    
    # 初始化测试数据（如果存在）
    if [ -d "/app/test_data/candidates" ] && [ -d "/app/test_data/models" ]; then
        echo "📋 初始化测试数据..."
        python3 manage.py init_test_data
    fi
    
    echo "✅ 系统初始化完成"
    exit 0
fi

# 检查是否为Celery模式
if [ "$1" = "celery" ]; then
    echo "⚡ 启动Celery Worker (默认队列)..."
    exec celery -A config worker -l info \
        --queues=default \
        --concurrency=${CELERY_CONCURRENCY:-4} \
        --max-tasks-per-child=2 \
        --pool=prefork \
        --hostname=worker_default@%h
fi

# 检查是否为Celery匹配任务专用Worker
if [ "$1" = "celery-matching" ]; then
    echo "🎯 启动Celery Matching Worker (专用队列 - 串行执行)..."
    exec celery -A config worker -l info \
        --queues=matching \
        --concurrency=${CELERY_MATCHING_CONCURRENCY:-1} \
        --max-tasks-per-child=2 \
        --hostname=worker_matching@%h \
        --prefetch-multiplier=1
fi

# 检查是否为Web模式
if [ "$1" = "web" ] || [ $# -eq 0 ]; then
    echo "🌐 启动Django Web服务..."
    
    # 等待数据库
    python3 manage.py wait_for_db
    
    # 检查是否需要初始化（首次启动）
    if ! python3 manage.py shell -c "from django.contrib.auth.models import User; print(User.objects.filter(username='admin').exists())" 2>/dev/null | grep -q "True"; then
        echo "🔧 首次启动，运行初始化..."
        
        # 运行迁移
        python3 manage.py migrate
        
        # 收集静态文件
        python3 manage.py collectstatic --noinput
        
        # 创建超级用户和初始数据
        python3 init_docker.py
        
        # 初始化测试数据（如果存在）
        if [ -d "/app/test_data/candidates" ] && [ -d "/app/test_data/models" ]; then
            echo "📋 初始化测试数据..."
            python3 manage.py init_test_data
        fi
        
        echo "✅ 初始化完成"
    else
        echo "✅ 系统已初始化，跳过初始化步骤"
        # 仍然运行迁移以防有新的更改
        python3 manage.py migrate
    fi
    
    # 启动Web服务器
    # 在Docker环境中使用开发服务器以便提供静态文件
    if [ "${DJANGO_ENVIRONMENT}" = "docker" ] || [ "${DEBUG:-False}" = "True" ]; then
        echo "🔧 开发模式启动 (Django runserver)..."
        exec python3 manage.py runserver 0.0.0.0:8000
    else
        echo "🚀 生产模式启动 (Gunicorn)..."
        exec gunicorn --bind 0.0.0.0:8000 --workers 4 --worker-class sync --timeout 300 config.wsgi:application
    fi
fi

# 默认执行传入的命令
exec "$@"
