import { IpcMain } from 'electron';
import * as path from 'path';
import * as fs from 'fs';
import { v4 as uuidv4 } from 'uuid';

export function setupFileHandlers(ipcMain: IpcMain, userDataPath: string): void {
    
    // 上传文件
    ipcMain.handle('file:upload', async (event, sourcePath: string, type: 'blank' | 'model') => {
        try {
            // 检查源文件是否存在
            if (!fs.existsSync(sourcePath)) {
                throw new Error(`文件不存在: ${sourcePath}`);
            }

            // 获取文件信息
            const stats = fs.statSync(sourcePath);
            const fileName = path.basename(sourcePath);
            const extension = path.extname(sourcePath);
            
            // 验证文件格式
            if (extension.toLowerCase() !== '.3dm') {
                throw new Error('仅支持 .3dm 格式的文件');
            }

            // 验证文件大小（最大 500MB）
            const maxSize = 500 * 1024 * 1024;
            if (stats.size > maxSize) {
                throw new Error('文件大小超过限制（最大 500MB）');
            }

            // 生成新文件名（UUID + 原始文件名）
            const newFileName = `${uuidv4()}_${fileName}`;
            const targetDir = type === 'blank' ? 'blanks' : 'models';
            const targetPath = path.join(userDataPath, targetDir, newFileName);

            // 确保目标目录存在
            const targetDirPath = path.dirname(targetPath);
            if (!fs.existsSync(targetDirPath)) {
                fs.mkdirSync(targetDirPath, { recursive: true });
            }

            // 复制文件
            await copyFile(sourcePath, targetPath);

            // 返回新文件路径和元数据
            return {
                success: true,
                path: targetPath,
                fileName: newFileName,
                originalName: fileName,
                size: stats.size,
                type: type
            };

        } catch (error: any) {
            console.error('文件上传失败:', error);
            return {
                success: false,
                error: error.message
            };
        }
    });

    // 删除文件
    ipcMain.handle('file:delete', async (event, filePath: string) => {
        try {
            // 安全检查：确保文件在用户数据目录内
            const normalizedPath = path.normalize(filePath);
            if (!normalizedPath.startsWith(userDataPath)) {
                throw new Error('无权删除该文件');
            }

            if (fs.existsSync(filePath)) {
                fs.unlinkSync(filePath);
                console.log('文件已删除:', filePath);
            }

            return { success: true };

        } catch (error: any) {
            console.error('文件删除失败:', error);
            return {
                success: false,
                error: error.message
            };
        }
    });

    // 获取文件路径
    ipcMain.handle('file:getPath', (event, type: string, fileName: string) => {
        return path.join(userDataPath, type, fileName);
    });

    // 提取3DM文件元数据
    ipcMain.handle('file:extractMetadata', async (event, filePath: string) => {
        try {
            // 基本文件信息
            const stats = fs.statSync(filePath);
            const metadata = {
                fileName: path.basename(filePath),
                fileSize: stats.size,
                createdAt: stats.birthtime,
                modifiedAt: stats.mtime
            };

            // TODO: 这里应该调用 Python 脚本来提取 3DM 文件的几何信息
            // 暂时返回基本信息
            return {
                success: true,
                metadata: metadata
            };

        } catch (error: any) {
            console.error('提取元数据失败:', error);
            return {
                success: false,
                error: error.message
            };
        }
    });

    // 生成3D预览
    ipcMain.handle('file:generatePreview', async (event, filePath: string, outputPath: string) => {
        try {
            // TODO: 调用 Python 渲染器生成预览 HTML
            // 这里需要集成 enhanced_3dm_renderer.py
            
            return {
                success: true,
                previewPath: outputPath
            };

        } catch (error: any) {
            console.error('生成预览失败:', error);
            return {
                success: false,
                error: error.message
            };
        }
    });

    // 清理临时文件
    ipcMain.handle('file:cleanTemp', async () => {
        try {
            const tempDir = path.join(userDataPath, 'temp');
            if (fs.existsSync(tempDir)) {
                const files = fs.readdirSync(tempDir);
                for (const file of files) {
                    const filePath = path.join(tempDir, file);
                    const stats = fs.statSync(filePath);
                    
                    // 删除超过24小时的临时文件
                    const ageInHours = (Date.now() - stats.mtime.getTime()) / (1000 * 60 * 60);
                    if (ageInHours > 24) {
                        fs.unlinkSync(filePath);
                        console.log('已删除临时文件:', filePath);
                    }
                }
            }

            return { success: true };

        } catch (error: any) {
            console.error('清理临时文件失败:', error);
            return {
                success: false,
                error: error.message
            };
        }
    });

    // 获取目录文件列表
    ipcMain.handle('file:listDirectory', async (event, directory: string) => {
        try {
            const dirPath = path.join(userDataPath, directory);
            if (!fs.existsSync(dirPath)) {
                return [];
            }

            const files = fs.readdirSync(dirPath);
            const fileList = files.map(file => {
                const filePath = path.join(dirPath, file);
                const stats = fs.statSync(filePath);
                return {
                    name: file,
                    path: filePath,
                    size: stats.size,
                    createdAt: stats.birthtime,
                    modifiedAt: stats.mtime,
                    isDirectory: stats.isDirectory()
                };
            });

            return fileList;

        } catch (error: any) {
            console.error('获取文件列表失败:', error);
            return [];
        }
    });

    // 检查文件是否存在
    ipcMain.handle('file:exists', (event, filePath: string) => {
        return fs.existsSync(filePath);
    });

    // 获取文件大小
    ipcMain.handle('file:getSize', (event, filePath: string) => {
        try {
            const stats = fs.statSync(filePath);
            return stats.size;
        } catch (error) {
            return 0;
        }
    });
}

// 辅助函数：异步复制文件
function copyFile(source: string, target: string): Promise<void> {
    return new Promise((resolve, reject) => {
        const readStream = fs.createReadStream(source);
        const writeStream = fs.createWriteStream(target);

        readStream.on('error', reject);
        writeStream.on('error', reject);
        writeStream.on('finish', resolve);

        readStream.pipe(writeStream);
    });
}
