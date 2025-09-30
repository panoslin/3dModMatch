/**
 * 双模型叠加热力图系统
 * 用于3D鞋模与粗胚的实时对齐显示和间隙可视化
 */

/**
 * 对齐还原器 - 精确还原cppcore对齐结果
 */
class AlignmentRestorer {
    constructor(viewer, progressCallback = null) {
        this.viewer = viewer;
        this.targetModel = null;
        this.candidateModel = null;
        this.alignmentData = null;
        this.originalTargetMatrix = null;
        this.originalCandidateMatrix = null;
        this.progressCallback = progressCallback; // 进度回调函数
    }

    /**
     * 还原对齐结果
     * @param {string} taskId - 任务ID
     * @param {number} resultIndex - 结果索引
     * @returns {Promise<boolean>} 是否成功
     */
    async restoreAlignment(taskId, resultIndex) {
        try {
            console.log(`开始还原对齐: ${taskId}/${resultIndex}`);
            
            // 1. 获取对齐数据
            this.alignmentData = await this.fetchAlignmentData(taskId, resultIndex);
            if (!this.alignmentData) {
                throw new Error('无法获取对齐数据');
            }

            console.log('对齐数据:', this.alignmentData);
            
            // 2. 加载原始模型
            await this.loadOriginalModels(taskId, resultIndex);
            
            // 3. 应用精确变换
            this.applyExactTransformation();
            
            // 4. 验证对齐质量
            const isValid = this.validateAlignment();
            
            if (!isValid) {
                console.warn('对齐质量验证失败，但继续执行');
            }
            
            console.log('对齐还原完成');
            return true;
            
        } catch (error) {
            console.error('对齐还原失败:', error);
            throw error;
        }
    }

