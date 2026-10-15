"""Enkripsi password proxy dengan Windows DPAPI (terikat ke akun Windows pengguna)."""
import base64
import sys

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    _crypt32 = ctypes.windll.crypt32
    _kernel32 = ctypes.windll.kernel32
    _kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    _UI_FORBIDDEN = 0x1

    def _call(func, data: bytes) -> bytes:
        buf = ctypes.create_string_buffer(data, len(data))
        inp = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
        out = _Blob()
        if not func(ctypes.byref(inp), None, None, None, None, _UI_FORBIDDEN, ctypes.byref(out)):
            raise ctypes.WinError()
        try:
            return ctypes.string_at(out.pbData, out.cbData)
        finally:
            _kernel32.LocalFree(ctypes.cast(out.pbData, ctypes.c_void_p))

    def _protect(b: bytes) -> bytes:
        return _call(_crypt32.CryptProtectData, b)

    def _unprotect(b: bytes) -> bytes:
        return _call(_crypt32.CryptUnprotectData, b)


def protect(text: str) -> str:
    if not text:
        return ""
    if sys.platform == "win32":
        return "dpapi:" + base64.b64encode(_protect(text.encode("utf-8"))).decode()
    return "b64:" + base64.b64encode(text.encode("utf-8")).decode()


def unprotect(token: str) -> str:
    if not token:
        return ""
    try:
        kind, _, payload = token.partition(":")
        raw = base64.b64decode(payload)
        if kind == "dpapi":
            return _unprotect(raw).decode("utf-8")
        return raw.decode("utf-8")
    except Exception:
        return ""
