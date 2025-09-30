# 3D鞋模智能匹配系统 - Web应用Dockerfile（基于hybrid构建）
FROM ubuntu:22.04

# 设置环境变量
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=config.settings.docker
ENV DJANGO_ENVIRONMENT=docker

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Python runtime
    python3.10 python3.10-dev python3-pip python3-setuptools python3-wheel \
    # Essential runtime libraries
    libeigen3-dev \
    # Database and web server dependencies
    libpq-dev \
    # Network utilities
    curl wget \
    # Docker support
    docker.io \
    # Image processing runtime libraries
    libjpeg-turbo8 libpng16-16 libtiff5 \
    # Compression and network runtime
    libzip4 zlib1g libcurl4 libssl3 libffi8 \
    # Spatial indexing runtime
    libspatialindex6 \
    # TBB library for Open3D
    libtbb12 libtbb-dev \
    # OpenMP library (required for Open3D)
    libgomp1 \
    # OpenGL support
    libgl1-mesa-glx libglu1-mesa libglfw3 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 创建工作目录
WORKDIR /app

# 复制requirements文件并安装Python依赖
COPY shoe_matcher_web/requirements.txt /app/
RUN pip3 install --no-cache-dir -r requirements.txt

# 复制预构建的库文件压缩包并解压
COPY docker-extract.tar.gz /tmp/
RUN cd /tmp && tar -xzf docker-extract.tar.gz \
    && cp docker-extract/libOpen3D.so* /usr/local/lib/ \
    && cp docker-extract/libOpenNURBS.so /usr/local/lib/ \
    && cp docker-extract/libopennurbs* /usr/local/lib/ \
    && cp -r docker-extract/open3d /usr/local/include/ \
    && cp -r docker-extract/OpenNURBS /usr/local/include/ \
    && cp -r docker-extract/opennurbsStatic /usr/local/include/ \
    && rm -rf /tmp/docker-extract.tar.gz /tmp/docker-extract

# 复制编译好的Python扩展模块
COPY cppcore.cpython-310-x86_64-linux-gnu.so /usr/local/lib/python3.10/dist-packages/

# 创建符号链接和更新库路径（参考hybrid方式）
RUN ln -sf /usr/lib/x86_64-linux-gnu/libtbb.so.12 /usr/lib/x86_64-linux-gnu/libtbb.so.12.12 \
    && ln -sf /usr/local/include/OpenNURBS /usr/local/include/opennurbs \
    && echo "/usr/local/lib" >> /etc/ld.so.conf.d/local.conf \
    && ldconfig

# 复制Django项目和必要的Python模块
COPY shoe_matcher_web/ /app/
COPY entrypoint.sh /app/
COPY hybrid_matcher.py /app/

# 创建必要目录
RUN mkdir -p /app/media/{shoes,blanks,heatmaps,temp,converted} \
    /app/static \
    /app/logs \
    /app/results

# 设置权限
RUN chmod +x /app/entrypoint.sh

# 创建非root用户
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app

# 设置环境变量（参考hybrid方式）
ENV LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH
ENV LD_PRELOAD=/usr/local/lib/libOpen3D.so
ENV OMP_NUM_THREADS=1

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/health/ || exit 1

# 设置入口点和默认命令
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["web"]
