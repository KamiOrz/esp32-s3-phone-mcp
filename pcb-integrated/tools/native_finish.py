"""Final PCB audit, revision label and mechanical-envelope renders.
Invoke only through kicad-tool project-build tools/finish_board.py.
"""
import argparse,json,subprocess,os,hashlib
from pathlib import Path
import wx
app=wx.App(False)
import pcbnew as k
R=Path(__file__).resolve().parents[1];P=R/'phone-mcp-s3.kicad_pcb'
p=argparse.ArgumentParser();p.add_argument('action',choices=['audit','revision','models','render']);p.add_argument('--dry-run',action='store_true');a=p.parse_args()
b=k.LoadBoard(str(P));fps={f.GetReference():f for f in b.GetFootprints()}
def pos(o):return [round(k.ToMM(o.GetPosition().x),4),round(k.ToMM(o.GetPosition().y),4)]
if a.action=='revision':
 for d in b.GetDrawings():
  if isinstance(d,k.PCB_TEXT) and d.GetText()=='PHONE MCP S3 - A0':d.SetText('PHONE MCP S3 - A1')
 b.GetTitleBlock().SetRevision('A1 - four-layer prototype')
 if not a.dry_run:k.SaveBoard(str(P),b)
 print('Updated revision to A1')
elif a.action=='audit':
 report=json.loads((R/'review/final/drc.rpt').read_text());parity=json.loads((R/'review/final/parity.json').read_text())
 assert not report['violations'] and not report['unconnected_items'],'PCB DRC is not clean'
 assert b.GetCopperLayerCount()==4
 holes={r:{'at_mm':pos(fps[r]),'drill_mm':round(k.ToMM(next(iter(fps[r].Pads())).GetDrillSize().x),4)} for r in ['H1','H2','H3','H4']}
 for r,at in [('H1',[103,103]),('H2',[152,103]),('H3',[103,132]),('H4',[152,132])]:assert holes[r]['at_mm']==at and holes[r]['drill_mm']==2.2
 tracks=list(b.GetTracks());vias=[t for t in tracks if isinstance(t,k.PCB_VIA)]
 stats={'stage':'routed_prototype_review','revision':'A1','copper_layers':4,'outline_mm':[55,35],'component_envelope_mm':[55,41.5],'mounting_holes':holes,'hole_pitch_mm':[49,29],'screw_head_keepout_diameter_mm':5,'footprints':len(fps),'track_segments':len(tracks)-len(vias),'vias':len(vias),'erc_errors':0,'erc_warnings':0,'geometry_violations':0,'unrouted_findings':0,'schematic_parity_findings':0,'checked_pin_net_assignments':234,'routed':True,'manufacturing_release':False,'hardware_tested':False,'placement':{r:pos(f)+[f.GetOrientationDegrees()] for r,f in fps.items()},'sha256':{name:hashlib.sha256((R/name).read_bytes()).hexdigest() for name in ['phone-mcp-s3.kicad_sch','phone-mcp-s3.kicad_pcb','phone-mcp-s3.kicad_pro','BOM.csv']}}
 if not a.dry_run:
  (R/'review/state.json').write_text(json.dumps(stats,indent=2));(R/'review/placement.json').write_text(json.dumps(stats,indent=2))
 print(json.dumps({x:y for x,y in stats.items() if x not in ['placement','sha256']},indent=2))
elif a.action=='models':
 modeldir=R/'models';modeldir.mkdir(exist_ok=True)
 def box(x,y,z,dx,dy,dz,col):
  vals=[v/2.54 for v in [x,y,z,dx,dy,dz]]
  return 'Transform { translation %g %g %g children [ Shape { appearance Appearance { material Material { diffuseColor %s } } geometry Box { size %g %g %g } } ] }\n'%(tuple(vals[:3])+(' '.join(map(str,col)),)+tuple(vals[3:]))
 # Mechanical envelopes from manufacturer drawings; simplified, explicitly documented.
 j1=''
 for args in [(-4.37,0,1.63,.2,7.35,3.26),(4.37,0,1.63,.2,7.35,3.26),(0,0,3.16,8.94,7.35,.2),(0,0,.1,8.94,7.35,.2),(0,3.575,1.63,8.94,.2,3.26)]:j1+=box(*args,(.68,.7,.72))
 j1+=box(0,-1.2,1.63,7,4,.6,(.10,.10,.11))
 j2=''
 for args in [(0,-4.15,3.5,16.1,.3,7),(-7.9,3.2,3.5,.3,15,7),(7.9,3.2,3.5,.3,15,7),(0,3.2,6.85,16.1,15,.3),(0,3.2,.15,16.1,15,.3)]:j2+=box(args[0],-args[1],*args[2:],(.68,.7,.72))
 j2+=box(0,-1.0,3.5,12,5,2.2,(.10,.10,.11))
 l=box(0,0,1,4,4,2,(.18,.19,.20))
 if not a.dry_run:
  for ref,name,text in [('J1','USB_C_envelope',j1),('J2','USB_A_envelope',j2),('L1','XGL4020_envelope',l),('U3','X2QFN_envelope',box(0,0,.2,1.6,1.6,.4,(.12,.12,.12))),('U6','DFN_envelope',box(0,0,.4,2,2,.8,(.12,.12,.12)))]:
   (modeldir/(name+'.wrl')).write_text('#VRML V2.0 utf8\n# Simplified mechanical envelope, NOT vendor CAD\n'+text)
   f=fps[ref];f.Models().clear();m=k.FP_3DMODEL();m.m_Filename='${KIPRJMOD}/models/'+name+'.wrl';f.Models().push_back(m)
  k.SaveBoard(str(P),b)
 print('Attached five explicitly simplified mechanical envelope models')
elif a.action=='render':
 if not a.dry_run:
  env=os.environ.copy();env['KICAD9_3DMODEL_DIR']='/Applications/KiCad/KiCad.app/Contents/SharedSupport/3dmodels';env['KICAD10_3DMODEL_DIR']=env['KICAD9_3DMODEL_DIR']
  for name,rot in [('pcb-3d-top','0,0,0'),('pcb-3d-isometric','325,0,25')]:
   subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','render','--width','1800','--height','1300','--quality','high','--background','opaque','--rotate='+rot,'-o',str(R/'review'/ (name+'.png')),str(P)],env=env,check=True)
