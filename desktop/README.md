# 鞋模智能匹配桌面应用

## 📱 概述

基于 Electron + Angular + PrimeNG 构建的跨平台桌面应用，集成了强大的 3D 鞋模与粗胚智能匹配引擎。

## 🎯 核心功能

- **粗胚管理**: 批量上传和分类管理粗胚 3DM 文件，支持多分类关联
- **智能匹配**: 一个鞋模对多个粗胚的批量匹配，自动评估最佳匹配
- **3D 预览**: 实时预览粗胚、鞋模和匹配热图
- **历史记录**: 完整的匹配历史记录和结果查询
- **数据统计**: 可视化展示匹配统计信息

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                    Electron 主进程                        │
│  - 窗口管理、文件系统、SQLite 数据库                      │
└────────────┬───────────────────────────────┬────────────┘
             │                               │
             ▼                               ▼
┌──────────────────────┐       ┌────────────────────────┐
│  Angular 前端         │       │   Python 匹配引擎       │
│  - PrimeNG UI        │◄─────►│  - hybrid_matcher      │
│  - 3D 可视化         │  IPC  │  - C++ 优化核心        │
└──────────────────────┘       └────────────────────────┘
```

## 📦 项目结构

```
desktop/
├── docs/                  # 设计文档
├── electron/              # Electron 主进程
│   ├── main.ts           # 主进程入口
│   ├── preload.ts        # 预加载脚本
│   ├── ipc-handlers/     # IPC 处理器
│   └── services/         # 服务层
├── angular-app/           # Angular 应用
│   └── src/
│       ├── app/
│       │   ├── components/  # UI 组件
│       │   └── services/    # 服务
│       └── assets/          # 静态资源
├── python-engine/         # Python 匹配引擎
│   ├── main.py           # Python 入口
│   └── engine/           # 核心匹配算法
├── database/              # SQLite 数据库
└── user-data/            # 用户数据（运行时生成）
```

## 🚀 快速开始

### 前置要求

- Node.js 18+
- Python 3.10+
- Docker (用于构建 Python 引擎)
- Git

### 安装步骤

1. **克隆仓库**
```bash
git clone https://github.com/your-repo/3dModMatch.git
cd 3dModMatch/desktop
```

2. **安装依赖**
```bash
npm install
```

3. **构建 Angular 应用**
```bash
cd angular-app
npm install
npm run build
cd ..
```

4. **构建 Python 引擎** (使用 Docker)
```bash
cd python-engine
chmod +x build_with_docker.sh
./build_with_docker.sh
cd ..
```

5. **编译 TypeScript**
```bash
npx tsc
```

6. **启动应用**
```bash
npm start
```

## 🔨 开发模式

### 启动开发服务器

1. **启动 Angular 开发服务器**
```bash
cd angular-app
ng serve
```

2. **启动 Electron (开发模式)**
```bash
npm run dev
```

### 调试

- 按 `Ctrl+Shift+I` (Windows/Linux) 或 `Cmd+Option+I` (macOS) 打开开发者工具
- 使用 Chrome DevTools 调试前端
- 查看主进程日志在终端输出

## 📦 打包发布

### macOS
```bash
npm run dist:mac
```

### Windows
```bash
npm run dist:win
```

打包后的安装程序位于 `dist/` 目录。

## 🔧 配置说明

### 数据库配置
- 数据库文件自动创建在用户数据目录
- 位置: `~/AppData/Roaming/shoe-last-matcher/database.db` (Windows)
- 位置: `~/Library/Application Support/shoe-last-matcher/database.db` (macOS)

### Python 引擎配置
- 匹配参数可在界面中调整
- 默认间隙要求: 2.0mm
- 默认阈值: P15

## 📊 使用指南

### 1. 粗胚管理

1. 点击左侧菜单「粗胚管理」
2. 点击「上传粗胚」按钮
3. 选择 `.3dm` 格式的粗胚文件
4. 为粗胚分配分类（可多选）
5. 点击保存

### 2. 开始匹配

1. 点击左侧菜单「开始匹配」
2. 上传目标鞋模文件（.3dm 格式）
3. 选择要匹配的粗胚（通过分类或直接选择）
4. 设置匹配参数：
   - 间隙要求（默认 2.0mm）
   - 是否启用缩放
   - 阈值选择（Min/P10/P15/P20）
5. 点击「开始匹配」按钮
6. 查看实时进度和控制台输出

### 3. 查看结果

1. 匹配完成后自动显示结果
2. 结果包含：
   - 覆盖率
   - 体积比
   - P15 间隙值
   - 最小间隙
   - 通过/失败状态
3. 点击结果可查看 3D 热图

### 4. 历史记录

1. 点击左侧菜单「历史记录」
2. 查看所有匹配历史
3. 可按日期、状态筛选
4. 支持结果导出

## 🐛 故障排除

### 常见问题

**Q: Python 引擎启动失败**
- A: 确保已正确构建 Python 引擎，检查 `python-engine/dist/` 目录是否存在可执行文件

**Q: 3D 预览无法显示**
- A: 检查 WebGL 支持，更新显卡驱动

**Q: 数据库连接失败**
- A: 检查用户数据目录权限，尝试删除数据库文件重新创建

**Q: 内存占用过高**
- A: 减少并行处理数量，在设置中调整

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📞 联系方式

- 项目主页: https://github.com/your-repo/3dModMatch
- 问题反馈: https://github.com/your-repo/3dModMatch/issues

---

## 附录: NPM 脚本

```json
{
  "start": "electron .",                    // 启动应用
  "dev": "npm run build:angular && electron . --dev",  // 开发模式
  "build:angular": "cd angular-app && ng build",       // 构建 Angular
  "build:python": "cd python-engine && pyinstaller build.spec",  // 构建 Python
  "build": "npm run build:angular && npm run build:python && electron-builder",  // 完整构建
  "dist:mac": "npm run build && electron-builder --mac",  // macOS 打包
  "dist:win": "npm run build && electron-builder --win"   // Windows 打包
}
```

## 系统要求

### 最低配置
- **操作系统**: Windows 10 / macOS 10.14
- **处理器**: 双核 2GHz
- **内存**: 4GB RAM
- **存储**: 2GB 可用空间
- **显卡**: 支持 WebGL 2.0

### 推荐配置
- **操作系统**: Windows 11 / macOS 12+
- **处理器**: 四核 3GHz+
- **内存**: 8GB+ RAM
- **存储**: 5GB+ 可用空间
- **显卡**: 独立显卡，支持 WebGL 2.0

---

*版本: 1.0.0 | 最后更新: 2024*
