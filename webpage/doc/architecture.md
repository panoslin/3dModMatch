# 3D鞋模智能匹配系统 - 系统架构文档

## 1. 系统概述

本系统是一个基于Django的SSR网页应用程序，用于包装和管理3D鞋模智能匹配功能。系统集成了现有的hybrid匹配算法，提供友好的Web界面进行鞋模与粗胚的智能匹配。

## 2. 技术架构

### 2.1 技术栈
- **后端框架**: Django 4.2 + Python 3.10
- **前端技术**: Bootstrap 5 + jQuery + Plotly.js
- **数据库**: PostgreSQL 13
- **异步任务**: Celery + Redis
- **容器化**: Docker + Docker Compose
- **3D处理**: Open3D + C++17核心模块
- **文件存储**: Django文件系统

### 2.2 系统架构图
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Browser   │◄──►│  Django Web App │◄──►│   PostgreSQL    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │  Celery Worker  │◄──►│     Redis       │
                       └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │ Hybrid Matcher  │
                       │   Container     │
                       └─────────────────┘
```

## 3. 应用架构

### 3.1 Django应用结构
```
shoe_matcher_web/
├── config/                 # 项目配置
├── apps/
│   ├── core/              # 核心功能
│   ├── blanks/            # 粗胚管理
│   ├── shoes/             # 鞋模管理
│   ├── matching/          # 匹配功能
│   └── visualization/     # 3D可视化
```

### 3.2 数据模型关系
```
BlankCategory (分类)
    ├── 1:N → BlankModel (粗胚)
    └── M:N → MatchingTask (匹配任务)

ShoeModel (鞋模)
    └── 1:N → MatchingTask (匹配任务)

MatchingTask (匹配任务)
    ├── N:1 → ShoeModel
    ├── M:N → BlankCategory
    └── 1:N → MatchingResult (匹配结果)
```

## 4. 核心功能模块

### 4.1 文件处理模块
- 3DM文件上传和验证
- 几何信息提取
- 3D预览生成

### 4.2 匹配计算模块
- Docker容器集成
- 异步任务处理
- 结果数据解析

### 4.3 可视化模块
- 3D模型预览
- 匹配结果热图
- 交互式图表

## 5. 用户界面设计

### 5.1 页面结构
- **主页/匹配页面** (`/`) - 所有功能的入口
- **历史记录页面** (`/history/`) - 查看历史匹配记录

### 5.2 Modal组件
- 鞋模上传Modal
- 粗胚管理Modal
- 匹配结果Modal
- 3D预览Modal

## 6. 集成方案

### 6.1 与Hybrid系统集成
- 通过Docker容器运行匹配算法
- 文件系统共享数据
- JSON格式结果交换

### 6.2 C++模块集成
- 使用现有的cppcore模块
- 通过build_cpp.sh构建
- Python绑定调用

## 7. 部署架构

### 7.1 容器化部署
```yaml
services:
  web:        # Django应用
  db:         # PostgreSQL数据库
  redis:      # Redis缓存
  celery:     # 异步任务处理
  matcher:    # Hybrid匹配容器
```

### 7.2 数据流向
1. 用户上传文件 → Django处理
2. Django创建匹配任务 → Celery队列
3. Celery调用Hybrid容器 → 执行匹配
4. 容器输出结果 → Django解析
5. 结果存储数据库 → 前端展示

## 8. 安全考虑

### 8.1 文件安全
- 文件类型验证
- 文件大小限制
- 安全的文件存储路径

### 8.2 系统安全
- CSRF保护
- SQL注入防护
- 用户权限控制

## 9. 性能优化

### 9.1 前端优化
- 静态文件压缩
- 异步加载
- 缓存策略

### 9.2 后端优化
- 数据库查询优化
- Redis缓存
- 异步任务处理

## 10. 监控和日志

### 10.1 日志记录
- Django应用日志
- 匹配任务日志
- 错误追踪

### 10.2 系统监控
- 任务队列状态
- 容器健康检查
- 资源使用监控


