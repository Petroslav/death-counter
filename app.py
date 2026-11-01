"""Local Windows death counter: global hotkeys plus rolling boss-name OCR."""
import ctypes
from ctypes import wintypes
from collections import deque
import json
import logging
import os
from pathlib import Path
import queue
import re
import threading
import time
import sys
import tkinter as tk
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from tkinter import ttk, messagebox, filedialog, simpledialog
from profile_store import ProfileStore
from death_edits import merge_categories, transfer_deaths

APP_ROOT = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
DATA_ROOT = Path(os.environ.get('DEATH_COUNTER_DATA', APP_ROOT / 'data' if getattr(sys, 'frozen', False) else APP_ROOT))
DATA = DATA_ROOT / 'counter.json'

# Some Windows Python installs omit the Tcl search path inside virtualenvs.
for variable, folder in ([] if getattr(sys, 'frozen', False) else [('TCL_LIBRARY', 'tcl8.6'), ('TK_LIBRARY', 'tk8.6')]):
    library = Path(sys.base_prefix) / 'tcl' / folder
    if library.is_dir():
        os.environ.setdefault(variable, str(library))


def choose_boss(history, now):
    """Use the most recent name confirmed twice in the preceding ten seconds."""
    recent = sorted((stamp, name) for stamp, name in history if 0 <= now - stamp <= 10)
    counts = {}
    for _, name in recent:
        key = ' '.join(name.split()).casefold()
        counts[key] = counts.get(key, 0) + 1
    return next((name for _, name in reversed(recent) if counts[' '.join(name.split()).casefold()] >= 2), 'Enemy/environment death')


def resolve_boss(name, aliases, existing=()):
    existing = list(existing)
    key = ' '.join(name.split()).casefold()
    if key in ('the hunt, hunter of the order', 'hunter of the order', 'unter ofthe order', 'the hunt, hunter of the eorder', 'hunter of the eorder'):
        return 'Hunter of the Order'
    for source, target in aliases.items():
        if ' '.join(source.split()).casefold() == key:
            return target
    exact = next((saved for saved in existing if ' '.join(saved.split()).casefold() == key), None)
    if exact:
        return exact
    tokens = sorted(re.findall(r'\w+', key))
    if len(tokens) >= 3 and len(''.join(tokens)) >= 8:
        matches = {target for source, target in ([(saved,saved) for saved in existing] + list(aliases.items())) if sorted(re.findall(r'\w+',source.casefold())) == tokens}
        if len(matches) == 1:
            return matches.pop()
    def compact(text):
        text = re.sub(r'^the\s+hunt\s*[,.:;-]?\s*', '', text.casefold())
        return ''.join(c for c in text if c.isalnum())
    query = compact(name)
    if len(query) < 8 or key == 'enemy/environment death':
        return name
    scores = {}
    candidates = [(saved, saved) for saved in existing] + list(aliases.items())
    for source, target in candidates:
        if target.casefold() == 'enemy/environment death':
            continue
        candidate = compact(source)
        if len(candidate) < 8:
            continue
        score = SequenceMatcher(None, query, candidate).ratio()
        scores[target] = max(scores.get(target, 0), score)
    ranked = sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
    if ranked and ranked[0][1] >= 0.88 and (len(ranked) == 1 or ranked[0][1] - ranked[1][1] >= 0.06):
        return ranked[0][0]
    return name


def prepare_boss_image(image):
    import cv2
    gray = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
    enhanced = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)


def boss_text(result):
    parts = [(i,text.strip()) for i,(text,score) in enumerate(zip(result.txts or [],result.scores or [])) if score >= 0.8]
    boxes = getattr(result,'boxes',None)
    if boxes is not None and len(boxes) == len(result.txts or []):
        parts.sort(key=lambda part: sum(float(point[0]) for point in boxes[part[0]])/len(boxes[part[0]]))
    return re.sub(r'\s+', ' ', ' '.join(text for _,text in parts)).strip()


