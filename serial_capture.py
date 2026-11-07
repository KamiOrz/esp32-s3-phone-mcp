#!/usr/bin/env python3
"""Receive a screenshot acquired by S3's own ADB client over UART."""
import argparse,base64,json,pathlib,re,struct,time,zlib
import serial

def validate_png(data):
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('Phone response is not a PNG')
    off=8;dims=None;ended=False
    while off+12<=len(data):
        n=struct.unpack('>I',data[off:off+4])[0];end=off+12+n
        if end>len(data):raise ValueError('Truncated PNG chunk')
        kind=data[off+4:off+8];body=data[off+8:off+8+n]
        crc=struct.unpack('>I',data[off+8+n:end])[0]
        if zlib.crc32(kind+body)&0xffffffff!=crc:raise ValueError('PNG CRC mismatch')
        if kind==b'IHDR':dims=struct.unpack('>II',body[:8])
        off=end
        if kind==b'IEND':ended=True;break
    if not ended or off!=len(data) or not dims:raise ValueError('Invalid PNG ending')
    return dims

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--port',default='/dev/cu.usbserial-A5069RR4');ap.add_argument('--output',default=str(pathlib.Path(__file__).resolve().parent/'output'));ap.add_argument('--timeout',type=int,default=300);args=ap.parse_args()
    out=pathlib.Path(args.output);out.mkdir(parents=True,exist_ok=True)
    ser=serial.Serial(port=None,baudrate=115200,timeout=.5);ser.dtr=False;ser.rts=False;ser.port=args.port;ser.open()
    ser.reset_input_buffer();ser.rts=True;time.sleep(.15);ser.rts=False
    chunks=[];active=False;complete=False;deadline=time.monotonic()+args.timeout;start=time.monotonic();last=start
    with (out/'capture.log').open('w') as log:
        while time.monotonic()<deadline:
            raw=ser.readline();line=raw.decode('ascii','replace').strip()
            if not line:continue
            if line.startswith('@PNG '):
                if not active:raise ValueError('Data before screenshot start')
                chunks.append(base64.b64decode(line[5:],validate=True))
                if time.monotonic()-last>10:
                    print(f'Received {sum(map(len,chunks))} screenshot bytes',flush=True);last=time.monotonic()
                continue
            log.write(line+'\n');log.flush()
            if line=='@PNG_BEGIN':active=True;chunks=[]
            elif line.startswith('@PNG_END '):
                expected=int(re.search(r'bytes=(\d+)',line).group(1));data=b''.join(chunks)
                if len(data)!=expected:raise ValueError(f'Transfer length mismatch: {len(data)} != {expected}')
                complete=True;break
            elif any(x in line for x in ('ADB_', 'USB_DEVICE', 'SCREENSHOT_', 'S3_', 'STATUS', 'PHONE_')):print(line,flush=True)
    ser.close()
    if not complete:raise TimeoutError('S3 did not complete screenshot')
    dims=validate_png(data);(out/'phone-screen.png').write_bytes(data)
    print(f'PNG verified: {dims[0]}x{dims[1]}, {len(data)} bytes, {time.monotonic()-start:.1f}s',flush=True)
if __name__=='__main__':main()
