from __future__ import annotations

import json
import struct
import time

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtNetwork import QTcpServer, QTcpSocket, QHostAddress

from .protocol import (
    MSG_FRAME,
    MSG_TELEMETRY,
    MSG_COMMAND,
    MSG_PING,
    MSG_PONG,
    MSG_AUTH,
    MSG_AUTH_RESULT,
    HEADER_SIZE,
    pack_message,
)


class CameraServer(QObject):
    """Server TCP yang menerima 1 koneksi kamera (Android) sekaligus."""

    frame_received = pyqtSignal(bytes)
    telemetry_received = pyqtSignal(dict)
    client_connected = pyqtSignal(str)
    client_disconnected = pyqtSignal()
    log_message = pyqtSignal(str)
    ping_updated = pyqtSignal(float)
    auth_status_changed = pyqtSignal(bool)
    pairing_completed = pyqtSignal(str)

    def __init__(self, port: int = 8765, parent=None):
        super().__init__(parent)
        self.port = port
        self.server = QTcpServer(self)
        self.server.newConnection.connect(self._on_new_connection)
        self.socket: QTcpSocket | None = None
        self._buffer = bytearray()
        self._ping_start = 0.0
        self._ping_token = ""
        self._authenticated = False
        # Callable(camera_id: str, password: str) -> bool, di-set dari MainWindow.
        self.auth_validator = None
        # Callable() -> bool, True jika Mode Pairing sedang aktif.
        self.pairing_mode_provider = None
        # Callable() -> tuple[str, str], mengembalikan (camera_id, password) aktif.
        self.credentials_provider = None

    def start(self) -> bool:
        if not self.server.listen(QHostAddress.Any, self.port):
            self.log_message.emit(f"Gagal membuka port {self.port}: {self.server.errorString()}")
            return False
        self.log_message.emit(f"Server aktif di port {self.port}, menunggu kamera...")
        return True

    def stop(self):
        if self.socket is not None:
            self.socket.disconnectFromHost()
            self.socket = None
        self.server.close()
        self.log_message.emit("Server dihentikan")

    def _on_new_connection(self):
        pending = self.server.nextPendingConnection()
        if self.socket is not None:
            # Hanya izinkan 1 kamera aktif dalam satu waktu.
            pending.disconnectFromHost()
            pending.deleteLater()
            self.log_message.emit("Koneksi tambahan ditolak (sudah ada kamera aktif)")
            return

        self.socket = pending
        self.socket.readyRead.connect(self._on_ready_read)
        self.socket.disconnected.connect(self._on_disconnected)
        self._authenticated = False
        self.auth_status_changed.emit(False)
        peer = self.socket.peerAddress().toString().replace("::ffff:", "")
        self.client_connected.emit(peer)
        self.log_message.emit(f"Kamera terhubung dari {peer}, menunggu autentikasi...")

    def _on_disconnected(self):
        self.log_message.emit("Kamera terputus")
        self.socket = None
        self._buffer.clear()
        self._authenticated = False
        self.auth_status_changed.emit(False)
        self.client_disconnected.emit()

    def _on_ready_read(self):
        if self.socket is None:
            return
        self._buffer.extend(bytes(self.socket.readAll()))
        while True:
            if len(self._buffer) < HEADER_SIZE:
                return
            msg_type, length = struct.unpack(">BI", self._buffer[:HEADER_SIZE])
            if len(self._buffer) < HEADER_SIZE + length:
                return
            payload = bytes(self._buffer[HEADER_SIZE:HEADER_SIZE + length])
            del self._buffer[:HEADER_SIZE + length]
            self._handle_message(msg_type, payload)

    def _handle_message(self, msg_type: int, payload: bytes):
        if msg_type == MSG_AUTH:
            self._handle_auth(payload)
            return

        if not self._authenticated:
            # Abaikan semua data sebelum autentikasi berhasil.
            return

        if msg_type == MSG_FRAME:
            self.frame_received.emit(payload)
        elif msg_type == MSG_TELEMETRY:
            try:
                data = json.loads(payload.decode("utf-8"))
                self.telemetry_received.emit(data)
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
        elif msg_type == MSG_PONG:
            if payload.decode("utf-8", "ignore") == self._ping_token:
                latency_ms = (time.monotonic() - self._ping_start) * 1000.0
                self.ping_updated.emit(latency_ms)

    def _handle_auth(self, payload: bytes):
        try:
            data = json.loads(payload.decode("utf-8"))
            camera_id = str(data.get("camera_id", ""))
            password = str(data.get("password", ""))
        except (json.JSONDecodeError, UnicodeDecodeError):
            camera_id, password = "", ""

        ok = self.auth_validator(camera_id, password) if self.auth_validator else True
        is_pairing = False

        if not ok and self.pairing_mode_provider is not None and self.pairing_mode_provider():
            # Mode Pairing aktif: terima kamera baru tanpa perlu ID/password cocok,
            # lalu langsung dorongkan kredensial resmi ke kamera tersebut.
            ok = True
            is_pairing = True

        self._authenticated = ok
        self.auth_status_changed.emit(ok)

        if self.socket is not None:
            result_payload = json.dumps({"ok": ok}).encode("utf-8")
            self.socket.write(pack_message(MSG_AUTH_RESULT, result_payload))

        if ok and is_pairing:
            real_id, real_password = ("", "")
            if self.credentials_provider is not None:
                real_id, real_password = self.credentials_provider()
            self.send_command("set_credentials", camera_id=real_id, password=real_password)
            self.log_message.emit(f"Kamera baru dipasangkan (pairing) dengan ID: {real_id}")
            self.pairing_completed.emit(real_id)
        elif ok:
            self.log_message.emit(f"Autentikasi berhasil ({camera_id})")
        else:
            self.log_message.emit(f"Autentikasi GAGAL ({camera_id}) - koneksi ditolak")
            if self.socket is not None:
                self.socket.disconnectFromHost()

    def send_command(self, cmd: str, **kwargs):
        if not self.is_connected:
            return
        payload = json.dumps({"cmd": cmd, **kwargs}).encode("utf-8")
        self.socket.write(pack_message(MSG_COMMAND, payload))

    def send_ping(self):
        if not self.is_connected:
            return
        self._ping_token = f"{time.monotonic():.6f}"
        self._ping_start = time.monotonic()
        self.socket.write(pack_message(MSG_PING, self._ping_token.encode("utf-8")))

    @property
    def is_connected(self) -> bool:
        return self.socket is not None and self.socket.state() == QTcpSocket.ConnectedState

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated
