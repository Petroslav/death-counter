# Portable Windows build

Use Windows x64 and Python 3.13. In a dedicated virtual environment:

```powershell
python -m pip install -r requirements-build.txt
python -m unittest discover -v
python prepare_models.py
python -m PyInstaller --noconfirm DeathCounter.spec
```

The complete app is `dist/DeathCounter/`. Keep the EXE and `_internal` directory
together. It bundles Python, Tk, ONNX Runtime, OCR models, and the built-in death
reference. `prepare_models.py` exercises the lazy OCR stages to ensure all three
models are present before packaging. Build machines require internet; end users
do not need model downloads.

Run the packaged verification (writes a JSON result without loading user data):

```powershell
$report = Join-Path $env:TEMP 'death-counter-smoke.json'
$process = Start-Process .\dist\DeathCounter\DeathCounter.exe -ArgumentList @('--self-test', $report) -PassThru -WindowStyle Hidden
$process.WaitForExit()
Get-Content $report
```

## GitHub Actions

The Windows portable build workflow runs tests, prepares models, builds the
windowed app, and runs the packaged verification. Pushes to master, pull requests,
and manual workflow runs produce a downloadable **DeathCounter-Windows-portable**
artifact. A `v*` tag also creates a GitHub Release containing the portable ZIP.
No personal profiles, history, or screenshots are included in build artifacts.

## Updates and profiles

Packaged data is in `data/` beside the EXE, outside `_internal`. Export profiles
before an update. Replace application files while retaining data, or import the
export into a fresh installation. Restart launches the packaged EXE directly.
Unsigned local builds are not code-signed; signing can be added to the release
workflow later.

References: [PyInstaller options](https://pyinstaller.org/en/stable/usage.html),
[GitHub workflow triggers](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).
