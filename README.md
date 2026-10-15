# Anti Detect Browser — Free Multi-Profile Browser for Windows

[![Download](https://img.shields.io/github/v/release/Ardibirawinata/Anti-detect-browser?label=Download&style=for-the-badge)](https://github.com/Ardibirawinata/Anti-detect-browser/releases/latest)
![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-blue?style=for-the-badge)
![Price](https://img.shields.io/badge/price-free-brightgreen?style=for-the-badge)

**Privacy Browser** is a **free anti-detect browser** for Windows. Run **many isolated browser profiles at the same time**, each with its own browser fingerprint, cookies, and proxy, so websites see every profile as a different device. A free alternative to **Multilogin, GoLogin, AdsPower, Dolphin Anty, and Incogniton** for managing multiple accounts.

Website: **https://ardibirawinata.github.io/Anti-detect-browser/**

Each profile has its own:

- **Data**: cookies, logins, history, and extensions are never shared between profiles
- **Unique, persistent fingerprint**: canvas, WebGL (graphics card), audio, screen resolution, CPU cores, RAM, language, and timezone
- **Proxy**: HTTP, HTTPS, SOCKS4, SOCKS5, including SOCKS5 with username/password
- **Automatic proxy sync**: timezone, language, and GPS location are matched to the proxy IP's country
- **WebRTC leak protection**: your real IP is not leaked through WebRTC

## Use cases

- Managing multiple social media, e-commerce, or ad accounts without them being linked
- Affiliate marketing, airdrops, and multi-account workflows
- Web scraping and QA testing with different fingerprints and IP addresses
- Keeping work, personal, and client browsing fully separated

## Download

Get the latest installer from the **[Releases](https://github.com/Ardibirawinata/Anti-detect-browser/releases/latest)** page → `PrivacyBrowser-Setup.exe`.

Requirements: Windows 10/11 64-bit. No need to install Python or any other software.

## For users

1. Run `PrivacyBrowser-Setup.exe` → Next → Finish. No admin rights or extra software required.
2. Click **➕ Profil baru** (New profile), give it a name, then paste a proxy in the **Proxy** tab (optional) → **Simpan** (Save).
3. Double-click the profile or press **▶ Buka browser** (Open browser).

Supported proxy formats (paste as-is):

```
1.2.3.4:8080
1.2.3.4:8080:user:pass
socks5://user:pass@1.2.3.4:1080
http://user:pass@proxy.example.com:3128
```

**Buat banyak** (Bulk create) creates dozens of profiles at once. Paste a list of proxies (one per line) and each proxy automatically gets its own profile with a random fingerprint.

Browser used: **Google Chrome** if installed. Otherwise **Microsoft Edge**, which is always available on Windows 10/11.

Profile data is stored in `%LOCALAPPDATA%\PrivacyBrowser\data` and is kept when uninstalling. Proxy passwords are encrypted with Windows DPAPI, tied to your Windows account.

Portable mode: place an empty file named `portable` next to `PrivacyBrowser.exe`, and data will be stored in a `data\` folder beside it.

Diagnostics: `PrivacyBrowser.exe --selftest` opens a test browser and writes the result to `selftest.log` in the data folder.

> Seeing "Windows protected your PC"? Click **More info → Run anyway**. This happens because the EXE is not yet signed with a code-signing certificate.

## For developers

```bash
pip install -r requirements.txt
python main.py
```

Build the EXE + installer:

```bash
build.bat
```

Build output:
- `dist\PrivacyBrowser\`: portable version (can be zipped)
- `installer\PrivacyBrowser-Setup.exe`: only created if [Inno Setup 6](https://jrsoftware.org/isinfo.php) is installed (`winget install JRSoftware.InnoSetup`)

### Structure

| File | Contents |
|---|---|
| `privacy_browser/gui.py` | Tkinter interface (profile list, edit dialog, bulk create) |
| `privacy_browser/engine.py` | Launches many browsers in parallel via Patchright (anti-detection Playwright fork, asyncio) |
| `privacy_browser/stealth.js` | Fingerprint spoofing script injected into every frame |
| `privacy_browser/fingerprint.py` | Realistic fingerprint generator + country → language mapping |
| `privacy_browser/socks_relay.py` | Local relay so Chromium can use SOCKS5 with authentication |
| `privacy_browser/proxy_check.py` | Proxy test: exit IP, country, timezone |
| `privacy_browser/models.py` | Profile data, proxy parser, JSON storage |

### Known limitations

- The fingerprint is spoofed in pages and iframes. Web Workers and Service Workers still see real values for CPU, OffscreenCanvas, and similar.
- The CSS `device-width` media query still uses the real monitor resolution.
- The User-Agent is left as the real one by default. Changing it manually may make the UA mismatch Client Hints (`Sec-CH-UA`).

## FAQ

**What is an anti-detect browser?**
A browser that gives every profile its own fingerprint (canvas, WebGL, audio, screen, timezone, etc.) and its own cookies and proxy, so websites cannot tell that multiple profiles belong to the same person or computer.

**Is it free?**
Yes. There are no profile limits, subscriptions, or accounts.

**How many profiles can I create?**
Unlimited. Use **Buat banyak** (Bulk create) to create dozens of profiles from a proxy list at once.

**Does it need Chrome?**
No. It uses Google Chrome if installed, otherwise Microsoft Edge, which is built into Windows 10/11.

**Which proxies are supported?**
HTTP, HTTPS, SOCKS4, and SOCKS5 (with or without username/password).

**Is my data sent anywhere?**
No. All profiles are stored locally on your computer, and proxy passwords are encrypted with Windows DPAPI. The only outside requests the app makes are proxy checks (to ipinfo.io / ip-api.com) to detect the proxy's IP, country, and timezone.

## Author

**Ardi Birawinata** ([@Ardibirawinata](https://github.com/Ardibirawinata))
