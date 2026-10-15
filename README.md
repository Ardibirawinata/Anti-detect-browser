# Anti Detect Browser

**Privacy Browser** adalah aplikasi Windows untuk menjalankan **banyak browser terpisah sekaligus**. Setiap profil punya:

- **Data sendiri**: cookie, login, riwayat, dan ekstensi tidak tercampur antarprofil
- **Fingerprint unik yang tetap**: canvas, WebGL (kartu grafis), audio, resolusi layar, jumlah CPU, RAM, bahasa, dan zona waktu
- **Proxy sendiri**: HTTP, HTTPS, SOCKS4, SOCKS5, termasuk SOCKS5 dengan username/password
- **Sinkron otomatis dengan proxy**: zona waktu, bahasa, dan lokasi GPS disamakan dengan negara IP proxy
- **Perlindungan kebocoran WebRTC**: IP asli tidak bocor lewat WebRTC

## Download

Unduh installer terbaru di halaman **[Releases](https://github.com/Ardibirawinata/Anti-detect-browser/releases/latest)** → `PrivacyBrowser-Setup.exe`.

Syarat: Windows 10/11 64-bit. Tidak perlu memasang Python atau aplikasi lain.

## Untuk pengguna

1. Jalankan `PrivacyBrowser-Setup.exe` → Next → Selesai. Tidak perlu hak admin dan tidak perlu memasang aplikasi lain.
2. Klik **➕ Profil baru**, beri nama, lalu tempel proxy di tab **Proxy** (opsional) → **Simpan**.
3. Klik dua kali profil atau tekan **▶ Buka browser**.

Format proxy yang bisa langsung ditempel:

```
1.2.3.4:8080
1.2.3.4:8080:user:pass
socks5://user:pass@1.2.3.4:1080
http://user:pass@proxy.contoh.com:3128
```

**Buat banyak** membuat puluhan profil sekaligus. Tempel daftar proxy (satu per baris), dan setiap proxy otomatis mendapat profil dengan fingerprint acak.

Browser yang dipakai: **Google Chrome** kalau terpasang. Kalau tidak ada, dipakai **Microsoft Edge**, yang selalu tersedia di Windows 10/11.

Data profil tersimpan di `%LOCALAPPDATA%\PrivacyBrowser\data` dan tidak ikut terhapus saat uninstall. Password proxy dienkripsi dengan Windows DPAPI, terikat ke akun Windows Anda.

Mode portable: taruh file kosong bernama `portable` di samping `PrivacyBrowser.exe`, maka data disimpan di folder `data\` di sebelahnya.

Diagnosa: `PrivacyBrowser.exe --selftest` membuka browser uji dan menulis hasilnya ke `selftest.log` di folder data.

> Muncul "Windows protected your PC"? Klik **More info → Run anyway**. Ini terjadi karena EXE belum ditandatangani dengan sertifikat code-signing.

## Untuk developer

```bash
pip install -r requirements.txt
python main.py
```

Build EXE + installer:

```bash
build.bat
```

Hasil build:
- `dist\PrivacyBrowser\`: versi portable (bisa di-zip)
- `installer\PrivacyBrowser-Setup.exe`: hanya dibuat jika [Inno Setup 6](https://jrsoftware.org/isinfo.php) terpasang (`winget install JRSoftware.InnoSetup`)

### Struktur

| File | Isi |
|---|---|
| `privacy_browser/gui.py` | Antarmuka Tkinter (daftar profil, dialog edit, buat banyak) |
| `privacy_browser/engine.py` | Meluncurkan banyak browser paralel via Patchright (fork Playwright anti-deteksi, asyncio) |
| `privacy_browser/stealth.js` | Script pemalsu fingerprint yang disuntikkan ke setiap frame |
| `privacy_browser/fingerprint.py` | Generator fingerprint realistis + pemetaan negara → bahasa |
| `privacy_browser/socks_relay.py` | Relay lokal agar Chromium bisa memakai SOCKS5 dengan login |
| `privacy_browser/proxy_check.py` | Tes proxy: IP keluar, negara, zona waktu |
| `privacy_browser/models.py` | Data profil, parser proxy, penyimpanan JSON |

### Batasan yang diketahui

- Fingerprint dipalsukan di halaman dan iframe. Web Worker dan Service Worker masih melihat nilai asli untuk CPU, canvas di OffscreenCanvas, dan sejenisnya.
- Media query CSS `device-width` masih memakai resolusi monitor asli.
- User-Agent dibiarkan asli secara default. Mengubahnya secara manual bisa membuat UA tidak cocok dengan Client Hints (`Sec-CH-UA`).

## Author

**Ardi Birawinata** ([@Ardibirawinata](https://github.com/Ardibirawinata))
