# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YaolinDong
"""Independent checks of saved schematic connectivity and PCB pin/net mapping."""
from collections import defaultdict
from pathlib import Path
import argparse
import json
import math
from native_project import ProjectFile, symbol_pins, pin_world, all_pcb_pads


def schematic_connections(project):
    doc=project.of_type('SCH_PAGE')
    parent={}
    point=lambda x,y:(round(x,5),round(y,5))
    def find(k):
        parent.setdefault(k,k)
        if parent[k]!=k:parent[k]=find(parent[k])
        return parent[k]
    def join(a,b):parent[find(a)]=find(b)
    wire_points=defaultdict(list)
    for _,b in doc.items('LINE'):
        if not b.get('lineGroup'):continue
        a=point(b['startX'],b['startY']);z=point(b['endX'],b['endY'])
        join(a,z)
        wire_points[b['lineGroup']]+=[a,z]
    names=defaultdict(set)
    for _,b in doc.items('ATTR'):
        if b.get('key')=='NET' and b.get('value'):
            for pt in wire_points.get(b.get('parentId'),[]):names[find(pt)].add(b['value'])
    for cid,component in doc.items('COMPONENT'):
        attrs=doc.attributes(cid)
        if 'Global Net Name' in attrs:
            net=attrs['Global Net Name'][1].get('value')
            if net:names[find(point(component['x'],component['y']))].add(net)
    result={};ambiguous=[]
    for ref,(cid,component,attrs) in doc.components().items():
        symbol=project.docs[('SYMBOL',attrs['Symbol'][1]['value'])]
        for num,(_,pin) in symbol_pins(symbol).items():
            pt=point(*pin_world(pin,component))
            nets=names.get(find(pt),set())
            if len(nets)>1:ambiguous.append((ref,num,sorted(nets)))
            if nets:result[(ref,num)]=sorted(nets)[0]
    return result,ambiguous


def compare(expected,actual):
    return {'missing':[(r,p,n) for (r,p),n in expected.items() if (r,p) not in actual],
            'wrong':[(r,p,n,actual[(r,p)]) for (r,p),n in expected.items() if (r,p) in actual and actual[(r,p)]!=n],
            'unexpected':[(r,p,n) for (r,p),n in actual.items() if n and (r,p) not in expected]}


def check(root, expected_path=None):
    root=Path(root)
    expected_path = Path(expected_path) if expected_path else Path(__file__).resolve().parents[1]/'verification/expected-netlist.json'
    expected=json.loads(expected_path.read_text())
    wanted={(c['ref'],p):n for parts in expected.values() for c in parts for p,n in c['pins'].items()}
    actual={};ambiguous=[]
    for path in sorted((root/'sch/Schematic1').glob('*.esch2')):
        got,bad=schematic_connections(ProjectFile(path));actual.update(got);ambiguous+=bad
    sch=compare(wanted,actual);sch['ambiguous']=ambiguous
    pcbfile=ProjectFile(root/'pcb/PCB1.epcb2');pcb=pcbfile.of_type('PCB')
    allpads=all_pcb_pads(pcbfile)
    actualpcb={(p['ref'],p['num']):p['net'] for p in allpads if p['ref']}
    wantedpcb={(c['ref'],p):n for parts in expected.values() for c in parts if c['pcb'] for p,n in c['pins'].items()}
    pcm=compare(wantedpcb,actualpcb)
    j7=[p for p in allpads if p['ref']=='J7']
    errors=[]
    refs=set(pcb.components())
    desiredrefs={c['ref'] for parts in expected.values() for c in parts if c['pcb']}
    if refs!=desiredrefs:errors.append('component set differs: '+str((sorted(refs-desiredrefs),sorted(desiredrefs-refs))))
    report={'schematic_expected_connections':len(wanted),'schematic_found_connections':len(actual),
            'schematic':sch,'pcb_expected_connections':len(wantedpcb),'pcb_component_pad_count':len(actualpcb),
            'pcb':pcm,'component_count':len(refs),'j7_pads':len(j7),'structural_errors':errors,
            'limitations':['Checks net names and pin mapping; not a substitute for geometric DRC, ERC, or electrical simulation.']}
    report['passed']=not any(sch.values()) and not any(pcm.values()) and not errors
    return report


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('project',nargs='?',default=str(Path(__file__).resolve().parents[1]/'hardware/infrabot_pcb_4p3'));ap.add_argument('--output');args=ap.parse_args()
    report=check(args.project)
    text=json.dumps(report,ensure_ascii=False,indent=2)
    if args.output:Path(args.output).write_text(text+'\n')
    print(text)
    raise SystemExit(0 if report['passed'] else 1)
