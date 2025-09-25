#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Three.js演示视图
提供测试GLB数据以演示渲染器功能

作者：AI Assistant
创建时间：2024-09-25
版本：v1.0
"""

from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET
import json
import struct
import base64


def create_simple_cube_glb():
    """
    创建一个简单的立方体GLB文件用于演示
    返回GLB格式的二进制数据
    """
    # 立方体顶点数据（8个顶点）
    vertices = [
        # 前面
        -1.0, -1.0,  1.0,  # 0
         1.0, -1.0,  1.0,  # 1
         1.0,  1.0,  1.0,  # 2
        -1.0,  1.0,  1.0,  # 3
        # 后面
        -1.0, -1.0, -1.0,  # 4
         1.0, -1.0, -1.0,  # 5
         1.0,  1.0, -1.0,  # 6
        -1.0,  1.0, -1.0,  # 7
    ]
    
    # 立方体索引数据（12个三角形，36个索引）
    indices = [
        # 前面
        0, 1, 2,  2, 3, 0,
        # 后面
        4, 6, 5,  6, 4, 7,
        # 左面
        4, 0, 3,  3, 7, 4,
        # 右面
        1, 5, 6,  6, 2, 1,
        # 上面
        3, 2, 6,  6, 7, 3,
        # 下面
        4, 5, 1,  1, 0, 4,
    ]
    
    # 法向量数据
    normals = [
        # 前面
         0.0,  0.0,  1.0,
         0.0,  0.0,  1.0,
         0.0,  0.0,  1.0,
         0.0,  0.0,  1.0,
        # 后面
         0.0,  0.0, -1.0,
         0.0,  0.0, -1.0,
         0.0,  0.0, -1.0,
         0.0,  0.0, -1.0,
    ]
    
    # 将数据转换为字节
    vertices_bytes = struct.pack(f'<{len(vertices)}f', *vertices)
    indices_bytes = struct.pack(f'<{len(indices)}I', *indices)
    normals_bytes = struct.pack(f'<{len(normals)}f', *normals)
    
    # 计算缓冲区大小和偏移
    vertices_offset = 0
    normals_offset = len(vertices_bytes)
    indices_offset = normals_offset + len(normals_bytes)
    total_buffer_size = indices_offset + len(indices_bytes)
    
    # 构建GLTF JSON结构
    gltf_json = {
        "asset": {
            "version": "2.0",
            "generator": "3dModMatch Demo"
        },
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{
            "primitives": [{
                "attributes": {
                    "POSITION": 0,
                    "NORMAL": 1
                },
                "indices": 2,
                "material": 0
            }]
        }],
        "materials": [{
            "pbrMetallicRoughness": {
                "baseColorFactor": [0.8, 0.2, 0.2, 1.0],  # 红色
                "metallicFactor": 0.1,
                "roughnessFactor": 0.8
            }
        }],
        "accessors": [
            {  # 0: POSITION
                "bufferView": 0,
                "byteOffset": 0,
                "componentType": 5126,  # FLOAT
                "count": 8,
                "type": "VEC3",
                "max": [1.0, 1.0, 1.0],
                "min": [-1.0, -1.0, -1.0]
            },
            {  # 1: NORMAL
                "bufferView": 1,
                "byteOffset": 0,
                "componentType": 5126,  # FLOAT
                "count": 8,
                "type": "VEC3"
            },
            {  # 2: INDICES
                "bufferView": 2,
                "byteOffset": 0,
                "componentType": 5125,  # UNSIGNED_INT
                "count": 36,
                "type": "SCALAR"
            }
        ],
        "bufferViews": [
            {  # 0: vertices
                "buffer": 0,
                "byteOffset": vertices_offset,
                "byteLength": len(vertices_bytes),
                "target": 34962  # ARRAY_BUFFER
            },
            {  # 1: normals
                "buffer": 0,
                "byteOffset": normals_offset,
                "byteLength": len(normals_bytes),
                "target": 34962  # ARRAY_BUFFER
            },
            {  # 2: indices
                "buffer": 0,
                "byteOffset": indices_offset,
                "byteLength": len(indices_bytes),
                "target": 34963  # ELEMENT_ARRAY_BUFFER
            }
        ],
        "buffers": [{
            "byteLength": total_buffer_size
        }]
    }
    
    # 转换JSON为字节
    json_str = json.dumps(gltf_json, separators=(',', ':'))
    json_bytes = json_str.encode('utf-8')
    
    # 确保JSON块长度是4的倍数
    json_padding = (4 - (len(json_bytes) % 4)) % 4
    json_bytes += b' ' * json_padding
    
    # 组合二进制数据
    binary_data = vertices_bytes + normals_bytes + indices_bytes
    
    # 确保二进制块长度是4的倍数
    binary_padding = (4 - (len(binary_data) % 4)) % 4
    binary_data += b'\x00' * binary_padding
    
    # 构建GLB文件
    # GLB头部 (12字节)
    magic = b'glTF'
    version = struct.pack('<I', 2)
    total_length = 12 + 8 + len(json_bytes) + 8 + len(binary_data)
    length = struct.pack('<I', total_length)
    
    # JSON块头部 (8字节)
    json_chunk_length = struct.pack('<I', len(json_bytes))
    json_chunk_type = b'JSON'
    
    # 二进制块头部 (8字节)
    binary_chunk_length = struct.pack('<I', len(binary_data))
    binary_chunk_type = b'BIN\x00'
    
    # 组装完整的GLB文件
    glb_data = (magic + version + length +
                json_chunk_length + json_chunk_type + json_bytes +
                binary_chunk_length + binary_chunk_type + binary_data)
    
    return glb_data


@require_GET
@cache_control(max_age=3600)  # 缓存1小时
def demo_cube_glb(request):
    """
    返回演示用的立方体GLB文件
    """
    try:
        glb_data = create_simple_cube_glb()
        
        response = HttpResponse(glb_data, content_type='model/gltf-binary')
        response['Content-Disposition'] = 'attachment; filename="demo_cube.glb"'
        response['Content-Length'] = len(glb_data)
        
        return response
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'demo_glb_generation_failed',
            'message': f'无法生成演示GLB文件: {str(e)}'
        }, status=500)


@require_GET
def demo_model_status(request):
    """
    返回演示模型的状态信息
    """
    return JsonResponse({
        'success': True,
        'data': {
            'has_glb_files': True,
            'lod_levels': ['demo'],
            'webgl_ready': True,
            'model_info': {
                'name': '演示立方体',
                'description': '用于测试Three.js渲染器的简单立方体',
                'vertices': 8,
                'faces': 12,
                'file_size_kb': 2
            },
            'optimization_status': {
                'geometry_simplified': True,
                'compression_ratio': 0.9,
                'supports_webgl': True
            }
        }
    })


