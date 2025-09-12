#!/bin/bash

# Build script for Shoe Last Matcher Docker environment
set -e

echo "=========================================="
echo "Shoe Last Matcher - Docker Build Script"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    exit 1
fi

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo -e "${YELLOW}Warning: docker-compose not found, trying docker compose${NC}"
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

# Parse arguments
BUILD_FRESH=false
USE_CACHE=true
PUSH_IMAGE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --fresh)
            BUILD_FRESH=true
            shift
            ;;
        --no-cache)
            USE_CACHE=false
            shift
            ;;
        --push)
            PUSH_IMAGE=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --fresh      Remove existing containers and volumes before building"
            echo "  --no-cache   Build without using Docker cache"
            echo "  --push       Push image to registry after building"
            echo "  --help       Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Clean up if fresh build requested
if [ "$BUILD_FRESH" = true ]; then
    echo -e "${YELLOW}Cleaning up existing containers and volumes...${NC}"
    $COMPOSE_CMD down -v
    docker system prune -f
fi

# Build the Docker image
echo -e "${GREEN}Building Docker image...${NC}"
if [ "$USE_CACHE" = false ]; then
    $COMPOSE_CMD build --no-cache shoe-matcher
else
    $COMPOSE_CMD build shoe-matcher
fi

# Tag the image
docker tag shoe-matcher:latest shoe-matcher:$(date +%Y%m%d)

echo -e "${GREEN}✓ Build completed successfully!${NC}"
echo ""
echo "=========================================="
echo "Next steps:"
echo "1. Start the container: ./run.sh"
echo "2. Connect via SSH: ssh -p 2222 dev@localhost (password: devcontainer)"
echo "3. Or use VSCode Remote-SSH extension"
echo "=========================================="
