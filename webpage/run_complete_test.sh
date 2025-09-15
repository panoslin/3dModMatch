#!/bin/bash

# 3D鞋模智能匹配系统 - 完整系统测试脚本

set -e

echo "🚀 3D鞋模智能匹配系统 - 完整系统测试"
echo "=========================================="

# 检查前置条件
echo "🔍 检查前置条件..."

# 检查Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker未安装"
    exit 1
fi

if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker未运行"
    exit 1
fi

echo "✅ Docker运行正常"

# 检查docker-compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose未安装"
    exit 1
fi

echo "✅ docker-compose可用"

# 检查hybrid镜像
if ! docker images | grep -q "hybrid-shoe-matcher"; then
    echo "🔨 构建Hybrid匹配器镜像..."
    cd ../hybrid
    docker build -t hybrid-shoe-matcher:latest .
    cd ../webpage
else
    echo "✅ Hybrid镜像已存在"
fi

# 检查测试数据
if [ ! -d "../candidates" ] || [ ! -f "../models/34鞋模.3dm" ]; then
    echo "❌ 测试数据不完整"
    echo "   需要: ../candidates/*.3dm 和 ../models/34鞋模.3dm"
    exit 1
fi

echo "✅ 测试数据完整"

# 清理现有容器
echo "🧹 清理现有容器..."
docker-compose down -v 2>/dev/null || true

# 构建Web应用
echo "🔨 构建Web应用镜像..."
docker-compose build --no-cache

# 启动数据库和Redis
echo "🗄️ 启动数据库和Redis..."
docker-compose up -d db redis

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 15

# 检查数据库连接
echo "🔗 检查数据库连接..."
docker-compose exec -T db pg_isready -U postgres || {
    echo "❌ 数据库连接失败"
    docker-compose logs db
    exit 1
}

echo "✅ 数据库连接正常"

# 运行初始化
echo "🔧 运行系统初始化..."
docker-compose run --rm init || {
    echo "❌ 初始化失败"
    docker-compose logs init
    exit 1
}

echo "✅ 系统初始化完成"

# 启动Web服务
echo "🌐 启动Web服务..."
docker-compose up -d web celery

# 等待Web服务启动
echo "⏳ 等待Web服务启动..."
sleep 20

# 检查Web服务健康状态
echo "🩺 检查Web服务健康状态..."
max_attempts=10
attempt=1

while [ $attempt -le $max_attempts ]; do
    if curl -f http://localhost:8000/api/health/ > /dev/null 2>&1; then
        echo "✅ Web服务健康检查通过"
        break
    else
        echo "⏳ 等待Web服务启动... ($attempt/$max_attempts)"
        sleep 10
        ((attempt++))
    fi
done

if [ $attempt -gt $max_attempts ]; then
    echo "❌ Web服务启动失败"
    docker-compose logs web
    exit 1
fi

# 运行API测试
echo "🧪 运行API功能测试..."
python3 test_matching.py || {
    echo "❌ API测试失败"
    echo "📋 查看服务日志:"
    echo "docker-compose logs web"
    echo "docker-compose logs celery"
    exit 1
}

echo ""
echo "🎉 完整系统测试成功！"
echo "=========================================="
echo "📍 系统访问信息:"
echo "   主页: http://localhost:8000"
echo "   管理后台: http://localhost:8000/admin"
echo "   用户名: admin"
echo "   密码: admin123"
echo ""
echo "📊 服务状态:"
docker-compose ps
echo ""
echo "📝 有用的命令:"
echo "   查看Web日志: docker-compose logs -f web"
echo "   查看Celery日志: docker-compose logs -f celery"
echo "   停止系统: docker-compose down"
echo "   重启系统: docker-compose restart"
echo ""
echo "✨ 系统已完全就绪，可以开始使用！"
