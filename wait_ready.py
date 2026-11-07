import json,time,urllib.request
from pathlib import Path
c=json.loads(Path(__file__).with_name('keys').joinpath('network.json').read_text())
for _ in range(40):
 try:
  r=urllib.request.Request('http://192.168.2.110/health',headers={'Authorization':'Bearer '+c['token']})
  v=json.load(urllib.request.urlopen(r,timeout=1))
  if v.get('adb_connected'):print(v);break
 except Exception:pass
 time.sleep(.5)
else:raise SystemExit('Not ready')
