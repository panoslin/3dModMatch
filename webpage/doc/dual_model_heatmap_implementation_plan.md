# 双模型叠加热力图实施计划

## 📋 项目概述

### 目标
将当前基于Python Plotly的热力图系统升级为基于Three.js的双模型叠加热力图，实现：
- 鞋模与粗胚的真实空间叠加显示
- 基于间隙的实时颜色映射（红色=危险，绿色=安全）
- 高性能的前端WebGL渲染
- 直观的生产质量控制界面

### 性能目标
| 指标 | 当前Plotly | 目标Three.js | 改进幅度 |
|------|------------|--------------|----------|
| 数据传输 | 5-15MB | 50-200KB | 97%+ 减少 |
| 加载时间 | 5-10秒 | <1秒 | 90%+ 减少 |
| 服务器计算 | 10-30秒 | 2-5秒 | 80%+ 减少 |
| 交互性能 | 中等 | 优秀 | 显著提升 |

## 🏗️ 系统架构设计

### 技术栈
- **前端**: Three.js WebGL渲染 + 现有AdvancedModelViewer系统
- **后端**: Django REST API + 轻量级间隙计算
- **数据格式**: JSON间隙数据 + GLB模型文件
- **对齐算法**: cppcore变换矩阵精确还原

### 架构流程图
```
后端cppcore对齐 → 变换矩阵保存 → 前端GLB加载 → 精确变换应用 → 双模型叠加 → 间隙着色
```

## 📅 实施时间表

### Phase 1: 核心功能开发 (5-6天)

#### Day 1-2: 后端API重构
- [ ] 创建轻量级间隙计算API (`apps/matching/views.py`)
- [ ] 优化对齐数据保存结构 (`models.py`)
- [ ] 实现坐标系标准化函数
- [ ] 添加数据缓存机制

#### Day 3-4: 前端核心渲染器
- [ ] 创建`AlignmentRestorer`类（精确对齐还原）
- [ ] 创建`DualModelHeatmapRenderer`类（双模型渲染）
- [ ] 实现变换矩阵解析和应用
- [ ] 基础间隙颜色映射

#### Day 5-6: 系统集成
- [ ] 集成到现有`AdvancedModelViewer`
- [ ] 修改匹配结果页面调用
- [ ] 基础UI控制面板
- [ ] 降级兼容机制

### Phase 2: 交互功能增强 (3-4天)

#### Day 7-8: 交互控制
- [ ] 模型显示/隐藏切换
- [ ] 透明度动态调节
- [ ] 间隙阈值实时调整
- [ ] 统计信息显示

#### Day 9-10: 用户体验优化
- [ ] 视角预设和动画
- [ ] 加载状态和进度指示
- [ ] 错误处理和用户提示
- [ ] 移动端响应式适配

### Phase 3: 高级特性和优化 (2-3天，可选)

#### Day 11-12: 性能优化
- [ ] WebGL着色器加速颜色计算
- [ ] 智能缓存和内存管理
- [ ] 分级渲染优化
- [ ] GPU计算迁移

#### Day 13: 高级可视化
- [ ] 动态剖面显示
- [ ] 问题区域自动标注
- [ ] 3D标签和测量工具

## 💻 核心代码实现

### 1. 后端API设计

```python
# apps/matching/views.py - 新增API端点

@api_view(['GET'])
def get_alignment_data_api(request, task_id, result_index):
    """返回cppcore对齐数据"""
    try:
        task = MatchingTask.objects.get(task_id=task_id)
        results = task.result_data['results']
        result = results[int(result_index)]
        
        alignment_data = {
            'target_id': task.shoe_model.id,
            'candidate_id': result.get('blank_id'),
            'transform_matrix': result.get('transform', []),  # 4x4矩阵
            'mirrored': result.get('mirrored', False),
            'chamfer_distance': result.get('chamfer', 0),
            'coordinate_system': {
                'units': 'mm',
                'right_handed': True,
                'y_up': True
            }
        }
        
        return Response({'success': True, 'data': alignment_data})
        
    except Exception as e:
        return Response({'success': False, 'error': str(e)})

@api_view(['GET']) 
def get_clearance_data_api(request, task_id, result_index):
    """返回轻量级间隙数据"""
    try:
        # 轻量级间隙计算（不生成Plotly图形）
        clearance_data = calculate_clearance_lightweight(
            target_path, blank_path, transform_matrix
        )
        
        return Response({
            'success': True,
            'data': {
                'clearances': clearance_data['clearances'].tolist(),
                'min_clearance': float(clearance_data['min_clearance']),
                'max_clearance': float(clearance_data['max_clearance']),
                'vertex_count': len(clearance_data['clearances'])
            }
        })
        
    except Exception as e:
        return Response({'success': False, 'error': str(e)})
```

### 2. 前端核心类架构

