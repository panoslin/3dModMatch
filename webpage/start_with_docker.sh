#!/bin/bash

# 使用纯Docker命令启动系统（避免docker-compose版本问题）

set -e

echo "🚀 使用Docker命令启动3D鞋模智能匹配系统"
echo "============================================"

# 创建网络
echo "🌐 创建Docker网络..."
docker network create shoe_matcher_network 2>/dev/null || echo "网络已存在"

# 启动PostgreSQL
echo "🗄️ 启动PostgreSQL数据库..."
docker run -d \
    --name shoe_matcher_db \
    --network shoe_matcher_network \
    -e POSTGRES_DB=shoe_matcher \
    -e POSTGRES_USER=postgres \
    -e POSTGRES_PASSWORD=postgres123 \
    -v shoe_matcher_postgres_data:/var/lib/postgresql/data \
    postgres:13

# 启动Redis
echo "🔴 启动Redis..."
docker run -d \
    --name shoe_matcher_redis \
    --network shoe_matcher_network \
    -v shoe_matcher_redis_data:/data \
    redis:7-alpine

# 等待数据库启动
echo "⏳ 等待数据库启动..."
sleep 15

# 构建Web应用镜像
echo "🔨 构建Web应用镜像..."
docker build -t shoe_matcher_web:latest .

# 运行数据库初始化
echo "🔧 初始化数据库..."
docker run --rm \
    --network shoe_matcher_network \
    -v $(pwd)/shoe_matcher_web/media:/app/media \
    -v $(pwd)/../candidates:/app/test_data/candidates:ro \
    -v $(pwd)/../models:/app/test_data/models:ro \
    -e DJANGO_ENVIRONMENT=docker \
    -e DB_HOST=shoe_matcher_db \
    -e DB_NAME=shoe_matcher \
    -e DB_USER=postgres \
    -e DB_PASSWORD=postgres123 \
    -e REDIS_URL=redis://shoe_matcher_redis:6379/0 \
    shoe_matcher_web:latest \
    bash -c "
        echo '=== 等待数据库 ===' &&
        python manage.py wait_for_db &&
        echo '=== 运行迁移 ===' &&
        python manage.py migrate &&
        echo '=== 创建超级用户 ===' &&
        python manage.py shell -c \"
        from django.contrib.auth.models import User;
        User.objects.filter(username='admin').exists() or 
        User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
        \" &&
        echo '=== 初始化测试数据 ===' &&
        python manage.py init_test_data &&
        echo '=== 初始化完成 ==='
    "

# 启动Web服务
echo "🌐 启动Web服务..."
docker run -d \
    --name shoe_matcher_web \
    --network shoe_matcher_network \
    -p 8000:8000 \
    -v $(pwd)/shoe_matcher_web/media:/app/media \
    -v $(pwd)/shoe_matcher_web/logs:/app/logs \
    -v $(pwd)/results:/app/results \
    -v $(pwd)/../candidates:/app/test_data/candidates:ro \
    -v $(pwd)/../models:/app/test_data/models:ro \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -e DJANGO_ENVIRONMENT=docker \
    -e DB_HOST=shoe_matcher_db \
    -e DB_NAME=shoe_matcher \
    -e DB_USER=postgres \
    -e DB_PASSWORD=postgres123 \
    -e REDIS_URL=redis://shoe_matcher_redis:6379/0 \
    -e CELERY_BROKER_URL=redis://shoe_matcher_redis:6379/0 \
    -e CELERY_RESULT_BACKEND=redis://shoe_matcher_redis:6379/0 \
    -e MATCHER_DOCKER_IMAGE=hybrid-shoe-matcher:latest \
    shoe_matcher_web:latest

# 启动Celery Worker
echo "⚡ 启动Celery Worker..."
docker run -d \
    --name shoe_matcher_celery \
    --network shoe_matcher_network \
    -v $(pwd)/shoe_matcher_web/media:/app/media \
    -v $(pwd)/shoe_matcher_web/logs:/app/logs \
    -v $(pwd)/results:/app/results \
    -v $(pwd)/../candidates:/app/test_data/candidates:ro \
    -v $(pwd)/../models:/app/test_data/models:ro \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -e DJANGO_ENVIRONMENT=docker \
    -e DB_HOST=shoe_matcher_db \
    -e DB_NAME=shoe_matcher \
    -e DB_USER=postgres \
    -e DB_PASSWORD=postgres123 \
    -e REDIS_URL=redis://shoe_matcher_redis:6379/0 \
    -e CELERY_BROKER_URL=redis://shoe_matcher_redis:6379/0 \
    -e CELERY_RESULT_BACKEND=redis://shoe_matcher_redis:6379/0 \
    -e MATCHER_DOCKER_IMAGE=hybrid-shoe-matcher:latest \
    shoe_matcher_web:latest \
    celery -A config worker -l info --concurrency=2

# 等待服务启动
echo "⏳ 等待Web服务启动..."
sleep 20

# 检查服务状态
echo "📊 检查服务状态..."
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# 测试API
echo "🧪 测试API健康状态..."
curl -f http://localhost:8000/api/health/ && echo "✅ API健康检查通过" || echo "❌ API健康检查失败"

echo ""
echo "🎉 系统启动完成！"
echo "============================================"
echo "📍 访问地址:"
echo "   主页: http://localhost:8000"
echo "   管理后台: http://localhost:8000/admin (admin/admin123)"
echo ""
echo "🛑 停止系统:"
echo "   docker stop shoe_matcher_web shoe_matcher_celery shoe_matcher_db shoe_matcher_redis"
echo "   docker rm shoe_matcher_web shoe_matcher_celery shoe_matcher_db shoe_matcher_redis"
echo "   docker network rm shoe_matcher_network"
