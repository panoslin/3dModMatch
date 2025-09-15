#!/bin/bash

# 3D鞋模智能匹配系统 - Docker一键启动脚本
# 替代docker-compose，使用纯Docker命令

set -e

# 加载环境变量
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# 设置默认值
DB_NAME=${DB_NAME:-shoe_matcher}
DB_USER=${DB_USER:-postgres}
DB_PASSWORD=${DB_PASSWORD:-postgres123}
WEB_PORT=${WEB_PORT:-8000}
SECRET_KEY=${SECRET_KEY:-django-insecure-change-this}
DEBUG=${DEBUG:-False}
ALLOWED_HOSTS=${ALLOWED_HOSTS:-localhost,127.0.0.1}

echo "🚀 3D鞋模智能匹配系统 - 一键启动"
echo "===================================="
echo "配置信息:"
echo "  数据库: $DB_NAME"
echo "  Web端口: $WEB_PORT"
echo "  调试模式: $DEBUG"
echo "===================================="

# 创建网络
echo "🌐 创建Docker网络..."
docker network create shoe_matcher_network 2>/dev/null || echo "网络已存在"

# 创建数据卷
echo "💾 创建数据卷..."
docker volume create shoe_matcher_postgres_data 2>/dev/null || echo "PostgreSQL卷已存在"
docker volume create shoe_matcher_redis_data 2>/dev/null || echo "Redis卷已存在"

# 构建Hybrid镜像
if ! docker images | grep -q "hybrid-shoe-matcher"; then
    echo "🔨 构建Hybrid匹配器镜像..."
    cd ../hybrid
    docker build -t hybrid-shoe-matcher:latest .
    cd ../webpage
fi

# 构建Web应用镜像
echo "🔨 构建Web应用镜像..."
docker build -t shoe_matcher_web:latest .

# 启动PostgreSQL
echo "🗄️ 启动PostgreSQL..."
docker run -d \
    --name shoe_matcher_db \
    --network shoe_matcher_network \
    -e POSTGRES_DB=$DB_NAME \
    -e POSTGRES_USER=$DB_USER \
    -e POSTGRES_PASSWORD=$DB_PASSWORD \
    -v shoe_matcher_postgres_data:/var/lib/postgresql/data \
    --restart unless-stopped \
    postgres:13

# 启动Redis
echo "🔴 启动Redis..."
docker run -d \
    --name shoe_matcher_redis \
    --network shoe_matcher_network \
    -v shoe_matcher_redis_data:/data \
    --restart unless-stopped \
    redis:7-alpine redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru

# 启动Hybrid匹配服务
echo "🔧 启动Hybrid匹配服务..."
docker run -d \
    --name shoe_matcher_hybrid \
    --network shoe_matcher_network \
    -v $(pwd)/results:/app/output \
    -v $(pwd)/shoe_matcher_web/media:/app/input:ro \
    -v $(pwd)/logs:/app/logs \
    -e LD_LIBRARY_PATH=/usr/local/lib \
    -e LD_PRELOAD=/usr/local/lib/libOpen3D.so \
    -e PYTHONPATH=/app/python \
    -e OMP_NUM_THREADS=4 \
    --restart unless-stopped \
    hybrid-shoe-matcher:latest \
    tail -f /dev/null

# 等待基础服务启动
echo "⏳ 等待基础服务启动..."
sleep 15

# 运行系统初始化
echo "🔧 运行系统初始化..."
docker run --rm \
    --network shoe_matcher_network \
    -v $(pwd)/shoe_matcher_web/media:/app/media \
    -v $(pwd)/shoe_matcher_web/static:/app/static \
    -v $(pwd)/logs:/app/logs \
    -v $(pwd)/../candidates:/app/test_data/candidates:ro \
    -v $(pwd)/../models:/app/test_data/models:ro \
    -e DJANGO_ENVIRONMENT=docker \
    -e SECRET_KEY="$SECRET_KEY" \
    -e DB_HOST=shoe_matcher_db \
    -e DB_NAME=$DB_NAME \
    -e DB_USER=$DB_USER \
    -e DB_PASSWORD=$DB_PASSWORD \
    -e REDIS_URL=redis://shoe_matcher_redis:6379/0 \
    shoe_matcher_web:latest \
    init

# 启动Web服务
echo "🌐 启动Web服务..."
docker run -d \
    --name shoe_matcher_web \
    --network shoe_matcher_network \
    -p $WEB_PORT:8000 \
    -v $(pwd)/shoe_matcher_web/media:/app/media \
    -v $(pwd)/shoe_matcher_web/static:/app/static \
    -v $(pwd)/logs:/app/logs \
    -v $(pwd)/results:/app/results \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -e DJANGO_ENVIRONMENT=docker \
    -e DEBUG=$DEBUG \
    -e SECRET_KEY="$SECRET_KEY" \
    -e ALLOWED_HOSTS=$ALLOWED_HOSTS \
    -e DB_HOST=shoe_matcher_db \
    -e DB_NAME=$DB_NAME \
    -e DB_USER=$DB_USER \
    -e DB_PASSWORD=$DB_PASSWORD \
    -e REDIS_URL=redis://shoe_matcher_redis:6379/0 \
    -e CELERY_BROKER_URL=redis://shoe_matcher_redis:6379/0 \
    -e CELERY_RESULT_BACKEND=redis://shoe_matcher_redis:6379/0 \
    -e MATCHER_DOCKER_IMAGE=hybrid-shoe-matcher:latest \
    --restart unless-stopped \
    shoe_matcher_web:latest \
    web

# 启动Celery Worker
echo "⚡ 启动Celery Worker..."
docker run -d \
    --name shoe_matcher_celery \
    --network shoe_matcher_network \
    -v $(pwd)/shoe_matcher_web/media:/app/media \
    -v $(pwd)/logs:/app/logs \
    -v $(pwd)/results:/app/results \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -e DJANGO_ENVIRONMENT=docker \
    -e DEBUG=$DEBUG \
    -e SECRET_KEY="$SECRET_KEY" \
    -e DB_HOST=shoe_matcher_db \
    -e DB_NAME=$DB_NAME \
    -e DB_USER=$DB_USER \
    -e DB_PASSWORD=$DB_PASSWORD \
    -e REDIS_URL=redis://shoe_matcher_redis:6379/0 \
    -e CELERY_BROKER_URL=redis://shoe_matcher_redis:6379/0 \
    -e CELERY_RESULT_BACKEND=redis://shoe_matcher_redis:6379/0 \
    -e MATCHER_DOCKER_IMAGE=hybrid-shoe-matcher:latest \
    --restart unless-stopped \
    shoe_matcher_web:latest \
    celery

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 25

# 检查服务状态
echo "📊 服务状态:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep shoe_matcher

# 测试API
echo "🧪 测试API健康状态..."
if curl -f http://localhost:$WEB_PORT/api/health/ > /dev/null 2>&1; then
    echo "✅ API健康检查通过"
else
    echo "❌ API健康检查失败"
    exit 1
fi

echo ""
echo "🎉 系统启动完成！"
echo "===================================="
echo "📍 访问地址:"
echo "   主页: http://localhost:$WEB_PORT"
echo "   管理后台: http://localhost:$WEB_PORT/admin"
echo "   用户名: admin"
echo "   密码: admin123"
echo ""
echo "🛑 停止系统:"
echo "   docker stop shoe_matcher_web shoe_matcher_celery shoe_matcher_hybrid shoe_matcher_redis shoe_matcher_db"
echo ""
echo "✨ 系统已就绪！"
