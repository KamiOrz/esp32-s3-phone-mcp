"""CLI-owned export and independent connectivity checks."""
import subprocess,json,xml.etree.ElementTree as ET
from pathlib import Path
R=Path(__file__).resolve().parents[1];K='/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
subprocess.run([K,'sch','export','netlist','--format','kicadxml','-o',str(R/'review/verified.net'),str(R/'phone-mcp-s3.kicad_sch')],check=True,capture_output=True)
xml=ET.parse(R/'review/verified.net');nets={};actual={}
for net in xml.findall('./nets/net'):
 name=net.attrib['name'].lstrip('/');nets[name]=set()
 for node in net.findall('node'):
  key=(node.attrib['ref'],node.attrib['pin']);nets[name].add(key);actual[key]=name
spec=json.loads((R/'design.json').read_text());expected={}
for c in spec['components']:
 if c['ref'].startswith('#'):continue
 for pin,name in c['nets'].items():expected[(c['ref'],pin)]=name
errors=[(key,name,actual.get(key)) for key,name in expected.items() if actual.get(key)!=name]
assert not errors,errors
# Assert architecture-critical separations and signal routing independently of ERC.
assert nets['PC_DP'].isdisjoint(nets['PHONE_DP']) and nets['PC_DM'].isdisjoint(nets['PHONE_DM'])
assert actual['U1','13']=='ESP_USB_DM' and actual['U1','14']=='ESP_USB_DP'
assert actual['U2','21']==actual['U1','36']=='ESP_RX'
assert actual['U2','20']==actual['U1','37']=='ESP_TX'
assert actual['U5','1']=='5V_SYS' and actual['U5','6']=='PHONE_VBUS'
assert actual['U3','3']==actual['U3','5']==actual['U3','11']=='GND'
assert all(('U1',str(p)) not in actual or actual['U1',str(p)].startswith('unconnected') for p in [28,29,30])
assert actual['D2','1']=='VBUS_RAW' and actual['D2','2']=='GND'
assert actual['C23','1']=='PHONE_VBUS' and actual['C23','2']=='GND'
# Quantitative component-limit review (datasheet equations, resistor tolerance).
rmin=44.2*(1-0.01);rmax=44.2*(1+0.01)
maximum=22980/rmin**.94;minimum=25230/rmax**1.016
ovlo_min=1.13*(1+367*.999/(100*1.001));ovlo_max=1.27*(1+367*1.001/(100*.999))
report={'checked_pin_net_assignments':len(expected),'logical_nets':len(set(expected.values())),'connectivity':'PASS','usb_data_channels_independent':True,'phone_limit_mA':[round(minimum,1),round(maximum,1)],'input_OVLO_threshold_range_V':[round(ovlo_min,3),round(ovlo_max,3)],'manufacturing_release':False,'pcb_routed':False}
(R/'review/connectivity-check.json').write_text(json.dumps(report,indent=2))
subprocess.run([K,'sch','export','pdf','-o',str(R/'review/phone-mcp-s3-schematic.pdf'),str(R/'phone-mcp-s3.kicad_sch')],check=True,capture_output=True)
subprocess.run([K,'sch','export','svg','-o',str(R/'review/svg')+'/',str(R/'phone-mcp-s3.kicad_sch')],check=True,capture_output=True)
print(json.dumps(report,indent=2))
