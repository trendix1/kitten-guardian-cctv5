package com.kittenguardian.cctv

import android.util.Log
import kotlinx.coroutines.*
import org.json.JSONObject
import java.io.DataInputStream
import java.io.DataOutputStream
import java.net.InetSocketAddress
import java.net.Socket
import java.util.concurrent.LinkedBlockingQueue

/**
 * Mengelola koneksi TCP ke Desktop Server: reconnect otomatis, autentikasi
 * (Camera ID + Password), antrian pengiriman (frame + telemetry), dan
 * pembacaan command dari server.
 */
class NetworkClient(
    private val host: String,
    private val port: Int,
    private val cameraId: String,
    private val password: String,
    private val scope: CoroutineScope,
    private val onConnectionChanged: (Boolean) -> Unit,
    private val onAuthResult: (Boolean) -> Unit,
    private val onCommand: (String, JSONObject) -> Unit,
) {
    companion object {
        private const val TAG = "NetworkClient"
        private const val RECONNECT_DELAY_MS = 3000L
        private const val AUTH_FAIL_RECONNECT_DELAY_MS = 10000L
    }

    @Volatile private var running = false
    @Volatile private var connected = false
    @Volatile private var lastAuthFailed = false
    private var socket: Socket? = null
    private var output: DataOutputStream? = null

    private val sendQueue = LinkedBlockingQueue<ByteArray>(30)
    private var writerJob: Job? = null
    private var readerJob: Job? = null
    private var connectJob: Job? = null

    val isConnected: Boolean get() = connected

    fun start() {
        if (running) return
        running = true
        connectJob = scope.launch(Dispatchers.IO) { connectLoop() }
    }

    fun stop() {
        running = false
        connectJob?.cancel()
        writerJob?.cancel()
        readerJob?.cancel()
        closeSocketQuietly()
        sendQueue.clear()
    }

    fun sendFrame(jpegBytes: ByteArray) {
        offer(Protocol.pack(Protocol.MSG_FRAME, jpegBytes))
    }

    fun sendTelemetry(json: JSONObject) {
        offer(Protocol.pack(Protocol.MSG_TELEMETRY, json.toString().toByteArray(Charsets.UTF_8)))
    }

    private fun sendPong(token: String) {
        offer(Protocol.pack(Protocol.MSG_PONG, token.toByteArray(Charsets.UTF_8)))
    }

    private fun sendAuth() {
        val json = JSONObject()
        json.put("camera_id", cameraId)
        json.put("password", password)
        offer(Protocol.pack(Protocol.MSG_AUTH, json.toString().toByteArray(Charsets.UTF_8)))
    }

    private fun offer(data: ByteArray) {
        if (!connected) return
        if (!sendQueue.offer(data)) {
            sendQueue.poll()
            sendQueue.offer(data)
        }
    }

    private suspend fun connectLoop() {
        while (running) {
            try {
                Log.i(TAG, "Menghubungkan ke $host:$port ...")
                val s = Socket()
                s.tcpNoDelay = true
                s.keepAlive = true
                s.connect(InetSocketAddress(host, port), 5000)
                socket = s
                output = DataOutputStream(s.getOutputStream())
                connected = true
                onConnectionChanged(true)
                Log.i(TAG, "Terhubung ke server, mengirim autentikasi...")

                writerJob = scope.launch(Dispatchers.IO) { writerLoop(s) }
                readerJob = scope.launch(Dispatchers.IO) { readerLoop(s) }

                sendAuth()

                writerJob?.join()
                readerJob?.join()
            } catch (e: Exception) {
                Log.w(TAG, "Koneksi gagal: ${e.message}")
            } finally {
                connected = false
                onConnectionChanged(false)
                closeSocketQuietly()
            }

            if (running) {
                val delayMs = if (lastAuthFailed) AUTH_FAIL_RECONNECT_DELAY_MS else RECONNECT_DELAY_MS
                delay(delayMs)
            }
        }
    }

    private fun writerLoop(s: Socket) {
        try {
            val out = output ?: return
            while (running && !s.isClosed) {
                val data = sendQueue.poll(1, java.util.concurrent.TimeUnit.SECONDS) ?: continue
                out.write(data)
                out.flush()
            }
        } catch (e: Exception) {
            Log.w(TAG, "Writer error: ${e.message}")
        }
    }

    private fun readerLoop(s: Socket) {
        try {
            val input = DataInputStream(s.getInputStream())
            while (running && !s.isClosed) {
                val msgType = input.readUnsignedByte()
                val length = input.readInt()
                val payload = ByteArray(length)
                input.readFully(payload)

                when (msgType) {
                    Protocol.MSG_COMMAND -> {
                        val json = JSONObject(String(payload, Charsets.UTF_8))
                        val cmd = json.optString("cmd")
                        onCommand(cmd, json)
                    }
                    Protocol.MSG_PING -> {
                        sendPong(String(payload, Charsets.UTF_8))
                    }
                    Protocol.MSG_AUTH_RESULT -> {
                        val json = JSONObject(String(payload, Charsets.UTF_8))
                        val ok = json.optBoolean("ok", false)
                        lastAuthFailed = !ok
                        onAuthResult(ok)
                        if (!ok) {
                            Log.w(TAG, "Autentikasi ditolak server, cek Camera ID / Password")
                        }
                    }
                }
            }
        } catch (e: Exception) {
            Log.w(TAG, "Reader error: ${e.message}")
        }
    }

    private fun closeSocketQuietly() {
        try {
            output?.close()
        } catch (_: Exception) {
        }
        try {
            socket?.close()
        } catch (_: Exception) {
        }
        socket = null
        output = null
    }
}
