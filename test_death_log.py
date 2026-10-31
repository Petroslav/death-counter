import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
import cv2
import numpy as np
from death_log import ScreenshotLog, before_frame, encode


class LogTests(unittest.TestCase):
    def test_only_frames_one_to_two_seconds_before(self):
        frames = [(7, 'old', b''), (8.1, 'early', b''), (8.5, 'target', b''), (9.8, 'late', b'')]
        self.assertEqual(before_frame(frames, 10)[1], 'target')
        self.assertIsNone(before_frame([frames[0], frames[-1]], 10))

    def test_evidence_files_and_timestamps(self):
        image = np.zeros((60, 80, 4), dtype=np.uint8)
        log = ScreenshotLog(threading.Event(), lambda _: None)
        log.frames.append((8.5, '2026-10-31T10:00:00.000+02:00', encode(image)))
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
