package com.kittenguardian.cctv

import android.content.Context
import android.content.SharedPreferences

/**
 * Menyimpan kredensial (Camera ID + Password) dan 2 profil koneksi:
 * "wifi" (jaringan lokal) dan "internet" (WAN, mis. lewat port forwarding / DDNS).
 * Password bisa diperbarui otomatis oleh server (mode rotasi) dan disimpan
 * di sini supaya reconnect berikutnya otomatis pakai password terbaru.
 */
class CredentialsStore(context: Context) {

    private val prefs: SharedPreferences =
        context.applicationContext.getSharedPreferences("kitten_guardian_prefs", Context.MODE_PRIVATE)

    companion object {
        const val MODE_WIFI = "wifi"
        const val MODE_INTERNET = "internet"

        private const val KEY_CAMERA_ID = "camera_id"
        private const val KEY_PASSWORD = "password"
        private const val KEY_CONN_MODE = "connection_mode"

        private const val KEY_WIFI_HOST = "wifi_host"
        private const val KEY_WIFI_PORT = "wifi_port"
        private const val KEY_INTERNET_HOST = "internet_host"
        private const val KEY_INTERNET_PORT = "internet_port"
    }

    var cameraId: String
        get() = prefs.getString(KEY_CAMERA_ID, "kitten-cam-01") ?: "kitten-cam-01"
        set(value) = prefs.edit().putString(KEY_CAMERA_ID, value).apply()

    var password: String
        get() = prefs.getString(KEY_PASSWORD, "") ?: ""
        set(value) = prefs.edit().putString(KEY_PASSWORD, value).apply()

    var connectionMode: String
        get() = prefs.getString(KEY_CONN_MODE, MODE_WIFI) ?: MODE_WIFI
        set(value) = prefs.edit().putString(KEY_CONN_MODE, value).apply()

    var wifiHost: String
        get() = prefs.getString(KEY_WIFI_HOST, "") ?: ""
        set(value) = prefs.edit().putString(KEY_WIFI_HOST, value).apply()

    var wifiPort: Int
        get() = prefs.getInt(KEY_WIFI_PORT, Protocol.DEFAULT_PORT)
        set(value) = prefs.edit().putInt(KEY_WIFI_PORT, value).apply()

    var internetHost: String
        get() = prefs.getString(KEY_INTERNET_HOST, "") ?: ""
        set(value) = prefs.edit().putString(KEY_INTERNET_HOST, value).apply()

    var internetPort: Int
        get() = prefs.getInt(KEY_INTERNET_PORT, Protocol.DEFAULT_PORT)
        set(value) = prefs.edit().putInt(KEY_INTERNET_PORT, value).apply()

    /** Host & port aktif sesuai mode koneksi yang dipilih. */
    fun activeHostPort(): Pair<String, Int> {
        return if (connectionMode == MODE_INTERNET) {
            internetHost to internetPort
        } else {
            wifiHost to wifiPort
        }
    }
}
