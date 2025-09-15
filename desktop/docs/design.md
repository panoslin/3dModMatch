# 鞋模智能匹配桌面应用 - 系统设计文档

## 1. 项目概述

### 1.1 系统简介
鞋模智能匹配桌面应用是一个基于 Electron + Angular + PrimeNG 构建的跨平台桌面应用程序，用于智能匹配鞋模与粗胚模型，确保生产中的2mm间隙要求。

### 1.2 核心功能
- 粗胚文件管理与多分类关联
- 3DM格式鞋模文件上传与处理
- 一对多匹配（一个鞋模对多个粗胚）
- 实时3D预览（粗胚、鞋模、热图）
- 匹配历史记录与查询
- 覆盖率、体积比、P15间隙等关键指标展示

### 1.3 技术栈
- **前端框架**: Angular + PrimeNG
- **桌面框架**: Electron
- **3D渲染**: Plotly (嵌入式WebView)
- **后端引擎**: Python (PyInstaller打包)
- **数据存储**: SQLite
- **目标平台**: macOS, Windows

## 2. 系统架构

### 2.1 整体架构图
```
┌─────────────────────────────────────────────────────────┐
│                    Electron 主进程                        │
│  - 窗口管理                                              │
│  - Python子进程管理                                       │
│  - 文件系统操作                                          │
│  - SQLite数据库管理                                      │
└────────────┬───────────────────────────────┬────────────┘
             │                               │
             ▼                               ▼
┌──────────────────────┐       ┌────────────────────────┐
│  Angular 渲染进程     │       │   Python 引擎          │
│  - PrimeNG UI组件    │◄─────►│  - hybrid_matcher      │
│  - Plotly WebView    │  IPC  │  - PyInstaller打包     │
│  - 状态管理          │       │  - 子进程模式          │
└──────────────────────┘       └────────────────────────┘
```

### 2.2 进程通信流程
1. **用户操作** → Angular组件 → Electron Service → IPC调用
2. **IPC处理** → Electron主进程 → 生成Python子进程
3. **Python执行** → 标准输出流 → 实时数据返回
4. **结果处理** → 数据库存储 → UI更新

## 3. 目录结构

```
desktop/
├── docs/                          # 文档目录
│   ├── design.md                 # 系统设计文档
│   └── TODO.md                    # 开发任务清单
├── electron/                      # Electron主进程
│   ├── main.ts                   # 主进程入口
│   ├── preload.ts                # 预加载脚本
│   ├── ipc-handlers/             # IPC处理器
│   │   ├── database.handler.ts   # 数据库操作
│   │   ├── file.handler.ts       # 文件管理
│   │   └── matching.handler.ts   # 匹配流程
│   └── services/                  # 服务层
│       ├── python-runner.service.ts  # Python进程管理
│       └── database.service.ts       # 数据库服务
├── angular-app/                   # Angular应用
│   ├── src/
│   │   ├── app/
│   │   │   ├── components/       # UI组件
│   │   │   │   ├── dashboard/    # 主面板
│   │   │   │   ├── blank-manager/    # 粗胚管理
│   │   │   │   ├── matching/     # 匹配操作
│   │   │   │   ├── history/      # 历史记录
│   │   │   │   └── viewer-3d/    # 3D查看器
│   │   │   ├── services/         # 服务层
│   │   │   ├── models/           # 数据模型
│   │   │   └── app.module.ts
│   │   └── assets/
│   │       └── i18n/
│   │           └── zh-CN.json    # 中文语言包
├── python-engine/                 # Python引擎
│   ├── main.py                   # 入口包装器
│   ├── engine/                   # 核心匹配引擎
│   │   └── (hybrid matcher拷贝)
│   ├── requirements.txt          # 依赖清单
│   └── build.spec                # PyInstaller配置
├── database/                      # 数据库
│   └── schema.sql                # 数据库架构
├── resources/                     # 资源文件
│   ├── icons/                    # 应用图标
│   └── installer/                # 安装程序资源
├── user-data/                     # 用户数据（运行时生成）
│   ├── database.db               # SQLite数据库
│   ├── blanks/                   # 粗胚文件存储
│   ├── models/                   # 鞋模文件存储
│   └── results/                  # 匹配结果存储
└── package.json                   # 项目配置
```

