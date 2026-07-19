from __future__ import annotations

import time

import cv2
import numpy as np
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap, QKeyEvent
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QTextEdit, QComboBox, QSpinBox, QLineEdit, QFormLayout,
    QSizePolicy, QSplitter, QTabWidget, QFrame,
)

from core.server import CameraServer
from core.motion_detector import MotionDetector
from core.alarm import AlarmPlayer
from core.storage import SnapshotStorage
from core.auth import AuthManager
from core.protocol import DEFAULT_PORT
from gui.theme import DARK_STYLESHEET
from gui.widgets import StatusRow


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kitten Guardian CCTV")
        self.resize(1280, 760)
        self.setStyleSheet(DARK_STYLESHEET)

        self.server = CameraServer(port=DEFAULT_PORT)
        self.motion_detector = MotionDetector()
        self.alarm = AlarmPlayer()
        self.storage = SnapshotStorage()
        self.auth = AuthManager()
        self.server.auth_validator = self.auth.validate
        self.server.pairing_mode_provider = lambda: self.btn_pairing_mode.isChecked()
        self.server.credentials_provider = lambda: (self.auth.config.camera_id, self.auth.config.password)

        self._latest_frame: np.ndarray | None = None
        self._burst_frames_left = 0
        self._burst_index = 0
        self._motion_active_until = 0.0
        self._is_fullscreen = False

        self._fps_counter = 0
        self._fps_value = 0

        self._build_ui()
        self._connect_signals()
        self._refresh_auth_display()

        self._fps_timer = QTimer(self)
        self._fps_timer.setInterval(1000)
        self._fps_timer.timeout.connect(self._update_fps)
        self._fps_timer.start()

        self._ping_timer = QTimer(self)
        self._ping_timer.setInterval(2000)
        self._ping_timer.timeout.connect(self.server.send_ping)

        self._burst_timer = QTimer(self)
        self._burst_timer.setInterval(220)
        self._burst_timer.timeout.connect(self._capture_burst_step)

        self._motion_reset_timer = QTimer(self)
        self._motion_reset_timer.setInterval(300)
        self._motion_reset_timer.timeout.connect(self._maybe_clear_motion_banner)

        self._rotation_timer = QTimer(self)
        self._rotation_timer.setInterval(60_000)
        self._rotation_timer.timeout.connect(self._check_password_rotation)
        self._rotation_timer.start()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, stretch=1)

        # ================= Panel kiri: video =================
        left_panel = QWidget()
        left_col = QVBoxLayout(left_panel)
        left_col.setContentsMargins(0, 0, 0, 0)
        left_col.setSpacing(8)

        self.warning_label = QLabel("")
        self.warning_label.setObjectName("WarningLabel")
        self.warning_label.setAlignment(Qt.AlignCenter)
        self.warning_label.setFixedHeight(28)
        left_col.addWidget(self.warning_label)

        self.video_label = QLabel("Menunggu kamera terhubung...")
        self.video_label.setObjectName("VideoLabel")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(560, 400)
        self.video_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left_col.addWidget(self.video_label, stretch=1)

        splitter.addWidget(left_panel)

        # ================= Panel kanan: tab-tab terpisah =================
        right_panel = QTabWidget()
        right_panel.setMinimumWidth(340)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        right_panel.addTab(self._build_tab_status(), "Status")
        right_panel.addTab(self._build_tab_security(), "Keamanan")
        right_panel.addTab(self._build_tab_log(), "Log")

        # ================= Bar kontrol bawah =================
        control_frame = QFrame()
        control_frame.setObjectName("ControlBar")
        controls = QHBoxLayout(control_frame)
        controls.setContentsMargins(12, 10, 12, 10)
        controls.setSpacing(8)

        self.btn_start = QPushButton("Start")
        self.btn_start.setObjectName("PrimaryButton")
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setObjectName("DangerButton")
        self.btn_stop.setEnabled(False)
        self.btn_flash = QPushButton("Flash: OFF")
        self.btn_flash_blink = QPushButton("Flash Blink x4")
        self.btn_alarm_test = QPushButton("Alarm Test")
        self.btn_pest_alarm = QPushButton("Usir Hewan")
        self.btn_pest_alarm.setObjectName("DangerButton")
        self.btn_fullscreen = QPushButton("Fullscreen")

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Mode 1: 1 Foto", 1)
        self.mode_combo.addItem("Mode 2: 4 Foto Berurutan", 2)

        controls.addWidget(self.btn_start)
        controls.addWidget(self.btn_stop)
        controls.addSpacing(12)
        controls.addWidget(self.btn_flash)
        controls.addWidget(self.btn_flash_blink)
        controls.addSpacing(12)
        controls.addWidget(self.btn_alarm_test)
        controls.addWidget(self.btn_pest_alarm)
        controls.addStretch(1)
        controls.addWidget(self.mode_combo)
        controls.addWidget(self.btn_fullscreen)

        root.addWidget(control_frame)

    def _build_tab_status(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(14)

        conn_group = QGroupBox("Koneksi")
        conn_form = QFormLayout(conn_group)
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(DEFAULT_PORT)
        conn_form.addRow("Port Server:", self.port_spin)
        layout.addWidget(conn_group)

        status_group = QGroupBox("Status Koneksi")
        status_layout = QVBoxLayout(status_group)
        self.row_connection = StatusRow("Connection")
        self.row_auth = StatusRow("Autentikasi")
        self.row_fps = StatusRow("FPS")
        self.row_ping = StatusRow("Ping")
        self.row_motion = StatusRow("Motion Status")
        for row in (self.row_connection, self.row_auth, self.row_fps, self.row_ping, self.row_motion):
            status_layout.addWidget(row)
        layout.addWidget(status_group)

        mon_group = QGroupBox("Monitoring Kamera (Android)")
        mon_layout = QVBoxLayout(mon_group)
        self.row_battery = StatusRow("Battery")
        self.row_charging = StatusRow("Charging")
        self.row_temperature = StatusRow("Temperature")
        self.row_voltage = StatusRow("Voltage")
        self.row_ip = StatusRow("IP Address")
        self.row_wifi = StatusRow("WiFi Status")
        for row in (
            self.row_battery, self.row_charging, self.row_temperature,
            self.row_voltage, self.row_ip, self.row_wifi,
        ):
            mon_layout.addWidget(row)
        layout.addWidget(mon_group)

        layout.addStretch(1)
        return tab

    def _build_tab_security(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(14)

        auth_group = QGroupBox("ID & Password Kamera")
        auth_form = QFormLayout(auth_group)
        auth_form.setVerticalSpacing(10)

        self.edit_camera_id = QLineEdit(self.auth.config.camera_id)
        auth_form.addRow("Camera ID:", self.edit_camera_id)

        self.password_mode_combo = QComboBox()
        self.password_mode_combo.addItem("Password Tetap (Static)", "static")
        self.password_mode_combo.addItem("Rotasi Otomatis tiap 3 Jam", "rotating")
        idx = 0 if self.auth.config.mode == "static" else 1
        self.password_mode_combo.setCurrentIndex(idx)
        auth_form.addRow("Mode Password:", self.password_mode_combo)

        self.edit_password = QLineEdit(self.auth.config.password)
        self.edit_password.setEchoMode(QLineEdit.Normal)
        auth_form.addRow("Password:", self.edit_password)

        pw_btn_row = QHBoxLayout()
        self.btn_generate_password = QPushButton("Generate Kuat")
        self.btn_save_auth = QPushButton("Simpan")
        self.btn_save_auth.setObjectName("PrimaryButton")
        pw_btn_row.addWidget(self.btn_generate_password)
        pw_btn_row.addWidget(self.btn_save_auth)
        auth_form.addRow("", pw_btn_row)

        self.label_rotation_info = QLabel("")
        self.label_rotation_info.setWordWrap(True)
        auth_form.addRow(self.label_rotation_info)

        layout.addWidget(auth_group)

        pairing_group = QGroupBox("Pairing Kamera Baru")
        pairing_layout = QVBoxLayout(pairing_group)
        pairing_layout.setSpacing(10)

        self.btn_pairing_mode = QPushButton("Mode Pairing: OFF")
        self.btn_pairing_mode.setCheckable(True)
        self.btn_pairing_mode.setObjectName("PrimaryButton")
        pairing_layout.addWidget(self.btn_pairing_mode)

        self.label_pairing_info = QLabel(
            "Aktifkan Mode Pairing, lalu tekan Start Streaming di HP (tanpa perlu isi ID/password). "
            "HP otomatis menerima kredensial yang benar dan tersimpan untuk seterusnya."
        )
        self.label_pairing_info.setWordWrap(True)
        pairing_layout.addWidget(self.label_pairing_info)

        layout.addWidget(pairing_group)
        layout.addStretch(1)
        return tab

    def _build_tab_log(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)

        self.log_view = QTextEdit()
        self.log_view.setObjectName("LogView")
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)
        return tab

    def _connect_signals(self):
        self.btn_start.clicked.connect(self._on_start)
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_flash.clicked.connect(self._on_toggle_flash)
        self.btn_flash_blink.clicked.connect(self._on_flash_blink)
        self.btn_alarm_test.clicked.connect(lambda: self.alarm.play(duration_s=2.0))
        self.btn_pest_alarm.clicked.connect(self._on_pest_alarm)
        self.btn_fullscreen.clicked.connect(self._toggle_fullscreen)
        self.btn_generate_password.clicked.connect(self._on_generate_password)
        self.btn_save_auth.clicked.connect(self._on_save_auth)
        self.btn_pairing_mode.toggled.connect(self._on_pairing_toggled)

        self.server.frame_received.connect(self._on_frame_received)
        self.server.telemetry_received.connect(self._on_telemetry_received)
        self.server.client_connected.connect(self._on_client_connected)
        self.server.client_disconnected.connect(self._on_client_disconnected)
        self.server.auth_status_changed.connect(self._on_auth_status_changed)
        self.server.pairing_completed.connect(self._on_pairing_completed)
        self.server.log_message.connect(self._log)
        self.server.ping_updated.connect(self._on_ping_updated)

    # --------------------------------------------------------------- Slots
    def _on_start(self):
        self.server.port = self.port_spin.value()
        if self.server.start():
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)
            self.port_spin.setEnabled(False)
            self._ping_timer.start()
            self._motion_reset_timer.start()

    def _on_stop(self):
        self.server.stop()
        self.alarm.stop()
        self._ping_timer.stop()
        self._burst_timer.stop()
        self._motion_reset_timer.stop()
        self.motion_detector.reset()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.port_spin.setEnabled(True)
        self.row_connection.set_value("Disconnected", "valueBad")
        self.row_auth.set_value("-")
        self.video_label.setText("Menunggu kamera terhubung...")
        self.video_label.setPixmap(QPixmap())

    def _on_toggle_flash(self):
        turning_on = self.btn_flash.text().endswith("OFF")
        self.server.send_command("flash_on" if turning_on else "flash_off")
        self.btn_flash.setText("Flash: ON" if turning_on else "Flash: OFF")
        self._log(f"Flash {'ON' if turning_on else 'OFF'} dikirim")

    def _on_flash_blink(self):
        self.server.send_command("flash_blink")
        self._log("Perintah kedip senter x4 dikirim ke kamera")

    def _on_pest_alarm(self):
        self.server.send_command("pest_alarm", duration_s=5)
        self._log("Perintah alarm usir hewan (tikus dll) dikirim ke kamera")

    def _toggle_fullscreen(self):
        self._is_fullscreen = not self._is_fullscreen
        if self._is_fullscreen:
            self.showFullScreen()
            self.btn_fullscreen.setText("Keluar Fullscreen (Esc)")
        else:
            self.showNormal()
            self.btn_fullscreen.setText("Fullscreen")

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_F11:
            self._toggle_fullscreen()
        elif event.key() == Qt.Key_Escape and self._is_fullscreen:
            self._toggle_fullscreen()
        else:
            super().keyPressEvent(event)

    def _on_client_connected(self, peer: str):
        self.row_connection.set_value(f"Connected ({peer})", "value")
        self.row_auth.set_value("Menunggu...", "valueWarn")
        self.row_ip.set_value(peer)

    def _on_client_disconnected(self):
        self.row_connection.set_value("Disconnected", "valueBad")
        self.row_auth.set_value("-")
        self.row_fps.set_value("0")
        self.row_ping.set_value("-")
        self.motion_detector.reset()
        self.video_label.setText("Kamera terputus, menunggu reconnect...")

    def _on_auth_status_changed(self, ok: bool):
        if ok:
            self.row_auth.set_value("Terverifikasi", "value")
        else:
            self.row_auth.set_value("Ditolak", "valueBad")

    def _on_pairing_toggled(self, checked: bool):
        if checked:
            self.btn_pairing_mode.setText("Mode Pairing: ON (menunggu kamera baru...)")
            self._log("Mode Pairing diaktifkan - kamera baru akan diterima otomatis")
        else:
            self.btn_pairing_mode.setText("Mode Pairing: OFF")

    def _on_pairing_completed(self, camera_id: str):
        self.btn_pairing_mode.setChecked(False)
        self._log(f"Pairing selesai untuk kamera: {camera_id}")

    def _on_ping_updated(self, latency_ms: float):
        role = "value" if latency_ms < 150 else ("valueWarn" if latency_ms < 400 else "valueBad")
        self.row_ping.set_value(f"{latency_ms:.0f} ms", role)

    def _on_telemetry_received(self, data: dict):
        battery = data.get("battery_pct")
        if battery is not None:
            role = "value" if battery > 30 else ("valueWarn" if battery > 15 else "valueBad")
            self.row_battery.set_value(f"{battery}%", role)

        charging = data.get("charging")
        if charging is not None:
            self.row_charging.set_value("Ya" if charging else "Tidak")

        temp = data.get("temperature_c")
        if temp is not None:
            role = "value" if temp < 40 else ("valueWarn" if temp < 45 else "valueBad")
            self.row_temperature.set_value(f"{temp:.1f} \u00b0C", role)

        voltage = data.get("voltage_v")
        if voltage is not None:
            self.row_voltage.set_value(f"{voltage:.2f} V")

        ip = data.get("ip_address")
        if ip:
            self.row_ip.set_value(ip)

        wifi_status = data.get("wifi_status")
        if wifi_status:
            self.row_wifi.set_value(wifi_status)

    def _on_frame_received(self, jpeg_bytes: bytes):
        self._fps_counter += 1
        arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return

        self._latest_frame = frame

        motion = self.motion_detector.detect(frame)
        if motion:
            self._trigger_motion(frame)

        self._render_frame(frame)

    # ------------------------------------------------------------- Motion
    def _trigger_motion(self, frame: np.ndarray):
        self.row_motion.set_value("ADA PERGERAKAN", "valueBad")
        self.warning_label.setText("PERINGATAN - ADA PERGERAKAN")
        self._motion_active_until = time.monotonic() + 2.0

        if not self.alarm.is_playing:
            self.alarm.play(duration_s=2.5)

        mode = self.mode_combo.currentData()
        if mode == 1:
            path = self.storage.save_single(frame)
            self._log(f"Gerakan terdeteksi -> disimpan: {path}")
        else:
            if self._burst_frames_left == 0:
                self._burst_frames_left = 4
                self._burst_index = 0
                self._log("Gerakan terdeteksi -> mengambil 4 foto berurutan...")
                self._capture_burst_step()
                self._burst_timer.start()

    def _capture_burst_step(self):
        if self._burst_frames_left <= 0 or self._latest_frame is None:
            self._burst_timer.stop()
            return
        path = self.storage.save_frame_in_burst(self._latest_frame, self._burst_index)
        self._log(f"  foto burst {self._burst_index + 1}/4 -> {path}")
        self._burst_index += 1
        self._burst_frames_left -= 1
        if self._burst_frames_left == 0:
            self._burst_timer.stop()

    def _maybe_clear_motion_banner(self):
        if self._motion_active_until and time.monotonic() > self._motion_active_until:
            self.warning_label.setText("")
            self.row_motion.set_value("Aman", "value")
            self._motion_active_until = 0.0

    # ----------------------------------------------------- Auth / Password
    def _refresh_auth_display(self):
        self.edit_camera_id.setText(self.auth.config.camera_id)
        self.edit_password.setText(self.auth.config.password)
        if self.auth.config.mode == "rotating":
            remaining = self.auth.seconds_until_next_rotation()
            mins = int(remaining // 60)
            self.label_rotation_info.setText(
                f"Rotasi otomatis aktif. Password berikutnya dalam kurang lebih {mins} menit. "
                f"Password otomatis diperbarui di HP selama koneksi tetap aktif."
            )
            self.edit_password.setEnabled(False)
        else:
            self.label_rotation_info.setText(
                "Password tetap, tidak berubah otomatis. Pastikan cukup kuat & rahasia."
            )
            self.edit_password.setEnabled(True)

    def _on_generate_password(self):
        new_pw = AuthManager.generate_strong_password()
        self.edit_password.setText(new_pw)
        self._log("Password kuat baru dibuat (klik Simpan untuk menerapkan)")

    def _on_save_auth(self):
        self.auth.set_camera_id(self.edit_camera_id.text())

        mode = self.password_mode_combo.currentData()
        if mode == "rotating":
            new_pw = self.auth.enable_rotation(interval_hours=3)
            self._log(f"Mode password: rotasi otomatis tiap 3 jam. Password baru: {new_pw}")
            self._push_new_credentials(new_pw)
        else:
            ok, reason = self.auth.set_static_password(self.edit_password.text())
            if not ok:
                self._log(f"Password ditolak: {reason}")
                return
            self._log("Mode password: statis, tersimpan.")
            self._push_new_credentials(self.auth.config.password)

        self._refresh_auth_display()

    def _check_password_rotation(self):
        if self.auth.rotation_due():
            new_pw = self.auth.rotate_now()
            self._log(f"Password dirotasi otomatis: {new_pw}")
            self._push_new_credentials(new_pw)
            self._refresh_auth_display()
        elif self.auth.config.mode == "rotating":
            self._refresh_auth_display()

    def _push_new_credentials(self, new_password: str):
        if self.server.is_connected and self.server.is_authenticated:
            self.server.send_command("update_credentials", password=new_password)
            self._log("Password baru dikirim ke kamera yang sedang terhubung")

    # --------------------------------------------------------------- Misc
    def _render_frame(self, frame_bgr: np.ndarray):
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg).scaled(
            self.video_label.width(), self.video_label.height(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation,
        )
        self.video_label.setPixmap(pixmap)

    def _update_fps(self):
        self._fps_value = self._fps_counter
        self._fps_counter = 0
        role = "value" if self._fps_value >= 5 else ("valueWarn" if self._fps_value > 0 else "valueBad")
        self.row_fps.set_value(str(self._fps_value), role)

    def _log(self, message: str):
        ts = time.strftime("%H:%M:%S")
        self.log_view.append(f"[{ts}] {message}")

    def closeEvent(self, event):
        self.alarm.stop()
        self.server.stop()
        super().closeEvent(event)
