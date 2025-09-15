"""
鞋模管理视图
"""

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.decorators import api_view
from django.shortcuts import get_object_or_404
from .models import ShoeModel
from .serializers import ShoeModelSerializer


class ShoeUploadAPIView(generics.CreateAPIView):
    """鞋模上传API"""
    queryset = ShoeModel.objects.all()
    serializer_class = ShoeModelSerializer
    parser_classes = (MultiPartParser, FormParser)
    
    def create(self, request, *args, **kwargs):
        """上传鞋模文件"""
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            shoe = serializer.save()
            
            # 异步处理3DM文件
            from .tasks import process_shoe_file
            process_shoe_file.delay(shoe.id)
            
            return Response({
                'success': True,
                'data': serializer.data,
                'message': '鞋模上传成功，正在处理中...'
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
        queryset = self.get_queryset()
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
