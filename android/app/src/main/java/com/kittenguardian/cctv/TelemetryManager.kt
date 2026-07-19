package com.kittenguardian.cctv

import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.wifi.WifiManager
import android.os.BatteryManager
import org.json.JSONObject
import java.net.Inet4Address
import java.net.NetworkInterface

/**
 * Mengumpulkan data status perangkat Android: baterai, suhu, tegangan,
 * status charging, IP address, dan status WiFi.
 */
class TelemetryManager(private val context: Context) {

    fun collect(): JSONObject {
        val batteryIntent = context.registerReceiver(
            null, IntentFilter(Intent.ACTION_BATTERY_CHANGED)
        )

        val json = JSONObject()

        if (batteryIntent != null) {
            val level = batteryIntent.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
            val scale = batteryIntent.getIntExtra(BatteryManager.EXTRA_SCALE, -1)
            val pct = if (level >= 0 && scale > 0) (level * 100 / scale) else -1
            val status = batteryIntent.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
            val charging = status == BatteryManager.BATTERY_STATUS_CHARGING ||
                status == BatteryManager.BATTERY_STATUS_FULL
            val tempTenths = batteryIntent.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, -1)
            val voltageMv = batteryIntent.getIntExtra(BatteryManager.EXTRA_VOLTAGE, -1)

            json.put("battery_pct", pct)
            json.put("charging", charging)
            if (tempTenths >= 0) json.put("temperature_c", tempTenths / 10.0)
            if (voltageMv >= 0) json.put("voltage_v", voltageMv / 1000.0)
        }

        json.put("ip_address", getLocalIpAddress() ?: "-")
        json.put("wifi_status", getWifiStatus())

        return json
    }

    private fun getWifiStatus(): String {
        return try {
            val wifiManager = context.applicationContext
                .getSystemService(Context.WIFI_SERVICE) as WifiManager
            val info = wifiManager.connectionInfo
            val rssi = info.rssi
            val ssid = info.ssid?.replace("\"", "") ?: "unknown"
            "$ssid (${rssi} dBm)"
        } catch (e: Exception) {
            "unknown"
        }
    }

    private fun getLocalIpAddress(): String? {
        try {
            val interfaces = NetworkInterface.getNetworkInterfaces()
            while (interfaces.hasMoreElements()) {
                val iface = interfaces.nextElement()
                val addrs = iface.inetAddresses
                while (addrs.hasMoreElements()) {
                    val addr = addrs.nextElement()
                    if (!addr.isLoopbackAddress && addr is Inet4Address) {
                        return addr.hostAddress
                    }
                }
            }
        } catch (_: Exception) {
        }
        return null
    }
}
