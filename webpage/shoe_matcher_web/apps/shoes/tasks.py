"""
鞋模处理异步任务
"""

from celery import shared_task
from django.conf import settings
import os
import sys
import logging
import gc

# 添加项目路径以便导入enhanced_3dm_renderer
sys.path.insert(0, os.path.join(settings.BASE_DIR.parent.parent, 'hybrid'))

logger = logging.getLogger(__name__)


@shared_task
def process_shoe_file(shoe_id):
    """处理鞋模3DM文件"""
    from .models import ShoeModel
    
    try:
        shoe = ShoeModel.objects.get(id=shoe_id)
        logger.info(f"开始处理鞋模 {shoe_id}: {shoe.name}, 文件: {shoe.file.path}")
        
        shoe.processing_status = 'processing'
        shoe.save()
        
        # 验证文件存在
        if not os.path.exists(shoe.file.path):
            raise FileNotFoundError(f"鞋模文件不存在: {shoe.file.path}")
        
        file_size = os.path.getsize(shoe.file.path)
        logger.info(f"文件大小: {file_size} bytes")
        
        # 导入enhanced_3dm_renderer
        try:
            from utils.enhanced_3dm_renderer import Enhanced3DRenderer
            logger.info("Enhanced3DRenderer 导入成功")
            
            # 处理3DM文件
            renderer = Enhanced3DRenderer()
            
            logger.info("开始读取3DM文件...")
            data = renderer.read_3dm(shoe.file.path)
            logger.info(f"3DM文件读取完成: success={data.success}")
            
            if data.success:
                # 更新几何信息
                stats = data.stats
                shoe.volume = stats.get('volume', 0)
                shoe.bounding_box = stats.get('bounds', {})
                shoe.vertex_count = stats.get('vertex_count', 0)
                shoe.face_count = stats.get('face_count', 0)
                
                logger.info(f"几何信息提取完成:")
                logger.info(f"  - 体积: {shoe.volume} mm³")
                logger.info(f"  - 顶点数: {shoe.vertex_count}")
                logger.info(f"  - 面数: {shoe.face_count}")
                
                # 生成预览HTML - 已禁用以节省内存
                # 改用前端Three.js直接加载GLB文件进行渲染
                logger.info("跳过预览HTML生成（节省内存），依赖Three.js前端渲染")
                shoe.preview_html = ""  # 清空，使用LOD生成的GLB文件
                
                # 原代码已注释（占用~140MB/任务）:
                # fig = renderer.create_figure(data)
                # if fig:
                #     shoe.preview_html = fig.to_html(...)
                #     del fig
                
                # 清理renderer和data对象
                logger.info("清理临时对象...")
                if 'data' in locals():
                    del data
                if 'renderer' in locals():
                    del renderer
                
                # 强制垃圾回收
                gc.collect()
                gc.collect()  # 执行两次确保清理
                
                shoe.processing_status = 'completed'
                shoe.is_processed = True
                
                logger.info(f"鞋模处理完成: {shoe_id} ({shoe.name})")
                
                # 触发LOD处理（异步）
                try:
                    from utils.lod_processing_tasks import process_model_lod
                    logger.info(f"启动LOD处理任务: {shoe_id}")
                    process_model_lod.delay(shoe_id, 'shoe')
                except ImportError as e:
                    logger.warning(f"无法启动LOD处理: {e}")
                except Exception as e:
                    logger.error(f"启动LOD处理失败: {e}")
                
            else:
                shoe.processing_status = 'failed'
                logger.error(f"鞋模处理失败: {shoe_id}, 3DM数据无效: {data.error if hasattr(data, 'error') else '未知错误'}")
                
        except ImportError as e:
            shoe.processing_status = 'failed'
            logger.error(f"Failed to import enhanced_3dm_renderer: {e}")
            
        except Exception as e:
            shoe.processing_status = 'failed'
            logger.error(f"Error processing shoe {shoe_id}: {e}")
        
        shoe.save()
        return {'success': shoe.processing_status == 'completed', 'shoe_id': shoe_id}
        
    except ShoeModel.DoesNotExist:
        logger.error(f"Shoe {shoe_id} does not exist")
        return {'success': False, 'error': 'Shoe not found'}
    except Exception as e:
        logger.error(f"Unexpected error processing shoe {shoe_id}: {e}")
        return {'success': False, 'error': str(e)}
    finally:
        # 确保最后执行垃圾回收
        gc.collect()
        logger.info(f"[任务完成] shoe_id={shoe_id}")
