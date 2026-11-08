"""kicad-tool project-build entry for controlled native board operations."""
import subprocess,sys
from pathlib import Path
native='/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3.9'
raise SystemExit(subprocess.run([native,str(Path(__file__).with_name('native_finish.py')),*sys.argv[1:]]).returncode)
