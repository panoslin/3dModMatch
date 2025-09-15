# 3D鞋模智能匹配系统

基于Django的Web应用程序，集成高性能C++17匹配算法，提供专业的3D鞋模与粗胚智能匹配服务。

## 🚀 一键启动

```bash
cd /root/3dModMatch/webpage
docker-compose up -d
```

## 🌐 访问系统

- **主页**: http://localhost:8000
- **管理后台**: http://localhost:8000/admin (admin/admin123)

## 📊 系统功能

- **智能匹配**: 高精度3D几何匹配算法
- **实时分析**: 覆盖率、体积比、P15间隙分析
- **文件管理**: 3DM格式文件上传和分类管理
- **结果可视化**: 交互式3D预览和匹配热图
- **历史记录**: 完整的匹配历史追踪

## 🔧 系统管理

```bash
# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 重启服务
docker-compose restart

# 停止系统
docker-compose down
```

## ⚙️ 配置

编辑 `.env` 文件来自定义系统配置：

```env
WEB_PORT=8000
DB_PASSWORD=your-secure-password
CELERY_CONCURRENCY=4
MAX_CONCURRENT_TASKS=3
```

## 🏗️ 技术架构

- **后端**: Django 4.2 + Django REST Framework
- **前端**: Bootstrap 5 + jQuery + Plotly.js
- **数据库**: PostgreSQL 13
- **缓存**: Redis 7
- **异步任务**: Celery
- **3D处理**: Open3D + C++17核心
- **容器化**: Docker + Docker Compose

## 📁 项目结构

```
webpage/
├── docker-compose.yml     # Docker Compose配置
├── .env                   # 环境变量
├── Dockerfile             # Web应用镜像
├── entrypoint.sh          # 容器入口脚本
└── shoe_matcher_web/      # Django应用
    ├── config/            # 项目配置
    ├── apps/              # 应用模块
    ├── templates/         # 模板文件
    ├── static/           # 静态文件
    └── utils/            # 工具模块
```

---

**版本**: v1.0.0  
**Python**: 3.10+  
**Docker镜像**: panoslin/shoe_matcher_hybrid:latest
