# Ubuntu 22.04 LTS with Open3D 0.18 and Shoe Last Matcher development environment
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
    sed -i 's@//.*security.ubuntu.com@//mirrors.aliyun.com@g' /etc/apt/sources.list && \
    sed -i 's@//ports.ubuntu.com@//mirrors.aliyun.com@g' /etc/apt/sources.list

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
    sudo \
    # Build essentials
    build-essential \
    cmake \
    ninja-build \
    pkg-config \
    # C++ development
    gcc-11 \
    g++-11 \
    clang-12 \
    gdb \
    valgrind \
    # Python 3.10 and development
    python3.10 \
    python3.10-dev \
    python3-pip \
    python3-setuptools \
    python3-wheel \
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
    gfortran \
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
    # For Open3D GUI (optional)
    libsdl2-dev \
    libglfw3-dev \
    libglew-dev \
    # Spatial indexing for trimesh
    libspatialindex-dev \
    && rm -rf /var/lib/apt/lists/*

# Set GCC 11 as default
RUN update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-11 100 && \
    update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-11 100

# Set Clang 12 for Open3D compilation
RUN update-alternatives --install /usr/bin/clang clang /usr/bin/clang-12 100 && \
    update-alternatives --install /usr/bin/clang++ clang++ /usr/bin/clang++-12 100

# Install nlohmann-json
RUN apt-get update && apt-get install -y \
    nlohmann-json3-dev \
    && rm -rf /var/lib/apt/lists/*

# Configure Python with China mirrors
RUN pip3 config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip3 config set global.trusted-host pypi.tuna.tsinghua.edu.cn

# Install Python dependencies for the shoe last matcher
RUN pip3 install --no-cache-dir \
    numpy==1.24.3 \
    scipy==1.10.1 \
    matplotlib==3.7.1 \
    trimesh==4.0.8 \
    rhino3dm==8.4.0 \
    plotly==5.18.0 \
    scikit-learn==1.3.2 \
    networkx==3.1 \
    rtree==1.1.0 \
    scikit-build-core==0.6.1 \
    pybind11==2.11.1 \
    jupyter==1.0.0 \
    ipywidgets==8.1.1

# Build and install Open3D 0.18 from source
RUN cd /tmp && \
    git clone --depth 1 --branch v0.18.0 https://github.com/isl-org/Open3D.git && \
    cd Open3D && \
    mkdir build && cd build && \
    CC=clang-12 CXX=clang++-12 cmake \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX=/usr/local \
        -DBUILD_GUI=OFF \
        -DBUILD_EXAMPLES=OFF \
        -DBUILD_UNIT_TESTS=OFF \
        -DBUILD_PYTHON_MODULE=ON \
        -DPYTHON_EXECUTABLE=/usr/bin/python3 \
        -DBUILD_SHARED_LIBS=ON \
        -DBUILD_CUDA_MODULE=OFF \
        -DBUILD_WEBRTC=OFF \
        .. && \
    make -j$(nproc) && \
    make install && \
    cd / && rm -rf /tmp/Open3D

# Install Open3D Python bindings
RUN pip3 install --no-cache-dir open3d==0.18.0

# Update library paths
RUN echo "/usr/local/lib" >> /etc/ld.so.conf.d/local.conf && \
    ldconfig

# Install OpenNURBS (for 3DM file support)
RUN cd /tmp && \
    wget https://github.com/mcneel/opennurbs/archive/refs/tags/v8.21.25188.17001.tar.gz && \
    tar -xf v8.21.25188.17001.tar.gz && \
    cd opennurbs-8.21.25188.17001 && \
    mkdir build && cd build && \
    cmake .. -DCMAKE_INSTALL_PREFIX=/usr/local -DCMAKE_BUILD_TYPE=Release -DON_DISABLE_TESTS=ON && \
    make -j$(nproc) && \
    make install && \
    cp ../opennurbs_cpp_base.h /usr/local/include/OpenNURBS/ && \
    ln -sf /usr/local/include/OpenNURBS /usr/local/include/opennurbs && \
    cd / && rm -rf /tmp/opennurbs* /tmp/v8.21.25188.17001.tar.gz

# Install VSCode Server dependencies
RUN apt-get update && apt-get install -y \
    openssh-server \
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

# Create directories for the project structure
RUN mkdir -p /workspace/project/hybrid/cpp \
             /workspace/project/hybrid/python \
             /workspace/project/models \
             /workspace/project/candidates \
             /workspace/project/output && \
    chown -R dev:dev /workspace

# Set working directory
WORKDIR /workspace/project

# Expose ports
EXPOSE 2222 8888 8050

# Create startup script
RUN echo '#!/bin/bash\n\
# Start SSH service\n\
service ssh start\n\
\n\
# Set library path for Open3D\n\
export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH\n\
\n\
# Print environment info\n\
echo "=== Shoe Last Matcher Development Environment ==="\n\
echo "Open3D version: $(python3 -c \"import open3d; print(open3d.__version__)\" 2>/dev/null || echo \"Not available\")"\n\
echo "Python version: $(python3 --version)"\n\
echo "CMake version: $(cmake --version | head -n1)"\n\
echo "Clang version: $(clang --version | head -n1)"\n\
echo "GCC version: $(gcc --version | head -n1)"\n\
echo "================================="\n\
\n\
# Keep container running\n\
tail -f /dev/null' > /start.sh && \
    chmod +x /start.sh

# Create build script for the C++ extension
RUN echo '#!/bin/bash\n\
cd /workspace/project/hybrid\n\
echo "Building C++ extension for Shoe Last Matcher..."\n\
pip3 uninstall -y shoe-last-hybrid 2>/dev/null\n\
python3 -m pip install -v .\n\
echo "Build complete!"\n\
echo "Testing import..."\n\
LD_PRELOAD=/usr/local/lib/libOpen3D.so python3 -c "import cppcore; print(\"✓ cppcore module imported successfully\")" || echo "✗ Failed to import cppcore"' > /workspace/build_extension.sh && \
    chmod +x /workspace/build_extension.sh

# Create test script
RUN echo '#!/bin/bash\n\
echo "=== Testing Shoe Last Matcher Environment ==="\n\
echo ""\n\
echo "1. Python packages:"\n\
python3 -c "import numpy; print(f\"  ✓ NumPy {numpy.__version__}\")"\n\
python3 -c "import trimesh; print(f\"  ✓ Trimesh {trimesh.__version__}\")"\n\
python3 -c "import rhino3dm; print(f\"  ✓ Rhino3dm {rhino3dm.__version__}\")"\n\
python3 -c "import open3d; print(f\"  ✓ Open3D {open3d.__version__}\")"\n\
python3 -c "import plotly; print(f\"  ✓ Plotly {plotly.__version__}\")"\n\
echo ""\n\
echo "2. C++ libraries:"\n\
[ -f /usr/local/lib/libOpen3D.so ] && echo "  ✓ Open3D library installed" || echo "  ✗ Open3D library not found"\n\
[ -f /usr/local/include/opennurbs/opennurbs.h ] && echo "  ✓ OpenNURBS headers installed" || echo "  ✗ OpenNURBS not found"\n\
pkg-config --exists eigen3 && echo "  ✓ Eigen3 $(pkg-config --modversion eigen3)" || echo "  ✗ Eigen3 not found"\n\
echo ""\n\
echo "3. Build tools:"\n\
cmake --version | head -n1 | sed "s/^/  ✓ /"\n\
ninja --version | sed "s/^/  ✓ Ninja /"\n\
echo ""\n\
echo "=== Environment Ready ==="\n\
echo "To build the C++ extension, run: /workspace/build_extension.sh"\n\
echo "To run the matcher, use: LD_PRELOAD=/usr/local/lib/libOpen3D.so python3 hybrid/python/hybrid_matcher_optimized.py"' > /workspace/test_env.sh && \
    chmod +x /workspace/test_env.sh

# Switch to dev user
USER dev

# Set environment variables for dev user
ENV LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH
ENV PATH=/home/dev/.local/bin:$PATH

CMD ["/start.sh"]