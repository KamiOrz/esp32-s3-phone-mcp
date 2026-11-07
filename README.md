# ESP32-S3 phone MCP over Wi-Fi

An ESP32-S3 controls one Android phone over USB ADB, independently of the computer's ADB installation. The S3 exposes an authenticated MCP Streamable HTTP endpoint over 2.4 GHz Wi-Fi. The computer is an MCP client. The calling multimodal AI interprets the screenshot and selects actions directly.

## Current hardware / wiring

- YD-ESP32-23 2022-V1.3, ESP32-S3 revision 0.2, 16 MB flash, embedded 8 MB octal PSRAM.
- COM connector: power, UART logs and flashing. `/dev/cu.usbserial-A5069RR4`, 115200 baud for logs.
- Native USB connector: USB Hub upstream; Hub USB-A downstream to Android phone through an A-to-C data cable.
- USB-OTG solder jumper was bridged by the user to supply VBUS. This changes power routing: do not directly attach another USB power source to the native port. Board-specific CC/VBUS wiring matters.
- Android USB debugging must be enabled. No APK or helper application is installed on the phone.

## MCP connection

Current DHCP address: **http://192.168.2.110/mcp** (may change after network changes).

The endpoint requires `Authorization: Bearer <token>`. Local configuration containing the token is in `keys/mcp-client.json`; the token alone is in `keys/mcp-token.txt`. These files and network credentials are ignored by Git. `network_config.h` contains build-time Wi-Fi credentials/token and is also ignored.

Implemented tools (MCP 0.4.0):

| Tool | Arguments | Result |
|---|---|---|
| `phone_status` | none | Network and USB ADB connection state |
| `phone_screenshot` | none | Fresh PNG as MCP image content, plus USB acquisition timing |
| `phone_tap` | integer `x`, `y` | Tap at original screenshot pixel coordinates |
| `phone_swipe` | integer `x1`, `y1`, `x2`, `y2`, `duration_ms` | Swipe |
| `phone_press_key` | `key`: BACK, HOME, ENTER, APP_SWITCH | Navigation key |
| `phone_wake_screen` | none | Wake without toggling power |
| `phone_input_password` | numeric `password`, optional `submit` | Enter known PIN; no automatic retry |
| `phone_adb_shell` | `command`, optional `timeout_seconds` | Android shell, exit code and bounded text output |
| `phone_list_apps` | optional `filter`, `kind` | Installed package IDs |
| `phone_launch_app` | `package`, optional `activity` | Resolve and launch Activity directly |
| `phone_stop_app` | `package` | Force-stop process; does not clear data |
| `phone_app_info` | `package` | APK path/version/install metadata |
| `phone_foreground_app` | none | Resumed Activity and focused window |
| `phone_device_info` | none | Android version, display, battery |
| `phone_ui_hierarchy` | none | UI XML including text/resource IDs/bounds |
| `phone_open_url` | `url` | ACTION_VIEW URL/deep link |
| `phone_input_text` | printable ASCII `text` | Input into focused field; no submission |
| `phone_keyevent` | numeric `code`, optional `longpress` | General Android keycode |
| `phone_long_press` | `x`, `y`, optional `duration_ms` | Long-press |

Protocol version: 2025-06-18. Stateless JSON responses over Streamable HTTP; POST `/mcp`, GET `/mcp` returns 405 (no server SSE stream). Standard Python MCP client initialization and tool discovery were tested. Browser Origin headers are rejected. No session identifier is issued. Only one operation is executed at a time. The prototype uses local HTTP, not TLS.

## Run the visual AI client

```sh
cd /Volumes/Data/codes/hacker/work/phone-mcp-s3
.venv/bin/python wifi_client.py --url http://192.168.2.110/mcp --status-only
.venv/bin/python wifi_client.py --url http://192.168.2.110/mcp
```

