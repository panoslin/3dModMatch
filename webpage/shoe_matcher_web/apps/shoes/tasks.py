"""
鞋模处理异步任务
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
def process_shoe_file(shoe_id):
    """处理鞋模3DM文件"""
    from .models import ShoeModel
    
    try:
        shoe = ShoeModel.objects.get(id=shoe_id)
        shoe.processing_status = 'processing'
        shoe.save()
        
        # 导入enhanced_3dm_renderer
        try:
            from utils.enhanced_3dm_renderer import Enhanced3DRenderer
            
            # 处理3DM文件
            renderer = Enhanced3DRenderer()
            data = renderer.read_3dm(shoe.file.path)
            
            if data.success:
                # 更新几何信息
                shoe.volume = data.stats.get('volume', 0)
                shoe.bounding_box = data.stats.get('bounds', {})
                shoe.vertex_count = data.stats.get('vertex_count', 0)
                shoe.face_count = data.stats.get('face_count', 0)
                
                # 生成预览HTML
                fig = renderer.create_figure(data)
                if fig:
                    shoe.preview_html = fig.to_html(
                        include_plotlyjs='cdn',
                        div_id=f'shoe_preview_{shoe.id}'
                    )
                
                shoe.processing_status = 'completed'
                shoe.is_processed = True
                
                logger.info(f"Successfully processed shoe {shoe_id}: {shoe.name}")
                
            else:
                shoe.processing_status = 'failed'
                logger.error(f"Failed to process shoe {shoe_id}: Invalid 3DM data")
                
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