## 4. 数据库设计

### 4.1 数据表结构

#### categories - 分类表（层级结构）
```sql
CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER,
    name TEXT NOT NULL,
    level INTEGER NOT NULL,
    path TEXT NOT NULL, -- 例如: "/鞋型/尖头"
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES categories(id)
);
```

#### blanks - 粗胚表
```sql
CREATE TABLE blanks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    metadata JSON, -- 包含: volume, vertices, faces, bounds等
    tags JSON, -- 标签数组: ["高跟", "女鞋", "36码"]
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### blank_categories - 粗胚分类关联表（多对多）
```sql
CREATE TABLE blank_categories (
    blank_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    PRIMARY KEY (blank_id, category_id),
    FOREIGN KEY (blank_id) REFERENCES blanks(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
);
```

#### models - 鞋模表
```sql
CREATE TABLE models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### matches - 匹配任务表
```sql
CREATE TABLE matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id INTEGER NOT NULL,
    selected_blank_ids JSON, -- 选中的粗胚ID数组
    status TEXT NOT NULL, -- 'processing', 'completed', 'failed'
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    FOREIGN KEY (model_id) REFERENCES models(id)
);
```

#### match_results - 匹配结果表
```sql
CREATE TABLE match_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL,
    blank_id INTEGER NOT NULL,
    result_data JSON, -- 完整的匹配结果数据
    coverage_rate REAL, -- 覆盖率
    volume_ratio REAL, -- 体积比
    p15_clearance REAL, -- P15间隙值
    min_clearance REAL, -- 最小间隙
    passed BOOLEAN, -- 是否通过
    heatmap_path TEXT, -- 热图文件路径
    ply_path TEXT, -- PLY文件路径
    FOREIGN KEY (match_id) REFERENCES matches(id),
    FOREIGN KEY (blank_id) REFERENCES blanks(id)
);
```

### 4.2 索引设计
```sql
CREATE INDEX idx_blank_categories_blank ON blank_categories(blank_id);
CREATE INDEX idx_blank_categories_category ON blank_categories(category_id);
CREATE INDEX idx_matches_model ON matches(model_id);
CREATE INDEX idx_match_results_match ON match_results(match_id);
CREATE INDEX idx_match_results_passed ON match_results(passed);
```

## 5. 核心功能模块

### 5.1 粗胚管理模块
- **功能特性**:
  - 批量上传3DM格式粗胚文件
  - 多分类关联（一个粗胚可属于多个分类）
  - 层级分类树展示与管理
  - 自定义分类创建与编辑
  - 3D预览功能
  - 元数据自动提取

- **UI组件**:
  - PrimeNG Tree (多选模式)
  - PrimeNG FileUpload
  - PrimeNG DataTable
  - Plotly WebView (3D预览)

### 5.2 匹配执行模块
- **功能特性**:
  - 上传鞋模文件
  - 选择多个粗胚（通过分类或直接选择）
  - 配置匹配参数（间隙要求、缩放等）
  - 实时进度显示
  - 控制台输出流式展示

- **处理流程**:
  1. 文件验证与拷贝
  2. 参数配置
  3. 生成Python子进程
  4. 实时接收处理进度
  5. 结果存储与展示

### 5.3 结果展示模块
- **功能特性**:
  - 多粗胚对比表格
  - 关键指标可视化
  - 热图3D展示
  - 通过/失败状态标识
  - 结果导出功能

### 5.4 历史记录模块
- **功能特性**:
  - 匹配历史查询
  - 按日期/状态/结果筛选
  - 结果对比功能
  - 重新运行历史任务

## 6. 技术实现细节

### 6.1 Python子进程管理
```typescript
// electron/services/python-runner.service.ts
export class PythonRunnerService {
    spawn(args: MatchArgs): Observable<MatchProgress> {
        const pythonPath = path.join(app.getPath('userData'), 'python-engine', 'shoe-matcher-engine');
        const child = spawn(pythonPath, ['--json-mode']);
        
        // 写入JSON参数
        child.stdin.write(JSON.stringify(args));
        child.stdin.end();
        
        // 流式读取输出
        return new Observable(observer => {
            child.stdout.on('data', (data) => {
                const lines = data.toString().split('\n');
                lines.forEach(line => {
                    if (line.trim()) {
                        observer.next(JSON.parse(line));
                    }
                });
            });
            
            child.on('close', (code) => {
                if (code === 0) {
                    observer.complete();
                } else {
                    observer.error(`Process exited with code ${code}`);
                }
            });
        });
    }
}
```

### 6.2 文件管理策略
- **上传流程**:
  1. 用户选择文件
  2. 立即复制到 `user-data/blanks/` 或 `user-data/models/`
  3. 使用UUID前缀重命名，保持原扩展名
  4. 提取元数据存入数据库
  5. 原始路径不保留

- **存储结构**:
  ```
  user-data/
  ├── blanks/
  │   ├── uuid1_鞋型A.3dm
  │   ├── uuid2_鞋型B.3dm
  │   └── ...
  ├── models/
  │   ├── uuid3_待匹配模型.3dm
  │   └── ...
  └── results/
      ├── match_001/
      │   ├── heatmaps/
      │   └── exports/
      └── ...
  ```

### 6.3 3D预览集成
```typescript
// angular-app/src/app/components/viewer-3d/viewer-3d.component.ts
export class Viewer3DComponent {
    @Input() filePath: string;
    @Input() viewType: 'blank' | 'model' | 'heatmap';
    
    private generatePreview(): void {
        // 调用Python渲染器生成HTML
        this.electronService.invoke('generate-3d-preview', {
            filePath: this.filePath,
            outputPath: this.getTempHtmlPath(),
            type: this.viewType
        }).subscribe(htmlPath => {
            // 在iframe中加载生成的HTML
            this.iframeSrc = this.sanitizer.bypassSecurityTrustResourceUrl(
                `file://${htmlPath}`
            );
        });
    }
}
```

### 6.4 实时进度处理
```typescript
// 定义进度消息格式
interface ProgressMessage {
    type: 'log' | 'progress' | 'result' | 'error';
    stage: 'preparing' | 'processing' | 'analyzing' | 'complete';
    progress: number; // 0-100
    message: string;
    details?: any;
    timestamp: number;
}
```

## 7. UI/UX设计

### 7.1 主界面布局
```
┌────────────────────────────────────────────────────────────┐
│  鞋模智能匹配系统 v1.0.0          [－] [口] [×]            │
├────────────────────────────────────────────────────────────┤
│ ┌────────────┬──────────────────────────────────────────┐  │
│ │            │                                          │  │
│ │  侧边菜单   │              主工作区                     │  │
│ │            │                                          │  │
│ │ ▼ 粗胚管理  │  ┌─────────────┬─────────────────┐     │  │
│ │   ├ 尖头   │  │             │                 │     │  │
│ │   ├ 圆头   │  │  3D预览区    │   操作面板      │     │  │
│ │   └ 方头   │  │             │                 │     │  │
│ │            │  │  [Plotly]   │   匹配参数:     │     │  │
│ │ ▶ 开始匹配  │  │             │   □ 间隙: 2mm  │     │  │
│ │            │  │             │   □ 缩放: 是   │     │  │
│ │ ▶ 历史记录  │  │             │   □ 阈值: P15  │     │  │
│ │            │  └─────────────┴─────────────────┘     │  │
│ │ ▶ 系统设置  │                                          │  │
│ │            │  ┌────────────────────────────────┐     │  │
│ │            │  │     实时控制台输出               │     │  │
│ │            │  │  > 正在处理...                 │     │  │
│ │            │  │  > 匹配进度: 45%               │     │  │
│ │            │  └────────────────────────────────┘     │  │
│ └────────────┴──────────────────────────────────────────┘  │
│ 就绪 | 内存: 512MB | 任务: 0                               │
└────────────────────────────────────────────────────────────┘
```

### 7.2 交互流程
1. **粗胚准备阶段**:
   - 用户上传粗胚文件
   - 分配到多个分类
   - 预览3D模型

2. **匹配执行阶段**:
   - 上传鞋模文件
   - 选择粗胚（通过分类树多选）
   - 设置匹配参数
   - 开始匹配
   - 查看实时进度

3. **结果查看阶段**:
   - 查看对比表格
   - 查看热图
   - 导出结果

## 8. 构建与分发

### 8.1 PyInstaller配置
```python
# python-engine/build.spec
a = Analysis(['main.py'],
             pathex=['./'],
             binaries=[
                 ('engine/cppcore.so', 'engine'),
             ],
             datas=[
                 ('engine/*.py', 'engine'),
             ],
             hiddenimports=[
                 'rhino3dm',
                 'plotly',
                 'trimesh',
                 'numpy',
                 'scipy',
                 'sklearn'
             ],
             excludes=['matplotlib', 'PIL', 'tkinter'])

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='shoe-matcher-engine',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=True,
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None,
          onefile=True)
