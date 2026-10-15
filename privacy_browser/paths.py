import os
import sys
from pathlib import Path


def app_dir() -> Path:
    """Folder aplikasi (folder EXE saat di-build, atau root proyek saat dev)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    """Saat terinstal: %LOCALAPPDATA%/PrivacyBrowser (folder program tidak bisa ditulisi).
    Mode portable: taruh file bernama 'portable' di samping EXE -> data disimpan di ./data."""
    if getattr(sys, "frozen", False) and not (app_dir() / "portable").exists():
        d = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "PrivacyBrowser" / "data"
    else:
        d = app_dir() / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def userdata_root() -> Path:
    d = data_dir() / "userdata"
    d.mkdir(parents=True, exist_ok=True)
    return d


def resource(name: str) -> Path:
    """File yang dibundel bersama paket (mis. stealth.js)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "privacy_browser" / name
