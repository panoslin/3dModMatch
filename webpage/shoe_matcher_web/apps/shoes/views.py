"""
鞋模管理视图
"""

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.decorators import api_view, parser_classes
from django.shortcuts import get_object_or_404
from django.conf import settings
import os
import uuid
from datetime import datetime
from .models import ShoeModel
from .serializers import ShoeModelSerializer

# 导入 C++ 模块
try:
    import cppcore
    CPP_AVAILABLE = True
except ImportError as e:
    print(f"Warning: C++ module not available: {e}")
    CPP_AVAILABLE = False

# 导入文件转换服务
from utils.file_conversion_service import FileConversionService


class ShoeUploadAPIView(generics.CreateAPIView):
    """鞋模上传API"""
    queryset = ShoeModel.objects.all()
    serializer_class = ShoeModelSerializer
    parser_classes = (MultiPartParser, FormParser)
    
    def create(self, request, *args, **kwargs):
        """上传鞋模文件 - 支持STL自动转换"""
        try:
            # 检查是否需要文件转换
            uploaded_file = request.FILES.get('file')
            if not uploaded_file:
                return Response({
                    'success': False,
                    'error': 'no_file',
                    'message': '请选择要上传的文件'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            conversion_info = {}
            original_format = FileConversionService.get_file_format(uploaded_file)
            
            # 如果是STL文件，进行自动转换
            if FileConversionService.is_conversion_needed(uploaded_file):
                conversion_result = FileConversionService.convert_if_needed(
                    uploaded_file, 
                    user=request.user if request.user.is_authenticated else None
                )
                
                if not conversion_result['success']:
                    return Response({
                        'success': False,
                        'error': 'conversion_failed',
                        'message': f'文件转换失败: {conversion_result["error"]}'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # 使用转换后的文件 - 确保使用正确的3DM文件名
                converted_file = conversion_result['converted_file']
                
                # 强制修改文件名为3DM格式 - 这次直接修改原始上传文件对象
                base_name = os.path.splitext(uploaded_file.name)[0]
                correct_3dm_name = f"{base_name}_converted.3dm"
                
                # 关键修复：直接修改上传文件对象的名称
                uploaded_file.name = correct_3dm_name
                # 替换文件内容但保持修改后的文件名
                uploaded_file.file = converted_file.file
                
                conversion_info = conversion_result['conversion_info']
            
            # 验证和保存模型
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            shoe = serializer.save()
            
            # 记录转换信息（如果有转换的话）
            if conversion_info:
                from datetime import datetime
                shoe.original_format = original_format.lstrip('.')  # 去掉点号
                shoe.conversion_info = conversion_info
                shoe.converted_at = datetime.now()
                shoe.save()
                
                # 转换服务已经返回正确命名的文件，无需重命名操作
                print(f"[转换成功] 文件已保存为: {shoe.file.name}")
            
            # 异步处理3DM文件
            from .tasks import process_shoe_file
            process_shoe_file.delay(shoe.id)
            
            # 准备响应消息
            message = '鞋模上传成功，正在处理中...'
            if conversion_info:
                message += f' (已从{original_format}格式自动转换)'
            
            response_data = serializer.data.copy()
            if conversion_info:
                response_data['conversion_info'] = FileConversionService.get_conversion_stats(conversion_info)
            
            return Response({
                'success': True,
                'data': response_data,
                'message': message
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': 'upload_failed',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class ShoeListAPIView(generics.ListAPIView):
    """鞋模列表API"""
    queryset = ShoeModel.objects.filter(is_processed=True)
    serializer_class = ShoeModelSerializer
    
    
    def list(self, request, *args, **kwargs):
        """获取鞋模列表"""
        queryset = self.filter_queryset(self.get_queryset())
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                'success': True,
                'data': serializer.data
            })
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'data': serializer.data
        })


class ShoeDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """鞋模详情API"""
    queryset = ShoeModel.objects.all()
    serializer_class = ShoeModelSerializer
    
    def retrieve(self, request, *args, **kwargs):
        """获取鞋模详情"""
        shoe = self.get_object()
        serializer = self.get_serializer(shoe)
        
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    def destroy(self, request, *args, **kwargs):
        """删除鞋模"""
        shoe = self.get_object()
        shoe.delete()
        
        return Response({
            'success': True,
            'message': '鞋模删除成功'
        }, status=status.HTTP_200_OK)


@api_view(['GET'])
def shoe_preview_api(request, shoe_id):
    """获取鞋模3D预览"""
    try:
        shoe = get_object_or_404(ShoeModel, id=shoe_id)
        
        if not shoe.preview_html:
            return Response({
                'success': False,
                'error': 'preview_not_ready',
                'message': '预览还未生成，请稍后重试'
            }, status=status.HTTP_404_NOT_FOUND)
        
        return Response({
            'success': True,
            'data': {
                'html': shoe.preview_html,
                'metadata': {
                    'name': shoe.name,
                    'volume': shoe.volume,
                    'vertex_count': shoe.vertex_count,
                    'face_count': shoe.face_count,
                    'dimensions': shoe.dimensions
                }
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': 'preview_failed',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def stl_to_3dm_convert_api(request):
    """STL 转 3DM API - 使用高性能 C++ 实现"""
    try:
        if not CPP_AVAILABLE:
            return Response({
                'success': False,
                'error': 'cpp_module_not_available',
                'message': 'C++ 转换模块不可用，请检查安装'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # 检查文件是否存在
        if 'stl_file' not in request.FILES:
            return Response({
                'success': False,
                'error': 'no_file',
                'message': '请上传 STL 文件'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        stl_file = request.FILES['stl_file']
        
        # 检查文件扩展名
        if not stl_file.name.lower().endswith('.stl'):
            return Response({
                'success': False,
                'error': 'invalid_file_type',
                'message': '只支持 STL 文件格式'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 生成唯一的文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        base_name = os.path.splitext(stl_file.name)[0]
        
        # 保存上传的 STL 文件
        stl_filename = f"{base_name}_{timestamp}_{unique_id}.stl"
        stl_path = os.path.join(settings.MEDIA_ROOT, 'temp', stl_filename)
        os.makedirs(os.path.dirname(stl_path), exist_ok=True)
        
        with open(stl_path, 'wb') as f:
            for chunk in stl_file.chunks():
                f.write(chunk)
        
        # 生成输出 3DM 文件路径
        output_filename = f"{base_name}_{timestamp}_{unique_id}.3dm"
        output_path = os.path.join(settings.MEDIA_ROOT, 'converted', output_filename)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # 使用 C++ 模块进行转换
        result = cppcore.stl_to_3dm(stl_path, output_path)
        converter_used = 'C++ (High Performance)'
        
        # 清理临时 STL 文件
        try:
            os.remove(stl_path)
        except:
            pass
        
        if not result.get('success', False):
            return Response({
                'success': False,
                'error': 'conversion_failed',
                'message': result.get('error', '转换失败')
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # 生成访问 URL
        media_url = settings.MEDIA_URL if settings.MEDIA_URL.endswith('/') else settings.MEDIA_URL + '/'
        file_url = f"{media_url}converted/{output_filename}"
        
        return Response({
            'success': True,
            'message': '转换成功',
            'data': {
                'original_filename': stl_file.name,
                'converted_filename': output_filename,
                'file_url': file_url,
                'file_path': f"converted/{output_filename}",
                'converter_used': converter_used,
                'statistics': {
                    'triangle_count': result.get('triangle_count', 0),
                    'vertex_count': result.get('vertex_count', 0),
                    'file_size_mb': round(os.path.getsize(output_path) / (1024 * 1024), 2)
                }
            }
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        # 清理可能的临时文件
        try:
            if 'stl_path' in locals() and os.path.exists(stl_path):
                os.remove(stl_path)
        except:
            pass
            
        return Response({
            'success': False,
            'error': 'server_error',
            'message': f'服务器错误：{str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
