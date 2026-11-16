#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YaolinDong
"""Arrange the existing R8 schematic by circuit function without changing nets.

Run only when intentionally updating the editable drawings. Component identity,
MPN/footprint properties and embedded libraries are preserved. The resulting
pin/net graph is checked in memory before any source file is written.
"""
from pathlib import Path
from copy import deepcopy
from collections import defaultdict
import argparse,hashlib,heapq,json,math,time
from native_project import ProjectFile,symbol_pins,pin_world,rotate
from check_connectivity import schematic_connections
from schematic_adjustments import apply_adjustments
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'hardware/infrabot_pcb_4p3/sch/Schematic1'
STEP=5

# x, y, rotation, optional mirror. Schematic coordinates are 10 mil units.
LAYOUT={
'Core_BTB':[
 ('CORE CONNECTORS',(45,180,820,770),{'CN1':(240,420,0),'CN2':(620,420,0)},False),
 ('BOOT MODE',(860,540,1130,770),{'R1':(970,640,270)},True),
 ('RESET',(860,180,1130,510),{'SW2':(980,350,0)},True)],
'Power':[
 ('DC INPUT / PROTECTION (6-12 V)',(45,555,420,770),{'J1':(110,665,0),'D1':(220,675,180),'D2':(300,630,270),'C1':(375,630,270)},True),
 ('5 V BUCK REGULATOR',(445,360,1135,770),{'U1':(585,610,0),'C2':(485,680,270),'C3':(485,535,270),'C4':(700,675,90),'L1':(815,675,0),'C5':(955,620,270),'C6':(1055,620,270),'R4':(815,525,270),'R5':(815,430,270),'C8':(940,525,270)},True),
 ('DC / USB POWER SELECTION',(45,355,420,535),{'D4':(150,465,180),'D5':(150,405,180),'C7':(320,430,270)},True),
 ('3.3 V REGULATOR',(45,185,430,335),{'U2':(230,255,0),'C9':(100,250,270),'C10':(340,250,270),'C11':(385,250,270)},True),
 ('POWER INDICATOR',(45,45,420,165),{'R6':(145,105,0),'LED1':(285,105,0)},True),
 ('MAIN POWER SWITCH',(445,45,1135,340),{'Q1':(600,170,270),'R2':(535,260,0),'R3':(720,260,0),'SW1':(975,225,0),'C26':(770,160,270)},True)],
'Ethernet':[
 ('LAN8720A / MDI TERMINATION',(45,425,690,770),{'U3':(245,595,0),'R7':(370,700,0),'R10':(430,675,90),'R11':(500,665,90),'R8':(570,655,90),'R9':(640,645,90),'R12':(120,485,270)},True),
 ('RJ45 / LINK LED / SHIELD',(715,425,1160,770),{'J2':(955,595,0),'R13':(770,700,270),'R14':(770,500,270),'R15':(840,485,0),'R16':(1045,475,0),'FB2':(1090,600,270)},True),
 ('PHY SUPPLY FILTERING',(45,235,690,400),{'FB1':(110,335,0),'C14':(220,315,270),'C15':(300,315,270),'C16':(380,315,270),'C20':(460,315,270),'C17':(550,315,270),'C18':(590,295,270),'C19':(650,295,270)},True),
 ('RESET SUPERVISOR',(715,235,1135,400),{'U7':(945,310,0),'R25':(795,310,270),'C27':(1080,310,270)},True),
 ('50 MHz CLOCK DISTRIBUTION',(45,15,690,210),{'Y1':(165,135,0),'U6':(395,135,0),'R23':(555,105,0),'R24':(555,165,0),'C12':(65,75,270),'C13':(285,75,270)},True),
 ('REFERENCE / BYPASS CAPACITORS',(715,45,1135,210),{'C31':(765,130,270),'C32':(845,130,270),'C35':(925,130,270),'C36':(1005,130,270),'C37':(1085,130,270)},True)],
'UART_CAN_SWD':[
 ('USB-C / CC TERMINATION',(45,470,425,770),{'J3':(165,625,0,True),'R17':(285,665,270),'R18':(365,560,270)},True),
 ('USB TO UART',(450,470,1135,770),{'U4':(735,620,0),'R19':(555,685,180),'R20':(555,555,0),'C21':(620,530,270),'C22':(925,650,270),'C23':(1045,650,270)},True),
 ('CAN TRANSCEIVER / PROTECTION / TERMINATION',(45,185,1135,445),{'U5':(260,315,0),'C24':(100,340,270),'C25':(410,255,270),'D3':(575,310,0),'R21':(780,350,270),'J4':(780,245,90),'J5':(1045,310,0)},True),
 ('SWD',(45,45,370,165),{'J6':(160,100,0,True)},False),
 ('SUPPLY / REFERENCE CAPACITORS',(395,45,1135,185),{'C33':(480,110,270),'C34':(650,110,270),'C38':(820,110,270),'C39':(990,110,270)},True)],
'Panel':[
 ('STOP / KEY1',(45,450,565,770),{'SW3':(135,610,0),'R26':(285,590,0),'R27':(390,550,270),'C28':(490,550,270)},True),
 ('RESUME / KEY2',(590,450,1135,770),{'SW4':(680,610,0),'R28':(830,590,0),'R29':(935,550,270),'C29':(1040,550,270)},True),
 ('STATUS INPUT PULL-UPS',(45,285,580,425),{'R33':(135,350,270),'R34':(285,350,270),'R35':(435,350,270)},True),
 ('RGB STATUS LED / OPEN-DRAIN DRIVER',(45,45,1135,280),{'U8':(300,170,0),'C30':(500,170,270),'R30':(700,230,180),'R31':(700,170,180),'R32':(700,110,180),'LED2':(930,170,0,True)},True)],
'LCD':[]}

