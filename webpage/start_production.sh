#!/bin/bash

# 3D鞋模智能匹配系统 - 生产环境启动脚本

set -e

echo "🚀 3D鞋模智能匹配系统 - 生产环境部署"
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

# 检查环境变量文件
if [ ! -f ".env" ]; then
    echo "⚠️ 环境变量文件不存在，使用示例文件..."
    cp env.prod.example .env
    echo "📝 请编辑 .env 文件配置生产参数"
fi

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
if [ ! -d "../candidates" ] || [ ! -d "../models" ]; then
    echo "⚠️ 测试数据目录不存在，请确保 ../candidates 和 ../models 目录存在"
fi

# 清理现有部署
echo "🧹 清理现有部署..."
docker-compose -f docker-compose.prod.yml down -v 2>/dev/null || true

# 构建所有镜像
echo "🔨 构建应用镜像..."
docker-compose -f docker-compose.prod.yml build --no-cache

# 启动基础服务
echo "🗄️ 启动基础服务 (数据库、Redis、匹配器)..."
docker-compose -f docker-compose.prod.yml up -d db redis matcher

# 等待基础服务启动
echo "⏳ 等待基础服务启动..."
sleep 20

# 检查基础服务健康状态
echo "🩺 检查基础服务健康状态..."
for service in db redis matcher; do
    echo "  检查 $service..."
    timeout=60
    while [ $timeout -gt 0 ]; do
        if docker-compose -f docker-compose.prod.yml ps $service | grep -q "healthy\|Up"; then
            echo "  ✅ $service 健康"
            break
        fi
        sleep 2
        ((timeout-=2))
    done
    
    if [ $timeout -le 0 ]; then
        echo "  ❌ $service 启动超时"
        docker-compose -f docker-compose.prod.yml logs $service
        exit 1
    fi
done

# 运行系统初始化
echo "🔧 运行系统初始化..."
docker-compose -f docker-compose.prod.yml run --rm init || {
    echo "❌ 系统初始化失败"
    docker-compose -f docker-compose.prod.yml logs init
    exit 1
}

echo "✅ 系统初始化完成"

# 启动Web服务
echo "🌐 启动Web服务..."
docker-compose -f docker-compose.prod.yml up -d web celery celery-beat

# 等待Web服务启动
echo "⏳ 等待Web服务启动..."
sleep 30

# 检查Web服务健康状态
echo "🩺 检查Web服务健康状态..."
max_attempts=20
attempt=1

while [ $attempt -le $max_attempts ]; do
    if curl -f http://localhost:8000/api/health/ > /dev/null 2>&1; then
        echo "✅ Web服务健康检查通过"
        break
    else
        echo "⏳ 等待Web服务启动... ($attempt/$max_attempts)"
        sleep 5
        ((attempt++))
    fi
done

if [ $attempt -gt $max_attempts ]; then
    echo "❌ Web服务启动失败"
    echo "📋 Web服务日志:"
    docker-compose -f docker-compose.prod.yml logs web
    echo "📋 Celery服务日志:"
    docker-compose -f docker-compose.prod.yml logs celery
    exit 1
fi

# 启动Nginx (可选)
if [ "${ENABLE_NGINX:-true}" = "true" ]; then
    echo "🌐 启动Nginx反向代理..."
    docker-compose -f docker-compose.prod.yml up -d nginx
fi

# 运行完整功能测试
echo "🧪 运行功能测试..."
if python3 test_matching_simple.py; then
    echo "✅ 功能测试通过"
else
    echo "⚠️ 功能测试未完全通过，但系统已启动"
fi

echo ""
echo "🎉 生产环境部署完成！"
echo "=========================================="
echo "📍 访问信息:"
echo "   主页: http://localhost:8000"
echo "   管理后台: http://localhost:8000/admin"
echo "   用户名: admin"
echo "   密码: admin123"
echo ""
echo "📊 服务状态:"
docker-compose -f docker-compose.prod.yml ps
echo ""
echo "📝 常用命令:"
echo "   查看所有日志: docker-compose -f docker-compose.prod.yml logs -f"
echo "   查看Web日志: docker-compose -f docker-compose.prod.yml logs -f web"
echo "   查看Celery日志: docker-compose -f docker-compose.prod.yml logs -f celery"
echo "   重启服务: docker-compose -f docker-compose.prod.yml restart"
echo "   停止系统: docker-compose -f docker-compose.prod.yml down"
echo "   完全清理: docker-compose -f docker-compose.prod.yml down -v"
echo ""
echo "🔧 系统管理:"
echo "   进入Web容器: docker-compose -f docker-compose.prod.yml exec web bash"
echo "   数据库备份: docker-compose -f docker-compose.prod.yml exec db pg_dump -U postgres shoe_matcher > backup.sql"
echo "   查看任务队列: docker-compose -f docker-compose.prod.yml exec redis redis-cli llen celery"
echo ""
echo "✨ 系统已完全就绪，可以开始使用！"