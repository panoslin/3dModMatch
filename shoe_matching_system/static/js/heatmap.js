/**
 * 3D热力图计算和渲染工具
 * 用于显示匹配质量和余量分布
 */

class HeatmapRenderer {
    constructor(scene, model) {
        this.scene = scene;
        this.model = model;
        this.heatmapPoints = [];
        this.heatmapGeometry = null;
        this.heatmapMaterial = null;
        this.heatmapMesh = null;
    }
    
    /**
     * 生成热力图数据
     * @param {Object} matchData - 匹配数据
     * @param {number} marginDistance - 余量距离
     */
    generateHeatmap(matchData, marginDistance) {
        // 清除现有热力图
        this.clearHeatmap();
        
        // 生成点云数据
        this.generatePointCloud(matchData, marginDistance);
        
        // 创建热力图几何体
        this.createHeatmapGeometry();
        
        // 应用热力图材质
        this.applyHeatmapMaterial();
        
        // 添加到场景
        this.scene.add(this.heatmapMesh);
    }
    
    /**
     * 生成点云数据
     */
    generatePointCloud(matchData, marginDistance) {
        const { analysis_details } = matchData;
        const { avg_margin, min_margin, max_margin, margin_coverage } = analysis_details;
        
        // 模拟点云数据（实际应用中应该从真实的3D模型数据生成）
        const pointCount = 1000;
        this.heatmapPoints = [];
        
        for (let i = 0; i < pointCount; i++) {
            // 生成随机点位置
            const x = (Math.random() - 0.5) * 4; // -2 到 2
            const y = (Math.random() - 0.5) * 2; // -1 到 1
            const z = (Math.random() - 0.5) * 2; // -1 到 1
            
            // 计算余量（模拟）
            const distance = Math.sqrt(x * x + y * y + z * z);
            const margin = Math.max(0, distance - 1.0); // 假设模型半径为1
            
            // 计算热力图强度
            const intensity = this.calculateIntensity(margin, marginDistance);
            
            this.heatmapPoints.push({
                position: [x, y, z],
                intensity: intensity,
                margin: margin
            });
        }
    }
    
    /**
     * 计算热力图强度
     */
    calculateIntensity(margin, targetMargin) {
        if (margin < 0) {
            return 1.0; // 红色：余量不足
        } else if (margin < targetMargin * 0.5) {
            return 0.8; // 橙色：余量较少
        } else if (margin < targetMargin) {
            return 0.5; // 黄色：余量适中
        } else if (margin < targetMargin * 1.5) {
            return 0.3; // 浅绿色：余量充足
        } else {
            return 0.1; // 深绿色：余量过多
        }
    }
    
    /**
     * 创建热力图几何体
     */
    createHeatmapGeometry() {
        const positions = [];
        const colors = [];
        const sizes = [];
        
        this.heatmapPoints.forEach(point => {
            positions.push(...point.position);
            
            // 根据强度设置颜色
            const color = this.intensityToColor(point.intensity);
            colors.push(...color);
            
            // 根据强度设置点大小
            const size = 0.02 + point.intensity * 0.03;
            sizes.push(size);
        });
        
        this.heatmapGeometry = new THREE.BufferGeometry();
        this.heatmapGeometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
        this.heatmapGeometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
        this.heatmapGeometry.setAttribute('size', new THREE.Float32BufferAttribute(sizes, 1));
    }
    
    /**
     * 强度转颜色
     */
    intensityToColor(intensity) {
        if (intensity > 0.8) {
            return [1.0, 0.0, 0.0]; // 红色：问题区域
        } else if (intensity > 0.6) {
            return [1.0, 0.5, 0.0]; // 橙色：警告区域
        } else if (intensity > 0.4) {
            return [1.0, 1.0, 0.0]; // 黄色：注意区域
        } else if (intensity > 0.2) {
            return [0.0, 1.0, 0.0]; // 绿色：正常区域
        } else {
            return [0.0, 0.5, 0.0]; // 深绿色：优秀区域
        }
    }
    
