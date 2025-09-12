# 在库里检索（递归扫描 .3dm）
python shoe_last_matcher.py \
  --target "models/36小.3dm" \
  --candidates "candidates/" \
  --clearance 2.0 \
  --voxel 2.5 \
  --icp-thr 8.0 \
  --fpfh-radius 6.0 \
  --topk 10 \
  --safety-delta 0.3 \
  --export_report "output/match_report.json" \
  --export_glb_dir "output/glb" \
  --export_ply_dir "output/ply" \
  --export_heatmap_dir "output/heatmap" \
  --export_topk 3