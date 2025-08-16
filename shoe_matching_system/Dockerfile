# Django 3D鞋模匹配系统 Dockerfile
FROM python:3.11-slim

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    default-mysql-client \
    default-libmysqlclient-dev \
    build-essential \
    pkg-config \
    python3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制并安装Python依赖
COPY requirements.txt .
# 使用国内PyPI镜像源
RUN pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple/ && \
    pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/

# 创建应用用户
RUN addgroup --system appgroup && \
    adduser --system --group appuser

# 复制项目文件
COPY . .

# 创建媒体和静态文件目录
RUN mkdir -p media/shoes media/blanks media/analysis \
    && mkdir -p staticfiles \
    && chown -R appuser:appgroup /app

# 切换到应用用户
USER appuser

# 收集静态文件
RUN python manage.py collectstatic --noinput --settings=config.settings.production || true

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "config.wsgi:application"]
