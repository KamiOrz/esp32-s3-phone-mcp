#!/usr/bin/env python3
"""Call the S3 phone MCP from a terminal; no host adb or OCR dependency."""
import argparse,asyncio,base64,getpass,json,pathlib
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client,httpx2
from png_check import validate_png
ROOT=pathlib.Path(__file__).resolve().parent
async def main(args):
    config=json.loads((ROOT/'keys/network.json').read_text())
    arguments=json.loads(args.args)
    if not isinstance(arguments,dict):raise ValueError('--args must be a JSON object')
    if args.pin:
        if args.tool!='phone_input_password':raise ValueError('--pin is only for phone_input_password')
        arguments['password']=getpass.getpass('Known numeric PIN: ')
    async with httpx2.AsyncClient(headers={'Authorization':'Bearer '+config['token']},timeout=90,trust_env=False) as http:
        async with streamable_http_client(args.url,http_client=http) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize()
                if args.list:
                    tools=await session.list_tools()
                    for tool in tools.tools:print(tool.name+'\t'+(tool.description or ''))
                    return
                result=await session.call_tool(args.tool,arguments)
                arguments.clear()
                if result.structured_content is not None:print(json.dumps(result.structured_content,ensure_ascii=False,indent=2))
                else:
                    for content in result.content:
                        if content.type=='text':print(content.text)
                        elif content.type=='image':
                            data=base64.b64decode(content.data,validate=True);dimensions=validate_png(data)
                            output=pathlib.Path(args.output);output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(data)
                            print(f'PNG {dimensions[0]}x{dimensions[1]} saved to {output.resolve()}')
                return 1 if result.is_error else 0
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('tool',nargs='?',default='phone_status');parser.add_argument('--args',default='{}');parser.add_argument('--url',default='http://192.168.2.110/mcp');parser.add_argument('--list',action='store_true');parser.add_argument('--pin',action='store_true');parser.add_argument('--output',default=str(ROOT/'output/cli-screen.png'))
    raise SystemExit(asyncio.run(main(parser.parse_args())))
