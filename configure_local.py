#!/usr/bin/env python3
"""Create ignored local build/client configuration. Requires adb for keygen only."""
import argparse
import getpass
import json
import os
from pathlib import Path
import secrets
import subprocess


def configure(root, ssid, password, url):
    keys = root / 'keys'
    keys.mkdir(mode=0o700, exist_ok=True)
    header = root / 'hub-probe/main'
    targets = [keys / 'network.json', header / 'network_config.h', header / 'adb_key.h']
    if any(p.exists() for p in targets):
        raise SystemExit('Local configuration already exists; back it up before reconfiguring.')
    key = keys / 's3-adb-key'
    if not key.exists():
        subprocess.run(['adb', 'keygen', str(key)], check=True)
    private = key.read_text()
    public = key.with_suffix('.pub').read_text().strip()
    token = secrets.token_hex(24)
    config = {'ssid': ssid, 'password': password, 'token': token}
    (keys / 'network.json').write_text(json.dumps(config, indent=2))
    (keys / 'mcp-token.txt').write_text(token + '\n')
    (keys / 'mcp-client.json').write_text(json.dumps({'mcpServers': {'phone-s3': {
        'url': url, 'headers': {'Authorization': 'Bearer ' + token}}}}, indent=2))
    (header / 'network_config.h').write_text('#pragma once\n' + ''.join(
        '#define ' + name + ' ' + json.dumps(value) + '\n'
        for name, value in [('PHONE_WIFI_SSID', ssid), ('PHONE_WIFI_PASSWORD', password), ('PHONE_API_TOKEN', token)]))
    (header / 'adb_key.h').write_text('#pragma once\n' +
        'static const char adb_private_key[] =\n' + ''.join(json.dumps(s + '\n') + '\n' for s in private.splitlines()) + ';\n' +
        'static const char adb_public_key[] = ' + json.dumps(public) + ';\n')
    for path in list(keys.iterdir()) + [header / 'network_config.h', header / 'adb_key.h']:
        if path.is_file():
            path.chmod(0o600)
    print('Created local configuration. Authorize the S3 identity on the phone after flashing.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://192.168.1.50/mcp', help='Board URL; update after DHCP assignment')
    args = parser.parse_args()
    os.umask(0o077)
    configure(Path(__file__).resolve().parent, input('2.4 GHz Wi-Fi SSID: '),
              getpass.getpass('Wi-Fi password: '), args.url)