def uid(s):return hashlib.sha256(('infrabot-sch-readability:'+s).encode()).hexdigest()[:16]
def snap(v):return round(v/STEP)*STEP

def write_changes(p):
    lines=[];ticket=p.max_ticket;now=int(time.time()*1000)
    for dk,doc in p.docs.items():
        old=p.baseline[dk];changed=[(k,v) for k,v in doc.records.items() if old.records.get(k)!=v];deleted=[k for k in old.records if k not in doc.records]
        if not changed and not deleted:continue
        ticket+=1;head={**doc.head,'updateTime':now,'version':str(now),'client':'schematic-layout'}
        lines.append(ProjectFile.encode({'type':'DOCHEAD','ticket':ticket},head))
        for (kind,ident),value in changed+[(k,None) for k in deleted]:
            ticket+=1;lines.append(ProjectFile.encode({'type':kind,'id':ident,'ticket':ticket},value))
    if lines:p.path.write_text(p.original.rstrip('\n')+'\n'+'\n'.join(lines)+'\n')
    return len(lines)

# The reader is deliberately read-only. This explicit writer is confined to
# this opt-in layout tool and uses the same native per-field log encoding.
def encode(head,body):
    dump=lambda x:json.dumps(x,ensure_ascii=False,separators=(',',':'))
    return dump(head)+'||'+(dump(body) if body is not None else '')+'|'
ProjectFile.encode=staticmethod(encode)

