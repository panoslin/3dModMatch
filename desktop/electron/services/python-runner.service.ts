import { spawn, ChildProcess } from 'child_process';
import { EventEmitter } from 'events';
import * as path from 'path';
import * as fs from 'fs';

export interface MatchParams {
    modelPath: string;
    blankPaths: string[];
    clearance: number;
    enableScaling: boolean;
    enableMultiStart: boolean;
    threshold: 'min' | 'p10' | 'p15' | 'p20';
    maxScale: number;
    exportHeatmap: boolean;
    exportPly: boolean;
}

export interface MatchProgress {
    type: 'log' | 'progress' | 'result' | 'error';
    stage: 'preparing' | 'processing' | 'analyzing' | 'complete';
    progress: number; // 0-100
    message: string;
    details?: any;
    timestamp: number;
}

export class PythonRunnerService extends EventEmitter {
    private pythonPath: string;
    private activeProcesses: Map<number, ChildProcess> = new Map();
    private nextProcessId: number = 1;

    constructor(pythonPath: string) {
        super();
        this.pythonPath = pythonPath;
        
        // 验证 Python 引擎是否存在
        if (!fs.existsSync(this.pythonPath)) {
            console.warn('Python 引擎未找到，将在首次使用时构建:', this.pythonPath);
        }
    }

    /**
     * 启动匹配任务
     */
    async startMatch(params: MatchParams): Promise<number> {
        return new Promise((resolve, reject) => {
            const processId = this.nextProcessId++;
            
            // 构建命令参数
            const args = this.buildArguments(params);
            
            console.log('启动 Python 进程:', this.pythonPath);
            console.log('参数:', args);
            
            // 创建子进程
            const child = spawn(this.pythonPath, args, {
                cwd: path.dirname(this.pythonPath),
                env: {
                    ...process.env,
                    PYTHONUNBUFFERED: '1', // 禁用 Python 输出缓冲
                    OMP_NUM_THREADS: '1'   // 限制 OpenMP 线程数
                }
            });
            
            this.activeProcesses.set(processId, child);
            
            // 处理标准输出
            child.stdout.on('data', (data) => {
                const lines = data.toString().split('\n');
                lines.forEach((line: string) => {
                    if (line.trim()) {
                        this.parseAndEmitProgress(processId, line);
                    }
                });
            });
            
            // 处理标准错误
            child.stderr.on('data', (data) => {
                const message = data.toString();
                console.error('Python 错误输出:', message);
                
                this.emit('progress', processId, {
                    type: 'error',
                    stage: 'processing',
                    progress: 0,
                    message: message,
                    timestamp: Date.now()
                } as MatchProgress);
            });
            
            // 处理进程关闭
            child.on('close', (code) => {
                this.activeProcesses.delete(processId);
                
                if (code === 0) {
                    this.emit('complete', processId, {
                        type: 'result',
                        stage: 'complete',
                        progress: 100,
                        message: '匹配完成',
                        timestamp: Date.now()
                    } as MatchProgress);
                } else {
                    this.emit('error', processId, {
                        type: 'error',
                        stage: 'complete',
                        progress: 0,
                        message: `进程异常退出，代码: ${code}`,
                        timestamp: Date.now()
                    } as MatchProgress);
                    
                    reject(new Error(`进程异常退出，代码: ${code}`));
                }
            });
            
            // 处理进程错误
            child.on('error', (error) => {
                this.activeProcesses.delete(processId);
                console.error('启动 Python 进程失败:', error);
                
                this.emit('error', processId, {
                    type: 'error',
                    stage: 'preparing',
                    progress: 0,
                    message: `启动进程失败: ${error.message}`,
                    timestamp: Date.now()
                } as MatchProgress);
                
                reject(error);
            });
            
            // 返回进程 ID
            resolve(processId);
        });
    }

    /**
     * 取消匹配任务
     */
    cancelMatch(processId: number): boolean {
        const child = this.activeProcesses.get(processId);
        if (child) {
            child.kill('SIGTERM');
            this.activeProcesses.delete(processId);
            
            this.emit('cancelled', processId, {
                type: 'log',
                stage: 'complete',
                progress: 0,
                message: '任务已取消',
                timestamp: Date.now()
            } as MatchProgress);
            
            return true;
        }
        return false;
    }

