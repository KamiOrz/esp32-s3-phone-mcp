#!/usr/bin/env python3
"""Standard MCP-over-HTTP client for the ESP32-S3 phone server."""
import argparse,asyncio,base64,json,pathlib,time
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client,httpx2
from png_check import validate_png
ROOT=pathlib.Path(__file__).resolve().parent
async def run(args):
    config=json.loads((ROOT/'keys/network.json').read_text())
    url=args.url
    async with httpx2.AsyncClient(headers={'Authorization':'Bearer '+config['token']},timeout=60,trust_env=False) as http:
        async with streamable_http_client(url,http_client=http) as (read,write):
            async with ClientSession(read,write) as session:
                init=await session.initialize();print('MCP initialized:',init.server_info.name,init.server_info.version,init.protocol_version,flush=True)
                tools=await session.list_tools();print('Tools:',', '.join(t.name for t in tools.tools),flush=True)
                result=await session.call_tool('phone_status',{});print('Status:',result.content,flush=True)
                if args.status_only:return
                start=time.monotonic();result=await session.call_tool('phone_screenshot',{});elapsed=time.monotonic()-start
                if result.is_error:raise RuntimeError(str(result.content))
                image=next(c for c in result.content if c.type=='image');data=base64.b64decode(image.data,validate=True)
                dims=validate_png(data);out=ROOT/'output/wifi';out.mkdir(parents=True,exist_ok=True);(out/'phone-screen.png').write_bytes(data)
                meta=[c.text for c in result.content if c.type=='text'];metrics={'total_seconds':elapsed,'bytes':len(data),'width':dims[0],'height':dims[1],'metadata':meta}
                print('Screenshot:',json.dumps(metrics),flush=True);(out/'metrics.json').write_text(json.dumps(metrics,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',default='http://192.168.2.110/mcp');p.add_argument('--status-only',action='store_true');asyncio.run(run(p.parse_args()))
