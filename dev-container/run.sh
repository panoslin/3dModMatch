#!/bin/bash

# Run script for Shoe Last Matcher Docker environment
set -e

echo "=========================================="
echo "Shoe Last Matcher - Docker Run Script"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

# Parse arguments
DETACHED=true
WITH_JUPYTER=false
FOLLOW_LOGS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --attach)
            DETACHED=false
            shift
            ;;
        --jupyter)
            WITH_JUPYTER=true
            shift
            ;;
        --logs)
            FOLLOW_LOGS=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --attach     Run in attached mode (see output)"
            echo "  --jupyter    Also start Jupyter notebook service"
            echo "  --logs       Follow logs after starting"
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

# Start the services
echo -e "${GREEN}Starting Shoe Last Matcher container...${NC}"

if [ "$WITH_JUPYTER" = true ]; then
    if [ "$DETACHED" = true ]; then
        $COMPOSE_CMD --profile jupyter up -d
    else
        $COMPOSE_CMD --profile jupyter up
    fi
else
    if [ "$DETACHED" = true ]; then
        $COMPOSE_CMD up -d shoe-matcher
    else
        $COMPOSE_CMD up shoe-matcher
    fi
fi

# Wait for container to be ready
echo -e "${YELLOW}Waiting for container to be ready...${NC}"
sleep 5

# Check if container is running
if docker ps | grep -q shoe-matcher-dev; then
    echo -e "${GREEN}✓ Container is running!${NC}"
    echo ""
    echo "=========================================="
    echo -e "${BLUE}Connection Information:${NC}"
    echo "----------------------------------------"
    echo "SSH:      ssh -p 2222 dev@localhost"
    echo "Password: devcontainer"
    echo ""
    if [ "$WITH_JUPYTER" = true ]; then
        echo "Jupyter:  http://localhost:8889"
        echo "          (no password required)"
        echo ""
    fi
    echo "=========================================="
    echo -e "${BLUE}Quick Commands:${NC}"
    echo "----------------------------------------"
    echo "Enter container:  docker exec -it shoe-matcher-dev bash"
    echo "Test environment: docker exec shoe-matcher-dev /workspace/test_env.sh"
    echo "Build extension:  docker exec shoe-matcher-dev /workspace/build_extension.sh"
    echo "View logs:        docker logs shoe-matcher-dev"
    echo "Stop container:   docker-compose down"
    echo "=========================================="
    
    # Follow logs if requested
    if [ "$FOLLOW_LOGS" = true ]; then
        echo ""
        echo -e "${YELLOW}Following container logs (Ctrl+C to exit)...${NC}"
        docker logs -f shoe-matcher-dev
    fi
else
    echo -e "${RED}✗ Container failed to start${NC}"
    echo "Check logs with: docker logs shoe-matcher-dev"
    exit 1
fi