class Page:
    def __init__(self,path,nets):
        self.p=ProjectFile(path);self.d=self.p.of_type('SCH_PAGE');self.name=path.stem;self.parts=self.d.components();self.nets=nets;self.seq=0;self.pin_data={};self.bodies={};self.labels=[];self.routes=[]
        actual,ambiguous=schematic_connections(self.p)
        wanted={(ref,num):net for ref in self.parts for num,net in nets[ref].items()}
        if actual!=wanted or ambiguous:raise ValueError('Input schematic differs from the expected circuit; stop instead of overwriting electrical changes')
        self.ground=None
        removed=set()
        for cid,co in list(self.d.items('COMPONENT')):
            a=self.d.attributes(cid)
            if 'Global Net Name' in a:
                if a['Global Net Name'][1]['value']=='GND' and self.ground is None:self.ground=(deepcopy(co),deepcopy(a))
                removed.add(cid);del self.d.records['COMPONENT',cid]
            elif 'Designator' not in a:
                for k,(_,v) in a.items():
                    if k in {'Width','Height','Company','Drawed','Version'}:v['value']={'Width':'1170','Height':'825','Company':'YaolinDong','Drawed':'YaolinDong','Version':'R8'}[k]
        wire_ids={i for i,_ in self.d.items('WIRE')}
        for key,v in list(self.d.records.items()):
            kind,ident=key
            if kind in {'WIRE','LINE','TEXT','JUNCTION','RECT'} or (kind=='ATTR' and v.get('parentId') in removed|wire_ids):del self.d.records[key]
    def ident(self,what):self.seq+=1;return uid(f'{self.name}:{self.seq}:{what}')
    def text(self,x,y,value,size=11,bold=False):
        self.d.records['TEXT',self.ident('text')]={'x':x,'y':y,'rotation':0,'color':'#000000','fillColor':'#000000','fontFamily':'Arial','fontSize':size,'fontWeight':bold,'italic':False,'underline':False,'align':'LEFT_BOTTOM','value':value,'zIndex':1000,'yAxisDirection':'up'}
    def line(self,a,b,group=None):
        if a==b:return
        v={'startX':a[0],'startY':a[1],'endX':b[0],'endY':b[1],'strokeColor':None if group else '#707070','strokeWidth':None if group else .3,'strokeStyle':None,'fillColor':None,'fillStyle':None,'yAxisDirection':'up'}
        if group:v['lineGroup']=group
        self.d.records['LINE',self.ident('line')]=v
    def box(self,rect,title):
        x0,y0,x1,y1=rect
        self.d.records['RECT',uid(self.name+':box:'+title)]={'dotX1':x0,'dotY1':y0,'dotX2':x1,'dotY2':y1,'radiusX':0,'radiusY':0,'rotation':0,'strokeColor':'#707070','strokeWidth':.3,'strokeStyle':0,'fillColor':None,'fillStyle':0,'zIndex':0,'yAxisDirection':'up'}
        self.text(x0+10,y1-20,title,12,True)
    def place(self,ref,spec):
        cid,co,attrs=self.parts[ref];old=deepcopy(co);x,y,angle=spec[:3];mirror=bool(spec[3]) if len(spec)>3 else False
        # Preserve pin overrides such as NO_CONNECT while moving their graphics.
        def inverse(px,py):
            px-=old['x'];py-=old['y']
            if old.get('isMirror'):px=-px
            return rotate(px,py,-old.get('rotation',0))
        for _,a in self.d.items('ATTR'):
            parent=a.get('parentId','')
            if (parent==cid or parent.startswith(cid+'-')) and a.get('x') is not None and a.get('y') is not None:
                lx,ly=inverse(a['x'],a['y']);nx,ny=rotate(lx,ly,angle)
                a['x']=(-nx if mirror else nx)+x;a['y']=ny+y
        co.update(x=x,y=y,rotation=angle,isMirror=mirror)
        symbol=self.p.docs['SYMBOL',attrs['Symbol'][1]['value']];rawpart=symbol.records.get(('PART',co['partId'])) or next(v for _,v in symbol.items('PART'));box=rawpart['BBOX']
        corners=[]
        for px,py in [(box[0],box[1]),(box[0],box[3]),(box[2],box[1]),(box[2],box[3])]:
            nx,ny=rotate(px,py,angle);corners.append(((-nx if mirror else nx)+x,ny+y))
        bb=[min(p[0] for p in corners),min(p[1] for p in corners),max(p[0] for p in corners),max(p[1] for p in corners)];self.bodies[ref]=bb
        passive=ref.startswith(('R','C','L','FB')) and not ref.startswith('CN')
        vertical=(passive or ref.startswith('D')) and angle%180==90
        for k in ['Designator','Name']:
            if k not in attrs:continue
            a=attrs[k][1];a.update(rotation=0,fontFamily='Arial',fontSize=8,color='#000080',fillColor='#000080',keyVisible=False,valueVisible=True)
            if vertical:a.update(x=bb[2]+9,y=y+(7 if k=='Designator' else -8),align='LEFT_MIDDLE')
            elif passive:a.update(x=x,y=bb[3]+10 if k=='Designator' else bb[1]-15,align='CENTER_BOTTOM')
            else:a.update(x=x,y=bb[3]+25 if k=='Designator' else bb[3]+11,align='CENTER_BOTTOM')
            if ref=='Q1':a.update(x=bb[2]+18,y=y+(10 if k=='Designator' else -30),align='LEFT_MIDDLE')
            if ref=='D3':a.update(x=bb[2]+15,y=bb[3]+(0 if k=='Designator' else -14),align='LEFT_BOTTOM')
            value=str(a.get('value',''))
            if value.startswith('={'):
                key=value[2:-1];value=str(attrs.get(key,('',{}))[1].get('value',value))
            width=max(12,len(value)*4.1);height=9
            lx=a['x']-width/2 if a['align'].startswith('CENTER') else a['x'];self.labels.append([lx-2,a['y']-3,lx+width+2,a['y']+height])
        for num,(pid,pin) in symbol_pins(symbol).items():
            px,py=pin_world(pin,co);r=(pin.get('rotation',0)+angle)%360;dx,dy=rotate(-1,0,r)
            if mirror:dx=-dx
            dx=round(dx);dy=round(dy);anchor=(snap(px+dx*20),snap(py+dy*20))
            self.pin_data[ref,num]={'ref':ref,'num':num,'point':(snap(px),snap(py)),'anchor':anchor,'direction':(dx,dy),'net':self.nets[ref].get(num)}
    def ground_symbol(self,point):
        if self.ground is None:return
        template,attrs=self.ground;old=deepcopy(template);cid=self.ident('ground');ox,oy=old['x'],old['y'];old['x'],old['y']=point;old['rotation']=0;old['isMirror']=False;self.d.records['COMPONENT',cid]=old
        for key,(_,a) in attrs.items():
            a=deepcopy(a);a['parentId']=cid
            if a.get('x') is not None:a['x']=point[0]
            if a.get('y') is not None:a['y']=point[1]-(30 if key=='Symbol' else 25)
            self.d.records['ATTR',self.ident('ground-attr')]=a
    def net(self,net,segments,point,align='LEFT_BOTTOM',visible=True):
        gid=self.ident(net);self.d.records['WIRE',gid]={'zIndex':500}
        # Split at every endpoint, so tee junctions are explicit in the saved graph.
        endpoints={p for seg in segments for p in seg}
        for a,b in segments:
            if a==b:continue
            on=[p for p in endpoints if (a[0]==b[0]==p[0] and min(a[1],b[1])<=p[1]<=max(a[1],b[1])) or (a[1]==b[1]==p[1] and min(a[0],b[0])<=p[0]<=max(a[0],b[0]))]
            on.sort(key=lambda p:abs(p[0]-a[0])+abs(p[1]-a[1]))
            for u,v in zip(on,on[1:]):self.line(u,v,gid)
        self.d.records['ATTR',self.ident('net-label')]={'parentId':gid,'key':'NET','value':net,'x':point[0],'y':point[1],'rotation':0,'fontFamily':'Arial','fontSize':8,'color':'#000080','fillColor':'#000080','align':align,'keyVisible':False,'valueVisible':visible,'zIndex':501,'yAxisDirection':'up'}

