cd /workspace/project && 
LD_PRELOAD=/usr/local/lib/libOpen3D.so \
python3 hybrid/python/hybrid_matcher.py   \
--target models/39大.3dm   \
--candidates candidates/   \
--clearance 2.0   \
--enable-scaling   \
--enable-multi-start   \
--threshold p15   \
--max-scale 1.03   \
--export-report output/optimized_report.json   \
--export-ply-dir output/optimized_ply
