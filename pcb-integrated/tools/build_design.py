#!/usr/bin/env python3
"""Reproducible structural KiCad builder; run via kicad-tool project-build.
Only this CLI-owned builder serializes EDA documents. Never edits existing designs.
"""
import argparse,copy,json,math,uuid
from pathlib import Path
from kiutils.schematic import Schematic
from kiutils.symbol import SymbolLib,Symbol,SymbolPin
from kiutils.items.common import Position,Property,Effects,Font,PageSettings,TitleBlock,Stroke,Fill,Justify
from kiutils.items.schitems import SchematicSymbol,SymbolProjectInstance,SymbolProjectPath,Connection,LocalLabel,NoConnect,Text
from kiutils.items.syitems import SyRect
ROOT=Path(__file__).resolve().parents[1]
LIB=Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols')
NS=uuid.UUID('8bc32d7e-02cd-47ed-bfd6-86a8b8da1a3e')
def uid(s):return str(uuid.uuid5(NS,s))
def fx(size=1.0,hide=False,align=None):return Effects(font=Font(height=size,width=size),hide=hide,justify=Justify(horizontally=align))
cache={}
def library(name):
 if name not in cache:cache[name]={s.entryName:s for s in SymbolLib.from_file(str(LIB/(name+'.kicad_sym'))).symbols}
 return cache[name]
def resolve(lib,name):
 s=copy.deepcopy(library(lib)[name])
 if s.extends:
  base=resolve(lib,s.extends)
  props={p.key:p for p in base.properties};props.update({p.key:p for p in s.properties})
  base.properties=list(props.values())
  if s.units:base.units=s.units
  base.entryName=name;base.extends=None
  s=base
 for i,u in enumerate(s.units):
  # Preserve unit/style IDs while reidentifying inherited units.
  u.entryName=name
 s.libraryNickname=lib;s.entryName=name
 return s
custom=[]
def custom_ic(name,pinrows,fp,url):
 s=Symbol(entryName=name,inBom=True,onBoard=True,pinNames=True,pinNamesOffset=0.5)
 s.properties=[Property(key=k,value=v,position=Position(0,0,0),effects=fx(hide=k not in ('Reference','Value'))) for k,v in [('Reference','U'),('Value',name),('Footprint',fp),('Datasheet',url)]]
 unit=Symbol(entryName=name,unitId=1,styleId=1)
 left=[p for p in pinrows if p[3]=='L'];right=[p for p in pinrows if p[3]=='R']
 h=max(len(left),len(right))*2.54/2+2.54
 unit.graphicItems=[SyRect(start=Position(-10.16,h),end=Position(10.16,-h),stroke=Stroke(width=0.254,type='default'),fill=Fill(type='background'))]
 for rows,side in [(left,'L'),(right,'R')]:
  for i,(num,pname,typ,_) in enumerate(rows):
   unit.pins.append(SymbolPin(number=str(num),name=pname,electricalType=typ,position=Position(-12.7 if side=='L' else 12.7,(len(rows)-1)*1.27-i*2.54,0 if side=='L' else 180),length=2.54,nameEffects=fx(),numberEffects=fx()))
 s.units=[unit];custom.append(s);library('PhoneMCP')[name]=s
# Project-local symbol library loaded in memory before resolving.
cache['PhoneMCP']={}
custom_ic('TPS2553DBVR',[(1,'IN','power_in','L'),(3,'EN','input','L'),(2,'GND','power_in','L'),(6,'OUT','power_out','R'),(4,'~{FAULT}','open_collector','R'),(5,'ILIM','passive','R')],'Package_TO_SOT_SMD:SOT-23-6','https://www.ti.com/lit/ds/symlink/tps2553.pdf')
custom_ic('TPS259573DSGR',[(3,'IN','power_in','L'),(4,'IN','passive','L'),(2,'EN/OVLO','input','L'),(1,'dVdt','passive','L'),(5,'OUT','power_out','R'),(6,'~{FLT}','open_collector','R'),(7,'ILM','passive','R'),(8,'GND','power_in','R'),(9,'EP/GND','passive','R')],'Package_DFN_QFN:WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm','https://www.ti.com/lit/ds/symlink/tps2595.pdf')
# LAI has the same package/pin map as this library symbol; distinguish exact part.
u3=resolve('Interface_USB','TUSB320');u3.libraryNickname=None;u3.entryName='TUSB320LAIRWBR'
for u in u3.units:u.entryName='TUSB320LAIRWBR'
for prop in u3.properties:
 if prop.key=='Value':prop.value=u3.entryName
 if prop.key=='Datasheet':prop.value='https://www.ti.com/lit/ds/symlink/tusb320lai.pdf'
