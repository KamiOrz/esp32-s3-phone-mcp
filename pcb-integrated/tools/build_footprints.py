"""Project-specific footprint construction via kicad-tool project-build."""
import argparse,json,uuid
from pathlib import Path
from kiutils.footprint import Footprint,Pad,Attributes,DrillDefinition
from kiutils.items.common import Position,Effects,Font
from kiutils.items.fpitems import FpText,FpRect
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--dry-run',action='store_true');a=p.parse_args()
 f=Footprint(entryName='USB_A_SameSky_UJ2_AH_SMT',version='20221018',generator='phone_mcp_kicad_tool',attributes=Attributes(type='smd'),description='Same Sky UJ2-AH-4-SMT-TR; manufacturer uj2-ah-smt.pdf 2025-07-15 p2; all solder pads SMT; plastic locating pegs NPTH')
 f.properties={'Reference':'REF**','Value':f.entryName}
 f.graphicItems=[FpText(type='reference',text='REF**',position=Position(0,-6.2,0),layer='F.SilkS',effects=Effects(font=Font(height=1,width=1))),FpText(type='value',text=f.entryName,position=Position(0,12,0),layer='F.Fab',hide=True,effects=Effects(font=Font(height=1,width=1))),FpRect(start=Position(-8.05,-4.3),end=Position(8.05,10.7),layer='F.Fab',width=0.1),FpRect(start=Position(-8.65,-5.4),end=Position(8.65,11.2),layer='F.CrtYd',width=0.05)]
 for n,x in enumerate([-3.5,-1,1,3.5],1):f.pads.append(Pad(number=str(n),type='smd',shape='rect',position=Position(x,-3.55,0),size=Position(1.1,3.2),layers=['F.Cu','F.Paste','F.Mask']))
 for x in [-7.325,7.325]:f.pads.append(Pad(number='SH',type='smd',shape='rect',position=Position(x,-1.32,0),size=Position(2.15,4.8),layers=['F.Cu','F.Paste','F.Mask']))
 for x in [-2.5,2.5]:f.pads.append(Pad(number='',type='np_thru_hole',shape='circle',position=Position(x,0,0),size=Position(1.3,1.3),drill=DrillDefinition(diameter=1.3),layers=['*.Cu','*.Mask']))
 assert all(p.type in ('smd','np_thru_hole') for p in f.pads)
 text=f.to_sexpr()
 l=Footprint(entryName='L_Coilcraft_XGL4020',version='20221018',generator='phone_mcp_kicad_tool',attributes=Attributes(type='smd'),description='Coilcraft XGL4020; xgl4020.pdf document 1334-3 land pattern; 0.98x3.4mm pads 2.37mm pitch')
 l.properties={'Reference':'REF**','Value':'XGL4020-472MEC'}
 l.graphicItems=[FpRect(start=Position(-2.15,-2.15),end=Position(2.15,2.15),layer='F.Fab',width=0.1),FpRect(start=Position(-2.4,-2.4),end=Position(2.4,2.4),layer='F.CrtYd',width=0.05)]
 for n,x in [(1,1.185),(2,-1.185)]:l.pads.append(Pad(number=str(n),type='smd',shape='rect',position=Position(x,0,0),size=Position(0.98,3.4),layers=['F.Cu','F.Paste','F.Mask']))
 l.to_sexpr()
 module=Footprint.from_file('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/RF_Module.pretty/ESP32-S3-WROOM-1.kicad_mod')
 module.entryName='ESP32_S3_WROOM_1_Overhang';module.graphicItems=[g for g in module.graphicItems if getattr(g,'layer','')!='F.SilkS']
 module.to_sexpr()
 if not a.dry_run:
  lib=ROOT/'PhoneMCP.pretty';lib.mkdir(exist_ok=True);f.to_file(str(lib/(f.entryName+'.kicad_mod')));l.to_file(str(lib/(l.entryName+'.kicad_mod')))
  (ROOT/'fp-lib-table').write_text('(fp_lib_table (version 7) (lib (name "PhoneMCP")(type "KiCad")(uri "${KIPRJMOD}/PhoneMCP.pretty")(options "")(descr "Manufacturer drawing based SMT connector")))\n')
 if not a.dry_run:
  # Retain the stock file verbatim except for its identity and front-silk graphics.
  # kiutils does not round-trip every KiCad-10 rule-area token yet.
  source=Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/RF_Module.pretty/ESP32-S3-WROOM-1.kicad_mod').read_text()
  ranges=[];depth=0;quoted=False;escape=False;begin=None
  for i,ch in enumerate(source):
   if quoted:
    if escape:escape=False
    elif ch=='\\':escape=True
    elif ch=='"':quoted=False
    continue
   if ch=='"':quoted=True
   elif ch=='(':
    if depth==1:begin=i
    depth+=1
   elif ch==')':
    depth-=1
    if depth==1 and begin is not None:
     block=source[begin:i+1]
     if block.startswith(('(fp_line','(fp_rect','(fp_poly','(fp_arc','(fp_circle','(fp_text')) and '(layer "F.SilkS")' in block:ranges.append((begin,i+1))
     begin=None
  assert depth==0 and not quoted
  for first,last in reversed(ranges):source=source[:first]+source[last:]
  source=source.replace('(footprint "ESP32-S3-WROOM-1"','(footprint "ESP32_S3_WROOM_1_Overhang"',1)
  (ROOT/'PhoneMCP.pretty/ESP32_S3_WROOM_1_Overhang.kicad_mod').write_text(source)
 print(json.dumps({'dry_run':a.dry_run,'footprint':f.entryName,'smd_pads':6,'locating_holes':2,'soldered_through_hole_pads':0,'bytes':len(text)}))
if __name__=='__main__':main()
