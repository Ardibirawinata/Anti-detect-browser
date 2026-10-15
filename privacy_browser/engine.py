"""Mesin peluncur: menjalankan banyak instance browser paralel di satu event loop asyncio."""
from __future__ import annotations

import asyncio
import copy
import json
import os
import shutil
import threading
from concurrent.futures import Future
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from patchright.async_api import BrowserContext, Playwright, async_playwright

from . import fingerprint as fpgen
from . import paths, proxy_check
from .models import Profile
from .socks_relay import SocksRelay

EventSink = Callable[[tuple], None]


@dataclass
class Instance:
    profile_id: str
    context: BrowserContext
    relay: SocksRelay | None = None


def build_stealth_script(fp) -> str:
    src = paths.resource("stealth.js").read_text("utf-8")
    return src.replace("/*__FP__*/null", json.dumps(fpgen.to_js_config(fp)), 1)


def _write_prefs(user_data_dir: Path, fp) -> None:
    """Atur kebijakan WebRTC & tandai exit normal (hindari bubble 'Restore pages')."""
    pref_file = user_data_dir / "Default" / "Preferences"
    pref_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        prefs = json.loads(pref_file.read_text("utf-8"))
    except Exception:
        prefs = {}
    webrtc = prefs.setdefault("webrtc", {})
    if fp.webrtc in ("proxy", "disable"):
        webrtc.update(ip_handling_policy="disable_non_proxied_udp",
                      multiple_routes_enabled=False, nonproxied_udp_enabled=False)
    else:
        for k in ("ip_handling_policy", "multiple_routes_enabled", "nonproxied_udp_enabled"):
            webrtc.pop(k, None)
    prof = prefs.setdefault("profile", {})
    prof["exit_type"] = "Normal"
    prof["exited_cleanly"] = True
    pref_file.write_text(json.dumps(prefs), "utf-8")


