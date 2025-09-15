# 部署文档

## 1. 系统要求

### 1.1 硬件要求
- **CPU**: 8核以上推荐
- **内存**: 16GB以上推荐
- **存储**: 100GB以上可用空间
- **网络**: 稳定的网络连接

### 1.2 软件要求
- **操作系统**: Ubuntu 22.04 LTS 或 CentOS 8+
- **Docker**: 20.10+
- **Docker Compose**: 2.0+
- **Python**: 3.10+

## 2. 环境配置

### 2.1 环境变量配置
创建 `.env` 文件：

```env
# Django配置
DEBUG=False
SECRET_KEY=your-super-secret-key-change-this-in-production
ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.com

# 数据库配置
DB_ENGINE=django.db.backends.postgresql
DB_NAME=shoe_matcher
DB_USER=postgres
DB_PASSWORD=your-secure-password
DB_HOST=db
DB_PORT=5432

# Redis配置
REDIS_URL=redis://redis:6379/0

# Celery配置
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# 文件存储配置
MEDIA_ROOT=/app/media
STATIC_ROOT=/app/static
MAX_UPLOAD_SIZE=104857600  # 100MB

# 匹配服务配置
MATCHER_DOCKER_IMAGE=hybrid-shoe-matcher:latest
DEFAULT_CLEARANCE=2.0
MAX_CONCURRENT_TASKS=5

# 邮件配置（可选）
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_USE_TLS=True

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=/app/logs/django.log

# 安全配置
SECURE_SSL_REDIRECT=True
SECURE_BROWSER_XSS_FILTER=True
SECURE_CONTENT_TYPE_NOSNIFF=True
```

### 2.2 Docker Compose配置
`docker-compose.yml`:

```yaml
version: '3.8'

services:
  db:
    image: postgres:13
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./docker/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER}"]
      interval: 30s
      timeout: 10s
      retries: 3

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

  web:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./media:/app/media
      - ./static:/app/static
      - ./logs:/app/logs
    environment:
      - DEBUG=${DEBUG}
      - SECRET_KEY=${SECRET_KEY}
      - DB_HOST=db
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health/"]
      interval: 30s
      timeout: 10s
      retries: 3

  celery:
    build: .
    command: celery -A config worker -l info --concurrency=4
    volumes:
      - ./media:/app/media
      - ./logs:/app/logs
    environment:
      - DEBUG=${DEBUG}
      - SECRET_KEY=${SECRET_KEY}
      - DB_HOST=db
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
      - matcher

  celery-beat:
    build: .
    command: celery -A config beat -l info
    volumes:
      - ./logs:/app/logs
    environment:
      - DEBUG=${DEBUG}
      - SECRET_KEY=${SECRET_KEY}
      - DB_HOST=db
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis

  matcher:
    build:
      context: ../hybrid
      dockerfile: Dockerfile
    volumes:
      - ./media:/app/input:ro
      - ./results:/app/output
      - ./logs:/app/logs
    environment:
      - OMP_NUM_THREADS=1
    healthcheck:
      test: ["CMD", "python3", "-c", "import cppcore; print('OK')"]
      interval: 60s
      timeout: 30s
      retries: 3

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./docker/nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./static:/var/www/static:ro
      - ./media:/var/www/media:ro
      - ./docker/nginx/ssl:/etc/nginx/ssl:ro
    depends_on:
      - web

volumes:
  postgres_data:
  redis_data:
```

## 3. 构建和部署步骤

### 3.1 准备工作
```bash
# 1. 克隆项目
git clone <repository-url>
cd 3dModMatch/webpage

# 2. 创建环境变量文件
cp .env.example .env
# 编辑 .env 文件，配置相应参数

# 3. 创建必要目录
mkdir -p media/{shoes,blanks,heatmaps}
mkdir -p static
mkdir -p logs
mkdir -p results
```

### 3.2 构建Docker镜像
```bash
# 1. 构建Hybrid匹配器镜像
cd ../hybrid
docker build -t hybrid-shoe-matcher:latest .

# 2. 构建Web应用镜像
cd ../webpage/shoe_matcher_web
docker build -t shoe-matcher-web:latest .
```

### 3.3 部署应用
```bash
# 1. 启动所有服务
docker-compose up -d

# 2. 等待数据库初始化
docker-compose logs -f db

# 3. 运行数据库迁移
docker-compose exec web python manage.py migrate

# 4. 创建超级用户
docker-compose exec web python manage.py createsuperuser

# 5. 收集静态文件
docker-compose exec web python manage.py collectstatic --noinput

# 6. 验证部署
docker-compose ps
curl http://localhost:8000/api/health/
```