The client loads the token locally, captures a fresh screenshot via MCP, validates the PNG signature, every chunk CRC and its ending, and saves the PNG and timings under `output/wifi/`. The MCP screenshot tool returns image content directly to a multimodal AI. The AI locates targets in the original screenshot pixels and invokes control tools, then captures a new screenshot to verify the result. The client has no OCR option, OCR HTTP request, or dependency on an OCR service. Historical OCR experiment outputs are retained only as previous test artifacts.

## Firmware architecture

`hub-probe/` is a native ESP-IDF 6.1 project using locally vendored Espressif USB Host 1.6.0 and cJSON. External and multilevel hubs are enabled. The USB client and RSA authentication run on S3. A dedicated key is embedded via ignored `main/adb_key.h`; it is not the computer's ordinary ADB identity. This phone accepted CNXN directly in the observed sessions, so the RSA signature challenge path has not been exercised on this phone.

ADB runs in its own owner loop; HTTP requests queue commands to it. Screenshots use `exec:screencap -p`, are accumulated in a 6 MiB PSRAM buffer, and are sent as MCP image data over Wi-Fi. Screenshot bytes never pass through the UART. The original serial experiment remains available in `serial_capture.py` and the saved source snapshots.

Short idle keepalive commands maintain the observed phone connection; their output is isolated from screenshot buffers. A pending outbound packet is retained when another USB transmission is busy. Command strings can occupy up to 4096 bytes including the ADB service prefix; generic raw shell input is limited to 768 UTF-8 bytes. A USB transfer error/disconnection triggers a board restart after two seconds to recover. Wi-Fi starts after initial USB enumeration and disables Wi-Fi power saving. This is a bring-up implementation, not a multi-phone server.

## Build and flash

This is a private repository; see `PRIVATE.md`. Runtime captures, logs, downloaded
hardware reference files and local source snapshots mentioned below are not included.

On a fresh checkout, install Android platform-tools for **local key generation only**,
then run `python3 configure_local.py --url http://BOARD_IP/mcp`. It prompts for Wi-Fi
credentials and creates a dedicated ADB identity, token and ignored configuration
headers. It refuses to overwrite existing configuration. No phone PIN is stored.
The computer does not need adb for normal MCP operation.

Install ESP-IDF 6.1 with ESP32-S3 support and source its `export.sh`, then build
with the command below. Client dependencies are pinned in
`client-requirements.lock.txt` (captured on Python 3.14).


```sh
bash hub-probe/build.sh -p /dev/cu.usbserial-A5069RR4 -b 460800 build flash
```

The wrapper currently uses the existing ESP-IDF/toolchain under `../xiaozhi-s3`. SDK configuration enables 8 MB octal PSRAM at 80 MHz and CPU at 240 MHz. Original Arduino/PlatformIO v1 probe is historical; use the native IDF project for the Wi-Fi firmware.

## Limits

- Screenshot PNG limit: 6 MiB. Phone must permit screenshot capture; protected content can be unavailable.
- ADB payloads are negotiated at 4096 bytes. This is not continuous video streaming.
- A request waits up to 45 seconds for ADB completion. An operation timeout schedules automatic board recovery; the network connection will temporarily drop.
- Current coordinates are original screen pixels; no rotation/scaling abstraction or stale-frame checking yet.
- Shell commands execute with the existing Android ADB-shell permissions; the firmware does not automatically request root. Unicode text entry is not implemented. Binary output, APK upload/install transport, and interactive shell sessions are not implemented.
- Inspect `wifi-test.log`, `wifi-tools-test.log`, and `output/wifi/*metrics.json` for measured integration results. Original 115200-baud serial capture took 36.1 seconds for a 294650-byte screenshot; compare timings with image size/content in mind.

## Known-PIN lock-screen test (MCP 0.3.0)

- `phone_wake_screen {}` sends Android KEYCODE_WAKEUP (224), without toggling power or claiming to unlock.
- `phone_input_password {"password":"<known numeric PIN>","submit":false}` accepts 4–16 decimal digits. Default submit is false. With submit=true it also presses Enter.
- First inspect the lock screen and use a swipe to reveal/focus its PIN field. Only submit a known correct PIN once, then inspect a fresh screenshot. A delivery acknowledgment is not proof of successful unlock.
- The device firmware does not persist or echo the PIN. It clears parsed PIN text, HTTP body and temporary command/transfer buffers after use. Calling clients must also avoid logging tool arguments. Runtime values still pass through RAM and the existing authenticated LAN HTTP transport.
- This is input simulation via an already-authorized ADB connection, not a credential-bypass API. Pattern locks and nonnumeric passwords are not supported by this tool version.

