# 🚀 Quick Start Guide - C++ Development Container

## One-Command Setup

```bash
cd dev-container
./setup_all.sh
./start_dev.sh
```

## 🔗 Connect via VSCode

1. **Install Extension**: "Remote - SSH" in VSCode
2. **Connect**: `Ctrl+Shift+P` → "Remote-SSH: Connect to Host" → "shoe-matcher-dev"
3. **Password**: `devcontainer`

## 🛠️ Build & Test

```bash
# Inside container or VSCode terminal
/workspace/project/dev-container/build_cpp.sh
/workspace/project/dev-container/test_build.sh
```

## 📋 What's Included

✅ **Ubuntu 22.04** with China mirrors  
✅ **C++17** development tools (GCC 11, CMake)  
✅ **All dependencies**: Eigen3, nlohmann-json, Open3D, OpenNURBS  
✅ **SSH server** for VSCode remote development  
✅ **VSCode configuration** with debugging support  
✅ **Build scripts** and test automation  

## 🌏 China Optimized

- **APT**: Aliyun mirrors
- **Docker**: China-optimized images  
- **Python**: Tsinghua PyPI mirror
- **Git**: Optional Gitee mirror

## 🔧 Proxy Support

```bash
export HTTP_PROXY=http://localhost:7890
export HTTPS_PROXY=http://localhost:7890
./start_dev.sh
```

## 📁 File Structure

```
dev-container/
├── setup_all.sh          # Complete setup
├── start_dev.sh          # Start container
├── build_cpp.sh          # Build C++ project
├── test_build.sh         # Test build
├── Dockerfile            # Container definition
├── docker-compose.yml    # Container orchestration
└── .vscode/              # VSCode configuration
```

## 🎯 Ready to Code!

Your C++ development environment is ready with all dependencies installed and optimized for China. Start coding! 🎉