```javascript
// static/js/dual-model-heatmap.js

/**
 * 对齐还原器 - 精确还原cppcore对齐结果
 */
class AlignmentRestorer {
    constructor(viewer) {
        this.viewer = viewer;
        this.targetModel = null;
        this.candidateModel = null;
        this.alignmentData = null;
    }

    async restoreAlignment(taskId, resultIndex) {
        // 1. 获取对齐数据
        this.alignmentData = await this.fetchAlignmentData(taskId, resultIndex);
        
        // 2. 加载原始模型
        await this.loadOriginalModels();
        
        // 3. 应用精确变换
        this.applyExactTransformation();
        
        // 4. 验证对齐质量
        this.validateAlignment();
    }

    applyExactTransformation() {
        const transformMatrix = this.parseTransformMatrix(
            this.alignmentData.transform_matrix
        );
        
        if (this.alignmentData.mirrored) {
            const mirrorMatrix = this.createMirrorMatrix('YZ');
            transformMatrix.premultiply(mirrorMatrix);
        }
        
        this.candidateModel.applyMatrix4(transformMatrix);
        this.candidateModel.updateMatrixWorld(true);
    }
}

/**
 * 双模型热力图渲染器
 */
class DualModelHeatmapRenderer {
    constructor(viewer) {
        this.viewer = viewer;
        this.settings = {
            targetOpacity: 0.3,
            candidateOpacity: 1.0,
            dangerThreshold: 1.0,    // 红色阈值
            warningThreshold: 2.5,   // 黄色阈值
            colorRange: { min: 0, max: 10 }
        };
    }

    async loadDualModelHeatmap(taskId, resultIndex) {
        try {
            // 1. 对齐模型
            const alignmentRestorer = new AlignmentRestorer(this.viewer);
            await alignmentRestorer.restoreAlignment(taskId, resultIndex);
            
            // 2. 获取间隙数据
            const clearanceData = await this.fetchClearanceData(taskId, resultIndex);
            
            // 3. 应用双模型渲染
            this.setupTargetModel(alignmentRestorer.targetModel);
            await this.applyClearanceColoring(
                alignmentRestorer.candidateModel, 
                clearanceData
            );
            
            // 4. 添加交互控制
            this.setupInteractiveControls();
            
        } catch (error) {
            console.error('双模型热力图加载失败:', error);
            throw error;
        }
    }

    setupTargetModel(targetModel) {
        // 设置参考鞋模为半透明灰色
        targetModel.traverse((child) => {
            if (child.isMesh) {
                child.material = new THREE.MeshLambertMaterial({
                    color: 0x888888,
                    transparent: true,
                    opacity: this.settings.targetOpacity,
                    wireframe: false
                });
                child.renderOrder = 1;
            }
        });
    }

    async applyClearanceColoring(candidateModel, clearanceData) {
        const colors = this.generateDistanceColors(clearanceData.clearances);
        
        candidateModel.traverse((child) => {
            if (child.isMesh) {
                const geometry = child.geometry;
                geometry.setAttribute('color', 
                    new THREE.Float32BufferAttribute(colors, 3));
                
                child.material = new THREE.MeshLambertMaterial({
                    vertexColors: true,
                    transparent: false,
                    side: THREE.DoubleSide
                });
                
                child.material.needsUpdate = true;
            }
        });
    }

    generateDistanceColors(distances) {
        const colors = [];
        
        distances.forEach(distance => {
            let color;
            
            if (distance < 0) {
                // 穿模 - 深红色
                color = { r: 0.8, g: 0.0, b: 0.0 };
            } else if (distance < this.settings.dangerThreshold) {
                // 危险区域 - 红色渐变
                const ratio = distance / this.settings.dangerThreshold;
                color = { r: 1.0, g: ratio * 0.3, b: 0.0 };
            } else if (distance < this.settings.warningThreshold) {
                // 警告区域 - 红到黄渐变
                const ratio = (distance - this.settings.dangerThreshold) / 
                             (this.settings.warningThreshold - this.settings.dangerThreshold);
                color = { r: 1.0, g: ratio * 0.8, b: 0.0 };
            } else {
                // 安全区域 - 黄到绿渐变
                const ratio = Math.min(1, (distance - this.settings.warningThreshold) / 
                                      (this.settings.colorRange.max - this.settings.warningThreshold));
                color = { r: 1.0 - ratio, g: 1.0, b: 0.0 };
            }
            
            colors.push(color.r, color.g, color.b);
        });
        
        return colors;
    }
}
```

### 3. 前端集成代码

```javascript
// static/js/matching.js - 修改现有代码

class MatchingResultsManager {
    async loadHeatmapWithStatus(taskId, resultIndex) {
        // 检查Three.js查看器和双模型支持
        if (this.threeViewer && window.DualModelHeatmapRenderer) {
            try {
                $('#heatmap-preview').html(`
                    <div class="heatmap-loading">
                        <div class="loader-spinner"></div>
                        <div class="loader-text">正在生成双模型热力图...</div>
                    </div>
                `);
                
                // 使用Three.js双模型热力图
                const heatmapRenderer = new DualModelHeatmapRenderer(this.threeViewer);
                await heatmapRenderer.loadDualModelHeatmap(taskId, resultIndex);
                
                this.showHeatmapControls();
                
            } catch (error) {
                console.error('Three.js热力图失败，降级到Plotly:', error);
                this.loadPlotlyHeatmap(taskId, resultIndex);  // 降级方案
            }
        } else {
            // 降级到原有Plotly方案
            this.loadPlotlyHeatmap(taskId, resultIndex);
        }
    }
    
    showHeatmapControls() {
        // 显示双模型控制面板
        const controlsHtml = `
            <div class="dual-model-controls">
                <h4>双模型显示控制</h4>
                <div class="control-row">
                    <label>
                        <input type="checkbox" id="show-target" checked>
                        显示鞋模（参考）
                    </label>
                </div>
                <div class="control-row">
                    <label>鞋模透明度:</label>
                    <input type="range" id="target-opacity" min="0" max="100" value="30" step="5">
                    <span id="target-opacity-value">30%</span>
                </div>
                <!-- 更多控制... -->
            </div>
        `;
        
        $('#heatmap-controls').html(controlsHtml).show();
    }
}
```

