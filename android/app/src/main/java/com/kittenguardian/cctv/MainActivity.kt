package com.kittenguardian.cctv

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.RadioGroup
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat

class MainActivity : AppCompatActivity() {

    private lateinit var radioConnectionMode: RadioGroup
    private lateinit var editWifiIp: EditText
    private lateinit var editWifiPort: EditText
    private lateinit var editInternetHost: EditText
    private lateinit var editInternetPort: EditText
    private lateinit var btnToggle: Button
    private lateinit var textStatus: TextView
    private lateinit var textTelemetry: TextView
    private lateinit var textPairingStatus: TextView
    private lateinit var telemetryManager: TelemetryManager
    private lateinit var credentialsStore: CredentialsStore

    private var isStreaming = false

    private val cameraPermissionLauncher = registerForActivityResult(
        androidx.activity.result.contract.ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            startStreamingService()
        } else {
            textStatus.text = "Status: Izin kamera ditolak"
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        CrashLogger.install(this)
        setContentView(R.layout.activity_main)

        radioConnectionMode = findViewById(R.id.radio_connection_mode)
        editWifiIp = findViewById(R.id.edit_wifi_ip)
        editWifiPort = findViewById(R.id.edit_wifi_port)
        editInternetHost = findViewById(R.id.edit_internet_host)
        editInternetPort = findViewById(R.id.edit_internet_port)
        btnToggle = findViewById(R.id.btn_toggle_stream)
        textStatus = findViewById(R.id.text_status)
        textTelemetry = findViewById(R.id.text_telemetry)
        textPairingStatus = findViewById(R.id.text_pairing_status)
        telemetryManager = TelemetryManager(this)
        credentialsStore = CredentialsStore(this)

        loadSavedValues()
        updatePairingStatusText()

        btnToggle.setOnClickListener { onToggleClicked() }

        updateLocalTelemetryPreview()
    }

    override fun onResume() {
        super.onResume()
        updatePairingStatusText()
        PairingEvents.setListener { updatePairingStatusText() }
    }

    override fun onPause() {
        super.onPause()
        PairingEvents.setListener(null)
    }

    private fun loadSavedValues() {
        editWifiIp.setText(credentialsStore.wifiHost)
        editWifiPort.setText(credentialsStore.wifiPort.toString())
        editInternetHost.setText(credentialsStore.internetHost)
        editInternetPort.setText(credentialsStore.internetPort.toString())

        if (credentialsStore.connectionMode == CredentialsStore.MODE_INTERNET) {
            radioConnectionMode.check(R.id.radio_mode_internet)
        } else {
            radioConnectionMode.check(R.id.radio_mode_wifi)
        }
    }

    private fun saveCurrentValues() {
        credentialsStore.wifiHost = editWifiIp.text.toString().trim()
        credentialsStore.wifiPort = editWifiPort.text.toString().toIntOrNull() ?: Protocol.DEFAULT_PORT
        credentialsStore.internetHost = editInternetHost.text.toString().trim()
        credentialsStore.internetPort = editInternetPort.text.toString().toIntOrNull() ?: Protocol.DEFAULT_PORT
        credentialsStore.connectionMode = if (radioConnectionMode.checkedRadioButtonId == R.id.radio_mode_internet) {
            CredentialsStore.MODE_INTERNET
        } else {
            CredentialsStore.MODE_WIFI
        }
    }

    private fun updatePairingStatusText() {
        if (credentialsStore.password.isNotEmpty()) {
            textPairingStatus.text = "Status Pairing: Sudah dipasangkan (ID: ${credentialsStore.cameraId})"
        } else {
            textPairingStatus.text = "Status Pairing: Belum dipasangkan - aktifkan Mode Pairing di desktop lalu tekan Start Streaming"
        }
    }

    private fun onToggleClicked() {
        if (isStreaming) {
            stopStreamingService()
        } else {
            requestCameraPermissionAndStart()
        }
    }

    private fun requestCameraPermissionAndStart() {
        val granted = ContextCompat.checkSelfPermission(
            this, Manifest.permission.CAMERA
        ) == PackageManager.PERMISSION_GRANTED

        if (granted) {
            startStreamingService()
        } else {
            cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
        }
    }

    private fun startStreamingService() {
        saveCurrentValues()

        val (host, port) = credentialsStore.activeHostPort()
        if (host.isEmpty()) {
            textStatus.text = "Status: Isi alamat server terlebih dahulu"
            return
        }

        val intent = Intent(this, CameraStreamService::class.java).apply {
            putExtra(CameraStreamService.EXTRA_HOST, host)
            putExtra(CameraStreamService.EXTRA_PORT, port)
            putExtra(CameraStreamService.EXTRA_CAMERA_ID, credentialsStore.cameraId)
            putExtra(CameraStreamService.EXTRA_PASSWORD, credentialsStore.password)
        }
        ContextCompat.startForegroundService(this, intent)

        isStreaming = true
        btnToggle.text = "Stop Streaming"
        textStatus.text = if (credentialsStore.password.isEmpty()) {
            "Status: Menghubungkan (pairing) ke $host:$port ..."
        } else {
            "Status: Streaming ke $host:$port"
        }
    }

    private fun stopStreamingService() {
        val intent = Intent(this, CameraStreamService::class.java).apply {
            action = CameraStreamService.ACTION_STOP
        }
        startService(intent)

        isStreaming = false
        btnToggle.text = "Start Streaming"
        textStatus.text = "Status: Idle"
        updatePairingStatusText()
    }

    private fun updateLocalTelemetryPreview() {
        try {
            val data = telemetryManager.collect()
            textTelemetry.text = buildString {
                append("Battery : ${data.optInt("battery_pct", -1)}%\n")
                append("Charging: ${data.optBoolean("charging", false)}\n")
                append("IP      : ${data.optString("ip_address", "-")}\n")
                append("WiFi    : ${data.optString("wifi_status", "-")}")
            }
        } catch (_: Exception) {
        }
    }
}
