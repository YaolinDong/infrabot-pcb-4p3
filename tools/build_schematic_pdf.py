#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YaolinDong
"""Build ordinary engineering drawing sheets from native R8 SVG exports.

Optional documentation tool: reportlab, pypdf and system Python with
PyGObject/Rsvg/Cairo. Ordinary tools/verify.py needs none of these dependencies.
Only native page frames, their title tables and the editor grid are omitted;
functional circuit layout comes from the editable schematic source. Reviewed
symbol-text offsets compensate for font baseline differences in the PDF.
"""
from pathlib import Path
import argparse,io,json,subprocess,tempfile,zipfile
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape,A3
from reportlab.lib.colors import HexColor
from pypdf import PdfReader,PdfWriter
ROOT=Path(__file__).resolve().parents[1]
SHEETS=[('Core_BTB','Core-module interface','BTB connectors, assigned MCU pins and supporting circuits.'),('Power','Power supply','DC input, 5 V conversion, power switching and 3.3 V regulation.'),('Ethernet','Ethernet and clocks','RMII, PHY, clock distribution and the RJ45 interface.'),('UART_CAN_SWD','Communication and debug','USB-UART, CAN and SWD interfaces.'),('LCD','Display integration','Direct FPC connection to the core module; no baseboard RGB branch.'),('Panel','Buttons and status','STOP / RESUME inputs, filtering and RGB status drive.')]
PAGE_W,PAGE_H=landscape(A3)
# Render native SVG graphics with embedded fonts. The SVG's paper/title groups
# are identifiable c_partid nodes; removing them never touches circuit groups.
RSVG_RENDER=r'''
import sys,json,xml.etree.ElementTree as ET
from pathlib import Path
import gi,cairo
gi.require_version('Rsvg','2.0')
from gi.repository import Rsvg
src,dest=map(Path,sys.argv[1:3]);W,H=map(float,sys.argv[3:5])
sys.path.insert(0,sys.argv[5])
from schematic_svg import prepare_svg
root=ET.fromstring(src.read_bytes())
offset_count=prepare_svg(root,sys.argv[6])
shape=next(c for c in root if c.attrib.get('class')=='shapeBox');shape.set('id','circuit-content')
for child in list(root):
    if child.attrib.get('id') in {'gridBg','fillBg'}:root.remove(child)
removed=[]
for child in list(shape):
    if child.attrib.get('c_partid') in {'sheet','table'}:
        removed.append(child.attrib.get('c_partid'));shape.remove(child)
labels=[''.join(t.itertext()) for t in shape.iter() if t.tag.endswith('text')]
h=Rsvg.Handle.new_from_data(ET.tostring(root));ok,ink,logical=h.get_geometry_for_element('#circuit-content')
if not ok or ink.width<=0 or ink.height<=0:raise RuntimeError('Empty schematic content')
surface=cairo.PDFSurface(str(dest),W,H)
surface.set_metadata(cairo.PDF_METADATA_CREATE_DATE,'2026-11-16T00:00:00+08:00')
ctx=cairo.Context(surface);ctx.set_source_rgb(1,1,1);ctx.paint()
# A3 drawing area with space for the bottom-right engineering title block.
scale=min((W-52)/ink.width,(H-118)/ink.height,1.25)
rect=Rsvg.Rectangle();rect.x=26;rect.y=26;rect.width=ink.width*scale;rect.height=ink.height*scale
if not h.render_element(ctx,'#circuit-content',rect):raise RuntimeError('SVG render failed')
surface.finish()
print(json.dumps({'svg':src.name,'circuit_labels':labels,'removed_non_circuit_groups':removed,'pdf_text_offsets':offset_count,'native_ink_size':[ink.width,ink.height],'page_size_pt':[W,H]}))
'''

def stamp(title,sheet):
    b=io.BytesIO();c=canvas.Canvas(b,pagesize=(PAGE_W,PAGE_H),invariant=1)
    c.setStrokeColorRGB(0,0,0);c.setFillColorRGB(0,0,0);c.setLineWidth(.5)
    c.rect(14,14,PAGE_W-28,PAGE_H-28,stroke=1,fill=0)
    x=PAGE_W-475;y=14;w=461;h=64
    c.rect(x,y,w,h,stroke=1,fill=0)
    for dy in [18,40]:c.line(x,y+dy,x+w,y+dy)
    c.line(x+310,y,x+310,y+40);c.line(x+390,y,x+390,y+40)
    c.setFont('Helvetica-Bold',10);c.drawString(x+8,y+48,'InfraBot 4.3 - '+title)
    c.setFont('Helvetica',8);c.drawString(x+8,y+27,'Drawn: YaolinDong')
    c.drawString(x+158,y+27,'Date: 2026-11-16');c.drawString(x+318,y+27,'Rev: R8')
    c.drawString(x+398,y+27,'Size: A3')
    c.drawString(x+8,y+6,'File: '+SHEETS[sheet-1][0]+'.esch2')
    c.drawString(x+318,y+6,f'Sheet: {sheet}/6')
    c.drawString(x+398,y+6,'Scale: NTS')
    c.save();b.seek(0);return PdfReader(b).pages[0]

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,default=ROOT/'docs/schematics/infrabot-pcb-4p3-R8-schematic.pdf');ap.add_argument('--svg-python',default='/usr/bin/python3');ap.add_argument('--report',type=Path);a=ap.parse_args()
    src=ROOT/'docs/schematics/native-svg-R8.zip';writer=PdfWriter();report=[]
    with tempfile.TemporaryDirectory(prefix='infrabot-schematic-pdf-') as tmp:
        tmp=Path(tmp);render=tmp/'render.py';render.write_text(RSVG_RENDER)
        with zipfile.ZipFile(src) as archive:
            for i,(key,title,_) in enumerate(SHEETS,1):
                matches=[n for n in archive.namelist() if f'_{i}-{key}_' in n and n.endswith('.svg')]
                if len(matches)!=1:raise ValueError('Missing or duplicate native SVG sheet: '+key)
                svg=tmp/f'{i}-{key}.svg';svg.write_bytes(archive.read(matches[0]));pdf=tmp/f'{i}.pdf'
                result=subprocess.run([a.svg_python,'-B',str(render),str(svg),str(pdf),str(PAGE_W),str(PAGE_H),str(ROOT/'tools'),key],check=True,capture_output=True,text=True)
                record=json.loads(result.stdout);record['source_zip_member']=matches[0];record['sheet']=key;report.append(record)
                page=PdfReader(pdf).pages[0];page.merge_page(stamp(title,i));writer.add_page(page)
    for i,(key,title,_) in enumerate(SHEETS):
        writer.add_outline_item(f'{i+1}. {title}',i)
    writer.add_metadata({'/Title':'InfraBot 4.3 - R8 Schematics','/Author':'YaolinDong','/Subject':'Electrical schematics','/Creator':'EasyEDA / Cairo','/Keywords':'InfraBot, R8, STM32H743, schematic, open hardware'})
    writer.page_mode='/UseOutlines';a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('wb') as f:writer.write(f)
    if a.report:a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'pdf':str(a.output),'pages':len(writer.pages),'bytes':a.output.stat().st_size,'native_sheet_order':[s[0] for s in SHEETS]},indent=2))
if __name__=='__main__':main()
