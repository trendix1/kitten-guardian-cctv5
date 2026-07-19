package com.kittenguardian.cctv

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Intent
import android.graphics.ImageFormat
import android.graphics.Rect
import android.graphics.YuvImage
import android.os.Build
import android.os.PowerManager
import android.net.wifi.WifiManager
import android.util.Log
import android.util.Size
import androidx.camera.core.Camera
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.app.NotificationCompat
import androidx.lifecycle.LifecycleService
import kotlinx.coroutines.*
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.util.concurrent.Executors

/**
 * Foreground service yang mengambil frame dari kamera belakang (CameraX),
 * mengompresnya ke JPEG, lalu mengirim ke laptop lewat NetworkClient.
 * Tidak pernah menyimpan frame ke penyimpanan lokal.
 *
 * Hemat daya: frame rate & kualitas JPEG menyesuaikan level baterai secara
 * otomatis (adaptive), pakai partial wake lock supaya proses tetap jalan
 * saat layar HP dimatikan (device diletakkan sebagai kamera statis).
 */
class CameraStreamService : LifecycleService() {

    companion object {
        const val EXTRA_HOST = "extra_host"
        const val EXTRA_PORT = "extra_port"
        const val EXTRA_CAMERA_ID = "extra_camera_id"
        const val EXTRA_PASSWORD = "extra_password"
        const val ACTION_STOP = "com.kittenguardian.cctv.STOP"
        const val NOTIF_CHANNEL_ID = "kitten_guardian_stream"
        const val NOTIF_ID = 1

        // Baseline hemat daya: ~8 fps kondisi baterai normal/cas.
        const val FRAME_INTERVAL_NORMAL_MS = 125L   // ~8 fps
        const val FRAME_INTERVAL_SAVING_MS = 200L   // ~5 fps saat baterai < 30%
        const val FRAME_INTERVAL_LOW_MS = 350L       // ~2-3 fps saat baterai < 15%

        const val JPEG_QUALITY_NORMAL = 55
        const val JPEG_QUALITY_SAVING = 42

        val TARGET_RESOLUTION = Size(640, 480)

        private const val TAG = "CameraStreamService"
    }

