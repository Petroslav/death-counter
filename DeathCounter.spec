from PyInstaller.utils.hooks import collect_all
import os
import sys
from pathlib import Path

for variable, folder in [('TCL_LIBRARY', 'tcl8.6'), ('TK_LIBRARY', 'tk8.6')]:
    library = Path(sys.base_prefix) / 'tcl' / folder
    if library.is_dir():
        os.environ.setdefault(variable, str(library))

datas = [('assets', 'assets')]
binaries = []
hiddenimports = []
for package in ('rapidocr', 'onnxruntime'):
    data, binary, hidden = collect_all(package)
    datas += data
    binaries += binary
    hiddenimports += hidden

a = Analysis(['app.py'], pathex=[], binaries=binaries, datas=datas,
             hiddenimports=hiddenimports, hookspath=[], hooksconfig={},
             runtime_hooks=[], excludes=['torch', 'paddle', 'openvino', 'tensorrt'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='DeathCounter',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='DeathCounter')
