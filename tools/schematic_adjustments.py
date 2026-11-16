#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YaolinDong
"""Apply reviewed drawing-only corrections after the functional layout pass."""
from pathlib import Path
from copy import deepcopy
import hashlib,json
from native_project import symbol_pins,pin_world
ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'tools/schematic_text_adjustments.json'

def apply_adjustments(project,sheet,config=None):
    config=config if config is not None else json.loads(CONFIG.read_text())
    spec=config.get('sheets',{}).get(sheet,{})
    d=project.of_type('SCH_PAGE');parts=d.components()
    def pin(ref,num):
        _,co,attrs=parts[ref];symbol=project.docs['SYMBOL',attrs['Symbol'][1]['value']]
        _,p=symbol_pins(symbol)[str(num)];return tuple(round(x,8) for x in pin_world(p,co))
    routes=[]
    for item in spec.get('routes',[]):
        ends={pin(*x) for x in item['pins']};matches=[]
        for gid,_ in d.items('WIRE'):
            if d.attributes(gid).get('NET',('',{}))[1].get('value')!=item['net']:continue
            points={(v[kx],v[ky]) for _,v in d.items('LINE') if v.get('lineGroup')==gid for kx,ky in [('startX','startY'),('endX','endY')]}
            if ends<=points:matches.append(gid)
        if len(matches)!=1:raise ValueError(f'Cannot identify reviewed wire group: {sheet}/{item["net"]}')
        routes.append((matches[0],item))
    for ref,target in spec.get('components',{}).items():
        cid,co,attrs=parts[ref];dx=target[0]-co['x'];dy=target[1]-co['y'];co['x'],co['y']=target
        for _,a in d.items('ATTR'):
            parent=a.get('parentId','')
            if parent==cid or parent.startswith(cid+'-'):
                if a.get('x') is not None:a['x']=round(a['x']+dx,8)
                if a.get('y') is not None:a['y']=round(a['y']+dy,8)
    for gid,item in routes:
        old=[(i,v) for i,v in d.items('LINE') if v.get('lineGroup')==gid]
        points=[pin(*p['pin']) if isinstance(p,dict) else tuple(p) for p in item['path']]
        for a,b in zip(points,points[1:]):
            if a[0]!=b[0] and a[1]!=b[1]:raise ValueError('Reviewed path is not orthogonal')
        for i,_ in old:del d.records['LINE',i]
        for index,(a,b) in enumerate(zip(points,points[1:])):
            ident=old[index][0] if index<len(old) else hashlib.sha256(f'text-clearance:{sheet}:{gid}:{index}'.encode()).hexdigest()[:16]
            v=deepcopy(old[0][1]);v.update(startX=a[0],startY=a[1],endX=b[0],endY=b[1]);d.records['LINE',ident]=v
    for item in spec.get('attributes',[]):
        key=('ATTR',item['id']);a=d.records.get(key)
        if a is None or a.get('key')!=item['key'] or a.get('value')!=item['value']:raise ValueError(f'Text correction no longer matches: {sheet}/{item["id"]}')
        a.update({k:item[k] for k in ['x','y','rotation'] if k in item})
    return project
