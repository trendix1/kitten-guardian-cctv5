from __future__ import annotations

import os
import time

import cv2
import numpy as np


class SnapshotStorage:
    """Menyimpan foto hasil deteksi gerakan saja.
    Frame yang tidak ada gerakan TIDAK PERNAH disimpan."""

    def __init__(self, base_dir: str = "captures"):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def _new_path(self, tag: str = "") -> str:
        ts = time.strftime("%Y%m%d_%H%M%S")
        ms = int((time.time() % 1) * 1000)
        suffix = f"_{tag}" if tag else ""
        return os.path.join(self.base_dir, f"motion_{ts}_{ms:03d}{suffix}.jpg")

    def save_single(self, frame_bgr: np.ndarray) -> str:
        path = self._new_path()
        cv2.imwrite(path, frame_bgr)
        return path

    def save_frame_in_burst(self, frame_bgr: np.ndarray, index: int) -> str:
        path = self._new_path(tag=f"b{index}")
        cv2.imwrite(path, frame_bgr)
        return path
