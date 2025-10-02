# 3D鞋模智能匹配系统 (3dModMatch)

<div align="center">

**基于C++17高性能算法和Django Web框架的专业3D鞋模与粗胚智能匹配系统**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-4.2-green.svg)](https://www.djangoproject.com/)
[![C++](https://img.shields.io/badge/C++-17-orange.svg)](https://isocpp.org/)
[![Docker](https://img.shields.io/badge/Docker-ready-blue.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## 📖 项目简介

3dModMatch 是一个专为制鞋行业设计的智能匹配系统，用于自动化匹配鞋模(Shoe Last)与粗胚(Blank)，通过高精度3D几何分析算法，快速判断某个粗胚是否适合用来制作特定的鞋模，显著提升生产效率并降低人工判断的错误率。

### 🎯 核心价值

- 🚀 **高性能**: C++17核心算法 + Open3D，支持多进程并行批量处理
- 🎨 **智能配准**: FPFH特征提取 + RANSAC全局配准 + ICP精细对齐
- 📊 **精确分析**: 多维度匹配指标（P15间隙、覆盖率、体积比、Chamfer距离）
- 🔄 **自适应优化**: 支持自动镜像检测和自适应缩放（最大1.03倍）
- 🖥️ **友好界面**: 现代化Web界面，支持Plotly和Three.js双渲染引擎
- 🔍 **可视化**: 交互式3D预览、LOD多精度渲染和间隙热图
- 🐳 **易部署**: 完整Docker容器化方案，一键启动

---

## ✨ 主要功能

### 🔧 核心匹配功能

- ✅ **智能配准对齐**
  - FPFH特征提取 + RANSAC全局配准
  - Point-to-Plane ICP局部优化
  - 自动镜像检测（左右脚容错）
  - 多起点对齐优化

- ✅ **多维度分析**
  - **Chamfer距离**: 几何相似度
  - **间隙检测**: P01/P05/P10/P15/P20/P50百分位数
  - **覆盖率分析**: 粗胚包覆鞋模的比例
  - **体积比**: 粗胚与鞋模的体积对比
  - **最小间隙**: 最危险的薄弱点位置

- ✅ **通过标准**
  - **严格标准**: 最小间隙≥阈值
  - **P10标准**: 90%顶点满足间隙要求
  - **P15标准**: 85%顶点满足间隙要求（推荐）
  - **P20标准**: 80%顶点满足间隙要求

### 🌐 Web系统功能

- 📤 **文件管理**
  - 支持3DM/STL格式上传
  - 自动STL转3DM（使用cppcore C++模块）
  - 几何特征自动提取（体积、边界框、面数）
  
- 🗂️ **分类管理**
  - 粗胚分层分类组织
  - 支持父子分类关系
  - 批量导入和管理
  
- ⚡ **异步处理**
  - Celery后台任务队列
  - 实时进度更新
  - 最多支持5个并发任务
  
- 📊 **结果可视化** 
  - 双渲染引擎（Plotly传统模式 / Three.js优化模式）
  - LOD多精度加载（preview/detail/full）
  - 间隙热图生成
  - 匹配结果详情表格
  
- 📜 **历史记录**
  - 完整的匹配任务追踪
  - 参数和结果永久存储
  - 支持结果对比和导出
  
- 🔐 **后台管理**
  - Django Admin管理界面
  - 文件和分类管理
  - 任务监控

---

## 🏗️ 技术架构

### 技术栈

| 层次 | 技术 |
|------|------|
| **前端** | Bootstrap 5, jQuery, Plotly.js |
| **后端** | Django 4.2, Django REST Framework |
| **数据库** | PostgreSQL 13 |
| **缓存/队列** | Redis 7 |
| **异步任务** | Celery |
| **3D处理** | Open3D, C++17, pybind11 |
| **科学计算** | Eigen3, NumPy |
| **3D文件** | rhino3dm, trimesh |
| **容器化** | Docker, Docker Compose |

### 架构图

```
┌──────────────────────────────────────────────────────────────────┐
│                         Web Browser                              │
│              (Bootstrap 5 + jQuery + Plotly/Three.js)            │
└───────────────────────────────┬──────────────────────────────────┘
                                │ HTTP/REST API
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                      Django Web Container                         │
│   ┌──────────────────────────────────────────────────────────┐   │
│   │              Django Apps (config.wsgi)                   │   │
│   │  ┌─────┬──────┬───────┬──────────┬──────────┬──────────┐ │   │
│   │  │Core │ API  │Shoes  │ Blanks   │Matching  │Visual.   │ │   │
│   │  │     │      │(鞋模)  │ (粗胚)    │ (匹配)   │(可视化)   │ │   │
│   │  └─────┴──────┴───────┴──────────┴──────────┴──────────┘ │   │
│   └──────────────────────────────────────────────────────────┘   │
│   内置: cppcore.so (C++模块) + hybrid_matcher.py                  │
└──────┬──────────────────────────────────────────┬────────────────┘
       │                                          │
       │ psycopg2                                 │ redis-py
       ▼                                          ▼
┌──────────────┐                         ┌──────────────┐
│ PostgreSQL   │                         │    Redis     │
│  (数据库)     │                         │ (队列/缓存)   │
└──────────────┘                         └──────┬───────┘
                                                │ Celery broker
                                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                     Celery Worker Container                       │
│   Celery进程监听任务队列 → 执行run_matching_task()                   │
└─────────────────────────────────┬────────────────────────────────┘
                                  │ subprocess.run(['docker', ...])
                                  ▼
┌──────────────────────────────────────────────────────────────────┐
│         临时Hybrid Matcher容器 (panoslin/shoe_matcher_hybrid)      │
│                                                                  │
│  python3 python/hybrid_matcher_multiprocess.py                   │
│    --target /app/target.3dm                                      │
│    --candidates /app/candidates/                                 │
│    --clearance 2.0 --threshold p15                               │
│    --processes 8                                                 │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  多进程并行处理                                         │     │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  │     │
│  │  │Process 1│  │Process 2│  │Process N│  │  ...    │  │     │
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └─────────┘  │     │
│  │       │            │            │                     │     │
│  │       └────────────┴────────────┘                     │     │
│  │                    │                                  │     │
│  │                    ▼                                  │     │
│  │      ┌───────────────────────────────┐               │     │
│  │      │  cppcore C++扩展模块(pybind11) │               │     │
│  │      │  - FPFH特征提取               │               │     │
│  │      │  - RANSAC + ICP配准           │               │     │
│  │      │  - 间隙计算(Open3D)           │               │     │
│  │      │  - Chamfer距离                │               │     │
│  │      └───────────────────────────────┘               │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  输出: /app/output/report.json + PLY文件                          │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🚀 快速开始

### 前置要求

- Docker 20.10+
- Docker Compose 2.0+
- 至少4GB可用内存
- 10GB可用磁盘空间

### 一键部署

```bash
# 克隆仓库
git clone <repository-url>
cd 3dModMatch/webpage

# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 访问系统

- **主页**: http://localhost:8000
- **管理后台**: http://localhost:8000/admin
  - 用户名: `admin`
  - 密码: `admin123`

### 停止服务

```bash
cd /root/3dModMatch/webpage
docker-compose down
```

---

## 📚 使用指南

### 1️⃣ 初始化系统

首次启动后，系统会自动：
- 运行数据库迁移
- 创建管理员账户（admin/admin123）
- 加载测试数据（如果存在）

### 2️⃣ 上传鞋模

1. 访问主页 http://localhost:8000
2. 点击页面上的"上传鞋模"按钮
3. 选择文件（支持.3dm、.stl）
4. 填写鞋模名称
5. 点击上传，系统会自动：
   - STL文件自动转换为3DM（通过cppcore C++模块）
   - 提取几何特征（体积、边界框、面数）
   - 生成3D预览

### 3️⃣ 管理粗胚库

**创建分类：**
1. 点击"粗胚管理"按钮
2. 点击"新建分类"
3. 输入分类名称（如：002系列、113系列）
4. 可选设置父分类（支持分层结构）

**上传粗胚：**
1. 在粗胚管理界面点击"上传粗胚"
2. 选择文件并指定分类
3. 系统自动处理和索引

### 4️⃣ 执行匹配

1. 在主页的"鞋模选择"区域选择目标鞋模
2. 在"粗胚分类"区域勾选要匹配的分类
3. 设置匹配参数：
   - **间隙要求**: 默认2.0mm
   - **通过标准**: 推荐P15标准
   - **自适应缩放**: 建议开启
   - **多起点对齐**: 建议开启
4. 点击"开始匹配"
5. 系统后台Celery异步处理，页面显示实时进度
6. 完成后自动显示结果表格

### 5️⃣ 查看结果

**结果表格包含：**
- ✅/❌ **通过状态**: 基于所选标准（P15等）
- 📏 **P15间隙**: 第15百分位间隙值（mm）
- 📊 **平均间隙**: 所有顶点的平均间隙
- 📏 **最小间隙**: 最危险点的间隙值
- 🎯 **覆盖率**: 鞋模被粗胚包覆的比例（%）
- 📦 **体积比**: 粗胚体积/鞋模体积
- 🔄 **缩放比例**: 实际使用的缩放倍数
- 🪞 **镜像**: 是否镜像处理

**操作：**
- 点击行可查看详细数据
- 点击"3D预览"查看对齐后的模型
- 点击"热图"查看间隙分布（如已生成）
- 结果自动保存到历史记录

### 6️⃣ 历史记录

访问 http://localhost:8000/history/ 可查看：
- 所有历史匹配任务
- 任务参数和结果摘要
- 重新查看详细结果

---

## 📁 项目结构

```
3dModMatch/
├── README.md                          # 本文档
├── requirements.txt                   # Python依赖
├── candidates/                        # 测试粗胚数据
├── models/                            # 测试鞋模数据
│
├── hybrid/                            # 匹配引擎核心
│   ├── CMakeLists.txt                # C++构建配置
│   ├── pyproject.toml                # Python包配置
│   ├── Dockerfile                    # Hybrid容器镜像
│   ├── docker-extract/               # 预编译的库文件
│   │   ├── libOpen3D.so*            # Open3D动态库
│   │   ├── libOpenNURBS.so          # OpenNURBS库
│   │   └── ...
│   ├── cpp/
│   │   └── bindings.cpp              # C++17核心算法 + pybind11绑定
│   ├── python/
│   │   ├── hybrid_matcher.py         # 单进程匹配脚本
│   │   ├── hybrid_matcher_multiprocess.py  # 多进程并行版本
│   │   └── heatmap_worker.py         # 热图生成工具
│   └── README.md                     # 匹配引擎文档
│
├── webpage/                           # Django Web应用
│   ├── docker-compose.yml            # 容器编排配置 ⭐
│   ├── Dockerfile                    # Web应用镜像
│   ├── entrypoint.sh                 # 容器入口脚本
│   ├── cppcore.cpython-310-*.so      # 预编译的C++模块
│   ├── hybrid_matcher.py             # 匹配脚本（复制自hybrid）
│   ├── shoe_matcher_web/             # Django项目根目录
│   │   ├── manage.py                # Django管理脚本
│   │   ├── init_docker.py           # Docker初始化脚本
│   │   ├── requirements.txt         # Python依赖
│   │   ├── config/                  # 项目配置
│   │   │   ├── __init__.py
│   │   │   ├── urls.py             # 主路由配置
│   │   │   ├── wsgi.py             # WSGI入口
│   │   │   ├── celery.py           # Celery配置
│   │   │   └── settings/           # 分环境配置
│   │   │       ├── base.py         # 基础配置
│   │   │       ├── development.py  # 开发环境
│   │   │       ├── docker.py       # Docker环境
│   │   │       └── production.py   # 生产环境
│   │   ├── apps/                    # Django应用模块
│   │   │   ├── core/               # 核心功能（主页、健康检查）
│   │   │   ├── api/                # API端点
│   │   │   ├── shoes/              # 鞋模管理
│   │   │   ├── blanks/             # 粗胚管理
│   │   │   ├── matching/           # 匹配功能
│   │   │   └── visualization/      # 3D可视化
│   │   ├── templates/              # HTML模板
│   │   │   ├── base.html           # 基础模板
│   │   │   ├── core/
│   │   │   │   ├── matching.html   # 匹配主页
│   │   │   │   └── history.html    # 历史记录页
│   │   │   └── components/         # 模态框组件
│   │   ├── static/                 # 静态资源
│   │   │   ├── css/
│   │   │   ├── js/
│   │   │   │   ├── transparent-overlay-viewer.js  # Three.js渲染器
│   │   │   │   └── ...
│   │   │   └── icons/
│   │   ├── utils/                  # 工具模块
│   │   │   ├── hybrid_integration.py  # Hybrid服务集成
│   │   │   ├── file_converter.py      # 文件转换工具
│   │   │   └── ...
│   │   └── media/                  # 用户上传文件（挂载）
│   │       ├── shoes/              # 鞋模文件
│   │       ├── blanks/             # 粗胚文件
│   │       └── heatmaps/           # 热图
│   ├── results/                     # 匹配结果（挂载）
│   ├── temp/                        # 临时文件（挂载）
│   ├── logs/                        # 日志文件（挂载）
│   └── doc/                         # 系统文档
│       ├── architecture.md         # 架构设计
│       ├── api_design.md           # API设计
│       └── ...
│
└── dev-container/                   # 开发容器环境
    ├── Dockerfile
    ├── docker-compose.yml
    └── README.md
```

**关键文件说明：**
- `docker-compose.yml`: 定义4个服务（db, redis, web, celery）
- `hybrid_integration.py`: 负责调用Docker容器执行匹配
- `matching/tasks.py`: Celery异步任务实现
- `matching/models.py`: MatchingTask数据模型

---

## ⚙️ 配置说明

### 环境变量

在 `webpage/.env` 文件中配置：

```env
# Web服务
WEB_PORT=8000
DEBUG=False
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.com

# 数据库
DB_NAME=shoe_matcher
DB_USER=postgres
DB_PASSWORD=your-secure-password
DB_HOST=db
DB_PORT=5432

# Redis
REDIS_URL=redis://redis:6379/0

# 匹配参数
DEFAULT_CLEARANCE=2.0            # 默认余量要求(mm)
MAX_CONCURRENT_TASKS=3           # 最大并发任务数
MAX_UPLOAD_SIZE=104857600        # 最大上传文件大小(100MB)

# Celery
CELERY_CONCURRENCY=4             # Worker并发数
CELERY_MAX_CPUS=4
CELERY_MAX_MEMORY=4G

# 匹配引擎
MATCHER_DOCKER_IMAGE=panoslin/shoe_matcher_hybrid:latest
MATCHER_OMP_THREADS=4
```

### 匹配算法参数

Web界面可调整参数：

```yaml
clearance: 2.0            # 间隙要求(mm)，默认2.0
threshold: p15            # 通过标准(min/p10/p15/p20)，默认p15
enable_scaling: true      # 启用自适应缩放，默认开启
max_scale: 1.03           # 最大缩放比例，默认1.03（即±3%）
enable_multi_start: true  # 启用多起点对齐，默认开启
processes: 8              # 并行进程数，默认8
export_topk: 3            # 导出前N个PLY文件，默认3
```

命令行高级参数（hybrid容器）：

```bash
--target <file>           # 目标鞋模文件
--candidates <dir>        # 候选粗胚目录
--clearance 2.0          # 间隙要求(mm)
--threshold p15          # 通过标准
--enable-scaling         # 启用自适应缩放
--max-scale 1.03         # 最大缩放比例
--enable-multi-start     # 启用多起点对齐
--processes 8            # 并行进程数
--export-report <file>   # 导出报告JSON
--export-ply-dir <dir>   # 导出对齐后的PLY文件
--export-topk 3          # 导出前N个结果
```

---

## 🔧 开发指南

### 本地开发环境

#### 1. 构建C++核心模块

```bash
cd hybrid

# 安装依赖
sudo apt-get install -y libopen3d-dev libeigen3-dev ninja-build

# 构建
./build_cpp.sh

# 或手动构建
mkdir -p build && cd build
cmake .. -GNinja
ninja
```

#### 2. 启动Django开发服务器

```bash
cd webpage/shoe_matcher_web

# 创建虚拟环境
python3.10 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 数据库迁移
python manage.py migrate

# 创建超级用户
python manage.py createsuperuser

# 启动开发服务器
python manage.py runserver 0.0.0.0:8000
```

#### 3. 启动Celery Worker

```bash
cd webpage/shoe_matcher_web
celery -A config worker -l info --pool=threads --concurrency=4
```

### 测试

```bash
# 测试C++模块构建
cd hybrid
./test_build.sh

# 测试匹配功能
cd /root/3dModMatch
./test_match.sh

# Django测试
cd webpage/shoe_matcher_web
python manage.py test
```

### 代码风格

- **Python**: PEP 8
- **C++**: Google C++ Style Guide
- **JavaScript**: Airbnb JavaScript Style Guide

---

## 🐳 Docker镜像和部署

### 使用的Docker镜像

项目使用3个Docker镜像：

1. **panoslin/3d-shoe-matcher-web:v1** - Django Web应用
   - 基于Ubuntu 22.04
   - 包含Django 4.2、Celery、PostgreSQL客户端
   - 内置cppcore.so C++扩展模块
   - 支持Docker socket访问

2. **panoslin/shoe_matcher_hybrid:latest** - Hybrid匹配引擎
   - 基于Ubuntu 22.04
   - 包含Open3D、OpenNURBS、Eigen3
   - C++17编译的cppcore模块
   - 多进程并行处理能力

3. **postgres:13** - PostgreSQL数据库

4. **redis:7-alpine** - Redis缓存和消息队列

### Docker Compose服务

```yaml
services:
  db:         # PostgreSQL数据库
  redis:      # Redis缓存/队列
  web:        # Django Web服务 (端口8000)
  celery:     # Celery异步任务处理器
```

**注意**: `matcher`服务已注释，实际通过`docker run`临时创建容器执行匹配。

### 构建自定义镜像

```bash
# 1. 构建Hybrid匹配引擎（如果修改了C++代码）
cd /root/3dModMatch/hybrid
docker build -t shoe_matcher_hybrid:custom .

# 2. 构建Web应用（如果修改了Django代码）
cd /root/3dModMatch/webpage
docker build -t shoe_matcher_web:custom .

# 3. 更新docker-compose.yml中的镜像名称
# 将 panoslin/xxx 改为 xxx:custom

# 4. 重启服务
docker-compose down
docker-compose up -d
```

---

## 📊 性能指标

### 匹配性能

基于典型鞋模（约5-10万顶点）和粗胚模型：

- **单个候选匹配**: 5-15秒（配准+间隙计算）
- **批量处理（8进程）**: 可达20-40个候选/分钟
- **内存占用**: 
  - 单个匹配: 500MB-1GB
  - 8进程并行: 4-8GB
- **CPU利用**: 多进程并行，充分利用多核CPU
- **磁盘IO**: 临时文件约100MB/任务

### 系统容量

- **并发匹配任务**: 默认5个（可通过`MAX_CONCURRENT_TASKS`调整）
- **单任务候选数**: 理论无限制，实测100+个候选无压力
- **文件上传限制**: 100MB/文件（可通过`MAX_UPLOAD_SIZE`调整）
- **数据库**: PostgreSQL，支持海量历史记录
- **历史记录**: 永久保存，包含完整参数和结果
- **文件存储**: 取决于磁盘空间，建议预留50GB+

### 性能优化建议

1. **增加并行进程**: 修改`--processes`参数（默认8）
2. **调整Celery并发**: 修改`CELERY_CONCURRENCY`环境变量
3. **使用SSD**: 显著提升临时文件读写速度
4. **增加内存**: 支持更多并发任务和更大模型

---

## 🔍 常见问题

### Q: 支持哪些3D文件格式？

A: 

**Web界面上传：**
- ✅ **原生支持**: `.3dm` (Rhino格式，推荐)
- ✅ **自动转换**: `.stl` → `.3dm`（通过cppcore C++模块自动转换）
- ❌ **暂不支持**: `.ply`, `.obj`, `.step`, `.iges` 等其他格式

**Hybrid引擎能力：**
- 底层C++引擎支持 `.3dm`, `.ply`, `.obj`, `.stl` 等格式
- Web界面暂未开放所有格式的上传，后续版本将逐步支持

**注意事项：**
- STL文件上传后会自动转换为3DM格式
- 3DM文件建议包含渲染网格（Render Mesh）
- 模型单位必须为毫米(mm)
- 文件大小限制：100MB

### Q: 匹配任务卡住不动怎么办？

A:
```bash
# 1. 检查任务状态
docker-compose logs celery -f

# 2. 检查是否有僵尸Docker容器
docker ps -a | grep shoe_matcher_hybrid

# 3. 清理僵尸容器
docker rm -f $(docker ps -aq --filter ancestor=panoslin/shoe_matcher_hybrid:latest)

# 4. 重启Celery Worker
docker-compose restart celery

# 5. 如需清空任务队列
docker-compose exec redis redis-cli FLUSHALL
```

### Q: 如何理解通过标准？

A: 系统提供4种通过标准：
- **严格标准(min)**: 最小间隙≥阈值（最严格，100%顶点满足）
- **P10标准**: 90%的顶点满足间隙要求（严格）
- **P15标准**: 85%的顶点满足间隙要求（**推荐**，平衡严格性和通过率）
- **P20标准**: 80%的顶点满足间隙要求（宽松）

例如：阈值2mm + P15标准 = 至少85%的鞋模表面点距离粗胚≥2mm

### Q: 什么是覆盖率(inside_ratio)？

A: 覆盖率表示鞋模有多少比例被粗胚完全包覆。
- **100%**: 完美包覆，鞋模所有部分都在粗胚内部
- **80-99%**: 良好包覆，大部分区域满足要求
- **<80%**: 包覆不足，可能有较大区域突出

### Q: 余量(clearance)2mm是什么意思？

A: 余量指粗胚表面到鞋模表面的最小距离，即加工预留空间：
- **2mm**: 标准加工余量，适用于常规鞋模
- **1.5mm**: 紧凑型粗胚，节省材料但加工难度增加
- **3mm**: 宽松余量，适用于复杂造型或精细加工

### Q: 自适应缩放是什么？

A: 自适应缩放允许粗胚在1.00-1.03倍范围内缩放以获得更好的匹配：
- **启用**: 粗胚可在±3%范围内自动调整大小
- **禁用**: 粗胚保持原始大小，不进行任何缩放
- **用途**: 补偿制造误差或尺码微调
- **显示**: 结果中的`scale_used`字段显示实际使用的缩放比例

### Q: 如何查看详细的匹配报告？

A: 
1. 在历史记录页面点击任务可查看摘要
2. 点击"查看详情"可看到每个候选的完整数据
3. 匹配报告JSON文件存储在`webpage/temp/match_xxx/output/report.json`
4. PLY文件存储在同目录下的`ply/`文件夹

### Q: 如何备份数据？

A:
```bash
# 进入项目目录
cd /root/3dModMatch/webpage

# 备份PostgreSQL数据库
docker-compose exec db pg_dump -U postgres shoe_matcher > backup_$(date +%Y%m%d).sql

# 备份用户上传的文件
tar -czf media_backup_$(date +%Y%m%d).tar.gz shoe_matcher_web/media/

# 备份匹配结果
tar -czf results_backup_$(date +%Y%m%d).tar.gz results/

# 恢复数据库
cat backup_20250930.sql | docker-compose exec -T db psql -U postgres shoe_matcher
```

---

## 🛠️ 故障排除

### 服务启动失败

```bash
# 查看详细日志
docker-compose logs

# 检查端口占用
sudo netstat -tulpn | grep 8000

# 清理重建
docker-compose down -v
docker-compose up -d --force-recreate
```

### 匹配结果异常

1. 检查输入文件是否有效的3D模型
2. 确认文件单位为毫米(mm)
3. 检查模型是否过大或过小
4. 查看匹配日志: `webpage/logs/matching.log`

### 性能问题

1. 增加Docker资源限制
2. 减少`MAX_CONCURRENT_TASKS`
3. 调整`CELERY_CONCURRENCY`
4. 使用更快的磁盘(SSD)

---

## 🚦 系统监控

### 健康检查

```bash
# 检查所有服务健康状态
docker-compose ps

# 检查Web服务
curl http://localhost:8000/api/health/

# 检查数据库
docker-compose exec db pg_isready

# 检查Redis
docker-compose exec redis redis-cli ping
```

### 日志位置

- **Django**: `webpage/logs/django.log`
- **匹配任务**: `webpage/logs/matching.log`
- **Celery**: `docker-compose logs celery`
- **容器日志**: `docker-compose logs <service-name>`

---

## 📈 路线图

### v1.1 (计划中)

- [ ] 支持更多3D格式 (OBJ, PLY, STEP, IGES)
- [ ] 批量匹配导出Excel报告
- [ ] 匹配结果对比功能
- [ ] RESTful API完善
- [ ] 热图自动生成

### v1.2 (计划中)

- [ ] 机器学习优化匹配参数
- [ ] 实时匹配进度推送(WebSocket)
- [ ] 多语言支持(i18n)
- [ ] 移动端适配

### v2.0 (远期)

- [ ] GPU加速(CUDA)
- [ ] 分布式计算支持
- [ ] 自动化测试套件
- [ ] Kubernetes部署

---

## 🤝 贡献指南

我们欢迎所有形式的贡献！

1. Fork本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

## 👥 作者

**3dModMatch Team**

---

## 🙏 致谢

- [Open3D](https://github.com/isl-org/Open3D) - 强大的3D数据处理库
- [Django](https://www.djangoproject.com/) - 优秀的Web框架
- [rhino3dm](https://github.com/mcneel/rhino3dm) - Rhino文件处理
- [Plotly](https://plotly.com/) - 交互式可视化

---

## 📞 技术支持

遇到问题时的排查顺序：

1. **查看日志**
   ```bash
   cd /root/3dModMatch/webpage
   docker-compose logs web
   docker-compose logs celery
   tail -f logs/matching.log
   ```

2. **检查服务状态**
   ```bash
   docker-compose ps
   curl http://localhost:8000/api/health/
   ```

3. **查看本README的常见问题章节**

4. **查看详细文档**
   - 架构设计: `webpage/doc/architecture.md`
   - API设计: `webpage/doc/api_design.md`
   - 部署指南: `webpage/doc/deployment.md`

---

<div align="center">

**⭐ 3D鞋模智能匹配系统 ⭐**

为制鞋行业提供专业的智能化匹配解决方案

基于 Django 4.2 + C++17 + Open3D 构建

---

**核心技术**: FPFH | RANSAC | ICP | SDF | Chamfer Distance

**运行环境**: Docker | PostgreSQL | Redis | Celery

Made with ❤️ for 制鞋行业

</div>

