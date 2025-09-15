# 🚀 3D鞋模智能匹配系统 - 最终使用指南

## 🎯 一键启动 (标准Docker Compose)

```bash
cd /root/3dModMatch/webpage
docker-compose up -d
```

**就这么简单！** 系统会自动：
- 从Docker Hub拉取hybrid匹配器镜像
- 启动所有必需服务
- 初始化数据库和测试数据
- 配置服务依赖关系

## 📊 系统验证

### 检查服务状态
```bash
docker-compose ps
```

期望输出：
```
NAME                  STATUS
shoe_matcher_web      Up (healthy)
shoe_matcher_celery   Up (healthy)  
shoe_matcher_hybrid   Up (healthy)
shoe_matcher_db       Up (healthy)
shoe_matcher_redis    Up (healthy)
```

### 测试API
```bash
curl http://localhost:8000/api/health/
```

期望输出：
```json
{"success":true,"data":{"status":"healthy","database":"connected"}}
```

## 🌐 访问系统

- **主页**: http://localhost:8000
- **管理后台**: http://localhost:8000/admin
- **用户名**: admin
- **密码**: admin123

## 📝 常用命令

```bash
# 启动系统
docker-compose up -d

# 查看状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 重启服务
docker-compose restart

# 停止系统
docker-compose down

# 完全清理
docker-compose down -v
```

## 🔧 配置选项

编辑 `.env` 文件来自定义配置：

```env
# 端口配置
WEB_PORT=8000

# 数据库配置
DB_PASSWORD=your-secure-password

# 性能配置
CELERY_CONCURRENCY=4
MAX_CONCURRENT_TASKS=3
```

## 🎉 系统特色

- **🔄 智能匹配**: 高精度3D几何匹配算法
- **📊 实时分析**: 覆盖率、体积比、间隙分析
- **🎨 现代界面**: Bootstrap 5响应式设计
- **⚡ 异步处理**: Celery后台任务队列
- **🐳 容器化**: 标准Docker Compose部署
- **☁️ 云镜像**: Docker Hub预构建镜像

---

## 🚀 立即开始

```bash
docker-compose up -d
```

**您的3D鞋模智能匹配系统现在完全就绪！** ✨
