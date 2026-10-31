# Death Counter

Windows desktop counter. Press **F8 when you die**; **F9** undoes the last death.
OCR reads a selected boss-name area locally. A name must appear in at least two
captures within the ten seconds before death detection or the hotkey to receive the death.
If live OCR has no confirmed name, the app scans up to 12 buffered snapshots from
the preceding ten seconds, newest first, and updates the death when two readings
agree. Lookup runs in the background. This may attribute a death to a boss seen
within that window even if you have just left the fight.
Otherwise the death goes to **Enemy/environment death**.

## Automatic death detection

The app searches the whole selected monitor using the supplied built-in death-symbol
reference, at multiple positions and sizes. No death-screen calibration is needed.
Enable **Automatically count deaths** to start. Extra black margins are fine.
A match must persist for 0.25 seconds; the symbol must clear for two seconds
before the next death can count. F8 adds missed deaths and F9 undoes mistakes.
Manual/automatic counts within two seconds are deduplicated. Other windows showing
the same reference image can also trigger detection: close them before playing.
Actual gameplay accuracy still needs validation.

## Screenshot death log

Click **Death log / screenshots** to browse deaths and view both timestamped images
side by side inside the app. Select an entry or use **Previous** / **Next**;
**Refresh log** loads new entries. A short selected-monitor screenshot buffer runs in memory at
roughly four frames per second. Only counted deaths write screenshots to
`death_logs/`: the closest available frame 1–2 seconds before detection (target
1.5 seconds), and a fresh capture when the death is recorded. Timestamps include
the local UTC offset and milliseconds. No before image is substituted if none
exists in that interval. The log includes manual F8 deaths too; for those, timing
is relative to the key press, so press while the death screen is visible.

Captures cover the whole selected monitor, including any visible desktop windows.
Images stay local. Undo removes the counted entry but preserves its files on disk.
Existing deaths have no retroactive screenshots. Screenshots accumulate until you
remove their folders manually. The log window is a snapshot; reopen it to refresh.

## Launch

Double-click `start.bat`. Requires Python 3.13 (Python Launcher `py`). The first
launch installs dependencies into `.venv`; OCR may download its model files.
Boss OCR captures are processed in memory; death-log screenshots are saved locally.

1. Use borderless/windowed gameplay and choose the game display from the dropdown.
2. Click **Select boss-name screen area** and select the area where boss names
   appear. The boss need not be active; avoid unrelated interface text.
3. Return to the game. Automatic detection counts deaths; F8 covers missed deaths.
4. Select a category and enter the correct name to merge/rename OCR mistakes.

Totals, death timestamps, aliases, and the capture region persist in `counter.json`.
Undo removes the latest death across sessions. Back up that JSON to keep a copy.
Selecting a new area clears recent detections. Moving the HUD or changing resolution
requires selecting the area again. Arbitrary text in the selected area can be mistaken
for a name; verify with actual gameplay. F8/F9 must be available to register globally.

Use **F7** during a death screen, then **Detection check**, to inspect the captured
image and match score. **Restart app** reloads code and saved settings.

## Game profiles and portable version

The profile dropdown switches games by restarting capture. **New game** creates a
separate profile. Each profile owns its names, counts, screenshots, display, boss
area, and optional uploaded red death-screen reference. New profiles start with
automatic counting disabled. The current detector supports red death symbols;
arbitrary colors or animated screens may require a different detector.

Your existing source installation keeps using the original `counter.json` and
image paths as the **Phantom Blade Zero** profile. First profile startup creates
`counter.before-profiles.json` once. No image folders are moved or removed.

**Export** writes a ZIP with that profile's settings, death history, available
screenshots, and custom reference. **Import** creates an independent copy with a
new profile ID, never overwriting another game. Export after finishing a session
to include the newest deaths. Missing screenshots are reported during export.

The portable ZIP contains `DeathCounter.exe` and `_internal/`. Extract the entire
folder to a writable location and double-click the EXE. No installer, Python, or
console window is needed. Its user data lives in `data/` next to the EXE. Keep
that folder when updating. Source and EXE data locations are intentionally
separate: to move current progress, export from the source app, close it, then
import the ZIP inside the EXE. Do not run both counters during gameplay.

See [BUILDING.md](BUILDING.md) for local builds and GitHub Actions.
