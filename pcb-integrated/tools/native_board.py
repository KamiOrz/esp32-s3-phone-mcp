"""Native PCB creation; invoked only by kicad-tool project-build build_board.py."""
import argparse,json,math,xml.etree.ElementTree as ET
from pathlib import Path
import wx
app=wx.App(False)
import pcbnew as k
R=Path(__file__).resolve().parents[1];F=Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints')
parser=argparse.ArgumentParser();parser.add_argument('--dry-run',action='store_true');a=parser.parse_args()
mm=k.FromMM
vec=lambda x,y:k.VECTOR2I(mm(x),mm(y))
b=k.BOARD();ds=b.GetDesignSettings();ds.SetCopperLayerCount(2);ds.m_MinClearance=mm(.15);ds.m_MinThroughDrill=mm(.2);ds.m_HoleClearance=mm(.15);ds.m_CopperEdgeClearance=mm(.25)
nc=ds.m_NetSettings.GetDefaultNetclass();nc.SetClearance(mm(.15));nc.SetTrackWidth(mm(.15));nc.SetViaDiameter(mm(.6));nc.SetViaDrill(mm(.3))
power=k.NETCLASS('Power');power.SetClearance(mm(.15));power.SetTrackWidth(mm(.6));power.SetViaDiameter(mm(.8));power.SetViaDrill(mm(.4))
netlist=ET.parse(R/'review/verified.net');netmap={};pinnets={}
for n in netlist.findall('./nets/net'):
 name=n.attrib['name'];name=name.replace('/','{slash}') if name.startswith('unconnected-') else name;net=k.NETINFO_ITEM(b,name);b.Add(net);netmap[name]=net
 if name in ['/GND','/3V3','/5V_SYS','/VBUS_RAW','/PHONE_VBUS','/BUCK_SW']:net.SetNetClass(power)
 for node in n.findall('node'):pinnets[node.attrib['ref'],node.attrib['pin']]=net
spec=json.loads((R/'design.json').read_text());conn=json.loads((R/'connectivity.json').read_text());records={r['ref']:r for r in conn['components']}
fixed={'U1':(115,106.25,0),'U2':(128,122,0),'U3':(120,125.5,0),'U4':(136,108,0),'U5':(138,116.5,0),'U6':(120.5,130,0),'U7':(111,124,0),'U8':(143,116.8,0),'U9':(116,124.5,0),'J1':(110,131.325,0),'J2':(143,124.3,0),'L1':(141,108,180),'C23':(150,115,0),'SW1':(130,103.5,0),'SW2':(129,111.5,0),'D1':(128,114.5,0),'C1':(103,105.5,90),'C2':(103,109,90),'C3':(103,101.8,90),'C17':(136,105,0),'C18':(132,107.5,90),'C19':(145.4,106,90),'C20':(145.4,110,90),'R24':(103,115.8,180),'R25':(103,118.0,180)}
anchors={'U1':(104,114),'U2':(125,124),'U3':(121,125),'U4':(136,107),'U5':(138,115),'U6':(120,130),'U7':(110,124),'U8':(143,118),'U9':(116,124)}
# Reference groups from the placement/specification sheet.
sections={}
for c in spec['components']:
 if c['ref'].startswith(('#','TP')):continue
 x,y=c['at'];column=round((x-105)/205);row=0 if y<280 else 1
 sections[c['ref']]=max(0,min(3,column))+4*row
sanchors={0:(104,114),1:(126,123),2:(122,125),3:(112,124),4:(121,130),5:(137,107),6:(138,115),7:(143,118)}
fps={}
for c in spec['components']:
 ref=c['ref']
 if ref.startswith('#'):continue
 record=records[ref];lib,name=record['footprint'].split(':',1)
 libpath=R/'PhoneMCP.pretty' if lib=='PhoneMCP' else F/(lib+'.pretty')
 f=k.FootprintLoad(str(libpath),name)
 if not f:raise RuntimeError('Missing footprint '+record['footprint'])
 f.SetReference(ref);f.SetValue(record['value']);f.SetAttributes(f.GetAttributes() & ~k.FP_EXCLUDE_FROM_BOM);
 for key,value in record.get('properties',{}).items():
  if key not in ['Reference','Value','Footprint']:
   f.SetField(key,value);f.GetField(key).SetVisible(False)
 f.SetFPID(k.LIB_ID(lib,name));f.SetPath(k.KIID_PATH('/'+str(__import__('uuid').uuid5(__import__('uuid').UUID('8bc32d7e-02cd-47ed-bfd6-86a8b8da1a3e'),'sheet'))+'/'+record['uuid']))
 f.Reference().SetVisible(False);f.Reference().SetTextSize(vec(.8,.8));f.Reference().SetTextThickness(mm(.12));f.Value().SetVisible(False)
 for p in f.Pads():
  pn=p.GetNumber()
  if pn and (ref,pn) in pinnets:p.SetNet(pinnets[ref,pn])
  if pn and p.GetAttribute()!=k.PAD_ATTRIB_SMD and not (ref=='U1' and pn=='41' and k.ToMM(p.GetDrillSize().x)<=.3):raise AssertionError('Soldered non-SMT pad '+ref+'.'+pn)
 b.Add(f);fps[ref]=f
