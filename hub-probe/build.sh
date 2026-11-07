#!/bin/bash
set -e
cd "$(dirname "$0")"
# Prefer a standard ESP-IDF environment initialized by export.sh.
if command -v idf.py >/dev/null 2>&1; then
    exec idf.py "$@"
fi
# Preserve the original workstation's adjacent SDK as an optional fallback.
local_sdk="$(cd ../.. && pwd)/xiaozhi-s3"
if [ -d "$local_sdk/esp-idf" ] && [ -d "$local_sdk/idf-tools" ]; then
    export ESP_IDF_VERSION=6.1.0
    export IDF_PATH="$local_sdk/esp-idf"
    export IDF_TOOLS_PATH="$local_sdk/idf-tools"
    export IDF_PYTHON_ENV_PATH="$IDF_TOOLS_PATH/python_env/idf6.1_py3.12_env"
    export PATH="$IDF_PYTHON_ENV_PATH/bin:$IDF_TOOLS_PATH/tools/xtensa-esp-elf/esp-15.2.0_20251204/xtensa-esp-elf/bin:$IDF_PATH/tools:$PATH"
    exec python "$IDF_PATH/tools/idf.py" "$@"
fi
printf '%s\n' 'Source the ESP-IDF 6.1 export.sh before running this script.' >&2
exit 1