class Engine:
    def __init__(self, sink: EventSink):
        self.sink = sink
        self.loop = asyncio.new_event_loop()
        self._pw: Playwright | None = None
        self._pw_lock: asyncio.Lock | None = None
        self.instances: dict[str, Instance] = {}
        self._starting: set[str] = set()
        threading.Thread(target=self._run, name="engine", daemon=True).start()

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self._pw_lock = asyncio.Lock()
        self.loop.run_forever()

    def submit(self, coro) -> Future:
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def is_running(self, pid: str) -> bool:
        return pid in self.instances or pid in self._starting

    # ------------------------------------------------------------------ API publik
    def launch(self, profile: Profile, user_data_dir: Path) -> Future:
        return self.submit(self._launch(copy.deepcopy(profile), user_data_dir))

    def stop(self, pid: str) -> Future:
        return self.submit(self._stop(pid))

    def shutdown(self, timeout: float = 15) -> None:
        try:
            self.submit(self._shutdown()).result(timeout)
        except Exception:
            pass
        self.loop.call_soon_threadsafe(self.loop.stop)

    # ------------------------------------------------------------------ internal
    async def _playwright(self) -> Playwright:
        async with self._pw_lock:
            if self._pw is None:
                self._pw = await async_playwright().start()
        return self._pw

    async def _launch(self, profile: Profile, user_data_dir: Path) -> None:
        pid = profile.id
        if self.is_running(pid):
            return
        self._starting.add(pid)
        self.sink(("status", pid, "starting", "Memulai..."))
        relay = None
        try:
            fp = profile.fingerprint
            px = profile.proxy

            # 1) Cek proxy + sinkronkan timezone/bahasa/lokasi dengan IP proxy
            if px.enabled and px.host:
                self.sink(("status", pid, "starting", "Cek proxy..."))
                geo = await asyncio.to_thread(proxy_check.check, px)
                if px.auto_geo:
                    fpgen.apply_geo(fp, geo)
                self.sink(("geo", pid, geo, copy.deepcopy(fp) if px.auto_geo else None))

            # 2) Konfigurasi proxy untuk Chromium
            proxy_arg = None
            if px.enabled and px.host:
                # SOCKS5+auth dan SOCKS4 lewat relay lokal: Chromium tidak bisa login SOCKS5,
                # dan SOCKS4 bawaan Chromium me-resolve DNS di lokal (bocor).
                if (px.type == "socks5" and px.username) or px.type == "socks4":
                    relay = SocksRelay(px.host, px.port, px.username, px.get_password(), upstream=px.type)
                    port = await relay.start()
                    proxy_arg = {"server": f"socks5://127.0.0.1:{port}"}
                else:
                    proxy_arg = {"server": f"{px.type}://{px.host}:{px.port}"}
                    if px.username:
                        proxy_arg.update(username=px.username, password=px.get_password())

            # 3) Argumen browser
            win_h = fp.screen_height - 48
            args = [
                "--disable-blink-features=AutomationControlled",
                f"--window-size={fp.screen_width},{win_h}",
                "--window-position=0,0",
                f"--lang={fp.locale}",
                "--no-default-browser-check",
                "--disable-features=Translate,OptimizationHints,MediaRouter",
            ]
            if fp.webrtc in ("proxy", "disable"):
                args.append("--force-webrtc-ip-handling-policy=disable_non_proxied_udp")

            user_data_dir.mkdir(parents=True, exist_ok=True)
            _write_prefs(user_data_dir, fp)
            if fp.block_service_worker:
                # Service worker lama (terdaftar sebelum diblokir) bisa membaca hardware asli
                shutil.rmtree(user_data_dir / "Default" / "Service Worker", ignore_errors=True)

            opts = dict(
                headless=False,
                no_viewport=True,
                args=args,
                ignore_default_args=["--enable-automation", "--disable-extensions"],
                locale=fp.locale,
                proxy=proxy_arg,
                accept_downloads=True,
            )
            browser = resolve_browser(profile.browser)
            if browser in ("chrome", "msedge"):
                opts["channel"] = browser
            if fp.user_agent.strip():
                opts["user_agent"] = fp.user_agent.strip()
            if fp.timezone:
                opts["timezone_id"] = fp.timezone
            if fp.geo_enabled:
                opts["geolocation"] = {"latitude": fp.latitude, "longitude": fp.longitude, "accuracy": 50}
                opts["permissions"] = ["geolocation"]

            self.sink(("status", pid, "starting", "Membuka browser..."))
            pw = await self._playwright()
            ctx = await pw.chromium.launch_persistent_context(str(user_data_dir), **opts)
            await ctx.add_init_script(build_stealth_script(fp))

            inst = Instance(pid, ctx, relay)
            self.instances[pid] = inst
            ctx.on("close", lambda _c: asyncio.ensure_future(self._cleanup(pid)))

            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            if profile.start_url:
                try:
                    await page.goto(profile.start_url, timeout=45000)
                except Exception as e:  # halaman gagal dimuat bukan alasan menutup browser
                    self.sink(("log", pid, f"Gagal membuka {profile.start_url}: {e}"))
            self.sink(("status", pid, "running", "Berjalan"))
        except Exception as e:
            if relay:
                await relay.close()
            self.sink(("status", pid, "error", _friendly_error(e, profile)))
        finally:
            self._starting.discard(pid)

    async def _cleanup(self, pid: str) -> None:
        inst = self.instances.pop(pid, None)
        if inst and inst.relay:
            await inst.relay.close()
        self.sink(("status", pid, "stopped", "Berhenti"))

    async def _stop(self, pid: str) -> None:
        inst = self.instances.get(pid)
        if inst:
            try:
                await inst.context.close()
            except Exception:
                pass
            await self._cleanup(pid)

    async def _shutdown(self) -> None:
        await asyncio.gather(*(self._stop(pid) for pid in list(self.instances)), return_exceptions=True)
        if self._pw:
            await self._pw.stop()
            self._pw = None
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for t in pending:
            t.cancel()
        await asyncio.gather(*pending, return_exceptions=True)


def installed_browsers() -> list[str]:
    found = []
    bases = [os.environ.get(k) for k in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
    for name, rel in (("chrome", r"Google\Chrome\Application\chrome.exe"),
                      ("msedge", r"Microsoft\Edge\Application\msedge.exe")):
        if any(b and Path(b, rel).exists() for b in bases):
            found.append(name)
    return found


def resolve_browser(choice: str) -> str:
    """'auto' = Chrome kalau ada, kalau tidak Edge (selalu ada di Windows 10/11)."""
    if choice != "auto":
        return choice
    found = installed_browsers()
    return found[0] if found else "chromium"


def _friendly_error(e: Exception, profile: Profile) -> str:
    msg = str(e)
    if "Executable doesn't exist" in msg or "is not found at" in msg or "chromium distribution" in msg.lower():
        if resolve_browser(profile.browser) == "chromium":
            return ("Tidak ditemukan Google Chrome maupun Microsoft Edge di komputer ini.\n"
                    "Silakan pasang Google Chrome, lalu coba lagi.")
        return (f"Browser '{profile.browser}' tidak ditemukan di komputer ini.\n"
                "Edit profil dan pilih Browser: Otomatis.")
    if "user data directory is already in use" in msg.lower() or "ProcessSingleton" in msg:
        return "Folder profil sedang dipakai proses browser lain. Tutup jendela browser profil ini dulu."
    if isinstance(e, ConnectionError):
        return msg[:600]
    return msg.splitlines()[0][:400] if msg else e.__class__.__name__
