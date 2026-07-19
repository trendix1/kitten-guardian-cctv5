# Kitten Guardian CCTV

Sistem monitoring anak kucing pribadi: HP Android lama sebagai kamera, laptop Windows sebagai pusat monitoring (GUI, motion detection, alarm).

```
Android (kamera, client)  --WiFi lokal-->  Python Desktop (server, GUI)
```

## Desktop (Windows)

```
cd desktop
pip install -r requirements.txt
python main.py
```

- Klik **Start** untuk membuka server (default port `8765`).
- Catat IP laptop di jaringan WiFi yang sama (`ipconfig`).

## Android

1. Buka folder `android/` sebagai project di Android Studio, atau build via GitHub Actions (`.github/workflows/android-build.yml` -> artifact APK debug).
2. Install APK di HP (target: OPPO A3s / Android 8.1+).
3. Isi IP & port laptop, tekan **Start Streaming**.

## Protokol

TCP, 1 koneksi kamera aktif per waktu. Frame: `[1 byte tipe][4 byte panjang][payload]`.
Tipe pesan: `FRAME` (JPEG), `TELEMETRY` (JSON), `COMMAND` (JSON, server->client), `PING`/`PONG` (latency).

Detail lengkap: `desktop/core/protocol.py` dan `android/.../Protocol.kt`.

## Fitur Tambahan

- **Fullscreen**: tombol Fullscreen di GUI desktop, atau tekan `F11` (Esc untuk keluar).
- **Alarm Usir Hewan**: tombol "Usir Hewan" di desktop mengirim perintah ke HP untuk membunyikan nada frekuensi tinggi (sapuan 15-19.5 kHz) lewat speaker HP, terpisah dari alarm notifikasi biasa. **Catatan jujur**: speaker HP pada umumnya hanya mampu mereproduksi hingga sekitar 20 kHz (batas atas pendengaran manusia), bukan ultrasonik murni (>20 kHz) seperti alat pengusir komersial, dan efektivitas alat semacam ini terhadap hewan pengerat masih diperdebatkan secara ilmiah. Fitur ini tetap berguna sebagai bunyi mendadak bernada tinggi yang mengejutkan hewan kecil.
- **Flash Blink x4**: tombol di desktop untuk mengedipkan senter HP 4x berturut-turut (dikirim sebagai perintah jarak jauh, tidak ada tombol di aplikasi HP).
- **Mode Koneksi ganda (WiFi Lokal / Internet)**: di HP bisa disimpan 2 profil alamat server — WiFi Lokal (untuk di rumah) dan Internet/WAN (untuk akses dari luar). Desktop tetap hanya membuka **satu port** (default `8765`); untuk mode Internet, atur **port forwarding** di router rumah (external port -> IP laptop:8765) atau gunakan DDNS/VPN (mis. Tailscale) untuk keamanan lebih baik daripada expose port TCP polos ke internet.
- **Autentikasi Camera ID + Password via Pairing**: ID dan password **hanya diatur di desktop** (panel "Keamanan Kamera"), tidak perlu diketik manual di HP. Alurnya:
  1. Di desktop, klik **Mode Pairing: OFF** untuk mengaktifkannya (jadi ON).
  2. Di HP, tekan **Start Streaming** (tanpa isi apa pun soal ID/password).
  3. HP otomatis menerima ID+password yang benar dari server dan menyimpannya. Mode Pairing otomatis nonaktif setelah 1 kamera berhasil dipasangkan.
  4. Untuk koneksi berikutnya, HP memakai kredensial tersimpan tanpa perlu pairing ulang.

  Dua mode password di desktop:
  - **Static**: password tetap, kuat (minimal 10 karakter, kombinasi huruf besar/kecil/angka), tidak berubah otomatis.
  - **Rotasi Otomatis tiap 3 jam**: password baru dibuat otomatis oleh server dan didorong (push) ke HP yang sedang terhubung, tersimpan otomatis untuk reconnect berikutnya. Jika koneksi terputus sebelum sempat menerima update, aktifkan Mode Pairing sebentar untuk memasangkan ulang.
- **Hemat Daya Adaptif (Android)**: frame rate & kualitas JPEG otomatis diturunkan saat baterai HP di bawah 30%/15% (dan tidak sedang dicas), kembali normal saat dicas atau baterai cukup.
- **WiFi Lock & TCP Keepalive**: mencegah radio WiFi HP masuk mode hemat daya saat layar mati, dan mendeteksi koneksi putus lebih cepat — mengurangi kegagalan reconnect di HP dengan manajemen baterai agresif (mis. ColorOS/OPPO).

## Catatan

- Frame kamera **tidak pernah disimpan** kecuali saat gerakan terdeteksi (Mode 1: 1 foto, Mode 2: 4 foto berurutan).
- Streaming dibatasi ~8 FPS, resolusi 640x480, JPEG quality 55 — dioptimalkan untuk RAM/CPU/baterai HP lama.