## 4. 生产环境配置

### 4.1 Nginx配置
`docker/nginx/nginx.conf`:

```nginx
events {
    worker_connections 1024;
}

http {
    upstream web {
        server web:8000;
    }

    server {
        listen 80;
        server_name your-domain.com;
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name your-domain.com;

        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;

        client_max_body_size 100M;

        location / {
            proxy_pass http://web;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location /static/ {
            alias /var/www/static/;
            expires 1y;
            add_header Cache-Control "public, immutable";
        }

        location /media/ {
            alias /var/www/media/;
            expires 1h;
        }
    }
}
```

### 4.2 数据库备份脚本
`scripts/backup_db.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="shoe_matcher"

# 创建备份目录
mkdir -p $BACKUP_DIR

# 数据库备份
docker-compose exec -T db pg_dump -U postgres $DB_NAME > $BACKUP_DIR/db_backup_$DATE.sql

# 压缩备份文件
gzip $BACKUP_DIR/db_backup_$DATE.sql

# 删除7天前的备份
find $BACKUP_DIR -name "db_backup_*.sql.gz" -mtime +7 -delete

echo "Database backup completed: db_backup_$DATE.sql.gz"
```

### 4.3 监控脚本
`scripts/health_check.sh`:

```bash
#!/bin/bash

# 检查服务状态
check_service() {
    SERVICE=$1
    if docker-compose ps $SERVICE | grep -q "Up"; then
        echo "✓ $SERVICE is running"
    else
        echo "✗ $SERVICE is not running"
        return 1
    fi
}

# 检查所有服务
echo "=== Service Health Check ==="
check_service db
check_service redis
check_service web
check_service celery
check_service matcher

# 检查API健康状态
echo "=== API Health Check ==="
if curl -f http://localhost:8000/api/health/ > /dev/null 2>&1; then
    echo "✓ API is responding"
else
    echo "✗ API is not responding"
fi

# 检查磁盘空间
echo "=== Disk Space Check ==="
df -h | grep -E "(/$|/var)"

# 检查内存使用
echo "=== Memory Usage ==="
free -h

# 检查活跃任务
echo "=== Active Tasks ==="
docker-compose exec -T redis redis-cli llen celery | xargs echo "Pending tasks:"
```

## 5. 维护和更新

### 5.1 应用更新流程
```bash
# 1. 备份数据库
./scripts/backup_db.sh

# 2. 拉取最新代码
git pull origin main

# 3. 重新构建镜像
docker-compose build

# 4. 停止服务
docker-compose down

# 5. 启动服务
docker-compose up -d

# 6. 运行迁移
docker-compose exec web python manage.py migrate

# 7. 收集静态文件
docker-compose exec web python manage.py collectstatic --noinput

# 8. 验证更新
./scripts/health_check.sh
```

### 5.2 日志管理
```bash
# 查看应用日志
docker-compose logs -f web

# 查看Celery日志
docker-compose logs -f celery

# 查看匹配器日志
docker-compose logs -f matcher

# 清理旧日志
docker system prune -f
```

## 6. 故障排除

### 6.1 常见问题

**问题1**: 数据库连接失败
```bash
# 解决方案
docker-compose restart db
docker-compose exec db psql -U postgres -c "SELECT 1;"
```

**问题2**: Celery任务堆积
```bash
# 清空任务队列
docker-compose exec redis redis-cli flushall
docker-compose restart celery
```

**问题3**: 匹配器容器无响应
```bash
# 重启匹配器
docker-compose restart matcher
# 检查C++模块
docker-compose exec matcher python3 -c "import cppcore; print('OK')"
```

### 6.2 性能优化

1. **数据库优化**
   - 定期执行 `VACUUM ANALYZE`
   - 监控慢查询
   - 适当增加连接池大小

2. **Redis优化**
   - 配置适当的内存限制
   - 启用持久化
   - 监控内存使用

3. **Nginx优化**
   - 启用gzip压缩
   - 配置适当的缓存策略
   - 优化worker进程数

## 7. 安全建议

1. **系统安全**
   - 定期更新系统和依赖包
   - 配置防火墙规则
   - 使用强密码和SSH密钥

2. **应用安全**
   - 启用HTTPS
   - 配置CSRF保护
   - 实施访问控制

3. **数据安全**
   - 定期备份数据
   - 加密敏感数据
   - 监控异常访问


