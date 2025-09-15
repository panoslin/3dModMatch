#!/bin/bash

# 测试全新部署 - 验证从Docker Hub拉取镜像

set -e

echo "🧪 测试全新部署 - 从Docker Hub拉取镜像"
echo "========================================"

# 停止并清理所有现有资源
echo "🧹 清理现有资源..."
/usr/local/bin/docker-compose-v2 down -v 2>/dev/null || true

# 删除本地hybrid镜像来测试从Docker Hub拉取
echo "🗑️ 删除本地hybrid镜像..."
docker rmi hybrid-shoe-matcher:latest 2>/dev/null || true
docker rmi panoslin/shoe_matcher_hybrid:latest 2>/dev/null || true

# 清理Docker缓存
echo "🧹 清理Docker缓存..."
docker system prune -f

echo "✅ 清理完成"

# 现在启动服务 - 应该自动从Docker Hub拉取镜像
echo "🚀 启动服务 (应该从Docker Hub拉取镜像)..."
/usr/local/bin/docker-compose-v2 up -d

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 30

# 检查服务状态
echo "📊 检查服务状态..."
/usr/local/bin/docker-compose-v2 ps

# 验证镜像来源
echo "🔍 验证镜像来源..."
docker images | grep shoe_matcher_hybrid

# 测试API
echo "🧪 测试API..."
if curl -f http://localhost:8000/api/health/ > /dev/null 2>&1; then
    echo "✅ API健康检查通过"
else
    echo "❌ API健康检查失败"
    exit 1
fi

echo ""
echo "🎉 全新部署测试成功！"
echo "✅ 成功从Docker Hub拉取镜像"
echo "✅ 所有服务正常启动"
echo "✅ API正常工作"
