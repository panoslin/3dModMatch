#!/bin/bash

# Build script for the C++ shoe last matcher project
# This script should be run inside the development container

set -e

echo "=== Building C++ Shoe Last Matcher ==="

# Navigate to project directory
cd /workspace/project/cpp_version

# Create build directory
mkdir -p build
cd build

# Configure CMake
echo "Configuring CMake..."
cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_CXX_STANDARD=17 \
    -DCMAKE_CXX_COMPILER=g++-11 \
    -DCMAKE_C_COMPILER=gcc-11 \
    -DCMAKE_INSTALL_PREFIX=/usr/local \
    -DEigen3_DIR=/usr/lib/cmake/eigen3 \
    -Dnlohmann_json_DIR=/usr/lib/x86_64-linux-gnu/cmake/nlohmann_json \
    -DOPENNURBS_PUBLIC_INSTALL_DIR=/usr/local \
    -DHAVE_OPENNURBS=ON

# Build the project
echo "Building project..."
make -j$(nproc)

# Install (optional)
echo "Installing..."
sudo make install

echo "=== Build Complete ==="
echo "Executables created:"
ls -la shoe_matcher* simple_test* 2>/dev/null || echo "No executables found"

echo ""
echo "To test the build:"
echo "  ./shoe_matcher --help"
echo "  ./simple_test"
