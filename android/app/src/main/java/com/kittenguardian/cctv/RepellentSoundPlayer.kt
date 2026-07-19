package com.kittenguardian.cctv

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioTrack
import android.util.Log
import kotlin.math.sin
import kotlin.math.PI

/**
 * Membunyikan nada frekuensi tinggi (sekitar batas atas jangkauan dengar manusia)
 * lewat speaker HP untuk mengusir tikus/hewan pengganggu, bukan suara alarm biasa
 * yang dipakai untuk notifikasi ke pemilik rumah.
 *
 * CATATAN JUJUR: speaker HP pada umumnya hanya mampu mereproduksi hingga
 * sekitar 20 kHz (batas atas pendengaran manusia), bukan ultrasonik murni
 * (>20 kHz) seperti alat pengusir hewan komersial. Efektivitasnya bisa
 * bervariasi tergantung hardware speaker & jenis hewan. Fitur ini tetap
 * berguna sebagai bunyi mendadak bernada tinggi yang mengejutkan hewan kecil.
 */
class RepellentSoundPlayer {

    companion object {
        private const val TAG = "RepellentSoundPlayer"
        private const val SAMPLE_RATE = 44100
    }

    @Volatile private var isPlaying = false
    private var track: AudioTrack? = null
    private var playThread: Thread? = null

    fun play(durationSeconds: Int = 5) {
        stop()
        isPlaying = true

        playThread = Thread {
            try {
                val minBufferSize = AudioTrack.getMinBufferSize(
                    SAMPLE_RATE,
                    AudioFormat.CHANNEL_OUT_MONO,
                    AudioFormat.ENCODING_PCM_16BIT,
                )

                val audioTrack = AudioTrack(
                    AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_ALARM)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                        .build(),
                    AudioFormat.Builder()
                        .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                        .setSampleRate(SAMPLE_RATE)
                        .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                        .build(),
                    minBufferSize,
                    AudioTrack.MODE_STREAM,
                    AudioManager.AUDIO_SESSION_ID_GENERATE,
                )
                track = audioTrack
                audioTrack.play()

                val endAt = System.currentTimeMillis() + durationSeconds * 1000L
                var freq = 15000.0 // mulai dari 15kHz, sapu naik ke ~19.5kHz lalu ulang
                val bufferSamples = 2048
                val buffer = ShortArray(bufferSamples)

                var phase = 0.0
                while (isPlaying && System.currentTimeMillis() < endAt) {
                    // Sapuan frekuensi naik-turun supaya lebih efektif mengejutkan hewan
                    // dibanding nada konstan tunggal.
                    freq += 400.0
                    if (freq > 19500.0) freq = 15000.0

                    val twoPiF = 2.0 * PI * freq / SAMPLE_RATE
                    for (i in 0 until bufferSamples) {
                        val sample = (sin(phase) * Short.MAX_VALUE * 0.9).toInt().toShort()
                        buffer[i] = sample
                        phase += twoPiF
                        if (phase > 2.0 * PI) phase -= 2.0 * PI
                    }
                    audioTrack.write(buffer, 0, bufferSamples)
                }

                audioTrack.stop()
                audioTrack.release()
            } catch (e: Exception) {
                Log.e(TAG, "Gagal memutar alarm usir hewan: ${e.message}")
            } finally {
                isPlaying = false
            }
        }
        playThread?.start()
    }

    fun stop() {
        isPlaying = false
        try {
            track?.stop()
            track?.release()
        } catch (_: Exception) {
        }
        track = null
        playThread?.let {
            try {
                it.join(500)
            } catch (_: Exception) {
            }
        }
        playThread = null
    }
}
