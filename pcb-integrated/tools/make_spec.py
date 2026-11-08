"""Generate the human-reviewable component/net specification (no EDA file access)."""
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
C=[];counts={};slots={}
def comp(ref,symbol,value,nets,section,at=None,footprint=None,mpn=None,nc=(),rotation=0):
 if at is None:
  idx=slots.get(section,0);slots[section]=idx+1
  cx,cy=[(105,177),(310,177),(515,177),(720,177),(105,425),(310,425),(515,425),(720,425)][section]
  at=[cx-60+(idx%3)*60,cy+(idx//3)*25]
 d={'ref':ref,'symbol':symbol,'value':value,'nets':{str(k):v for k,v in nets.items()},'nc':[str(n) for n in nc],'at':at}
 if footprint is not None:d['footprint']=footprint
 if mpn:d['mpn']=mpn
 if rotation:d['rotation']=rotation
 C.append(d);return ref
RFP='Resistor_SMD:R_0603_1608Metric';CFP='Capacitor_SMD:C_0603_1608Metric'
def two(prefix,symbol,value,a,b,section,fp,mpn=None):
 counts[prefix]=counts.get(prefix,0)+1
 return comp(prefix+str(counts[prefix]),symbol,value,{1:a,2:b},section,footprint=fp,mpn=mpn)
def R(value,a,b,s,mpn=None):return two('R','Device:R',value,a,b,s,RFP,mpn)
def cap(value,a,b,s,fp=CFP,mpn=None):return two('C','Device:C',value,a,b,s,fp,mpn)
U1={1:'GND',2:'3V3',3:'ESP_EN',4:'PHONE_EN',5:'PHONE_FAULT_N',6:'VIN_SENSE',7:'PHONE_SENSE',12:'CC_SDA',13:'ESP_USB_DM',14:'ESP_USB_DP',17:'CC_SCL',18:'STATUS_LED',19:'PC_SUSPEND',20:'CC_INT_N',21:'INPUT_FAULT_N',27:'BOOT_N',36:'ESP_RX',37:'ESP_TX',40:'GND',41:'GND'}
comp('U1','RF_Module:ESP32-S3-WROOM-1','ESP32-S3-WROOM-1-N16R8',U1,0,at=[105,95],mpn='ESP32-S3-WROOM-1-N16R8',footprint='PhoneMCP:ESP32_S3_WROOM_1_Overhang',nc=[i for i in range(1,42) if i not in U1])
cap('22u/6.3V X7R','3V3','GND',0,'Capacitor_SMD:C_0805_2012Metric');cap('1u/10V X7R','3V3','GND',0);cap('100n/10V X7R','3V3','GND',0)
R('10k 1%','3V3','ESP_EN',0);cap('1u/10V X7R','ESP_EN','GND',0);R('10k 1%','3V3','BOOT_N',0)
comp('SW1','Switch:SW_Push','RESET',{1:'ESP_EN',2:'GND'},0,footprint='Button_Switch_SMD:SW_SPST_PTS810',mpn='PTS810 SJM 250 SMTR LFS')
comp('SW2','Switch:SW_Push','BOOT',{1:'BOOT_N',2:'GND'},0,footprint='Button_Switch_SMD:SW_SPST_PTS810',mpn='PTS810 SJM 250 SMTR LFS')
R('1k 1%','STATUS_LED','LED_K',0)
comp('D1','Device:LED','GREEN',{1:'LED_K',2:'3V3'},0,footprint='LED_SMD:LED_0603_1608Metric')
# UART logic is powered from the external 3V3 converter: VREGIN/VDD/VIO tied together.
U2={2:'GND',3:'PC_DP',4:'PC_DM',5:'3V3',6:'3V3',7:'3V3',8:'PC_VBUS_DET',9:'UART_RST_N',17:'PC_SUSPEND',19:'UART_RTS',20:'ESP_TX',21:'ESP_RX',23:'UART_DTR',25:'GND'}
comp('U2','Interface_USB:CP2102N-Axx-xQFN24','CP2102N-A02-GQFN24R',U2,1,at=[310,95],mpn='CP2102N-A02-GQFN24R',nc=[i for i in range(1,26) if i not in U2])
cap('4.7u/10V X7R','3V3','GND',1);cap('100n/10V X7R','3V3','GND',1);cap('4.7u/10V X7R','3V3','GND',1);cap('100n/10V X7R','3V3','GND',1)
R('1k 1%','3V3','UART_RST_N',1);R('22.1k 1%','VBUS_RAW','PC_VBUS_DET',1);R('47.5k 1%','PC_VBUS_DET','GND',1)
R('10k 1%','UART_DTR','Q_RESET_B',1);R('10k 1%','UART_RTS','Q_BOOT_B',1)
comp('Q1','Transistor_BJT:MMBT3904','MMBT3904',{1:'Q_RESET_B',2:'UART_RTS',3:'ESP_EN'},1,mpn='MMBT3904-7-F')
comp('Q2','Transistor_BJT:MMBT3904','MMBT3904',{1:'Q_BOOT_B',2:'UART_DTR',3:'BOOT_N'},1,mpn='MMBT3904-7-F')
# Sink-only CC controller; internal Rd, no duplicate external 5.1k resistors.
comp('U3','PhoneMCP:TUSB320LAIRWBR','TUSB320LAIRWBR',{1:'CC1',2:'CC2',3:'GND',4:'CC_VBUS_DET',5:'GND',6:'CC_INT_N',7:'CC_SDA',8:'CC_SCL',10:'GND',11:'GND',12:'3V3'},2,at=[515,95],mpn='TUSB320LAIRWBR',nc=[9])
cap('100n/10V X7R','3V3','GND',2);R('887k 1%','VBUS_RAW','CC_VBUS_DET',2)
R('4.7k 1%','3V3','CC_SDA',2);R('4.7k 1%','3V3','CC_SCL',2);R('10k 1%','3V3','CC_INT_N',2)
R('330k 1%','VBUS_RAW','VIN_SENSE',2);R('100k 1%','VIN_SENSE','GND',2);cap('100n/10V X7R','VIN_SENSE','GND',2)
R('330k 1%','PHONE_VBUS','PHONE_SENSE',2);R('100k 1%','PHONE_SENSE','GND',2);cap('100n/10V X7R','PHONE_SENSE','GND',2)
J1={p:'GND' for p in ['A1','A12','B1','B12','SH']};J1.update({p:'VBUS_RAW' for p in ['A4','A9','B4','B9']});J1.update({'A5':'CC1','B5':'CC2','A6':'PC_DP','B6':'PC_DP','A7':'PC_DM','B7':'PC_DM'})
comp('J1','Connector:USB_C_Receptacle_USB2.0_16P','USB4110-GF-A',J1,3,at=[720,95],footprint='Connector_USB:USB_C_Receptacle_GCT_USB4110',mpn='USB4110-GF-A',nc=['A8','B8'])
cap('1u/25V X7R','VBUS_RAW','GND',3);cap('100n/25V X7R','VBUS_RAW','GND',3)
comp('D2','Device:D_Zener','SMF6.0A',{1:'VBUS_RAW',2:'GND'},3,footprint='Diode_SMD:D_SMF',mpn='SMF6.0A')
# Data shunt protection; both pins of each feedthrough channel share one net.
comp('U7','Power_Protection:USBLC6-2SC6','USBLC6-2SC6',{1:'PC_DM',6:'PC_DM',3:'PC_DP',4:'PC_DP',2:'GND',5:'5V_SYS'},3,mpn='USBLC6-2SC6')
comp('U9','Power_Protection:USBLC6-2SC6','USBLC6-2SC6',{1:'CC1',6:'CC1',3:'CC2',4:'CC2',2:'GND',5:'5V_SYS'},3,mpn='USBLC6-2SC6')
# Input eFuse: programmable active-low OVLO, not a 5.7V clamp variant.
comp('U6','PhoneMCP:TPS259573DSGR','TPS259573DSGR',{3:'VBUS_RAW',4:'VBUS_RAW',2:'INPUT_OVLO',1:'INPUT_DVDT',5:'5V_SYS',6:'INPUT_FAULT_N',7:'INPUT_ILIM',8:'GND',9:'GND'},4,at=[105,350],footprint='Package_DFN_QFN:DFN-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm',mpn='TPS259573DSGR')
R('367k 0.1%','VBUS_RAW','INPUT_OVLO',4);R('100k 0.1%','INPUT_OVLO','GND',4)
R('1.62k 1%','INPUT_ILIM','GND',4);cap('10n/25V C0G','INPUT_DVDT','GND',4);R('10k 1%','3V3','INPUT_FAULT_N',4)
cap('10u/10V X7R','5V_SYS','GND',4,'Capacitor_SMD:C_0805_2012Metric');cap('100n/25V X7R','5V_SYS','GND',4)
# 3.3V buck per AP63203 typical fixed-output circuit.
comp('U4','Regulator_Switching:AP63203WU','AP63203WU-7',{1:'3V3',2:'5V_SYS',3:'5V_SYS',4:'GND',5:'BUCK_SW',6:'BUCK_BST'},5,at=[310,350],mpn='AP63203WU-7')
comp('L1','Device:L','4.7uH XGL4020',{1:'BUCK_SW',2:'3V3'},5,footprint='PhoneMCP:L_Coilcraft_XGL4020',mpn='XGL4020-472MEC')
cap('100n/25V X7R','BUCK_BST','BUCK_SW',5);cap('10u/10V X7R','5V_SYS','GND',5,'Capacitor_SMD:C_0805_2012Metric')
cap('22u/6.3V X7R','3V3','GND',5,'Capacitor_SMD:C_0805_2012Metric');cap('22u/6.3V X7R','3V3','GND',5,'Capacitor_SMD:C_0805_2012Metric');cap('100n/10V X7R','3V3','GND',5)
# Phone port: 44.2k 1% guarantees a threshold above the 500mA port load; full-load operation must be measured.
comp('U5','PhoneMCP:TPS2553DBVR','TPS2553DBVR',{1:'5V_SYS',2:'GND',3:'PHONE_EN',4:'PHONE_FAULT_N',5:'PHONE_ILIM',6:'PHONE_VBUS'},6,at=[515,350],mpn='TPS2553DBVR')
R('44.2k 1%','PHONE_ILIM','GND',6);R('10k 1%','PHONE_EN','GND',6);R('10k 1%','3V3','PHONE_FAULT_N',6)
cap('100n/25V X7R','5V_SYS','GND',6)
cap('150u/10V low-ESR','PHONE_VBUS','GND',6,'Capacitor_Tantalum_SMD:CP_EIA-7343-31_Kemet-D',mpn='T520D157M010ATE055')
cap('100n/25V X7R','PHONE_VBUS','GND',6)
# Two 22R footprint options close to ESP32 USB pins, not at external connector.
R('22R 1%','ESP_USB_DM','PHONE_DM',7);R('22R 1%','ESP_USB_DP','PHONE_DP',7)
comp('J2','Connector:USB_A','UJ2-AH-4-SMT-TR',{1:'PHONE_VBUS',2:'PHONE_DM',3:'PHONE_DP',4:'GND','SH':'GND'},7,at=[720,350],footprint='PhoneMCP:USB_A_SameSky_UJ2_AH_SMT',mpn='UJ2-AH-4-SMT-TR')
comp('U8','Power_Protection:USBLC6-2SC6','USBLC6-2SC6',{1:'PHONE_DM',6:'PHONE_DM',3:'PHONE_DP',4:'PHONE_DP',2:'GND',5:'PHONE_VBUS'},7,mpn='USBLC6-2SC6')
# Test points are exposed PCB pads, no through-hole connectors.
for i,net in enumerate(['GND','3V3','VBUS_RAW','5V_SYS','PHONE_VBUS','ESP_EN','BOOT_N','ESP_TX','ESP_RX','PHONE_EN','PHONE_FAULT_N','CC_SDA','CC_SCL','CC_INT_N','INPUT_FAULT_N','PC_SUSPEND']):
 comp('TP'+str(i+1),'Connector:TestPoint',net,{1:net},0,at=[35+i*50,550],footprint='TestPoint:TestPoint_Pad_D1.0mm')
for i,net in enumerate(['GND','VBUS_RAW','3V3']):
 comp('#FLG0'+str(i+1),'power:PWR_FLAG','PWR_FLAG',{1:net},0,at=[40+i*50,570],footprint='')
for i in range(1,5):
 comp('H'+str(i),'Mechanical:MountingHole','M2 NPTH 2.2mm',{},0,at=[35+i*45,595],footprint='MountingHole:MountingHole_2.2mm_M2')
for c in C:
 if c['ref']=='C23':c['symbol']='Device:C_Polarized'
notes=[]
for x,y,text in [(105,35,'01 ESP32-S3 / reset / status'),(310,35,'02 PC USB UART / auto download'),(515,35,'03 Type-C sink / power sensing'),(720,35,'04 PC USB-C / ESD / input'),(105,300,'05 Input eFuse / controlled inrush'),(310,300,'06 3.3V switching supply'),(515,300,'07 Phone power / default OFF'),(720,300,'08 Android USB-A / USB FS')]:notes.append({'at':[x,y],'text':text,'size':2})
notes.extend([{'at':[410,19],'text':'PRIVATE - A1 PCB REVIEW - NO MANUFACTURING RELEASE','size':2.5},{'at':[110,278],'text':'NC on unused GPIO is intentional. IO35/36/37 reserved for module PSRAM.','size':1.1},{'at':[520,278],'text':'U3 PORT=GND: UFP; ADDR=GND: 0x47; EN_N=GND; internal Rd only.','size':1.1},{'at':[310,520],'text':'AUTO RESET: DTR/RTS 00 or 11 -> EN/BOOT both high; 10 -> reset; 01 -> boot low.','size':1.1},{'at':[640,520],'text':'Firmware must verify >=1.5A source before PHONE_EN. 44.2k limit approximately 0.53-0.66A.','size':1.1}])
(root/'design.json').write_text(json.dumps({'components':C,'notes':notes},indent=2))
print(len(C),'components written')
