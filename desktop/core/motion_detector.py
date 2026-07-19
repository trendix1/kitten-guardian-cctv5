from __future__ import annotations

import cv2
import numpy as np


class MotionDetector:
    """Deteksi gerakan sederhana dengan membandingkan frame sebelumnya
    dan frame sekarang (frame differencing)."""

    def __init__(self, min_area: int = 900, threshold: int = 25, blur_ksize: int = 21):
        self.min_area = min_area
        self.threshold = threshold
        self.blur_ksize = blur_ksize if blur_ksize % 2 == 1 else blur_ksize + 1
        self._prev_gray: np.ndarray | None = None

    def reset(self):
        self._prev_gray = None

    def detect(self, frame_bgr: np.ndarray) -> bool:
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (self.blur_ksize, self.blur_ksize), 0)

        if self._prev_gray is None:
            self._prev_gray = gray
            return False

        if self._prev_gray.shape != gray.shape:
            # Resolusi berubah (mis. reconnect), reset baseline.
            self._prev_gray = gray
            return False

        frame_delta = cv2.absdiff(self._prev_gray, gray)
        thresh = cv2.threshold(frame_delta, self.threshold, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        self._prev_gray = gray

        for c in contours:
            if cv2.contourArea(c) >= self.min_area:
                return True
        return False
