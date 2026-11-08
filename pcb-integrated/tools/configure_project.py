"""Set editable KiCad project rules/netclasses; does not read/write EDA geometry."""
import json,copy
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'phone-mcp-s3.kicad_pro'
d=json.loads(p.read_text());settings=d.setdefault('board',{}).setdefault('design_settings',{})
settings['meta']={'version':2}
settings.setdefault('rules',{}).update(min_clearance=.15,min_track_width=.15,min_via_diameter=.45,min_hole_clearance=.15,min_through_hole_diameter=.2,min_text_height=.8,min_copper_edge_clearance=.25)
n=d.setdefault('net_settings',{});n['meta']={'version':5}
base={'name':'Default','clearance':.15,'track_width':.15,'via_diameter':.45,'via_drill':.2,'diff_pair_width':.2,'diff_pair_gap':.15,'diff_pair_via_gap':.25,'bus_width':12,'wire_width':6}
power=copy.deepcopy(base);power.update(name='Power',track_width=.6,via_diameter=.6,via_drill=.3,priority=0)
usb=copy.deepcopy(base);usb.update(name='USB_FS_review',track_width=.25,priority=1)
n['classes']=[base,power,usb]
n['netclass_patterns']=[{'netclass':'Power','pattern':name} for name in ['/VBUS_RAW','/5V_SYS','/3V3','/PHONE_VBUS','/BUCK_SW','/GND']]+[{'netclass':'USB_FS_review','pattern':name} for name in ['/PC_DP','/PC_DM','/ESP_USB_DP','/ESP_USB_DM','/PHONE_DP','/PHONE_DM']]
p.write_text(json.dumps(d,indent=2))
print('Power/USB routing classes configured; USB impedance remains unverified.')
