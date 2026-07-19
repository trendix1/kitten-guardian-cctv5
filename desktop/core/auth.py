from __future__ import annotations

import json
import os
import re
import secrets
import string
import time
from dataclasses import dataclass, asdict

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")


@dataclass
class AuthConfig:
    camera_id: str = "kitten-cam-01"
    password: str = ""
    mode: str = "static"  # "static" atau "rotating"
    rotate_interval_hours: int = 3
    last_rotated_at: float = 0.0


class AuthManager:
    """Mengelola ID kamera + password untuk autentikasi koneksi.
    Mode 'static': password kuat yang tidak berubah otomatis.
    Mode 'rotating': password baru dibuat otomatis tiap beberapa jam
    dan didorong (push) ke client yang sedang terhubung."""

    MIN_LENGTH = 10

    def __init__(self, path: str = CONFIG_PATH):
        self.path = path
        self.config = self._load()
        if not self.config.password:
            self.config.password = self.generate_strong_password()
            self._save()

    def _load(self) -> AuthConfig:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                merged = {**asdict(AuthConfig()), **data}
                return AuthConfig(**merged)
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        return AuthConfig()

    def _save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(asdict(self.config), f, indent=2)

    def validate(self, camera_id: str, password: str) -> bool:
        return camera_id == self.config.camera_id and password == self.config.password

    def set_camera_id(self, camera_id: str):
        camera_id = camera_id.strip()
        if camera_id:
            self.config.camera_id = camera_id
            self._save()

    def set_static_password(self, password: str) -> tuple[bool, str]:
        ok, reason = self.check_strength(password)
        if not ok:
            return False, reason
        self.config.mode = "static"
        self.config.password = password
        self._save()
        return True, "OK"

    def enable_rotation(self, interval_hours: int = 3) -> str:
        self.config.mode = "rotating"
        self.config.rotate_interval_hours = interval_hours
        return self.rotate_now()

    def rotate_now(self) -> str:
        new_password = self.generate_strong_password()
        self.config.password = new_password
        self.config.last_rotated_at = time.time()
        self._save()
        return new_password

    def seconds_until_next_rotation(self) -> float:
        if self.config.mode != "rotating":
            return -1.0
        interval_s = self.config.rotate_interval_hours * 3600
        elapsed = time.time() - self.config.last_rotated_at
        return max(0.0, interval_s - elapsed)

    def rotation_due(self) -> bool:
        return self.config.mode == "rotating" and self.seconds_until_next_rotation() <= 0

    @staticmethod
    def generate_strong_password(length: int = 12) -> str:
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        while True:
            pwd = "".join(secrets.choice(alphabet) for _ in range(length))
            ok, _ = AuthManager.check_strength(pwd)
            if ok:
                return pwd

    @staticmethod
    def check_strength(password: str) -> tuple[bool, str]:
        if len(password) < AuthManager.MIN_LENGTH:
            return False, f"Password minimal {AuthManager.MIN_LENGTH} karakter"
        if not re.search(r"[a-z]", password):
            return False, "Harus ada huruf kecil"
        if not re.search(r"[A-Z]", password):
            return False, "Harus ada huruf besar"
        if not re.search(r"\d", password):
            return False, "Harus ada angka"
        return True, "OK"
