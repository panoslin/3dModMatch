#!/bin/bash

# Test script for hybrid matcher
cd /root/3dModMatch && 
LD_LIBRARY_PATH=./hybrid/docker-extract:/usr/local/lib/python3.10/dist-packages/open3d:$LD_LIBRARY_PATH \
python3 hybrid/python/hybrid_matcher_multiprocess.py   \
--target "webpage/shoe_matcher_web/media/converted/金宇祥8073-36 2_20250925_035930_4bf6ed0f.3dm"   \
--candidates "stl-002large-3dm"   \
--clearance 2.0   \
--no-scaling   \
--enable-multi-start   \
--threshold p15   \
--export-report output/report.json   \
--export-ply-dir output/ply \
# --export-heatmap-dir ''
# --max-scale 1.03   \
