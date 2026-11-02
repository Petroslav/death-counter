# Death Counter

Windows desktop counter. Press **F8 when you die**; **F9** undoes the last death.
After a death, OCR reads a selected boss-name area locally. A name must appear in at least two
captures within the ten seconds before death detection or the hotkey to receive the death.
The app scans buffered snapshots from
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
roughly one frame per second. Only counted deaths write screenshots to
`death_logs/`: the closest available frame 1–2 seconds before detection (target
1.5 seconds), and a fresh capture when the death is recorded. If timing jitter
leaves no frame in the preferred interval, the nearest earlier frame between
0.25 and 10 seconds old is saved instead, with its actual age shown in the log.
Timestamps include the local UTC offset and milliseconds. Buffer age diagnostics
and a missing-image reason are stored with new deaths. The log includes manual F8 deaths too; for those, timing
is relative to the key press, so press while the death screen is visible.

Captures cover the whole selected monitor, including any visible desktop windows.
Images stay local. Undo removes the counted entry but preserves its files on disk.
Buffered before images and saved death-screen images retain full resolution.
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

## Correcting deaths in the app

- **Mark selected fight killed**: select a boss row after winning. The row gets
  `[Killed]`, and future deaths to the same name start `Rematch 1`, `Rematch 2`,
  etc. Marking a victory does not increase the death total. No automatic win-screen
  detection is used; short win animations can be missed at 1 FPS.
- **Remove killed tag** undoes the tag; it does not merge existing rematches.
- **Killed after this death…** in the log fixes an older encounter boundary.
  Select the final death before the earlier winning attempt; later deaths in
  that fight move to a separate rematch. The exact win time is not reconstructed.

- **Merge selected boss categories…**: Ctrl-click categories in the main table,
  click Merge, and choose an existing category or type the correct name. Their
  counts combine and spelling aliases are remembered for future readings.
- **Move selected death(s)…**: open **Death log / screenshots**, select the entries
  (Ctrl/Shift-click for several), click Move, and choose a target category. This
  changes only those entries; it does not redirect future environment deaths.
- **Rename selected boss** still renames an entire category and merges into an
  existing name when applicable.

Merge/transfer dropdowns list each encounter separately, including killed fights.
All edits preserve timestamps and screenshot links, and create a JSON backup in
the active profile's `backups/` directory. Manually assigned deaths are protected
from later automatic OCR reassignment. OCR boxes are assembled left to right;
known names with the same words in a different order reuse the same category.
First startup with encounter support also creates `counter.before-encounters.json`.
Profile export/import preserves encounter IDs and killed tags.

Totals, death timestamps, aliases, and the capture region persist in `counter.json`.
Undo removes the latest death across sessions. Back up that JSON to keep a copy.
Selecting a new area clears recent detections. Moving the HUD or changing resolution
requires selecting the area again. Arbitrary text in the selected area can be mistaken
for a name; verify with actual gameplay. F8/F9 must be available to register globally.

Use **F7** during a death screen, then **Detection check**, to inspect the captured
image and match score. **Restart app** reloads code and saved settings.

## Performance and pause

A single capture loop captures and checks for the death screen once per second.
Two matching samples confirm the death. Boss OCR does not load or run during
ordinary gameplay: only after a confirmed death or F8 count does it search the
previous ten seconds, newest first. Two agreeing names are required. OCR inference
and OpenCV are limited to one CPU thread each to reduce contention with games.
The 12-second history stores full-resolution, uncompressed pixels in RAM. Compression
occurs only when saving the two death-log screenshots (or an F7 diagnostic).
At 2560×1440, twelve RGB frames take about 133 MB, plus the latest capture and
application overhead (about 150–160 MB of image buffers). 4K uses more memory.
Buffering still has capture/copy costs but no routine JPEG encoding.

**Pause all capture and processing** stops background screenshots, OCR, and death
detection and clears recent image/name history. Resume before playing again;
the history needs time to refill. Pause also disables manual counts and F7 capture.
Use pause when playing a different game: automatic process/window tracking is not
implemented yet. Turning off only **Automatically count deaths** leaves the
screenshot buffer running; OCR still runs only after an F8 count.

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
