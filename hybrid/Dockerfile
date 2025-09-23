# Multi-stage Dockerfile for Hybrid Shoe Last Matcher
# Stage 1: Build environment
FROM ubuntu:22.04 as builder

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# # Configure China mirrors for apt
# RUN sed -i 's@//.*archive.ubuntu.com@//mirrors.aliyun.com@g' /etc/apt/sources.list && \
#     sed -i 's@//.*security.ubuntu.com@//mirrors.aliyun.com@g' /etc/apt/sources.list && \
#     sed -i 's@//ports.ubuntu.com@//mirrors.aliyun.com@g' /etc/apt/sources.list

# Install system dependencies, CMake, and set GCC in one layer
RUN apt-get update && apt-get install -y \
    # Build essentials
    build-essential cmake ninja-build pkg-config git wget \
    # C++ development
    gcc-11 g++-11 \
    # Python 3.10
    python3.10 python3.10-dev python3-pip python3-setuptools python3-wheel \
    # Math and development libraries
    libeigen3-dev nlohmann-json3-dev \
    # Image processing
    libjpeg-dev libpng-dev libtiff-dev \
    # Compression and network
    libzip-dev zlib1g-dev libcurl4-openssl-dev \
    # Other utilities
    libssl-dev libffi-dev libspatialindex-dev \
    # For Open3D GUI (optional)
    libsdl2-dev libglfw3-dev libglew-dev \
    # OpenGL and TBB
    libgl1-mesa-dev libglu1-mesa-dev libtbb12 libtbb-dev \
    && rm -rf /var/lib/apt/lists/* \
    # Install newer CMake and set GCC in same layer
    && cd /tmp \
    && wget -q https://github.com/Kitware/CMake/releases/download/v3.28.1/cmake-3.28.1-linux-x86_64.tar.gz \
    && tar -xzf cmake-3.28.1-linux-x86_64.tar.gz \
    && cp -r cmake-3.28.1-linux-x86_64/bin/* /usr/local/bin/ \
    && cp -r cmake-3.28.1-linux-x86_64/share/* /usr/local/share/ \
    && rm -rf cmake-3.28.1-linux-x86_64* \
    && update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-11 100 \
    && update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-11 100

# # Configure Python with China mirrors
# RUN pip3 config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
#     pip3 config set global.trusted-host pypi.tuna.tsinghua.edu.cn

# Install Python dependencies for hybrid matcher (build stage)
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
    pygltflib==1.16.5 \
    # Install regular Open3D (will be cleaned up in runtime stage)
    open3d==0.19.0

# Copy pre-built Open3D and OpenNURBS libraries from compressed archive
# This avoids the time-consuming compilation and network issues
COPY docker-extract.tar.gz /tmp/

# Configure Open3D libraries, headers, and CMake files in one layer
RUN cd /tmp \
    && tar -xzf docker-extract.tar.gz \
    && cp -r docker-extract/* /usr/local/ \
    && rm -rf docker-extract docker-extract.tar.gz \
    && mv /usr/local/libOpen3D.so* /usr/local/lib/ \
    && mv /usr/local/libOpenNURBS.so* /usr/local/lib/ \
    && mv /usr/local/libopennurbs* /usr/local/lib/ \
    && mv /usr/local/open3d /usr/local/include/ \
    && mv /usr/local/OpenNURBS /usr/local/include/ \
    && mv /usr/local/opennurbs /usr/local/include/ \
    && mv /usr/local/opennurbsStatic /usr/local/include/ \
    # Fix CMake configuration files
    && if [ -f /usr/local/lib/cmake/Open3D/Open3DTargets-release.cmake ]; then \
        sed -i 's|${_IMPORT_PREFIX}/lib/libtbb.so.12.12|/usr/lib/x86_64-linux-gnu/libtbb.so.12|g' /usr/local/lib/cmake/Open3D/Open3DTargets-release.cmake \
        && sed -i 's|${_IMPORT_PREFIX}/lib/libOpen3D.so.0.19.0|/usr/local/lib/libOpen3D.so.0.19.0|g' /usr/local/lib/cmake/Open3D/Open3DTargets-release.cmake; \
    fi \
    && if [ -f /usr/local/lib/cmake/Open3D/Open3DConfig.cmake ]; then \
        sed -i 's|get_filename_component(PACKAGE_PREFIX_DIR "${CMAKE_CURRENT_LIST_DIR}/../../../" ABSOLUTE)|set(PACKAGE_PREFIX_DIR "/usr/local")|g' /usr/local/lib/cmake/Open3D/Open3DConfig.cmake; \
    fi \
    && if [ -f /usr/local/lib/cmake/Open3D/Open3DTargets.cmake ]; then \
        sed -i 's|\${_IMPORT_PREFIX}/include|/usr/local/include|g' /usr/local/lib/cmake/Open3D/Open3DTargets.cmake; \
    fi \
    # Create symbolic links and update library paths
    && ln -sf /usr/lib/x86_64-linux-gnu/libtbb.so.12 /usr/lib/x86_64-linux-gnu/libtbb.so.12.12\
    && echo "/usr/local/lib" >> /etc/ld.so.conf.d/local.conf \
    && ldconfig

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

# ============================================================================
# Stage 2: Runtime environment (much smaller)
# ============================================================================
FROM ubuntu:22.04 as runtime

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Install only runtime dependencies (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Python runtime
    python3.10 python3-pip \
    # Essential runtime libraries only (minimal headers)
    libeigen3-dev \
    # Image processing runtime libraries
    libjpeg-turbo8 libpng16-16 libtiff5 \
    # Compression and network runtime
    libzip4 zlib1g libcurl4 libssl3 libffi8 \
    # Spatial indexing runtime
    libspatialindex6 \
    # TBB library for Open3D
    libtbb12 \
    # OpenMP library (required for Open3D)
    libgomp1 \
    # Minimal OpenGL support (runtime only)
    libgl1-mesa-glx libglu1-mesa \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    # Clean up additional cache and temporary files
    && find /var/cache -type f -delete \
    && find /var/log -type f -delete \
    && find /tmp -type f -delete

# Install Python dependencies (runtime only, no build dependencies)
RUN pip3 install --no-cache-dir --no-compile \
    numpy==1.26.4 \
    scipy==1.15.3 \
    trimesh==3.23.5 \
    rhino3dm==8.17.0 \
    plotly==6.3.0 \
    scikit-learn==1.7.1 \
    networkx==3.4.2 \
    rtree==1.4.1 \
    pandas==2.3.2 \
    pyembree==0.1.12 \
    pygltflib==1.16.5 \
    # Install regular Open3D
    && pip3 install --no-cache-dir --no-compile open3d==0.19.0 \
    # Aggressive cleanup to reduce image size (saves ~800MB+)
    && find /usr/local/lib/python3.10/dist-packages -name "*.pyc" -delete \
    && find /usr/local/lib/python3.10/dist-packages -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python3.10/dist-packages -name "tests" -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python3.10/dist-packages -name "test" -exec rm -rf {} + 2>/dev/null || true \
    # Remove CUDA components (biggest space savings ~800MB)
    && rm -rf /usr/local/lib/python3.10/dist-packages/open3d/cuda || true \
    # Remove specific PyTorch files but keep ML structure (saves ~50MB)
    && find /usr/local/lib/python3.10/dist-packages/open3d -name "*torch_ops*" -delete || true \
    # Remove heavy ML model files but keep module structure (saves ~50MB)
    && find /usr/local/lib/python3.10/dist-packages/open3d -name "*.pth" -delete || true \
    && find /usr/local/lib/python3.10/dist-packages/open3d -name "*.onnx" -delete || true \
    # Remove documentation and examples (saves ~20MB)
    && find /usr/local/lib/python3.10/dist-packages -name "*.md" -delete || true \
    && find /usr/local/lib/python3.10/dist-packages -name "examples" -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python3.10/dist-packages -name "docs" -exec rm -rf {} + 2>/dev/null || true

# Copy pre-built libraries and compiled module from builder stage
COPY --from=builder /usr/local/lib/libOpen3D.so* /usr/local/lib/
COPY --from=builder /usr/local/lib/libOpenNURBS.so* /usr/local/lib/
COPY --from=builder /usr/local/lib/libopennurbs* /usr/local/lib/
COPY --from=builder /usr/local/include/open3d /usr/local/include/open3d
COPY --from=builder /usr/local/include/OpenNURBS /usr/local/include/OpenNURBS
COPY --from=builder /usr/local/include/opennurbs /usr/local/include/opennurbs
COPY --from=builder /usr/local/include/opennurbsStatic /usr/local/include/opennurbsStatic
COPY --from=builder /usr/local/lib/python3.10/dist-packages/cppcore.so /usr/local/lib/python3.10/dist-packages/cppcore.so

# Create symbolic links for TBB library
RUN ln -sf /usr/lib/x86_64-linux-gnu/libtbb.so.12 /usr/lib/x86_64-linux-gnu/libtbb.so.12.12

# Update library paths
RUN echo "/usr/local/lib" >> /etc/ld.so.conf.d/local.conf && ldconfig

# Create working directory
WORKDIR /app

# Copy only Python application files (not build artifacts)
COPY python/ /app/python/

# Set environment variables
ENV LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH
ENV LD_PRELOAD=/usr/local/lib/libOpen3D.so
ENV PYTHONPATH=/app/python:$PYTHONPATH
ENV OMP_NUM_THREADS=1
# Python optimization environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create minimal entrypoint script
RUN echo '#!/bin/bash\n\
export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH\n\
export LD_PRELOAD=/usr/local/lib/libOpen3D.so\n\
export PYTHONPATH=/app/python:$PYTHONPATH\n\
export OMP_NUM_THREADS=1\n\
exec "$@"' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command
CMD ["python3", "python/hybrid_matcher_multiprocess.py", "--help"]
