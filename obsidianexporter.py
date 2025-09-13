#!/usr/bin/env python3
"""
Obsidian Canvas Exporter
Exports Obsidian .canvas files to an interactive web format 
"""

import json
import sys
import os
import argparse
from pathlib import Path
import re
from typing import Dict, List, Any, Optional
import base64
from string import Template

class ObsidianCanvasExporter:
    def __init__(self, canvas_file_path: str):
        self.canvas_file_path = Path(canvas_file_path)
        self.canvas_data = None
        self.output_dir = None
        
    def load_canvas(self) -> bool:
        """Charge le fichier .canvas d'Obsidian"""
        try:
            if not self.canvas_file_path.exists():
                print(f"Error: File {self.canvas_file_path} does not exist.")
                return False
                
            if not self.canvas_file_path.suffix == '.canvas':
                print(f"Error: File {self.canvas_file_path} is not a .canvas file")
                return False
                
            with open(self.canvas_file_path, 'r', encoding='utf-8') as f:
                self.canvas_data = json.load(f)
                
            print(f"Canvas file loaded successfully: {self.canvas_file_path}")
            return True
            
        except json.JSONDecodeError:
            print(f"Error: File {self.canvas_file_path} is not valid JSON")
            return False
        except Exception as e:
            print(f"Error loading file: {e}")
            return False
    
    def create_output_directory(self) -> bool:
        try:
            self.output_dir = self.canvas_file_path.parent
            print(f"Output directory: {self.output_dir}")
            return True
        except Exception as e:
            print(f"Error setting output directory: {e}")
            return False
    
    def extract_node_content(self, node: Dict[str, Any]) -> str:
        content = ""
        node_type = node.get('type', 'text')
        
        if node_type == 'group':
            content = ""
            
        elif node_type == 'text':
            if 'text' in node:
                content += node['text']
                
        elif node_type == 'file':
            file_path = node.get('file', '')
            if file_path:
                content += f"📁  **File:** {file_path}"

                if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg')):
                    relative_path = f"_src/{Path(file_path).name}"
                    
                    content += f"\n\n__IMAGE_PLACEHOLDER_{relative_path}__"
                elif Path(file_path).exists():
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            file_content = f.read()
                            content += f"\n\n--- File content ---\n{file_content}"
                    except Exception as e:
                        content += f"\n\n--- File read error: {e} ---"
        
        if 'url' in node:
            content += f"\n\n🔗 **Link:** {node['url']}"
            
        return content
    
    def clean_content_after_code(self, content: str) -> str:
        """Nettoie le contenu en supprimant la première ligne des blocs de code (nom du langage)"""
        if not content:
            return content

        def replace_code_block(match):
            code_content = match.group(1)
            lines = code_content.split('\n')
            
            if len(lines) > 1:
                return '```\n' + '\n'.join(lines[1:]) + '\n```'
            else:
                return '```\n```'

        content = re.sub(r'```([\s\S]*?)```', replace_code_block, content)
        
        return content
    
    def get_node_color(self, node: Dict[str, Any]) -> str:
        """Récupère la couleur d'un nœud"""
        color_code = node.get('color', '4')
        
        if isinstance(color_code, str) and color_code.startswith('#'):
            return color_code
            
        color_map = {
            "1": "#ff6b6b",
            "2": "#ffa726",
            "3": "#ffeb3b",
            "4": "#4caf50",
            "5": "#00bcd4",
            "6": "#9c27b0",
            "7": "#2196f3",
            "8": "#795548",
            "9": "#607d8b",
            "10": "#e91e63"
        }
        
        return color_map.get(color_code, "#4caf50")
    
    def filter_main_nodes(self, nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if len(nodes) <= 1:
            return nodes
            
        center_x = sum(node['x'] + node['width']/2 for node in nodes) / len(nodes)
        center_y = sum(node['y'] + node['height']/2 for node in nodes) / len(nodes)
        distances = []
        for node in nodes:
            node_center_x = node['x'] + node['width']/2
            node_center_y = node['y'] + node['height']/2
            distance = ((node_center_x - center_x)**2 + (node_center_y - center_y)**2)**0.5
            distances.append((distance, node))

        distances.sort(key=lambda x: x[0])

        if len(distances) > 2:
            mean_distance = sum(d[0] for d in distances) / len(distances)
            variance = sum((d[0] - mean_distance)**2 for d in distances) / len(distances)
            std_deviation = variance**0.5
            threshold = mean_distance + 1.5 * std_deviation
            
            main_nodes = [d[1] for d in distances if d[0] <= threshold]
            
            print(f"🔍 Main nodes detection:")
            print(f"   - Total nodes: {len(nodes)}")
            print(f"   - Main nodes: {len(main_nodes)}")
            print(f"   - Distance threshold: {threshold:.0f}px")
            print(f"   - Center of mass: ({center_x:.0f}, {center_y:.0f})")
            
            return main_nodes
        else:
            return nodes
    
    def get_edge_color(self, edge: Dict[str, Any]) -> str:
        """Récupère la couleur d'une connexion"""
        color_code = edge.get('color', '3')
        
        if isinstance(color_code, str) and color_code.startswith('#'):
            return color_code

        color_map = {
            "1": "#ff6b6b",
            "2": "#ffa726",
            "3": "#ffeb3b",
            "4": "#4caf50",
            "5": "#00bcd4",
            "6": "#9c27b0",
            "7": "#2196f3",
            "8": "#795548",
            "9": "#607d8b",
            "10": "#e91e63"
        }
        
        return color_map.get(color_code, "#ffeb3b")
    
    def generate_html(self) -> str:
        if not self.canvas_data:
            return ""
            
        nodes = self.canvas_data.get('nodes', [])
        edges = self.canvas_data.get('edges', [])
        
        if nodes:
            main_nodes = self.filter_main_nodes(nodes)
            
            if main_nodes:
                min_x = min(node['x'] for node in main_nodes)
                max_x = max(node['x'] + node['width'] for node in main_nodes)
                min_y = min(node['y'] for node in main_nodes)
                max_y = max(node['y'] + node['height'] for node in main_nodes)
            else:
                min_x = min(node['x'] for node in nodes)
                max_x = max(node['x'] + node['width'] for node in nodes)
                min_y = min(node['y'] for node in nodes)
                max_y = max(node['y'] + node['height'] for node in nodes)
            
            margin = 200
            title_margin = 100
            canvas_width = max_x - min_x + margin * 2
            canvas_height = max_y - min_y + margin * 2 + title_margin
            min_canvas_width = 2000
            min_canvas_height = 1500
            canvas_width = max(canvas_width, min_canvas_width)
            canvas_height = max(canvas_height, min_canvas_height)
            offset_x = -min_x + margin
            offset_y = -min_y + margin + title_margin
        else:
            canvas_width = 2000
            canvas_height = 1500
            offset_x = 0
            offset_y = 0

        html_template = Template("""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Canvas Obsidian: $title</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: #1a1a1a;
            color: #dcddde;
            overflow: hidden;
            height: 100vh;
        }
        
        .toolbar {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            height: 50px;
            background: #2d2d2d;
            border-bottom: 1px solid #404040;
            display: flex;
            align-items: center;
            padding: 0 20px;
            z-index: 1000;
        }
        
        .toolbar-title {
            font-size: 18px;
            font-weight: 600;
            color: #ffffff;
            margin-right: 20px;
        }
        
        .canvas-container {
            position: fixed;
            top: 50px;
            left: 0;
            right: 0;
            bottom: 0;
            overflow: hidden;
            background: #1a1a1a;
            background-image: 
                radial-gradient(circle at 25% 25%, #2a2a2a 1px, transparent 1px),
                radial-gradient(circle at 75% 75%, #2a2a2a 1px, transparent 1px);
            background-size: 50px 50px;
            cursor: grab;
            user-select: none;
        }
        
        .canvas-container.scroll-enabled {
            overflow: auto;
        }
        
        .canvas-container.scroll-enabled .canvas {
            min-width: 2000px;
            min-height: 1500px;
        }
        
        .canvas-container:active {
            cursor: grabbing;
        }
        
        .canvas {
            position: relative;
            width: $canvas_width;
            height: $canvas_height;
            background: transparent;
            user-select: none;
        }
        
        .node {
            position: absolute;
            border-radius: 8px;
            padding: 12px;
            cursor: default;
            user-select: none;
            transition: all 0.2s ease;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            z-index: 10;
            overflow: hidden;
        }
        
        .node.group {
            background: rgba(45, 45, 45, 0.9);
            border: 2px solid;
            backdrop-filter: blur(10px);
            padding-top: 20px;
            overflow: visible;
        }
        
        .group-title {
            position: absolute;
            top: -35px;
            left: 0px;
            background: #404040;
            color: #ffffff;
            padding: 8px 12px;
            border-radius: 6px 6px 0 0;
            font-size: 20px;
            font-weight: 600;
            text-align: left;
            border: none;
            z-index: 99999;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            pointer-events: none;
            box-shadow: 0 2px 8px rgba(0,0,0,0.5);
            width: auto;
            min-width: fit-content;
        }
        
        .node.text {
            background: #2d2d2d;
            border: 2px solid #404040;
        }
        
        .node.file {
            background: #2d2d2d;
            border: 2px solid #404040;
        }
        
        .node:hover {
            box-shadow: 0 4px 16px rgba(0,0,0,0.5);
            transform: translateY(-2px);
        }
        
        .node-content {
            color: #dcddde;
            font-size: 14px;
            line-height: 1.4;
            word-wrap: break-word;
            max-width: 100%;
            overflow-wrap: break-word;
            user-select: text;
            cursor: text;
            height: 100%;
            overflow-y: auto;
            overflow-x: hidden;
            padding-right: 8px;
        }
        
        .node-content::-webkit-scrollbar {
            width: 8px;
        }
        
        .node-content::-webkit-scrollbar-track {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
        }
        
        .node-content::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.3);
            border-radius: 4px;
        }
        
        .node-content::-webkit-scrollbar-thumb:hover {
            background: rgba(255, 255, 255, 0.5);
        }
        
        .node-content h1 {
            color: #ffffff;
            font-size: 24px;
            font-weight: 700;
            margin: 12px 0 10px 0;
            border-bottom: 2px solid currentColor;
            padding-bottom: 8px;
            word-wrap: break-word;
        }
        
        .node-content h2 {
            color: #ffffff;
            font-size: 20px;
            font-weight: 600;
            margin: 10px 0 8px 0;
            border-bottom: 1px solid currentColor;
            padding-bottom: 6px;
            word-wrap: break-word;
        }
        
        .node-content h3 {
            color: #ffffff;
            font-size: 18px;
            font-weight: 600;
            margin: 8px 0 6px 0;
            word-wrap: break-word;
        }
        
        .node-content h4 {
            color: #ffffff;
            font-size: 16px;
            font-weight: 500;
            margin: 6px 0 4px 0;
            word-wrap: break-word;
        }
        
        .node-content h5 {
            color: #ffffff;
            font-size: 14px;
            font-weight: 500;
            margin: 4px 0 2px 0;
            word-wrap: break-word;
        }
        
        .node-content h6 {
            color: #ffffff;
            font-size: 12px;
            font-weight: 500;
            margin: 2px 0 2px 0;
            word-wrap: break-word;
        }
        
        .node-content p {
            margin: 8px 0;
            word-wrap: break-word;
        }
        
        .node-content pre {
            background: #1a1a1a;
            padding: 8px;
            border-radius: 4px;
            overflow-x: auto;
            font-size: 11px;
            margin: 8px 0;
            border: 1px solid #404040;
            max-height: 150px;
            user-select: text;
            cursor: text;
            word-wrap: break-word;
        }
        
        .node-content code {
            background: #1a1a1a;
            padding: 2px 4px;
            border-radius: 3px;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 11px;
            border: 1px solid #404040;
            user-select: text;
            cursor: text;
            word-wrap: break-word;
        }
        
        .node-content .code-block {
            background: transparent;
            color: inherit;
            padding: 0;
            border-radius: 0;
            overflow-x: auto;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 12px;
            margin: 8px 0;
            border: none;
            max-height: 200px;
            user-select: text;
            cursor: text;
            word-wrap: break-word;
            line-height: 1.4;
            white-space: pre;
            tab-size: 4;
        }
        
        /* Style pour les boîtes contenant du code */
        .node.has-code .node-content {
            background: #1e1e1e;
            color: #ffffff;
            padding: 16px;
            border-radius: 8px;
            border: 1px solid #333333;
            white-space: pre;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 12px;
            line-height: 1.4;
        }
        
        .node-content strong {
            color: #ffffff;
            font-weight: 600;
        }
        
        .node-content em {
            color: #b9bbbe;
            font-style: italic;
        }
        
        .node-content a {
            color: #7289da;
            text-decoration: none;
        }
        
        .node-content a:hover {
            text-decoration: underline;
        }
        
        .node-content img {
            max-width: 100%;
            height: auto;
            border-radius: 4px;
            margin: 8px 0;
            display: block;
        }
        
        .node-content ul, .node-content ol {
            margin: 8px 0;
            padding-left: 20px;
        }
        
        .node-content li {
            margin: 4px 0;
            word-wrap: break-word;
        }
        
        .code-block {
            position: relative;
            background: #1a1a1a;
            border-radius: 6px;
            padding: 8px 8px 8px 8px;
            margin: 8px 0;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            line-height: 1.4;
            overflow-x: auto;
        }
        
        .code-content {
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        
        .copy-button {
            position: absolute;
            top: -20px;
            right: -10px;
            background: transparent;
            color: #ffffff;
            border: none;
            border-radius: 8px;
            padding: 12px 16px;
            font-size: 30px;
            cursor: pointer;
            opacity: 1;
            transition: all 0.3s ease;
            backdrop-filter: blur(4px);
            font-weight: 500;
            z-index: 10;
            pointer-events: auto;
            transform: translateZ(0);
        }
        
        .copy-button:hover {
            background: transparent;
            transform: scale(1.2);
        }
        
        .copy-button.copied {
            background: #4caf50;
            color: white;
        }
        
        .edges-layer {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 999;
        }
        
        .edge-line {
            stroke-width: 3;
            fill: none;
            marker-end: url(#arrowhead);
            stroke-linecap: round;
            filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3));
        }
        
        .edge-line:hover {
            stroke-width: 5;
            filter: drop-shadow(0 4px 8px rgba(0, 0, 0, 0.5));
        }
        
        .edge-label {
            fill: #ffffff;
            font-size: 12px;
            font-weight: bold;
            text-anchor: middle;
            dominant-baseline: middle;
        }
        
        .search-overlay {
            position: fixed;
            top: 60px;
            right: 20px;
            background: #2d2d2d;
            border: 1px solid #404040;
            border-radius: 8px;
            padding: 15px;
            width: 300px;
            z-index: 1001;
            box-shadow: 0 4px 16px rgba(0,0,0,0.3);
        }
        
        .search-input {
            width: 100%;
            background: #1a1a1a;
            border: 1px solid #404040;
            color: #dcddde;
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 14px;
            margin-bottom: 10px;
        }
        
        .search-input:focus {
            outline: none;
            border-color: #7289da;
        }
        
        .search-results {
            max-height: 200px;
            overflow-y: auto;
        }
        
        .search-result {
            padding: 8px;
            border-radius: 4px;
            cursor: pointer;
            transition: background 0.2s;
        }
        
        .search-result:hover {
            background: #404040;
        }
        
        .search-result.highlighted {
            background: #7289da;
            color: #ffffff;
        }
        
        .zoom-controls {
            position: fixed;
            bottom: 20px;
            right: 20px;
            display: flex;
            flex-direction: column;
            gap: 5px;
            z-index: 1001;
        }
        
        .zoom-btn {
            width: 40px;
            height: 40px;
            background: #2d2d2d;
            border: 1px solid #404040;
            color: #dcddde;
            border-radius: 50%;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            transition: all 0.2s;
        }
        
        .zoom-btn:hover {
            background: #404040;
            transform: scale(1.1);
        }
        
        @media (max-width: 768px) {
            .search-overlay {
                width: calc(100vw - 40px);
                right: 20px;
            }
        }
    </style>
</head>
<body>
    <div class="toolbar">
        <div class="toolbar-title">🎨 Canvas Obsidian: $title</div>
    </div>
    
    <div class="search-overlay">
        <input type="text" class="search-input" id="searchInput" placeholder="🔍 Search within content...">
        <div class="search-results" id="searchResults"></div>
    </div>
    
    <div class="zoom-controls">
        <button class="zoom-btn" id="zoomIn">+</button>
        <button class="zoom-btn" id="zoomOut">-</button>
        <button class="zoom-btn" id="zoomReset">1:1</button>
    </div>
    
    <div class="canvas-container" id="canvasContainer">
        <div class="canvas" id="canvas">
            <svg class="edges-layer" id="edgesLayer" width="$canvas_width" height="$canvas_height">
                <defs>
                    <marker id="arrowhead" markerWidth="12" markerHeight="8" 
                            refX="0" refY="4" orient="auto">
                        <polygon points="0 0, 12 4, 0 8" fill="#00ff88" />
                    </marker>
                </defs>
            </svg>
""")
        
        html_content = html_template.substitute(
            title=self.canvas_file_path.stem,
            canvas_width=f"{canvas_width}px",
            canvas_height=f"{canvas_height}px"
        )

        for i, node in enumerate(nodes):
            node_id = node.get('id', f'node_{i}')
            node_type = node.get('type', 'text')
            x = node.get('x', 100 + i * 200) + offset_x
            y = node.get('y', 100 + i * 150) + offset_y
            width = max(150, node.get('width', 200))
            height = max(60, node.get('height', 100))
            color = self.get_node_color(node)
            content = self.extract_node_content(node)
            content = content.replace('<', '&lt;').replace('>', '&gt;')

            def add_copy_button(match):
                code_content = match.group(1)

                lines = code_content.split('\n')
                if len(lines) > 1:
                    clean_code = '\n'.join(lines[1:])
                else:
                    clean_code = code_content

                return f'''<pre class="code-block" style="position: relative; margin-top: 0; padding: 8px 8px 8px 8px;"><button class="copy-button" onclick="const codeContent = this.parentElement.textContent.replace('⮻', '').trim(); navigator.clipboard.writeText(codeContent).then(() => {{this.textContent = '✅ Copié !'; this.style.background = '#4caf50'; setTimeout(() => {{this.textContent = '⮻'; this.style.background = 'transparent';}}, 2000);}}).catch(() => {{this.textContent = '❌ Erreur'; setTimeout(() => {{this.textContent = '⮻';}}, 2000);}});">⮻</button><div class="code-content">{clean_code}</div></pre>'''

            lines = content.split('\n')
            result_lines = []
            in_code_block = False
            
            for line in lines:
                if line.strip().startswith('```'):
                    in_code_block = not in_code_block
                    result_lines.append(line)
                    continue

                if in_code_block:
                    result_lines.append(line)
                else:
                    if line.strip().startswith('# '):
                        result_lines.append(re.sub(r'^# (.*)$', r'<h1>\1</h1>', line))
                    elif line.strip().startswith('## '):
                        result_lines.append(re.sub(r'^## (.*)$', r'<h2>\1</h2>', line))
                    elif line.strip().startswith('### '):
                        result_lines.append(re.sub(r'^### (.*)$', r'<h3>\1</h3>', line))
                    elif line.strip().startswith('#### '):
                        result_lines.append(re.sub(r'^#### (.*)$', r'<h4>\1</h4>', line))
                    elif line.strip().startswith('##### '):
                        result_lines.append(re.sub(r'^##### (.*)$', r'<h5>\1</h5>', line))
                    elif line.strip().startswith('###### '):
                        result_lines.append(re.sub(r'^###### (.*)$', r'<h6>\1</h6>', line))
                    else:
                        result_lines.append(line)
            
            content = '\n'.join(result_lines)
            
            has_code = '```' in content
            if has_code:
                content = self.clean_content_after_code(content)
                content = re.sub(r'```([\s\S]*?)```', add_copy_button, content)
            
            content = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', content)
            content = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', content)
            content = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank">\1</a>', content)
            content = re.sub(r'\n\s*\n', '</p><p>', content)
            content = '<p>' + content + '</p>'
            content = re.sub(r'<p>\s*</p>', '', content)
            content = re.sub(r'\n', '<br>', content)
            content = re.sub(r'<p>(\d+)\.\s+(.+?)</p>', r'<li>\2</li>', content)
            content = re.sub(r'<p>[-*]\s+(.+?)</p>', r'<li>\1</li>', content)
            lines = content.split('<br>')
            result_lines = []
            in_list = False
            list_type = None
            
            for line in lines:
                if line.strip().startswith('<li>'):
                    if not in_list:
                        if re.search(r'^\d+\.', line):
                            list_type = 'ol'
                        else:
                            list_type = 'ul'
                        result_lines.append(f'<{list_type}>')
                        in_list = True
                    result_lines.append(line)
                else:
                    if in_list:
                        result_lines.append(f'</{list_type}>')
                        in_list = False
                    result_lines.append(line)

            if in_list:
                result_lines.append(f'</{list_type}>')
            
            content = '<br>'.join(result_lines)
            
            if node_type == 'group':
                border_color = color
                # Convert hex color to RGB for transparency
                if color.startswith('#'):
                    r = int(color[1:3], 16)
                    g = int(color[3:5], 16)
                    b = int(color[5:7], 16)
                    if width * height > 4000000:
                        background_color = f"rgba({r}, {g}, {b}, 0.05)"
                    else:
                        background_color = f"rgba({r}, {g}, {b}, 0.3)"
                else:
                    # For numeric colors, convert to hex first, then to RGB
                    numeric_color = self.get_node_color(node)
                    if numeric_color.startswith('#'):
                        r = int(numeric_color[1:3], 16)
                        g = int(numeric_color[3:5], 16)
                        b = int(numeric_color[5:7], 16)
                        if width * height > 4000000:
                            background_color = f"rgba({r}, {g}, {b}, 0.05)"
                        else:
                            background_color = f"rgba({r}, {g}, {b}, 0.3)"
                    else:
                        background_color = "rgba(76, 175, 80, 0.3)"  # Default green
                label = node.get('label', 'Unnamed Group')
                code_class = " has-code" if has_code else ""
                html_content += f"""
            <div class="node {node_type}{code_class}" id="{node_id}" data-type="{node_type}" 
                 style="left: {x}px; top: {y}px; width: {width}px; height: {height}px; border: 2px solid {border_color} !important; background-color: {background_color};">
                <div class="group-title" style="background-color: {color}; color: #000000;">{label}</div>
                <div class="node-content">{content}</div>
            </div>
            """
            else:
                # Check if node has a specific color defined
                node_color = node.get('color')
                if node_color:
                    border_color = color
                    border_style = f"border: 2px solid {border_color} !important;"
                else:
                    # No color defined - use default CSS border
                    border_style = ""
                background_color = "transparent"
                code_class = " has-code" if has_code else ""
                html_content += f"""
            <div class="node {node_type}{code_class}" id="{node_id}" data-type="{node_type}" 
                 style="left: {x}px; top: {y}px; width: {width}px; height: {height}px; {border_style} background-color: {background_color};">
                <div class="node-content">{content}</div>
            </div>
            """

        html_end_template = Template("""
        </div>
    </div>

    <script>
        class ObsidianCanvas {
            constructor() {
                this.canvas = document.getElementById('canvas');
                this.container = document.getElementById('canvasContainer');
                this.edgesLayer = document.getElementById('edgesLayer');
                this.nodes = [];
                this.edges = [];
                this.zoom = 1;
                this.optimalZoom = 1;
                this.init();
            }
            
            init() {
                this.loadCanvasData();
                this.setupEventListeners();
                this.drawEdges();
                this.centerView();
            }
            
            loadCanvasData() {
                const nodeElements = document.querySelectorAll('.node');
                nodeElements.forEach(nodeEl => {
                    this.nodes.push({
                        id: nodeEl.id,
                        element: nodeEl,
                        x: parseFloat(nodeEl.style.left),
                        y: parseFloat(nodeEl.style.top),
                        width: parseFloat(nodeEl.style.width),
                        height: parseFloat(nodeEl.style.height),
                        type: nodeEl.dataset.type
                    });
                });
                const edgesData = $edges_json;
                this.edges = edgesData;
                
                console.log('Canvas loaded:', this.nodes.length, 'nodes,', this.edges.length, 'connections');
            }
            
            centerView() {
                if (this.nodes.length > 0) {
                    const minX = Math.min(...this.nodes.map(n => n.x));
                    const maxX = Math.max(...this.nodes.map(n => n.x + n.width));
                    const minY = Math.min(...this.nodes.map(n => n.y));
                    const maxY = Math.max(...this.nodes.map(n => n.y + n.height));
                    const contentWidth = maxX - minX;
                    const contentHeight = maxY - minY;
                    const containerWidth = this.container.clientWidth;
                    const containerHeight = this.container.clientHeight;
                    const margin = 100;
                    const scaleX = (containerWidth - margin) / contentWidth;
                    const scaleY = (containerHeight - margin) / contentHeight;
                    const optimalZoom = Math.min(scaleX, scaleY, 1);
                    const finalZoom = Math.max(optimalZoom, 0.1);
                    this.zoom = finalZoom;
                    this.optimalZoom = finalZoom;
                    this.applyZoom();
                    const centerX = (minX + maxX) / 2;
                    const centerY = (minY + maxY) / 2;
                    const finalScrollLeft = (centerX * this.zoom) - (containerWidth / 2);
                    const finalScrollTop = (centerY * this.zoom) - (containerHeight / 2);
                    this.container.scrollLeft = finalScrollLeft;
                    this.container.scrollTop = finalScrollTop;
                    console.log('Initial optimal view (auto-zoom out):', {
                        finalZoom: this.zoom,
                        contentWidth: contentWidth,
                        contentHeight: contentHeight,
                        containerWidth: containerWidth,
                        containerHeight: containerHeight,
                        finalScrollLeft: finalScrollLeft,
                        finalScrollTop: finalScrollTop
                    });
                }
            }
            
            setupEventListeners() {
                document.getElementById('zoomIn').addEventListener('click', () => {
                    this.zoomIn();
                });
                
                document.getElementById('zoomOut').addEventListener('click', () => {
                    this.zoomOut();
                });
                
                document.getElementById('zoomReset').addEventListener('click', () => {
                    this.zoomReset();
                });
                
                document.getElementById('searchInput').addEventListener('input', (e) => {
                    this.searchNodes(e.target.value);
                });
                
                this.container.addEventListener('mousedown', (e) => {
                    this.startPanning(e);
                });
                
                this.container.addEventListener('mousemove', (e) => {
                    this.pan(e);
                });
                
                this.container.addEventListener('mouseup', (e) => {
                    this.stopPanning();
                });
                
                this.container.addEventListener('wheel', (e) => {
                    this.handleWheel(e);
                });
                
                this.container.addEventListener('mousemove', (e) => {
                    this.lastMouseX = e.clientX;
                    this.lastMouseY = e.clientY;
                });
            }
            
            startPanning(e) {
                if (e.target.closest('.node')) return;
                
                this.isPanning = true;
                this.panStart = { x: e.clientX, y: e.clientY };
                this.scrollStart = { x: this.container.scrollLeft, y: this.container.scrollTop };
                this.container.style.cursor = 'grabbing';
            }
            
            pan(e) {
                if (!this.isPanning) return;
                
                const deltaX = e.clientX - this.panStart.x;
                const deltaY = e.clientY - this.panStart.y;
                
                this.container.scrollLeft = this.scrollStart.x - deltaX;
                this.container.scrollTop = this.scrollStart.y - deltaY;
            }
            
            stopPanning() {
                this.isPanning = false;
                this.container.style.cursor = 'grab';
            }
            
            handleWheel(e) {
                if (e.ctrlKey || e.metaKey) {
                    e.preventDefault();
                    const mouseX = e.clientX;
                    const mouseY = e.clientY;
                    const canvasRect = this.canvas.getBoundingClientRect();
                    const relativeX = (mouseX - canvasRect.left) / this.zoom + this.container.scrollLeft / this.zoom;
                    const relativeY = (mouseY - canvasRect.top) / this.zoom + this.container.scrollTop / this.zoom;
                    const oldZoom = this.zoom;
                    const delta = e.deltaY > 0 ? 0.9 : 1.1;
                    this.zoom *= delta;
                    const minZoom = this.calculateMinZoom();
                    this.zoom = Math.max(minZoom, Math.min(3, this.zoom));
                    this.applyZoomWithMouseFocus(relativeX, relativeY, oldZoom);
                }
            }
            
            drawEdges() {
                console.log('Drawing connections...');
                this.edges.forEach(edge => {
                    this.drawEdge(edge);
                });
            }
            
            drawEdge(edge) {
                const fromNode = this.nodes.find(n => n.id === edge.fromNode);
                const toNode = this.nodes.find(n => n.id === edge.toNode);
                
                if (!fromNode || !toNode) {
                    console.warn('Missing node for connection:', edge);
                    return;
                }

                const fromAnchor = this.calculateAnchorPoint(fromNode, toNode, edge.fromSide || 'right', false);
                const toAnchor = this.calculateAnchorPoint(toNode, fromNode, edge.toSide || 'left', true);
                
                console.log('Drawing connection:', edge.id, 'from', fromNode.id, 'to', toNode.id);
                console.log('FromSide:', edge.fromSide, 'ToSide:', edge.toSide);
                console.log('FromAnchor:', fromAnchor, 'ToAnchor:', toAnchor);
                const midX = (fromAnchor.x + toAnchor.x) / 2;
                const midY = (fromAnchor.y + toAnchor.y) / 2;
                const dx = toAnchor.x - fromAnchor.x;
                const dy = toAnchor.y - fromAnchor.y;
                const distance = Math.sqrt(dx * dx + dy * dy);
                const baseOffset = Math.min(distance * 0.4, 60);
                const randomFactor = 0.8 + Math.random() * 0.4;
                let offset = baseOffset * randomFactor;
                const isHorizontalPerfect = Math.abs(fromAnchor.y - toAnchor.y) < 1;
                const isHorizontalConnection = Math.abs(dx) > Math.abs(dy) * 3;
                const isVerticalPerfect = Math.abs(fromAnchor.x - toAnchor.x) < 1;
                const isVerticalConnection = Math.abs(dy) > Math.abs(dx) * 3;
                const fromSide = edge.fromSide || 'right';
                const toSide = edge.toSide || 'left';
                const sameSideConnection = fromSide === toSide;
                let path;
                let labelX, labelY;
                
                if (isHorizontalPerfect && isHorizontalConnection && !sameSideConnection) {
                    const controlPoints = this.createPerpendicularControlPoints(fromAnchor, toAnchor, fromSide, toSide);
                    path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                    const d = 'M ' + fromAnchor.x + ' ' + fromAnchor.y + 
                              ' L ' + controlPoints.fromControl.x + ' ' + controlPoints.fromControl.y + 
                              ' L ' + controlPoints.toControl.x + ' ' + controlPoints.toControl.y + 
                              ' L ' + toAnchor.x + ' ' + toAnchor.y;
                    path.setAttribute('d', d);
                    labelX = (fromAnchor.x + toAnchor.x) / 2;
                    labelY = fromAnchor.y;
                } else if (isVerticalPerfect && isVerticalConnection && !sameSideConnection) {
                    const controlPoints = this.createPerpendicularControlPoints(fromAnchor, toAnchor, fromSide, toSide);
                    path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                    const d = 'M ' + fromAnchor.x + ' ' + fromAnchor.y + 
                              ' L ' + controlPoints.fromControl.x + ' ' + controlPoints.fromControl.y + 
                              ' L ' + controlPoints.toControl.x + ' ' + controlPoints.toControl.y + 
                              ' L ' + toAnchor.x + ' ' + toAnchor.y;
                    path.setAttribute('d', d);

                    labelX = fromAnchor.x;
                    labelY = (fromAnchor.y + toAnchor.y) / 2;
                } else {
                    const controlPoints = this.createPerpendicularControlPoints(fromAnchor, toAnchor, fromSide, toSide);
                    let direction;
                    
                    if (sameSideConnection) {
                        console.log('Same side connection detected:', fromSide, '→', toSide);
                        if (fromSide === 'left' && toSide === 'left') {
                            direction = -1;
                            console.log('Left→Left: direction =', direction);
                        } else if (fromSide === 'right' && toSide === 'right') {
                            direction = 1;
                            console.log('Right→Right: direction =', direction);
                        } else if (fromSide === 'top' && toSide === 'top') {
                            direction = -1;
                            console.log('Top→Top: direction =', direction);
                        } else if (fromSide === 'bottom' && toSide === 'bottom') {
                            direction = 1;
                            console.log('Bottom→Bottom: direction =', direction);
                        } else {
                            direction = Math.random() > 0.5 ? 1 : -1;
                            console.log('Default direction:', direction);
                        }

                        offset = Math.min(offset * 1.2, 40);
                        console.log('Offset adjusted for same side:', offset);
                    } else {
                        direction = Math.random() > 0.5 ? 1 : -1;
                        console.log('Random direction for opposite sides:', direction);
                    }

                    let perpX, perpY;
                    
                    if (Math.abs(dx) > Math.abs(dy)) {
                        perpX = 0;
                        perpY = direction * offset;
                        console.log('Horizontal connection: perpX =', perpX, 'perpY =', perpY);
                    } else {
                        perpX = direction * offset;
                        perpY = 0;
                        console.log('Vertical connection: perpX =', perpX, 'perpY =', direction * offset);
                    }

                    const midControlX = midX + perpX;
                    const midControlY = midY + perpY;
                    console.log('Central control point:', midControlX, midControlY);
                    path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                    
                    const adjustedEndPoint = this.adjustArrowEndPoint(toAnchor, toSide);
                    const d = 'M ' + fromAnchor.x + ' ' + fromAnchor.y + 
                              ' C ' + controlPoints.fromControl.x + ' ' + controlPoints.fromControl.y + 
                              ' ' + controlPoints.toControl.x + ' ' + controlPoints.toControl.y + 
                              ' ' + adjustedEndPoint.x + ' ' + adjustedEndPoint.y;
                    path.setAttribute('d', d);
                    console.log("Original anchor point:", toAnchor);
                    console.log("Adjusted end point:", adjustedEndPoint);
                    console.log('SVG path created with curve and arrow base arrival:', d);
                    const t = 0.5;
                    const oneMinusT = 1 - t;
                    const oneMinusTSquared = oneMinusT * oneMinusT;
                    const oneMinusTCubed = oneMinusTSquared * oneMinusT;
                    const tSquared = t * t;
                    const tCubed = tSquared * t;
                    labelX = oneMinusTCubed * fromAnchor.x + 
                            3 * oneMinusTSquared * t * controlPoints.fromControl.x + 
                            3 * oneMinusT * tSquared * controlPoints.toControl.x + 
                            tCubed * adjustedEndPoint.x;
                    labelY = oneMinusTCubed * fromAnchor.y + 
                            3 * oneMinusTSquared * t * controlPoints.fromControl.y + 
                            3 * oneMinusT * tSquared * controlPoints.toControl.y + 
                            tCubed * adjustedEndPoint.y;
                }
                
                path.setAttribute('class', 'edge-line');
                path.setAttribute('fill', 'none');
                path.setAttribute('stroke', this.getEdgeColor(edge));
                path.setAttribute('stroke-width', '2');
                path.setAttribute('marker-end', 'url(#arrowhead)');
                
                console.log('Arrow color applied:', {
                    edgeId: edge.id,
                    edgeColor: edge.color,
                    finalColor: this.getEdgeColor(edge)
                });
                
                this.edgesLayer.appendChild(path);

                if (edge.label) {
                    console.log('Adding label:', edge.label, 'at position:', labelX, labelY);
                    
                    const labelGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
                    
                    const textElement = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    textElement.setAttribute('x', labelX);
                    textElement.setAttribute('y', labelY);
                    textElement.setAttribute('class', 'edge-label');
                    textElement.textContent = edge.label;

                    this.edgesLayer.appendChild(labelGroup);
                    labelGroup.appendChild(textElement);

                    setTimeout(() => {
                        try {
                            const bbox = textElement.getBBox();
                            const padding = 6;
                            
                            console.log('Text dimensions after timeout:', bbox);
                            
                            if (bbox.width > 0 && bbox.height > 0) {
                                const backgroundRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
                                backgroundRect.setAttribute('x', bbox.x - padding);
                                backgroundRect.setAttribute('y', bbox.y - padding);
                                backgroundRect.setAttribute('width', bbox.width + padding * 2);
                                backgroundRect.setAttribute('height', bbox.height + padding * 2);
                                backgroundRect.setAttribute('fill', 'rgba(128, 128, 128, 0.8)');
                                backgroundRect.setAttribute('rx', '4');
                                backgroundRect.setAttribute('ry', '4');
                                labelGroup.insertBefore(backgroundRect, textElement);
                                console.log('Label background added successfully');
                            } else {
                                console.warn('Text dimensions still null, using default dimensions');
                                const defaultWidth = edge.label.length * 8;
                                const defaultHeight = 16;
                                
                                const backgroundRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
                                backgroundRect.setAttribute('x', labelX - defaultWidth/2 - padding);
                                backgroundRect.setAttribute('y', labelY - defaultHeight/2 - padding);
                                backgroundRect.setAttribute('width', defaultWidth + padding * 2);
                                backgroundRect.setAttribute('height', defaultHeight + padding * 2);
                                backgroundRect.setAttribute('fill', 'rgba(128, 128, 128, 0.8)');
                                backgroundRect.setAttribute('rx', '4');
                                backgroundRect.setAttribute('ry', '4');
                                
                                labelGroup.insertBefore(backgroundRect, textElement);
                                console.log('Label background added with default dimensions');
                            }
                        } catch (error) {
                            console.error('Error creating label background:', error);
                        }
                    }, 0);
                    
                    console.log('Label added successfully');
                }
            }
            
            calculateAnchorPoint(node, targetNode, side, isArrival = false) {
                const centerX = node.x + node.width / 2;
                const centerY = node.y + node.height / 2;
                
                let anchorX, anchorY;

                const offset = isArrival ? 30 : 0;
                
                switch(side) {
                    case 'top':
                        anchorX = centerX;
                        anchorY = node.y - offset;
                        break;
                    case 'bottom':
                        anchorX = centerX;
                        anchorY = node.y + node.height + offset;
                        break;
                    case 'left':
                        anchorX = node.x - offset;
                        anchorY = centerY;
                        break;
                    case 'right':
                        anchorX = node.x + node.width + offset;
                        anchorY = centerY;
                        break;
                    default:
                        const dx = targetNode.x - node.x;
                        const dy = targetNode.y - node.y;
                        
                        if (Math.abs(dx) > Math.abs(dy)) {
                            if (dx > 0) {
                                anchorX = node.x + node.width + offset;
                                anchorY = centerY;
                            } else {
                                anchorX = node.x - offset;
                                anchorY = centerY;
                            }
                        } else {
                            // Connexion verticale
                            if (dy > 0) {
                                anchorX = centerX;
                                anchorY = node.y + node.height + offset;
                            } else {
                                anchorX = centerX;
                                anchorY = node.y - offset;
                            }
                        }
                }
                
                return { x: anchorX, y: anchorY };
            }

            createPerpendicularControlPoints(fromAnchor, toAnchor, fromSide, toSide) {
                const offset = 80;
                
                let fromControl, toControl;

                switch(fromSide) {
                    case 'top':
                        fromControl = { x: fromAnchor.x, y: fromAnchor.y - offset };
                        break;
                    case 'bottom':
                        fromControl = { x: fromAnchor.x, y: fromAnchor.y + offset };
                        break;
                    case 'left':
                        fromControl = { x: fromAnchor.x - offset, y: fromAnchor.y };
                        break;
                    case 'right':
                        fromControl = { x: fromAnchor.x + offset, y: fromAnchor.y };
                        break;
                    default:
                        fromControl = fromAnchor;
                }

                switch(toSide) {
                    case 'top':
                        toControl = { x: toAnchor.x, y: toAnchor.y - offset };
                        break;
                    case 'bottom':
                        toControl = { x: toAnchor.x, y: toAnchor.y + offset };
                        break;
                    case 'left':
                        toControl = { x: toAnchor.x - offset, y: toAnchor.y };
                        break;
                    case 'right':
                        toControl = { x: toAnchor.x + offset, y: toAnchor.y };
                        break;
                    default:
                        toControl = toAnchor;
                }
                
                return { fromControl, toControl };
            }

            adjustArrowEndPoint(toAnchor, toSide) {
                return toAnchor;
            }
            
            getEdgeColor(edge) {
                const colorCode = edge.color || "3";

                if (typeof colorCode === 'string' && colorCode.startsWith('#')) {
                    return colorCode;
                }

                const colorMap = {
                    "1": "#ff6b6b",
                    "2": "#ffa726",
                    "3": "#ffeb3b",
                    "4": "#4caf50",
                    "5": "#00bcd4",
                    "6": "#9c27b0",
                    "7": "#2196f3",
                    "8": "#795548",
                    "9": "#607d8b",
                    "10": "#e91e63"
                };
                
                return colorMap[colorCode] || "#ffeb3b";
            }
            
            searchNodes(query) {
                const results = document.getElementById('searchResults');
                results.innerHTML = '';
                
                if (!query.trim()) return;
                
                const matchingNodes = this.nodes.filter(node => {
                    const content = node.element.querySelector('.node-content').textContent.toLowerCase();
                    return content.includes(query.toLowerCase());
                });
                
                matchingNodes.forEach(node => {
                    const resultEl = document.createElement('div');
                    resultEl.className = 'search-result';
                    resultEl.textContent = node.element.querySelector('.node-content').textContent.substring(0, 50) + '...';
                    
                    resultEl.addEventListener('click', () => {
                        this.scrollToNode(node);
                        this.highlightNode(node);
                    });
                    
                    results.appendChild(resultEl);
                });
            }
            
            scrollToNode(node) {
                const containerRect = this.container.getBoundingClientRect();
                const zoomedX = node.x * this.zoom;
                const zoomedY = node.y * this.zoom;
                const zoomedWidth = node.width * this.zoom;
                const zoomedHeight = node.height * this.zoom;
                
                this.container.scrollTo({
                    left: zoomedX - containerRect.width / 2 + zoomedWidth / 2,
                    top: zoomedY - containerRect.height / 2 + zoomedHeight / 2,
                    behavior: 'smooth'
                });
                
                console.log('Scroll to node with zoom:', {
                    nodeId: node.id,
                    originalX: node.x,
                    originalY: node.y,
                    zoom: this.zoom,
                    zoomedX: zoomedX,
                    zoomedY: zoomedY,
                    scrollLeft: zoomedX - containerRect.width / 2 + zoomedWidth / 2,
                    scrollTop: zoomedY - containerRect.height / 2 + zoomedHeight / 2
                });
            }
            
            highlightNode(node) {
                node.element.style.boxShadow = '0 0 0 3px rgba(114, 137, 218, 0.8)';
                setTimeout(() => {
                    node.element.style.boxShadow = '';
                }, 2000);
            }
            
            zoomIn() {
                const oldZoom = this.zoom;
                this.zoom = Math.min(this.zoom * 1.2, 3);
                const mouseX = this.lastMouseX || (this.container.clientWidth / 2);
                const mouseY = this.lastMouseY || (this.container.clientHeight / 2);
                const canvasRect = this.canvas.getBoundingClientRect();
                const relativeX = (mouseX - canvasRect.left) / oldZoom + this.container.scrollLeft / oldZoom;
                const relativeY = (mouseY - canvasRect.top) / oldZoom + this.container.scrollTop / oldZoom;
                
                this.applyZoomWithMouseFocus(relativeX, relativeY, oldZoom);
            }
            
            zoomOut() {
                const oldZoom = this.zoom;
                this.zoom = this.zoom / 1.2;
                const minZoom = this.calculateMinZoom();
                this.zoom = Math.max(minZoom, this.zoom);
                const mouseX = this.lastMouseX || (this.container.clientWidth / 2);
                const mouseY = this.lastMouseY || (this.container.clientHeight / 2);
                const canvasRect = this.canvas.getBoundingClientRect();
                const relativeX = (mouseX - canvasRect.left) / oldZoom + this.container.scrollLeft / oldZoom;
                const relativeY = (mouseY - canvasRect.top) / oldZoom + this.container.scrollTop / oldZoom;
                
                this.applyZoomWithMouseFocus(relativeX, relativeY, oldZoom);
            }
            
            calculateMinZoom() {
                const containerWidth = this.container.clientWidth;
                const containerHeight = this.container.clientHeight;
                const minX = Math.min(...this.nodes.map(n => n.x));
                const maxX = Math.max(...this.nodes.map(n => n.x + n.width));
                const minY = Math.min(...this.nodes.map(n => n.y));
                const maxY = Math.max(...this.nodes.map(n => n.y + n.height));
                
                const contentWidth = maxX - minX;
                const contentHeight = maxY - minY;
                const margin = 100;
                const scaleX = (containerWidth - margin) / contentWidth;
                const scaleY = (containerHeight - margin) / contentHeight;
                const optimalZoom = Math.min(scaleX, scaleY, 1);
                const finalZoom = Math.max(optimalZoom, 0.1);
                
                return finalZoom;
            }
            
            zoomReset() {
                this.centerView();
            }
            
            applyZoom() {
                this.canvas.style.transform = `scale($${this.zoom})`;
                this.canvas.style.transformOrigin = 'top left';
                if (this.optimalZoom === undefined || this.optimalZoom === 1) {
                    this.optimalZoom = this.zoom;
                }
                const isOptimal = Math.abs(this.zoom - this.optimalZoom) < 0.05;
                
                console.log('applyZoom debug:', {
                    currentZoom: this.zoom,
                    optimalZoom: this.optimalZoom,
                    difference: Math.abs(this.zoom - this.optimalZoom),
                    isOptimal: isOptimal
                });
                
                if (isOptimal) {
                    this.container.classList.remove('scroll-enabled');
                    console.log('Scroll disabled - optimal view');
                } else {
                    this.container.classList.add('scroll-enabled');
                    console.log('Scroll enabled - different zoom');
                }
            }

            applyZoomWithMouseFocus(relativeX, relativeY, oldZoom) {
                this.applyZoom();

                const mouseX = relativeX * oldZoom - this.container.scrollLeft;
                const mouseY = relativeY * oldZoom - this.container.scrollTop;
                const newScrollLeft = relativeX * this.zoom - mouseX;
                const newScrollTop = relativeY * this.zoom - mouseY;

                this.container.scrollLeft = newScrollLeft;
                this.container.scrollTop = newScrollTop;
                
                console.log('Zoom on mouse pointer (dynamic):', {
                    relativeX: relativeX,
                    relativeY: relativeY,
                    oldZoom: oldZoom,
                    newZoom: this.zoom,
                    mouseX: mouseX,
                    mouseY: mouseY,
                    newScrollLeft: newScrollLeft,
                    newScrollTop: newScrollTop
                });
            }

            applyZoomWithCenterFocus(oldZoom) {

                this.applyZoom();

                const centerX = this.container.clientWidth / 2;
                const centerY = this.container.clientHeight / 2;
                const newScrollLeft = centerX * this.zoom - (centerX * oldZoom - this.container.scrollLeft);
                const newScrollTop = centerY * this.zoom - (centerY * oldZoom - this.container.scrollTop);
                
                this.container.scrollLeft = newScrollLeft;
                this.container.scrollTop = newScrollTop;
            }
        }

        function copyCode(button) {
            const codeBlock = button.parentElement;
            const pre = codeBlock.querySelector('pre');
            const codeContent = pre.textContent;
            
            navigator.clipboard.writeText(codeContent).then(() => {
                button.textContent = '✅ Copied!';
                button.classList.add('copied');
                
                setTimeout(() => {
                    button.textContent = '⮻';
                    button.classList.remove('copied');
                }, 2000);
            }).catch(err => {
                console.error('Copy error:', err);
                button.textContent = '❌ Error';
                setTimeout(() => {
                    button.textContent = '⮻';
                }, 2000);
            });
        }

        document.addEventListener('DOMContentLoaded', () => {
            const canvas = new ObsidianCanvas();
        });
    </script>
</body>
</html>""")
        html_content += html_end_template.substitute(
            edges_json=json.dumps(edges)
        )

        if '__IMAGE_PLACEHOLDER_' in html_content:
            matches = re.findall(r'__IMAGE_PLACEHOLDER_(_src/.*?\.(?:png|jpg|jpeg|gif|svg))__', html_content)
            print(f"🔍 Image markers found: {matches}")
            for match in matches:
                old_marker = f'__IMAGE_PLACEHOLDER_{match}__'
                new_img = f'<img src="{match}" alt="Image" style="width: 100%; height: 100%; object-fit: cover; border-radius: 4px; display: block;">'
                html_content = html_content.replace(old_marker, new_img)
                print(f"🔄 Replaced: {old_marker} → {new_img[:50]}...")
        
        return html_content
    
    def copy_referenced_images(self) -> None:
        if not self.canvas_data:
            return
            
        nodes = self.canvas_data.get('nodes', [])
        
        for node in nodes:
            if node.get('type') == 'file':
                file_path = node.get('file', '')
                if file_path:
                    canvas_image_dir = Path(self.canvas_file_path.parent) / "_src"
                    image_file = canvas_image_dir / Path(file_path).name
                    
                    if image_file.exists():
                        print(f"✅ Image found: {image_file}")
                    else:
                        print(f"⚠️ Image not found: {image_file}")
                        print(f"   Check that the file exists in: {canvas_image_dir}")
    
    def export_to_web(self) -> bool:
        try:
            if not self.create_output_directory():
                return False
                
            html_content = self.generate_html()
            html_file = self.output_dir / "index.html"
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            self.copy_referenced_images()
            
            print(f"✅ Export completed successfully!")
            print(f"✅ Output directory: {self.output_dir}")
            print(f"✅ Open {html_file} in your browser")
            print(f"✅ Obsidian-faithful interface with interactive canvas")
            
            return True
            
        except Exception as e:
            print(f"❌ Export error: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(
        description="Exports Obsidian .canvas files to an interactive web format faithful to the original",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage examples:
  python3 obsidianexporter.py my_canvas.canvas
  python3 obsidianexporter.py /path/to/my_canvas.canvas
        """
    )
    
    parser.add_argument(
        'canvas_file',
        help='Path to the .canvas file to export'
    )
    
    args = parser.parse_args()
    
    print("Obsidian Canvas Exporter - Obsidian-faithful interface")
    print("=" * 60)
    exporter = ObsidianCanvasExporter(args.canvas_file)
    
    if not exporter.load_canvas():     
          sys.exit(1)
    
    if not exporter.export_to_web():
        sys.exit(1)
    
    print("\n🎉 Export completed successfully!")
    print("🎨 Interface now faithfully reproduces Obsidian!")

if __name__ == "__main__":
    main()