custom.append(u3);cache['PhoneMCP'][u3.entryName]=u3

def build(spec):
 sch=Schematic(version='20250114',generator='phone_mcp_kicad_tool',uuid=uid('sheet'),paper=PageSettings(paperSize='A1'),titleBlock=TitleBlock(title='Phone MCP S3 - integrated USB controller',date='2026-11-08',revision='A0 - schematic review',company='Private project',comments={1:'NOT FOR FABRICATION - PCB unrouted',2:'5V input only; phone VBUS defaults OFF; full SMT'}))
 embedded={};records=[];wire_keys=set();label_keys=set();net_nodes={}
 for c in spec['components']:
  lib,name=c['symbol'].split(':',1)
  if c['symbol'] not in embedded:
   embedded[c['symbol']]=resolve(lib,name);sch.libSymbols.append(embedded[c['symbol']])
  symbol=embedded[c['symbol']];ref=c['ref'];x,y=[round(round(v/1.27)*1.27,4) for v in c['at']];ang=c.get('rotation',0);rad=math.radians(ang)
  inst=SchematicSymbol(libraryNickname=lib,entryName=name,position=Position(x,y,ang),unit=1,inBom=not ref.startswith('#'),onBoard=not ref.startswith('#'),uuid=uid(ref),instances=[SymbolProjectInstance(name='phone-mcp-s3',paths=[SymbolProjectPath(sheetInstancePath='/'+sch.uuid,reference=ref,unit=1)])])
  vals={p.key:p.value for p in symbol.properties if not p.key.startswith('ki_')};vals.update(c.get('properties',{}));vals['Reference']=ref;vals['Value']=c.get('value',vals.get('Value',name))
  if 'footprint' in c:vals['Footprint']=c['footprint']
  if 'mpn' in c:vals['MPN']=c['mpn']
  pins=[p for u in symbol.units if u.unitId in (0,1) and u.styleId in (0,1) for p in u.pins]
  unique={p.number:p for p in pins};pins=list(unique.values())
  # Use explicit fixed field placement rather than guessing from font glyph metrics.
  top=max([p.position.Y*math.cos(rad)-p.position.X*math.sin(rad) for p in pins]+[0])
  py=y-top-12.7
  for key,value in vals.items():
   vis=key in ('Reference','Value')
   yy=py if key=='Reference' else py+1.7 if key=='Value' else y
   field_x=x
   small=ref.startswith(('R','C','L')) and len(pins)==2
   if small and vis:field_x=x+4.5;yy=y-1.1 if key=='Reference' else y+1.1
   inst.properties.append(Property(key=key,value=value,position=Position(field_x,yy,0),effects=fx(1.05 if key=='Reference' else 0.9,hide=not vis,align='left' if small else None)))
  nc=c.get('nc',[]);assigned=set(c.get('nets',{}))
  assert not assigned.intersection(nc),(ref,'connected and NC')
  assert assigned.union(nc)==set(unique),(ref,'Unspecified pins',set(unique)-assigned-set(nc))
  for pin in pins:
   inst.pins[pin.number]=uid(ref+'.'+pin.number)
   # Local library coords are Cartesian; schematic Y is downward.
   px=x+pin.position.X*math.cos(rad)-pin.position.Y*math.sin(rad)
   py=y-pin.position.X*math.sin(rad)-pin.position.Y*math.cos(rad)
   px,py=round(px,4),round(py,4)
   if pin.number in nc:
    if pin.electricalType!='no_connect':sch.noConnects.append(NoConnect(position=Position(px,py),uuid=uid('NC'+ref+pin.number)))
    continue
   net=c['nets'][pin.number];net_nodes.setdefault(net,[]).append((ref,pin.number))
   # Pin points toward body; extend outward by 5.08 mm.
   a=math.radians((pin.position.angle or 0)+ang)
   ex,ey=round(px-5.08*math.cos(a),4),round(py+5.08*math.sin(a),4)
   key=(px,py,ex,ey)
   if key not in wire_keys:
    wire_keys.add(key);sch.graphicalItems.append(Connection(points=[Position(px,py),Position(ex,ey)],stroke=Stroke(width=0,type='default'),uuid=uid('wire'+repr(key))))
   lk=(ex,ey,net)
   if lk not in label_keys:
    label_keys.add(lk)
    # Outward-facing readable labels; upright labels on vertical pins.
    angle=180 if ex<px-0.1 else 0 if ex>px+0.1 else 90
    sch.labels.append(LocalLabel(text=net,position=Position(ex,ey,angle),effects=Effects(font=Font(height=0.9,width=0.9),justify=Justify(horizontally='left',vertically='bottom')),uuid=uid('label'+repr(lk))))
  sch.schematicSymbols.append(inst)
  records.append({'ref':ref,'value':vals['Value'],'footprint':vals.get('Footprint',''),'mpn':vals.get('MPN',''),'nets':c.get('nets',{}),'uuid':inst.uuid,'nc':nc,'properties':vals})
 for i,note in enumerate(spec.get('notes',[])):
  sch.texts.append(Text(text=note['text'],position=Position(*note['at'],0),effects=fx(note.get('size',1.5)),uuid=uid('note'+str(i))))
 return sch,records,net_nodes

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--dry-run',action='store_true');args=parser.parse_args()
 spec=json.loads((ROOT/'design.json').read_text());sch,records,nets=build(spec)
 # Serialization is performed even in dry-run to catch data/schema errors.
 serialized=sch.to_sexpr()
 if not args.dry_run:
  target=ROOT/'phone-mcp-s3.kicad_sch'
  sch.to_file(str(target))
  SymbolLib(version='20211014',generator='phone_mcp_kicad_tool',symbols=custom).to_file(str(ROOT/'PhoneMCP.kicad_sym'))
  (ROOT/'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "PhoneMCP")(type "KiCad")(uri "${KIPRJMOD}/PhoneMCP.kicad_sym")(options "")(descr "Project-local verified pin maps")))\n')
  (ROOT/'phone-mcp-s3.kicad_pro').write_text(json.dumps({'meta':{'filename':'phone-mcp-s3.kicad_pro','version':1},'board':{'design_settings':{'meta':{'version':2},'rules':{'min_clearance':0.15,'min_track_width':0.15,'min_hole_clearance':0.15,'min_through_hole_diameter':0.2,'min_text_height':0.6,'min_text_thickness':0.1}}},'net_settings':{'classes':[{'name':'Default','clearance':0.15,'track_width':0.25,'via_diameter':0.6,'via_drill':0.3}]},'schematic':{}},indent=2))
  (ROOT/'connectivity.json').write_text(json.dumps({'components':records,'nets':nets},indent=2))
  import csv
  with (ROOT/'BOM.csv').open('w') as f:
   w=csv.writer(f);w.writerow(['Reference','Value','Footprint','MPN'])
   for r in records:
    if not r['ref'].startswith('#'):w.writerow([r[k] for k in ['ref','value','footprint','mpn']])
 print(json.dumps({'dry_run':args.dry_run,'symbols':len(records),'nets':len(nets),'bytes':len(serialized),'target':str(ROOT/'phone-mcp-s3.kicad_sch')}))
if __name__=='__main__':main()
