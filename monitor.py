import serial,time,pathlib
s=serial.Serial(port=None,baudrate=115200,timeout=.3);s.dtr=False;s.rts=False;s.port='/dev/cu.usbserial-A5069RR4';s.open();s.reset_input_buffer();s.rts=True;time.sleep(.1);s.rts=False
end=time.monotonic()+150
with pathlib.Path(__file__).with_name('wifi-live.log').open('w') as f:
 while time.monotonic()<end:
  t=s.readline().decode('utf-8','replace');f.write(t);f.flush()
  if any(k in t for k in ['MCP_URL','ADB_','STATUS','USB_DEVICE','RESTART','WIFI_DISCONNECTED','PHONE_WIFI','ERROR']):print(t.strip(),flush=True)
s.close()
