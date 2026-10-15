"""Model data profil + penyimpanan JSON."""
from __future__ import annotations

import copy
import json
import os
import shutil
import time
import uuid
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from . import crypto, paths

PROXY_TYPES = ["http", "https", "socks5", "socks4"]
BROWSERS = ["auto", "chrome", "msedge", "chromium"]


def _from_dict(cls, d: dict):
    names = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in (d or {}).items() if k in names})


@dataclass
class ProxyConfig:
    enabled: bool = False
    type: str = "http"
    host: str = ""
    port: int = 0
    username: str = ""
    password_enc: str = ""
    auto_geo: bool = True
    last_ip: str = ""
    last_country: str = ""
    saved_id: str = ""              # id SavedProxy asal (kosong = diisi manual)

    def get_password(self) -> str:
        return crypto.unprotect(self.password_enc)

    def set_password(self, pwd: str) -> None:
        self.password_enc = crypto.protect(pwd)

    def display(self) -> str:
        if not self.enabled or not self.host:
            return "⚠ tanpa proxy (IP asli)"
        auth = f"{self.username}@" if self.username else ""
        return f"{self.type}://{auth}{self.host}:{self.port}"


def parse_proxy(text: str, default_type: str = "http") -> ProxyConfig | None:
    """Terima format:
    host:port | host:port:user:pass | type://host:port | type://user:pass@host:port
    """
    s = text.strip()
    if not s:
        return None
    ptype = default_type
    if "://" in s:
        ptype, s = s.split("://", 1)
        ptype = ptype.lower()
        ptype = {"socks5h": "socks5", "socks4a": "socks4", "socks": "socks5"}.get(ptype, ptype)
    if ptype not in PROXY_TYPES:
        raise ValueError(f"Tipe proxy tidak dikenal: {ptype}")
    user = pwd = ""
    if "@" in s:
        cred, hostport = s.rsplit("@", 1)
        user, _, pwd = cred.partition(":")
        host, _, port = hostport.rpartition(":")
    else:
        parts = s.split(":")
        if len(parts) == 4:
            host, port, user, pwd = parts
        elif len(parts) == 2:
            host, port = parts
        else:
            raise ValueError(f"Format proxy tidak valid: {text}")
    host = host.strip().strip("[]")
    if not host:
        raise ValueError(f"Host proxy kosong: {text}")
    cfg = ProxyConfig(enabled=True, type=ptype, host=host, port=int(port), username=user)
    cfg.set_password(pwd)
    return cfg


@dataclass
class Fingerprint:
    user_agent: str = ""            # kosong = UA asli browser (paling konsisten)
    platform: str = "Win32"
    locale: str = "en-US"
    languages: list = field(default_factory=lambda: ["en-US", "en"])
    timezone: str = ""              # kosong = timezone sistem
    geo_enabled: bool = False
    latitude: float = 0.0
    longitude: float = 0.0
    screen_width: int = 1920
    screen_height: int = 1080
    hardware_concurrency: int = 8
    device_memory: int = 8
    webgl_vendor: str = ""
    webgl_renderer: str = ""
    canvas_noise: bool = True
    webgl_noise: bool = True
    audio_noise: bool = True
    font_noise: bool = True
    canvas_seed: int = 0
    webgl_seed: int = 0
    audio_seed: int = 0
    font_seed: int = 0
    webgl_params: dict = field(default_factory=dict)
    webrtc: str = "proxy"           # proxy | disable | real
    block_service_worker: bool = True  # SW tidak bisa disuntik spoof -> hardware asli bocor

    def summary(self) -> str:
        return f"{self.screen_width}x{self.screen_height}"

    def gpu_short(self) -> str:
        r = self.webgl_renderer
        if r.startswith("ANGLE ("):
            parts = r[7:].split(",")
            if len(parts) > 1:
                return parts[1].strip().split(" Direct3D")[0]
        return r or "asli"


@dataclass
class Profile:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = "Profil Baru"
    notes: str = ""
    group: str = ""
    start_url: str = "https://browserleaks.com/ip"
    browser: str = "auto"
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    fingerprint: Fingerprint = field(default_factory=Fingerprint)
    created: float = field(default_factory=time.time)
    last_used: float = 0.0

    @classmethod
    def from_dict(cls, d: dict) -> "Profile":
        p = _from_dict(cls, {k: v for k, v in d.items() if k not in ("proxy", "fingerprint")})
        p.proxy = _from_dict(ProxyConfig, d.get("proxy"))
        p.fingerprint = _from_dict(Fingerprint, d.get("fingerprint"))
        return p

    def to_dict(self) -> dict:
        return asdict(self)

    def clone(self) -> "Profile":
        return copy.deepcopy(self)


class ProfileStore:
    def __init__(self, file: Path | None = None):
        self.file = file or (paths.data_dir() / "profiles.json")
        self.profiles: dict[str, Profile] = {}
        self.load()

    def load(self) -> None:
        if not self.file.exists():
            return
        data = json.loads(self.file.read_text("utf-8"))
        self.profiles = {d["id"]: Profile.from_dict(d) for d in data.get("profiles", [])}

    def save(self) -> None:
        tmp = self.file.with_suffix(".tmp")
        payload = {"version": 1, "profiles": [p.to_dict() for p in self.profiles.values()]}
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), "utf-8")
        os.replace(tmp, self.file)

    def userdata_dir(self, pid: str) -> Path:
        return paths.userdata_root() / pid

    def put(self, profile: Profile) -> None:
        self.profiles[profile.id] = profile
        self.save()

    def delete(self, pid: str, remove_data: bool = True) -> None:
        self.profiles.pop(pid, None)
        self.save()
        if remove_data:
            shutil.rmtree(self.userdata_dir(pid), ignore_errors=True)

    def duplicate(self, pid: str, new_fingerprint: Fingerprint) -> Profile:
        src = self.profiles[pid]
        p = src.clone()
        p.id = uuid.uuid4().hex[:12]
        p.name = f"{src.name} (salinan)"
        p.created = time.time()
        p.last_used = 0.0
        p.fingerprint = new_fingerprint
        self.put(p)
        return p


