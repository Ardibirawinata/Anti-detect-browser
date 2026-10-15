"""Generator fingerprint yang realistis & konsisten untuk Windows + Chromium."""
from __future__ import annotations

import random

from .models import Fingerprint

# (lebar, tinggi, bobot) - resolusi desktop umum
SCREENS = [
    (1920, 1080, 40), (1366, 768, 12), (1536, 864, 10), (1440, 900, 6),
    (1600, 900, 6), (2560, 1440, 10), (1680, 1050, 4), (1280, 720, 3),
    (1280, 1024, 2), (1920, 1200, 4), (3840, 2160, 3),
]

CORES = [(4, 25), (6, 15), (8, 30), (12, 15), (16, 12), (20, 3)]
MEMORY = [(4, 20), (8, 80)]  # Chrome membatasi deviceMemory maksimal 8

# (vendor, renderer) - string ANGLE seperti yang dilaporkan Chrome di Windows
GPUS = [
    ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce GTX 1050 Ti Direct3D11 vs_5_0 ps_5_0, D3D11)"),
    ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce GTX 1060 6GB Direct3D11 vs_5_0 ps_5_0, D3D11)"),
    ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce GTX 1650 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
    ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 SUPER Direct3D11 vs_5_0 ps_5_0, D3D11)"),
    ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce RTX 2060 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
    ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
    ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce RTX 3070 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
    ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce RTX 4060 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
    ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
    ("Google Inc. (AMD)", "ANGLE (AMD, AMD Radeon RX 580 2048SP Direct3D11 vs_5_0 ps_5_0, D3D11)"),
    ("Google Inc. (AMD)", "ANGLE (AMD, AMD Radeon RX 6600 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
    ("Google Inc. (AMD)", "ANGLE (AMD, AMD Radeon RX 6700 XT Direct3D11 vs_5_0 ps_5_0, D3D11)"),
    ("Google Inc. (AMD)", "ANGLE (AMD, AMD Radeon(TM) Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)"),
    ("Google Inc. (Intel)", "ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
    ("Google Inc. (Intel)", "ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
    ("Google Inc. (Intel)", "ANGLE (Intel, Intel(R) UHD Graphics 770 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
    ("Google Inc. (Intel)", "ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)"),
    ("Google Inc. (Intel)", "ANGLE (Intel, Intel(R) HD Graphics 520 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
]

# Parameter WebGL (ANGLE/D3D11) per vendor GPU.
# getParameter selain vendor/renderer ikut dipalsukan supaya konsisten dengan
# kartu grafis yang diklaim dan tidak sama di semua profil.
_GL_BASE = {
    # WebGL1
    "34921": 16,        # MAX_VERTEX_ATTRIBS
    "36347": 4096,      # MAX_VERTEX_UNIFORM_VECTORS
    "36349": 1024,      # MAX_FRAGMENT_UNIFORM_VECTORS
    "36348": 30,        # MAX_VARYING_VECTORS
    "34930": 16,        # MAX_TEXTURE_IMAGE_UNITS
    "35660": 16,        # MAX_VERTEX_TEXTURE_IMAGE_UNITS
    "35661": 32,        # MAX_COMBINED_TEXTURE_IMAGE_UNITS
    "33902": [1, 1],    # ALIASED_LINE_WIDTH_RANGE (D3D11 hanya 1px)
    "34047": 16,        # MAX_TEXTURE_MAX_ANISOTROPY_EXT
    # WebGL2
    "34852": 8,         # MAX_DRAW_BUFFERS
    "36063": 8,         # MAX_COLOR_ATTACHMENTS
    "36303": 24,        # MAX_UNIFORM_BUFFER_BINDINGS
    "35371": 14,        # MAX_VERTEX_UNIFORM_BLOCKS
    "35373": 14,        # MAX_FRAGMENT_UNIFORM_BLOCKS
    "35376": 65536,     # MAX_UNIFORM_BLOCK_SIZE
    "34045": 15,        # MAX_TEXTURE_LOD_BIAS
    "35659": 120,       # MAX_VARYING_COMPONENTS
    "35979": 4,         # MAX_TRANSFORM_FEEDBACK_SEPARATE_ATTRIBS
    "36203": 4294967294,  # MAX_ELEMENT_INDEX
}

_GL_VENDOR = {
    "NVIDIA": {
        "3379": 16384, "34076": 16384, "34024": 16384,   # MAX_TEXTURE/CUBE_MAP/RENDERBUFFER_SIZE
        "3386": [32767, 32767],                          # MAX_VIEWPORT_DIMS
        "33901": [1, 1024],                              # ALIASED_POINT_SIZE_RANGE
        "32883": 2048, "35071": 2048,                    # MAX_3D_TEXTURE_SIZE, MAX_ARRAY_TEXTURE_LAYERS
        "36183": 8,                                      # MAX_SAMPLES
    },
    "AMD": {
        "3379": 16384, "34076": 16384, "34024": 16384,
        "3386": [16384, 16384],
        "33901": [1, 255],
        "32883": 2048, "35071": 2048,
        "36183": 8,
    },
    "Intel": {
        "3379": 16384, "34076": 16384, "34024": 8192,
        "3386": [16384, 16384],
        "33901": [1, 255],
        "32883": 1024, "35071": 512,
        "36183": 4,
    },
}

# GPU Intel lama (Skylake) punya batas tekstur lebih kecil
_GL_GPU_OVERRIDES = {
    "HD Graphics 520": {"3379": 8192, "34076": 8192, "34024": 8192},
}


def gl_params_for(vendor: str, renderer: str) -> dict:
    params = dict(_GL_BASE)
    for key, table in _GL_VENDOR.items():
        if key in vendor:
            params.update(table)
            break
    for name, extra in _GL_GPU_OVERRIDES.items():
        if name in renderer:
            params.update(extra)
    return params

TIMEZONES = [
    "", "Asia/Jakarta", "Asia/Makassar", "Asia/Jayapura", "Asia/Singapore",
    "Asia/Kuala_Lumpur", "Asia/Bangkok", "Asia/Ho_Chi_Minh", "Asia/Manila",
    "Asia/Tokyo", "Asia/Seoul", "Asia/Shanghai", "Asia/Hong_Kong", "Asia/Kolkata",
    "Asia/Dubai", "Europe/London", "Europe/Berlin", "Europe/Paris", "Europe/Amsterdam",
    "Europe/Madrid", "Europe/Rome", "Europe/Moscow", "Europe/Istanbul",
    "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
    "America/Toronto", "America/Sao_Paulo", "America/Mexico_City", "Australia/Sydney",
]

COUNTRY_LOCALE = {
    "US": "en-US", "GB": "en-GB", "CA": "en-CA", "AU": "en-AU", "NZ": "en-NZ",
    "IE": "en-IE", "IN": "en-IN", "SG": "en-SG", "PH": "en-PH", "ZA": "en-ZA",
    "ID": "id-ID", "MY": "ms-MY", "TH": "th-TH", "VN": "vi-VN", "JP": "ja-JP",
    "KR": "ko-KR", "CN": "zh-CN", "TW": "zh-TW", "HK": "zh-HK", "DE": "de-DE",
    "AT": "de-AT", "CH": "de-CH", "FR": "fr-FR", "BE": "fr-BE", "ES": "es-ES",
    "MX": "es-MX", "AR": "es-AR", "CO": "es-CO", "CL": "es-CL", "IT": "it-IT",
    "NL": "nl-NL", "PT": "pt-PT", "BR": "pt-BR", "RU": "ru-RU", "UA": "uk-UA",
    "PL": "pl-PL", "TR": "tr-TR", "SE": "sv-SE", "NO": "nb-NO", "DK": "da-DK",
    "FI": "fi-FI", "CZ": "cs-CZ", "RO": "ro-RO", "HU": "hu-HU", "GR": "el-GR",
    "IL": "he-IL", "SA": "ar-SA", "AE": "ar-AE", "EG": "ar-EG", "BD": "bn-BD",
    "PK": "en-PK", "NG": "en-NG",
}


def _weighted(items):
    values = [i[:-1] if len(i) > 2 else i[0] for i in items]
    weights = [i[-1] for i in items]
    return random.choices(values, weights=weights, k=1)[0]


def languages_for(locale: str) -> list[str]:
    lang = locale.split("-")[0]
    langs = [locale]
    if lang != locale:
        langs.append(lang)
    if lang != "en":
        langs += ["en-US", "en"]
    return langs


def generate(locale: str = "en-US", timezone: str = "") -> Fingerprint:
    w, h = _weighted(SCREENS)
    vendor, renderer = random.choice(GPUS)
    cores = _weighted(CORES)
    # laptop iGPU jarang punya 16+ core - jaga kombinasi tetap masuk akal
    if "Intel" in vendor and cores > 12:
        cores = random.choice([4, 8, 12])
    return Fingerprint(
        locale=locale,
        languages=languages_for(locale),
        timezone=timezone,
        screen_width=w,
        screen_height=h,
        hardware_concurrency=cores,
        device_memory=_weighted(MEMORY),
        webgl_vendor=vendor,
        webgl_renderer=renderer,
        canvas_seed=random.randint(1, 2**31 - 1),
        webgl_seed=random.randint(1, 2**31 - 1),
        audio_seed=random.randint(1, 2**31 - 1),
        font_seed=random.randint(1, 2**31 - 1),
        webgl_params=gl_params_for(vendor, renderer),
    )


def apply_geo(fp: Fingerprint, geo: dict) -> None:
    """Samakan timezone, bahasa & lokasi dengan IP proxy."""
    if geo.get("timezone"):
        fp.timezone = geo["timezone"]
    loc = COUNTRY_LOCALE.get((geo.get("country") or "").upper())
    if loc:
        fp.locale = loc
        fp.languages = languages_for(loc)
    if geo.get("lat") is not None and geo.get("lon") is not None:
        # sedikit jitter supaya tidak tepat di koordinat pusat kota milik database GeoIP
        fp.latitude = round(float(geo["lat"]) + random.uniform(-0.02, 0.02), 5)
        fp.longitude = round(float(geo["lon"]) + random.uniform(-0.02, 0.02), 5)
        fp.geo_enabled = True


def to_js_config(fp: Fingerprint) -> dict:
    """Konfigurasi yang dibaca oleh stealth.js."""
    return {
        "platform": fp.platform,
        "hardwareConcurrency": fp.hardware_concurrency,
        "deviceMemory": fp.device_memory,
        "languages": fp.languages,
        "screen": {
            "width": fp.screen_width,
            "height": fp.screen_height,
            "availWidth": fp.screen_width,
            "availHeight": fp.screen_height - 48,  # taskbar Windows 11
        },
        "canvasSeed": fp.canvas_seed if fp.canvas_noise else 0,
        "webglSeed": fp.webgl_seed if fp.webgl_noise else 0,
        "audioSeed": fp.audio_seed if fp.audio_noise else 0,
        "fontSeed": fp.font_seed if fp.font_noise else 0,
        "webglVendor": fp.webgl_vendor,
        "webglRenderer": fp.webgl_renderer,
        "webglParams": fp.webgl_params or gl_params_for(fp.webgl_vendor, fp.webgl_renderer),
        "webrtc": fp.webrtc,
        "blockServiceWorker": fp.block_service_worker,
    }
