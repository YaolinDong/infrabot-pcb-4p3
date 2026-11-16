# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YaolinDong
"""Reviewed SVG text offsets shared by PDF rendering and its clearance audit."""
import json
from pathlib import Path

CONFIG = Path(__file__).with_name('schematic_pdf_text_offsets.json')

def prepare_svg(root, sheet):
    offsets = json.loads(CONFIG.read_text())['sheets'].get(sheet, [])
    nodes = {e.get('id'): e for e in root.iter() if e.get('id')}
    for item in offsets:
        if 'parent_id' in item:
            # EDA regenerates inherited attribute IDs when a project reopens.
            # Pin-group IDs and the name/number text slots remain stable.
            parent = nodes.get(item['parent_id'])
            children = [] if parent is None else [e for e in parent if e.tag.endswith('text')]
            index = item['text_index']
            node = children[index] if index < len(children) else None
            identity = item['parent_id'] + ':' + str(index)
        else:
            node = nodes.get(item['id'])
            identity = item['id']
        if node is None or ''.join(node.itertext()) != item['text']:
            raise ValueError('Reviewed PDF text no longer matches: ' + identity)
        transform = node.get('transform', '')
        node.set('transform', f'translate({item["dx"]},{item["dy"]}) ' + transform)
    return len(offsets)