class Counter:
    def __init__(self, root):
        global DATA
        self.profiles = ProfileStore(DATA_ROOT)
        DATA = self.profiles.data_path()
        self.root = root
        self.events = queue.Queue()
        self.history = deque(maxlen=60)
        self.lock = threading.Lock()
        self.ocr_lock = threading.Lock()
        self.ocr_engine = None
        self.stop = threading.Event()
        self.paused = threading.Event()
        self.restart_requested = False
        self.region = None
        self.death_region = None
        self.death_template = None
        self.auto_enabled = True
        self.monitor_index = 1
        self.deaths = []
        self.last_press = 0
        self.aliases = {}
        self.reference_path = None
        if DATA.exists():
            try:
                saved = json.loads(DATA.read_text(encoding='utf-8'))
                self.deaths = saved.get('deaths', [])
                self.region = saved.get('region')
                self.aliases = saved.get('aliases', {})
                known = []
                for death in self.deaths:
                    if not death.get('manual_assignment'):
                        death['boss'] = resolve_boss(death['boss'], self.aliases, known)
                    known.append(death['boss'])
                for death in self.deaths:
                    if death['boss'] == 'Exploration / Unknown':
                        death['boss'] = 'Enemy/environment death'
                self.aliases.pop('Exploration / Unknown', None)
                self.death_region = saved.get('death_region')
                self.death_template = saved.get('death_template')
                self.auto_enabled = saved.get('auto_enabled', True)
                self.monitor_index = saved.get('monitor_index', 1)
                self.reference_path = saved.get('reference_path')
            except (ValueError, OSError):
                messagebox.showwarning('Saved data', 'Could not read counter.json. The original file will be preserved. Close the app and inspect it before continuing.')
                root.destroy()
                raise SystemExit(1)
        root.title('Death Counter')
        root.geometry('640x850')
        self.total = tk.StringVar()
        self.status = tk.StringVar(value='Starting OCR…')
        self.detected = tk.StringVar(value='No recent boss')
        ttk.Label(root, textvariable=self.total, font=('Segoe UI', 26, 'bold')).pack(pady=12)
        ttk.Label(root, text='F8: count death     F9: undo     F7: check detection').pack()
        ttk.Button(root, text='Restart app', command=self.restart).pack(pady=3)
        self.pause_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(root, text='Pause all capture and processing', variable=self.pause_var, command=self.toggle_pause).pack()
        profiles = ttk.Frame(root)
        profiles.pack(fill='x', padx=10, pady=5)
        self.profile_ids = list(self.profiles.state['profiles'])
        self.profile_choice = ttk.Combobox(profiles, state='readonly', values=[self.profiles.state['profiles'][ident] for ident in self.profile_ids], width=30)
        self.profile_choice.current(self.profile_ids.index(self.profiles.active))
        self.profile_choice.pack(side='left', fill='x', expand=True)
        self.profile_choice.bind('<<ComboboxSelected>>', self.switch_profile)
        ttk.Button(profiles, text='New game', command=self.new_profile).pack(side='left', padx=3)
        ttk.Button(profiles, text='Export', command=self.export_profile).pack(side='left')
        ttk.Button(profiles, text='Import', command=self.import_profile).pack(side='left', padx=3)
        ttk.Button(root, text='Upload red death-screen reference for this game', command=self.upload_reference).pack(pady=3)
        import mss
        with mss.mss() as capture:
            self.monitors = [dict(monitor) for monitor in capture.monitors[1:]]
        if not 1 <= self.monitor_index <= len(self.monitors):
            self.monitor_index = 1
        self.monitor_choice = ttk.Combobox(root, state='readonly', width=65, values=[f"Display {i}: {m['width']}×{m['height']} at ({m['left']}, {m['top']})" for i, m in enumerate(self.monitors, 1)])
        self.monitor_choice.current(self.monitor_index - 1)
        self.monitor_choice.pack(pady=5)
        self.monitor_choice.bind('<<ComboboxSelected>>', self.change_monitor)
        ttk.Button(root, text='Select boss-name screen area', command=self.select_region).pack(pady=10)
        self.region_status = tk.StringVar(value=self.region_description())
        ttk.Label(root, textvariable=self.region_status, wraplength=510).pack()
        self.ocr_status = tk.StringVar(value='Boss reader idle — runs only after a counted death')
        ttk.Label(root, textvariable=self.ocr_status, wraplength=510).pack()
        self.auto_var = tk.BooleanVar(value=self.auto_enabled)
        ttk.Checkbutton(root, text='Automatically count deaths', variable=self.auto_var, command=self.toggle_auto).pack(pady=5)
        self.death_status = tk.StringVar(value='Full-screen death detection — built-in reference, no calibration needed')
        ttk.Label(root, textvariable=self.death_status, wraplength=510).pack()
        ttk.Label(root, textvariable=self.detected).pack()
        ttk.Label(root, textvariable=self.status, wraplength=510).pack(pady=8)
        buttons = ttk.Frame(root)
        buttons.pack()
        ttk.Button(buttons, text='Count death', command=lambda: self.count(time.monotonic())).pack(side='left', padx=5)
        ttk.Button(buttons, text='Undo', command=self.undo).pack(side='left')
        ttk.Button(buttons, text='Death log / screenshots', command=self.show_log).pack(side='left', padx=5)
        ttk.Button(buttons, text='Detection check', command=self.show_diagnostic).pack(side='left')
        self.table = ttk.Treeview(root, columns=('boss', 'count'), show='headings', height=9)
        self.table.heading('boss', text='Boss / category')
        self.table.heading('count', text='Deaths')
        self.table.column('boss', width=360)
        self.table.column('count', width=80, anchor='center')
        self.table.pack(fill='both', expand=True, padx=12, pady=12)
        edit = ttk.Frame(root)
        edit.pack(fill='x', padx=12, pady=(0, 12))
        self.correction = ttk.Entry(edit)
        self.correction.pack(side='left', fill='x', expand=True)
        ttk.Button(edit, text='Rename selected boss', command=self.rename).pack(side='left', padx=5)
        ttk.Button(root, text='Merge selected boss categories… (Ctrl-click to select several)', command=self.merge_selected).pack(pady=(0,8))
        self.save()
        self.refresh()
        from death_log import ScreenshotLog
        self.screenshots = ScreenshotLog(self.stop, lambda text: self.events.put(('status', text)), lambda: self.monitor_index, lambda: not self.paused.is_set())
        threading.Thread(target=self.screenshots.run, daemon=True).start()
        self.hotkey_thread = threading.Thread(target=self.hotkeys, daemon=True)
        self.hotkey_thread.start()
        threading.Thread(target=self.death_loop, daemon=True).start()
        root.after(100, self.poll)
        root.protocol('WM_DELETE_WINDOW', self.close)

    def save(self):
        temp = DATA.with_suffix('.tmp')
        temp.write_text(json.dumps({'region': self.region, 'deaths': self.deaths, 'aliases': self.aliases, 'death_region': self.death_region, 'death_template': self.death_template, 'auto_enabled': self.auto_enabled, 'monitor_index': self.monitor_index, 'reference_path': self.reference_path}, indent=2), encoding='utf-8')
        temp.replace(DATA)

    def toggle_pause(self):
        if self.pause_var.get():
            self.paused.set()
            self.screenshots.clear()
            with self.lock:
                self.history.clear()
            self.status.set('Paused — no screenshots, OCR, or automatic counting')
        else:
            self.paused.clear()
            self.status.set('Capture resumed')

    def switch_profile(self, _=None):
        self.profiles.activate(self.profile_ids[self.profile_choice.current()])
        self.restart()

    def new_profile(self):
        name = simpledialog.askstring('New game profile', 'Game name:', parent=self.root)
        if name and name.strip():
            ident = self.profiles.create(name)
            self.profiles.activate(ident)
            self.restart()

    def export_profile(self):
        path = filedialog.asksaveasfilename(parent=self.root, title='Export game profile including screenshots', defaultextension='.zip', filetypes=[('Game profile ZIP', '*.zip')])
        if path:
            try:
                self.save()
                missing = self.profiles.export(path)
                messagebox.showinfo('Profile exported', 'Profile, settings, and available screenshots exported.' + (f' {missing} missing images could not be included.' if missing else ''))
            except Exception as exc:
                messagebox.showerror('Export failed', str(exc))

    def import_profile(self):
        path = filedialog.askopenfilename(parent=self.root, title='Import game profile', filetypes=[('Game profile ZIP', '*.zip')])
        if path:
            try:
                ident = self.profiles.import_archive(path)
                self.profiles.activate(ident)
                self.restart()
            except Exception as exc:
                messagebox.showerror('Import failed', str(exc))

    def upload_reference(self):
        path = filedialog.askopenfilename(parent=self.root, title='Select death screen with a red symbol', filetypes=[('Images', '*.png *.jpg *.jpeg *.bmp')])
        if path:
            try:
                import cv2
                from death_detection import ScreenDetector
                ScreenDetector(path)  # Validate before replacing a working reference.
                image = cv2.imread(path)
                target = DATA.parent / 'custom-death-reference.png'
                if not cv2.imwrite(str(target), image):
                    raise OSError('Could not save reference')
                self.reference_path = str(target.resolve())
                self.auto_enabled = True
                self.save()
                self.restart()
            except Exception as exc:
                messagebox.showerror('Reference not saved', str(exc))

    def region_description(self):
        if not self.region:
            return 'Boss area: not selected'
        r = self.region
        return f"Boss area saved: x={r['left']}, y={r['top']}, {r['width']} × {r['height']} pixels"

    def change_monitor(self, _=None):
        previous = self.monitors[self.monitor_index - 1]
        self.monitor_index = self.monitor_choice.current() + 1
        current = self.monitors[self.monitor_index - 1]
        if self.region:
            r = self.region
            self.region = {
                'left': current['left'] + round((r['left']-previous['left']) * current['width']/previous['width']),
                'top': current['top'] + round((r['top']-previous['top']) * current['height']/previous['height']),
                'width': round(r['width'] * current['width']/previous['width']),
                'height': round(r['height'] * current['height']/previous['height']),
            }
        with self.lock:
            self.history.clear()
        self.screenshots.clear()
        self.region_status.set(self.region_description())
        self.save()
        self.status.set('Display saved. Boss area moved to this display; check its position if the HUD differs.')

    def capture_diagnostic(self):
        if self.paused.is_set():
            self.status.set('Capture is paused. Resume before taking a detection check.')
            return
        try:
            import mss
            import numpy as np
            from death_log import encode
            from death_detection import ScreenDetector
            with mss.mss() as capture:
                monitor = dict(capture.monitors[self.monitor_index])
                image = np.array(capture.grab(monitor))
            folder = DATA.parent / 'diagnostics'
            folder.mkdir(exist_ok=True)
            (folder / 'capture.jpg').write_bytes(encode(image))
            score = ScreenDetector(self.reference_path).score(image)
            details = {'time': datetime.now().astimezone().isoformat(), 'score': score, 'threshold': 0.65, 'monitor': monitor, 'automatic_enabled': self.auto_enabled}
            (folder / 'capture.json').write_text(json.dumps(details, indent=2), encoding='utf-8')
            self.status.set(f'F7 captured screen: match {score:.0%}. Click Detection check to review.')
        except Exception as exc:
            self.status.set(f'Detection check failed: {exc}')

    def show_diagnostic(self):
        from PIL import Image, ImageTk
        folder = DATA.parent / 'diagnostics'
        if not (folder / 'capture.json').exists():
            messagebox.showinfo('Detection check', 'While the death symbol is visible IN THE GAME, press F7. Then return here and click Detection check. This records what the detector sees without counting a death.')
            return
        try:
            info = json.loads((folder / 'capture.json').read_text(encoding='utf-8'))
            with Image.open(folder / 'capture.jpg') as source:
                image = source.copy()
            image.thumbnail((1000, 650))
            window = tk.Toplevel(self.root)
            window.title('F7 detection check — captured game display')
            ttk.Label(window, text=f"{info['time']} — match {info['score']:.0%} (needs 65%)\nIf this does not show the game, check the monitor and try borderless mode.").pack(padx=10, pady=10)
            photo = ImageTk.PhotoImage(image, master=window)
            label = ttk.Label(window, image=photo)
            label.image = photo
            label.pack(padx=10, pady=10)
        except (OSError, ValueError) as exc:
            messagebox.showerror('Detection check', str(exc))

    def refresh(self):
        self.total.set(f'{len(self.deaths)} deaths')
        totals = {}
        for death in self.deaths:
            name = death['boss']
            totals[name] = totals.get(name, 0) + 1
        self.table.delete(*self.table.get_children())
        for name, count in sorted(totals.items()):
            self.table.insert('', 'end', values=(name, count))

    def count(self, stamp):
        if self.paused.is_set():
            return
        if abs(stamp - self.last_press) < 2:
            return
        self.last_press = stamp
        boss = 'Enemy/environment death'
        event_time = datetime.now().astimezone() - timedelta(seconds=max(0, time.monotonic() - stamp))
        death = {'boss': boss, 'time': event_time.isoformat(timespec='milliseconds')}
        error = None
        try:
            death['screenshots'] = self.screenshots.save(DATA.parent / 'death_logs', stamp)
        except Exception as exc:
            error = str(exc)
            death['screenshot_error'] = error
        self.deaths.append(death)
        self.save()
        self.refresh()
        self.status.set(f'Counted death for {boss}' + (f'; screenshot error: {error}' if error else ''))
        if boss == 'Enemy/environment death' and self.region:
            self.ocr_status.set('Death counted — searching the previous 10 seconds for a boss name…')
            frames = self.screenshots.recent_frames(stamp)
            region = dict(self.region)
            monitor = dict(self.monitors[self.monitor_index - 1])
            threading.Thread(target=self.recover_boss, args=(death, stamp, frames, region, monitor), daemon=True).start()

    def recover_boss(self, death, onset, frames, region, monitor):
        """Inspect snapshots newest first, without blocking the UI or death detector."""
        import cv2
        import numpy as np
        readings = []
        try:
            # No model loading or OCR inference during normal gameplay.
            with self.ocr_lock:
                if self.ocr_engine is None:
                    from rapidocr import RapidOCR
                    class EmptyTextFilter(logging.Filter):
                        def filter(self, record):
                            return 'The text detection result is empty' not in record.getMessage()
                    logging.getLogger('RapidOCR').addFilter(EmptyTextFilter())
                    self.ocr_engine = RapidOCR(params={'EngineConfig.onnxruntime.intra_op_num_threads': 1, 'EngineConfig.onnxruntime.inter_op_num_threads': 1})
            for stamp, _, encoded in frames:
                if self.stop.is_set() or self.paused.is_set():
                    return
                image = encoded if isinstance(encoded, np.ndarray) else cv2.imdecode(np.frombuffer(encoded, dtype=np.uint8), cv2.IMREAD_COLOR)
                scale_x, scale_y = image.shape[1]/monitor['width'], image.shape[0]/monitor['height']
                x, y = round((region['left']-monitor['left'])*scale_x), round((region['top']-monitor['top'])*scale_y)
                crop = image[max(0,y):max(0,y)+round(region['height']*scale_y), max(0,x):max(0,x)+round(region['width']*scale_x)]
                if not crop.size:
                    continue
                with self.ocr_lock:
                    if self.ocr_engine is None:
                        return
                    result = self.ocr_engine(prepare_boss_image(crop))
                name = boss_text(result)
                if len(name) >= 3 and any(c.isalpha() for c in name):
                    name = resolve_boss(name, dict(self.aliases), [entry['boss'] for entry in list(self.deaths)])
                    readings.append((stamp, name))
                boss = choose_boss(readings, onset)
                if boss != 'Enemy/environment death':
                    self.events.put(('recovered_boss', (death, boss)))
                    return
            self.events.put(('ocr_status', 'No confirmed boss name in previous 10 seconds — reader idle'))
        except Exception as exc:
            self.events.put(('status', f'Death saved; snapshot boss lookup failed: {exc}'))

    def show_log(self):
        from PIL import Image, ImageTk
        window = tk.Toplevel(self.root)
        window.title('Death log — screenshot viewer')
        window.geometry('1100x760')
        table_frame = ttk.Frame(window)
        table_frame.pack(fill='x', padx=10, pady=10)
        table = ttk.Treeview(table_frame, columns=('time', 'boss', 'before', 'death'), show='headings', height=7)
        for column, title in [('time', 'Death timestamp'), ('boss', 'Boss / category'), ('before', 'Before capture timestamp'), ('death', 'Death-screen capture timestamp')]:
            table.heading(column, text=title)
            table.column(column, width=240)
        table.pack(side='left', fill='x', expand=True)
        scrollbar = ttk.Scrollbar(table_frame, orient='vertical', command=table.yview)
        scrollbar.pack(side='right', fill='y')
        table.configure(yscrollcommand=scrollbar.set)
        previews = ttk.Frame(window)
        previews.pack(fill='both', expand=True, padx=10)
        panels = {}
        for kind, title in [('before', 'Before death'), ('death', 'Death screen')]:
            panel = ttk.LabelFrame(previews, text=title)
            panel.pack(side='left', fill='both', expand=True, padx=4)
            caption = ttk.Label(panel, text='Select a death', wraplength=480)
            caption.pack(pady=8)
            picture = ttk.Label(panel, anchor='center')
            picture.pack(fill='both', expand=True)
            panels[kind] = (caption, picture)
        entries = {}
        photos = {}
        def display(_=None):
            selection = table.selection()
            if not selection:
                return
            entry = entries[selection[0]]
            for kind, (caption, picture) in panels.items():
                shot = entry.get('screenshots', {}).get(kind)
                picture.configure(image='', text='Screenshot unavailable')
                photos.pop(kind, None)
                if not shot:
                    caption.configure(text=entry.get('screenshot_error', entry.get('screenshots',{}).get('before_unavailable_reason', 'No saved screenshot for this death.')))
                    continue
                caption.configure(text=shot['time'] + (f"  ({shot['seconds_before']:.2f}s before detection)" if 'seconds_before' in shot else ''))
                try:
                    with Image.open(shot['path']) as source:
                        image = source.copy()
                    image.thumbnail((max(200, window.winfo_width() // 2 - 45), max(180, window.winfo_height() - 310)))
                    photos[kind] = ImageTk.PhotoImage(image, master=window)
                    picture.configure(image=photos[kind], text='')
                except (OSError, ValueError) as exc:
                    picture.configure(text=f'Cannot load screenshot: {exc}', wraplength=400)
        def refresh_log():
            selected_deaths = {id(entries[item]) for item in table.selection() if item in entries}
            table.delete(*table.get_children())
            entries.clear()
            restored = []
            for death in reversed(self.deaths):
                shots = death.get('screenshots', {})
                before, current = shots.get('before'), shots.get('death')
                ident = table.insert('', 'end', values=(death['time'], death['boss'], before['time'] if before else 'Unavailable', current['time'] if current else 'Unavailable'))
                entries[ident] = death
                if id(death) in selected_deaths:
                    restored.append(ident)
            if entries:
                table.selection_set(restored or [next(iter(entries))])
                display()
            else:
                for caption, picture in panels.values():
                    caption.configure(text='No deaths logged yet')
                    picture.configure(image='', text='')
                photos.clear()
        def navigate(direction):
            items = list(table.get_children())
            if not items:
                return
            selected = table.selection()
            index = items.index(selected[0]) if selected else 0
            target = items[max(0, min(len(items)-1, index + direction))]
            table.selection_set(target)
            table.see(target)
        def move_selected():
            chosen = [entries[item] for item in table.selection() if item in entries]
            if not chosen:
                return
            target = self.pick_category(f'Move {len(chosen)} selected death(s)', chosen[0]['boss'], window)
            if target:
                self.backup_before_edit()
                transfer_deaths(self.deaths, chosen, target)
                self.save()
                self.refresh()
                refresh_log()
                self.status.set(f'Moved {len(chosen)} death(s) to {target}')
        table.bind('<<TreeviewSelect>>', display)
        actions = ttk.Frame(window)
        actions.pack(pady=(0, 10))
        ttk.Button(actions, text='Previous', command=lambda: navigate(-1)).pack(side='left', padx=5)
        ttk.Button(actions, text='Next', command=lambda: navigate(1)).pack(side='left', padx=5)
        ttk.Button(actions, text='Refresh log', command=refresh_log).pack(side='left', padx=5)
        ttk.Button(actions, text='Move selected death(s)…', command=move_selected).pack(side='left', padx=5)
        ttk.Label(window, text='Ctrl-click or Shift-click rows to move multiple deaths. Screenshots and timestamps stay attached.').pack(pady=(0,8))
        window.after(100, refresh_log)

    def undo(self):
        if self.deaths:
            removed = self.deaths.pop()
            self.save()
            self.refresh()
            self.status.set(f'Undid death for {removed["boss"]}')

    def rename(self):
        selected = self.table.selection()
        new = self.correction.get().strip()
        if not selected or not new:
            return
        old = self.table.item(selected[0], 'values')[0]
        self.backup_before_edit()
        merge_categories(self.deaths, self.aliases, [old], new)
        self.save()
        self.refresh()

    def backup_before_edit(self):
        import shutil
        if DATA.exists():
            folder = DATA.parent / 'backups'
            folder.mkdir(exist_ok=True)
            shutil.copy2(DATA,folder / f"before-edit-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.json")

    def pick_category(self, title, initial='', parent=None):
        dialog = tk.Toplevel(parent or self.root)
        dialog.title(title)
        dialog.transient(parent or self.root)
        dialog.grab_set()
        ttk.Label(dialog,text='Choose an existing category or type a new name:').pack(padx=15,pady=10)
        choices = sorted({death['boss'] for death in self.deaths} | {'Enemy/environment death'})
        target = ttk.Combobox(dialog,values=choices,width=55)
        target.set(initial)
        target.pack(padx=15,pady=5)
        result=[]
        def accept():
            name=target.get().strip()
            if name:
                name=next((choice for choice in choices if choice.casefold()==name.casefold()),name)
                result.append(name)
                dialog.destroy()
        actions=ttk.Frame(dialog)
        actions.pack(pady=12)
        ttk.Button(actions,text='Apply',command=accept).pack(side='left',padx=5)
        ttk.Button(actions,text='Cancel',command=dialog.destroy).pack(side='left')
        dialog.bind('<Return>',lambda _:accept())
        dialog.bind('<Escape>',lambda _:dialog.destroy())
        target.focus_set()
        self.root.wait_window(dialog)
        return result[0] if result else None

    def merge_selected(self):
        sources=[self.table.item(item,'values')[0] for item in self.table.selection()]
        if not sources:
            self.status.set('Select the boss categories to merge first (Ctrl-click for several).')
            return
        target=self.pick_category('Merge selected categories',sources[0])
        if target:
            self.backup_before_edit()
            changed=merge_categories(self.deaths,self.aliases,sources,target)
            self.save()
            self.refresh()
            self.status.set(f'Merged {changed} death(s) into {target}')

    def toggle_auto(self):
        self.auto_enabled = self.auto_var.get()
        self.save()

    def calibrate_death(self):
        self.root.withdraw()
        self.root.after(3000, lambda: self.select_region(death=True))

    def select_region(self, death=False):
        # Primary display coordinates, matched to Windows physical pixels.
        screenshot = None
        if death:
            import mss
            import numpy as np
            with mss.mss() as capture:
                screenshot = np.array(capture.grab(capture.monitors[self.monitor_index]))
        overlay = tk.Toplevel(self.root)
        monitor = self.monitors[self.monitor_index - 1]
        overlay.overrideredirect(True)
        overlay.geometry(f"{monitor['width']}x{monitor['height']}")
        overlay.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(overlay.winfo_id())
        ctypes.windll.user32.SetWindowPos(hwnd, -1, monitor['left'], monitor['top'], monitor['width'], monitor['height'], 0x0040)
        overlay.attributes('-topmost', True)
        overlay.attributes('-alpha', 0.45)
        canvas = tk.Canvas(overlay, bg='black', cursor='crosshair', highlightthickness=0)
        canvas.pack(fill='both', expand=True)
        canvas.create_text(25, 40, anchor='nw', text='Drag around the RED DEATH SYMBOL. Escape cancels.' if death else 'Drag tightly around the boss NAME only. Escape cancels.', fill='white', font=('Segoe UI', 18))
        start = []
        def finish():
            overlay.destroy()
            self.root.deiconify()
        def down(event):
            start[:] = [event.x_root, event.y_root]
            canvas.delete('selection')
        def move(event):
            if start:
                canvas.delete('selection')
                canvas.create_rectangle(start[0]-monitor['left'], start[1]-monitor['top'], event.x, event.y, outline='cyan', width=3, tags='selection')
        def up(event):
            if start:
                x, y = start
                width, height = abs(event.x_root-x), abs(event.y_root-y)
                if width >= 20 and height >= 10:
                    region = {'left': min(x, event.x_root), 'top': min(y, event.y_root), 'width': width, 'height': height}
                    if death:
                        from death_detection import red_mask
                        left, top = region['left']-monitor['left'], region['top']-monitor['top']
                        mask = red_mask(screenshot[top:top+height, left:left+width])
                        if int(mask.sum()) < 80:
                            self.death_status.set('Calibration failed: too little red. Try with the full symbol visible.')
                            finish()
                            return
                        with self.lock:
                            self.death_region = region
                            self.death_template = mask.tolist()
                        self.auto_enabled = True
                        self.auto_var.set(True)
                        self.death_status.set('Calibration saved. Automatic counting ON; waiting for this death screen to clear.')
                    else:
                        self.region = region
                        with self.lock:
                            self.history.clear()
                    self.save()
                    self.region_status.set(self.region_description())
                    self.status.set('Screen area saved; it will be restored on restart.')
            finish()
        canvas.bind('<ButtonPress-1>', down)
        canvas.bind('<B1-Motion>', move)
        canvas.bind('<ButtonRelease-1>', up)
        overlay.bind('<Escape>', lambda _: finish())

    def death_loop(self):
        try:
            from death_detection import ScreenDetector, DeathGate
            detector = ScreenDetector(self.reference_path)
            gate = DeathGate()
            previous_monitor = self.monitor_index
            previous_stamp = None
            while not self.stop.wait(0.1):
                if self.monitor_index != previous_monitor:
                    gate = DeathGate()
                    previous_monitor = self.monitor_index
                if not self.auto_enabled or self.paused.is_set():
                    gate = DeathGate()
                    continue
                latest = self.screenshots.latest_frame()
                if latest is None:
                    continue
                index, stamp, frame = latest
                if index != self.monitor_index or stamp == previous_stamp:
                    continue
                previous_stamp = stamp
                score = detector.score(frame)
                onset = gate.update(score >= 0.65, stamp)
                self.events.put(('death_status', f'Death symbol match: {score:.0%}' + (' — waiting for symbol to clear' if gate.active else ' — watching')))
                if onset is not None:
                    self.events.put(('death', onset))
        except Exception as exc:
            self.events.put(('death_status', f'Automatic detection unavailable: {exc}'))

    def hotkeys(self):
        user32 = ctypes.windll.user32
        # MOD_NOREPEAT suppresses repeated key-down messages while held.
        registered = []
        try:
            for ident, key in ((1, 0x77), (2, 0x78), (3, 0x76)):
                if user32.RegisterHotKey(None, ident, 0x4000, key):
                    registered.append(ident)
                else:
                    self.events.put(('status', f'Could not register F{ {1:8, 2:9, 3:7}[ident] }; another app may use it.'))
            msg = wintypes.MSG()
            while not self.stop.wait(0.02):
                while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                    if msg.message == 0x0312:
                        self.events.put(({1:'death', 2:'undo', 3:'diagnostic'}[msg.wParam], time.monotonic()))
        finally:
            for ident in registered:
                user32.UnregisterHotKey(None, ident)

    def poll(self):
        while True:
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == 'death':
                self.count(value)
            elif kind == 'undo':
                self.undo()
            elif kind == 'diagnostic':
                self.capture_diagnostic()
            elif kind == 'recovered_boss':
                death, boss = value
                if any(entry is death for entry in self.deaths) and death['boss'] == 'Enemy/environment death' and not death.get('manual_assignment'):
                    death['boss'] = resolve_boss(boss, self.aliases, (entry['boss'] for entry in self.deaths))
                    self.save()
                    self.refresh()
                    self.status.set(f"Recovered boss from recent snapshots: {death['boss']}")
                    self.ocr_status.set(f"Last death boss: {death['boss']} — reader idle")
            elif kind == 'death_status':
                self.death_status.set(value)
            elif kind == 'ocr_status':
                self.ocr_status.set(value)
            else:
                self.status.set(value)
        self.detected.set('Boss names are checked after each counted death')
        self.root.after(100, self.poll)

    def close(self):
        self.stop.set()
        self.root.destroy()

    def restart(self):
        # Every user edit is already persisted; do not overwrite externally edited data.
        self.restart_requested = True
        self.close()


def packaged_self_test(destination):
    """Exercise bundled Tk, assets, and all OCR stages without touching user data."""
    import traceback
    report = {'ok': False}
    try:
        import cv2
        import numpy as np
        from rapidocr import RapidOCR
        from death_detection import ScreenDetector
        root = tk.Tk()
        root.withdraw()
        root.update()
        root.destroy()
        detector = ScreenDetector()
        reference = cv2.imread(str(Path(__file__).parent / 'assets' / 'death-reference.png'))
        if detector.score(reference) < 0.65:
            raise RuntimeError('Bundled reference match failed')
        image = np.zeros((150, 700, 3), dtype=np.uint8)
        cv2.putText(image, 'DEATH COUNTER', (20, 90), cv2.FONT_HERSHEY_SIMPLEX, 1.8, (255, 255, 255), 3)
        result = RapidOCR()(image)
        if not result.txts:
            raise RuntimeError('Bundled OCR failed')
        report = {'ok': True, 'ocr': list(result.txts)}
    except Exception:
        report['error'] = traceback.format_exc()
    Path(destination).write_text(json.dumps(report, indent=2), encoding='utf-8')
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--self-test':
        raise SystemExit(packaged_self_test(sys.argv[2]))
    ctypes.windll.user32.SetProcessDPIAware()
    counter = Counter(tk.Tk())
    counter.root.mainloop()
    counter.hotkey_thread.join(timeout=2)
    if counter.restart_requested:
        if getattr(sys, 'frozen', False):
            os.environ['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
            os.execl(sys.executable, sys.executable)
        else:
            os.execl(sys.executable, sys.executable, str(Path(__file__).resolve()))
