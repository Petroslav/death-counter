import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
import cv2
import numpy as np
from death_log import ScreenshotLog, before_frame, encode


class LogTests(unittest.TestCase):
    def test_paused_capture_does_not_grab_and_clears_history(self):
        stop = threading.Event()
        log = ScreenshotLog(stop, self.fail, enabled=lambda: False)
        log.frames.append((1, 'old', b''))
        log.latest = (1, 1, None)
        with patch('death_log.mss.mss') as capture:
            worker = threading.Thread(target=log.run)
            worker.start()
            stop.wait(0.05)
            stop.set()
            worker.join(1)
            capture.return_value.__enter__.return_value.grab.assert_not_called()
        self.assertEqual(len(log.frames),0)
        self.assertIsNone(log.latest_frame())

    def test_shared_frame_and_full_resolution_history(self):
        stop = threading.Event()
        image = np.zeros((1440,2560,4),dtype=np.uint8)
        log = ScreenshotLog(stop, self.fail)
        with patch('death_log.mss.mss') as capture, patch('death_log.encode', return_value=b'jpeg') as encoder:
            mock = capture.return_value.__enter__.return_value
            mock.monitors = [None, {}]
            mock.grab.return_value = image
            worker = threading.Thread(target=log.run)
            worker.start()
            for _ in range(30):
                if log.latest_frame() is not None:
                    break
                stop.wait(0.01)
            stop.set()
            worker.join(1)
            encoder.assert_not_called()
        self.assertEqual(log.latest_frame()[2].shape,(1440,2560,4))
        self.assertEqual(log.frames[0][2].shape,(1440,2560,3))

    def test_snapshot_scan_is_recent_first_and_bounded(self):
        log = ScreenshotLog(threading.Event(), lambda _: None)
        log.frames.extend((i/4, '', b'') for i in range(64))
        selected = log.recent_frames(15)
        self.assertLessEqual(len(selected),12)
        self.assertTrue(all(0 <= 15-frame[0] <= 10 for frame in selected))
        self.assertTrue(all(a[0] > b[0] for a,b in zip(selected,selected[1:])))

    def test_only_frames_one_to_two_seconds_before(self):
        frames = [(7, 'old', b''), (8.1, 'early', b''), (8.5, 'target', b''), (9.8, 'late', b'')]
        self.assertEqual(before_frame(frames, 10)[1], 'target')
        self.assertIsNone(before_frame([frames[0], frames[-1]], 10))

    def test_evidence_files_and_timestamps(self):
        image = np.zeros((60, 80, 4), dtype=np.uint8)
        log = ScreenshotLog(threading.Event(), lambda _: None)
        log.frames.append((8.5, '2026-10-31T10:00:00.000+02:00', image[:, :, :3].copy()))
        with tempfile.TemporaryDirectory() as folder, patch('death_log.mss.mss') as capture:
            capture.return_value.__enter__.return_value.monitors = [None, {}]
            capture.return_value.__enter__.return_value.grab.return_value = image
            result = log.save(folder, 10)
            self.assertEqual(result['before']['seconds_before'], 1.5)
            for kind in ('before', 'death'):
                path = Path(result[kind]['path'])
                self.assertTrue(path.is_file())
                self.assertEqual(cv2.imread(str(path)).shape, (60, 80, 3))
                self.assertIn('T', result[kind]['time'])

    def test_empty_buffer_is_explicit(self):
        image = np.zeros((60, 80, 4), dtype=np.uint8)
        log = ScreenshotLog(threading.Event(), lambda _: None)
        with tempfile.TemporaryDirectory() as folder, patch('death_log.mss.mss') as capture:
            capture.return_value.__enter__.return_value.monitors = [None, {}]
            capture.return_value.__enter__.return_value.grab.return_value = image
            result = log.save(folder, 10)
            self.assertIsNone(result['before'])
            self.assertIsNotNone(result['death'])


if __name__ == '__main__':
    unittest.main()
