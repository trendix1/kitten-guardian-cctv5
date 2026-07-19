package com.kittenguardian.cctv

import android.content.Context
import android.util.Log
import java.io.File
import java.io.PrintWriter
import java.io.StringWriter
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Menangkap crash yang tidak tertangani dan menyimpannya ke file teks lokal
 * (Android/data/com.kittenguardian.cctv/files/crash_log.txt) supaya bisa
 * dibaca lewat File Manager tanpa perlu ADB/komputer.
 */
object CrashLogger {

    private const val TAG = "CrashLogger"
    private const val FILE_NAME = "crash_log.txt"

    fun install(context: Context) {
        val appContext = context.applicationContext
        val defaultHandler = Thread.getDefaultUncaughtExceptionHandler()

        Thread.setDefaultUncaughtExceptionHandler { thread, throwable ->
            try {
                writeToFile(appContext, thread, throwable)
            } catch (e: Exception) {
                Log.e(TAG, "Gagal menulis crash log: ${e.message}")
            }
            // Tetap teruskan ke handler default (sistem) supaya app close secara normal.
            defaultHandler?.uncaughtException(thread, throwable)
        }
    }

    private fun writeToFile(context: Context, thread: Thread, throwable: Throwable) {
        val dir = context.getExternalFilesDir(null) ?: context.filesDir
        val file = File(dir, FILE_NAME)

        val sw = StringWriter()
        throwable.printStackTrace(PrintWriter(sw))

        val timestamp = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault()).format(Date())
        val entry = buildString {
            append("=== CRASH $timestamp (thread: ${thread.name}) ===\n")
            append(sw.toString())
            append("\n\n")
        }

        file.appendText(entry)
        Log.e(TAG, "Crash dicatat ke: ${file.absolutePath}")
    }
}
