"""
Custom pagination for blanks to exclude heavy fields
"""

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class BlankListPagination(PageNumberPagination):
    """Custom pagination that excludes heavy fields in list views"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    def get_paginated_response(self, data):
        """Return paginated response with optimized data"""
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data
        })
