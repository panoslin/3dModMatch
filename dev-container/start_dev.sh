#!/bin/bash

# Development environment startup script
# This script starts the development container and sets up the environment

set -e

echo "=== Starting C++ Development Environment ==="

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker first."
    exit 1
fi

# Set proxy if provided
if [ -n "$HTTP_PROXY" ]; then
    echo "Using HTTP proxy: $HTTP_PROXY"
fi

# Build and start the container
echo "Building and starting development container..."
docker-compose up --build -d

# Wait for container to be ready
echo "Waiting for container to be ready..."
sleep 10

# Check if container is running
if docker-compose ps | grep -q "Up"; then
    echo "Container is running!"
    echo ""
    echo "=== Connection Information ==="
    echo "SSH Host: localhost"
    echo "SSH Port: 2222"
    echo "Username: dev"
    echo "Password: devcontainer"
    echo ""
    echo "=== VSCode Remote Development ==="
    echo "1. Install 'Remote - SSH' extension in VSCode"
    echo "2. Press Ctrl+Shift+P and select 'Remote-SSH: Connect to Host'"
    echo "3. Select 'shoe-matcher-dev' from the list"
    echo "4. Enter password: devcontainer"
    echo ""
    echo "=== Manual SSH Connection ==="
    echo "ssh dev@localhost -p 2222"
    echo ""
    echo "=== Container Management ==="
    echo "Stop container: docker-compose down"
    echo "View logs: docker-compose logs -f"
    echo "Enter container: docker-compose exec cpp-dev bash"
    echo ""
    echo "=== Next Steps ==="
    echo "1. Connect via VSCode Remote SSH"
    echo "2. Run: /workspace/project/dev-container/build_cpp.sh"
    echo "3. Run: /workspace/project/dev-container/test_build.sh"
else
    echo "Error: Container failed to start. Check logs with: docker-compose logs"
    exit 1
fi

