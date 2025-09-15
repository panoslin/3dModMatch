"""
粗胚管理视图
"""

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from .models import BlankModel, BlankCategory
from .serializers import BlankModelSerializer, BlankCategorySerializer


class BlankListCreateAPIView(generics.ListCreateAPIView):
    """粗胚列表和创建API"""
    queryset = BlankModel.objects.filter(is_active=True)
    serializer_class = BlankModelSerializer
    parser_classes = (MultiPartParser, FormParser)
    
    def get_queryset(self):
        queryset = super().get_queryset()
        category_id = self.request.query_params.get('category_id')
        if category_id:
            queryset = queryset.filter(categories__id=category_id)
        return queryset
    
    def create(self, request, *args, **kwargs):
        """创建新的粗胚"""
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            blank = serializer.save()
            
            # 异步处理3DM文件
            from .tasks import process_blank_file
            process_blank_file.delay(blank.id)
            
            return Response({
                'success': True,
                'data': serializer.data,
                'message': '粗胚上传成功，正在处理中...'
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': 'upload_failed',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class BlankDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """粗胚详情API"""
    queryset = BlankModel.objects.filter(is_active=True)
    serializer_class = BlankModelSerializer
    
    def destroy(self, request, *args, **kwargs):
        """删除粗胚"""
        blank = self.get_object()
        blank.is_active = False  # 软删除
        blank.save()
        
        return Response({
            'success': True,
            'message': '粗胚删除成功'
        }, status=status.HTTP_200_OK)


class CategoryListCreateAPIView(generics.ListCreateAPIView):
    """分类列表和创建API"""
    queryset = BlankCategory.objects.filter(is_active=True)
    serializer_class = BlankCategorySerializer
    
    def list(self, request, *args, **kwargs):
        """获取分类树"""
        categories = self.get_queryset().filter(parent=None)
        serializer = self.get_serializer(categories, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    def create(self, request, *args, **kwargs):
        """创建新分类"""
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            category = serializer.save()
            
            return Response({
                'success': True,
                'data': serializer.data,
                'message': '分类创建成功'
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': 'create_failed',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


