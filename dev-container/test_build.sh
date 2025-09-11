#!/bin/bash

# Test script for the C++ shoe last matcher
# This script tests the build and runs basic functionality tests

set -e

echo "=== Testing C++ Shoe Last Matcher ==="

# Navigate to project directory
cd /workspace/project/cpp_version

# Test if build exists
if [ ! -f "build/shoe_matcher" ]; then
    echo "Build not found. Running build script..."
    /workspace/project/dev-container/build_cpp.sh
fi

cd build

# Test basic functionality
echo "Testing basic functionality..."

# Test help command
echo "1. Testing help command..."
./shoe_matcher --help || echo "Help command failed"

# Test with sample data if available
if [ -d "/workspace/project/models" ] && [ -d "/workspace/project/candidates" ]; then
    echo "2. Testing with sample data..."
    
    # Find a model file
    MODEL_FILE=$(find /workspace/project/models -name "*.3dm" | head -n1)
    if [ -n "$MODEL_FILE" ]; then
        echo "   Using model: $MODEL_FILE"
        
        # Test single candidate
        CANDIDATE_FILE=$(find /workspace/project/candidates -name "*.3dm" | head -n1)
        if [ -n "$CANDIDATE_FILE" ]; then
            echo "   Testing single candidate: $CANDIDATE_FILE"
            ./shoe_matcher --target "$MODEL_FILE" --single-candidate "$CANDIDATE_FILE" --clearance 2.0
        fi
        
        # Test candidate library
        echo "   Testing candidate library..."
        ./shoe_matcher --target "$MODEL_FILE" --candidates /workspace/project/candidates/ --clearance 2.0 --topk 3
    else
        echo "   No model files found in /workspace/project/models"
    fi
else
    echo "2. No sample data found. Skipping data tests."
fi

# Test simple test executable
if [ -f "simple_test" ]; then
    echo "3. Running simple test..."
    ./simple_test
fi

echo "=== Test Complete ==="
