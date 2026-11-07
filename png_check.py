import struct,zlib
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

