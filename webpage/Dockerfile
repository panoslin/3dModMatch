# 3D鞋模智能匹配系统 - 完整Web应用Dockerfile
FROM python:3.10-slim

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=config.settings.docker
ENV DJANGO_ENVIRONMENT=docker

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# 创建工作目录
WORKDIR /app

# 复制requirements文件
COPY shoe_matcher_web/requirements.txt /app/

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制整个项目
COPY shoe_matcher_web/ /app/
COPY entrypoint.sh /app/

# 创建必要目录
RUN mkdir -p /app/media/{shoes,blanks,heatmaps} \
    /app/static \
    /app/logs \
    /app/results

# 设置权限
RUN chmod +x /app/start_dev.sh /app/test_system.py /app/entrypoint.sh

# 创建非root用户
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/health/ || exit 1

# 设置入口点和默认命令
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["web"]