    /**
     * 获取对齐数据
     */
    async fetchAlignmentData(taskId, resultIndex) {
        try {
            const response = await fetch(
                `/api/matching/${taskId}/alignment-data/${resultIndex}/`,
                {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': this.getCsrfToken()
                    }
                }
            );

            const data = await response.json();
            
            if (!response.ok || !data.success) {
                throw new Error(data.message || '获取对齐数据失败');
            }

            return data.data;
            
        } catch (error) {
            console.error('获取对齐数据失败:', error);
            throw error;
        }
    }

    /**
     * 加载原始模型
     */
    async loadOriginalModels(taskId, resultIndex) {
        try {
            // 获取当前Three.js场景中的模型
            const scene = this.viewer?.scene;
            
            if (!scene) {
                throw new Error('Viewer scene 未初始化');
            }
            
            const loadedModels = [];
            
            // 收集所有网格对象
            scene.traverse((child) => {
                if (child.isMesh && child.parent !== scene) {
                    loadedModels.push(child);
                }
            });

            console.log(`找到 ${loadedModels.length} 个已加载的模型`);

            // 如果场景中没有模型，需要加载它们
            if (loadedModels.length === 0) {
                console.log('场景为空，开始加载模型...');
                await this.loadTargetAndCandidateModels(taskId, resultIndex);
                return;
            }

            // 假设前两个模型分别是target和candidate
            // 实际项目中应该根据模型ID或名称来识别
            if (loadedModels.length >= 2) {
                this.targetModel = loadedModels[0];  // 鞋模
                this.candidateModel = loadedModels[1];  // 粗胚
                
                // 保存原始变换矩阵
                this.originalTargetMatrix = this.targetModel.matrix.clone();
                this.originalCandidateMatrix = this.candidateModel.matrix.clone();
                
                console.log('模型识别完成:', {
                    target: this.targetModel.name || 'Target',
                    candidate: this.candidateModel.name || 'Candidate'
                });
                
            } else if (loadedModels.length === 1) {
                // 如果只有一个模型，尝试重新加载candidate模型
                this.targetModel = loadedModels[0];
                await this.loadCandidateModel(taskId, resultIndex);
                
            } else {
                throw new Error('场景中没有找到足够的模型');
            }
            
        } catch (error) {
            console.error('加载原始模型失败:', error);
            throw error;
        }
    }
    
    /**
     * 加载目标和候选模型
     */
    async loadTargetAndCandidateModels(taskId, resultIndex) {
        try {
            // 从对齐数据中获取模型信息
            const targetId = this.alignmentData.target_id;
            const candidateId = this.alignmentData.candidate_id;
            const candidateName = this.alignmentData.candidate_name;
            const targetType = this.alignmentData.target_type;
            const candidateType = this.alignmentData.candidate_type;
            
            console.log(`加载模型: target=${targetId} (${targetType}), candidate=${candidateId || candidateName} (${candidateType})`);
            
            // 构建目标模型 URL
            const targetUrl = `/api/lod/${targetType}/${targetId}/data/?level=detail&engine=threejs`;
            
            // 构建候选模型 URL
            let candidateUrl;
            if (candidateId) {
                // 如果有 candidate_id，使用标准的 ID 端点
                candidateUrl = `/api/lod/${candidateType}/${candidateId}/data/?level=detail&engine=threejs`;
            } else {
                // 如果没有 ID，尝试直接使用文件路径（需要特殊处理）
                throw new Error(`候选模型 ID 未找到。候选模型名称: ${candidateName}。请确保后端已正确查询并返回 candidate_id。`);
            }
            
            // 加载目标模型
            if (this.progressCallback) {
                this.progressCallback('正在加载鞋模...', 25);
            }
            await this.loadTargetModel(targetUrl);
            
            // 加载候选模型
            if (this.progressCallback) {
                this.progressCallback('正在加载粗胚模型...', 60);
            }
            await this.loadCandidateModel(candidateUrl);
            
            if (this.progressCallback) {
                this.progressCallback('模型加载完成', 90);
            }
            console.log('模型加载完成');
            
        } catch (error) {
            console.error('加载目标和候选模型失败:', error);
            throw error;
        }
    }

    /**
     * 加载目标模型
     */
    async loadTargetModel(modelUrl) {
        try {
            console.log('加载目标模型:', modelUrl);
            
            // 检查 GLTFLoader 是否可用
            if (!THREE.GLTFLoader) {
                throw new Error('THREE.GLTFLoader 未加载，请确保已引入 GLTFLoader.js');
            }
            
            const loader = new THREE.GLTFLoader();
            const gltf = await new Promise((resolve, reject) => {
                loader.load(
                    modelUrl,
                    (gltf) => resolve(gltf),
                    (progress) => {
                        // Progress tracking (silent)
                    },
                    (error) => reject(error)
                );
            });
            
            this.targetModel = gltf.scene.children[0];
            this.viewer.scene.add(gltf.scene);
            this.originalTargetMatrix = this.targetModel.matrix.clone();
            
            console.log('目标模型加载成功');
            
        } catch (error) {
            console.error('加载目标模型失败:', error);
            throw error;
        }
    }
    
    /**
     * 加载候选模型
     */
    async loadCandidateModel(modelUrl) {
        try {
            console.log('加载候选模型:', modelUrl);
            
            // 检查 GLTFLoader 是否可用
            if (!THREE.GLTFLoader) {
                throw new Error('THREE.GLTFLoader 未加载，请确保已引入 GLTFLoader.js');
            }
            
            const loader = new THREE.GLTFLoader();
            const gltf = await new Promise((resolve, reject) => {
                loader.load(
                    modelUrl,
                    (gltf) => resolve(gltf),
                    (progress) => {
                        // Progress tracking (silent)
                    },
                    (error) => reject(error)
                );
            });
            
            this.candidateModel = gltf.scene.children[0];
            this.viewer.scene.add(gltf.scene);
            this.originalCandidateMatrix = this.candidateModel.matrix.clone();
            
            console.log('候选模型加载成功');
            
        } catch (error) {
            console.error('加载候选模型失败:', error);
            throw error;
        }
    }

    /**
     * 应用精确变换
     */
    applyExactTransformation() {
        if (!this.candidateModel || !this.alignmentData.transform_matrix) {
            console.error('缺少变换所需的数据');
            return;
        }

        try {
            // 重置到原始状态
            this.candidateModel.matrix.copy(this.originalCandidateMatrix);
            
            // 解析变换矩阵
            const transformMatrix = this.parseTransformMatrix(
                this.alignmentData.transform_matrix
            );

            console.log('应用变换矩阵:', transformMatrix.elements.slice(0, 8));
            
            // 如果需要镜像处理
            if (this.alignmentData.mirrored) {
                console.log('应用镜像变换');
                const mirrorMatrix = this.createMirrorMatrix('YZ');
                transformMatrix.premultiply(mirrorMatrix);
            }
            
            // 应用变换
            this.candidateModel.applyMatrix4(transformMatrix);
            this.candidateModel.updateMatrixWorld(true);
            
            console.log('变换应用完成');
            
        } catch (error) {
            console.error('应用变换失败:', error);
            throw error;
        }
    }

    /**
     * 解析变换矩阵
     */
    parseTransformMatrix(matrixArray) {
        const matrix = new THREE.Matrix4();
        
        if (Array.isArray(matrixArray)) {
            if (matrixArray.length === 16) {
                // 4x4矩阵扁平化数组
                matrix.fromArray(matrixArray);
            } else if (matrixArray.length === 4 && Array.isArray(matrixArray[0])) {
                // 4x4二维数组
                const flatArray = matrixArray.flat();
                matrix.fromArray(flatArray);
            } else {
                throw new Error(`不支持的矩阵格式: ${matrixArray.length}`);
            }
        } else {
            throw new Error('变换矩阵必须是数组格式');
        }
        
        return matrix;
    }

    /**
     * 创建镜像矩阵
     */
    createMirrorMatrix(plane) {
        const matrix = new THREE.Matrix4();
        
        switch (plane) {
            case 'YZ':
                matrix.set(
                    -1, 0, 0, 0,
                     0, 1, 0, 0,
                     0, 0, 1, 0,
                     0, 0, 0, 1
                );
                break;
            case 'XZ':
                matrix.set(
                     1, 0, 0, 0,
                     0,-1, 0, 0,
                     0, 0, 1, 0,
                     0, 0, 0, 1
                );
                break;
            case 'XY':
                matrix.set(
                     1, 0, 0, 0,
                     0, 1, 0, 0,
                     0, 0,-1, 0,
                     0, 0, 0, 1
                );
                break;
            default:
                console.warn(`未知的镜像平面: ${plane}`);
        }
        
        return matrix;
    }

    /**
     * 验证对齐质量
     */
    validateAlignment() {
        if (!this.targetModel || !this.candidateModel) {
            return false;
        }

        try {
            // 计算两个模型的边界框
            const targetBox = new THREE.Box3().setFromObject(this.targetModel);
            const candidateBox = new THREE.Box3().setFromObject(this.candidateModel);
            
            // 检查边界框重叠
            const intersection = targetBox.clone().intersect(candidateBox);
            const hasIntersection = !intersection.isEmpty();
            
            // 计算中心距离
            const targetCenter = targetBox.getCenter(new THREE.Vector3());
            const candidateCenter = candidateBox.getCenter(new THREE.Vector3());
            const distance = targetCenter.distanceTo(candidateCenter);
            
            console.log('对齐质量检查:', {
                hasIntersection,
                centerDistance: distance.toFixed(2),
                quality: this.alignmentData.alignment_quality
            });
            
            // 简单的验证：中心距离应该合理
            return hasIntersection && distance < 50; // 50mm阈值
            
        } catch (error) {
            console.error('对齐质量验证失败:', error);
            return false;
        }
    }

    /**
     * 获取CSRF令牌
     */
    getCsrfToken() {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrftoken') {
                return value;
            }
        }
        
        // 备用方案：从meta标签获取
        const metaToken = document.querySelector('meta[name="csrf-token"]');
        return metaToken ? metaToken.getAttribute('content') : '';
    }
}



// 导出到全局作用域
if (typeof window !== 'undefined') {
    window.AlignmentRestorer = AlignmentRestorer;
}
