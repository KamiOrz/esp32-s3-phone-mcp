import asyncio,base64,json,pathlib,time,xml.etree.ElementTree as ET
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client,httpx2
from png_check import validate_png
P=pathlib.Path(__file__).resolve().parent
async def main():
 c=json.loads((P/'keys/network.json').read_text());out=P/'output/commands';out.mkdir(parents=True,exist_ok=True)
 async with httpx2.AsyncClient(headers={'Authorization':'Bearer '+c['token']},timeout=90,trust_env=False) as h:
  async with streamable_http_client('http://192.168.2.110/mcp',http_client=h) as (read,write):
   async with ClientSession(read,write) as s:
    init=await s.initialize();assert init.server_info.version=='0.4.0';print('MCP',init.server_info.version,flush=True)
    tools=await s.list_tools();print('Tools:',len(tools.tools),', '.join(t.name for t in tools.tools),flush=True)
    async def call(name,args,expect=0):
     t=time.monotonic();r=await s.call_tool(name,args);data=r.structured_content
     if data:
      assert data['exit_code']==expect,(name,r)
      assert r.is_error==(expect!=0),(name,r)
      print(name,{'exit_code':data['exit_code'],'seconds':round(time.monotonic()-t,3),'truncated':data['truncated'],'bytes':data['bytes_received'],'preview':data['output'][:350]},flush=True)
     else:assert not r.is_error,(name,r)
     return r,data
    await call('phone_device_info',{})
    r,d=await call('phone_adb_shell',{'command':"printf '%s\\n' \"quote's & dollar \\$\"; id"});assert "quote's & dollar $" in d['output']
    await call('phone_adb_shell',{'command':'exit 7'},expect=7)
    await call('phone_adb_shell',{'command':'sleep 3','timeout_seconds':1},expect=124)
    r,d=await call('phone_adb_shell',{'command':'seq 1 10000'});assert d['truncated'] and d['exit_code_known'];(out/'truncation-metadata.json').write_text(json.dumps({k:v for k,v in d.items() if k!='output'},indent=2))
    for n,a in [('phone_launch_app',{'package':'com.example; echo injected'}),('phone_stop_app',{'package':'-a'}),('phone_input_text',{'text':'中文'}),('phone_adb_shell',{'command':'echo no','timeout_seconds':0})]:
     r=await s.call_tool(n,a);assert r.is_error;print('Rejected invalid arguments:',n,flush=True)
    r,calc=await call('phone_list_apps',{'filter':'calculator'});packages=[x.removeprefix('package:').strip() for x in calc['output'].splitlines() if x.startswith('package:')];assert packages;calculator=packages[0]
    r,dy=await call('phone_list_apps',{'filter':'aweme'});packages=[x.removeprefix('package:').strip() for x in dy['output'].splitlines() if x.startswith('package:')];assert packages;douyin=next((x for x in packages if x=='com.ss.android.ugc.aweme'),packages[0])
    await call('phone_app_info',{'package':calculator})
    await call('phone_launch_app',{'package':calculator})
    r,d=await call('phone_foreground_app',{});assert calculator in d['output']
    if 'u0 com.android.systemui}' in d['output']:
     result=await s.call_tool('phone_press_key',{'key':'BACK'});assert not result.is_error
    r,d=await call('phone_ui_hierarchy',{});xml=d['output'].strip();start=xml.find('<?xml');xml=xml[start:] if start>=0 else xml[xml.find('<hierarchy'):];ET.fromstring(xml);(out/'calculator-ui.xml').write_text(xml)
    r=await s.call_tool('phone_screenshot',{});assert not r.is_error
    for v in r.content:
     if v.type=='image':b=base64.b64decode(v.data);validate_png(b);(out/'calculator.png').write_bytes(b)
    await call('phone_stop_app',{'package':calculator})
    await call('phone_launch_app',{'package':douyin})
    r,d=await call('phone_foreground_app',{});assert douyin in d['output']
    (out/'apps.json').write_text(json.dumps({'calculator':calculator,'douyin':douyin},indent=2));print('COMMAND TOOLS TEST PASSED',flush=True)
asyncio.run(main())
