import { IpcMain, BrowserWindow } from 'electron';
import { PythonRunnerService, MatchParams, MatchProgress } from '../services/python-runner.service';
import { DatabaseService } from '../services/database.service';
import * as path from 'path';

interface ActiveMatch {
    id: number;
    processId: number;
    modelId: number;
    blankIds: number[];
    startTime: Date;
    status: 'running' | 'completed' | 'failed' | 'cancelled';
}

export function setupMatchingHandlers(
    ipcMain: IpcMain,
    pythonRunner: PythonRunnerService,
    dbService: DatabaseService
): void {
    
    const activeMatches = new Map<number, ActiveMatch>();

    // 启动匹配任务
    ipcMain.handle('match:start', async (event, params: any) => {
        try {
            console.log('启动匹配任务:', params);

            // 创建数据库记录
            const matchId = await dbService.createMatch({
                model_id: params.modelId,
                selected_blank_ids: params.blankIds,
                status: 'processing'
            });

            // 获取文件路径
            const model = await dbService.getModelById(params.modelId);
            const blanks = await Promise.all(
                params.blankIds.map((id: number) => dbService.getBlankById(id))
            );

            if (!model || blanks.some(b => !b)) {
                throw new Error('无法找到模型或粗胚文件');
            }

            // 构建匹配参数
            const matchParams: MatchParams = {
                modelPath: model.file_path,
                blankPaths: blanks.map(b => b.file_path),
                clearance: params.clearance || 2.0,
                enableScaling: params.enableScaling !== false,
                enableMultiStart: params.enableMultiStart !== false,
                threshold: params.threshold || 'p15',
                maxScale: params.maxScale || 1.03,
                exportHeatmap: params.exportHeatmap !== false,
                exportPly: params.exportPly !== false
            };

            // 启动 Python 进程
            const processId = await pythonRunner.startMatch(matchParams);

            // 记录活跃匹配
            const activeMatch: ActiveMatch = {
                id: matchId,
                processId: processId,
                modelId: params.modelId,
                blankIds: params.blankIds,
                startTime: new Date(),
                status: 'running'
            };
            activeMatches.set(matchId, activeMatch);

            // 设置进度监听
            const progressHandler = (data: MatchProgress) => {
                // 发送进度到渲染进程
                const windows = BrowserWindow.getAllWindows();
                windows.forEach(win => {
                    win.webContents.send('match:progress', {
                        matchId: matchId,
                        ...data
                    });
                });

                // 记录日志
                if (data.type === 'log') {
                    console.log(`[Match ${matchId}] ${data.message}`);
                }
            };

            // 设置结果处理
            const resultHandler = async (results: any) => {
                console.log(`匹配 ${matchId} 收到结果:`, results);

                // 保存结果到数据库
                if (Array.isArray(results)) {
                    for (const result of results) {
                        const blankId = params.blankIds[results.indexOf(result)];
                        await dbService.saveMatchResult({
                            match_id: matchId,
                            blank_id: blankId,
                            result_data: result,
                            coverage_rate: result.coverage_rate || result.inside_ratio,
                            volume_ratio: result.volume_ratio,
                            p15_clearance: result.p15_clearance,
                            min_clearance: result.min_clearance,
                            passed: result.pass_p15 || false,
                            heatmap_path: result.heatmap_path || null,
                            ply_path: result.ply_path || null
                        });
                    }
                }
            };

            // 设置完成处理
            const completeHandler = async () => {
                console.log(`匹配 ${matchId} 完成`);
                
                // 更新数据库状态
                await dbService.updateMatchStatus(matchId, 'completed');

                // 更新活跃匹配状态
                const match = activeMatches.get(matchId);
                if (match) {
                    match.status = 'completed';
                }

                // 通知渲染进程
                const windows = BrowserWindow.getAllWindows();
                windows.forEach(win => {
                    win.webContents.send('match:complete', {
                        matchId: matchId,
                        status: 'completed'
                    });
                });

                // 清理监听器
                pythonRunner.removeListener(`progress_${processId}`, progressHandler);
                pythonRunner.removeListener(`result_${processId}`, resultHandler);
                pythonRunner.removeListener(`complete_${processId}`, completeHandler);
                pythonRunner.removeListener(`error_${processId}`, errorHandler);
            };

            // 设置错误处理
            const errorHandler = async (error: any) => {
                console.error(`匹配 ${matchId} 出错:`, error);
                
                // 更新数据库状态
                await dbService.updateMatchStatus(matchId, 'failed', error.message);

                // 更新活跃匹配状态
                const match = activeMatches.get(matchId);
                if (match) {
                    match.status = 'failed';
                }

                // 通知渲染进程
                const windows = BrowserWindow.getAllWindows();
                windows.forEach(win => {
                    win.webContents.send('match:error', {
                        matchId: matchId,
                        error: error.message
                    });
                });

                // 清理监听器
                pythonRunner.removeListener(`progress_${processId}`, progressHandler);
                pythonRunner.removeListener(`result_${processId}`, resultHandler);
                pythonRunner.removeListener(`complete_${processId}`, completeHandler);
                pythonRunner.removeListener(`error_${processId}`, errorHandler);
            };

            // 监听事件
            pythonRunner.on(`progress_${processId}`, progressHandler);
            pythonRunner.on(`result_${processId}`, resultHandler);
            pythonRunner.on(`complete_${processId}`, completeHandler);
            pythonRunner.on(`error_${processId}`, errorHandler);

            // 返回匹配 ID
            return {
                success: true,
                matchId: matchId,
                processId: processId
            };

        } catch (error: any) {
            console.error('启动匹配失败:', error);
            return {
                success: false,
                error: error.message
            };
        }
    });

    // 取消匹配任务
    ipcMain.handle('match:cancel', async (event, matchId: number) => {
        try {
            const match = activeMatches.get(matchId);
            if (!match) {
                throw new Error('找不到该匹配任务');
            }

            // 终止 Python 进程
            const cancelled = pythonRunner.cancelMatch(match.processId);
            
            if (cancelled) {
                // 更新数据库状态
                await dbService.updateMatchStatus(matchId, 'cancelled');

                // 更新活跃匹配状态
                match.status = 'cancelled';

                // 通知渲染进程
                const windows = BrowserWindow.getAllWindows();
                windows.forEach(win => {
                    win.webContents.send('match:cancelled', {
                        matchId: matchId
                    });
                });

                return { success: true };
            } else {
                throw new Error('无法取消该任务');
            }

        } catch (error: any) {
            console.error('取消匹配失败:', error);
            return {
                success: false,
                error: error.message
            };
        }
    });

    // 获取匹配进度
    ipcMain.handle('match:getProgress', async (event, matchId: number) => {
        const match = activeMatches.get(matchId);
        if (!match) {
            return {
                status: 'unknown',
                message: '任务不存在或已完成'
            };
        }

        return {
            status: match.status,
            startTime: match.startTime,
            duration: Date.now() - match.startTime.getTime()
        };
    });

    // 获取活跃匹配列表
    ipcMain.handle('match:getActiveMatches', async () => {
        const matches = Array.from(activeMatches.values()).map(match => ({
            id: match.id,
            modelId: match.modelId,
            blankCount: match.blankIds.length,
            status: match.status,
            startTime: match.startTime
        }));

        return matches;
    });

    // 验证 Python 引擎
    ipcMain.handle('match:verifyEngine', async () => {
        try {
            const isValid = await pythonRunner.verifyPythonEngine();
            return {
                success: isValid,
                message: isValid ? 'Python 引擎正常' : 'Python 引擎未找到或无法运行'
            };
        } catch (error: any) {
            return {
                success: false,
                message: error.message
            };
        }
    });

    // 清理已完成的任务
    ipcMain.handle('match:cleanup', async () => {
        const toRemove: number[] = [];
        
        for (const [id, match] of activeMatches) {
            if (match.status === 'completed' || match.status === 'failed' || match.status === 'cancelled') {
                // 只保留最近1小时的已完成任务
                const ageInHours = (Date.now() - match.startTime.getTime()) / (1000 * 60 * 60);
                if (ageInHours > 1) {
                    toRemove.push(id);
                }
            }
        }

        toRemove.forEach(id => activeMatches.delete(id));

        return {
            cleaned: toRemove.length,
            active: activeMatches.size
        };
    });

    // Python 运行器事件转发
    pythonRunner.on('progress', (processId: number, data: MatchProgress) => {
        // 找到对应的匹配 ID
        let matchId: number | null = null;
        for (const [id, match] of activeMatches) {
            if (match.processId === processId) {
                matchId = id;
                break;
            }
        }

        if (matchId !== null) {
            pythonRunner.emit(`progress_${processId}`, data);
        }
    });

    pythonRunner.on('result', (processId: number, data: any) => {
        pythonRunner.emit(`result_${processId}`, data);
    });

    pythonRunner.on('complete', (processId: number, data: any) => {
        pythonRunner.emit(`complete_${processId}`, data);
    });

    pythonRunner.on('error', (processId: number, data: any) => {
        pythonRunner.emit(`error_${processId}`, data);
    });
}
