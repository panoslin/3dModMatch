#!/bin/bash

# Script to manually install OpenNURBS
# This script should be run inside the container after it's built

set -e

echo "=== Installing OpenNURBS ==="
echo "This script will help you install OpenNURBS for 3DM file support."
echo ""

# Check if we're in the container
if [ ! -f "/workspace/test_env.sh" ]; then
    echo "Error: This script should be run inside the development container."
    echo "Please connect to the container first:"
    echo "  ssh dev@localhost -p 2222"
    echo "  Password: devcontainer"
    exit 1
fi

echo "Step 1: Download OpenNURBS from GitHub"
echo "Source: https://github.com/mcneel/opennurbs/releases/tag/v8.21.25188.17001"
echo "Download the latest version (currently v8.21.25188.17001)"
echo ""

# Create a temporary directory for the download
TEMP_DIR="/tmp/opennurbs_install"
mkdir -p "$TEMP_DIR"
cd "$TEMP_DIR"

echo "Step 2: Please download the OpenNURBS zip file to this container"
echo "You can use one of these methods:"
echo ""
echo "Method 1 - Using wget (if you have the direct URL):"
echo "  wget <DOWNLOAD_URL> -O opennurbs.zip"
echo ""
echo "Method 2 - Using scp from host machine:"
echo "  scp -P 2222 /path/to/opennurbs.zip dev@localhost:/tmp/opennurbs_install/"
echo ""
echo "Method 3 - Using Docker cp:"
echo "  docker cp /path/to/opennurbs.zip shoe-matcher-dev:/tmp/opennurbs_install/"
echo ""

# Wait for user to download the file
echo "Press Enter when you have downloaded the file to $TEMP_DIR/opennurbs.zip"
read -p "Press Enter to continue..."

# Check if the file exists
if [ ! -f "opennurbs.zip" ]; then
    echo "Error: opennurbs.zip not found in $TEMP_DIR"
    echo "Please download the file first."
    exit 1
fi

echo "Step 3: Extracting and building OpenNURBS..."
unzip -q opennurbs.zip

# Find the extracted directory
EXTRACTED_DIR=$(find . -maxdepth 1 -type d -name "opennurbs*" | head -n1)
if [ -z "$EXTRACTED_DIR" ]; then
    echo "Error: Could not find extracted OpenNURBS directory"
    exit 1
fi

cd "$EXTRACTED_DIR"

echo "Step 4: Building OpenNURBS..."
mkdir -p build
cd build

cmake .. \
    -DCMAKE_INSTALL_PREFIX=/usr/local \
    -DCMAKE_BUILD_TYPE=Release \
    -DON_DISABLE_TESTS=ON

make -j$(nproc)
sudo make install

echo "Step 5: Cleaning up..."
cd /
rm -rf "$TEMP_DIR"

echo ""
echo "=== OpenNURBS Installation Complete ==="
echo "OpenNURBS has been installed to /usr/local/include/opennurbs/"
echo "You can now build your C++ project with 3DM file support."
echo ""
echo "To test the installation:"
echo "  /workspace/project/dev-container/test_environment.sh"
