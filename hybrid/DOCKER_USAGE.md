# Hybrid Shoe Last Matcher - Docker 使用指南

## 🐳 Docker 镜像信息

- **镜像名称**: `hybrid-shoe-matcher:latest`
- **基础镜像**: Ubuntu 22.04 LTS
- **Python版本**: 3.10.12
- **Open3D版本**: 0.19.0
- **主要功能**: 运行 `hybrid_matcher_multiprocess.py` 进行3D鞋模智能匹配

## 🚀 快速开始

### 1. 构建镜像
```bash
cd /root/3dModMatch/hybrid
docker build -t hybrid-shoe-matcher:latest .
```

### 2. 运行容器
```bash
# 查看帮助信息
docker run --rm hybrid-shoe-matcher:latest python3 python/hybrid_matcher_multiprocess.py --help

# 运行匹配任务
docker run --rm -v /path/to/models:/app/models:ro -v /path/to/candidates:/app/candidates:ro -v /path/to/output:/app/output hybrid-shoe-matcher:latest python3 python/hybrid_matcher_multiprocess.py --target /app/models/target.3dm --candidates /app/candidates --clearance 2.0
```

### 3. 使用 docker-compose
```bash
# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

## 📁 目录结构

容器内的目录结构：
```
/app/
├── python/                    # Python脚本目录
│   ├── hybrid_matcher_multiprocess.py
│   ├── hybrid_matcher_optimized.py
│   └── ...
├── cpp/                       # C++源码目录
├── build/                     # 构建目录
├── models/                    # 目标模型目录 (挂载)
├── candidates/                # 候选模型目录 (挂载)
├── output/                    # 输出结果目录 (挂载)
├── test_env.sh               # 环境测试脚本
└── entrypoint.sh             # 容器入口脚本
```

## 🔧 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `LD_LIBRARY_PATH` | `/usr/local/lib:$LD_LIBRARY_PATH` | 库文件路径 |
| `LD_PRELOAD` | `/usr/local/lib/libOpen3D.so` | Open3D预加载库 |
| `PYTHONPATH` | `/app/python:$PYTHONPATH` | Python模块路径 |
| `OMP_NUM_THREADS` | `1` | OpenMP线程数 |

## 📊 使用示例

### 基本匹配
```bash
docker run --rm \
  -v /host/models:/app/models:ro \
  -v /host/candidates:/app/candidates:ro \
  -v /host/output:/app/output \
  hybrid-shoe-matcher:latest \
  python3 python/hybrid_matcher_multiprocess.py \
  --target /app/models/target.3dm \
  --candidates /app/candidates \
  --clearance 2.0 \
  --processes 4
```

### 高级匹配（启用所有功能）
```bash
docker run --rm \
  -v /host/models:/app/models:ro \
  -v /host/candidates:/app/candidates:ro \
  -v /host/output:/app/output \
  hybrid-shoe-matcher:latest \
  python3 python/hybrid_matcher_multiprocess.py \
  --target /app/models/target.3dm \
  --candidates /app/candidates \
  --clearance 2.0 \
  --enable-scaling \
  --enable-multi-start \
  --threshold p15 \
  --processes 8 \
  --export-report /app/output/report.json \
  --export-ply-dir /app/output/passing_candidates \
  --export-topk 10
```

### 批量处理
```bash
# 处理多个目标
for target in /host/models/*.3dm; do
  docker run --rm \
    -v /host/models:/app/models:ro \
    -v /host/candidates:/app/candidates:ro \
    -v /host/output:/app/output \
    hybrid-shoe-matcher:latest \
    python3 python/hybrid_matcher_multiprocess.py \
    --target "$target" \
    --candidates /app/candidates \
    --clearance 2.0 \
    --export-report "/app/output/$(basename "$target" .3dm)_report.json"
done
```

## 🧪 测试和验证

### 运行环境测试
```bash
docker run --rm hybrid-shoe-matcher:latest /app/test_env.sh
```

### 运行完整测试套件
```bash
python3 test_docker_container.py
```

## 🔍 故障排除

### 常见问题

1. **Open3D库加载失败**
   ```bash
   # 检查LD_PRELOAD设置
   docker run --rm hybrid-shoe-matcher:latest env | grep LD_PRELOAD
   ```

2. **Python模块导入失败**
   ```bash
   # 检查PYTHONPATH设置
   docker run --rm hybrid-shoe-matcher:latest env | grep PYTHONPATH
   ```

3. **C++模块无法加载**
   ```bash
   # 测试cppcore模块
   docker run --rm hybrid-shoe-matcher:latest python3 -c "import cppcore; print('OK')"
   ```

### 调试模式
```bash
# 进入容器进行调试
docker run -it --rm hybrid-shoe-matcher:latest /bin/bash

# 在容器内运行测试
python3 /app/test_env.sh
```

## 📈 性能优化

### 资源限制
```bash
# 限制CPU和内存使用
docker run --rm \
  --cpus="4.0" \
  --memory="8g" \
  --memory-swap="8g" \
  hybrid-shoe-matcher:latest \
  python3 python/hybrid_matcher_multiprocess.py \
  --target /app/models/target.3dm \
  --candidates /app/candidates \
  --clearance 2.0 \
  --processes 4
```

### 并行处理
```bash
# 使用所有可用CPU核心
docker run --rm \
  --cpus="$(nproc)" \
  hybrid-shoe-matcher:latest \
  python3 python/hybrid_matcher_multiprocess.py \
  --target /app/models/target.3dm \
  --candidates /app/candidates \
  --clearance 2.0 \
  --processes $(nproc)
```

## 🔒 安全注意事项

1. **只读挂载**: 模型和候选文件目录应使用只读挂载 (`:ro`)
2. **输出目录**: 确保输出目录有适当的写入权限
3. **资源限制**: 在生产环境中设置适当的CPU和内存限制
4. **网络隔离**: 如不需要网络访问，使用 `--network none`

## 📝 日志和监控

### 查看容器日志
```bash
# 实时查看日志
docker run --rm hybrid-shoe-matcher:latest python3 python/hybrid_matcher_multiprocess.py [参数] 2>&1 | tee output.log

# 使用docker-compose查看日志
docker-compose logs -f hybrid-matcher
```

### 性能监控
```bash
# 监控容器资源使用
docker stats hybrid-shoe-matcher

# 查看详细资源使用
docker run --rm --cpus="4.0" --memory="8g" hybrid-shoe-matcher:latest python3 python/hybrid_matcher_multiprocess.py [参数]
```

## 🎯 生产环境部署

### 使用docker-compose
```yaml
version: '3.8'
services:
  hybrid-matcher:
    image: hybrid-shoe-matcher:latest
    container_name: hybrid-shoe-matcher
    volumes:
      - ./models:/app/models:ro
      - ./candidates:/app/candidates:ro
      - ./output:/app/output
    environment:
      - OMP_NUM_THREADS=4
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 8G
        reservations:
          cpus: '2.0'
          memory: 4G
    restart: unless-stopped
```

### 健康检查
```bash
# 添加健康检查
docker run --rm \
  --health-cmd="python3 -c 'import cppcore; import open3d; print(\"OK\")'" \
  --health-interval=30s \
  --health-timeout=10s \
  --health-retries=3 \
  hybrid-shoe-matcher:latest
```

---

## 📞 支持

如有问题，请检查：
1. Docker镜像是否正确构建
2. 挂载的目录路径是否正确
3. 输入文件格式是否支持
4. 系统资源是否充足

更多信息请参考项目文档或联系开发团队。
