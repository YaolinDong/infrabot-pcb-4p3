#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YaolinDong
"""Audit rendered text against schematic wires, text, and pin-stem crossings.

Optional documentation check; requires system PyGObject/Rsvg. Uses the same
SVG preparation and font renderer as build_schematic_pdf.py. No source edits.
It does not check electrical behavior or replace native ERC/visual review.
"""
from pathlib import Path
import argparse,hashlib,json,math,zipfile,xml.etree.ElementTree as ET
from native_project import ProjectFile,pin_world,rotate,symbol_pins
from check_connectivity import schematic_connections
from schematic_svg import prepare_svg
ROOT=Path(__file__).resolve().parents[1]
# Native schematic units are 10 mil; test ink clearance, not just intersection.
MIN_TEXT_GAP=1.5

def rect_distance(a,b):
    return math.hypot(max(a[0]-b[2],b[0]-a[2],0),max(a[1]-b[3],b[1]-a[3],0))

def segment_box(a,b):
    if abs(a[0]-b[0])>1e-6 and abs(a[1]-b[1])>1e-6:
        raise ValueError('Only orthogonal schematic segments are supported')
    return [min(a[0],b[0]),min(a[1],b[1]),max(a[0],b[0]),max(a[1],b[1])]

def audit_sheet(data,project,sheet,raw=False):
    import gi
    gi.require_version('Rsvg','2.0')
    from gi.repository import Rsvg
    svg=ET.fromstring(data)
    offsets=0 if raw else prepare_svg(svg,sheet)
    handle=Rsvg.Handle.new_from_data(ET.tostring(svg))
    vx,vy,vw,vh=map(float,svg.get('viewBox').split())
    vp=Rsvg.Rectangle();vp.x=vp.y=0;vp.width=vw;vp.height=vh
    skipped=set()
    for node in svg.iter():
        if node.get('c_partid') in {'sheet','table'}:
            skipped.update(id(n) for n in node.iter())
    texts=[]
    for node in svg.iter():
        ident=node.get('id');value=''.join(node.itertext())
        if not node.tag.endswith('text') or not ident or id(node) in skipped or not value.strip():continue
        ok,ink,_=handle.get_geometry_for_layer('#'+ident,vp)
        if ok and ink.width>0:
            texts.append({'id':ident,'text':value,'bbox':[ink.x+vx,-(ink.y+vy+ink.height),ink.x+vx+ink.width,-(ink.y+vy)]})
    d=project.of_type('SCH_PAGE')
    nets={i:d.attributes(i).get('NET',('',{}))[1].get('value') for i,_ in d.items('WIRE')}
    wires=[]
    for ident,v in d.items('LINE'):
        if v.get('lineGroup') not in nets:continue
        a=(v['startX'],v['startY']);b=(v['endX'],v['endY'])
        wires.append({'id':ident,'net':nets[v['lineGroup']],'a':a,'b':b,'bbox':segment_box(a,b)})
    wire_hits=[]
    for text in texts:
        hits=[w['id'] for w in wires if rect_distance(text['bbox'],w['bbox'])<.05]
        if hits:wire_hits.append({'text_id':text['id'],'text':text['text'],'wire_ids':hits})
    text_hits=[];tight_text=[]
    for i,t in enumerate(texts):
        for u in texts[i+1:]:
            a,b=t['bbox'],u['bbox']
            if min(a[2],b[2])-max(a[0],b[0])>.15 and min(a[3],b[3])-max(a[1],b[1])>.15:
                text_hits.append({'ids':[t['id'],u['id']],'text':[t['text'],u['text']]})
            gap=rect_distance(a,b)
            if gap<MIN_TEXT_GAP:
                tight_text.append({'ids':[t['id'],u['id']],'text':[t['text'],u['text']],'gap':round(gap,6)})
    pin_nets,ambiguous=schematic_connections(project)
    if ambiguous:raise ValueError('Ambiguous input nets')
    stem_hits=[];stem_boxes=[]
    for ref,(_,co,attrs) in d.components().items():
        symbol=project.docs['SYMBOL',attrs['Symbol'][1]['value']]
        for num,(_,pin) in symbol_pins(symbol).items():
            a=pin_world(pin,co);dx,dy=rotate(pin.get('length',0),0,pin.get('rotation',0)+co.get('rotation',0))
            if co.get('isMirror'):dx=-dx
            b=(a[0]+dx,a[1]+dy)
            # Trim the connection endpoint so ordinary attached wires are not hits.
            length=math.hypot(dx,dy)
            if length<.2:continue
            stem_boxes.append((ref,num,segment_box(a,b)))
            aa=(a[0]+dx*.1/length,a[1]+dy*.1/length);box=segment_box(aa,b)
            for w in wires:
                if w['net']!=pin_nets.get((ref,num)) and rect_distance(w['bbox'],box)<.01:
                    stem_hits.append({'ref':ref,'pin':num,'wire_id':w['id'],'wire_net':w['net']})
    text_stem_hits=[]
    for text in texts:
        hits=[{'ref':ref,'pin':num} for ref,num,box in stem_boxes if rect_distance(text['bbox'],box)<.05]
        if hits:text_stem_hits.append({'text_id':text['id'],'text':text['text'],'pins':hits})
    cross_hits=[]
    for i,w in enumerate(wires):
        for u in wires[i+1:]:
            if w['net']!=u['net'] and rect_distance(w['bbox'],u['bbox'])<.01:
                cross_hits.append([w['id'],u['id']])
    return {'sheet':sheet,'rendered_text_count':len(texts),'pdf_text_offsets':offsets,'wire_text_overlaps':wire_hits,'text_text_overlaps':text_hits,'text_pairs_below_minimum_gap':tight_text,'text_pin_stem_overlaps':text_stem_hits,'different_net_pin_stem_crossings':stem_hits,'different_net_wire_crossings':cross_hits}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,default=ROOT/'hardware/infrabot_pcb_4p3')
    ap.add_argument('--svg',type=Path,default=ROOT/'docs/schematics/native-svg-R8.zip')
    ap.add_argument('--report',type=Path,default=ROOT/'.build/schematic-text-check.json')
    ap.add_argument('--raw-svg',action='store_true',help='Measure raw native SVG without PDF text offsets')
    args=ap.parse_args();pages=[];hashes={}
    with zipfile.ZipFile(args.svg) as z:
        for name in sorted(z.namelist()):
            if not name.endswith('.svg'):continue
            matches=[p for p in (args.source/'sch/Schematic1').glob('*.esch2') if f'-{p.stem}_' in Path(name).name]
            if len(matches)!=1:raise ValueError('Cannot identify SVG sheet: '+name)
            path=matches[0];sheet=path.stem;hashes[sheet]=hashlib.sha256(path.read_bytes()).hexdigest()
            pages.append(audit_sheet(z.read(name),ProjectFile(path),sheet,args.raw_svg))
    keys=['wire_text_overlaps','text_text_overlaps','text_pairs_below_minimum_gap','text_pin_stem_overlaps','different_net_pin_stem_crossings','different_net_wire_crossings']
    counts={key:sum(len(p[key]) for p in pages) for key in keys}
    result={'schema':'infrabot-schematic-text-review-v1','passed':len(pages)==6 and not any(counts.values()),'scope':'Rendered text ink bounds against external wires, pin strokes and other text; different-net pin-stem/wire crossings. Other component artwork, no-connect marks, electrical behavior and physical PCB are outside this geometry check.','source_sha256':hashes,'svg_sha256':hashlib.sha256(args.svg.read_bytes()).hexdigest(),'counts':counts,'sheets':pages}
    result['minimum_text_gap_native_units']=MIN_TEXT_GAP
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'passed':result['passed'],'counts':counts,'report':str(args.report)},indent=2))
    raise SystemExit(0 if result['passed'] else 1)
if __name__=='__main__':main()
