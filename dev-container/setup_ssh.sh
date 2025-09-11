#!/bin/bash

# Setup script for SSH connection to the development container
# Run this script to configure SSH for VSCode remote development

set -e

echo "=== Setting up SSH for VSCode Remote Development ==="

# Create SSH config directory if it doesn't exist
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# Copy SSH config
if [ -f "ssh_config" ]; then
    echo "Adding SSH configuration..."
    cat ssh_config >> ~/.ssh/config
    chmod 600 ~/.ssh/config
    echo "SSH config added to ~/.ssh/config"
else
    echo "Error: ssh_config file not found!"
    exit 1
fi

# Test SSH connection
echo "Testing SSH connection..."
echo "You can now connect using: ssh shoe-matcher-dev"
echo "Password: devcontainer"
echo ""
echo "For VSCode Remote Development:"
echo "1. Install the 'Remote - SSH' extension in VSCode"
echo "2. Press Ctrl+Shift+P and select 'Remote-SSH: Connect to Host'"
echo "3. Select 'shoe-matcher-dev' from the list"
echo "4. Enter password: devcontainer"
echo ""
echo "=== Setup Complete ==="
