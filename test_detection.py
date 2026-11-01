import unittest
import numpy as np
from death_detection import DeathGate, red_mask, similarity, ScreenDetector
import cv2
from pathlib import Path
import threading
import queue
from types import SimpleNamespace
from unittest.mock import Mock, patch
from app import Counter
from app import choose_boss, resolve_boss


class DetectionTests(unittest.TestCase):
    def test_boss_lookup_reads_raw_snapshots_after_death(self):
        counter = Counter.__new__(Counter)
        counter.stop = threading.Event()
        counter.paused = threading.Event()
        counter.ocr_lock = threading.Lock()
        counter.ocr_engine = Mock(return_value=SimpleNamespace(txts=['HUA, DEADLY BETROTHED'], scores=[0.99]))
        counter.aliases = {}
        counter.deaths = []
        counter.events = queue.Queue()
        image = np.zeros((90,160,3),dtype=np.uint8)
        death = {'boss':'Enemy/environment death'}
        with patch('cv2.imdecode') as decode:
            counter.recover_boss(death,10,[(9,'',image),(8,'',image),(7,'',image)],{'left':0,'top':0,'width':100,'height':30},{'left':0,'top':0,'width':160,'height':90})
            decode.assert_not_called()
        self.assertEqual(counter.ocr_engine.call_count,2)
        kind,payload=counter.events.get_nowait()
        self.assertEqual(kind,'recovered_boss')
        self.assertEqual(payload[1],'HUA, DEADLY BETROTHED')

    def test_two_fps_counts_once_and_rearms(self):
        gate = DeathGate()
        counts = []
        for stamp, matched in [(0,False),(0.5,True),(1,True),(1.5,True),(2,False),(2.5,False),(3,False),(3.5,False),(4,False),(4.5,True),(5,True)]:
            onset=gate.update(matched,stamp)
            if onset is not None:
                counts.append(onset)
        self.assertEqual(counts,[0.5,4.5])

    def test_one_second_samples_count_once_and_rearm(self):
        gate = DeathGate()
        counts=[]
        for stamp,matched in [(0,False),(1,True),(2,True),(3,True),(4,False),(5,False),(6,False),(7,True),(8,True)]:
            onset=gate.update(matched,stamp)
            if onset is not None:
                counts.append(onset)
        self.assertEqual(counts,[1,7])

    def test_truncated_name_matches_known_boss(self):
        self.assertEqual(resolve_boss('HUA DEADLY BETROTH', {}, ['HUA, DEADLY BETROTHED']), 'HUA, DEADLY BETROTHED')
        self.assertEqual(resolve_boss('HUNTER OF THE EORDER', {}, ['Hunter of the Order']), 'Hunter of the Order')

    def test_different_or_ambiguous_names_stay_separate(self):
        self.assertEqual(resolve_boss('SIXFOLD SCYTHE', {}, ['HUA, DEADLY BETROTHED']), 'SIXFOLD SCYTHE')
        self.assertEqual(resolve_boss('HUA', {}, ['HUA, DEADLY BETROTHED']), 'HUA')
        self.assertEqual(resolve_boss('abcdefghix', {}, ['abcdefghia', 'abcdefghib']), 'abcdefghix')

    def test_full_screen_reference_with_black_margins(self):
        detector = ScreenDetector()
        reference = cv2.imread(str(Path(__file__).parent / 'assets' / 'death-reference.png'))
        for width, height in [(620, 580), (850, 795)]:
            screen = np.zeros((1080, 1920, 3), dtype=np.uint8)
            screen[100:100+height, 500:500+width] = cv2.resize(reference, (width, height))
            self.assertGreaterEqual(detector.score(screen), 0.65)
        self.assertLess(detector.score(np.zeros_like(screen)), 0.65)
        self.assertLess(detector.score(np.full_like(screen, (0, 0, 230))), 0.65)

    def test_one_count_until_clear_and_return(self):
        gate = DeathGate()
        self.assertIsNone(gate.update(True, 10))
        self.assertEqual(gate.update(True, 10.3), 10)
        self.assertIsNone(gate.update(True, 20))
        gate.update(False, 21)
        gate.update(True, 22)  # Brief flicker must not rearm.
        self.assertIsNone(gate.update(True, 22.4))
        gate.update(False, 23)
        gate.update(False, 25.1)
        gate.update(True, 26)
        self.assertEqual(gate.update(True, 26.3), 26)

    def test_flash_does_not_count(self):
        gate = DeathGate()
        gate.update(True, 1)
        self.assertIsNone(gate.update(False, 1.1))
        self.assertFalse(gate.active)

    def test_red_shape_not_just_red_screen(self):
        image = np.zeros((128, 128, 3), dtype=np.uint8)
        image[20:100, 55:70, 2] = 230
        mask = red_mask(image)
        self.assertEqual(similarity(mask, mask), 1)
        self.assertLess(similarity(red_mask(np.full_like(image, (0, 0, 230))), mask), 0.72)
        self.assertEqual(similarity(red_mask(np.zeros_like(image)), mask), 0)

    def test_boss_window_uses_detection_onset(self):
        self.assertEqual(choose_boss([(5, 'Boss'), (5.2, 'Boss')], 10), 'Boss')
        self.assertEqual(choose_boss([(5, 'Boss'), (5.2, 'Boss')], 14.9), 'Boss')
        self.assertEqual(choose_boss([(5, 'Boss'), (5.2, 'Boss')], 15.3), 'Enemy/environment death')
        self.assertEqual(choose_boss([], 10), 'Enemy/environment death')

    def test_latest_confirmed_name_in_reverse_snapshot_order(self):
        self.assertEqual(choose_boss([(9,'NEW'), (8,'new'), (4,'Old'), (3,'Old')],10), 'NEW')
        self.assertEqual(choose_boss([(9,'Noise'), (8,'Boss'), (7,'Boss')],10), 'Boss')


if __name__ == '__main__':
    unittest.main()