    /**
     * 应用热力图材质
     */
    applyHeatmapMaterial() {
        this.heatmapMaterial = new THREE.ShaderMaterial({
            uniforms: {
                time: { value: 0.0 }
            },
            vertexShader: `
                attribute float size;
                attribute vec3 color;
                varying vec3 vColor;
                varying float vIntensity;
                
                void main() {
                    vColor = color;
                    vIntensity = size;
                    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
                    gl_PointSize = size * (300.0 / -mvPosition.z);
                    gl_Position = projectionMatrix * mvPosition;
                }
            `,
            fragmentShader: `
                varying vec3 vColor;
                varying float vIntensity;
                uniform float time;
                
                void main() {
                    // 创建脉动效果
                    float pulse = sin(time * 2.0) * 0.1 + 0.9;
                    vec3 finalColor = vColor * pulse;
                    
                    // 添加发光效果
                    float glow = vIntensity * 0.5;
                    finalColor += glow * vec3(1.0, 1.0, 1.0);
                    
                    gl_FragColor = vec4(finalColor, 0.8);
                }
            `,
            transparent: true,
            vertexColors: true
        });
        
        this.heatmapMesh = new THREE.Points(this.heatmapGeometry, this.heatmapMaterial);
    }
    
    /**
     * 更新热力图动画
     */
    updateAnimation(time) {
        if (this.heatmapMaterial && this.heatmapMaterial.uniforms) {
            this.heatmapMaterial.uniforms.time.value = time;
        }
    }
    
    /**
     * 清除热力图
     */
    clearHeatmap() {
        if (this.heatmapMesh) {
            this.scene.remove(this.heatmapMesh);
            this.heatmapMesh = null;
        }
        
        if (this.heatmapGeometry) {
            this.heatmapGeometry.dispose();
            this.heatmapGeometry = null;
        }
        
        if (this.heatmapMaterial) {
            this.heatmapMaterial.dispose();
            this.heatmapMaterial = null;
        }
        
        this.heatmapPoints = [];
    }
    
    /**
     * 获取热力图统计信息
     */
    getStatistics() {
        if (this.heatmapPoints.length === 0) {
            return null;
        }
        
        const intensities = this.heatmapPoints.map(p => p.intensity);
        const margins = this.heatmapPoints.map(p => p.margin);
        
        return {
            totalPoints: this.heatmapPoints.length,
            averageIntensity: intensities.reduce((a, b) => a + b, 0) / intensities.length,
            averageMargin: margins.reduce((a, b) => a + b, 0) / margins.length,
            minMargin: Math.min(...margins),
            maxMargin: Math.max(...margins),
            problemAreas: intensities.filter(i => i > 0.8).length,
            warningAreas: intensities.filter(i => i > 0.6 && i <= 0.8).length,
            normalAreas: intensities.filter(i => i <= 0.6).length
        };
    }
}

/**
 * 截面分析工具
 */
class SectionAnalyzer {
    constructor(scene, model) {
        this.scene = scene;
        this.model = model;
        this.sectionPlane = null;
        this.sectionLine = null;
    }
    
    /**
     * 创建截面平面
     */
    createSectionPlane(position, normal) {
        // 清除现有截面
        this.clearSection();
        
        // 创建截面平面几何体
        const planeGeometry = new THREE.PlaneGeometry(10, 10);
        const planeMaterial = new THREE.MeshBasicMaterial({
            color: 0xff0000,
            side: THREE.DoubleSide,
            transparent: true,
            opacity: 0.3
        });
        
        this.sectionPlane = new THREE.Mesh(planeGeometry, planeMaterial);
        this.sectionPlane.position.copy(position);
        this.sectionPlane.lookAt(normal);
        
        this.scene.add(this.sectionPlane);
        
        // 创建截面线
        this.createSectionLine(position, normal);
    }
    
