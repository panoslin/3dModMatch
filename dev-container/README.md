# Shoe Last Matcher - Docker Development Environment

## 🚀 Quick Start

### 1. Build the Docker Image
```bash
cd dev-container
chmod +x build.sh run.sh
./build.sh
```

### 2. Start the Container
```bash
./run.sh
```

### 3. Connect to the Container

#### Option A: SSH Connection
```bash
ssh -p 2222 dev@localhost
# Password: devcontainer
```

#### Option B: VSCode Remote-SSH
1. Install "Remote - SSH" extension in VSCode
2. Add SSH host: `ssh dev@localhost -p 2222`
3. Connect and open `/workspace/project`

#### Option C: Direct Docker Exec
```bash
docker exec -it shoe-matcher-dev bash
```

## 📦 What's Included

### Core Components
- **Ubuntu 22.04 LTS** base image
- **Open3D 0.18.0** (built from source with Clang 12)
- **Python 3.10** with scientific computing stack
- **C++ Development**: GCC 11, Clang 12, CMake, Ninja
- **Shoe Last Matcher**: Full project with C++ extensions

### Python Packages
- NumPy, SciPy, Matplotlib
- Trimesh (3D mesh processing)
- Rhino3dm (3DM file support)
- Plotly (interactive visualization)
- scikit-learn (machine learning)
- Jupyter (notebooks)

### Build Tools
- CMake 3.22+
- Ninja build system
- scikit-build-core
- pybind11

## 🛠️ Building the C++ Extension

Inside the container:
```bash
cd /workspace/project/hybrid
pip3 install -v .

# Test the build
LD_PRELOAD=/usr/local/lib/libOpen3D.so python3 -c "import cppcore; print('Success!')"
```

Or use the convenience script:
```bash
/workspace/build_extension.sh
```

## 🎯 Running the Shoe Last Matcher

### Basic Usage
```bash
cd /workspace/project
LD_PRELOAD=/usr/local/lib/libOpen3D.so python3 hybrid/python/hybrid_matcher_optimized.py \
  --target models/36小.3dm \
  --candidates candidates/ \
  --clearance 2.0 \
  --export-report output/report.json
```

### With All Optimizations
```bash
LD_PRELOAD=/usr/local/lib/libOpen3D.so python3 hybrid/python/hybrid_matcher_optimized.py \
  --target candidates/B004小.3dm \
  --candidates candidates/ \
  --clearance 2.0 \
  --enable-scaling \
  --enable-multi-start \
  --threshold p15 \
  --max-scale 1.03 \
  --export-report output/optimized_report.json \
  --export-ply-dir output/optimized_ply
```

## 📊 Testing the Environment

```bash
# Run the test script
/workspace/test_env.sh

# Expected output:
# ✓ NumPy 1.24.3
# ✓ Trimesh 4.0.8
# ✓ Open3D 0.18.0
# ✓ All dependencies installed
```

## 🐳 Docker Commands

### Build Options
```bash
# Fresh build (remove cache)
./build.sh --fresh --no-cache

# Regular build with cache
./build.sh
```

### Run Options
```bash
# Start detached (background)
./run.sh

# Start with Jupyter notebook
./run.sh --jupyter

# Start attached (see output)
./run.sh --attach

# Follow logs
./run.sh --logs
```

### Container Management
```bash
# Stop container
docker-compose down

# View logs
docker logs shoe-matcher-dev

# Remove all data
docker-compose down -v

# Shell into running container
docker exec -it shoe-matcher-dev bash
```

## 🔧 Troubleshooting

### Open3D Import Error
```bash
# Always use LD_PRELOAD when running Python scripts that use cppcore
LD_PRELOAD=/usr/local/lib/libOpen3D.so python3 your_script.py
```

### Build Errors
```bash
# Clean build artifacts
rm -rf /workspace/build/*
cd /workspace/project/hybrid
pip3 uninstall shoe-last-hybrid
pip3 install -v .
```

### Permission Issues
```bash
# Fix ownership (run as root)
sudo chown -R dev:dev /workspace/project
```

## 📁 Directory Structure

```
/workspace/project/
├── hybrid/
│   ├── cpp/           # C++ source files
│   │   └── bindings.cpp
│   ├── python/        # Python modules
│   │   ├── hybrid_matcher.py
│   │   ├── hybrid_matcher_enhanced.py
│   │   ├── hybrid_matcher_production.py
│   │   └── hybrid_matcher_optimized.py
│   ├── CMakeLists.txt
│   └── pyproject.toml
├── models/            # Target shoe lasts
├── candidates/        # Candidate blanks
├── output/           # Results and exports
└── dev-container/    # Docker configuration
```

## 🌐 Network Ports

- **2222**: SSH server
- **8888**: Jupyter notebook (main service)
- **8889**: Jupyter notebook (optional service)
- **8050**: Dash/Plotly web apps

## 💡 Tips

1. **Use tmux/screen** for long-running processes
2. **Mount additional data** by modifying docker-compose.yml volumes
3. **Adjust resource limits** in docker-compose.yml based on your system
4. **Enable GUI support** by setting DISPLAY environment variable

## 📝 Notes

- The container runs as user `dev` (not root) for security
- China mirrors are configured for faster package downloads
- Open3D is compiled with Clang 12 for better compatibility
- The LD_PRELOAD workaround is needed due to TLS issues with Open3D

## 🤝 Contributing

To modify the environment:
1. Edit `Dockerfile` for system changes
2. Edit `docker-compose.yml` for service configuration
3. Rebuild with `./build.sh --fresh`
4. Test changes thoroughly before committing