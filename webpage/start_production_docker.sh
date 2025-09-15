#!/bin/bash

# 3D鞋模智能匹配系统 - 生产环境Docker启动脚本

set -e

echo "🚀 3D鞋模智能匹配系统 - 生产环境部署"
echo "============================================"

# 检查前置条件
echo "🔍 检查前置条件..."

if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker未运行"
    exit 1
fi

echo "✅ Docker运行正常"

# 检查hybrid镜像
if ! docker images | grep -q "hybrid-shoe-matcher"; then
    echo "🔨 构建Hybrid匹配器镜像..."
    cd ../hybrid
    docker build -t hybrid-shoe-matcher:latest .
    cd ../webpage
else
    echo "✅ Hybrid镜像已存在"
fi

# 创建网络
echo "🌐 创建Docker网络..."
docker network create shoe_matcher_prod_network 2>/dev/null || echo "网络已存在"

# 清理现有容器
echo "🧹 清理现有容器..."
docker stop shoe_matcher_db_prod shoe_matcher_redis_prod shoe_matcher_web_prod shoe_matcher_celery_prod shoe_matcher_hybrid_prod 2>/dev/null || true
docker rm shoe_matcher_db_prod shoe_matcher_redis_prod shoe_matcher_web_prod shoe_matcher_celery_prod shoe_matcher_hybrid_prod 2>/dev/null || true

# 启动PostgreSQL
echo "🗄️ 启动PostgreSQL数据库..."
docker run -d \
    --name shoe_matcher_db_prod \
    --network shoe_matcher_prod_network \
    -e POSTGRES_DB=shoe_matcher \
    -e POSTGRES_USER=postgres \
    -e POSTGRES_PASSWORD=postgres123 \
    -v shoe_matcher_postgres_prod:/var/lib/postgresql/data \
    postgres:13

# 启动Redis
echo "🔴 启动Redis..."
docker run -d \
    --name shoe_matcher_redis_prod \
    --network shoe_matcher_prod_network \
    -v shoe_matcher_redis_prod:/data \
    redis:7-alpine redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru

# 启动Hybrid匹配服务
echo "🔧 启动Hybrid匹配服务..."
docker run -d \
    --name shoe_matcher_hybrid_prod \
    --network shoe_matcher_prod_network \
    -v $(pwd)/results:/app/output \
    -v $(pwd)/shoe_matcher_web/media:/app/input:ro \
    -v $(pwd)/shoe_matcher_web/logs:/app/logs \
    -e LD_LIBRARY_PATH=/usr/local/lib \
    -e LD_PRELOAD=/usr/local/lib/libOpen3D.so \
    -e PYTHONPATH=/app/python \
    -e OMP_NUM_THREADS=4 \
    --restart unless-stopped \
    hybrid-shoe-matcher:latest \
    tail -f /dev/null  # 保持容器运行

# 等待基础服务启动
echo "⏳ 等待基础服务启动..."
sleep 20

# 构建Web应用镜像
echo "🔨 构建Web应用镜像..."
docker build -t shoe_matcher_web_prod:latest .

# 运行数据库初始化
echo "🔧 初始化数据库..."
docker run --rm \
    --network shoe_matcher_prod_network \
    -v $(pwd)/shoe_matcher_web/media:/app/media \
    -v $(pwd)/shoe_matcher_web/static:/app/static \
    -v $(pwd)/../candidates:/app/test_data/candidates:ro \
    -v $(pwd)/../models:/app/test_data/models:ro \
    -e DJANGO_ENVIRONMENT=docker \
    -e DB_HOST=shoe_matcher_db_prod \
    -e DB_NAME=shoe_matcher \
    -e DB_USER=postgres \
    -e DB_PASSWORD=postgres123 \
    -e REDIS_URL=redis://shoe_matcher_redis_prod:6379/0 \
    shoe_matcher_web_prod:latest \
    bash -c "
        python manage.py wait_for_db &&
        python manage.py migrate &&
        python manage.py collectstatic --noinput &&
        python init_docker.py &&
        python manage.py init_test_data
    "

echo "✅ 数据库初始化完成"

