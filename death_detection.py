"""Match the calibrated red symbol, and emit once per death screen."""
import cv2
import numpy as np
from pathlib import Path


def symbol_mask(image):
    b, g, r = cv2.split(image[:, :, :3].astype(np.float32))
    return ((r > 95) & (r > g * 1.6) & (r > b * 1.5)).astype(np.uint8)


class ScreenDetector:
    """Search all screen positions and multiple scales for the supplied symbol."""
    def __init__(self):
        image = cv2.imread(str(Path(__file__).parent / 'assets' / 'death-reference.png'))
        if image is None:
            raise OSError('Missing built-in death-reference.png')
        mask = symbol_mask(image)
        points = cv2.findNonZero(mask)
        x, y, w, h = cv2.boundingRect(points)
        self.reference = mask[y:y+h, x:x+w]
        self.cache = {}

    def score(self, image):
        height, width = image.shape[:2]
        ratio = min(1.0, 640 / width, 640 / height)
        small = cv2.resize(image[:, :, :3], (round(width*ratio), round(height*ratio)))
        mask = symbol_mask(small)
        h, w = mask.shape
        if int(mask.sum()) < 100:
            return 0.0
        key = (h, w)
        if key not in self.cache:
            templates = []
            target = max(32, int(h * 0.25))
            while target <= h:
                tw = round(target * self.reference.shape[1] / self.reference.shape[0])
                if tw <= w:
                    templates.append(cv2.resize(self.reference, (tw, target), interpolation=cv2.INTER_NEAREST))
                target = max(target+1, round(target*1.07))
            self.cache[key] = templates
        best = 0.0
        for template in self.cache[key]:
            matches = cv2.matchTemplate(mask, template, cv2.TM_CCOEFF_NORMED)
            _, correlation, _, position = cv2.minMaxLoc(matches)
            if correlation > best:
                x, y = position
                th, tw = template.shape
                patch = mask[y:y+th, x:x+tw]
                dice = similarity(patch, template)
                best = max(best, min(correlation, dice))
        return best


def red_mask(image):
    b, g, r = cv2.split(image[:, :, :3].astype(np.int16))
    mask = ((r > 85) & (r > g * 1.45) & (r > b * 1.35)).astype(np.uint8)
    return cv2.resize(mask, (128, 128), interpolation=cv2.INTER_NEAREST)


def similarity(mask, reference):
    # Dice compares shape, penalizing unrelated red fills and missing strokes.
    a, b = mask > 0, reference > 0
    denominator = int(a.sum() + b.sum())
    return 2 * int((a & b).sum()) / denominator if denominator else 0.0


class DeathGate:
    def __init__(self):
        self.active = False
        self.first_match = None
        self.first_clear = None

    def update(self, matched, now):
        if matched:
            self.first_clear = None
            if self.first_match is None:
                self.first_match = now
            if not self.active and now - self.first_match >= 0.25:
                self.active = True
                return self.first_match
        else:
            self.first_match = None
            if self.first_clear is None:
                self.first_clear = now
            if now - self.first_clear >= 2:
                self.active = False
        return None
