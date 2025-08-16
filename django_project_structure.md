# Django SSR 3D鞋模匹配系统项目结构

## 项目目录结构
```
shoe_matching_system/
│
├── manage.py
├── requirements.txt
├── README.md
│
├── config/                     # 项目配置
│   ├── __init__.py
│   ├── settings.py            # Django设置
│   ├── urls.py               # 主URL配置  
│   └── wsgi.py               # WSGI配置
│
├── apps/
│   ├── core/                  # 核心业务逻辑
│   │   ├── __init__.py
│   │   ├── models.py         # 数据模型（文件、匹配结果）
│   │   ├── views.py          # 视图处理
│   │   ├── forms.py          # 表单处理
│   │   ├── urls.py           # URL路由
│   │   └── admin.py          # 管理后台
│   │
│   ├── file_processing/       # 3D文件处理
│   │   ├── __init__.py
│   │   ├── parsers.py        # .3dm/.MOD文件解析
│   │   ├── geometry.py       # 几何分析算法
│   │   └── utils.py          # 工具函数
│   │
│   └── matching/              # 智能匹配引擎
│       ├── __init__.py
│       ├── algorithms.py     # 匹配算法
│       ├── optimization.py   # 优化算法
│       └── analysis.py       # 结果分析
│
├── templates/                 # Django模板
│   ├── base.html             # 基础模板
│   ├── index.html            # 首页
│   ├── upload.html           # 文件上传页面
│   ├── analysis.html         # 分析结果页面
│   └── components/           # 模板组件
│       ├── file_list.html
│       ├── 3d_viewer.html
│       └── results_table.html
│
├── static/                    # 静态资源
│   ├── css/
│   │   ├── base.css          # 基础样式
│   │   ├── modern.css        # 现代浏览器样式
│   │   └── legacy.css        # IE兼容样式
│   ├── js/
│   │   ├── base.js           # 基础JavaScript
│   │   ├── three.min.js      # Three.js (兼容版本)
│   │   └── 3d_viewer.js      # 3D查看器
│   └── images/               # 图片资源
│
├── media/                     # 用户上传文件
│   ├── shoes/                # 鞋模文件
│   ├── blanks/               # 粗胚文件
│   └── analysis/             # 分析结果文件
│
└── tests/                     # 测试文件
    ├── test_models.py
    ├── test_views.py
    └── test_algorithms.py
```

## 核心配置文件

### requirements.txt
```
Django==4.2.7
mysqlclient==2.2.0
Pillow==10.1.0
numpy==1.24.3
scipy==1.10.1
open3d==0.18.0
python-decouple==3.8
gunicorn==21.2.0
```

### settings.py 核心配置
```python
import os
from decouple import config

# 数据库配置
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('DB_NAME', 'shoe_matching'),
        'USER': config('DB_USER', 'root'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', 'localhost'),
        'PORT': config('DB_PORT', '3306'),
    }
}

# 文件上传设置
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
FILE_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024  # 100MB

# 缓存配置 (可选 - 使用文件缓存)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': os.path.join(BASE_DIR, 'cache'),
        'TIMEOUT': 3600 * 24,  # 24小时过期
    }
}

# 静态文件设置
STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
```

## 核心模型设计

### models.py
```python
from django.db import models
from django.contrib.auth.models import User
import json

class ShoeModel(models.Model):
    """鞋模文件模型"""
    filename = models.CharField(max_length=255)
    file = models.FileField(upload_to='shoes/')
    file_size = models.BigIntegerField()
    volume = models.DecimalField(max_digits=10, decimal_places=3, null=True)
    key_features = models.JSONField(default=dict)  # 存储几何特征
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.filename

class BlankModel(models.Model):
    """粗胚文件模型"""
    filename = models.CharField(max_length=255)
    file = models.FileField(upload_to='blanks/')
    file_size = models.BigIntegerField()
    volume = models.DecimalField(max_digits=10, decimal_places=3, null=True)
    key_features = models.JSONField(default=dict)
    material_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.filename

class MatchingResult(models.Model):
    """匹配结果模型"""
    shoe_model = models.ForeignKey(ShoeModel, on_delete=models.CASCADE)
    blank_model = models.ForeignKey(BlankModel, on_delete=models.CASCADE)
    similarity_score = models.DecimalField(max_digits=5, decimal_places=2)
    material_utilization = models.DecimalField(max_digits=5, decimal_places=2)
    average_margin = models.DecimalField(max_digits=4, decimal_places=1)
    min_margin = models.DecimalField(max_digits=4, decimal_places=1)
    is_optimal = models.BooleanField(default=False)  # 是否为最优解
    analysis_data = models.JSONField(default=dict)  # 详细分析数据
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['shoe_model', 'blank_model']
```

## 核心视图逻辑

