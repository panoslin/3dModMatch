#!/bin/bash

# 3D鞋模智能匹配系统 - 完整系统启动脚本

set -e

echo "🚀 3D鞋模智能匹配系统 - 完整系统启动"
echo "=" * 60

# 检查Docker是否运行
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker未运行，请先启动Docker"
    exit 1
fi

# 检查hybrid镜像是否存在
if ! docker images | grep -q "hybrid-shoe-matcher"; then
    echo "🔨 构建Hybrid匹配器镜像..."
    cd ../hybrid
    docker build -t hybrid-shoe-matcher:latest .
    cd ../webpage
else
    echo "✅ Hybrid镜像已存在"
fi

# 停止现有容器
echo "🛑 停止现有容器..."
docker-compose down -v 2>/dev/null || true

# 构建Web应用镜像
echo "🔨 构建Web应用镜像..."
docker-compose build

# 启动所有服务
echo "🚀 启动所有服务..."
docker-compose up -d db redis

# 等待数据库启动
echo "⏳ 等待数据库启动..."
sleep 10

# 运行初始化服务
echo "🔧 运行数据库初始化..."
docker-compose run --rm init

# 启动Web服务和Celery
echo "🌐 启动Web服务..."
docker-compose up -d web celery

# 等待Web服务启动
echo "⏳ 等待Web服务启动..."
sleep 15

# 初始化测试数据
echo "📋 初始化测试数据..."
docker-compose exec web python manage.py init_test_data

# 检查服务状态
echo "🧪 检查服务状态..."
docker-compose ps

# 测试API健康状态
echo "🌐 测试API健康状态..."
sleep 5
curl -f http://localhost:8000/api/health/ || echo "⚠️ API健康检查失败"

# 测试API端点
echo "🧪 测试主要API端点..."
echo "  测试粗胚列表API..."
curl -s http://localhost:8000/api/blanks/ | jq '.success' || echo "⚠️ 粗胚API失败"

echo "  测试分类列表API..."
curl -s http://localhost:8000/api/blanks/categories/ | jq '.success' || echo "⚠️ 分类API失败"

echo "  测试鞋模列表API..."
curl -s http://localhost:8000/api/shoes/ | jq '.success' || echo "⚠️ 鞋模API失败"

echo ""
echo "🎉 系统启动完成！"
echo "=" * 60
echo "📍 访问地址:"
echo "   主页: http://localhost:8000"
echo "   管理后台: http://localhost:8000/admin (admin/admin123)"
echo "   API健康检查: http://localhost:8000/api/health/"
echo ""
echo "📊 服务状态:"
docker-compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
echo ""
echo "📝 查看日志:"
echo "   docker-compose logs -f web"
echo "   docker-compose logs -f celery"
echo ""
echo "🛑 停止系统:"
echo "   docker-compose down"