```

### 8.2 Electron Builder配置
```json
{
  "build": {
    "appId": "com.shoelast.matcher",
    "productName": "鞋模智能匹配系统",
    "directories": {
      "output": "dist"
    },
    "files": [
      "electron/**/*",
      "angular-app/dist/**/*",
      "python-engine/dist/**/*",
      "database/schema.sql"
    ],
    "extraResources": [
      {
        "from": "python-engine/dist",
        "to": "python-engine",
        "filter": ["**/*"]
      }
    ],
    "mac": {
      "category": "public.app-category.productivity",
      "icon": "resources/icons/icon.icns",
      "hardenedRuntime": true,
      "gatekeeperAssess": false,
      "entitlements": "build/entitlements.mac.plist",
      "entitlementsInherit": "build/entitlements.mac.plist"
    },
    "win": {
      "target": "nsis",
      "icon": "resources/icons/icon.ico"
    },
    "nsis": {
      "oneClick": false,
      "allowToChangeInstallationDirectory": true,
      "language": "2052",
      "menuCategory": true,
      "artifactName": "鞋模智能匹配系统-${version}-setup.${ext}"
    },
    "linux": {
      "target": "AppImage",
      "icon": "resources/icons"
    }
  }
}
```

## 9. 性能优化策略

### 9.1 懒加载实现
- Angular路由懒加载
- 虚拟滚动列表（大数据集）
- 按需加载3D预览
- 分页查询历史记录

### 9.2 缓存策略
- 3D预览HTML缓存
- 元数据缓存
- 查询结果缓存
- 分类树缓存

### 9.3 资源管理
- 定期清理临时文件
- 压缩存储历史结果
- 限制控制台输出缓冲区
- 内存使用监控

## 10. 错误处理

### 10.1 错误类型
- 文件格式错误
- Python进程崩溃
- 数据库操作失败
- 内存不足
- 网络错误（如有远程功能）

### 10.2 处理策略
- 快速失败，清晰提示
- 自动保存进度
- 错误日志记录
- 崩溃报告收集
- 恢复机制

## 11. 安全考虑

### 11.1 进程隔离
- 使用contextBridge限制IPC
- 禁用nodeIntegration
- 启用contextIsolation

### 11.2 文件安全
- 文件类型验证
- 文件大小限制
- 路径遍历防护
- 临时文件权限控制

## 12. 部署要求

### 12.1 系统要求
- **macOS**: 10.14+
- **Windows**: Windows 10 1903+
- **内存**: 最低4GB，推荐8GB
- **存储**: 最低2GB可用空间
- **处理器**: 64位，多核推荐

### 12.2 依赖要求
- 无需预装Python
- 无需预装数据库
- 所有依赖打包在应用内

## 13. 版本规划

### v1.0.0 - 基础版本
- 核心匹配功能
- 基本UI界面
- 单机版本

### v1.1.0 - 增强版本
- 批量处理优化
- 更多3D查看选项
- 性能优化

### v1.2.0 - 专业版本
- 高级筛选功能
- 报表生成
- 数据导入导出

## 14. 总结

本设计文档定义了鞋模智能匹配桌面应用的完整技术架构和实现方案。系统采用Electron + Angular + Python的混合架构，通过子进程方式集成现有的匹配引擎，实现了跨平台的桌面应用解决方案。

关键设计决策：
1. 使用子进程而非服务模式，确保隔离性和稳定性
2. 采用SQLite本地数据库，支持复杂查询和多对多关系
3. 通过PyInstaller打包Python引擎，避免环境依赖
4. 使用Plotly WebView实现3D预览，复用现有渲染代码
5. 实时流式输出，提供良好的用户反馈

通过以上设计，系统能够满足专业用户的鞋模匹配需求，提供直观、高效、可靠的桌面应用体验。