class Router:
    def __init__(self,page,rect,refs):
        self.page=page;self.rect=rect;self.refs=refs;self.occupied=defaultdict(set);self.pin_nodes={};self.bounds=[(snap(rect[0]+10),snap(rect[1]+15)),(snap(rect[2]-10),snap(rect[3]-25))]
        self.obstacles=[]
        for r in refs:
            x0,y0,x1,y1=page.bodies[r];self.obstacles.append((x0-5,y0-5,x1+5,y1+5))
        self.obstacles+=page.labels
        for (ref,num),p in page.pin_data.items():
            if ref not in refs:continue
            self.pin_nodes[p['point']]=p['net'] or '__NC__'
            if p['net']:
                self.mark(p['point'],p['anchor'],p['net'])
    def points(self,a,b):
        dx=0 if a[0]==b[0] else (STEP if b[0]>a[0] else -STEP);dy=0 if a[1]==b[1] else (STEP if b[1]>a[1] else -STEP)
        p=a;yield p
        while p!=b:p=(p[0]+dx,p[1]+dy);yield p
    def mark(self,a,b,net):
        for p in self.points(a,b):self.occupied[p].add(net)
    def blocked(self,p,net,ends):
        if p in ends:return False
        (x0,y0),(x1,y1)=self.bounds
        if not (x0<=p[0]<=x1 and y0<=p[1]<=y1):return True
        if self.pin_nodes.get(p,net)!=net:return True
        if any(n!=net for n in self.occupied.get(p,())):return True
        return any(a<=p[0]<=c and b<=p[1]<=d for a,b,c,d in self.obstacles)
    def route(self,a,b,net):
        if a==b:return [a]
        ends={a,b};q=[];counter=0;start=(a,-1);cost={start:0};parent={};heur=lambda p:abs(p[0]-b[0])+abs(p[1]-b[1]);heapq.heappush(q,(heur(a),counter,start));limit=0
        directions=[(STEP,0),(-STEP,0),(0,STEP),(0,-STEP)]
        while q:
            _,_,state=heapq.heappop(q);point,last=state;limit+=1
            if point==b:
                path=[point]
                while state in parent:state=parent[state];path.append(state[0])
                path.reverse();return path
            if limit>80000:break
            for di,(dx,dy) in enumerate(directions):
                nxt=(point[0]+dx,point[1]+dy)
                if self.blocked(nxt,net,ends):continue
                nstate=(nxt,di);nc=cost[state]+STEP+(12 if last>=0 and last!=di else 0)
                if nc>=cost.get(nstate,float('inf')):continue
                cost[nstate]=nc;parent[nstate]=state;counter+=1;heapq.heappush(q,(nc+heur(nxt),counter,nstate))
        diagnostic={str(p):{str((p[0]+dx,p[1]+dy)):{'blocked':self.blocked((p[0]+dx,p[1]+dy),net,ends),'wire':sorted(self.occupied.get((p[0]+dx,p[1]+dy),[])),'obstacles':[r for r in self.obstacles if r[0]<=p[0]+dx<=r[2] and r[1]<=p[1]+dy<=r[3]]} for dx,dy in directions} for p in [a,b]}
        raise RuntimeError(f'No schematic path: {self.page.name} {net} {a}->{b} examined={limit} {diagnostic}')
    def simplify(self,path):
        if len(path)<3:return path
        keep=[path[0]]
        for a,b,c in zip(path,path[1:],path[2:]):
            if (b[0]-a[0],b[1]-a[1])!=(c[0]-b[0],c[1]-b[1]):keep.append(b)
        return keep+[path[-1]]

