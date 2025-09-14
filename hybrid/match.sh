#!/bin/bash

# Test script for hybrid matcher
cd /root/3dModMatch && 
LD_PRELOAD=/usr/local/lib/libOpen3D.so \
python3 hybrid/python/hybrid_matcher_multiprocess.py   \
--target "models/34鞋模(1).3dm"   \
--candidates candidates/   \
--clearance 2.0   \
--no-scaling   \
--enable-multi-start   \
--threshold p15   \
--export-report output/report.json   \
--export-ply-dir output/ply \
--export-heatmap-dir output/heatmap
# --max-scale 1.03   \
