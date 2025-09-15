# API设计文档

## 1. API概述

本系统采用RESTful API设计，主要用于前端AJAX调用和系统内部通信。所有API返回JSON格式数据。

## 2. 通用响应格式

### 2.1 成功响应
```json
{
    "success": true,
    "data": {},
    "message": "操作成功"
}
```

### 2.2 错误响应
```json
{
    "success": false,
    "error": "错误类型",
    "message": "错误描述",
    "details": {}
}
```

## 3. 鞋模相关API

### 3.1 上传鞋模
```http
POST /api/shoes/upload/
Content-Type: multipart/form-data

参数:
- file: 3DM文件
- name: 鞋模名称

响应:
{
    "success": true,
    "data": {
        "id": 1,
        "name": "鞋模名称",
        "file_url": "/media/shoes/2024/01/model.3dm",
        "volume": 631470.0,
        "preview_html": "<div>...</div>"
    }
}
```

### 3.2 获取鞋模预览
```http
GET /api/shoes/{id}/preview/

响应:
{
    "success": true,
    "data": {
        "html": "<div id='preview'>...</div>",
        "metadata": {
            "volume": 631470.0,
            "bounding_box": {...}
        }
    }
}
```

## 4. 粗胚相关API

### 4.1 获取粗胚列表
```http
GET /api/blanks/
参数:
- category_id: 分类ID (可选)
- page: 页码
- page_size: 每页数量

响应:
{
    "success": true,
    "data": {
        "results": [
            {
                "id": 1,
                "name": "002大.3dm",
                "volume": 1269882.0,
                "categories": [1, 2],
                "preview_thumbnail": "/media/thumbnails/blank_1.jpg"
            }
        ],
        "count": 50,
        "next": "/api/blanks/?page=2",
        "previous": null
    }
}
```

### 4.2 上传粗胚
```http
POST /api/blanks/
Content-Type: multipart/form-data

参数:
- file: 3DM文件
- name: 粗胚名称
- category_ids: 分类ID列表

响应:
{
    "success": true,
    "data": {
        "id": 1,
        "name": "粗胚名称",
        "volume": 1000000.0,
        "categories": [1, 2]
    }
}
```

### 4.3 删除粗胚
```http
DELETE /api/blanks/{id}/

响应:
{
    "success": true,
    "message": "粗胚删除成功"
}
```

## 5. 分类管理API

### 5.1 获取分类树
```http
GET /api/categories/

响应:
{
    "success": true,
    "data": [
        {
            "id": 1,
            "name": "女鞋",
            "children": [
                {
                    "id": 2,
                    "name": "尖头",
                    "children": [
                        {
                            "id": 3,
                            "name": "高跟",
                            "children": []
                        }
                    ]
                }
            ]
        }
    ]
}
```

### 5.2 创建分类
```http
POST /api/categories/
Content-Type: application/json

{
    "name": "分类名称",
    "parent_id": 1,
    "description": "分类描述"
}

响应:
{
    "success": true,
    "data": {
        "id": 4,
        "name": "分类名称",
        "parent_id": 1
    }
}
```

## 6. 匹配相关API

### 6.1 开始匹配
```http
POST /api/matching/start/
Content-Type: application/json

{
    "shoe_model_id": 1,
    "category_ids": [1, 2, 3],
    "clearance": 2.0,
    "enable_scaling": true,
    "max_scale": 1.03,
    "threshold": "p15"
}

响应:
{
    "success": true,
    "data": {
        "task_id": "match_20240115_123456",
        "status": "pending",
        "estimated_time": 120
    }
}
```

### 6.2 获取匹配状态
```http
GET /api/matching/{task_id}/status/

响应:
{
    "success": true,
    "data": {
        "task_id": "match_20240115_123456",
        "status": "processing",
        "progress": 45,
        "current_step": "处理候选模型 3/12",
        "estimated_remaining": 75
    }
}
```

### 6.3 获取匹配结果
```http
GET /api/matching/{task_id}/result/

响应:
{
    "success": true,
    "data": {
        "task_id": "match_20240115_123456",
        "status": "completed",
        "results": [
            {
                "blank_id": 1,
                "blank_name": "002大.3dm",
                "inside_ratio": 0.87426,
                "volume_ratio": 2.28,
                "min_clearance": 0.0,
                "p15_clearance": 107.79,
                "pass_p15": true,
                "chamfer": 6.16,
                "scale_used": 1.0,
                "mirrored": false,
                "heatmap_url": "/media/heatmaps/task_123_result_1.html"
            }
        ],
        "summary": {
            "total_candidates": 12,
            "passed_p15": 12,
            "passed_p10": 7,
            "passed_strict": 0,
            "processing_time": 118.5
        }
    }
}
```

## 7. 3D预览API

### 7.1 生成3D预览
```http
GET /api/preview/3dm/{model_id}/
参数:
- type: "shoe" | "blank"
- format: "html" | "json"

响应:
{
    "success": true,
    "data": {
        "html": "<div>3D预览HTML</div>",
        "metadata": {
            "vertices": 102962,
            "faces": 205924,
            "volume": 631470.0
        }
    }
}
```

## 8. 历史记录API

### 8.1 获取匹配历史
```http
GET /api/history/
参数:
- page: 页码
- page_size: 每页数量
- date_from: 开始日期
- date_to: 结束日期

响应:
{
    "success": true,
    "data": {
        "results": [
            {
                "task_id": "match_20240115_123456",
                "shoe_name": "金宇祥8073-36.3dm",
                "created_at": "2024-01-15T12:34:56Z",
                "status": "completed",
                "best_match": {
                    "blank_name": "002大.3dm",
                    "p15_clearance": 107.79
                },
                "total_candidates": 12
            }
        ],
        "count": 100
    }
}
```

## 9. 文件管理API

### 9.1 文件上传进度
```http
GET /api/upload/progress/{upload_id}/

响应:
{
    "success": true,
    "data": {
        "upload_id": "upload_123",
        "progress": 75,
        "status": "uploading",
        "bytes_uploaded": 7500000,
        "total_bytes": 10000000
    }
}
```

## 10. 系统状态API

### 10.1 系统健康检查
```http
GET /api/health/

响应:
{
    "success": true,
    "data": {
        "database": "healthy",
        "redis": "healthy",
        "matcher_container": "healthy",
        "disk_space": "85%",
        "active_tasks": 2
    }
}
```

## 11. 错误码定义

| 错误码 | 错误类型 | 描述 |
|--------|----------|------|
| 400 | BAD_REQUEST | 请求参数错误 |
| 401 | UNAUTHORIZED | 未授权访问 |
| 403 | FORBIDDEN | 禁止访问 |
| 404 | NOT_FOUND | 资源不存在 |
| 413 | FILE_TOO_LARGE | 文件过大 |
| 415 | UNSUPPORTED_MEDIA_TYPE | 不支持的文件类型 |
| 422 | VALIDATION_ERROR | 数据验证错误 |
| 500 | INTERNAL_ERROR | 服务器内部错误 |
| 503 | SERVICE_UNAVAILABLE | 服务不可用 |

## 12. API限制

### 12.1 请求限制
- 文件上传大小限制: 100MB
- 请求频率限制: 100次/分钟
- 并发匹配任务限制: 5个

### 12.2 数据格式要求
- 日期格式: ISO 8601 (YYYY-MM-DDTHH:MM:SSZ)
- 文件格式: 仅支持.3dm格式
- 字符编码: UTF-8