    /**
     * 创建截面线
     */
    createSectionLine(position, normal) {
        // 这里应该计算实际的截面轮廓
        // 简化版本：创建一条直线
        const lineGeometry = new THREE.BufferGeometry().setFromPoints([
            new THREE.Vector3(-2, 0, 0),
            new THREE.Vector3(2, 0, 0)
        ]);
        
        const lineMaterial = new THREE.LineBasicMaterial({
            color: 0x00ff00,
            linewidth: 3
        });
        
        this.sectionLine = new THREE.Line(lineGeometry, lineMaterial);
        this.sectionLine.position.copy(position);
        this.sectionLine.lookAt(normal);
        
        this.scene.add(this.sectionLine);
    }
    
    /**
     * 清除截面
     */
    clearSection() {
        if (this.sectionPlane) {
            this.scene.remove(this.sectionPlane);
            this.sectionPlane = null;
        }
        
        if (this.sectionLine) {
            this.scene.remove(this.sectionLine);
            this.sectionLine = null;
        }
    }
    
    /**
     * 移动截面平面
     */
    moveSectionPlane(direction) {
        if (this.sectionPlane && this.sectionLine) {
            const moveDistance = 0.1;
            this.sectionPlane.position.add(direction.multiplyScalar(moveDistance));
            this.sectionLine.position.copy(this.sectionPlane.position);
        }
    }
}

/**
 * 动画控制器
 */
class AnimationController {
    constructor() {
        this.animations = [];
        this.isPlaying = false;
        this.currentTime = 0;
    }
    
    /**
     * 添加匹配过程动画
     */
    addMatchingAnimation(shoeModel, blankModel, matchData) {
        const animation = {
            type: 'matching',
            shoeModel: shoeModel,
            blankModel: blankModel,
            matchData: matchData,
            duration: 3000, // 3秒
            startTime: 0
        };
        
        this.animations.push(animation);
    }
    
    /**
     * 播放动画
     */
    play() {
        this.isPlaying = true;
        this.currentTime = 0;
        this.animate();
    }
    
    /**
     * 停止动画
     */
    stop() {
        this.isPlaying = false;
    }
    
    /**
     * 动画循环
     */
    animate() {
        if (!this.isPlaying) return;
        
        this.currentTime += 16; // 约60fps
        
        this.animations.forEach(animation => {
            this.updateAnimation(animation);
        });
        
        requestAnimationFrame(() => this.animate());
    }
    
    /**
     * 更新单个动画
     */
    updateAnimation(animation) {
        const progress = (this.currentTime - animation.startTime) / animation.duration;
        
        if (progress >= 1) {
            // 动画完成
            this.completeAnimation(animation);
            return;
        }
        
        switch (animation.type) {
            case 'matching':
                this.updateMatchingAnimation(animation, progress);
                break;
        }
    }
    
    /**
     * 更新匹配动画
     */
    updateMatchingAnimation(animation, progress) {
        const { shoeModel, blankModel } = animation;
        
        if (progress < 0.3) {
            // 第一阶段：鞋模和粗胚分离
            const separation = progress / 0.3;
            shoeModel.position.x = -separation * 2;
            blankModel.position.x = separation * 2;
        } else if (progress < 0.7) {
            // 第二阶段：分析过程
            const analysis = (progress - 0.3) / 0.4;
            // 可以添加分析效果，如旋转、缩放等
        } else {
            // 第三阶段：匹配结果
            const result = (progress - 0.7) / 0.3;
            // 显示匹配结果
        }
    }
    
    /**
     * 完成动画
     */
    completeAnimation(animation) {
        // 重置模型位置
        if (animation.shoeModel) {
            animation.shoeModel.position.set(0, 0, 0);
        }
        if (animation.blankModel) {
            animation.blankModel.position.set(0, 0, 0);
        }
    }
}

// 导出类
window.HeatmapRenderer = HeatmapRenderer;
window.SectionAnalyzer = SectionAnalyzer;
window.AnimationController = AnimationController;
