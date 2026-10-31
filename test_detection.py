import unittest
import numpy as np
from death_detection import DeathGate, red_mask, similarity, ScreenDetector
import cv2
from pathlib import Path
from app import choose_boss


class DetectionTests(unittest.TestCase):
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
        self.assertEqual(choose_boss([(5, 'Boss'), (5.2, 'Boss')], 10.3), 'Enemy/environment death')
        self.assertEqual(choose_boss([], 10), 'Enemy/environment death')


if __name__ == '__main__':
    unittest.main()
