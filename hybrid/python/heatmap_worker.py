#!/usr/bin/env python3
"""
Standalone Heatmap Generation Worker
This module provides functions for generating clearance heatmaps without nested multiprocessing
"""

import numpy as np
import trimesh
import plotly.graph_objects as go
from pathlib import Path
import sys
import os

# Add the parent directory to the path to import cppcore
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def generate_clearance_heatmap_standalone(args):
    """
    Standalone heatmap generation function that can be called by ProcessPoolExecutor
    Args: (V_target, F_target, V_cand, F_cand, clearance_data, output_html)
    """
    V_target, F_target, V_cand, F_cand, clearance_data, output_html = args
    
    try:
        # Create mesh objects
        mesh_cand = trimesh.Trimesh(vertices=V_cand, faces=F_cand)
        mesh_target = trimesh.Trimesh(vertices=V_target, faces=F_target)
        
        # Compute clearance using single-threaded approach
        print(f"  Computing clearance for {len(V_cand)} vertices...")
        _, clearances, _ = mesh_target.nearest.on_surface(V_cand)
        
        print(f"  Clearance range: {clearances.min():.3f}mm - {clearances.max():.3f}mm")
        
        # Create Plotly figure
        fig = go.Figure()
        
        # Add target mesh (solid, light color for contrast)
        fig.add_trace(go.Mesh3d(
            x=V_target[:, 0],
            y=V_target[:, 1],
            z=V_target[:, 2],
            i=F_target[:, 0],
            j=F_target[:, 1],
            k=F_target[:, 2],
            name='Target',
            color='lightgray',
            opacity=1.0  # Solid, not transparent
        ))
        
        # Add candidate mesh with clearance-based coloring (solid)
        fig.add_trace(go.Mesh3d(
            x=V_cand[:, 0],
            y=V_cand[:, 1],
            z=V_cand[:, 2],
            i=F_cand[:, 0],
            j=F_cand[:, 1],
            k=F_cand[:, 2],
            intensity=clearances,  # Use vertex clearance values for coloring
            colorscale='RdYlGn',
            cmin=0,
            cmax=10,
            colorbar=dict(title='Clearance (mm)'),
            opacity=1.0,  # Solid, not transparent for better visibility
            name='Candidate Clearance',
            showscale=True
        ))
        
        # Update layout
        fig.update_layout(
            title=f'Clearance Heatmap - Min: {clearance_data.get("min_clearance", 0):.2f}mm',
            scene=dict(
                xaxis_title='X (mm)',
                yaxis_title='Y (mm)', 
                zaxis_title='Z (mm)',
                aspectmode='data'
            ),
            width=1400,
            height=900
        )
        
        # Ensure output directory exists
        Path(output_html).parent.mkdir(parents=True, exist_ok=True)
        
        fig.write_html(output_html)
        print(f"  Generated heatmap: {output_html}")
        
        return {
            'success': True,
            'output_html': output_html,
            'clearance_range': (float(clearances.min()), float(clearances.max()))
        }
        
    except Exception as e:
        print(f"  Error generating heatmap {output_html}: {e}")
        return {
            'success': False,
            'output_html': output_html,
            'error': str(e)
        }

if __name__ == '__main__':
    # Test the function
    print("Heatmap worker module loaded successfully")
