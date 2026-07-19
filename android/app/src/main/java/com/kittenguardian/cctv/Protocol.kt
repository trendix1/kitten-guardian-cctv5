package com.kittenguardian.cctv

import java.io.ByteArrayOutputStream
import java.io.DataOutputStream

/**
 * Format frame: [1 byte msg_type][4 byte length big-endian][payload]
 * Harus sama persis dengan desktop/core/protocol.py
 */
object Protocol {
    const val MSG_FRAME: Int = 0x01
    const val MSG_TELEMETRY: Int = 0x02
    const val MSG_COMMAND: Int = 0x03
    const val MSG_PING: Int = 0x04
    const val MSG_PONG: Int = 0x05
    const val MSG_AUTH: Int = 0x06
    const val MSG_AUTH_RESULT: Int = 0x07

    const val HEADER_SIZE = 5
    const val DEFAULT_PORT = 8765

    fun pack(msgType: Int, payload: ByteArray): ByteArray {
        val out = ByteArrayOutputStream(Protocol.HEADER_SIZE + payload.size)
        val dos = DataOutputStream(out)
        dos.writeByte(msgType)
        dos.writeInt(payload.size) // DataOutputStream writeInt = big-endian
        dos.write(payload)
        return out.toByteArray()
    }
}
