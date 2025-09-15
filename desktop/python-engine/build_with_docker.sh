#!/bin/bash
#
# Build Python engine using the existing Docker configuration
# This ensures all dependencies are correctly included
#

set -e

echo "====================================="
echo "Building Python Engine with Docker"
echo "====================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

# Build the Docker image from hybrid directory
echo -e "${YELLOW}Step 1: Building Docker image...${NC}"
cd ../../hybrid
docker build -t hybrid-shoe-matcher:builder .

# Create a temporary container to extract the built files
echo -e "${YELLOW}Step 2: Extracting Python engine from Docker...${NC}"
docker create --name temp-matcher hybrid-shoe-matcher:builder

# Extract the compiled cppcore module
echo -e "${YELLOW}Step 3: Extracting C++ module...${NC}"
docker cp temp-matcher:/app/build/cppcore.cpython-310-x86_64-linux-gnu.so ../desktop/python-engine/cppcore.so || \
docker cp temp-matcher:/app/cppcore.so ../desktop/python-engine/cppcore.so || \
echo -e "${RED}Warning: Could not extract cppcore module${NC}"

# Extract Open3D libraries if needed
echo -e "${YELLOW}Step 4: Extracting Open3D libraries...${NC}"
mkdir -p ../desktop/python-engine/libs
docker cp temp-matcher:/usr/local/lib/libOpen3D.so ../desktop/python-engine/libs/ || \
echo -e "${RED}Warning: Could not extract Open3D library${NC}"

# Clean up
docker rm temp-matcher

echo -e "${GREEN}Docker build extraction complete!${NC}"
echo ""
echo "====================================="
echo "Building standalone executable with PyInstaller"
echo "====================================="

cd ../desktop/python-engine

# Install PyInstaller in a virtual environment
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
fi

source venv/bin/activate

echo -e "${YELLOW}Installing PyInstaller...${NC}"
pip install pyinstaller

# Build with PyInstaller
echo -e "${YELLOW}Building executable...${NC}"
pyinstaller build.spec --clean

if [ -f "dist/shoe-matcher-engine" ]; then
    echo -e "${GREEN}✅ Build successful!${NC}"
    echo "Executable created at: dist/shoe-matcher-engine"
    
    # Test the executable
    echo -e "${YELLOW}Testing executable...${NC}"
    ./dist/shoe-matcher-engine --version
else
    echo -e "${RED}❌ Build failed!${NC}"
    exit 1
fi

deactivate

echo ""
echo "====================================="
echo -e "${GREEN}Build complete!${NC}"
echo "====================================="
echo "The Python engine is ready at: dist/shoe-matcher-engine"
echo "You can now use it with the Electron app."
