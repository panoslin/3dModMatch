#!/bin/bash

# 3D鞋模智能匹配系统 - 开发环境启动脚本

set -e

echo "=== 3D鞋模智能匹配系统 - 开发环境启动 ==="

# 检查虚拟环境
if [ ! -d "../venv" ]; then
    echo "❌ 虚拟环境不存在，请先运行: python3.10 -m venv ../venv"
    exit 1
fi

# 激活虚拟环境
source ../venv/bin/activate

# 检查依赖
echo "📦 检查Python依赖..."
pip install -r requirements.txt

# 检查数据库迁移
echo "🗄️  检查数据库迁移..."
python manage.py makemigrations
python manage.py migrate

# 收集静态文件
echo "📁 收集静态文件..."
python manage.py collectstatic --noinput

# 启动开发服务器
echo "🚀 启动开发服务器..."
echo "访问地址: http://localhost:8000"
echo "管理后台: http://localhost:8000/admin"
echo "API文档: http://localhost:8000/api/health/"
echo ""
echo "按 Ctrl+C 停止服务器"

DJANGO_SETTINGS_MODULE=config.settings.development python manage.py runserver 0.0.0.0:8000
