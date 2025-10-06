"""
粗胚处理异步任务
"""

from celery import shared_task
from django.conf import settings
import os
import sys
import logging

# 添加项目路径以便导入enhanced_3dm_renderer
sys.path.insert(0, os.path.join(settings.BASE_DIR.parent.parent, 'hybrid'))

logger = logging.getLogger(__name__)


@shared_task
def process_blank_file(blank_id):
    """处理粗胚3DM文件"""
    from .models import BlankModel
    
    try:
        blank = BlankModel.objects.get(id=blank_id)
        blank.processing_status = 'processing'
        blank.save()
        
        # 导入enhanced_3dm_renderer
        try:
            from utils.enhanced_3dm_renderer import Enhanced3DRenderer
            
            # 处理3DM文件
            renderer = Enhanced3DRenderer()
            data = renderer.read_3dm(blank.file.path)
            
            if data.success:
                # 更新几何信息
                blank.volume = data.stats.get('volume', 0)
                blank.bounding_box = data.stats.get('bounds', {})
                blank.vertex_count = data.stats.get('vertex_count', 0)
                blank.face_count = data.stats.get('face_count', 0)
                
                # 生成预览HTML - 已禁用以节省内存
                # 改用前端Three.js直接加载GLB文件进行渲染
                logger.info("跳过预览HTML生成（节省内存），依赖Three.js前端渲染")
                blank.preview_html = ""  # 清空，使用LOD生成的GLB文件
                
                # 清理临时对象
                if 'data' in locals():
                    del data
                if 'renderer' in locals():
                    del renderer
                
                # 强制垃圾回收
                import gc
                gc.collect()
                gc.collect()
                
                blank.processing_status = 'completed'
                blank.is_processed = True
                
                # 触发LOD处理（异步）
                try:
                    from utils.lod_processing_tasks import process_model_lod
                    logger.info(f"启动LOD处理任务: {blank_id}")
                    process_model_lod.delay(blank_id, 'blank')
                except ImportError as e:
                    logger.warning(f"无法启动LOD处理: {e}")
                except Exception as e:
                    logger.error(f"启动LOD处理失败: {e}")
                
            else:
                blank.processing_status = 'failed'
                logger.error(f"Failed to process blank {blank_id}: Invalid 3DM data")
                
        except ImportError as e:
            blank.processing_status = 'failed'
            logger.error(f"Failed to import enhanced_3dm_renderer: {e}")
            
        except Exception as e:
            blank.processing_status = 'failed'
            logger.error(f"Error processing blank {blank_id}: {e}")
        
        blank.save()
        return {'success': blank.processing_status == 'completed', 'blank_id': blank_id}
        
    except BlankModel.DoesNotExist:
        logger.error(f"Blank {blank_id} does not exist")
        return {'success': False, 'error': 'Blank not found'}
    except Exception as e:
        logger.error(f"Unexpected error processing blank {blank_id}: {e}")
        return {'success': False, 'error': str(e)}


