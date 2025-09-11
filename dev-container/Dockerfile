# Ubuntu 22.04 LTS with China mirrors and C++ development environment
FROM ubuntu:22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Set proxy environment variables (optional)
ARG HTTP_PROXY=${HTTP_PROXY}
ARG HTTPS_PROXY=${HTTPS_PROXY}
ARG NO_PROXY=${NO_PROXY}
ENV HTTP_PROXY=${HTTP_PROXY}
ENV HTTPS_PROXY=${HTTPS_PROXY}
ENV NO_PROXY=${NO_PROXY}

# Configure China mirrors for apt
RUN sed -i 's@//.*archive.ubuntu.com@//mirrors.aliyun.com@g' /etc/apt/sources.list && \
    sed -i 's@//.*security.ubuntu.com@//mirrors.aliyun.com@g' /etc/apt/sources.list

# Update package lists and install basic dependencies
RUN apt-get update && apt-get install -y \
    # Basic system tools
    curl \
    wget \
    git \
    vim \
    nano \
    htop \
    tree \
    unzip \
    # Build essentials
    build-essential \
    cmake \
    pkg-config \
    # C++ development
    gcc-11 \
    g++-11 \
    gdb \
    valgrind \
    # Python for some dependencies
    python3 \
    python3-pip \
    python3-dev \
    # OpenGL and graphics libraries
    libgl1-mesa-dev \
    libglu1-mesa-dev \
    libxrandr-dev \
    libxinerama-dev \
    libxcursor-dev \
    libxi-dev \
    libxext-dev \
    # Math libraries
    libblas-dev \
    liblapack-dev \
    libeigen3-dev \
    # Image processing
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libopenexr-dev \
    # Compression
    libzip-dev \
    zlib1g-dev \
    # Network
    libcurl4-openssl-dev \
    # Other utilities
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Set GCC 11 as default
RUN update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-11 100 && \
    update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-11 100

# Install nlohmann-json (using apt package instead of building from source)
RUN apt-get update && apt-get install -y \
    nlohmann-json3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Open3D via pip (simpler and more reliable)
RUN pip3 install --no-cache-dir open3d==0.17.0

# Note: OpenNURBS installation requires manual download from https://www.rhino3d.com/opennurbs/
# The official download requires visiting the website and accepting terms
# For now, we'll create a placeholder directory structure
RUN mkdir -p /usr/local/include/opennurbs && \
    echo "// OpenNURBS placeholder - download from https://www.rhino3d.com/opennurbs/" > /usr/local/include/opennurbs/opennurbs.h && \
    echo "// and extract to /usr/local/include/opennurbs/" >> /usr/local/include/opennurbs/opennurbs.h

# Install VSCode Server dependencies
RUN apt-get update && apt-get install -y \
    openssh-server \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Configure SSH
RUN mkdir /var/run/sshd && \
    echo 'root:devcontainer' | chpasswd && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    echo 'Port 2222' >> /etc/ssh/sshd_config

# Create development user
RUN useradd -m -s /bin/bash dev && \
    echo 'dev:devcontainer' | chpasswd && \
    usermod -aG sudo dev && \
    echo 'dev ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

# Set up workspace
RUN mkdir -p /workspace && \
    chown -R dev:dev /workspace

# Configure Python with China mirrors
RUN pip3 config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip3 config set global.trusted-host pypi.tuna.tsinghua.edu.cn

# Install additional Python packages that might be needed
RUN pip3 install --no-cache-dir \
    numpy \
    scipy \
    matplotlib \
    jupyter

# Set working directory
WORKDIR /workspace

# Expose SSH port
EXPOSE 2222

# Create startup script
RUN echo '#!/bin/bash\n\
# Start SSH service\n\
service ssh start\n\
\n\
# Keep container running\n\
tail -f /dev/null' > /start.sh && \
    chmod +x /start.sh

# Switch to dev user
USER dev

# Set up git with China mirrors (optional)
RUN git config --global url."https://gitee.com/".insteadOf "https://github.com/" || true

# Create a simple test script
RUN echo '#!/bin/bash\n\
echo "=== C++ Development Environment ==="\n\
echo "GCC version: $(gcc --version | head -n1)"\n\
echo "CMake version: $(cmake --version | head -n1)"\n\
echo "Eigen3 version: $(pkg-config --modversion eigen3)"\n\
echo "nlohmann-json version: $(pkg-config --modversion nlohmann_json)"\n\
echo "Open3D installed: $(python3 -c "import open3d; print(open3d.__version__)" 2>/dev/null || echo "No")"\n\
echo "OpenNURBS: Placeholder created - download from https://www.rhino3d.com/opennurbs/"\n\
echo "=== Environment Ready ==="' > /workspace/test_env.sh && \
    chmod +x /workspace/test_env.sh

CMD ["/start.sh"]