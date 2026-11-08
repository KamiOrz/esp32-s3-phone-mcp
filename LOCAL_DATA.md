# Local data and credentials

The project is open source under the root MIT LICENSE. Vendored components retain their own licenses.

Wi-Fi credentials, MCP tokens, ADB private keys, phone PINs, runtime logs and phone screenshots are local data and must not be committed. `configure_local.py` creates a distinct ADB identity and ignored configuration for each device.

Only the explicitly supplied product demonstration photo is included in `docs/images/`; its EXIF/XMP/IPTC metadata has been removed. Do not add other phone captures without checking their contents.
