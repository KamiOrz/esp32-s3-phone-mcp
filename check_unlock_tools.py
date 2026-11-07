import asyncio,base64,json,pathlib
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client,httpx2
from png_check import validate_png
P=pathlib.Path(__file__).resolve().parent
async def main():
 c=json.loads((P/'keys/network.json').read_text())
 async with httpx2.AsyncClient(headers={'Authorization':'Bearer '+c['token']},timeout=60,trust_env=False) as h:
  async with streamable_http_client('http://192.168.2.110/mcp',http_client=h) as (r,w):
   async with ClientSession(r,w) as s:
    init=await s.initialize();assert init.server_info.version=='0.3.0';print('MCP',init.server_info.version,flush=True)
    tools=await s.list_tools();assert {'phone_wake_screen','phone_input_password'}<={t.name for t in tools.tools};print('Unlock tools registered',flush=True)
    for args in [{},{'password':'not-a-pin'},{'password':'123','submit':True}]:
     result=await s.call_tool('phone_input_password',args);assert result.is_error
    print('Invalid/missing PIN rejected; no PIN attempts made',flush=True)
    result=await s.call_tool('phone_wake_screen',{});assert not result.is_error;print('Wake command delivered',flush=True)
    result=await s.call_tool('phone_screenshot',{});assert not result.is_error
    for v in result.content:
     if v.type=='image':
      b=base64.b64decode(v.data,validate=True);print('PNG verified',validate_png(b),flush=True);(P/'output/unlock-before.png').write_bytes(b)
asyncio.run(main())