# 启动Web服务
echo "🌐 启动Web服务..."
docker run -d \
    --name shoe_matcher_web_prod \
    --network shoe_matcher_prod_network \
    -p 8000:8000 \
    -v $(pwd)/shoe_matcher_web/media:/app/media \
    -v $(pwd)/shoe_matcher_web/static:/app/static \
    -v $(pwd)/shoe_matcher_web/logs:/app/logs \
    -v $(pwd)/results:/app/results \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -e DJANGO_ENVIRONMENT=docker \
    -e DB_HOST=shoe_matcher_db_prod \
    -e DB_NAME=shoe_matcher \
    -e DB_USER=postgres \
    -e DB_PASSWORD=postgres123 \
    -e REDIS_URL=redis://shoe_matcher_redis_prod:6379/0 \
    -e CELERY_BROKER_URL=redis://shoe_matcher_redis_prod:6379/0 \
    -e CELERY_RESULT_BACKEND=redis://shoe_matcher_redis_prod:6379/0 \
    -e MATCHER_DOCKER_IMAGE=hybrid-shoe-matcher:latest \
    --restart unless-stopped \
    shoe_matcher_web_prod:latest

# 启动Celery Worker
echo "⚡ 启动Celery Worker..."
docker run -d \
    --name shoe_matcher_celery_prod \
    --network shoe_matcher_prod_network \
    -v $(pwd)/shoe_matcher_web/media:/app/media \
    -v $(pwd)/shoe_matcher_web/logs:/app/logs \
    -v $(pwd)/results:/app/results \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -e DJANGO_ENVIRONMENT=docker \
    -e DB_HOST=shoe_matcher_db_prod \
    -e DB_NAME=shoe_matcher \
    -e DB_USER=postgres \
    -e DB_PASSWORD=postgres123 \
    -e REDIS_URL=redis://shoe_matcher_redis_prod:6379/0 \
    -e CELERY_BROKER_URL=redis://shoe_matcher_redis_prod:6379/0 \
    -e CELERY_RESULT_BACKEND=redis://shoe_matcher_redis_prod:6379/0 \
    -e MATCHER_DOCKER_IMAGE=hybrid-shoe-matcher:latest \
    --restart unless-stopped \
    shoe_matcher_web_prod:latest \
    celery -A config worker -l info --concurrency=4 --max-tasks-per-child=100

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 30

# 检查服务状态
echo "📊 检查服务状态..."
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep shoe_matcher

# 测试API健康状态
echo "🩺 测试API健康状态..."
max_attempts=10
attempt=1

while [ $attempt -le $max_attempts ]; do
    if curl -f http://localhost:8000/api/health/ > /dev/null 2>&1; then
        echo "✅ API健康检查通过"
        break
    else
        echo "⏳ 等待API启动... ($attempt/$max_attempts)"
        sleep 5
        ((attempt++))
    fi
done

if [ $attempt -gt $max_attempts ]; then
    echo "❌ API启动失败"
    echo "📋 Web服务日志:"
    docker logs shoe_matcher_web_prod | tail -20
    exit 1
fi

# 运行完整功能测试
echo "🧪 运行完整功能测试..."
if python3 test_matching_simple.py; then
    echo "✅ 所有功能测试通过"
    test_result="成功"
else
    echo "⚠️ 部分功能测试未通过"
    test_result="部分成功"
fi

echo ""
echo "🎉 生产环境部署完成！"
echo "============================================"
echo "📍 系统访问信息:"
echo "   主页: http://localhost:8000"
echo "   管理后台: http://localhost:8000/admin"
echo "   用户名: admin"
echo "   密码: admin123"
echo ""
echo "📊 服务状态:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep shoe_matcher
echo ""
echo "🧪 功能测试结果: $test_result"
echo ""
echo "📝 系统管理命令:"
echo "   查看Web日志: docker logs -f shoe_matcher_web_prod"
echo "   查看Celery日志: docker logs -f shoe_matcher_celery_prod"
echo "   查看匹配器日志: docker logs -f shoe_matcher_hybrid_prod"
echo "   重启Web服务: docker restart shoe_matcher_web_prod"
echo "   重启Celery: docker restart shoe_matcher_celery_prod"
echo ""
echo "🛑 停止系统:"
echo "   docker stop shoe_matcher_web_prod shoe_matcher_celery_prod shoe_matcher_hybrid_prod shoe_matcher_db_prod shoe_matcher_redis_prod"
echo ""
echo "🗑️ 完全清理:"
echo "   docker rm shoe_matcher_web_prod shoe_matcher_celery_prod shoe_matcher_hybrid_prod shoe_matcher_db_prod shoe_matcher_redis_prod"
echo "   docker volume rm shoe_matcher_postgres_prod shoe_matcher_redis_prod"
echo "   docker network rm shoe_matcher_prod_network"
echo ""
echo "✨ 系统已完全就绪，可以开始使用！"
