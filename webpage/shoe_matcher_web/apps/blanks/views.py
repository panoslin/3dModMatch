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


class CategoryDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """分类详情API"""
    queryset = BlankCategory.objects.filter(is_active=True)
    serializer_class = BlankCategorySerializer
    
    def update(self, request, *args, **kwargs):
        """编辑分类"""
        try:
            category = self.get_object()
            
            # 验证父分类，防止循环引用
            parent_id = request.data.get('parent')
            if parent_id:
                if int(parent_id) == category.id:
                    return Response({
                        'success': False,
                        'error': 'invalid_parent',
                        'message': '分类不能设置自己为父分类'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # 检查是否会形成循环引用
                def check_circular_reference(parent_id, target_id):
                    try:
                        parent = BlankCategory.objects.get(id=parent_id)
                        if parent.parent and parent.parent.id == target_id:
                            return True
                        elif parent.parent:
                            return check_circular_reference(parent.parent.id, target_id)
                    except BlankCategory.DoesNotExist:
                        pass
                    return False
                
                if check_circular_reference(parent_id, category.id):
                    return Response({
                        'success': False,
                        'error': 'circular_reference',
                        'message': '不能形成循环引用'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            serializer = self.get_serializer(category, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            
            return Response({
                'success': True,
                'data': serializer.data,
                'message': '分类更新成功'
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': 'update_failed',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    def destroy(self, request, *args, **kwargs):
        """删除分类"""
        try:
            category = self.get_object()
            
            # 检查是否有子分类
            children_count = BlankCategory.objects.filter(parent=category, is_active=True).count()
            if children_count > 0:
                return Response({
                    'success': False,
                    'error': 'has_children',
                    'message': f'该分类下还有 {children_count} 个子分类，请先删除或移动子分类'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 检查是否有关联的粗胚
            blanks_count = BlankModel.objects.filter(categories=category, is_active=True).count()
            if blanks_count > 0:
                return Response({
                    'success': False,
                    'error': 'has_blanks',
                    'message': f'该分类下还有 {blanks_count} 个粗胚文件，请先删除或移动这些文件'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 软删除
            category.is_active = False
            category.save()
            
            return Response({
                'success': True,
                'message': '分类删除成功'
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': 'delete_failed',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

