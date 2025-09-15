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
                
                # 生成预览HTML
                fig = renderer.create_figure(data)
                if fig:
                    blank.preview_html = fig.to_html(
                        include_plotlyjs='cdn',
                        div_id=f'blank_preview_{blank.id}'
                    )
                
                blank.processing_status = 'completed'
                blank.is_processed = True
                
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


