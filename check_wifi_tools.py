import asyncio,base64,json,pathlib,time
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client,httpx2
from png_check import validate_png
P=pathlib.Path(__file__).resolve().parent
async def main():
 c=json.loads((P/'keys/network.json').read_text());url='http://192.168.2.110/mcp'
 async with httpx2.AsyncClient(timeout=60,trust_env=False) as h:
  r=await h.post(url,json={'jsonrpc':'2.0','id':1,'method':'ping'});assert r.status_code==401;print('Missing token rejected: 401')
  r=await h.post(url,headers={'Authorization':'Bearer '+c['token'],'Origin':'http://example.invalid'},json={'jsonrpc':'2.0','id':1,'method':'ping'});assert r.status_code==403;print('Browser origin rejected: 403')
 async with httpx2.AsyncClient(headers={'Authorization':'Bearer '+c['token']},timeout=60,trust_env=False) as h:
  async with streamable_http_client(url,http_client=h) as (read,write):
   async with ClientSession(read,write) as s:
    await s.initialize()
    invalid=await s.call_tool('phone_tap',{'x':-1,'y':0});assert invalid.is_error;print('Invalid tap rejected without phone operation')
    back=await s.call_tool('phone_press_key',{'key':'BACK'});assert not back.is_error;print('BACK result:',back.content)
    results=[]
    for i in range(3):
     t=time.monotonic();r=await s.call_tool('phone_screenshot',{});elapsed=time.monotonic()-t;assert not r.is_error
     image=next(v for v in r.content if v.type=='image');data=base64.b64decode(image.data,validate=True);dims=validate_png(data)
     (P/f'output/wifi/repeat-{i+1}.png').write_bytes(data)
     m={'seconds':elapsed,'bytes':len(data),'dimensions':dims,'metadata':[v.text for v in r.content if v.type=='text']};results.append(m);print(m,flush=True)
    (P/'output/wifi/repeat-metrics.json').write_text(json.dumps(results,indent=2))
asyncio.run(main())
