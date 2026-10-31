# Product roadmap

Implemented: independent game profiles, ZIP export/import with screenshots,
red-symbol reference uploads, legacy configuration backup, portable windowed
Windows build, and GitHub Actions build verification.

Remaining: support non-red death indicators, profile rename/delete controls,
code signing, and additional real-game validation.

## Separate game profiles

- Create, rename, and switch profiles in the app.
- Import a death-screen screenshot for each game and preview/test detection.
- Store each profile's reference, detection settings, display selection, boss area,
  name corrections, death totals, timestamps, and screenshots independently.
- Switching profiles stops capture, clears rolling buffers, and loads the selected
  profile before capture resumes. No frames or boss names carry across games.
- Migrate existing counter.json and screenshot history into the first profile
  without resetting counts or losing images. Back up legacy data before migration.
- Use stable profile IDs for folders; renaming a profile never moves or discards data.
- Keep personal profiles, screenshots, and imported references out of source control.

## Portable Windows release

- Build a windowed executable with bundled OCR models and detection assets.
- No Python installation, installer, console window, or first-run model download.
- Preserve user data outside bundled files across updates and restarts.
- GitHub Actions runs tests and builds a portable ZIP for tagged releases.

The lists above describe the intended profile and release behavior. The current
reference matcher supports red symbols; arbitrary death screens are not yet supported.
