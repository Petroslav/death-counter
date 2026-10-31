"""Bounded in-memory screenshot buffer and per-death evidence files."""
from collections import deque
from datetime import datetime
from pathlib import Path
import threading
import time
import uuid

import cv2
import numpy as np
import mss


def before_frame(frames, onset):
    eligible = [frame for frame in frames if 1 <= onset - frame[0] <= 2]
    return min(eligible, key=lambda frame: abs(onset - frame[0] - 1.5), default=None)


def encode(image):
    ok, encoded = cv2.imencode('.jpg', image[:, :, :3], [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise OSError('Could not encode screenshot')
    return encoded.tobytes()


class ScreenshotLog:
    def __init__(self, stop, on_error, monitor_index=lambda: 1):
        self.stop = stop
        self.on_error = on_error
        self.frames = deque(maxlen=20)
        self.lock = threading.Lock()
        self.monitor_index = monitor_index

    def run(self):
        try:
            with mss.mss() as capture:
                while not self.stop.is_set():
                    index = self.monitor_index()
                    image = np.array(capture.grab(capture.monitors[index]))
                    stamp, wall = time.monotonic(), datetime.now().astimezone().isoformat(timespec='milliseconds')
                    frame = (stamp, wall, encode(image))
                    with self.lock:
                        if index == self.monitor_index():
                            self.frames.append(frame)
                    self.stop.wait(0.25)
        except Exception as exc:
            self.on_error(f'Screenshot buffer unavailable: {exc}')

    def save(self, folder, onset):
        with self.lock:
            before = before_frame(list(self.frames), onset)
        folder = Path(folder) / (datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8])
        folder.mkdir(parents=True, exist_ok=False)
        result = {'before': None, 'death': None}
        if before is not None:
            path = folder / 'before.jpg'
            path.write_bytes(before[2])
            result['before'] = {'path': str(path.resolve()), 'time': before[1], 'seconds_before': round(onset - before[0], 3)}
        with mss.mss() as capture:
            image = np.array(capture.grab(capture.monitors[self.monitor_index()]))
            wall = datetime.now().astimezone().isoformat(timespec='milliseconds')
        path = folder / 'death.jpg'
        path.write_bytes(encode(image))
        result['death'] = {'path': str(path.resolve()), 'time': wall}
        return result
