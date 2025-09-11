#!/bin/bash

# Test script to verify the development environment
# This script can be run inside the container to check if everything is working

echo "=== Testing C++ Development Environment ==="

# Test basic tools
echo "1. Testing basic tools..."
echo "   GCC version: $(gcc --version | head -n1)"
echo "   G++ version: $(g++ --version | head -n1)"
echo "   CMake version: $(cmake --version | head -n1)"
echo "   Git version: $(git --version)"

# Test dependencies
echo ""
echo "2. Testing dependencies..."
echo "   Eigen3: $(pkg-config --modversion eigen3 2>/dev/null || echo "Not found")"
echo "   nlohmann-json: $(pkg-config --modversion nlohmann_json 2>/dev/null || echo "Not found")"

# Test Open3D
echo "   Open3D headers: $(ls /usr/local/include/open3d/ 2>/dev/null | wc -l) files"
echo "   Open3D libraries: $(ls /usr/local/lib/libOpen3D* 2>/dev/null | wc -l) files"

# Test OpenNURBS
echo "   OpenNURBS headers: $(ls /usr/local/include/opennurbs/ 2>/dev/null | wc -l) files"
echo "   OpenNURBS libraries: $(ls /usr/local/lib/libopennurbs* 2>/dev/null | wc -l) files"

# Test Python
echo ""
echo "3. Testing Python environment..."
echo "   Python version: $(python3 --version)"
echo "   Pip version: $(pip3 --version | head -n1)"

# Test SSH
echo ""
echo "4. Testing SSH service..."
if systemctl is-active --quiet ssh; then
    echo "   SSH service: Running"
else
    echo "   SSH service: Not running (this is normal in container)"
fi

# Test workspace
echo ""
echo "5. Testing workspace..."
echo "   Workspace directory: $(pwd)"
echo "   Project files: $(ls -la /workspace/project/ 2>/dev/null | wc -l) items"
echo "   C++ source files: $(find /workspace/project/cpp_version -name "*.cpp" 2>/dev/null | wc -l) files"

# Test build system
echo ""
echo "6. Testing build system..."
if [ -d "/workspace/project/cpp_version" ]; then
    cd /workspace/project/cpp_version
    if [ -f "CMakeLists.txt" ]; then
        echo "   CMakeLists.txt: Found"
        if [ -d "build" ]; then
            echo "   Build directory: Exists"
            if [ -f "build/Makefile" ]; then
                echo "   Makefile: Generated"
            else
                echo "   Makefile: Not generated (run cmake first)"
            fi
        else
            echo "   Build directory: Not created (run mkdir build && cd build && cmake ..)"
        fi
    else
        echo "   CMakeLists.txt: Not found"
    fi
else
    echo "   C++ project directory: Not found"
fi

echo ""
echo "=== Environment Test Complete ==="
echo ""
echo "If any tests failed, check the installation or run:"
echo "  /workspace/project/dev-container/build_cpp.sh"
