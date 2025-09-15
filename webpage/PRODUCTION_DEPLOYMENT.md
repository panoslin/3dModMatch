# 🚀 生产环境一键部署指南

## 📋 快速开始

### 一条命令启动所有服务

```bash
cd /root/3dModMatch/webpage
./start.sh
```

**就这么简单！** 🎉

## 🔧 详细部署步骤

### 1. 环境准备

确保您的系统已安装：
- Docker 20.10+
- docker-compose 1.29+

### 2. 配置环境变量

编辑 `.env` 文件（自动生成）：

```bash
# 基本配置
DEBUG=False
SECRET_KEY=your-super-secret-production-key
ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.com

# 数据库配置
DB_PASSWORD=your-secure-password

# 端口配置
WEB_PORT=8000
HTTP_PORT=80
HTTPS_PORT=443

# 性能配置
CELERY_CONCURRENCY=4
MAX_CONCURRENT_TASKS=3
```

### 3. 一键启动

```bash
./start.sh
```

这个脚本会自动：
1. ✅ 检查并构建Hybrid匹配器镜像
2. ✅ 创建环境变量文件
3. ✅ 构建Web应用镜像  
4. ✅ 启动所有服务（数据库、Redis、匹配器）
5. ✅ 运行数据库迁移
6. ✅ 初始化测试数据
7. ✅ 启动Web和Celery服务
8. ✅ 验证系统健康状态

## 🐳 服务架构

### 容器列表
```
shoe_matcher_db       # PostgreSQL数据库
shoe_matcher_redis    # Redis缓存/队列
shoe_matcher_hybrid   # Hybrid匹配服务
shoe_matcher_web      # Django Web应用
shoe_matcher_celery   # Celery异步任务
```

### 网络配置
- **网络名**: shoe_matcher_network
- **子网**: 172.30.0.0/16
- **Web端口**: 8000 (可配置)

## 📊 系统管理

### 查看服务状态
```bash
docker-compose ps
```

### 查看日志
```bash
# 所有服务日志
docker-compose logs -f

# 特定服务日志
docker-compose logs -f web
docker-compose logs -f celery
docker-compose logs -f matcher
```

### 重启服务
```bash
# 重启所有服务
docker-compose restart

# 重启特定服务
docker-compose restart web
docker-compose restart celery
```

### 停止系统
```bash
# 停止服务
docker-compose down

# 停止并删除数据
docker-compose down -v
```

## 🧪 功能验证

### API健康检查
```bash
curl http://localhost:8000/api/health/
```

### 完整功能测试
```bash
python3 test_matching_simple.py
```

### Web界面测试
访问: http://localhost:8000
- 用户名: `admin`
- 密码: `admin123`

## 📊 测试数据

系统会自动导入：
- **粗胚文件**: 15个 (从 `../candidates/` 目录)
- **鞋模文件**: 2个 (从 `../models/` 目录，包括34鞋模.3dm)
- **分类系统**: 4个测试分类

## 🔧 高级配置

### 性能调优

编辑 `.env` 文件：

```env
# Celery配置
CELERY_CONCURRENCY=8        # Worker并发数
CELERY_MAX_CPUS=6          # 最大CPU限制
CELERY_MAX_MEMORY=6G       # 最大内存限制

# 匹配器配置
MATCHER_OMP_THREADS=6      # OpenMP线程数
MATCHER_MAX_CPUS=12        # 最大CPU限制
MATCHER_MAX_MEMORY=12G     # 最大内存限制

# 系统配置
MAX_CONCURRENT_TASKS=5     # 最大并发匹配任务
MAX_UPLOAD_SIZE=209715200  # 最大上传大小(200MB)
```

### 启用Nginx反向代理

```bash
# 启动包含Nginx的完整服务
docker-compose --profile nginx up -d
```

### 数据库备份

```bash
# 备份数据库
docker-compose exec db pg_dump -U postgres shoe_matcher > backup.sql

# 恢复数据库
docker-compose exec -T db psql -U postgres shoe_matcher < backup.sql
```

## 🚨 故障排除

### 常见问题

**问题1**: 服务启动失败
```bash
# 查看详细日志
docker-compose logs [service_name]

# 重新构建
docker-compose build --no-cache
```

**问题2**: 匹配功能不工作
```bash
# 检查Hybrid容器
docker logs shoe_matcher_hybrid

# 检查Celery任务
docker-compose logs celery
```

**问题3**: 数据库连接问题
```bash
# 检查数据库状态
docker-compose exec db pg_isready -U postgres

# 重启数据库
docker-compose restart db
```

### 完全重置

```bash
# 停止并清理所有数据
docker-compose down -v

# 清理Docker资源
docker system prune -f

# 重新启动
./start.sh
```

## 🎯 生产环境建议

### 安全配置
1. 修改默认密码
2. 启用HTTPS
3. 配置防火墙
4. 定期备份数据

### 监控配置
1. 设置日志轮转
2. 监控资源使用
3. 配置告警系统
4. 定期健康检查

### 性能优化
1. 根据硬件调整并发数
2. 配置适当的资源限制
3. 启用Redis持久化
4. 优化数据库配置

---

## 🎊 总结

现在您只需要运行一条命令就能启动完整的3D鞋模智能匹配系统：

```bash
./start.sh
```

所有服务都会自动启动，包括：
- 数据库和缓存
- Web应用和API
- 异步任务处理
- 3D匹配算法服务

**系统完全就绪，立即可用！** ✨
