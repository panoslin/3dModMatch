# 应用图标资源

3D鞋楦智能匹配系统的应用图标资源文件。

## 设计概念

- **主题**: "Last" (鞋楦)
- **图形**: 两个垂直叠放的圆形，象征匹配对比
- **颜色**: 红色渐变 (上) + 紫色渐变 (下)
- **风格**: 苹果设计语言，深色背景

## 文件列表

### 矢量图标
- `app-icon.svg` - 原始SVG矢量图标 (128x128)

### ICO文件 
- `app-icon.ico` - 多尺寸ICO文件 (包含16x16, 32x32, 48x48, 64x64)

### PNG文件
- `app-icon-16.png` - 16x16像素
- `app-icon-32.png` - 32x32像素  
- `app-icon-48.png` - 48x48像素
- `app-icon-64.png` - 64x64像素
- `app-icon-128.png` - 128x128像素
- `app-icon-256.png` - 256x256像素
- `app-icon-512.png` - 512x512像素

## 使用指南

### Web应用
- **Favicon**: 使用 `app-icon.ico`
- **Apple Touch Icon**: 使用 `app-icon-180.png`
- **Android**: 使用 `app-icon-192.png` 和 `app-icon-512.png`

### 桌面应用
- **Windows**: 使用 `app-icon.ico`
- **macOS**: 使用 `app-icon-512.png`
- **Linux**: 使用各种PNG尺寸

### HTML引用示例

```html
<!-- Favicon -->
<link rel="icon" type="image/x-icon" href="/static/icons/app-icon.ico">

<!-- Apple Touch Icon -->
<link rel="apple-touch-icon" href="/static/icons/app-icon-128.png">

<!-- Android Chrome -->
<link rel="icon" type="image/png" sizes="192x192" href="/static/icons/app-icon-256.png">
<link rel="icon" type="image/png" sizes="512x512" href="/static/icons/app-icon-512.png">
```

---

**创建时间**: 2024年9月26日  
**版本**: 1.0