def apply_page(page,blocks,net_blocks):
    allrefs={r for _,_,parts,_ in blocks for r in parts}
    if allrefs!=set(page.parts):raise ValueError(f'Layout part set mismatch: {page.name}: {allrefs^set(page.parts)}')
    for title,rect,parts,connect in blocks:
        for ref,spec in parts.items():page.place(ref,spec)
    for block_index,(title,rect,parts,connect) in enumerate(blocks):
        page.box(rect,title);router=Router(page,rect,set(parts));groups=defaultdict(list)
        for (ref,num),p in page.pin_data.items():
            if ref in parts and p['net']:groups[p['net']].append(p)
        for net,pins in sorted(groups.items(),key=lambda pair:(pair[0] in ['GND','+3V3','+5V','VIN','VBUS_USB','5V_BUCK','5V_SYS'],len(pair[1]),pair[0])):
            symbolic=[p for p in pins if (page.name=='Ethernet' and p['ref'] in {'U3','U6','Y1','C12','C13'} and net in {'+3V3','ETH_VDDA','ETH_VDDCR'}) or (p['ref']=='J3' and net in {'VBUS_USB','USB_DP','USB_DM'}) or (p['ref']=='U8' and net=='+3V3')]
            for p in symbolic:
                a=p['anchor'];dx,dy=p['direction']
                page.net(net,[(p['point'],a)],(a[0]+dx*3,a[1]+3),'RIGHT_BOTTOM' if dx<0 else 'LEFT_BOTTOM',True)
            pins=[p for p in pins if p not in symbolic]
            if not pins:continue
            if net=='GND':
                # Individual ground symbols are standard schematic connections;
                # do not route a page-wide ground loop around IC pin banks.
                for p in pins:
                    a=p['anchor'];dx,dy=p['direction']
                    use_flag=dy<0 and page.ground is not None
                    if use_flag:page.ground_symbol(a)
                    page.net(net,[(p['point'],a)],(a[0]+dx*3,a[1]+3),'RIGHT_BOTTOM' if dx<0 else 'LEFT_BOTTOM',not use_flag)
                continue
            if not connect:
                for p in pins:
                    a=p['anchor'];dx,dy=p['direction'];label=(a[0]+dx*3,a[1]+2 if dy==0 else a[1]+dy*3);align='RIGHT_BOTTOM' if dx<0 else 'LEFT_BOTTOM'
                    page.net(net,[(p['point'],a)],label,align,True)
                continue
            segments=[(p['point'],p['anchor']) for p in pins];connected=[pins[0]['anchor']];pending=[p['anchor'] for p in pins[1:]]
            while pending:
                _,a,b=min((abs(a[0]-b[0])+abs(a[1]-b[1]),a,b) for a in connected for b in pending)
                path=router.simplify(router.route(a,b,net))
                for u,v in zip(path,path[1:]):segments.append((u,v));router.mark(u,v,net)
                connected+=path;pending.remove(b)
            # Power and signals that leave this functional block receive labels.
            visible=net=='GND' or len(net_blocks.get(net,()))>1 or len(pins)==1
            p=min(pins,key=lambda p:(p['anchor'][1],p['anchor'][0])) if net=='GND' else max(pins,key=lambda p:(p['anchor'][1],p['anchor'][0]))
            anchor=p['anchor'];dx,dy=p['direction']
            if net=='GND' and page.ground:
                # Place a real native ground flag at a free branch endpoint.
                target=(anchor[0],anchor[1]-20)
                try:
                    path=router.simplify(router.route(anchor,target,net))
                    for a,b in zip(path,path[1:]):segments.append((a,b));router.mark(a,b,net)
                    page.ground_symbol(target);visible=False
                except RuntimeError:pass
            label=(anchor[0] if dy else anchor[0]+(3 if dx>=0 else -3),anchor[1]+(-3 if dy<0 else 3))
            align=('CENTER_TOP' if dy<0 else 'CENTER_BOTTOM') if dy else ('RIGHT_BOTTOM' if dx<0 else 'LEFT_BOTTOM')
            page.net(net,segments,label,align,visible)
            page.routes.append({'block':title,'net':net,'pins':len(pins),'segments':len(segments)})
    return page

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--apply',action='store_true');ap.add_argument('--report',type=Path,default=ROOT/'.build/schematic-layout-report.json');args=ap.parse_args()
    expected=json.loads((ROOT/'verification/expected-netlist.json').read_text());nets={c['ref']:c['pins'] for group in expected.values() for c in group};net_blocks=defaultdict(set)
    for sheet,blocks in LAYOUT.items():
        for i,(_,_,parts,_) in enumerate(blocks):
            for ref in parts:
                for net in nets[ref].values():net_blocks[net].add((sheet,i))
    pages=[];report=[]
    for name,blocks in LAYOUT.items():
        page=Page(SOURCE/(name+'.esch2'),nets)
        if name=='LCD':
            page.box((50,100,1120,760),'DISPLAY CONNECTION')
            for x,y,text in [(90,680,'4.3-inch display: direct 40-pin FPC from the core module.'),(90,640,'480 x 272 / GL043056B0 family.'),(90,600,'No baseboard RGB, touch or LCD power branch.'),(90,560,'Verify the module connector orientation and use the matching FPC cable.')]:page.text(x,y,text,12)
        else:apply_page(page,blocks,net_blocks)
        apply_adjustments(page.p,name)
        got,ambiguous=schematic_connections(page.p);wanted={(ref,num):net for ref in page.parts for num,net in nets[ref].items()}
        if got!=wanted or ambiguous:raise RuntimeError(f'Connectivity changed on {name}: missing={wanted.keys()-got.keys()} wrong={[(k,v,got.get(k)) for k,v in wanted.items() if got.get(k)!=v][:12]} ambiguous={ambiguous[:4]}')
        wire_nets={i:page.d.attributes(i).get('NET',('',{}))[1].get('value') for i,_ in page.d.items('WIRE')}
        occupied=defaultdict(set)
        for ident,line in page.d.items('LINE'):
            net=wire_nets.get(line.get('lineGroup'))
            if not net:continue
            x,y=line['startX'],line['startY'];end=(line['endX'],line['endY']);dx=0 if x==end[0] else (STEP if end[0]>x else -STEP);dy=0 if y==end[1] else (STEP if end[1]>y else -STEP)
            while True:
                occupied[x,y].add(net)
                if (x,y)==end:break
                x+=dx;y+=dy
        collisions=[(pt,sorted(ns)) for pt,ns in occupied.items() if len(ns)>1]
        if collisions:raise RuntimeError(f'Cross-net schematic wire contact on {name}: {collisions[:10]}')
        # Embedded symbol/footprint/device content is never modified.
        assert all(d.records==page.p.baseline[dk].records for dk,d in page.p.docs.items() if dk[0]!='SCH_PAGE')
        pages.append(page);report.append({'sheet':name,'parts':len(page.parts),'assigned_connections':len(got),'net_graph_identical':True,'local_routes':page.routes})
    if args.apply:
        for page in pages:print(page.name,'native log records written',write_changes(page.p))
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps({'applied':args.apply,'sheets':report,'electrical_networks_changed':False},ensure_ascii=False,indent=2)+'\n')
    print('All six sheet pin/net graphs match the frozen R8 design.')
if __name__=='__main__':main()
