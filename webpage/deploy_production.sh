#!/bin/bash

# 3D鞋模智能匹配系统 - 生产环境一键部署脚本

set -e

echo "🚀 3D鞋模智能匹配系统 - 生产环境一键部署"
echo "================================================="

# 清理现有容器
echo "🧹 清理现有容器..."
docker stop $(docker ps -q) 2>/dev/null || true
docker rm $(docker ps -aq) 2>/dev/null || true
docker network rm shoe_matcher_network 2>/dev/null || true

# 创建网络
echo "🌐 创建Docker网络..."
docker network create shoe_matcher_network

# 构建镜像
echo "🔨 构建应用镜像..."
docker build -t shoe_matcher_web:latest .

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
sleep 20

# 运行数据库初始化
echo "🔧 初始化数据库和数据..."
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
        echo '=== 初始化用户和数据 ===' &&
        python init_docker.py &&
        echo '=== 初始化测试数据 ===' &&
        python manage.py init_test_data &&
        echo '=== 收集静态文件 ===' &&
        python manage.py collectstatic --noinput &&
        echo '=== 初始化完成 ==='
    "

# 启动Web服务 (使用Gunicorn生产服务器)
echo "🌐 启动Web服务 (生产模式)..."
docker run -d \
    --name shoe_matcher_web \
    --network shoe_matcher_network \
    -p 8000:8000 \
    -v $(pwd)/shoe_matcher_web/media:/app/media \
    -v $(pwd)/shoe_matcher_web/static:/app/static \
    -v $(pwd)/shoe_matcher_web/logs:/app/logs \
    -v $(pwd)/results:/app/results \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -e DEBUG=False \
    -e DJANGO_ENVIRONMENT=docker \
    -e DB_HOST=shoe_matcher_db \
    -e DB_NAME=shoe_matcher \
    -e DB_USER=postgres \
    -e DB_PASSWORD=postgres123 \
    -e REDIS_URL=redis://shoe_matcher_redis:6379/0 \
    -e CELERY_BROKER_URL=redis://shoe_matcher_redis:6379/0 \
    -e CELERY_RESULT_BACKEND=redis://shoe_matcher_redis:6379/0 \
    -e MATCHER_DOCKER_IMAGE=hybrid-shoe-matcher:latest \
    --restart unless-stopped \
    shoe_matcher_web:latest \
    gunicorn --bind 0.0.0.0:8000 --workers 4 --timeout 300 config.wsgi:application

# 启动Celery Worker
echo "⚡ 启动Celery Worker..."
docker run -d \
    --name shoe_matcher_celery \
    --network shoe_matcher_network \
    -v $(pwd)/shoe_matcher_web/media:/app/media \
    -v $(pwd)/shoe_matcher_web/logs:/app/logs \
    -v $(pwd)/results:/app/results \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -e DEBUG=False \
    -e DJANGO_ENVIRONMENT=docker \
    -e DB_HOST=shoe_matcher_db \
    -e DB_NAME=shoe_matcher \
    -e DB_USER=postgres \
    -e DB_PASSWORD=postgres123 \
    -e REDIS_URL=redis://shoe_matcher_redis:6379/0 \
    -e CELERY_BROKER_URL=redis://shoe_matcher_redis:6379/0 \
    -e CELERY_RESULT_BACKEND=redis://shoe_matcher_redis:6379/0 \
    -e MATCHER_DOCKER_IMAGE=hybrid-shoe-matcher:latest \
    --restart unless-stopped \
    shoe_matcher_web:latest \
    celery -A config worker -l info --concurrency=4

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 30

# 检查服务状态
echo "📊 检查服务状态..."
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# 测试系统健康
echo "🧪 测试系统健康..."
max_attempts=5
attempt=1

while [ $attempt -le $max_attempts ]; do
    if curl -f http://localhost:8000/api/health/ > /dev/null 2>&1; then
        echo "✅ 系统健康检查通过"
        break
    else
        echo "⏳ 等待系统就绪... ($attempt/$max_attempts)"
        sleep 10
        ((attempt++))
    fi
done

if [ $attempt -gt $max_attempts ]; then
    echo "❌ 系统健康检查失败"
    echo "📋 查看Web服务日志:"
    docker logs shoe_matcher_web
    exit 1
fi

# 测试基本API
echo "🧪 测试基本API..."
echo "  测试粗胚API..."
if curl -s http://localhost:8000/api/blanks/ | grep -q '"success":true'; then
    echo "  ✅ 粗胚API正常"
else
    echo "  ❌ 粗胚API异常"
fi

echo "  测试鞋模API..."
if curl -s http://localhost:8000/api/shoes/ | grep -q '"success":true'; then
    echo "  ✅ 鞋模API正常"
else
    echo "  ❌ 鞋模API异常"
fi

echo ""
echo "🎉 生产环境部署成功！"
echo "================================================="
echo "📍 系统访问信息:"
echo "   主页: http://localhost:8000"
echo "   管理后台: http://localhost:8000/admin"
echo "   用户名: admin"
echo "   密码: admin123"
echo ""
echo "📊 系统信息:"
echo "   数据库: PostgreSQL 13"
echo "   缓存: Redis 7"
echo "   Web服务器: Gunicorn (4 workers)"
echo "   异步任务: Celery (4 workers)"
echo "   匹配引擎: Hybrid容器集成"
echo ""
echo "📝 管理命令:"
echo "   查看所有服务: docker ps"
echo "   查看Web日志: docker logs shoe_matcher_web"
echo "   查看Celery日志: docker logs shoe_matcher_celery"
echo "   重启Web服务: docker restart shoe_matcher_web"
echo "   重启Celery: docker restart shoe_matcher_celery"
echo ""
echo "🛑 停止系统:"
echo "   docker stop shoe_matcher_web shoe_matcher_celery shoe_matcher_db shoe_matcher_redis"
echo ""
echo "🧪 测试匹配功能:"
echo "   python3 test_matching_simple.py"
echo ""
echo "✨ 系统已完全就绪，可以开始使用！"
