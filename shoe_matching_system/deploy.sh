#!/bin/bash
# 3D鞋模智能匹配系统部署脚本

set -e

echo "🚀 开始部署3D鞋模智能匹配系统..."

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ Docker未安装，请先安装Docker"
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo "❌ Docker Compose未安装，请先安装Docker Compose"
    exit 1
fi

# 创建环境文件
if [ ! -f .env ]; then
    echo "📝 创建环境配置文件..."
    cp config.env.example .env
    echo "⚠️  请编辑 .env 文件，修改数据库密码等配置"
    echo "   然后重新运行此脚本"
    exit 0
fi

# 创建必要目录
echo "📁 创建必要目录..."
mkdir -p logs
mkdir -p media/shoes
mkdir -p media/blanks
mkdir -p media/analysis
mkdir -p staticfiles
mkdir -p cache

# 设置目录权限
chmod 755 media
chmod 755 logs
chmod 755 staticfiles

echo "🏗️  构建Docker镜像..."
docker compose build

echo "🚀 启动服务..."
docker compose up -d

# 等待数据库启动
echo "⏳ 等待数据库启动..."
sleep 30

# 检查数据库连接
echo "🔍 检查数据库连接..."
docker compose exec -T db mysql -u root -p$(grep MYSQL_ROOT_PASSWORD .env | cut -d '=' -f2) -e "SELECT 1" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ 数据库连接正常"
else
    echo "❌ 数据库连接失败，请检查配置"
    exit 1
fi

# 运行数据库迁移
echo "🗄️  运行数据库迁移..."
docker compose exec -T web python manage.py migrate --noinput

# 收集静态文件
echo "📦 收集静态文件..."
docker compose exec -T web python manage.py collectstatic --noinput

# 检查服务状态
echo "🔍 检查服务状态..."
sleep 10
docker compose ps

# 测试Web服务
echo "🧪 测试Web服务..."
if curl -f http://localhost:8000/health/ > /dev/null 2>&1; then
    echo "✅ Web服务正常运行"
else
    echo "⚠️  Web服务可能未完全启动，请稍等..."
fi

echo ""
echo "🎉 部署完成！"
echo ""
echo "📋 访问信息："
echo "   主页地址: http://localhost"
echo "   管理后台: http://localhost/admin/"
echo ""
echo "⚙️  管理命令："
echo "   查看日志: docker compose logs -f"
echo "   重启服务: docker compose restart"
echo "   停止服务: docker compose down"
echo ""
echo "🔐 创建管理员账号："
echo "   docker compose exec web python manage.py createsuperuser"
echo ""
echo "📝 下一步："
echo "   1. 创建管理员账号（见上方命令）"
echo "   2. 访问管理后台配置系统"
echo "   3. 上传测试文件验证功能"
echo ""
echo "✨ 祝您使用愉快！"
