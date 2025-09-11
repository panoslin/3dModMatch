# C++ Development Container for Shoe Last Matcher

This development container provides a complete C++ development environment for the Shoe Last Matcher project with all necessary dependencies and China mirrors for optimal performance.

## 🚀 Quick Start

### 1. Start the Development Environment

```bash
# Start the container
./start_dev.sh

# Or manually with docker-compose
docker-compose up --build -d
```

### 2. Connect via VSCode Remote SSH

1. Install the "Remote - SSH" extension in VSCode
2. Press `Ctrl+Shift+P` and select "Remote-SSH: Connect to Host"
3. Select "shoe-matcher-dev" from the list
4. Enter password: `devcontainer`

### 3. Build and Test

```bash
# Build the project
/workspace/project/dev-container/build_cpp.sh

# Test the build
/workspace/project/dev-container/test_build.sh
```

## 📦 Included Dependencies

### Core C++ Libraries
- **Eigen3**: Linear algebra library
- **nlohmann-json**: JSON parsing and generation
- **Open3D**: 3D data processing and visualization
- **OpenNURBS**: 3DM file format support

### Build Tools
- **GCC 11**: C++17 compiler
- **CMake 3.16+**: Build system
- **GDB**: Debugger
- **Valgrind**: Memory debugging

### Development Tools
- **Git**: Version control
- **Vim/Nano**: Text editors
- **SSH Server**: Remote development
- **Python 3**: For some dependencies

## 🌏 China Mirrors

The container is optimized for users in China with mirrors for:
- **APT**: Aliyun mirrors for faster package installation
- **Docker**: Uses China-optimized base images
- **Python**: Tsinghua University PyPI mirror
- **Git**: Optional Gitee mirror for GitHub repositories

## 🔧 Configuration

### Environment Variables

You can set proxy environment variables:

```bash
export HTTP_PROXY=http://localhost:7890
export HTTPS_PROXY=http://localhost:7890
export NO_PROXY=localhost,127.0.0.1

./start_dev.sh
```

### SSH Configuration

The container exposes SSH on port 2222. You can connect manually:

```bash
ssh dev@localhost -p 2222
# Password: devcontainer
```

## 📁 Project Structure

```
dev-container/
├── Dockerfile              # Container definition
├── docker-compose.yml      # Container orchestration
├── ssh_config             # SSH configuration template
├── setup_ssh.sh           # SSH setup script
├── build_cpp.sh           # C++ build script
├── test_build.sh          # Test script
├── start_dev.sh           # Development startup script
├── .vscode/               # VSCode configuration
│   ├── settings.json      # Editor settings
│   ├── launch.json        # Debug configurations
│   └── tasks.json         # Build tasks
└── README.md              # This file
```

## 🛠️ Development Workflow

### 1. Build the Project

```bash
# Inside the container
cd /workspace/project/cpp_version
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
```

### 2. Run Tests

```bash
# Test with sample data
./shoe_matcher --target ../models/36小.3dm --candidates ../candidates/ --clearance 2.0

# Test single candidate
./shoe_matcher --target ../models/36小.3dm --single-candidate ../candidates/B004大.3dm
```

### 3. Debug with VSCode

1. Set breakpoints in your C++ code
2. Press `F5` to start debugging
3. Use the integrated debugger

## 🔍 Troubleshooting

### Container Issues

```bash
# Check container status
docker-compose ps

# View logs
docker-compose logs -f

# Restart container
docker-compose restart

# Rebuild container
docker-compose up --build --force-recreate
```

### Build Issues

```bash
# Clean build
rm -rf /workspace/project/cpp_version/build/*
/workspace/project/dev-container/build_cpp.sh

# Check dependencies
pkg-config --modversion eigen3
pkg-config --modversion nlohmann_json
```

### SSH Connection Issues

```bash
# Test SSH connection
ssh -v dev@localhost -p 2222

# Check SSH service
docker-compose exec cpp-dev service ssh status
```

## 📋 Available Commands

### Container Management
- `./start_dev.sh` - Start development environment
- `docker-compose down` - Stop container
- `docker-compose logs -f` - View logs

### Build Commands
- `./build_cpp.sh` - Build the project
- `./test_build.sh` - Test the build
- `Ctrl+Shift+P` → "Tasks: Run Task" → "build-cpp" - VSCode build

### Development
- `ssh dev@localhost -p 2222` - SSH connection
- VSCode Remote SSH - Full IDE experience

## 🎯 Next Steps

1. **Connect via VSCode**: Use Remote SSH to connect to the container
2. **Build the project**: Run the build script or use VSCode tasks
3. **Test functionality**: Run the test script with sample data
4. **Start developing**: Modify the C++ code and test changes

## 📞 Support

If you encounter any issues:
1. Check the troubleshooting section above
2. View container logs: `docker-compose logs -f`
3. Verify all dependencies are installed: `/workspace/test_env.sh`
4. Check the build output for specific error messages
