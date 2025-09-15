#!/bin/bash

# 3D鞋模智能匹配系统 - 一键启动脚本

set -e

echo "🚀 3D鞋模智能匹配系统 - 一键启动"
echo "=================================="

# 检查环境变量文件
if [ ! -f ".env" ]; then
    echo "📝 复制环境变量文件..."
    cp env.production .env
    echo "✅ 已创建 .env 文件"
    echo "💡 如需修改配置，请编辑 .env 文件"
fi

# 检查hybrid镜像
if ! docker images | grep -q "hybrid-shoe-matcher"; then
    echo "🔨 构建Hybrid匹配器镜像..."
    cd ../hybrid
    docker build -t hybrid-shoe-matcher:latest .
    cd ../webpage
    echo "✅ Hybrid镜像构建完成"
fi

# 停止现有服务
echo "🛑 停止现有服务..."
docker-compose down 2>/dev/null || true

# 构建并启动所有服务
echo "🔨 构建应用镜像..."
docker-compose build

echo "🚀 启动所有服务..."
docker-compose up -d db redis matcher

# 等待基础服务启动
echo "⏳ 等待基础服务启动..."
sleep 15

# 运行初始化
echo "🔧 运行系统初始化..."
docker-compose run --rm init

# 启动Web和Celery服务
echo "🌐 启动Web和Celery服务..."
docker-compose up -d web celery

# 等待Web服务启动
echo "⏳ 等待Web服务启动..."
sleep 20

# 检查服务状态
echo "📊 检查服务状态..."
docker-compose ps

# 测试API
echo "🧪 测试API健康状态..."
if curl -f http://localhost:8000/api/health/ > /dev/null 2>&1; then
    echo "✅ API健康检查通过"
else
    echo "❌ API健康检查失败"
    echo "📋 Web服务日志:"
    docker-compose logs web | tail -10
    exit 1
fi

echo ""
echo "🎉 系统启动完成！"
echo "=================================="
echo "📍 访问信息:"
echo "   主页: http://localhost:8000"
echo "   管理后台: http://localhost:8000/admin"
echo "   用户名: admin"
echo "   密码: admin123"
echo ""
echo "📊 服务状态:"
docker-compose ps
echo ""
echo "📝 常用命令:"
echo "   查看日志: docker-compose logs -f"
echo "   重启服务: docker-compose restart"
echo "   停止系统: docker-compose down"
echo "   完全清理: docker-compose down -v"
echo ""
echo "✨ 系统已就绪，可以开始使用！"