# Collision bounding boxes use courtyards when present and a small extra gap.
def bbox(f):
 if f.GetReference()=='U1':
  x,y=k.ToMM(f.GetPosition().x),k.ToMM(f.GetPosition().y)
  return (x-9.6,y-12.75,x+9.6,y+13.475)
 rect=f.GetBoundingBox(False,False)
 # Library drawings can contain distant reference/value fields; use courtyard geometry.
 points=[]
 for g in f.GraphicalItems():
  if g.GetLayer()==k.F_CrtYd:
   box=g.GetBoundingBox();points.extend([(k.ToMM(box.GetX()),k.ToMM(box.GetY())),(k.ToMM(box.GetRight()),k.ToMM(box.GetBottom()))])
 if not points:
  for p in f.Pads():
   box=p.GetBoundingBox();points.extend([(k.ToMM(box.GetX()),k.ToMM(box.GetY())),(k.ToMM(box.GetRight()),k.ToMM(box.GetBottom()))])
 return (min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points))
def clash(a,b,gap=.12):return a[0]<b[2]+gap and a[2]>b[0]-gap and a[1]<b[3]+gap and a[3]>b[1]-gap
placed={}
for ref,(x,y,rot) in fixed.items():
 f=fps[ref];f.SetPosition(vec(x,y));f.SetOrientationDegrees(rot);placed[ref]=bbox(f)
fixed_conflicts=[(r,s) for i,r in enumerate(placed) for s in list(placed)[i+1:] if clash(placed[r],placed[s])]
if fixed_conflicts:print('FIXED BOXES',placed);raise RuntimeError('Fixed footprint conflicts: '+str(fixed_conflicts))
remaining=[r for r in fps if r not in placed and not r.startswith('TP')]
remaining.sort(key=lambda r:-(bbox(fps[r])[2]-bbox(fps[r])[0])*(bbox(fps[r])[3]-bbox(fps[r])[1]))
for ref in remaining:
 f=fps[ref];ax,ay=sanchors.get(sections[ref],(128,118));best=None
 for rot in [0,90]:
  f.SetOrientationDegrees(rot);f.SetPosition(vec(0,0));offset=bbox(f)
  for ix in range(1010,1541,5):
   for iy in range(1010,1341,5):
    x,y=ix/10,iy/10;box=(offset[0]+x,offset[1]+y,offset[2]+x,offset[3]+y)
    if box[0]<100.4 or box[1]<100.4 or box[2]>154.6 or box[3]>134.6:continue
    if any(clash(box,q) for q in placed.values()):continue
    score=(x-ax)**2+(y-ay)**2
    if best is None or score<best[0]:best=(score,x,y,rot,box)
 if best is None:raise RuntimeError('Cannot place '+ref)
 _,x,y,rot,box=best;f.SetPosition(vec(x,y));f.SetOrientationDegrees(rot);placed[ref]=box
# Place SMT test pads with a pad-side courtyard reserve; never under the module.
for i,ref in enumerate(r for r in fps if r.startswith('TP')):
 f=fps[ref];best=None
 for ix in range(1010,1541,10):
  for iy in range(1010,1341,10):
   x,y=ix/10,iy/10;f.SetPosition(vec(x,y));box=bbox(f)
   if any(clash(box,q,.2) for q in placed.values()):continue
   score=(x-152)**2+(y-105-i*1.7)**2
   if best is None or score<best[0]:best=(score,x,y,box)
 if best is None:raise RuntimeError('Cannot place '+ref)
 _,x,y,box=best;f.SetPosition(vec(x,y));placed[ref]=box
# Straight 55 x 35 board; antenna extends beyond the top edge, no solder pins outside.
for p,q in [((100,100),(155,100)),((155,100),(155,135)),((155,135),(100,135)),((100,135),(100,100))]:
 edge=k.PCB_SHAPE();edge.SetShape(k.SHAPE_T_SEGMENT);edge.SetStart(vec(*p));edge.SetEnd(vec(*q));edge.SetLayer(k.Edge_Cuts);edge.SetWidth(mm(.05));b.Add(edge)
for txt,x,y in [('PHONE MCP S3 - A0',136,114),('PC / 5V',110,136.5),('PHONE',143,136.5)]:
 t=k.PCB_TEXT(b);t.SetText(txt);t.SetPosition(vec(x,y));t.SetLayer(k.B_SilkS if txt.startswith('PHONE MCP') else k.Dwgs_User);t.SetMirrored(txt.startswith('PHONE MCP'));t.SetTextSize(vec(.85,.85));t.SetTextThickness(mm(.12));b.Add(t)
# Ground reference plane; local signal routes may still create splits requiring review.
z=k.ZONE(b);z.SetLayer(k.B_Cu);z.SetNet(netmap['/GND']);z.SetLocalClearance(mm(.2));z.SetMinThickness(mm(.2));z.SetPadConnection(k.ZONE_CONNECTION_THERMAL);z.SetThermalReliefGap(mm(.25));z.SetThermalReliefSpokeWidth(mm(.3));poly=z.Outline();poly.NewOutline()
for x,y in [(100.3,100.3),(154.7,100.3),(154.7,134.7),(100.3,134.7)]:poly.Append(mm(x),mm(y))
b.Add(z);k.ZONE_FILLER(b).Fill(b.Zones())
summary={'footprints':len(fps),'nets':len(netmap),'soldered_through_hole_pads':0,'outline_mm':[55,35],'routed':False,'placement':{r:[round(k.ToMM(f.GetPosition().x),3),round(k.ToMM(f.GetPosition().y),3),f.GetOrientationDegrees()] for r,f in fps.items()}}
if not a.dry_run:
 k.SaveBoard(str(R/'phone-mcp-s3.kicad_pcb'),b)
 k.ExportSpecctraDSN(b,str(R/'review/phone-mcp-s3.dsn'))
 (R/'review/placement.json').write_text(json.dumps(summary,indent=2))
print(json.dumps({k:v for k,v in summary.items() if k!='placement'}))
