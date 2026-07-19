package com.kittenguardian.cctv

import android.content.Context
import android.util.Log
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Mencatat event & error penting (bukan cuma crash total) ke file teks lokal
 * supaya bisa dibaca lewat File Manager tanpa ADB:
 * Android/data/com.kittenguardian.cctv/files/app_log.txt
 */
object AppLogger {
    private const val FILE_NAME = "app_log.txt"
    private const val MAX_SIZE_BYTES = 512 * 1024 // 512KB, auto-terpotong biar tidak membengkak

    @Synchronized
    fun log(context: Context, tag: String, message: String, throwable: Throwable? = null) {
        Log.i(tag, message, throwable)
        try {
            val dir = context.applicationContext.getExternalFilesDir(null)
                ?: context.applicationContext.filesDir
            if (!dir.exists()) dir.mkdirs()
            val file = File(dir, FILE_NAME)

            if (file.exists() && file.length() > MAX_SIZE_BYTES) {
                file.delete()
            }

            val ts = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault()).format(Date())
            val line = buildString {
                append("[$ts] [$tag] $message")
                if (throwable != null) {
                    append(" | Exception: ${throwable.javaClass.simpleName}: ${throwable.message}")
                }
                append("\n")
            }
            file.appendText(line)
        } catch (e: Exception) {
            Log.e("AppLogger", "Gagal menulis log: ${e.message}")
        }
    }
}
