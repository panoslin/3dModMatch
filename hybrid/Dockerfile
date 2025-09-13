# Production Dockerfile for Hybrid Shoe Last Matcher
# Optimized for running hybrid_matcher_multiprocess.py
FROM ubuntu:22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Configure China mirrors for apt
RUN sed -i 's@//.*archive.ubuntu.com@//mirrors.aliyun.com@g' /etc/apt/sources.list && \
    sed -i 's@//.*security.ubuntu.com@//mirrors.aliyun.com@g' /etc/apt/sources.list && \
    sed -i 's@//ports.ubuntu.com@//mirrors.aliyun.com@g' /etc/apt/sources.list

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Build essentials
    build-essential \
    cmake \
    ninja-build \
    pkg-config \
    git \
    wget \
    # C++ development
    gcc-11 \
    g++-11 \
    # Python 3.10
    python3.10 \
    python3.10-dev \
    python3-pip \
    python3-setuptools \
    python3-wheel \
    # Math libraries
    libeigen3-dev \
    # Image processing
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    # Compression
    libzip-dev \
    zlib1g-dev \
    # Network
    libcurl4-openssl-dev \
    # Other utilities
    libssl-dev \
    libffi-dev \
    # Spatial indexing for trimesh
    libspatialindex-dev \
    # For Open3D GUI (optional)
    libsdl2-dev \
    libglfw3-dev \
    libglew-dev \
    # OpenGL
    libgl1-mesa-dev \
    libglu1-mesa-dev \
    && rm -rf /var/lib/apt/lists/*

# Install newer CMake (required for Open3D 0.19)
RUN cd /tmp && \
    wget https://github.com/Kitware/CMake/releases/download/v3.28.1/cmake-3.28.1-linux-x86_64.tar.gz && \
    tar -xzf cmake-3.28.1-linux-x86_64.tar.gz && \
    cp -r cmake-3.28.1-linux-x86_64/bin/* /usr/local/bin/ && \
    cp -r cmake-3.28.1-linux-x86_64/share/* /usr/local/share/ && \
    cp -r cmake-3.28.1-linux-x86_64/doc/* /usr/local/doc/ && \
    rm -rf cmake-3.28.1-linux-x86_64*

# Set GCC 11 as default
RUN update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-11 100 && \
    update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-11 100

# Install nlohmann-json
RUN apt-get update && apt-get install -y \
    nlohmann-json3-dev \
    && rm -rf /var/lib/apt/lists/*

# Configure Python with China mirrors
RUN pip3 config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip3 config set global.trusted-host pypi.tuna.tsinghua.edu.cn

# Install Python dependencies for hybrid matcher
RUN pip3 install --no-cache-dir \
    numpy==1.26.4 \
    scipy==1.15.3 \
    trimesh==3.23.5 \
    rhino3dm==8.17.0 \
    plotly==6.3.0 \
    scikit-learn==1.7.1 \
    networkx==3.4.2 \
    rtree==1.4.1 \
    scikit-build-core==0.6.1 \
    pybind11==2.11.1 \
    pandas==2.3.2 \
    Cython==0.29.37 \
    pyembree==0.1.12 \
    pygltflib==1.16.5

# Build and install Open3D 0.19 from source
RUN cd /tmp && \
    git clone --depth 1 --branch v0.19.0 https://github.com/isl-org/Open3D.git && \
    cd Open3D && \
    mkdir build && cd build && \
    cmake \
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
RUN pip3 install --no-cache-dir open3d==0.19.0

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

# Update library paths
RUN echo "/usr/local/lib" >> /etc/ld.so.conf.d/local.conf && \
    ldconfig

# Create working directory
WORKDIR /app

# Copy hybrid module
COPY . /app/

# Build C++ module
RUN cd /app && \
    rm -rf build && \
    mkdir -p build && \
    cd build && \
    cmake .. \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_CXX_STANDARD=17 \
        -DCMAKE_CXX_COMPILER=g++-11 \
        -DCMAKE_C_COMPILER=gcc-11 \
        -DCMAKE_INSTALL_PREFIX=/usr/local \
        -DEigen3_DIR=/usr/lib/cmake/eigen3 \
        -Dnlohmann_json_DIR=/usr/lib/x86_64-linux-gnu/cmake/nlohmann_json \
        -Dpybind11_DIR=/usr/local/lib/python3.10/dist-packages/pybind11/share/cmake/pybind11 && \
    make -j$(nproc) && \
    make install && \
    cp cppcore.cpython-310-x86_64-linux-gnu.so /usr/local/lib/python3.10/dist-packages/cppcore.so

# Set environment variables
ENV LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH
ENV LD_PRELOAD=/usr/local/lib/libOpen3D.so
ENV PYTHONPATH=/app/python:$PYTHONPATH
ENV OMP_NUM_THREADS=1

# Create test script
RUN echo '#!/bin/bash\n\
echo "=== Testing Hybrid Shoe Last Matcher ==="\n\
echo ""\n\
echo "1. Python packages:"\n\
python3 -c "import numpy; print(f\"  ✓ NumPy {numpy.__version__}\")"\n\
python3 -c "import trimesh; print(f\"  ✓ Trimesh {trimesh.__version__}\")"\n\
python3 -c "import rhino3dm; print(f\"  ✓ Rhino3dm {rhino3dm.__version__}\")"\n\
python3 -c "import open3d; print(f\"  ✓ Open3D {open3d.__version__}\")"\n\
python3 -c "import plotly; print(f\"  ✓ Plotly {plotly.__version__}\")"\n\
python3 -c "import sklearn; print(f\"  ✓ Scikit-learn {sklearn.__version__}\")"\n\
echo ""\n\
echo "2. C++ module test:"\n\
LD_PRELOAD=/usr/local/lib/libOpen3D.so python3 -c "import cppcore; print(\"  ✓ cppcore module working\")" 2>/dev/null || echo "  ✗ cppcore module not working"\n\
echo ""\n\
echo "3. Hybrid matcher test:"\n\
LD_PRELOAD=/usr/local/lib/libOpen3D.so python3 -c "from python.hybrid_matcher_multiprocess import run_multiprocess_matcher; print(\"  ✓ Hybrid matcher import successful\")" 2>/dev/null || echo "  ✗ Hybrid matcher import failed"\n\
echo ""\n\
echo "=== Environment Ready ==="\n\
echo "To run the matcher:"\n\
echo "  LD_PRELOAD=/usr/local/lib/libOpen3D.so python3 python/hybrid_matcher_multiprocess.py --help"' > /app/test_env.sh && \
    chmod +x /app/test_env.sh

# Create entrypoint script
RUN echo '#!/bin/bash\n\
# Set environment\n\
export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH\n\
export LD_PRELOAD=/usr/local/lib/libOpen3D.so\n\
export PYTHONPATH=/app/python:$PYTHONPATH\n\
export OMP_NUM_THREADS=1\n\
\n\
# Print environment info\n\
echo "=== Hybrid Shoe Last Matcher ==="\n\
echo "Open3D version: $(python3 -c \"import open3d; print(open3d.__version__)\" 2>/dev/null || echo \"Not available\")"\n\
echo "Python version: $(python3 --version)"\n\
echo "Working directory: $(pwd)"\n\
echo "================================="\n\
\n\
# Execute command\n\
exec "$@"' > /app/entrypoint.sh && \
    chmod +x /app/entrypoint.sh

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command
CMD ["python3", "python/hybrid_matcher_multiprocess.py", "--help"]