### views.py 核心实现
```python
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from .models import ShoeModel, BlankModel, MatchingResult
from .forms import FileUploadForm
from apps.matching.algorithms import find_optimal_match
import logging

logger = logging.getLogger(__name__)

class HomeView(TemplateView):
    """首页视图 - SSR渲染"""
    template_name = 'index.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'shoe_files': ShoeModel.objects.all()[:10],
            'blank_files': BlankModel.objects.all()[:10],
            'recent_results': MatchingResult.objects.filter(is_optimal=True)[:5],
            'total_matches': MatchingResult.objects.count(),
        })
        return context

def upload_files(request):
    """文件上传处理"""
    if request.method == 'POST':
        shoe_files = request.FILES.getlist('shoe_files')
        blank_files = request.FILES.getlist('blank_files')
        
        # 处理鞋模文件
        for file in shoe_files:
            shoe = ShoeModel.objects.create(
                filename=file.name,
                file=file,
                file_size=file.size,
                uploaded_by=request.user if request.user.is_authenticated else None
            )
            logger.info(f"Uploaded shoe model: {file.name}")
        
        # 处理粗胚文件
        for file in blank_files:
            blank = BlankModel.objects.create(
                filename=file.name,
                file=file,
                file_size=file.size
            )
            logger.info(f"Uploaded blank model: {file.name}")
        
        messages.success(request, f'成功上传 {len(shoe_files)} 个鞋模和 {len(blank_files)} 个粗胚文件')
        return redirect('analysis')
    
    return render(request, 'upload.html', {'form': FileUploadForm()})

def analysis_view(request):
    """分析页面 - 展示匹配结果"""
    shoe_id = request.GET.get('shoe_id')
    margin_distance = float(request.GET.get('margin', 2.5))
    
    if shoe_id:
        try:
            shoe = ShoeModel.objects.get(id=shoe_id)
            # 执行匹配算法
            optimal_result = find_optimal_match(shoe, margin_distance)
            
            context = {
                'shoe_model': shoe,
                'optimal_result': optimal_result,
                'margin_distance': margin_distance,
                'all_results': MatchingResult.objects.filter(shoe_model=shoe)[:10],
            }
        except ShoeModel.DoesNotExist:
            messages.error(request, '指定的鞋模不存在')
            return redirect('home')
    else:
        context = {
            'available_shoes': ShoeModel.objects.all(),
            'recent_results': MatchingResult.objects.filter(is_optimal=True)[:10],
        }
    
    return render(request, 'analysis.html', context)

@csrf_exempt
def api_match_models(request):
    """AJAX API - 用于异步匹配请求"""
    if request.method == 'POST':
        shoe_id = request.POST.get('shoe_id')
        margin = float(request.POST.get('margin', 2.5))
        
        try:
            shoe = ShoeModel.objects.get(id=shoe_id)
            result = find_optimal_match(shoe, margin)
            
            return JsonResponse({
                'success': True,
                'result': {
                    'blank_filename': result.blank_model.filename,
                    'material_utilization': float(result.material_utilization),
                    'average_margin': float(result.average_margin),
                    'min_margin': float(result.min_margin),
                    'similarity_score': float(result.similarity_score)
                }
            })
        except Exception as e:
            logger.error(f"Matching error: {str(e)}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})
```

## 模板示例

### base.html 基础模板
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}3D鞋模智能匹配系统{% endblock %}</title>
    
    <!-- 基础CSS - 所有浏览器都支持 -->
    <link rel="stylesheet" href="{% static 'css/base.css' %}">
    
    <!-- 渐进增强CSS - 现代浏览器 -->
    <!--[if !IE]><!-->
    <link rel="stylesheet" href="{% static 'css/modern.css' %}">
    <!--<![endif]-->
    
    <!-- IE兼容CSS -->
    <!--[if IE]>
    <link rel="stylesheet" href="{% static 'css/legacy.css' %}">
    <![endif]-->
    
    {% block extra_css %}{% endblock %}
</head>
<body>
    <div class="container">
        <header class="site-header">
            <h1>🥿 3D鞋模智能匹配系统</h1>
            <nav>
                <a href="{% url 'home' %}">首页</a>
                <a href="{% url 'upload' %}">文件上传</a>
                <a href="{% url 'analysis' %}">智能分析</a>
            </nav>
        </header>
        
        <main class="main-content">
            {% if messages %}
                <div class="messages">
                    {% for message in messages %}
                        <div class="alert alert-{{ message.tags }}">
                            {{ message }}
                        </div>
                    {% endfor %}
                </div>
            {% endif %}
            
            {% block content %}{% endblock %}
        </main>
        
        <footer class="site-footer">
            <p>&copy; 2024 3D鞋模智能匹配系统</p>
        </footer>
    </div>
    
    <!-- 基础JavaScript - 兼容所有浏览器 -->
    <script src="{% static 'js/base.js' %}"></script>
    
    <!-- 渐进增强JavaScript - 现代浏览器 -->
    <script>
    if (window.addEventListener && window.JSON) {
        // 现代浏览器：加载Three.js和高级功能
        var script = document.createElement('script');
        script.src = '{% static 'js/three.min.js' %}';
        script.onload = function() {
            // Three.js加载完成后初始化3D功能
            if (typeof init3DViewer === 'function') {
                init3DViewer();
            }
        };
        document.head.appendChild(script);
    }
    </script>
    
    {% block extra_js %}{% endblock %}
</body>
</html>
```

## 部署优势

### 1. 简单部署
```bash
# 一条命令部署
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic
gunicorn config.wsgi:application
```

### 2. Windows XP服务器兼容
- 可以部署在Windows Server 2003
- 支持IIS + FastCGI
- 无需复杂的前后端分离配置

### 3. 渐进增强策略
```python
# 浏览器检测中间件
class BrowserCompatibilityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        request.is_legacy_browser = 'MSIE' in user_agent or 'Trident' in user_agent
        return self.get_response(request)
```

这个Django SSR方案完美解决了所有兼容性问题，同时保持了现代化的用户体验！