    private val coroutineErrorHandler = CoroutineExceptionHandler { _, throwable ->
        Log.e(TAG, "Unhandled coroutine error: ${throwable.message}", throwable)
    }
    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.Default + coroutineErrorHandler)
    private lateinit var cameraExecutor: java.util.concurrent.ExecutorService
    private var camera: Camera? = null
    private var networkClient: NetworkClient? = null
    private lateinit var telemetryManager: TelemetryManager
    private lateinit var credentialsStore: CredentialsStore
    private val repellentPlayer = RepellentSoundPlayer()

    private var wakeLock: PowerManager.WakeLock? = null
    private var wifiLock: WifiManager.WifiLock? = null

    private var lastFrameSentAt = 0L
    private var telemetryJob: Job? = null
    private var flashBlinkJob: Job? = null

    // Nilai adaptif, diperbarui tiap kali telemetry dikumpulkan.
    @Volatile private var currentFrameIntervalMs = FRAME_INTERVAL_NORMAL_MS
    @Volatile private var currentJpegQuality = JPEG_QUALITY_NORMAL

    override fun onCreate() {
        super.onCreate()
        cameraExecutor = Executors.newSingleThreadExecutor()
        telemetryManager = TelemetryManager(this)
        credentialsStore = CredentialsStore(this)
        createNotificationChannel()
        acquireWakeLock()
        acquireWifiLock()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        super.onStartCommand(intent, flags, startId)

        when (intent?.action) {
            ACTION_STOP -> {
                stopStreaming()
                return START_NOT_STICKY
            }
        }

        val host = intent?.getStringExtra(EXTRA_HOST) ?: return START_NOT_STICKY
        val port = intent.getIntExtra(EXTRA_PORT, Protocol.DEFAULT_PORT)
        val cameraId = intent.getStringExtra(EXTRA_CAMERA_ID) ?: credentialsStore.cameraId
        val password = intent.getStringExtra(EXTRA_PASSWORD) ?: credentialsStore.password

        startForeground(NOTIF_ID, buildNotification("Menghubungkan ke $host:$port"))

        networkClient = NetworkClient(
            host = host,
            port = port,
            cameraId = cameraId,
            password = password,
            scope = serviceScope,
            onConnectionChanged = { isConnected ->
                updateNotification(if (isConnected) "Streaming aktif ke $host:$port" else "Menunggu koneksi ke $host:$port")
            },
            onAuthResult = { ok ->
                updateNotification(if (ok) "Terautentikasi, streaming aktif" else "Autentikasi ditolak, cek ID/Password")
            },
            onCommand = { cmd, json -> handleCommand(cmd, json) },
        )
        networkClient?.start()

        bindCameraUseCases()
        startTelemetryLoop()

        return START_STICKY
    }

    private fun handleCommand(cmd: String, json: JSONObject) {
        when (cmd) {
            "flash_on" -> camera?.cameraControl?.enableTorch(true)
            "flash_off" -> camera?.cameraControl?.enableTorch(false)
            "flash_blink" -> blinkFlash()
            "pest_alarm" -> {
                val duration = json.optInt("duration_s", 5)
                repellentPlayer.play(duration)
            }
            "update_credentials", "set_credentials" -> {
                val newCameraId = json.optString("camera_id")
                val newPassword = json.optString("password")
                if (newCameraId.isNotEmpty()) {
                    credentialsStore.cameraId = newCameraId
                }
                if (newPassword.isNotEmpty()) {
                    credentialsStore.password = newPassword
                }
                Log.i(TAG, "Kredensial diperbarui dari server (pairing/rotasi)")
                PairingEvents.notifyCredentialsUpdated()
            }
        }
    }

    /** Nyala-mati senter 4x berturut-turut lalu pastikan mati (untuk penanda/tes visual). */
    private fun blinkFlash() {
        flashBlinkJob?.cancel()
        flashBlinkJob = serviceScope.launch {
            try {
                repeat(4) {
                    camera?.cameraControl?.enableTorch(true)
                    delay(280)
                    camera?.cameraControl?.enableTorch(false)
                    delay(220)
                }
            } finally {
                camera?.cameraControl?.enableTorch(false)
            }
        }
    }

    private fun bindCameraUseCases() {
        val providerFuture = ProcessCameraProvider.getInstance(this)
        providerFuture.addListener({
            try {
                val cameraProvider = providerFuture.get()
                cameraProvider.unbindAll()

                val analysis = ImageAnalysis.Builder()
                    .setTargetResolution(TARGET_RESOLUTION)
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .build()

                analysis.setAnalyzer(cameraExecutor) { imageProxy ->
                    processFrame(imageProxy)
                }

                camera = cameraProvider.bindToLifecycle(
                    this,
                    CameraSelector.DEFAULT_BACK_CAMERA,
                    analysis,
                )
            } catch (e: Exception) {
                Log.e(TAG, "Gagal menyiapkan kamera: ${e.message}", e)
                updateNotification("Gagal mengakses kamera, coba buka ulang aplikasi")
            }
        }, cameraExecutor)
    }

    private fun processFrame(imageProxy: ImageProxy) {
        val now = System.currentTimeMillis()
        if (now - lastFrameSentAt < currentFrameIntervalMs || networkClient?.isConnected != true) {
            imageProxy.close()
            return
        }
        lastFrameSentAt = now

        try {
            val jpeg = yuv420ToJpeg(imageProxy, currentJpegQuality)
            if (jpeg != null) {
                networkClient?.sendFrame(jpeg)
            }
        } catch (e: Throwable) {
            Log.w(TAG, "Gagal encode frame, frame dilewati: ${e.message}")
        } finally {
            imageProxy.close()
        }
    }

    /** Konversi ImageProxy (YUV_420_888) -> NV21 -> JPEG. Hanya di memori, tidak disimpan. */
    private fun yuv420ToJpeg(image: ImageProxy, quality: Int): ByteArray? {
        if (image.format != ImageFormat.YUV_420_888) return null

        val yPlane = image.planes[0]
        val uPlane = image.planes[1]
        val vPlane = image.planes[2]

        val ySize = yPlane.buffer.remaining()
        val uSize = uPlane.buffer.remaining()
        val vSize = vPlane.buffer.remaining()

        val nv21 = ByteArray(ySize + uSize + vSize)
        yPlane.buffer.get(nv21, 0, ySize)
        vPlane.buffer.get(nv21, ySize, vSize)
        uPlane.buffer.get(nv21, ySize + vSize, uSize)

        val yuvImage = YuvImage(nv21, ImageFormat.NV21, image.width, image.height, null)
        val out = ByteArrayOutputStream()
        yuvImage.compressToJpeg(Rect(0, 0, image.width, image.height), quality, out)
        return out.toByteArray()
    }

    /** Sesuaikan frame rate & kualitas JPEG berdasarkan level baterai (hemat daya adaptif). */
    private fun updateAdaptivePowerProfile(batteryPct: Int, charging: Boolean) {
        if (charging || batteryPct < 0) {
            currentFrameIntervalMs = FRAME_INTERVAL_NORMAL_MS
            currentJpegQuality = JPEG_QUALITY_NORMAL
            return
        }
        when {
            batteryPct < 15 -> {
                currentFrameIntervalMs = FRAME_INTERVAL_LOW_MS
                currentJpegQuality = JPEG_QUALITY_SAVING
            }
            batteryPct < 30 -> {
                currentFrameIntervalMs = FRAME_INTERVAL_SAVING_MS
                currentJpegQuality = JPEG_QUALITY_SAVING
            }
            else -> {
                currentFrameIntervalMs = FRAME_INTERVAL_NORMAL_MS
                currentJpegQuality = JPEG_QUALITY_NORMAL
            }
        }
    }

    private fun startTelemetryLoop() {
        telemetryJob?.cancel()
        telemetryJob = serviceScope.launch {
            while (isActive) {
                try {
                    val data = telemetryManager.collect()
                    networkClient?.sendTelemetry(data)
                    val batteryPct = data.optInt("battery_pct", -1)
                    val charging = data.optBoolean("charging", false)
                    updateAdaptivePowerProfile(batteryPct, charging)
                } catch (e: Throwable) {
                    Log.w(TAG, "Gagal ambil/kirim telemetry: ${e.message}")
                }
                delay(3000)
            }
        }
    }

    private fun stopStreaming() {
        telemetryJob?.cancel()
        flashBlinkJob?.cancel()
        repellentPlayer.stop()
        networkClient?.stop()
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() {
        telemetryJob?.cancel()
        flashBlinkJob?.cancel()
        repellentPlayer.stop()
        networkClient?.stop()
        serviceScope.cancel()
        cameraExecutor.shutdown()
        releaseWakeLock()
        releaseWifiLock()
        super.onDestroy()
    }

    private fun acquireWakeLock() {
        try {
            val pm = getSystemService(POWER_SERVICE) as PowerManager
            wakeLock = pm.newWakeLock(
                PowerManager.PARTIAL_WAKE_LOCK,
                "KittenGuardianCCTV::StreamingWakeLock",
            )
            wakeLock?.setReferenceCounted(false)
            wakeLock?.acquire(6 * 60 * 60 * 1000L) // maksimal 6 jam per acquire, aman dari lupa release
        } catch (e: Exception) {
            Log.w(TAG, "Gagal acquire wake lock: ${e.message}")
        }
    }

    private fun releaseWakeLock() {
        try {
            if (wakeLock?.isHeld == true) {
                wakeLock?.release()
            }
        } catch (_: Exception) {
        }
        wakeLock = null
    }

    /** Mencegah radio WiFi masuk power-save saat layar mati - penyebab umum
     * koneksi putus mendadak di HP dengan manajemen baterai agresif (ColorOS dll). */
    private fun acquireWifiLock() {
        try {
            val wifiManager = applicationContext.getSystemService(WIFI_SERVICE) as WifiManager
            wifiLock = wifiManager.createWifiLock(
                WifiManager.WIFI_MODE_FULL_HIGH_PERF,
                "KittenGuardianCCTV::WifiLock",
            )
            wifiLock?.setReferenceCounted(false)
            wifiLock?.acquire()
        } catch (e: Exception) {
            Log.w(TAG, "Gagal acquire wifi lock: ${e.message}")
        }
    }

    private fun releaseWifiLock() {
        try {
            if (wifiLock?.isHeld == true) {
                wifiLock?.release()
            }
        } catch (_: Exception) {
        }
        wifiLock = null
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                NOTIF_CHANNEL_ID,
                "Kitten Guardian Streaming",
                NotificationManager.IMPORTANCE_LOW,
            )
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    private fun buildNotification(text: String): Notification {
        return NotificationCompat.Builder(this, NOTIF_CHANNEL_ID)
            .setContentTitle("Kitten Guardian CCTV")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_menu_camera)
            .setOngoing(true)
            .build()
    }

    private fun updateNotification(text: String) {
        val manager = getSystemService(NotificationManager::class.java)
        manager.notify(NOTIF_ID, buildNotification(text))
    }
}
