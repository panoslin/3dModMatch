#!/bin/bash

# Complete setup script for the C++ development environment
# This script sets up everything needed for development

set -e

echo "=== C++ Development Environment Setup ==="
echo "This script will set up a complete C++ development environment"
echo "with all dependencies and China mirrors for optimal performance."
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed. Please install Docker first."
    echo "Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker first."
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "Error: docker-compose is not installed. Please install docker-compose first."
    echo "Visit: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✓ Docker and docker-compose are available"

# Set up SSH configuration
echo "Setting up SSH configuration..."
if [ -f "ssh_config" ]; then
    ./setup_ssh.sh
    echo "✓ SSH configuration set up"
else
    echo "Warning: ssh_config not found, skipping SSH setup"
fi

# Make all scripts executable
echo "Making scripts executable..."
chmod +x *.sh
echo "✓ Scripts are executable"

# Create .env file for proxy settings if needed
if [ -n "$HTTP_PROXY" ] || [ -n "$HTTPS_PROXY" ]; then
    echo "Creating .env file for proxy settings..."
    cat > .env << EOF
HTTP_PROXY=${HTTP_PROXY:-}
HTTPS_PROXY=${HTTPS_PROXY:-}
NO_PROXY=${NO_PROXY:-}
EOF
    echo "✓ .env file created with proxy settings"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Start the development environment:"
echo "   ./start_dev.sh"
echo ""
echo "2. Connect via VSCode Remote SSH:"
echo "   - Install 'Remote - SSH' extension"
echo "   - Connect to 'shoe-matcher-dev'"
echo "   - Password: devcontainer"
echo ""
echo "3. Build and test the project:"
echo "   - Run: /workspace/project/dev-container/build_cpp.sh"
echo "   - Run: /workspace/project/dev-container/test_build.sh"
echo ""
echo "=== Ready for Development ==="

