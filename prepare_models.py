"""Warm lazy OCR components before packaging so first run works offline."""
import cv2
import numpy as np
from rapidocr import RapidOCR

image = np.zeros((150, 700, 3), dtype=np.uint8)
cv2.putText(image, 'DEATH COUNTER', (20, 90), cv2.FONT_HERSHEY_SIMPLEX, 1.8, (255, 255, 255), 3)
result = RapidOCR()(image)
if not result.txts:
    raise RuntimeError('OCR model preparation failed')
print('OCR detection, classification, and recognition models ready')
