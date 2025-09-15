# 3D鞋模智能匹配系统 - Web应用

## 项目概述

这是一个基于Django的SSR网页应用程序，用于包装和管理3D鞋模智能匹配功能。系统集成了现有的hybrid匹配算法，提供友好的Web界面进行鞋模与粗胚的智能匹配。

## 功能特点

- 🔄 **智能匹配**: 自动匹配鞋模与粗胚，支持多种匹配标准
- 📁 **文件管理**: 支持3DM格式文件的上传和管理
- 🏷️ **分类管理**: 灵活的粗胚分类系统
- 📊 **结果分析**: 详细的匹配报告和可视化
- 📝 **历史记录**: 完整的匹配历史追踪
- 🎨 **现代界面**: 基于Bootstrap 5的响应式界面

## 技术架构

### 后端技术栈
- **Django 4.2** - Web框架
- **Django REST Framework** - API框架
- **PostgreSQL** - 数据库
- **Redis** - 缓存和消息队列
- **Celery** - 异步任务处理

### 前端技术栈
- **Bootstrap 5** - UI框架
- **jQuery** - JavaScript库
- **Plotly.js** - 3D可视化
- **Font Awesome** - 图标库

### 3D处理
- **Open3D 0.19** - 3D几何处理
- **C++17核心模块** - 高性能匹配算法
- **enhanced_3dm_renderer** - 3D预览生成

## 项目结构

```
webpage/
├── doc/                          # 项目文档
│   ├── architecture.md          # 系统架构文档
│   ├── api_design.md            # API设计文档
│   ├── deployment.md            # 部署文档
│   └── user_guide.md            # 用户指南
└── shoe_matcher_web/            # Django项目
    ├── config/                  # 项目配置
    ├── apps/                    # Django应用
    │   ├── core/               # 核心功能
    │   ├── blanks/             # 粗胚管理
    │   ├── shoes/              # 鞋模管理
    │   ├── matching/           # 匹配功能
    │   └── visualization/      # 3D可视化
    ├── templates/              # 模板文件
    ├── static/                 # 静态文件
    └── media/                  # 媒体文件
```

## 快速开始

### 开发环境

1. **创建虚拟环境**
```bash
cd webpage
python3.10 -m venv venv
source venv/bin/activate
```

2. **安装依赖**
```bash
cd shoe_matcher_web
pip install -r requirements.txt
```

3. **配置数据库**
```bash
python manage.py makemigrations
python manage.py migrate
```

4. **创建超级用户**
```bash
python manage.py createsuperuser
```

5. **启动开发服务器**
```bash
DJANGO_SETTINGS_MODULE=config.settings.development python manage.py runserver
```

### 生产环境

1. **使用Docker Compose**
```bash
cd shoe_matcher_web
cp env.example .env
# 编辑.env文件配置生产参数
docker-compose up -d
```

2. **初始化数据库**
```bash
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
```

## 主要界面

### 匹配页面 (`/`)
- 鞋模文件上传
- 粗胚分类选择
- 匹配参数配置
- 实时匹配状态
- 结果展示和分析

### 历史记录页面 (`/history/`)
- 匹配历史查看
- 结果筛选和搜索
- 详细报告下载

### Modal组件
- **鞋模上传Modal**: 文件上传和3D预览
- **粗胚管理Modal**: 分类管理和文件管理
- **匹配结果Modal**: 详细结果和热图显示
- **3D预览Modal**: 交互式3D模型查看

## API接口

### RESTful API
- `GET/POST /api/blanks/` - 粗胚管理
- `GET/POST /api/shoes/` - 鞋模管理
- `POST /api/matching/start/` - 开始匹配
- `GET /api/matching/{task_id}/status/` - 匹配状态
- `GET /api/matching/{task_id}/result/` - 匹配结果

### 文件格式支持
- **输入**: 3DM格式 (Rhino 3D)
- **输出**: JSON报告, PLY模型, HTML热图

## 匹配算法

### 核心指标
- **覆盖率**: 鞋模被粗胚包含的百分比
- **体积比**: 粗胚与鞋模的体积比值
- **间隙分布**: P15, P10等百分位间隙值
- **Chamfer距离**: 几何相似度度量

### 通过标准
- **严格标准**: 最小间隙 ≥ 2.0mm
- **P15标准**: 85%点间隙 ≥ 2.0mm (推荐)
- **P10标准**: 90%点间隙 ≥ 2.0mm
- **P20标准**: 80%点间隙 ≥ 2.0mm

## 部署配置

### 环境变量
```env
DEBUG=False
SECRET_KEY=your-secret-key
DB_NAME=shoe_matcher
DB_USER=postgres
DB_PASSWORD=your-password
REDIS_URL=redis://redis:6379/0
```

### Docker服务
- **web**: Django应用服务器
- **db**: PostgreSQL数据库
- **redis**: Redis缓存
- **celery**: 异步任务处理
- **matcher**: 3D匹配算法容器
- **nginx**: 反向代理服务器

## 监控和日志

### 健康检查
- `/api/health/` - 系统健康状态
- Docker容器健康检查
- 数据库连接监控

### 日志记录
- Django应用日志
- 匹配任务日志
- 系统错误日志

## 开发指南

### 代码结构
- **models.py**: 数据模型定义
- **views.py**: 视图逻辑
- **serializers.py**: API序列化器
- **tasks.py**: Celery异步任务
- **urls.py**: URL路由配置

### 前端开发
- **templates/**: Django模板
- **static/css/**: 样式文件
- **static/js/**: JavaScript文件
- 使用Bootstrap 5组件
- 集成Plotly.js进行3D可视化

## 许可证

本项目采用MIT许可证。详见LICENSE文件。

## 支持

如有问题或建议，请联系开发团队或提交Issue。

---

**版本**: v1.0.0  
**更新时间**: 2025年1月15日  
**Python版本**: 3.10+  
**Django版本**: 4.2+


