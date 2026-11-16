#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YaolinDong
"""Offline R8 file integrity, pin connectivity and assembly-coordinate checks.

Uses Python's standard library only. Does not edit files or claim to run native
EDA geometric DRC, supplier DFM, or hardware tests.
"""
from pathlib import Path
import collections,csv,hashlib,json,math,sys,zipfile
from check_connectivity import check as check_connectivity
from native_project import ProjectFile
ROOT=Path(__file__).resolve().parents[1]
PROJECT='hardware/infrabot_pcb_4p3'


def verify_manifest(root,manifest):
    root=Path(root).resolve();errors=[];seen=set()
    if manifest.get('schema')!='infrabot-public-release-v1':errors.append('Unsupported manifest schema')
    for item in manifest.get('files',[]):
        rel=item['path'];p=(root/rel).resolve()
        if Path(rel).is_absolute() or not p.is_relative_to(root):
            errors.append('Path escapes repository: '+rel);continue
        if rel in seen:errors.append('Duplicate manifest path: '+rel)
        seen.add(rel)
        if not p.is_file():errors.append('Missing file: '+rel);continue
        data=p.read_bytes()
        if len(data)!=item['bytes'] or hashlib.sha256(data).hexdigest()!=item['sha256']:errors.append('Changed file: '+rel)
    if not seen:errors.append('Empty manifest')
    return errors


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def check_assembly(project,bom_path,cpl_path):
    b=ProjectFile(Path(project)/'pcb/PCB1.epcb2').of_type('PCB');parts=b.components()
    bom=read_csv(bom_path);cpl=read_csv(cpl_path);errors=[];bom_refs=[]
    for row in bom:
        refs=[s.strip() for s in row['Designator'].split(',') if s.strip()];bom_refs.extend(refs)
        if int(row['Quantity'])!=len(refs):errors.append('BOM quantity mismatch: '+row['Designator'])
        if not row['Manufacturer Part'].strip():errors.append('Missing MPN: '+row['Designator'])
    cpl_refs=[r['Designator'] for r in cpl]
    for label,values in [('BOM',bom_refs),('CPL',cpl_refs)]:
        if len(values)!=len(set(values)):errors.append(label+' has duplicate designators')
        if set(values)!=set(parts):errors.append(label+' designators differ from native PCB')
    for row in cpl:
        ref=row['Designator']
        if ref not in parts:continue
        _,co,_=parts[ref]
        xy=[float(row[k].removesuffix('mm')) for k in ['Mid X','Mid Y']]
        if any(abs(a-b)>.001 for a,b in zip(xy,[co['x']*.0254,co['y']*.0254])):errors.append('CPL position mismatch: '+ref)
        angle=(float(row['Rotation'])-co['angle']+180)%360-180
        if abs(angle)>.00001:errors.append('CPL rotation mismatch: '+ref)
        if row['Layer']!='T' or co['layerId']!=1:errors.append('Assembly side is not TOP: '+ref)
    return {'passed':not errors,'errors':errors,'native_components':len(parts),'bom_components':len(bom_refs),'cpl_components':len(cpl_refs)}


def verify(root=ROOT):
    root=Path(root);manifest=json.loads((root/'manufacturing/R8/manifest.json').read_text());errors=verify_manifest(root,manifest)
    connectivity=check_connectivity(root/PROJECT,root/'verification/expected-netlist.json')
    assembly=check_assembly(root/PROJECT,root/'manufacturing/R8/BOM.csv',root/'manufacturing/R8/CPL.csv')
    if not connectivity['passed']:errors.append('Schematic/PCB pin-net comparison failed')
    errors.extend(assembly['errors'])
    gerber=root/'manufacturing/R8/Gerber.zip'
    required={'Gerber_TopLayer.GTL','Gerber_InnerLayer1.G1','Gerber_InnerLayer2.G2','Gerber_BottomLayer.GBL','Gerber_BoardOutlineLayer.GKO','Gerber_TopSolderMaskLayer.GTS','Gerber_BottomSolderMaskLayer.GBS','Gerber_TopSilkscreenLayer.GTO','Gerber_BottomSilkscreenLayer.GBO','Gerber_TopPasteMaskLayer.GTP','Drill_PTH_Through.DRL','Drill_NPTH_Through.DRL'}
    with zipfile.ZipFile(gerber) as z:
        if z.testzip():errors.append('Gerber ZIP CRC error')
        names={Path(n).name for n in z.namelist()}
        if not required<=names:errors.append('Gerber ZIP is missing required manufacturing layers')
        if any(Path(n).is_absolute() or '..' in Path(n).parts or '\\' in n for n in z.namelist()):errors.append('Unsafe Gerber archive path')
    return {'passed':not errors,'errors':errors,'design_revision':'R8','manifest_files':len(manifest['files']),'components':assembly['native_components'],'assigned_pin_connections':connectivity['schematic_found_connections'],'component_pads':connectivity['pcb_component_pad_count'],'assembly':assembly,'native_drc_rerun':False,'physical_validation':'NOT_PERFORMED','scope':'Offline hashes, declared layer presence, schematic/PCB pin nets and BOM/CPL coordinates. See verification/README.md for inherited native DRC evidence.'}

if __name__=='__main__':
    try:
        result=verify();print(json.dumps(result,ensure_ascii=False,indent=2));sys.exit(0 if result['passed'] else 1)
    except (OSError,ValueError,KeyError,zipfile.BadZipFile) as exc:
        print(json.dumps({'passed':False,'error':str(exc)},ensure_ascii=False));sys.exit(1)
