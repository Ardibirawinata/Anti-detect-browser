"""Cek proxy: apakah hidup, IP keluar, negara, timezone & koordinat."""
from __future__ import annotations

import time
from urllib.parse import quote

import requests

from .models import ProxyConfig

_SCHEME = {"http": "http", "https": "https", "socks5": "socks5h", "socks4": "socks4a"}


def proxy_url(p: ProxyConfig) -> str:
    auth = ""
    if p.username:
        auth = f"{quote(p.username, safe='')}:{quote(p.get_password(), safe='')}@"
    return f"{_SCHEME[p.type]}://{auth}{p.host}:{p.port}"


def check(p: ProxyConfig | None, timeout: float = 15) -> dict:
    """Kembalikan dict {ip, country, city, timezone, lat, lon, latency_ms}.
    Lempar exception kalau proxy tidak bisa dipakai."""
    proxies = None
    if p and p.enabled and p.host:
        url = proxy_url(p)
        proxies = {"http": url, "https": url}
    s = requests.Session()
    s.trust_env = False
    t0 = time.perf_counter()
    errors = []
    try:
        j = s.get("https://ipinfo.io/json", proxies=proxies, timeout=timeout).json()
        lat, lon = (float(x) for x in j["loc"].split(","))
        return {
            "ip": j["ip"], "country": j.get("country", ""), "city": j.get("city", ""),
            "timezone": j.get("timezone", ""), "lat": lat, "lon": lon,
            "latency_ms": int((time.perf_counter() - t0) * 1000),
        }
    except Exception as e:
        errors.append(f"ipinfo: {e}")
    try:
        t0 = time.perf_counter()
        j = s.get(
            "http://ip-api.com/json/?fields=status,message,query,countryCode,city,timezone,lat,lon",
            proxies=proxies, timeout=timeout,
        ).json()
        if j.get("status") != "success":
            raise RuntimeError(j.get("message", "gagal"))
        return {
            "ip": j["query"], "country": j.get("countryCode", ""), "city": j.get("city", ""),
            "timezone": j.get("timezone", ""), "lat": j.get("lat"), "lon": j.get("lon"),
            "latency_ms": int((time.perf_counter() - t0) * 1000),
        }
    except Exception as e:
        errors.append(f"ip-api: {e}")
    raise ConnectionError("Proxy tidak bisa dipakai:\n" + "\n".join(errors))
