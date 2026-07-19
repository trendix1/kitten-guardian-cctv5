package com.kittenguardian.cctv

import android.os.Handler
import android.os.Looper

/**
 * Jembatan sederhana dalam-proses (in-process) supaya MainActivity bisa
 * memperbarui teks status pairing begitu CameraStreamService menerima
 * kredensial baru dari server, tanpa perlu library tambahan.
 */
object PairingEvents {
    @Volatile private var listener: (() -> Unit)? = null
    private val mainHandler = Handler(Looper.getMainLooper())

    fun setListener(callback: (() -> Unit)?) {
        listener = callback
    }

    fun notifyCredentialsUpdated() {
        val cb = listener ?: return
        mainHandler.post { cb() }
    }
}