    /**
     * 构建命令行参数
     */
    private buildArguments(params: MatchParams): string[] {
        const args: string[] = [];
        
        // 目标模型
        args.push('--target', params.modelPath);
        
        // 候选粗胚（以逗号分隔的路径列表）
        args.push('--candidates', params.blankPaths.join(','));
        
        // 间隙要求
        args.push('--clearance', params.clearance.toString());
        
        // 可选参数
        if (params.enableScaling) {
            args.push('--enable-scaling');
            args.push('--max-scale', params.maxScale.toString());
        } else {
            args.push('--no-scaling');
        }
        
        if (params.enableMultiStart) {
            args.push('--enable-multi-start');
        } else {
            args.push('--no-multi-start');
        }
        
        // 阈值
        args.push('--threshold', params.threshold);
        
        // 导出选项
        if (params.exportHeatmap) {
            args.push('--export-heatmap-dir', path.join(process.cwd(), 'user-data/results/heatmaps'));
        }
        
        if (params.exportPly) {
            args.push('--export-ply-dir', path.join(process.cwd(), 'user-data/results/exports'));
        }
        
        // JSON 输出模式
        args.push('--json-output');
        
        return args;
    }

    /**
     * 解析并发送进度信息
     */
    private parseAndEmitProgress(processId: number, line: string): void {
        try {
            // 尝试解析 JSON 格式的进度信息
            if (line.startsWith('{') && line.endsWith('}')) {
                const data = JSON.parse(line);
                
                const progress: MatchProgress = {
                    type: data.type || 'log',
                    stage: data.stage || 'processing',
                    progress: data.progress || 0,
                    message: data.message || line,
                    details: data.details || null,
                    timestamp: Date.now()
                };
                
                this.emit('progress', processId, progress);
                
                // 如果是结果数据，单独发送
                if (data.type === 'result') {
                    this.emit('result', processId, data.details);
                }
            } else {
                // 普通日志行
                const progress: MatchProgress = {
                    type: 'log',
                    stage: 'processing',
                    progress: 0,
                    message: line,
                    timestamp: Date.now()
                };
                
                this.emit('progress', processId, progress);
                
                // 尝试从日志中提取进度信息
                const progressMatch = line.match(/(\d+)%/);
                if (progressMatch) {
                    progress.progress = parseInt(progressMatch[1]);
                }
                
                // 检测阶段
                if (line.includes('准备') || line.includes('Loading')) {
                    progress.stage = 'preparing';
                } else if (line.includes('处理') || line.includes('Processing')) {
                    progress.stage = 'processing';
                } else if (line.includes('分析') || line.includes('Analyzing')) {
                    progress.stage = 'analyzing';
                } else if (line.includes('完成') || line.includes('Complete')) {
                    progress.stage = 'complete';
                }
            }
        } catch (error) {
            // 如果解析失败，作为普通日志处理
            const progress: MatchProgress = {
                type: 'log',
                stage: 'processing',
                progress: 0,
                message: line,
                timestamp: Date.now()
            };
            
            this.emit('progress', processId, progress);
        }
    }

    /**
     * 获取活跃进程数
     */
    getActiveProcessCount(): number {
        return this.activeProcesses.size;
    }

    /**
     * 清理所有进程
     */
    cleanup(): void {
        for (const [id, child] of this.activeProcesses) {
            child.kill('SIGTERM');
        }
        this.activeProcesses.clear();
    }

    /**
     * 验证 Python 引擎
     */
    async verifyPythonEngine(): Promise<boolean> {
        return new Promise((resolve) => {
            if (!fs.existsSync(this.pythonPath)) {
                resolve(false);
                return;
            }
            
            const child = spawn(this.pythonPath, ['--version'], {
                cwd: path.dirname(this.pythonPath)
            });
            
            child.on('close', (code) => {
                resolve(code === 0);
            });
            
            child.on('error', () => {
                resolve(false);
            });
            
            // 超时处理
            setTimeout(() => {
                child.kill();
                resolve(false);
            }, 5000);
        });
    }
}
