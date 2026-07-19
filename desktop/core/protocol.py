"""
Protokol komunikasi TCP antara Android (client) dan Desktop (server).

Frame format:
    [1 byte msg_type][4 byte length (big-endian uint32)][payload]

Message types:
    0x01 FRAME      -> payload = JPEG bytes (Android -> Desktop)
    0x02 TELEMETRY  -> payload = JSON utf-8 (Android -> Desktop)
    0x03 COMMAND    -> payload = JSON utf-8 (Desktop -> Android)
    0x04 PING       -> payload = token string (Desktop -> Android)
    0x05 PONG       -> payload = token string (Android -> Desktop)
    0x06 AUTH       -> payload = JSON {"camera_id":.., "password":..} (Android -> Desktop)
    0x07 AUTH_RESULT-> payload = JSON {"ok": bool} (Desktop -> Android)
"""
import struct

MSG_FRAME = 0x01
MSG_TELEMETRY = 0x02
MSG_COMMAND = 0x03
MSG_PING = 0x04
MSG_PONG = 0x05
MSG_AUTH = 0x06
MSG_AUTH_RESULT = 0x07

HEADER_SIZE = 5  # 1 + 4 bytes
DEFAULT_PORT = 8765


def pack_message(msg_type: int, payload: bytes) -> bytes:
    return struct.pack(">BI", msg_type, len(payload)) + payload


def unpack_header(header: bytes):
    msg_type, length = struct.unpack(">BI", header)
    return msg_type, length
