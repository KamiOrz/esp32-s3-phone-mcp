"""kicad-tool entry point for the native KiCad PCB structural API."""
import subprocess,sys
from pathlib import Path
native='/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3.9'
raise SystemExit(subprocess.run([native,str(Path(__file__).with_name('native_board.py')),*sys.argv[1:]]).returncode)