# ====================================================================== proxy tersimpan
@dataclass
class SavedProxy:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    type: str = "http"
    host: str = ""
    port: int = 0
    username: str = ""
    password_enc: str = ""
    last_ip: str = ""
    last_country: str = ""
    last_city: str = ""
    last_latency: int = 0
    last_check: float = 0.0
    last_ok: bool | None = None      # None = belum pernah dites
    created: float = field(default_factory=time.time)

    def get_password(self) -> str:
        return crypto.unprotect(self.password_enc)

    def set_password(self, pwd: str) -> None:
        self.password_enc = crypto.protect(pwd)

    def key(self) -> tuple:
        return (self.type, self.host.lower(), int(self.port), self.username)

    def label(self) -> str:
        return self.name or f"{self.host}:{self.port}"

    def address(self) -> str:
        return f"{self.host}:{self.port}"

    def to_config(self, auto_geo: bool = True) -> ProxyConfig:
        cfg = ProxyConfig(enabled=True, type=self.type, host=self.host, port=self.port,
                          username=self.username, password_enc=self.password_enc, auto_geo=auto_geo,
                          last_ip=self.last_ip, last_country=self.last_country, saved_id=self.id)
        return cfg

    def apply_to(self, cfg: ProxyConfig) -> None:
        """Salin data koneksi ke proxy profil (pengaturan auto_geo profil tetap)."""
        if (cfg.type, cfg.host, cfg.port) != (self.type, self.host, self.port):
            cfg.last_ip = self.last_ip
            cfg.last_country = self.last_country
        cfg.enabled = True
        cfg.type, cfg.host, cfg.port = self.type, self.host, self.port
        cfg.username, cfg.password_enc = self.username, self.password_enc
        cfg.saved_id = self.id

    @classmethod
    def from_config(cls, cfg: ProxyConfig, name: str = "") -> "SavedProxy":
        return cls(name=name, type=cfg.type, host=cfg.host, port=cfg.port, username=cfg.username,
                   password_enc=cfg.password_enc, last_ip=cfg.last_ip, last_country=cfg.last_country)


def parse_proxy_list(text: str, default_type: str = "http") -> tuple[list[ProxyConfig], list[tuple[int, str, str]]]:
    """Urai banyak proxy (satu per baris). Baris kosong & diawali '#' dilewati.
    Kembalikan (proxy_valid, [(nomor_baris, isi_baris, pesan_error), ...])."""
    ok, bad = [], []
    for i, ln in enumerate(text.splitlines(), 1):
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        try:
            cfg = parse_proxy(s, default_type)
            if cfg:
                ok.append(cfg)
        except Exception as e:  # noqa: BLE001
            bad.append((i, s, str(e)))
    return ok, bad


class ProxyStore:
    def __init__(self, file: Path | None = None):
        self.file = file or (paths.data_dir() / "proxies.json")
        self.proxies: dict[str, SavedProxy] = {}
        self.load()

    def load(self) -> None:
        if not self.file.exists():
            return
        data = json.loads(self.file.read_text("utf-8"))
        self.proxies = {d["id"]: _from_dict(SavedProxy, d) for d in data.get("proxies", [])}

    def save(self) -> None:
        tmp = self.file.with_suffix(".tmp")
        payload = {"version": 1, "proxies": [asdict(p) for p in self.proxies.values()]}
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), "utf-8")
        os.replace(tmp, self.file)

    def ordered(self) -> list[SavedProxy]:
        return sorted(self.proxies.values(), key=lambda p: p.created)

    def get(self, pid: str) -> SavedProxy | None:
        return self.proxies.get(pid) if pid else None

    def find(self, key: tuple) -> SavedProxy | None:
        return next((p for p in self.proxies.values() if p.key() == key), None)

    def put(self, proxy: SavedProxy) -> None:
        self.proxies[proxy.id] = proxy
        self.save()

    def delete(self, pid: str) -> None:
        self.proxies.pop(pid, None)
        self.save()

    def import_configs(self, configs: list[ProxyConfig], prefix: str = "") -> tuple[list[SavedProxy], int]:
        """Tambahkan banyak proxy sekaligus. Duplikat (tipe+host+port+user sama) dilewati.
        Kembalikan (proxy_baru, jumlah_duplikat)."""
        added, dup = [], 0
        seen = {p.key() for p in self.proxies.values()}
        n = len(self.proxies)
        base = time.time()
        for cfg in configs:
            sp = SavedProxy.from_config(cfg)
            if sp.key() in seen:
                dup += 1
                continue
            seen.add(sp.key())
            n += 1
            sp.name = f"{prefix} {n}".strip() if prefix else ""
            sp.created = base + len(added) * 1e-3  # jaga urutan sesuai teks
            self.proxies[sp.id] = sp
            added.append(sp)
        if added:
            self.save()
        return added, dup