Validated on the connected OnePlus 9R: wake -> swipe to credential entry -> one input/submission of the user-provided correct PIN -> fresh screenshot showing the launcher. PNG completeness was verified. The PIN-entry screen itself returned no PNG; this did not prevent the authorized ADB input command. Evidence images are output/unlock-before.png (lock screen) and output/unlock-after.png (launcher). No valid PIN value is stored in project files or test logs.


## Command-line application control (0.4.0)

Run from `/Volumes/Data/codes/hacker/work/phone-mcp-s3`:

```sh
# Discover tools / apps
.venv/bin/python phone_cli.py --list
.venv/bin/python phone_cli.py phone_list_apps --args '{"filter":"aweme"}'

# Launch directly; S3 resolves the launchable Activity first
.venv/bin/python phone_cli.py phone_launch_app --args '{"package":"com.ss.android.ugc.aweme"}'
.venv/bin/python phone_cli.py phone_foreground_app

# Read visible controls, text and bounds
.venv/bin/python phone_cli.py phone_ui_hierarchy

# Run Android shell commands through S3 (not the computer adb binary)
.venv/bin/python phone_cli.py phone_adb_shell --args '{"command":"getprop ro.product.model; wm size"}'
.venv/bin/python phone_cli.py phone_adb_shell --args '{"command":"dumpsys battery","timeout_seconds":10}'

# Printable ASCII only; call when a text field is focused
.venv/bin/python phone_cli.py phone_input_text --args '{"text":"hello world"}'

# Example numeric keycode: HOME
.venv/bin/python phone_cli.py phone_keyevent --args '{"code":3}'
```

`phone_cli.py` reads the local access token. It does not log tool arguments. For known PIN entry from your own terminal use `phone_input_password --pin --args '{"submit":true}'`; the PIN is requested using getpass rather than placed in the process command line. Check/focus the PIN field before input and never retry unknown credentials.

Shell tools return `structuredContent` with `output` (combined stdout/stderr), `exit_code`, `exit_code_known`, `truncated`, `bytes_received` and `elapsed_ms`. `isError` is set on nonzero/unknown exit codes. Timeout exits with 124 on this phone. Generic shell defaults to 15 seconds and permits 1–30 seconds; UI hierarchy has a 25-second limit. Output storage is 32 KiB including its terminating NUL. Excess output is drained, marked truncated, and the trailing exit status is retained separately. Use filters or bounded commands to retrieve the part you need. Shell commands should return text, not binary data.

Structured tools validate package/Activity names and shell-quote URLs/text. The generic shell tool intentionally accepts shell syntax under the authenticated user's authority. Do not use it for destructive operations or external actions beyond what the user requested. Current local transport remains HTTP; do not publish it to the public Internet.

The tested launcher IDs are `com.coloros.calculator` and `com.ss.android.ugc.aweme`. This phone's calculator does not resolve an implicit `am start -p` launch; the tool queries `cmd package resolve-activity` then launches the explicit component. It also detects Android's textual launch errors even when am returns 0. Foreground inspection combines activity and window dumps for OEM compatibility.

Validation: `check_command_tools.py` tested shell quoting, nonzero exit 7, timeout 124, 48908-byte output truncation with preserved exit status, malformed argument rejection, package discovery, app metadata, direct calculator launch, UI hierarchy XML parsing, screenshot PNG CRC validation, calculator force-stop, direct Douyin cold launch, and foreground verification. Results: `command-tools-test.log` and `output/commands/`. UI hierarchy was verified after dismissing this phone's USB-use dialog; custom-drawn apps can expose incomplete trees, so screenshots remain the fallback. No APK was installed.
