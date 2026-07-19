from __future__ import annotations

import threading
import time


class AlarmPlayer:
    """Membunyikan alarm beep berulang di background thread.
    Menggunakan winsound (Windows) dan fallback bell karakter di OS lain."""

    def __init__(self, freq_hz: int = 1400, beep_ms: int = 280, gap_s: float = 0.15):
        self.freq_hz = freq_hz
        self.beep_ms = beep_ms
        self.gap_s = gap_s
        self._stop_flag = threading.Event()
        self._thread: threading.Thread | None = None

    def _loop(self, duration_s: float | None):
        start = time.monotonic()
        try:
            import winsound

            def beep_once():
                winsound.Beep(self.freq_hz, self.beep_ms)
        except ImportError:
            def beep_once():
                print("\a", end="", flush=True)
                time.sleep(self.beep_ms / 1000.0)

        while not self._stop_flag.is_set():
            beep_once()
            if duration_s is not None and (time.monotonic() - start) >= duration_s:
                break
            self._stop_flag.wait(self.gap_s)

    def play(self, duration_s: float | None = 2.5):
        self.stop()
        self._stop_flag.clear()
        self._thread = threading.Thread(target=self._loop, args=(duration_s,), daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_flag.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None

    @property
    def is_playing(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
