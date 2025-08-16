# 3D鞋模智能匹配系统

> 基于Django + Docker + MySQL的专业3D鞋模与粗胚智能匹配系统

## 📋 需求文档

详细的系统需求和功能规格请参考：**[需求文档](docs/REQUIREMENTS.md)**

## 🎯 系统特性

- **🔍 智能匹配** - 自动找到最经济的粗胚匹配方案
- **📏 精确分析** - 高精度几何分析确保余量合理  
- **💰 成本优化** - 优先选择材料利用率高的方案
- **🎨 3D可视化** - 热力图、截面分析、动画演示
- **📱 兼容性好** - 支持Windows XP等老系统浏览器
- **🔄 批量处理** - 支持多文件同时分析

## 📋 技术栈

- **后端框架**: Django 4.2 (Python)
- **数据库**: MySQL 8.0
- **前端**: Bootstrap 5 + JavaScript (兼容IE8+)
- **3D处理**: NumPy + SciPy + 自研解析器
- **部署**: Docker + Docker Compose + Nginx
- **文件支持**: .3dm (Rhinoceros) + .MOD (自定义格式)

## 🚀 快速部署

### 1. 环境准备

确保您的系统已安装：
- Docker (>= 20.10)
- Docker Compose (>= 2.0)

### 2. 项目部署

```bash
# 1. 克隆或复制项目文件
cd shoe_matching_system

# 2. 创建环境配置文件
cp config.env.example .env
# 编辑.env文件，修改密码等敏感信息

# 3. 创建必要目录
mkdir -p logs media/shoes media/blanks media/analysis

# 4. 构建并启动服务
docker-compose up -d

# 5. 运行数据库迁移
docker-compose exec web python manage.py migrate

# 6. 创建超级管理员
docker-compose exec web python manage.py createsuperuser

# 7. 收集静态文件
docker-compose exec web python manage.py collectstatic --noinput
```

### 3. 访问系统

- **主页**: http://localhost
- **管理后台**: http://localhost/admin/
- **API文档**: http://localhost/api/

## 📁 项目结构

```
shoe_matching_system/
├── config/                 # Django项目配置
│   ├── settings/           # 分环境设置
│   ├── urls.py             # URL路由
│   └── wsgi.py             # WSGI配置
├── apps/                   # Django应用
│   ├── core/               # 核心业务逻辑
│   ├── file_processing/    # 3D文件处理
│   └── matching/           # 智能匹配算法
├── templates/              # Django模板
├── static/                 # 静态资源
├── media/                  # 用户上传文件
├── docker/                 # Docker配置
│   ├── nginx/              # Nginx配置
│   └── mysql/              # MySQL初始化
├── docker-compose.yml      # 服务编排
├── Dockerfile              # 应用镜像
├── requirements.txt        # Python依赖
└── manage.py               # Django管理工具
```

## 🔧 核心功能

### 1. 文件上传与解析

- 支持.3dm (Rhinoceros 3D)格式
- 支持.MOD自定义格式
- 自动几何特征提取
- 边界框和体积计算

### 2. 智能匹配算法

```python
# 匹配算法核心流程
def find_optimal_match(shoe_model, margin_distance):
    # 1. 获取所有可用粗胚
    available_blanks = BlankModel.objects.filter(is_processed=True)
    
    # 2. 几何兼容性检查
    compatible_blanks = check_geometric_compatibility(shoe_model, available_blanks, margin_distance)
    
    # 3. 按材料利用率排序
    ranked_matches = calculate_material_utilization(shoe_model, compatible_blanks)
    
    # 4. 返回最优方案
    return ranked_matches[0] if ranked_matches else None
```

### 3. 3D可视化

- 基于Three.js的现代浏览器支持
- 老浏览器降级为2D分析图表
- 交互式查看匹配效果
- 实时调整参数预览

### 4. 报表分析

- 材料利用率统计
- 成本节约分析
- 匹配历史记录
- 数据导出功能

## ⚙️ 配置说明

### 环境变量配置

| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| SECRET_KEY | Django安全密钥 | 需要设置 |
| DEBUG | 调试模式 | False |
| DB_HOST | 数据库主机 | db |
| DB_NAME | 数据库名 | shoe_matching |
| DB_USER | 数据库用户 | django_user |
| DB_PASSWORD | 数据库密码 | 需要设置 |

### 几何分析参数

| 参数 | 描述 | 范围 |
|------|------|------|
| DEFAULT_MARGIN_DISTANCE | 默认余量距离 | 2.5mm |
| MIN_MARGIN_DISTANCE | 最小余量 | 0.5mm |
| MAX_MARGIN_DISTANCE | 最大余量 | 10.0mm |
| PRECISION_TOLERANCE | 计算精度 | 0.01mm |

## 🔍 API接口

### 文件上传
```bash
POST /api/files/parse/
Content-Type: multipart/form-data

{
  "file": "shoe_model.3dm",
  "type": "shoe"
}
```

### 匹配分析
```bash
POST /api/matching/analyze/
Content-Type: application/json

{
  "shoe_id": 1,
  "margin_distance": 2.5
}
```

## 📊 系统监控

### 容器状态检查
```bash
# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f web

# 查看数据库连接
docker-compose exec web python manage.py dbshell
```

### 性能监控
```bash
# 系统资源使用
docker stats

# 数据库性能
docker-compose exec db mysql -u root -p -e "SHOW PROCESSLIST;"
```

## 🛠️ 开发指南

### 本地开发环境

```bash
# 1. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 使用开发设置
export DJANGO_SETTINGS_MODULE=config.settings.development

# 4. 运行开发服务器
python manage.py runserver

# 5. 运行测试
python manage.py test
```

### 添加新功能

1. 在相应的app中创建模型
2. 生成并应用迁移
3. 添加视图和URL
4. 创建模板
5. 编写测试用例

## 🔧 维护指南

### 数据备份
```bash
# 备份数据库
docker-compose exec db mysqldump -u root -p shoe_matching > backup.sql

# 恢复数据库
docker-compose exec -T db mysql -u root -p shoe_matching < backup.sql
```

### 日志管理
```bash
# 查看应用日志
docker-compose logs web

# 清理日志
docker-compose exec web find /app/logs -name "*.log" -mtime +7 -delete
```

### 更新部署
```bash
# 1. 停止服务
docker-compose down

# 2. 拉取最新代码
git pull origin main

# 3. 重新构建
docker-compose build

# 4. 启动服务
docker-compose up -d

# 5. 运行迁移
docker-compose exec web python manage.py migrate
```

## ❓ 常见问题

### Q: 上传的文件无法解析？
A: 检查文件格式是否为.3dm或.MOD，文件大小是否超过100MB限制。

### Q: 匹配结果不准确？
A: 调整余量距离参数，确保粗胚文件已正确解析。

### Q: 在IE8下功能受限？
A: 系统会自动降级为基础功能，3D可视化不可用但核心匹配功能正常。

### Q: 数据库连接失败？
A: 检查MySQL容器状态，确认数据库密码配置正确。

## 📞 技术支持

- **文档**: 查看docs/目录下的详细文档
- **问题反馈**: 创建GitHub Issue
- **功能建议**: 欢迎提交Pull Request

## 📄 开源协议

本项目采用 MIT 协议开源，详见 [LICENSE](LICENSE) 文件。

---

**3D鞋模智能匹配系统** - 让传统制鞋工艺与现代技术完美结合 🥿✨