## 🎯 风险评估和缓解策略

### 主要风险点

#### 1. 空间对齐精度 (高风险)
**风险**: cppcore对齐结果在Three.js中无法精确还原
**影响**: 错误的颜色显示，误导生产决策
**缓解策略**:
- 实施多层验证机制（边界框、控制点）
- 添加自动微调校正
- 提供手动精调接口
- 完整的回归测试

#### 2. 性能瓶颈 (中风险)
**风险**: 双模型渲染导致性能下降
**影响**: 交互卡顿，用户体验差
**缓解策略**:
- 分级渲染和LOD优化
- GPU着色器加速
- 智能缓存机制
- 性能监控和自动调节

#### 3. 系统集成复杂性 (中风险) 
**风险**: 与现有架构集成困难
**影响**: 开发延期，功能不稳定
**缓解策略**:
- 模块化设计，最小化影响
- 保留Plotly降级方案
- 渐进式部署
- 充分的集成测试

## 🧪 测试验证计划

### 单元测试
- [ ] 变换矩阵解析和应用
- [ ] 颜色映射算法
- [ ] 坐标系标准化
- [ ] 边界框验证

### 集成测试
- [ ] API端点数据一致性
- [ ] 前后端对齐精度
- [ ] 多浏览器兼容性
- [ ] 移动端性能

### 用户验收测试
- [ ] 直观性和易用性
- [ ] 生产场景准确性
- [ ] 性能基准达标
- [ ] 培训和文档

### 测试数据集
- [ ] 标准鞋模测试集（5个不同类型）
- [ ] 极端情况测试（穿模、大间隙）
- [ ] 性能压力测试（大模型、多用户）
- [ ] 兼容性测试（不同设备和浏览器）

## 🚀 部署计划

### 开发环境配置
```bash
# 1. 更新前端依赖
cd /root/3dModMatch/webpage/shoe_matcher_web/static/js/
# 添加新的JS文件

# 2. 数据库迁移（如有模型更改）
python manage.py makemigrations
python manage.py migrate

# 3. 静态文件收集
python manage.py collectstatic
```

### 生产部署步骤
1. **预部署验证**
   - 完整功能测试
   - 性能基准测试
   - 数据备份

2. **分步部署**
   - 后端API先上线（向后兼容）
   - 前端功能灰度发布
   - 全量切换

3. **监控和回滚**
   - 实时性能监控
   - 错误日志跟踪
   - 快速回滚预案

## 📖 文档和培训

### 技术文档
- [ ] API接口文档
- [ ] 前端组件使用指南
- [ ] 部署和维护手册
- [ ] 故障排查指南

### 用户文档
- [ ] 双模型热力图使用教程
- [ ] 控制面板功能说明
- [ ] 最佳实践指导
- [ ] 常见问题FAQ

## 📈 成功指标

### 技术指标
- 数据传输量减少 >95%
- 加载时间改善 >90%
- 服务器计算时间减少 >80%
- 前端渲染FPS >30

### 业务指标
- 用户使用率提升 >50%
- 问题识别准确率 >98%
- 生产决策效率提升
- 用户满意度评分 >4.5/5

## 🔄 后续优化方向

### Phase 4: 高级分析功能
- 自动质量评估报告
- 历史对比分析
- 批量处理模式
- 数据导出和分享

### Phase 5: AI增强功能
- 智能问题区域识别
- 自动优化建议
- 预测性质量控制
- 机器学习模型集成

---

## 📝 实施检查清单

### 准备阶段
- [ ] 开发环境搭建完成
- [ ] 测试数据集准备完毕
- [ ] 项目依赖关系梳理
- [ ] 团队角色分工确定

### 开发阶段
- [ ] 后端API开发完成并测试
- [ ] 前端核心功能开发完成
- [ ] 系统集成测试通过
- [ ] 性能基准测试达标

### 部署阶段
- [ ] 生产环境配置验证
- [ ] 数据库迁移脚本准备
- [ ] 监控和日志系统就绪
- [ ] 回滚方案制定完毕

### 交付阶段
- [ ] 用户培训完成
- [ ] 技术文档交付
- [ ] 维护流程建立
- [ ] 成功指标达成确认

---

*本实施计划将持续更新，确保项目按时高质量交付。*
