"""Antarmuka pengelola profil (Tkinter) - tampilan modern ala GoLogin/MoreLogin, tetap sederhana untuk pengguna awam."""
from __future__ import annotations

import os
import queue
import threading
import time
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from tkinter import font as tkfont
from tkinter import messagebox, ttk

from . import __version__, paths, proxy_check
from . import fingerprint as fpgen
from .engine import Engine, installed_browsers
from .models import (BROWSERS, PROXY_TYPES, Profile, ProfileStore, ProxyConfig, ProxyStore, SavedProxy,
                     parse_proxy, parse_proxy_list)

APP_NAME = "Privacy Browser"

BROWSER_LABELS = {
    "auto": "Otomatis (disarankan)",
    "chrome": "Google Chrome",
    "msedge": "Microsoft Edge",
    "chromium": "Chromium bawaan",
}
WEBRTC_LABELS = {
    "proxy": "Lewat proxy saja (disarankan)",
    "disable": "Matikan WebRTC",
    "real": "Asli (tidak dilindungi)",
}
STATUS_LABELS = {
    "running": "Berjalan",
    "starting": "Memulai...",
    "stopped": "Siap",
    "error": "Gagal",
}

# ====================================================================== tema
C = {
    "bg": "#F4F6FB",
    "surface": "#FFFFFF",
    "hover": "#F3F4F6",
    "border": "#E5E7EB",
    "border_strong": "#D1D5DB",
    "text": "#111827",
    "muted": "#6B7280",
    "subtle": "#9CA3AF",
    "primary": "#4F46E5",
    "primary_hover": "#4338CA",
    "primary_soft": "#EEF2FF",
    "select": "#E0E7FF",
    "sidebar": "#0F172A",
    "sidebar_hover": "#1E293B",
    "sidebar_active": "#1E1B4B",
    "sidebar_text": "#CBD5E1",
    "sidebar_muted": "#64748B",
    "success": "#16A34A",
    "success_soft": "#DCFCE7",
    "warn": "#D97706",
    "warn_soft": "#FEF3C7",
    "danger": "#DC2626",
    "danger_soft": "#FEE2E2",
    "idle": "#CBD5E1",
}
STATUS_COLORS = {  # titik di daftar, (teks, latar) untuk badge
    "running": (C["success"], C["success_soft"]),
    "starting": (C["warn"], C["warn_soft"]),
    "error": (C["danger"], C["danger_soft"]),
    "stopped": (C["muted"], C["hover"]),
}
FONT = "Segoe UI"
FONT_B = "Segoe UI Semibold"

# Glyph Segoe Fluent Icons (Win11) / Segoe MDL2 Assets (Win10)
ICONS = {
    "add": "", "play": "", "stop": "", "edit": "", "copy": "",
    "delete": "", "globe": "", "search": "", "folder": "", "people": "",
    "group": "", "shield": "", "shuffle": "", "help": "", "close": "",
    "info": "", "check": "",
    "paste": "", "network": "", "refresh": "",
}
_ICON_FONT: str | None = None
_SCALE = 1.0


def px(n: float) -> int:
    """Ukuran piksel yang ikut skala layar (DPI)."""
    return int(round(n * _SCALE))


def ico(name: str) -> str:
    return ICONS.get(name, "") if _ICON_FONT else ""


def init_theme(root: tk.Tk) -> None:
    global _ICON_FONT, _SCALE
    _SCALE = max(1.0, root.winfo_fpixels("1i") / 96)
    fams = set(tkfont.families(root))
    _ICON_FONT = next((f for f in ("Segoe Fluent Icons", "Segoe MDL2 Assets") if f in fams), None)

    root.option_add("*Font", (FONT, 10))
    root.option_add("*TCombobox*Listbox.font", (FONT, 10))
    root.option_add("*TCombobox*Listbox.background", C["surface"])
    root.option_add("*TCombobox*Listbox.selectBackground", C["select"])
    root.option_add("*TCombobox*Listbox.selectForeground", C["text"])
    root.option_add("*TCombobox*Listbox.borderWidth", 0)

    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure(".", background=C["surface"], foreground=C["text"], font=(FONT, 10),
                bordercolor=C["border"], lightcolor=C["surface"], darkcolor=C["surface"],
                troughcolor=C["bg"], focuscolor=C["primary"], selectbackground=C["select"],
                selectforeground=C["text"], insertcolor=C["text"])
    s.configure("TFrame", background=C["surface"])
    s.configure("TLabel", background=C["surface"], foreground=C["text"])
    s.configure("Hint.TLabel", foreground=C["muted"], font=(FONT, 9))
    s.configure("Field.TLabel", foreground="#374151", font=(FONT_B, 9))
    s.configure("TSeparator", background=C["border"])

    for w in ("TEntry", "TCombobox", "TSpinbox"):
        s.configure(w, fieldbackground=C["surface"], background=C["surface"], bordercolor=C["border_strong"],
                    lightcolor=C["surface"], darkcolor=C["surface"], padding=(px(8), px(5)),
                    arrowcolor=C["muted"], arrowsize=px(12))
        s.map(w, bordercolor=[("focus", C["primary"])], lightcolor=[("focus", C["primary"])],
              fieldbackground=[("disabled", C["hover"]), ("readonly", C["surface"])],
              foreground=[("disabled", C["subtle"])], arrowcolor=[("disabled", C["subtle"])],
              selectbackground=[("readonly", C["surface"])], selectforeground=[("readonly", C["text"])])

    for kind in ("Checkbutton", "Radiobutton"):
        on, off, dis_on, dis_off = (_indicator(root, kind == "Radiobutton", sel, dis)
                                    for sel, dis in ((True, False), (False, False), (True, True), (False, True)))
        s.element_create(f"Pb.{kind}.indicator", "image", off, ("disabled", "selected", dis_on),
                         ("disabled", dis_off), ("selected", on), sticky="w")
        s.layout(f"T{kind}", [(f"{kind}.padding", {"sticky": "nswe", "children": [
            (f"Pb.{kind}.indicator", {"side": "left", "sticky": ""}),
            (f"{kind}.label", {"side": "left", "sticky": "nswe"})]})])
        s.configure(f"T{kind}", background=C["surface"], foreground=C["text"], padding=(0, px(2)))
        s.map(f"T{kind}", foreground=[("disabled", C["subtle"])], background=[("active", C["surface"])])

    s.configure("TNotebook", background=C["surface"], borderwidth=0, tabmargins=(0, 0, 0, px(8)),
                bordercolor=C["border"], lightcolor=C["surface"], darkcolor=C["surface"])
    s.configure("TNotebook.Tab", background=C["surface"], foreground=C["muted"], padding=(px(16), px(8)),
                font=(FONT_B, 10), borderwidth=0, bordercolor=C["surface"], lightcolor=C["surface"])
    s.map("TNotebook.Tab", foreground=[("selected", C["primary"]), ("active", C["text"])],
          background=[("selected", C["primary_soft"]), ("active", C["hover"])],
          lightcolor=[("selected", C["primary_soft"])], bordercolor=[("selected", C["primary_soft"])],
          expand=[("selected", (0, 0, 0, 0))])

    s.layout("Slim.Vertical.TScrollbar", [("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
        ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
    s.configure("Slim.Vertical.TScrollbar", troughcolor=C["surface"], background=C["border_strong"],
                bordercolor=C["surface"], lightcolor=C["border_strong"], darkcolor=C["border_strong"],
                arrowsize=px(8), gripcount=0)
    s.map("Slim.Vertical.TScrollbar", background=[("active", C["subtle"])])

    s.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    s.layout("Treeview.Item", [("Treeitem.padding", {"sticky": "nswe", "children": [
        ("Treeitem.image", {"side": "left", "sticky": ""}),
        ("Treeitem.text", {"side": "left", "sticky": ""})]})])
    s.configure("Treeview", background=C["surface"], fieldbackground=C["surface"], foreground=C["text"],
                rowheight=px(42), borderwidth=0, relief="flat", font=(FONT, 10), indent=0)
    s.map("Treeview", background=[("selected", C["select"])], foreground=[("selected", C["text"])])
    s.configure("Treeview.Heading", background=C["surface"], foreground=C["muted"], font=(FONT_B, 9),
                relief="flat", borderwidth=0, padding=(px(6), px(10)), bordercolor=C["border"],
                lightcolor=C["surface"], darkcolor=C["border"])
    s.map("Treeview.Heading", background=[("active", C["hover"])])

    s.configure("TButton", background=C["surface"], foreground=C["text"], bordercolor=C["border_strong"],
                padding=(px(12), px(6)), font=(FONT_B, 10))
    s.map("TButton", background=[("active", C["hover"])])


_IMAGES: list[tk.PhotoImage] = []  # simpan referensi supaya gambar tidak hilang


def _raster(master, w: int, h: int, layers, bg=C["surface"], n=4) -> tk.PhotoImage:
    """Gambar bentuk sederhana dengan anti-alias. layers = [(fungsi_di_dalam(x, y), warna), ...]."""
    def rgb(c):
        return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))
    cols = [(f, rgb(c)) for f, c in layers]
    base = rgb(bg)
    rows = []
    for y in range(h):
        row = []
        for x in range(w):
            acc = [0, 0, 0]
            for i in range(n):
                for j in range(n):
                    sx, sy = x + (i + .5) / n, y + (j + .5) / n
                    c = base
                    for f, col in cols:
                        if f(sx, sy):
                            c = col
                    acc = [a + v for a, v in zip(acc, c)]
            row.append("#%02x%02x%02x" % tuple(int(a / (n * n)) for a in acc))
        rows.append("{" + " ".join(row) + "}")
    img = tk.PhotoImage(master=master, width=w, height=h)
    img.put(" ".join(rows))
    _IMAGES.append(img)
    return img


def _indicator(master, radio: bool, selected: bool, disabled: bool) -> tk.PhotoImage:
    """Kotak centang / tombol radio modern (pengganti tanda X bawaan tema)."""
    s = px(16)
    w, h, oy = s + px(8), s + 2, 1
    r = s / 2
    cx, cy = r, oy + r
    edge = C["primary"] if selected and not disabled else (C["subtle"] if selected else C["border_strong"])
    fill = C["hover"] if disabled else C["surface"]
    if radio:
        def circ(rr):
            return lambda x, y: (x - cx) ** 2 + (y - cy) ** 2 <= rr * rr
        if selected:
            return _raster(master, w, h, [(circ(r), edge), (circ(r * .38), C["surface"])])
        return _raster(master, w, h, [(circ(r), edge), (circ(r - 1.3), fill)])

    rad = px(4)

    def rrect(inset):
        def f(x, y):
            x0, y0, x1, y1 = inset, oy + inset, s - inset, oy + s - inset
            if not (x0 <= x <= x1 and y0 <= y <= y1):
                return False
            ra = max(rad - inset, 0)
            dx = max(x0 + ra - x, 0, x - (x1 - ra))
            dy = max(y0 + ra - y, 0, y - (y1 - ra))
            return dx * dx + dy * dy <= ra * ra
        return f

    if not selected:
        return _raster(master, w, h, [(rrect(0), edge), (rrect(1.3), fill)])
    pts = [(.25 * s, oy + .52 * s), (.43 * s, oy + .70 * s), (.76 * s, oy + .32 * s)]
    th = .085 * s

    def tick(x, y):
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            vx, vy = bx - ax, by - ay
            t = max(0, min(1, ((x - ax) * vx + (y - ay) * vy) / (vx * vx + vy * vy)))
            if (x - ax - t * vx) ** 2 + (y - ay - t * vy) ** 2 <= th * th:
                return True
        return False
    return _raster(master, w, h, [(rrect(0), edge), (tick, C["surface"])])


def run_bg(widget: tk.Misc, fn, done) -> None:
    """Jalankan fn() di thread lain, panggil done(hasil, error) di thread GUI."""
    box: dict = {}

    def work():
        try:
            box["ok"] = fn()
        except Exception as e:  # noqa: BLE001
            box["err"] = e

    t = threading.Thread(target=work, daemon=True)
    t.start()

    def poll():
        if t.is_alive():
            widget.after(120, poll)
        else:
            done(box.get("ok"), box.get("err"))

    widget.after(120, poll)


def fmt_geo(geo: dict) -> str:
    place = ", ".join(x for x in (geo.get("city"), geo.get("country")) if x)
    return f"IP {geo['ip']} — {place} — {geo.get('timezone', '')} ({geo.get('latency_ms', '?')} ms)"


def fmt_proxy(p: Profile) -> str:
    px_ = p.proxy
    if not px_.enabled or not px_.host:
        return "Tanpa proxy"
    return f"{px_.type.upper()}  ·  {px_.host}:{px_.port}"


def fmt_loc(p: Profile) -> str:
    if not p.proxy.enabled:
        return "IP asli komputer"
    if p.proxy.last_ip:
        return f"{p.proxy.last_country}  {p.proxy.last_ip}".strip()
    return "Belum dicek"


def make_dot(master: tk.Misc, color: str, bg: str = C["surface"]) -> tk.PhotoImage:
    """Titik status bulat (anti-alias sederhana) untuk kolom nama di daftar."""
    w, h, d = px(26), px(14), px(9)
    cx, cy, r = px(13), h / 2, d / 2
    img = tk.PhotoImage(master=master, width=w, height=h)
    c1 = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))
    c0 = tuple(int(bg[i:i + 2], 16) for i in (1, 3, 5))
    n = 4
    for y in range(h):
        for x in range(w):
            cov = sum((x + (i + .5) / n - cx) ** 2 + (y + (j + .5) / n - cy) ** 2 <= r * r
                      for i in range(n) for j in range(n)) / (n * n)
            if cov:
                rgb = tuple(int(a * cov + b * (1 - cov)) for a, b in zip(c1, c0))
                img.put("#%02x%02x%02x" % rgb, (x, y))
    return img


# ====================================================================== widget dasar
class Btn(tk.Frame):
    """Tombol datar modern dengan ikon + teks dan efek hover."""
    # bg, fg, hover, border, bg nonaktif, fg nonaktif
    STYLES = {
        "primary": (C["primary"], "#FFFFFF", C["primary_hover"], C["primary"], "#C7D2FE", "#FFFFFF"),
        "secondary": (C["surface"], C["text"], C["hover"], C["border_strong"], C["surface"], C["subtle"]),
        "danger": (C["surface"], C["danger"], C["danger_soft"], C["border_strong"], C["surface"], C["subtle"]),
        "danger_solid": (C["danger"], "#FFFFFF", "#B91C1C", C["danger"], "#FECACA", "#FFFFFF"),
        "ghost": (C["surface"], C["muted"], C["hover"], C["surface"], C["surface"], C["subtle"]),
    }
    SIZES = {"sm": (10, 5, 9), "md": (14, 7, 10), "lg": (18, 10, 10)}

    def __init__(self, master, text="", command=None, icon=None, variant="secondary", size="md"):
        self.colors = self.STYLES[variant]
        bg, fg, _h, border, _db, dfg = self.colors
        super().__init__(master, bg=bg, highlightthickness=1, highlightbackground=border,
                         highlightcolor=border, cursor="hand2")
        self.command = command
        self.enabled = True
        padx, pady, fsize = self.SIZES[size]
        inner = tk.Frame(self, bg=bg)
        inner.pack(padx=px(padx), pady=px(pady), expand=True)
        self._parts: list[tk.Widget] = [self, inner]
        self._labels: list[tk.Label] = []
        glyph = ico(icon) if icon else ""
        if glyph:
            li = tk.Label(inner, text=glyph, font=(_ICON_FONT, fsize), bg=bg, fg=fg, disabledforeground=dfg)
            li.pack(side="left", padx=(0, px(7) if text else 0))
            self._labels.append(li)
        if text:
            lt = tk.Label(inner, text=text, font=(FONT_B, fsize), bg=bg, fg=fg, disabledforeground=dfg)
            lt.pack(side="left")
            self._labels.append(lt)
        self._parts += self._labels
        for w in self._parts:
            w.bind("<Enter>", self._enter)
            w.bind("<Leave>", self._leave)
            w.bind("<ButtonRelease-1>", self._release)

    def _paint(self, bg, fg, border):
        tk.Frame.configure(self, bg=bg, highlightbackground=border, highlightcolor=border)
        for w in self._parts[1:]:
            w.configure(bg=bg)
        for lb in self._labels:
            lb.configure(fg=fg)

    def _normal(self):
        bg, fg, _h, border, dbg, dfg = self.colors
        if self.enabled:
            self._paint(bg, fg, border)
        else:
            self._paint(dbg, dfg, border if dbg == C["surface"] else dbg)

    def _enter(self, _e=None):
        if self.enabled:
            bg, fg, hover, border, *_ = self.colors
            self._paint(hover, fg, hover if bg != C["surface"] else border)

    def _leave(self, _e=None):
        self._normal()

    def _release(self, e):
        if self.enabled and self.command and self.winfo_containing(e.x_root, e.y_root) in self._parts:
            self.command()

    def set_state(self, enabled: bool):
        self.enabled = bool(enabled)
        tk.Frame.configure(self, cursor="hand2" if self.enabled else "arrow")
        for lb in self._labels:
            lb.configure(state="normal")
        self._normal()

    def configure(self, cnf=None, **kw):  # dukung .configure(state=...) seperti tombol ttk
        if "state" in kw:
            self.set_state(kw.pop("state") != "disabled")
        if cnf or kw:
            return tk.Frame.configure(self, cnf, **kw)
        return None

    config = configure


class NavItem(tk.Frame):
    """Item menu di sidebar."""

    def __init__(self, master, text, icon, command, active=False):
        super().__init__(master, bg=C["sidebar"], cursor="hand2")
        self.command = command
        self.active = active
        self.bar = tk.Frame(self, bg=C["sidebar"], width=px(3))
        self.bar.pack(side="left", fill="y")
        self.body = tk.Frame(self, bg=C["sidebar"])
        self.body.pack(side="left", fill="both", expand=True, padx=(px(12), px(10)), pady=px(9))
        self.l_icon = tk.Label(self.body, text=ico(icon) or "•", font=(_ICON_FONT or FONT, 11), bg=C["sidebar"])
        self.l_icon.pack(side="left", padx=(0, px(12)))
        self.l_text = tk.Label(self.body, text=text, font=(FONT_B, 10), bg=C["sidebar"])
        self.l_text.pack(side="left")
        for w in (self, self.body, self.l_icon, self.l_text):
            w.bind("<Enter>", lambda e: self._paint(True))
            w.bind("<Leave>", lambda e: self._paint(False))
            w.bind("<ButtonRelease-1>", lambda e: self.command())
        self._paint(False)

    def set_active(self, active: bool):
        self.active = active
        self._paint(False)

    def _paint(self, hover):
        bg = C["sidebar_active"] if self.active else (C["sidebar_hover"] if hover else C["sidebar"])
        fg = "#FFFFFF" if self.active or hover else C["sidebar_text"]
        for w in (self, self.body, self.l_icon, self.l_text):
            w.configure(bg=bg)
        self.l_icon.configure(fg="#A5B4FC" if self.active else fg)
        self.l_text.configure(fg=fg)
        self.bar.configure(bg=C["primary"] if self.active else bg)


class SearchBox(tk.Frame):
    """Kotak cari dengan ikon dan placeholder."""

    def __init__(self, master, variable: tk.StringVar, placeholder: str, width=32):
        super().__init__(master, bg=C["surface"], highlightthickness=1,
                         highlightbackground=C["border_strong"], highlightcolor=C["primary"])
        if _ICON_FONT:
            tk.Label(self, text=ico("search"), font=(_ICON_FONT, 10), fg=C["subtle"], bg=C["surface"]
                     ).pack(side="left", padx=(px(10), 0))
        self.entry = tk.Entry(self, textvariable=variable, relief="flat", bd=0, width=width, bg=C["surface"],
                              fg=C["text"], insertbackground=C["text"], font=(FONT, 10))
        self.entry.pack(side="left", fill="x", expand=True, padx=px(8), pady=px(7))
        self.ph = tk.Label(self, text=placeholder, fg=C["subtle"], bg=C["surface"], font=(FONT, 10), cursor="xterm")
        self.ph.bind("<Button-1>", lambda e: self.entry.focus_set())
        self.var = variable
        variable.trace_add("write", lambda *_: self._sync())
        self.entry.bind("<FocusIn>", lambda e: self.configure(highlightbackground=C["primary"]))
        self.entry.bind("<FocusOut>", lambda e: self.configure(highlightbackground=C["border_strong"]))
        self.entry.bind("<Escape>", lambda e: variable.set(""))
        self.after_idle(self._sync)

    def _sync(self):
        if self.var.get():
            self.ph.place_forget()
        else:
            self.ph.place(in_=self.entry, x=0, rely=0.5, anchor="w")


def styled_text(master, **kw) -> tk.Text:
    return tk.Text(master, relief="flat", bd=0, highlightthickness=1, highlightbackground=C["border_strong"],
                   highlightcolor=C["primary"], padx=px(8), pady=px(6), bg=C["surface"], fg=C["text"],
                   insertbackground=C["text"], **kw)


def dialog_header(parent, title: str, subtitle: str):
    head = tk.Frame(parent, bg=C["surface"])
    head.pack(fill="x", pady=(0, px(12)))
    tk.Label(head, text=title, font=(FONT_B, 14), bg=C["surface"], fg=C["text"]).pack(anchor="w")
    tk.Label(head, text=subtitle, font=(FONT, 9), bg=C["surface"], fg=C["muted"]).pack(anchor="w", pady=(px(2), 0))


def dialog_footer(parent, buttons):
    tk.Frame(parent, bg=C["border"], height=1).pack(fill="x", pady=(px(16), px(12)))
    bar = tk.Frame(parent, bg=C["surface"])
    bar.pack(fill="x")
    for b in buttons:
        b(bar).pack(side="right", padx=(px(8), 0))


def run_many(widget: tk.Misc, items: list, fn, on_one, on_all, workers: int = 8) -> None:
    """Jalankan fn(item) paralel (maks. `workers` sekaligus); on_one(item, hasil, error) & on_all() di thread GUI."""
    ex = ThreadPoolExecutor(max_workers=workers)
    futs = {ex.submit(fn, it): it for it in items}
    pending = set(futs)

    def poll():
        for fu in [f for f in pending if f.done()]:
            pending.discard(fu)
            err = fu.exception()
            on_one(futs[fu], None if err else fu.result(), err)
        if pending:
            widget.after(150, poll)
        else:
            ex.shutdown(wait=False)
            on_all()

    widget.after(150, poll)


def form_row(parent, r, label, widget, hint=None):
    ttk.Label(parent, text=label, style="Field.TLabel").grid(row=r, column=0, sticky="w", pady=px(5),
                                                            padx=(0, px(14)))
    widget.grid(row=r, column=1, sticky="we", pady=px(5))
    if hint:
        ttk.Label(parent, text=hint, style="Hint.TLabel").grid(row=r + 1, column=1, sticky="w")


PROXY_FORMAT_HINT = "Contoh: 1.2.3.4:8080  •  1.2.3.4:8080:user:pass  •  socks5://user:pass@host:1080"


class ProxyFields:
    """Isian proxy (tempel + tipe/host/port/user/pass) yang di-grid ke `parent` mulai baris `row0`.
    Dipakai di dialog profil (mode manual) dan dialog edit proxy tersimpan."""

    def __init__(self, parent, src, row0: int = 0, on_filled=None):
        self.parent = parent
        self.on_filled = on_filled
        self.v_paste = tk.StringVar()
        self.v_type = tk.StringVar(value=src.type or "http")
        self.v_host = tk.StringVar(value=src.host)
        self.v_port = tk.StringVar(value=str(src.port or ""))
        self.v_user = tk.StringVar(value=src.username)
        self.v_pass = tk.StringVar(value=src.get_password())
        g = parent
        g.columnconfigure(1, weight=1)
        paste = ttk.Frame(g)
        e = ttk.Entry(paste, textvariable=self.v_paste)
        e.pack(side="left", fill="x", expand=True)
        e.bind("<Return>", lambda _e: self.parse_paste())
        Btn(paste, "Isi otomatis", self.parse_paste, size="sm").pack(side="left", padx=(px(8), 0))
        form_row(g, row0, "Tempel proxy", paste, PROXY_FORMAT_HINT)
        ttk.Separator(g).grid(row=row0 + 2, column=0, columnspan=2, sticky="we", pady=px(10))
        form_row(g, row0 + 3, "Tipe", ttk.Combobox(g, textvariable=self.v_type, values=PROXY_TYPES,
                                                   state="readonly", width=12))
        form_row(g, row0 + 4, "Host / IP", ttk.Entry(g, textvariable=self.v_host))
        form_row(g, row0 + 5, "Port", ttk.Entry(g, textvariable=self.v_port, width=10))
        form_row(g, row0 + 6, "Username", ttk.Entry(g, textvariable=self.v_user))
        form_row(g, row0 + 7, "Password", ttk.Entry(g, textvariable=self.v_pass, show="•"))
        self.next_row = row0 + 8

    def parse_paste(self):
        try:
            cfg = parse_proxy(self.v_paste.get(), self.v_type.get() or "http")
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Format proxy tidak dikenali.\n\n{e}",
                                 parent=self.parent.winfo_toplevel())
            return
        if not cfg:
            return
        self.v_type.set(cfg.type)
        self.v_host.set(cfg.host)
        self.v_port.set(str(cfg.port))
        self.v_user.set(cfg.username)
        self.v_pass.set(cfg.get_password())
        self.v_paste.set("")
        if self.on_filled:
            self.on_filled()

    def read(self, target):
        """Validasi lalu tulis isian ke target (ProxyConfig / SavedProxy)."""
        host = self.v_host.get().strip()
        port = self.v_port.get().strip()
        if not host:
            raise ValueError("Host proxy belum diisi.")
        if not port.isdigit() or not 0 < int(port) < 65536:
            raise ValueError("Port proxy harus angka 1-65535.")
        target.type = self.v_type.get() or "http"
        target.host = host
        target.port = int(port)
        target.username = self.v_user.get().strip()
        target.set_password(self.v_pass.get())
        return target


def fill_check(sp: SavedProxy, geo: dict | None) -> None:
    """Catat hasil tes ke proxy tersimpan (geo None = gagal)."""
    sp.last_check = time.time()
    sp.last_ok = bool(geo)
    if geo:
        sp.last_ip, sp.last_country = geo["ip"], geo.get("country", "")
        sp.last_city, sp.last_latency = geo.get("city", ""), int(geo.get("latency_ms") or 0)


def saved_status(sp: SavedProxy) -> str:
    if sp.last_ok is None:
        return "Belum dites"
    if not sp.last_ok:
        return "Gagal / mati"
    place = " ".join(x for x in (sp.last_country, sp.last_city) if x)
    return "  ·  ".join(x for x in (place, sp.last_ip, f"{sp.last_latency} ms" if sp.last_latency else "") if x)


def proxy_line(sp: SavedProxy) -> str:
    """Satu baris proxy lengkap (bisa ditempel lagi)."""
    auth = f"{sp.username}:{sp.get_password()}@" if sp.username else ""
    return f"{sp.type}://{auth}{sp.host}:{sp.port}"


def center_on(win: tk.Toplevel):
    win.update_idletasks()
    m = win.master
    x = m.winfo_rootx() + (m.winfo_width() - win.winfo_width()) // 2
    y = m.winfo_rooty() + (m.winfo_height() - win.winfo_height()) // 3
    win.geometry(f"+{max(x, 0)}+{max(y, 0)}")


# ====================================================================== dialog proxy
class ProxyImportDialog(tk.Toplevel):
    """Tempel banyak proxy sekaligus lalu simpan ke menu Proxy."""

    def __init__(self, master, app: "App"):
        super().__init__(master)
        self.app = app
        self.result: tuple[list[SavedProxy], int] | None = None
        self.test = False
        self.title("Import proxy")
        self.transient(master)
        self.resizable(False, False)
        self.configure(padx=px(22), pady=px(18), bg=C["surface"])

        dialog_header(self, "Import proxy",
                      "Tempel daftar proxy, satu per baris. Proxy yang sudah tersimpan otomatis dilewati.")
        f = ttk.Frame(self)
        f.pack(fill="both")
        f.columnconfigure(0, weight=1)
        top = ttk.Frame(f)
        top.grid(row=0, column=0, sticky="we", pady=(0, px(6)))
        ttk.Label(top, text="Daftar proxy", style="Field.TLabel").pack(side="left", anchor="s")
        Btn(top, "Tempel dari clipboard", self._paste_clipboard, icon="paste", size="sm").pack(side="right")
        self.text = styled_text(f, height=12, width=72, font=("Consolas", 10), undo=True)
        self.text.grid(row=1, column=0, sticky="we")
        self.text.bind("<<Modified>>", self._modified)
        ttk.Label(f, text=PROXY_FORMAT_HINT, style="Hint.TLabel").grid(row=2, column=0, sticky="w", pady=(px(6), 0))

        opts = ttk.Frame(f)
        opts.grid(row=3, column=0, sticky="we", pady=(px(14), 0))
        self.v_type = tk.StringVar(value="http")
        self.v_prefix = tk.StringVar(value="Proxy")
        self.v_test = tk.BooleanVar(value=True)
        ttk.Label(opts, text="Tipe jika tidak ditulis", style="Field.TLabel").pack(side="left")
        cb = ttk.Combobox(opts, textvariable=self.v_type, values=PROXY_TYPES, state="readonly", width=9)
        cb.pack(side="left", padx=(px(8), px(24)))
        cb.bind("<<ComboboxSelected>>", lambda e: self._update_summary())
        ttk.Label(opts, text="Awalan nama", style="Field.TLabel").pack(side="left")
        ttk.Entry(opts, textvariable=self.v_prefix, width=14).pack(side="left", padx=px(8))
        ttk.Checkbutton(f, text="Tes semua proxy setelah diimport (cek hidup/mati & negara)", variable=self.v_test
                        ).grid(row=4, column=0, sticky="w", pady=(px(10), 0))
        self.lbl_sum = tk.Label(f, text="", font=(FONT_B, 9), bg=C["surface"], fg=C["muted"], anchor="w",
                                justify="left", wraplength=px(560))
        self.lbl_sum.grid(row=5, column=0, sticky="we", pady=(px(10), 0))

        self.btn_ok = None
        dialog_footer(self, [
            self._make_ok,
            lambda bar: Btn(bar, "Batal", self.destroy),
        ])
        self.bind("<Escape>", lambda e: self.destroy())
        self._update_summary()
        self.grab_set()
        self.text.focus_set()
        center_on(self)

    def _make_ok(self, bar):
        self.btn_ok = Btn(bar, "Import proxy", self._ok, icon="check", variant="primary")
        return self.btn_ok

    def _paste_clipboard(self):
        try:
            clip = self.clipboard_get()
        except tk.TclError:
            clip = ""
        if not clip.strip():
            messagebox.showinfo(APP_NAME, "Clipboard kosong. Salin dulu daftar proxy Anda.", parent=self)
            return
        cur = self.text.get("1.0", "end").strip()
        self.text.insert("end", ("\n" if cur else "") + clip.strip() + "\n")
        self.text.see("end")

    def _modified(self, _e=None):
        if self.text.edit_modified():
            self.text.edit_modified(False)
            self.after_idle(self._update_summary)

    def _parse(self):
        return parse_proxy_list(self.text.get("1.0", "end"), self.v_type.get())

    def _update_summary(self):
        ok, bad = self._parse()
        keys, dup = {p.key() for p in self.app.proxies.proxies.values()}, 0
        for cfg in ok:
            k = SavedProxy.from_config(cfg).key()
            dup += k in keys
            keys.add(k)
        new = len(ok) - dup
        if not ok and not bad:
            parts = ["Belum ada proxy ditempel."]
        else:
            parts = [f"✓ {new} proxy baru siap diimport"]
            if dup:
                parts.append(f"{dup} sudah tersimpan / duplikat (dilewati)")
            if bad:
                nums = ", ".join(str(n) for n, _l, _e in bad[:6]) + ("…" if len(bad) > 6 else "")
                parts.append(f"✗ {len(bad)} baris tidak dikenali (baris {nums})")
        self.lbl_sum.configure(text="   •   ".join(parts),
                               fg=C["warn"] if bad else (C["success"] if new else C["muted"]))
        if self.btn_ok:
            self.btn_ok.set_state(new > 0)

    def _ok(self):
        ok, bad = self._parse()
        if bad:
            sample = "\n".join(f"Baris {n}: {ln}" for n, ln, _e in bad[:8]) + ("\n..." if len(bad) > 8 else "")
            if not messagebox.askyesno(APP_NAME, f"{len(bad)} baris tidak dikenali dan akan dilewati:\n\n{sample}\n\n"
                                                  "Lanjutkan import proxy yang valid?", parent=self):
                return
        added, dup = self.app.proxies.import_configs(ok, self.v_prefix.get().strip())
        if not added:
            messagebox.showinfo(APP_NAME, "Tidak ada proxy baru — semuanya sudah tersimpan.", parent=self)
            return
        self.result = (added, dup)
        self.test = self.v_test.get()
        self.destroy()


class ProxyEditDialog(tk.Toplevel):
    """Tambah / ubah satu proxy tersimpan."""

    def __init__(self, master: "App", sp: SavedProxy, title: str):
        super().__init__(master)
        self.app = master
        self.sp = replace(sp)
        self.result: SavedProxy | None = None
        self._tested: tuple | None = None
        self.title(title)
        self.transient(master)
        self.resizable(False, False)
        self.configure(padx=px(22), pady=px(18), bg=C["surface"])

        dialog_header(self, title, "Profil yang memakai proxy ini ikut diperbarui saat disimpan.")
        f = ttk.Frame(self)
        f.pack(fill="both")
        self.v_name = tk.StringVar(value=sp.name)
        self.name_entry = ttk.Entry(f, textvariable=self.v_name, width=52)
        form_row(f, 0, "Nama", self.name_entry, "Opsional, mis. 'US Residential 1'. Kosong = pakai alamat proxy.")
        ttk.Separator(f).grid(row=2, column=0, columnspan=2, sticky="we", pady=px(10))
        self.fields = ProxyFields(f, sp, row0=3, on_filled=lambda: self._info(
            "Terisi. Klik 'Tes proxy' untuk memastikan proxy berfungsi."))
        test = ttk.Frame(f)
        test.grid(row=self.fields.next_row, column=0, columnspan=2, sticky="we", pady=(px(10), 0))
        self.btn_test = Btn(test, "Tes proxy", self._test, icon="globe", size="sm")
        self.btn_test.pack(side="left")
        self.lbl_test = ttk.Label(test, text="", wraplength=px(420))
        self.lbl_test.pack(side="left", padx=px(10))

        dialog_footer(self, [
            lambda bar: Btn(bar, "Simpan proxy", self._save, icon="check", variant="primary"),
            lambda bar: Btn(bar, "Batal", self.destroy),
        ])
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()
        self.name_entry.focus_set()
        center_on(self)

    def _info(self, text, color=C["muted"]):
        self.lbl_test.configure(text=text, foreground=color)

    def _test(self):
        try:
            cfg = self.fields.read(ProxyConfig(enabled=True))
        except ValueError as e:
            messagebox.showwarning(APP_NAME, str(e), parent=self)
            return
        self.btn_test.configure(state="disabled")
        self._info("Mengetes proxy...")

        def done(geo, err):
            if not self.winfo_exists():
                return
            self.btn_test.configure(state="normal")
            self._tested = (cfg.type, cfg.host, cfg.port, cfg.username)
            fill_check(self.sp, geo)
            if err:
                self._info(f"✗ {err}", C["danger"])
            else:
                self._info("✓ " + fmt_geo(geo), C["success"])

        run_bg(self, lambda: proxy_check.check(cfg), done)

    def _save(self):
        old = (self.sp.type, self.sp.host, self.sp.port, self.sp.username)
        try:
            self.fields.read(self.sp)
        except ValueError as e:
            messagebox.showwarning(APP_NAME, str(e), parent=self)
            return
        self.sp.name = self.v_name.get().strip()
        cur = (self.sp.type, self.sp.host, self.sp.port, self.sp.username)
        if cur != old and cur != self._tested:  # alamat berubah tanpa dites ulang -> hasil lama tidak berlaku
            self.sp.last_ok, self.sp.last_ip, self.sp.last_country, self.sp.last_city = None, "", "", ""
        dup = self.app.proxies.find(self.sp.key())
        if dup and dup.id != self.sp.id:
            messagebox.showwarning(APP_NAME, f"Proxy ini sudah tersimpan sebagai '{dup.label()}'.", parent=self)
            return
        self.result = self.sp
        self.destroy()


# ====================================================================== dialog profil
class ProfileDialog(tk.Toplevel):
    def __init__(self, master: "App", profile: Profile, title: str):
        super().__init__(master)
        self.app = master
        self.profile = profile.clone()
        self.result: Profile | None = None
        self.title(title)
        self.transient(master)
        self.resizable(False, False)
        self.configure(padx=px(22), pady=px(18), bg=C["surface"])

        dialog_header(self, title, "Atur identitas browser, proxy & fingerprint untuk profil ini.")
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)
        nb.add(self._tab_general(nb), text="Umum")
        nb.add(self._tab_proxy(nb), text="Proxy")
        nb.add(self._tab_fp(nb), text="Fingerprint (lanjutan)")

        dialog_footer(self, [
            lambda bar: Btn(bar, "Simpan profil", self._save, icon="check", variant="primary"),
            lambda bar: Btn(bar, "Batal", self.destroy),
        ])

        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()
        self.name_entry.focus_set()
        self.name_entry.select_range(0, "end")
        self._center()

    def _center(self):
        self.update_idletasks()
        m = self.master
        x = m.winfo_rootx() + (m.winfo_width() - self.winfo_width()) // 2
        y = m.winfo_rooty() + (m.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    _row = staticmethod(form_row)

    # ------------------------------------------------------------ tab Umum
    def _tab_general(self, nb):
        f = ttk.Frame(nb, padding=(px(4), px(10)))
        f.columnconfigure(1, weight=1)
        p = self.profile
        self.v_name = tk.StringVar(value=p.name)
        self.v_url = tk.StringVar(value=p.start_url)
        self.v_browser = tk.StringVar(value=BROWSER_LABELS.get(p.browser, BROWSER_LABELS["auto"]))

        self.name_entry = ttk.Entry(f, textvariable=self.v_name, width=56)
        self._row(f, 0, "Nama profil", self.name_entry)
        self._row(f, 1, "Halaman awal", ttk.Entry(f, textvariable=self.v_url))
        cb = ttk.Combobox(f, textvariable=self.v_browser, state="readonly",
                          values=[BROWSER_LABELS[b] for b in BROWSERS])
        found = installed_browsers()
        hint = "Terdeteksi: " + (", ".join(BROWSER_LABELS[b] for b in found) if found else "tidak ada")
        self._row(f, 2, "Browser", cb, hint)
        ttk.Label(f, text="Catatan", style="Field.TLabel").grid(row=4, column=0, sticky="nw", pady=px(8))
        self.t_notes = styled_text(f, height=6, width=56, font=(FONT, 10))
        self.t_notes.insert("1.0", p.notes)
        self.t_notes.grid(row=4, column=1, sticky="we", pady=px(8))
        return f

    # ------------------------------------------------------------ tab Proxy
    def _tab_proxy(self, nb):
        f = ttk.Frame(nb, padding=(px(4), px(10)))
        f.columnconfigure(0, weight=1)
        px_ = self.profile.proxy
        linked = self.app.proxies.get(px_.saved_id) if px_.enabled else None
        start = "none" if not (px_.enabled and px_.host) else ("saved" if linked else "manual")
        self.v_px_mode = tk.StringVar(value=start)
        self.v_px_geo = tk.BooleanVar(value=px_.auto_geo)
        self.v_px_save = tk.BooleanVar(value=False)
        self.v_px_saved = tk.StringVar()

        mode = ttk.Frame(f)
        mode.grid(row=0, column=0, sticky="w", pady=(0, px(10)))
        for i, (val, text) in enumerate((("none", "Tanpa proxy"), ("saved", "Pilih proxy tersimpan"),
                                         ("manual", "Atur manual"))):
            ttk.Radiobutton(mode, text=text, value=val, variable=self.v_px_mode, command=self._toggle_proxy
                            ).pack(side="left", padx=(0 if i == 0 else px(20), 0))

        # mode: tanpa proxy
        self.px_none = ttk.Label(f, style="Hint.TLabel", wraplength=px(480), justify="left",
                                 text="Profil ini akan memakai IP asli komputer Anda. Untuk memisahkan akun, "
                                      "pilih proxy tersimpan atau atur proxy secara manual.")

        # mode: proxy tersimpan
        self.px_saved = ttk.Frame(f)
        pick = ttk.Frame(self.px_saved)
        self.cb_saved = ttk.Combobox(pick, textvariable=self.v_px_saved, state="readonly", width=56)
        self.cb_saved.pack(side="left", fill="x", expand=True)
        self.cb_saved.bind("<<ComboboxSelected>>", lambda e: (self._saved_selected(), self.lbl_test.configure(text="")))
        Btn(pick, "Import", self._import_proxies, icon="paste", size="sm").pack(side="left", padx=(px(8), 0))
        form_row(self.px_saved, 0, "Proxy", pick)
        self.lbl_saved = tk.Label(self.px_saved, text="", font=(FONT, 9), bg=C["surface"], fg=C["muted"],
                                  wraplength=px(440), justify="left", anchor="w")
        self.lbl_saved.grid(row=1, column=1, sticky="we")
        self._fill_saved(linked.id if linked else "")

        # mode: manual
        self.px_manual = ttk.Frame(f)
        self.fields = ProxyFields(self.px_manual, px_, on_filled=lambda: self.lbl_test.configure(
            text="Terisi. Klik 'Tes proxy' untuk memastikan proxy berfungsi.", foreground=C["muted"]))
        ttk.Checkbutton(self.px_manual, variable=self.v_px_save,
                        text="Simpan juga ke menu Proxy (bisa dipilih untuk profil lain)"
                        ).grid(row=self.fields.next_row, column=0, columnspan=2, sticky="w", pady=(px(8), 0))

        # bagian bersama (saved & manual)
        self.px_common = ttk.Frame(f)
        ttk.Separator(self.px_common).pack(fill="x", pady=(px(10), px(4)))
        ttk.Checkbutton(self.px_common, variable=self.v_px_geo,
                        text="Samakan zona waktu, bahasa & lokasi dengan negara proxy (disarankan)"
                        ).pack(anchor="w", pady=(px(6), px(4)))
        test = ttk.Frame(self.px_common)
        test.pack(fill="x", pady=(px(6), 0))
        self.btn_test = Btn(test, "Tes proxy", self._test_proxy, icon="globe", size="sm")
        self.btn_test.pack(side="left")
        self.lbl_test = ttk.Label(test, text="", wraplength=px(440))
        self.lbl_test.pack(side="left", padx=px(10))
        self._toggle_proxy()
        return f

    def _toggle_proxy(self):
        m = self.v_px_mode.get()
        for w in (self.px_none, self.px_saved, self.px_manual, self.px_common):
            w.grid_remove()
        {"none": self.px_none, "saved": self.px_saved, "manual": self.px_manual}[m].grid(
            row=1, column=0, sticky="we")
        if m != "none":
            self.px_common.grid(row=2, column=0, sticky="we")
        self.lbl_test.configure(text="")

    def _saved_text(self, sp: SavedProxy, uses: int) -> str:
        addr = f"{sp.type.upper()} {sp.address()}"
        parts = [f"{sp.name}  —  {addr}" if sp.name else addr]
        if sp.last_ok is False:
            parts.append("✗ gagal")
        elif sp.last_country:
            parts.append(sp.last_country)
        if uses:
            parts.append(f"dipakai {uses} profil")
        return "   ·   ".join(parts)

    def _fill_saved(self, select_id: str = ""):
        self._saved_items = self.app.proxies.ordered()
        uses = self.app.proxy_usage(exclude=self.profile.id)
        self.cb_saved.configure(values=[self._saved_text(sp, uses.get(sp.id, 0)) for sp in self._saved_items])
        idx = next((i for i, sp in enumerate(self._saved_items) if sp.id == select_id), -1)
        if idx >= 0:
            self.cb_saved.current(idx)
        else:
            self.v_px_saved.set("")
        self._saved_selected()

    def _selected_saved(self) -> SavedProxy | None:
        i = self.cb_saved.current()
        return self._saved_items[i] if 0 <= i < len(self._saved_items) else None

    def _saved_selected(self):
        sp = self._selected_saved()
        color = C["muted"]
        if not self._saved_items:
            text = "Belum ada proxy tersimpan. Klik 'Import' untuk menempel daftar proxy Anda."
        elif not sp:
            text = f"Pilih salah satu dari {len(self._saved_items)} proxy tersimpan."
        else:
            lines = [f"Login: {sp.username}" if sp.username else "Tanpa login (username/password)",
                     "Tes terakhir: " + saved_status(sp)]
            uses = self.app.proxy_usage(exclude=self.profile.id).get(sp.id, 0)
            if uses:
                lines.append(f"⚠ Sudah dipakai {uses} profil lain — sebaiknya 1 proxy untuk 1 akun.")
                color = C["warn"]
            elif sp.last_ok is False:
                color = C["danger"]
            text = "\n".join(lines)
        self.lbl_saved.configure(text=text, fg=color)

    def _import_proxies(self):
        d = ProxyImportDialog(self, self.app)
        self.wait_window(d)
        if self.winfo_exists():
            self.grab_set()
        if not d.result:
            return
        added, dup = d.result
        self.app.proxy_page.refresh()
        if d.test:
            self.app.proxy_page.check(added, on_each=lambda: self.winfo_exists() and self._refresh_saved())
        self._fill_saved(added[0].id)
        self.v_px_mode.set("saved")
        self._toggle_proxy()
        self.app.set_status(f"{len(added)} proxy diimport" + (f", {dup} duplikat dilewati." if dup else "."))

    def _refresh_saved(self):
        sp = self._selected_saved()
        self._fill_saved(sp.id if sp else "")

    def _proxy_from_form(self):
        px_ = self.profile.proxy
        px_.auto_geo = self.v_px_geo.get()
        m = self.v_px_mode.get()
        if m == "none":
            px_.enabled = False
        elif m == "saved":
            sp = self._selected_saved()
            if not sp:
                raise ValueError("Pilih proxy tersimpan terlebih dahulu, atau ganti ke 'Atur manual'.")
            sp.apply_to(px_)
        else:
            self.fields.read(px_)
            px_.enabled = True
            px_.saved_id = ""
        return px_

    def _test_proxy(self):
        try:
            px_ = self._proxy_from_form()
        except ValueError as e:
            messagebox.showwarning(APP_NAME, str(e), parent=self)
            return
        if not px_.enabled:
            return
        self.btn_test.configure(state="disabled")
        self.lbl_test.configure(text="Mengetes proxy...", foreground=C["muted"])
        sp = self.app.proxies.get(px_.saved_id)

        def done(geo, err):
            if sp:
                self.app.record_check(sp, geo)
            if not self.winfo_exists():
                return
            self.btn_test.configure(state="normal")
            if sp:
                self._refresh_saved()
            if err:
                self.lbl_test.configure(text=f"✗ {err}", foreground=C["danger"])
                return
            self.lbl_test.configure(text="✓ " + fmt_geo(geo), foreground=C["success"])
            px_.last_ip, px_.last_country = geo["ip"], geo.get("country", "")
            if self.v_px_geo.get():
                fp = self._fp_from_form(silent=True)
                fpgen.apply_geo(fp, geo)
                self._load_fp(fp)

        run_bg(self, lambda: proxy_check.check(px_), done)

    # ------------------------------------------------------------ tab Fingerprint
    def _tab_fp(self, nb):
        f = ttk.Frame(nb, padding=(px(4), px(10)))
        f.columnconfigure(1, weight=1)
        f.columnconfigure(3, weight=1)
        self.v = {k: tk.StringVar() for k in (
            "locale", "languages", "timezone", "lat", "lon", "screen", "cores", "memory",
            "gpu", "vendor", "ua", "webrtc")}
        self.b = {k: tk.BooleanVar() for k in ("geo", "canvas", "webgl", "audio", "font", "sw")}
        v, b = self.v, self.b

        ttk.Label(f, text="Setiap profil punya fingerprint unik & tetap. Biasanya tidak perlu diubah.",
                  style="Hint.TLabel").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, px(8)))

        def lab(r, c, text):
            ttk.Label(f, text=text, style="Field.TLabel").grid(
                row=r, column=c, sticky="w", padx=(0 if c == 0 else px(16), px(10)), pady=px(4))

        lab(1, 0, "Bahasa (locale)")
        ttk.Entry(f, textvariable=v["locale"], width=12).grid(row=1, column=1, sticky="we")
        lab(1, 2, "Daftar bahasa")
        ttk.Entry(f, textvariable=v["languages"]).grid(row=1, column=3, sticky="we")

        lab(2, 0, "Zona waktu")
        ttk.Combobox(f, textvariable=v["timezone"], values=fpgen.TIMEZONES).grid(row=2, column=1, sticky="we")
        ttk.Label(f, text="(kosong = ikut komputer)", style="Hint.TLabel").grid(row=2, column=2, columnspan=2,
                                                                              sticky="w", padx=px(16))

        lab(3, 0, "Lokasi GPS")
        geo = ttk.Frame(f)
        geo.grid(row=3, column=1, columnspan=3, sticky="w")
        ttk.Checkbutton(geo, text="Palsukan", variable=self.b["geo"]).pack(side="left", padx=(0, px(14)))
        ttk.Label(geo, text="Lat", style="Field.TLabel").pack(side="left")
        ttk.Entry(geo, textvariable=v["lat"], width=11).pack(side="left", padx=(px(6), px(14)))
        ttk.Label(geo, text="Lon", style="Field.TLabel").pack(side="left")
        ttk.Entry(geo, textvariable=v["lon"], width=11).pack(side="left", padx=px(6))

        ttk.Separator(f).grid(row=4, column=0, columnspan=4, sticky="we", pady=px(10))
        lab(5, 0, "Resolusi layar")
        ttk.Combobox(f, textvariable=v["screen"], width=12,
                     values=[f"{w}x{h}" for w, h, _ in fpgen.SCREENS]).grid(row=5, column=1, sticky="we")
        lab(5, 2, "CPU core")
        ttk.Combobox(f, textvariable=v["cores"], width=6, values=[c for c, _ in fpgen.CORES]).grid(row=5, column=3,
                                                                                                 sticky="w")
        lab(6, 0, "RAM (GB)")
        ttk.Combobox(f, textvariable=v["memory"], width=6, values=[2, 4, 8], state="readonly").grid(row=6, column=1,
                                                                                                  sticky="w")
        lab(6, 2, "WebRTC")
        ttk.Combobox(f, textvariable=v["webrtc"], state="readonly", width=28,
                     values=list(WEBRTC_LABELS.values())).grid(row=6, column=3, sticky="we")
        lab(7, 0, "Kartu grafis")
        gpu = ttk.Combobox(f, textvariable=v["gpu"], values=[r for _, r in fpgen.GPUS])
        gpu.grid(row=7, column=1, columnspan=3, sticky="we")
        gpu.bind("<<ComboboxSelected>>", self._gpu_selected)
        lab(8, 0, "Vendor grafis")
        ttk.Entry(f, textvariable=v["vendor"]).grid(row=8, column=1, columnspan=3, sticky="we")
        lab(9, 0, "User-Agent")
        ttk.Entry(f, textvariable=v["ua"]).grid(row=9, column=1, columnspan=3, sticky="we")
        ttk.Label(f, text="(kosong = asli browser, paling aman)", style="Hint.TLabel").grid(row=10, column=1,
                                                                                          columnspan=3, sticky="w")

        noise = ttk.Frame(f)
        noise.grid(row=11, column=0, columnspan=4, sticky="w", pady=(px(12), 0))
        ttk.Label(noise, text="Lindungi:", style="Field.TLabel").pack(side="left")
        ttk.Checkbutton(noise, text="Canvas", variable=b["canvas"]).pack(side="left", padx=px(8))
        ttk.Checkbutton(noise, text="WebGL", variable=b["webgl"]).pack(side="left", padx=px(8))
        ttk.Checkbutton(noise, text="Audio", variable=b["audio"]).pack(side="left", padx=px(8))
        ttk.Checkbutton(noise, text="Font", variable=b["font"]).pack(side="left", padx=px(8))
        ttk.Checkbutton(noise, text="Blokir Service Worker", variable=b["sw"]).pack(side="left", padx=px(8))

        Btn(f, "Acak fingerprint baru", self._randomize, icon="shuffle", size="sm").grid(
            row=12, column=0, columnspan=4, sticky="w", pady=(px(14), 0))
        self._load_fp(self.profile.fingerprint)
        return f

    def _gpu_selected(self, _e=None):
        for vendor, renderer in fpgen.GPUS:
            if renderer == self.v["gpu"].get():
                self.v["vendor"].set(vendor)

    def _load_fp(self, fp):
        v, b = self.v, self.b
        v["locale"].set(fp.locale)
        v["languages"].set(", ".join(fp.languages))
        v["timezone"].set(fp.timezone)
        v["lat"].set(str(fp.latitude))
        v["lon"].set(str(fp.longitude))
        v["screen"].set(f"{fp.screen_width}x{fp.screen_height}")
        v["cores"].set(str(fp.hardware_concurrency))
        v["memory"].set(str(fp.device_memory))
        v["gpu"].set(fp.webgl_renderer)
        v["vendor"].set(fp.webgl_vendor)
        v["ua"].set(fp.user_agent)
        v["webrtc"].set(WEBRTC_LABELS.get(fp.webrtc, WEBRTC_LABELS["proxy"]))
        b["geo"].set(fp.geo_enabled)
        b["canvas"].set(fp.canvas_noise)
        b["webgl"].set(fp.webgl_noise)
        b["audio"].set(fp.audio_noise)
        b["font"].set(fp.font_noise)
        b["sw"].set(fp.block_service_worker)
        self._seeds = (fp.canvas_seed, fp.webgl_seed, fp.audio_seed, fp.font_seed)

    def _fp_from_form(self, silent=False):
        v, b = self.v, self.b
        fp = self.profile.fingerprint
        try:
            w, h = (int(x) for x in v["screen"].get().lower().split("x"))
            fp.screen_width, fp.screen_height = w, h
            fp.hardware_concurrency = int(v["cores"].get())
            fp.device_memory = int(v["memory"].get())
            fp.latitude = float(v["lat"].get() or 0)
            fp.longitude = float(v["lon"].get() or 0)
        except ValueError:
            if not silent:
                raise ValueError("Isian fingerprint tidak valid (resolusi mis. 1920x1080, angka untuk CPU/RAM/lokasi).")
        fp.locale = v["locale"].get().strip() or "en-US"
        langs = [x.strip() for x in v["languages"].get().split(",") if x.strip()]
        fp.languages = langs or fpgen.languages_for(fp.locale)
        fp.timezone = v["timezone"].get().strip()
        fp.webgl_renderer = v["gpu"].get().strip()
        fp.webgl_vendor = v["vendor"].get().strip()
        fp.user_agent = v["ua"].get().strip()
        fp.webrtc = next((k for k, lbl in WEBRTC_LABELS.items() if lbl == v["webrtc"].get()), "proxy")
        fp.geo_enabled = b["geo"].get()
        fp.canvas_noise, fp.webgl_noise, fp.audio_noise = b["canvas"].get(), b["webgl"].get(), b["audio"].get()
        fp.font_noise = b["font"].get()
        fp.block_service_worker = b["sw"].get()
        fp.canvas_seed, fp.webgl_seed, fp.audio_seed, fp.font_seed = self._seeds
        fp.webgl_params = fpgen.gl_params_for(fp.webgl_vendor, fp.webgl_renderer)
        return fp

    def _randomize(self):
        cur = self._fp_from_form(silent=True)
        new = fpgen.generate(cur.locale, cur.timezone)
        new.geo_enabled, new.latitude, new.longitude = cur.geo_enabled, cur.latitude, cur.longitude
        new.webrtc = cur.webrtc
        new.block_service_worker = cur.block_service_worker
        self._load_fp(new)

    # ------------------------------------------------------------ simpan
    def _save(self):
        p = self.profile
        p.name = self.v_name.get().strip() or "Tanpa nama"
        p.start_url = self.v_url.get().strip()
        p.browser = next((k for k, lbl in BROWSER_LABELS.items() if lbl == self.v_browser.get()), "auto")
        p.notes = self.t_notes.get("1.0", "end").strip()
        try:
            self._proxy_from_form()
            self._fp_from_form()
        except ValueError as e:
            messagebox.showwarning(APP_NAME, str(e), parent=self)
            return
        if self.v_px_mode.get() == "manual" and self.v_px_save.get():
            store = self.app.proxies
            sp = store.find(SavedProxy.from_config(p.proxy).key())
            if not sp:
                sp = SavedProxy.from_config(p.proxy)
                store.put(sp)
            p.proxy.saved_id = sp.id
            self.app.proxy_page.refresh()
        self.result = p
        self.destroy()


# ====================================================================== dialog buat banyak
class BulkDialog(tk.Toplevel):
    def __init__(self, master: "App"):
        super().__init__(master)
        self.app = master
        self.result: list[Profile] | None = None
        self.title("Buat banyak profil sekaligus")
        self.transient(master)
        self.configure(padx=px(22), pady=px(18), bg=C["surface"])
        self.resizable(False, False)

        self.v_prefix = tk.StringVar(value="Akun")
        self.v_count = tk.StringVar(value="5")
        self.v_type = tk.StringVar(value="http")
        self.v_url = tk.StringVar(value="https://browserleaks.com/ip")

        dialog_header(self, "Buat banyak profil", "Setiap profil otomatis mendapat fingerprint unik.")
        f = ttk.Frame(self)
        f.pack(fill="both")
        f.columnconfigure(1, weight=1)
        ttk.Label(f, text="Awalan nama", style="Field.TLabel").grid(row=0, column=0, sticky="w", pady=px(5),
                                                                    padx=(0, px(14)))
        ttk.Entry(f, textvariable=self.v_prefix, width=20).grid(row=0, column=1, sticky="w")
        ttk.Label(f, text="Jumlah profil", style="Field.TLabel").grid(row=1, column=0, sticky="w", pady=px(5))
        ttk.Spinbox(f, from_=1, to=500, textvariable=self.v_count, width=8).grid(row=1, column=1, sticky="w")
        ttk.Label(f, text="Halaman awal", style="Field.TLabel").grid(row=2, column=0, sticky="w", pady=px(5))
        ttk.Entry(f, textvariable=self.v_url, width=50).grid(row=2, column=1, sticky="we")

        ttk.Label(f, text="Daftar proxy (opsional, satu per baris)", style="Field.TLabel"
                  ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(px(14), 0))
        ttk.Label(f, text="Jika diisi, satu profil dibuat untuk tiap proxy dan jumlah di atas diabaikan.",
                  style="Hint.TLabel").grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, px(6)))
        self.t_proxies = styled_text(f, height=10, width=70, font=("Consolas", 10))
        self.t_proxies.grid(row=5, column=0, columnspan=2, sticky="we")
        row = ttk.Frame(f)
        row.grid(row=6, column=0, columnspan=2, sticky="w", pady=(px(8), 0))
        ttk.Label(row, text="Tipe default jika tidak ditulis:", style="Hint.TLabel").pack(side="left")
        ttk.Combobox(row, textvariable=self.v_type, values=PROXY_TYPES, state="readonly", width=10
                     ).pack(side="left", padx=px(8))
        self.v_save = tk.BooleanVar(value=True)
        ttk.Checkbutton(row, text="Simpan juga ke menu Proxy", variable=self.v_save).pack(side="left", padx=px(16))

        dialog_footer(self, [
            lambda bar: Btn(bar, "Buat profil", self._ok, icon="add", variant="primary"),
            lambda bar: Btn(bar, "Batal", self.destroy),
        ])
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()

    def _ok(self):
        lines = [ln.strip() for ln in self.t_proxies.get("1.0", "end").splitlines() if ln.strip()]
        proxies = []
        for i, ln in enumerate(lines, 1):
            try:
                proxies.append(parse_proxy(ln, self.v_type.get()))
            except Exception as e:
                messagebox.showerror(APP_NAME, f"Baris {i} tidak valid:\n{ln}\n\n{e}", parent=self)
                return
        try:
            count = len(proxies) if proxies else int(self.v_count.get())
        except ValueError:
            messagebox.showwarning(APP_NAME, "Jumlah harus angka.", parent=self)
            return
        prefix = self.v_prefix.get().strip() or "Profil"
        out = []
        for i in range(count):
            p = Profile(name=f"{prefix} {i + 1}", start_url=self.v_url.get().strip(),
                        fingerprint=fpgen.generate())
            if proxies:
                p.proxy = proxies[i]
                if self.v_save.get():
                    store = self.app.proxies
                    sp = store.find(SavedProxy.from_config(p.proxy).key())
                    if not sp:
                        sp = SavedProxy.from_config(p.proxy)
                        store.proxies[sp.id] = sp
                    p.proxy.saved_id = sp.id
            out.append(p)
        if proxies and self.v_save.get():
            self.app.proxies.save()
        self.result = out
        self.destroy()


# ====================================================================== halaman proxy
class ProxyPage(tk.Frame):
    """Menu Proxy: daftar proxy tersimpan, import lewat tempel teks, tes & kelola."""
    COLS = ("type", "addr", "auth", "status", "used")

    def __init__(self, master, app: "App"):
        super().__init__(master, bg=C["bg"])
        self.app = app
        self.checking: set[str] = set()

        head = tk.Frame(self, bg=C["bg"])
        head.pack(fill="x", padx=px(28), pady=(px(24), px(18)))
        Btn(head, "Import proxy", self.import_dialog, icon="paste", variant="primary", size="lg").pack(side="right")
        Btn(head, "Tambah manual", self.add_manual, icon="add", size="lg").pack(side="right", padx=px(10))
        titles = tk.Frame(head, bg=C["bg"])
        titles.pack(side="left", fill="x", expand=True)
        tk.Label(titles, text="Proxy Tersimpan", font=(FONT_B, 18), bg=C["bg"], fg=C["text"]).pack(anchor="w")
        tk.Label(titles, text="Simpan proxy sekali, lalu tinggal pilih saat membuat atau mengedit profil.",
                 font=(FONT, 10), bg=C["bg"], fg=C["muted"]).pack(anchor="w")

        stats = tk.Frame(self, bg=C["bg"])
        stats.pack(fill="x", padx=px(28), pady=(0, px(18)))
        self.stat = {}
        for i, (key, label, color, icon) in enumerate((
                ("total", "Total proxy", C["primary"], "network"),
                ("ok", "Hidup", C["success"], "check"),
                ("bad", "Gagal / mati", C["danger"], "close"),
                ("free", "Belum dipakai profil", "#0EA5E9", "info"))):
            stats.columnconfigure(i, weight=1, uniform="stat")
            self.stat[key] = app._stat_card(stats, label, color, icon)
            self.stat[key][0].grid(row=0, column=i, sticky="we", padx=(0 if i == 0 else px(14), 0))

        self.statusbar = tk.Label(self, text="Siap.", font=(FONT, 9), bg=C["bg"], fg=C["muted"], anchor="w")
        self.statusbar.pack(side="bottom", fill="x", padx=px(30), pady=(px(8), px(10)))

        card = tk.Frame(self, bg=C["surface"], highlightthickness=1, highlightbackground=C["border"])
        card.pack(fill="both", expand=True, padx=px(28))
        bar = tk.Frame(card, bg=C["surface"])
        bar.pack(fill="x", padx=px(16), pady=px(14))
        self.v_search = tk.StringVar()
        self.v_search.trace_add("write", lambda *_: self.refresh())
        SearchBox(bar, self.v_search, "Cari nama, IP, negara…", width=26).pack(side="left")
        self.lbl_count = tk.Label(bar, text="", font=(FONT, 9), bg=C["surface"], fg=C["muted"])
        self.lbl_count.pack(side="left", padx=px(14))

        self.btn_del = Btn(bar, "", self.delete_selected, icon="delete", variant="danger", size="sm")
        self.btn_del.pack(side="right")
        self.btn_edit = Btn(bar, "Edit", self.edit_selected, icon="edit", size="sm")
        self.btn_edit.pack(side="right", padx=px(6))
        tk.Frame(bar, bg=C["border"], width=1).pack(side="right", fill="y", padx=px(6), pady=px(2))
        self.btn_check_all = Btn(bar, "Tes semua", self.check_all, icon="refresh", size="sm")
        self.btn_check_all.pack(side="right", padx=(px(6), 0))
        self.btn_check = Btn(bar, "Tes proxy", self.check_selected, icon="globe", variant="primary", size="sm")
        self.btn_check.pack(side="right")

        tk.Frame(card, bg=C["border"], height=1).pack(fill="x")
        mid = tk.Frame(card, bg=C["surface"])
        mid.pack(fill="both", expand=True, padx=(px(4), 0), pady=(0, px(4)))
        self.tree = ttk.Treeview(mid, columns=self.COLS, show="tree headings", selectmode="extended")
        self.tree.heading("#0", text="       NAMA", anchor="w")
        self.tree.column("#0", width=px(200), minwidth=px(130), anchor="w")
        heads = {"type": ("TIPE", 80), "addr": ("ALAMAT", 200), "auth": ("LOGIN", 120),
                 "status": ("STATUS / LOKASI", 230), "used": ("DIPAKAI", 90)}
        for c, (t, w) in heads.items():
            self.tree.heading(c, text=t, anchor="w")
            self.tree.column(c, width=px(w), minwidth=px(60), anchor="w")
        sb = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview, style="Slim.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y", padx=(px(2), px(4)))
        self.tree.bind("<Double-1>", lambda e: self.edit_selected())
        self.tree.bind("<Return>", lambda e: self.edit_selected())
        self.tree.bind("<Delete>", lambda e: self.delete_selected())
        self.tree.bind("<Control-a>", lambda e: self.tree.selection_set(self.tree.get_children()))
        self.tree.bind("<Button-3>", self._context_menu)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._update_buttons())

        self.empty = self._empty_state(mid)

        self.menu = tk.Menu(self, tearoff=False, bg=C["surface"], fg=C["text"], activebackground=C["select"],
                            activeforeground=C["text"], bd=0, font=(FONT, 10))
        self.menu.add_command(label="Tes proxy", command=self.check_selected)
        self.menu.add_command(label="Edit", command=self.edit_selected)
        self.menu.add_command(label="Salin ke clipboard", command=self.copy_selected)
        self.menu.add_separator()
        self.menu.add_command(label="Pilih semua yang gagal", command=self.select_failed)
        self.menu.add_separator()
        self.menu.add_command(label="Hapus", command=self.delete_selected)
        self.refresh()

    def _empty_state(self, parent):
        box = tk.Frame(parent, bg=C["surface"])
        if _ICON_FONT:
            tk.Label(box, text=ico("network"), font=(_ICON_FONT, 30), bg=C["primary_soft"], fg=C["primary"],
                     padx=px(18), pady=px(14)).pack()
        tk.Label(box, text="Belum ada proxy tersimpan", font=(FONT_B, 13), bg=C["surface"], fg=C["text"]
                 ).pack(pady=(px(14), px(2)))
        tk.Label(box, text="Tempel daftar proxy Anda sekaligus — satu proxy per baris.",
                 font=(FONT, 10), bg=C["surface"], fg=C["muted"]).pack()
        Btn(box, "Import proxy", self.import_dialog, icon="paste", variant="primary").pack(pady=(px(16), 0))
        return box

    def _context_menu(self, e):
        row = self.tree.identify_row(e.y)
        if row:
            if row not in self.tree.selection():
                self.tree.selection_set(row)
            self.menu.tk_popup(e.x_root, e.y_root)

    # ------------------------------------------------------------ daftar
    def _state(self, sp: SavedProxy) -> str:
        if sp.id in self.checking:
            return "starting"
        return {True: "running", False: "error"}.get(sp.last_ok, "stopped")

    def _row_values(self, sp: SavedProxy, uses: dict):
        n = uses.get(sp.id, 0)
        status = "Mengecek..." if sp.id in self.checking else saved_status(sp)
        return (sp.type.upper(), sp.address(), sp.username or "—", status, f"{n} profil" if n else "—")

    def refresh(self):
        q = self.v_search.get().strip().lower()
        sel = set(self.tree.selection())
        self.tree.delete(*self.tree.get_children())
        uses = self.app.proxy_usage()
        for sp in self.app.proxies.ordered():
            hay = " ".join((sp.name, sp.host, sp.username, sp.last_ip, sp.last_country, sp.last_city)).lower()
            if q and q not in hay:
                continue
            self.tree.insert("", "end", iid=sp.id, text=sp.label(), image=self.app._dots[self._state(sp)],
                             values=self._row_values(sp, uses))
        keep = [i for i in sel if self.tree.exists(i)]
        if keep:
            self.tree.selection_set(keep)
        if not self.app.proxies.proxies:
            self.empty.place(relx=0.5, rely=0.45, anchor="center")
        else:
            self.empty.place_forget()
        self._update_stats(uses)
        self._update_buttons()

    def refresh_row(self, pid: str):
        sp = self.app.proxies.get(pid)
        if sp and self.tree.exists(pid):
            self.tree.item(pid, text=sp.label(), values=self._row_values(sp, self.app.proxy_usage()))
        self._update_stats()
        self._update_buttons()

    def _update_stats(self, uses: dict | None = None):
        uses = self.app.proxy_usage() if uses is None else uses
        items = list(self.app.proxies.proxies.values())
        for key, n in (("total", len(items)), ("ok", sum(1 for p in items if p.last_ok is True)),
                       ("bad", sum(1 for p in items if p.last_ok is False)),
                       ("free", sum(1 for p in items if not uses.get(p.id)))):
            self.stat[key][1].configure(text=str(n))
        shown = len(self.tree.get_children())
        self.lbl_count.configure(text=f"{shown} dari {len(items)} proxy" if shown != len(items)
                                 else f"{len(items)} proxy")

    def selected(self) -> list[SavedProxy]:
        return [self.app.proxies.proxies[i] for i in self.tree.selection() if i in self.app.proxies.proxies]

    def _update_buttons(self):
        sel = self.selected()
        for b in (self.btn_check, self.btn_del):
            b.set_state(bool(sel))
        self.btn_edit.set_state(len(sel) == 1)
        self.btn_check_all.set_state(bool(self.app.proxies.proxies) and not self.checking)
        selset = set(self.tree.selection())
        for iid in self.tree.get_children():
            sp = self.app.proxies.get(iid)
            if sp:
                self.tree.item(iid, image=(self.app._dots_sel if iid in selset else self.app._dots)[self._state(sp)])

    # ------------------------------------------------------------ aksi
    def import_dialog(self):
        d = ProxyImportDialog(self.app, self.app)
        self.app.wait_window(d)
        if not d.result:
            return
        added, dup = d.result
        self.v_search.set("")
        self.refresh()
        self.tree.selection_set([sp.id for sp in added])
        self.tree.see(added[0].id)
        self.app.set_status(f"{len(added)} proxy diimport" + (f", {dup} duplikat dilewati." if dup else "."))
        if d.test:
            self.check(added)

    def add_manual(self):
        d = ProxyEditDialog(self.app, SavedProxy(), "Tambah proxy")
        self.app.wait_window(d)
        if d.result:
            self.app.proxies.put(d.result)
            self.refresh()
            self.tree.selection_set(d.result.id)
            self.tree.see(d.result.id)
            self.app.set_status(f"Proxy '{d.result.label()}' disimpan.")

    def edit_selected(self):
        sel = self.selected()
        if len(sel) != 1:
            return
        d = ProxyEditDialog(self.app, sel[0], f"Edit proxy — {sel[0].label()}")
        self.app.wait_window(d)
        if d.result:
            self.app.proxies.put(d.result)
            n = self.app.sync_profiles(d.result)
            self.refresh()
            self.app.refresh()
            self.app.set_status(f"Proxy '{d.result.label()}' disimpan." +
                                (f" {n} profil yang memakainya ikut diperbarui." if n else ""))

    def delete_selected(self):
        sel = self.selected()
        if not sel:
            return
        uses = self.app.proxy_usage()
        used = sum(uses.get(sp.id, 0) for sp in sel)
        names = "\n".join(f"• {sp.label()}" for sp in sel[:10]) + ("\n..." if len(sel) > 10 else "")
        extra = (f"\n\n{used} profil memakai proxy ini. Profil tersebut tetap memakai salinan proxy-nya "
                 "(tidak ikut terhapus).") if used else ""
        if not messagebox.askyesno(APP_NAME, f"Hapus {len(sel)} proxy dari daftar?\n\n{names}{extra}",
                                   icon="warning", parent=self.app):
            return
        for sp in sel:
            self.app.proxies.proxies.pop(sp.id, None)
            self.checking.discard(sp.id)
        self.app.proxies.save()
        self.app.unlink_profiles({sp.id for sp in sel})
        self.refresh()
        self.app.refresh()
        self.app.set_status(f"{len(sel)} proxy dihapus.")

    def copy_selected(self):
        sel = self.selected()
        if sel:
            self.clipboard_clear()
            self.clipboard_append("\n".join(proxy_line(sp) for sp in sel))
            self.app.set_status(f"{len(sel)} proxy disalin ke clipboard.")

    def select_failed(self):
        bad = [sp.id for sp in self.app.proxies.proxies.values() if sp.last_ok is False and self.tree.exists(sp.id)]
        self.tree.selection_set(bad)
        if not bad:
            self.app.set_status("Tidak ada proxy yang gagal.")

    def check_selected(self):
        self.check(self.selected())

    def check_all(self):
        self.check(self.app.proxies.ordered())

    def check(self, items: list[SavedProxy], on_each=None):
        items = [sp for sp in items if sp.id not in self.checking]
        if not items:
            return
        for sp in items:
            self.checking.add(sp.id)
        self.refresh()
        total, counts = len(items), {"ok": 0, "bad": 0}

        def one(sp, geo, err):
            self.checking.discard(sp.id)
            counts["ok" if geo else "bad"] += 1
            if sp.id in self.app.proxies.proxies:
                self.app.record_check(sp, geo)
                self.refresh_row(sp.id)
            if on_each:
                on_each()
            done = counts["ok"] + counts["bad"]
            if done < total:
                self.app.set_status(f"Mengetes proxy {done}/{total}...  ✓ {counts['ok']} hidup  ✗ {counts['bad']} gagal")

        def all_done():
            self._update_buttons()
            self.app.set_status(f"Tes proxy selesai: ✓ {counts['ok']} hidup, ✗ {counts['bad']} gagal.")

        self.app.set_status(f"Mengetes {total} proxy...")
        run_many(self, items, lambda sp: proxy_check.check(sp.to_config()), one, all_done)


# ====================================================================== jendela utama
class App(tk.Tk):
    COLS = ("status", "proxy", "loc", "used")

    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} {__version__}")
        init_theme(self)
        w = min(px(1440), self.winfo_screenwidth() - px(60))
        h = min(px(860), self.winfo_screenheight() - px(100))
        self.geometry(f"{w}x{h}+{(self.winfo_screenwidth() - w) // 2}+{max((self.winfo_screenheight() - h) // 3, 0)}")
        self.minsize(px(1100), px(600))
        self.configure(bg=C["bg"])
        icon = paths.resource("icon.ico")
        if icon.exists():
            try:
                self.iconbitmap(str(icon))
            except tk.TclError:
                pass

        self.store = ProfileStore()
        self.proxies = ProxyStore()
        self.events: queue.Queue = queue.Queue()
        self.engine = Engine(self.events.put)
        self.state: dict[str, tuple[str, str]] = {}
        self._dots = {st: make_dot(self, STATUS_COLORS[st][0] if st != "stopped" else C["idle"])
                      for st in STATUS_COLORS}
        self._dots_sel = {st: make_dot(self, STATUS_COLORS[st][0] if st != "stopped" else C["idle"], C["select"])
                          for st in STATUS_COLORS}

        self._build()
        self.refresh()
        self.after(150, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------ tampilan
    def _build(self):
        self._build_sidebar()
        self.page_profiles = tk.Frame(self, bg=C["bg"])
        self.page_profiles.pack(side="left", fill="both", expand=True)
        page = self.page_profiles

        # panel detail di kanan
        tk.Frame(page, bg=C["border"], width=1).pack(side="right", fill="y")
        self.detail = tk.Frame(page, bg=C["surface"], width=px(320))
        self.detail.pack(side="right", fill="y")
        self.detail.pack_propagate(False)
        self.detail_body = tk.Frame(self.detail, bg=C["surface"])
        self.detail_body.pack(fill="both", expand=True, padx=px(22), pady=px(22))

        main = tk.Frame(page, bg=C["bg"])
        main.pack(side="left", fill="both", expand=True)

        # judul + tombol utama
        head = tk.Frame(main, bg=C["bg"])
        head.pack(fill="x", padx=px(28), pady=(px(24), px(18)))
        Btn(head, "Profil baru", self.new_profile, icon="add", variant="primary", size="lg").pack(side="right")
        Btn(head, "Buat banyak", self.bulk_create, icon="group", size="lg").pack(side="right", padx=px(10))
        titles = tk.Frame(head, bg=C["bg"])
        titles.pack(side="left", fill="x", expand=True)
        tk.Label(titles, text="Profil Browser", font=(FONT_B, 18), bg=C["bg"], fg=C["text"]).pack(anchor="w")
        tk.Label(titles, text="Fingerprint, cookie & proxy terpisah untuk setiap profil.",
                 font=(FONT, 10), bg=C["bg"], fg=C["muted"]).pack(anchor="w")

        # kartu statistik
        stats = tk.Frame(main, bg=C["bg"])
        stats.pack(fill="x", padx=px(28), pady=(0, px(18)))
        self.stat = {}
        for i, (key, label, color, icon) in enumerate((
                ("total", "Total profil", C["primary"], "people"),
                ("running", "Sedang berjalan", C["success"], "play"),
                ("proxy", "Pakai proxy", "#0EA5E9", "globe"),
                ("direct", "Tanpa proxy", C["warn"], "info"))):
            stats.columnconfigure(i, weight=1, uniform="stat")
            self.stat[key] = self._stat_card(stats, label, color, icon)
            self.stat[key][0].grid(row=0, column=i, sticky="we", padx=(0 if i == 0 else px(14), 0))

        self.statusbar = tk.Label(main, text="Siap.", font=(FONT, 9), bg=C["bg"], fg=C["muted"], anchor="w")
        self.statusbar.pack(side="bottom", fill="x", padx=px(30), pady=(px(8), px(10)))

        # kartu daftar profil
        card = tk.Frame(main, bg=C["surface"], highlightthickness=1, highlightbackground=C["border"])
        card.pack(fill="both", expand=True, padx=px(28))
        bar = tk.Frame(card, bg=C["surface"])
        bar.pack(fill="x", padx=px(16), pady=px(14))
        self.v_search = tk.StringVar()
        self.v_search.trace_add("write", lambda *_: self.refresh())
        SearchBox(bar, self.v_search, "Cari profil atau proxy…", width=26).pack(side="left")
        self.lbl_count = tk.Label(bar, text="", font=(FONT, 9), bg=C["surface"], fg=C["muted"])
        self.lbl_count.pack(side="left", padx=px(14))

        self.btn_del = Btn(bar, "", self.delete_selected, icon="delete", variant="danger", size="sm")
        self.btn_del.pack(side="right")
        self.btn_check = Btn(bar, "Cek proxy", self.check_selected, icon="globe", size="sm")
        self.btn_check.pack(side="right", padx=px(6))
        tk.Frame(bar, bg=C["border"], width=1).pack(side="right", fill="y", padx=px(6), pady=px(2))
        self.btn_stop = Btn(bar, "Tutup", self.stop_selected, icon="stop", size="sm")
        self.btn_stop.pack(side="right", padx=px(6))
        self.btn_open = Btn(bar, "Buka", self.launch_selected, icon="play", variant="primary", size="sm")
        self.btn_open.pack(side="right")

        tk.Frame(card, bg=C["border"], height=1).pack(fill="x")
        mid = tk.Frame(card, bg=C["surface"])
        mid.pack(fill="both", expand=True, padx=(px(4), 0), pady=(0, px(4)))
        self.tree = ttk.Treeview(mid, columns=self.COLS, show="tree headings", selectmode="extended")
        self.tree.heading("#0", text="       NAMA PROFIL", anchor="w")
        self.tree.column("#0", width=px(210), minwidth=px(140), anchor="w")
        heads = {"status": ("STATUS", 90), "proxy": ("PROXY", 210), "loc": ("LOKASI IP", 150),
                 "used": ("TERAKHIR DIPAKAI", 140)}
        for c, (t, w) in heads.items():
            self.tree.heading(c, text=t, anchor="w")
            self.tree.column(c, width=px(w), minwidth=px(70), anchor="w")
        sb = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview, style="Slim.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y", padx=(px(2), px(4)))
        self.tree.bind("<Double-1>", lambda e: self.launch_selected())
        self.tree.bind("<Return>", lambda e: self.launch_selected())
        self.tree.bind("<Delete>", lambda e: self.delete_selected())
        self.tree.bind("<Button-3>", self._context_menu)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._update_buttons())

        self.empty = self._empty_state(mid)

        self.menu = tk.Menu(self, tearoff=False, bg=C["surface"], fg=C["text"], activebackground=C["select"],
                            activeforeground=C["text"], bd=0, font=(FONT, 10))
        self.menu.add_command(label="Buka browser", command=self.launch_selected)
        self.menu.add_command(label="Tutup browser", command=self.stop_selected)
        self.menu.add_separator()
        self.menu.add_command(label="Edit", command=self.edit_selected)
        self.menu.add_command(label="Duplikat", command=self.duplicate_selected)
        self.menu.add_command(label="Cek proxy", command=self.check_selected)
        self.menu.add_command(label="Buka folder data", command=self.open_folder)
        self.menu.add_separator()
        self.menu.add_command(label="Hapus", command=self.delete_selected)

        self.proxy_page = ProxyPage(self, self)

    def _build_sidebar(self):
        side = tk.Frame(self, bg=C["sidebar"], width=px(232))
        side.pack(side="left", fill="y")
        side.pack_propagate(False)

        brand = tk.Frame(side, bg=C["sidebar"])
        brand.pack(fill="x", padx=px(20), pady=(px(24), px(28)))
        logo = self._logo_image(px(36))
        if logo:
            tk.Label(brand, image=logo, bg=C["sidebar"], bd=0).pack(side="left")
        else:
            tk.Label(brand, text=ico("shield") or "PB", font=(_ICON_FONT or FONT_B, 15), bg=C["primary"],
                     fg="#FFFFFF", padx=px(8), pady=px(6)).pack(side="left")
        names = tk.Frame(brand, bg=C["sidebar"])
        names.pack(side="left", padx=px(12))
        tk.Label(names, text=APP_NAME, font=(FONT_B, 12), bg=C["sidebar"], fg="#FFFFFF").pack(anchor="w")
        tk.Label(names, text=f"Anti-detect  •  v{__version__}", font=(FONT, 8), bg=C["sidebar"],
                 fg=C["sidebar_muted"]).pack(anchor="w")

        tk.Label(side, text="MENU", font=(FONT_B, 8), bg=C["sidebar"], fg=C["sidebar_muted"]
                 ).pack(anchor="w", padx=px(24), pady=(0, px(6)))
        self.nav = {
            "profiles": NavItem(side, "Profil", "people", lambda: self.show_page("profiles"), active=True),
            "proxies": NavItem(side, "Proxy", "network", lambda: self.show_page("proxies")),
        }
        for item in self.nav.values():
            item.pack(fill="x")
        NavItem(side, "Buat banyak", "group", self.bulk_create).pack(fill="x")
        NavItem(side, "Folder data", "folder", lambda: os.startfile(paths.data_dir())).pack(fill="x")
        NavItem(side, "Bantuan", "help", self.show_help).pack(fill="x")

        tip = tk.Frame(side, bg=C["sidebar_hover"])
        tip.pack(side="bottom", fill="x", padx=px(16), pady=px(18))
        tk.Label(tip, text="Tips", font=(FONT_B, 9), bg=C["sidebar_hover"], fg="#FFFFFF"
                 ).pack(anchor="w", padx=px(14), pady=(px(12), px(2)))
        tk.Label(tip, text="Pakai proxy berbeda di tiap profil supaya akun tidak saling terhubung.",
                 font=(FONT, 9), bg=C["sidebar_hover"], fg=C["sidebar_text"], justify="left",
                 wraplength=px(170)).pack(anchor="w", padx=px(14), pady=(0, px(12)))

    def _logo_image(self, size: int):
        """Logo PNG terdekat (>= size) dari aset bawaan; None jika tidak ada."""
        for s in (36, 45, 54, 63, 72):
            if s >= size or s == 72:
                path = paths.resource(f"logo_{s}.png")
                if path.exists():
                    try:
                        img = tk.PhotoImage(master=self, file=str(path))
                    except tk.TclError:
                        return None
                    _IMAGES.append(img)
                    return img
                return None

    def _stat_card(self, parent, label, color, icon):
        f = tk.Frame(parent, bg=C["surface"], highlightthickness=1, highlightbackground=C["border"])
        inner = tk.Frame(f, bg=C["surface"])
        inner.pack(fill="x", padx=px(18), pady=px(14))
        txt = tk.Frame(inner, bg=C["surface"])
        txt.pack(side="left")
        tk.Label(txt, text=label, font=(FONT, 9), bg=C["surface"], fg=C["muted"]).pack(anchor="w")
        val = tk.Label(txt, text="0", font=(FONT_B, 20), bg=C["surface"], fg=C["text"])
        val.pack(anchor="w")
        if _ICON_FONT:
            tk.Label(inner, text=ico(icon), font=(_ICON_FONT, 14), bg=C["bg"], fg=color, padx=px(10), pady=px(8)
                     ).pack(side="right")
        return f, val

    def _empty_state(self, parent):
        box = tk.Frame(parent, bg=C["surface"])
        if _ICON_FONT:
            tk.Label(box, text=ico("people"), font=(_ICON_FONT, 30), bg=C["primary_soft"], fg=C["primary"],
                     padx=px(18), pady=px(14)).pack()
        tk.Label(box, text="Belum ada profil", font=(FONT_B, 13), bg=C["surface"], fg=C["text"]
                 ).pack(pady=(px(14), px(2)))
        tk.Label(box, text="Buat profil pertama Anda — fingerprint unik dibuat otomatis.",
                 font=(FONT, 10), bg=C["surface"], fg=C["muted"]).pack()
        Btn(box, "Profil baru", self.new_profile, icon="add", variant="primary").pack(pady=(px(16), 0))
        return box

    def _context_menu(self, e):
        row = self.tree.identify_row(e.y)
        if row:
            if row not in self.tree.selection():
                self.tree.selection_set(row)
            self.menu.tk_popup(e.x_root, e.y_root)

    def set_status(self, text: str):
        self.statusbar.configure(text=text)
        if hasattr(self, "proxy_page"):
            self.proxy_page.statusbar.configure(text=text)

    def show_page(self, name: str):
        pages = {"profiles": self.page_profiles, "proxies": self.proxy_page}
        for key, frame in pages.items():
            if key != name:
                frame.pack_forget()
            self.nav[key].set_active(key == name)
        pages[name].pack(side="left", fill="both", expand=True)
        if name == "proxies":
            self.proxy_page.refresh()
            self.proxy_page.tree.focus_set()
        else:
            self.refresh()
            self.tree.focus_set()

    # ------------------------------------------------------------ proxy tersimpan
    def proxy_usage(self, exclude: str | None = None) -> dict[str, int]:
        """Jumlah profil yang memakai tiap proxy tersimpan."""
        out: dict[str, int] = {}
        for p in self.store.profiles.values():
            if p.id != exclude and p.proxy.enabled and p.proxy.saved_id:
                out[p.proxy.saved_id] = out.get(p.proxy.saved_id, 0) + 1
        return out

    def record_check(self, sp: SavedProxy, geo: dict | None):
        """Simpan hasil tes proxy tersimpan & salin IP/negara ke profil yang memakainya."""
        fill_check(sp, geo)
        self.proxies.save()
        if geo:
            changed = False
            for p in self.store.profiles.values():
                if p.proxy.saved_id == sp.id and p.proxy.host == sp.host and p.proxy.port == sp.port:
                    p.proxy.last_ip, p.proxy.last_country = sp.last_ip, sp.last_country
                    changed = True
                    self._refresh_row(p.id)
            if changed:
                self.store.save()

    def sync_profiles(self, sp: SavedProxy) -> int:
        """Perbarui profil yang memakai proxy tersimpan ini. Kembalikan jumlah profil."""
        linked = [p for p in self.store.profiles.values() if p.proxy.enabled and p.proxy.saved_id == sp.id]
        for p in linked:
            sp.apply_to(p.proxy)
        if linked:
            self.store.save()
        return len(linked)

    def unlink_profiles(self, ids: set[str]):
        """Proxy tersimpan dihapus: profil tetap memakai salinannya, tautannya dilepas."""
        changed = False
        for p in self.store.profiles.values():
            if p.proxy.saved_id in ids:
                p.proxy.saved_id = ""
                changed = True
        if changed:
            self.store.save()

    def show_help(self):
        messagebox.showinfo(
            f"Bantuan — {APP_NAME}",
            "Cara pakai singkat:\n\n"
            "1. Buka menu 'Proxy' lalu klik 'Import proxy' untuk menempel daftar proxy Anda (satu per baris).\n"
            "2. Klik 'Profil baru', beri nama, lalu di tab Proxy pilih proxy tersimpan — atau atur manual.\n"
            "3. Pilih profil di daftar lalu klik 'Buka' — atau klik dua kali.\n"
            "4. Login ke akun Anda di jendela browser yang terbuka. Cookie & login tersimpan per profil.\n\n"
            "Tips:\n"
            "• Satu akun = satu profil = satu proxy.\n"
            "• Gunakan 'Cek proxy' untuk memastikan IP dan negara proxy sudah benar.\n"
            "• 'Duplikat' membuat profil baru dengan fingerprint baru (login tidak ikut).",
            parent=self)

    # ------------------------------------------------------------ daftar
    def _row_values(self, p: Profile):
        st, _msg = self.state.get(p.id, ("stopped", ""))
        used = time.strftime("%d %b %Y, %H:%M", time.localtime(p.last_used)) if p.last_used else "Belum pernah"
        return (STATUS_LABELS.get(st, st), fmt_proxy(p), fmt_loc(p), used), st

    def _dot(self, pid: str, st: str):
        return (self._dots_sel if pid in self.tree.selection() else self._dots).get(st, self._dots["stopped"])

    def refresh(self):
        q = self.v_search.get().strip().lower() if hasattr(self, "v_search") else ""
        sel = set(self.tree.selection())
        self.tree.delete(*self.tree.get_children())
        items = sorted(self.store.profiles.values(), key=lambda p: p.name.lower())
        for p in items:
            if q and q not in p.name.lower() and q not in p.notes.lower() and q not in p.proxy.host.lower():
                continue
            vals, st = self._row_values(p)
            self.tree.insert("", "end", iid=p.id, text=p.name, image=self._dots[st], values=vals)
        keep = [i for i in sel if self.tree.exists(i)]
        if keep:
            self.tree.selection_set(keep)
        if not self.store.profiles:
            self.empty.place(relx=0.5, rely=0.45, anchor="center")
        else:
            self.empty.place_forget()
        self._update_stats()
        self._update_buttons()

    def _refresh_row(self, pid: str):
        p = self.store.profiles.get(pid)
        if p and self.tree.exists(pid):
            vals, st = self._row_values(p)
            self.tree.item(pid, text=p.name, image=self._dot(pid, st), values=vals)
        self._update_stats()
        self._update_buttons()

    def _update_stats(self):
        profiles = list(self.store.profiles.values())
        running = sum(1 for s, _ in self.state.values() if s == "running")
        with_proxy = sum(1 for p in profiles if p.proxy.enabled and p.proxy.host)
        for key, n in (("total", len(profiles)), ("running", running),
                       ("proxy", with_proxy), ("direct", len(profiles) - with_proxy)):
            self.stat[key][1].configure(text=str(n))
        shown = len(self.tree.get_children())
        self.lbl_count.configure(text=f"{shown} dari {len(profiles)} profil" if shown != len(profiles)
                                 else f"{len(profiles)} profil")

    def selected(self) -> list[Profile]:
        return [self.store.profiles[i] for i in self.tree.selection() if i in self.store.profiles]

    def _update_buttons(self):
        sel = self.selected()
        for b in (self.btn_open, self.btn_stop, self.btn_check, self.btn_del):
            b.set_state(bool(sel))
        # titik status ikut warna latar baris terpilih
        selset = set(self.tree.selection())
        for iid in self.tree.get_children():
            st = self.state.get(iid, ("stopped", ""))[0]
            self.tree.item(iid, image=(self._dots_sel if iid in selset else self._dots).get(st, self._dots["stopped"]))
        self._render_detail(sel)

    # ------------------------------------------------------------ panel detail
    def _render_detail(self, sel: list[Profile]):
        body = self.detail_body
        for w in body.winfo_children():
            w.destroy()
        bg = C["surface"]

        if not sel:
            box = tk.Frame(body, bg=bg)
            box.place(relx=0.5, rely=0.4, anchor="center")
            if _ICON_FONT:
                tk.Label(box, text=ico("info"), font=(_ICON_FONT, 22), bg=C["bg"], fg=C["subtle"],
                         padx=px(14), pady=px(10)).pack()
            tk.Label(box, text="Belum ada profil dipilih", font=(FONT_B, 11), bg=bg, fg=C["text"]
                     ).pack(pady=(px(12), px(4)))
            tk.Label(box, text="Klik salah satu profil di daftar untuk melihat detail & membukanya.",
                     font=(FONT, 9), bg=bg, fg=C["muted"], wraplength=px(230), justify="center").pack()
            return

        if len(sel) > 1:
            tk.Label(body, text=f"{len(sel)} profil dipilih", font=(FONT_B, 14), bg=bg, fg=C["text"]
                     ).pack(anchor="w")
            run = sum(1 for p in sel if self.engine.is_running(p.id))
            tk.Label(body, text=f"{run} sedang berjalan", font=(FONT, 9), bg=bg, fg=C["muted"]
                     ).pack(anchor="w", pady=(px(2), px(16)))
            Btn(body, "Buka semua", self.launch_selected, icon="play", variant="primary", size="lg").pack(fill="x")
            Btn(body, "Tutup semua", self.stop_selected, icon="stop").pack(fill="x", pady=(px(8), 0))
            Btn(body, "Cek semua proxy", self.check_selected, icon="globe").pack(fill="x", pady=(px(8), 0))
            Btn(body, "Hapus profil terpilih", self.delete_selected, icon="delete", variant="danger"
                ).pack(fill="x", pady=(px(8), 0))
            names = tk.Frame(body, bg=bg)
            names.pack(fill="x", pady=(px(18), 0))
            for p in sel[:12]:
                tk.Label(names, text="•  " + p.name, font=(FONT, 9), bg=bg, fg=C["muted"], anchor="w"
                         ).pack(fill="x")
            if len(sel) > 12:
                tk.Label(names, text=f"   dan {len(sel) - 12} lainnya", font=(FONT, 9), bg=bg, fg=C["subtle"],
                         anchor="w").pack(fill="x")
            return

        p = sel[0]
        st, msg = self.state.get(p.id, ("stopped", ""))
        fg, soft = STATUS_COLORS.get(st, STATUS_COLORS["stopped"])
        tk.Label(body, text=p.name, font=(FONT_B, 14), bg=bg, fg=C["text"], wraplength=px(270), justify="left"
                 ).pack(anchor="w")
        tk.Label(body, text="●  " + STATUS_LABELS.get(st, st), font=(FONT_B, 9), bg=soft, fg=fg,
                 padx=px(10), pady=px(3)).pack(anchor="w", pady=(px(8), px(16)))

        if self.engine.is_running(p.id) or st in ("running", "starting"):
            Btn(body, "Tutup browser", self.stop_selected, icon="stop", variant="danger_solid", size="lg").pack(fill="x")
        else:
            Btn(body, "Buka browser", self.launch_selected, icon="play", variant="primary", size="lg").pack(fill="x")
        row = tk.Frame(body, bg=bg)
        row.pack(fill="x", pady=(px(8), 0))
        for i, (text, cmd, icon) in enumerate((("Edit", self.edit_selected, "edit"),
                                               ("Salin", self.duplicate_selected, "copy"),
                                               ("Cek IP", self.check_selected, "globe"))):
            row.columnconfigure(i, weight=1, uniform="act")
            Btn(row, text, cmd, icon=icon, size="sm").grid(row=0, column=i, sticky="we",
                                                           padx=(0 if i == 0 else px(6), 0))

        fp = p.fingerprint

        def section(title):
            tk.Label(body, text=title, font=(FONT_B, 8), bg=bg, fg=C["subtle"]).pack(anchor="w", pady=(px(18), px(4)))
            g = tk.Frame(body, bg=bg)
            g.pack(fill="x")
            g.columnconfigure(1, weight=1)
            return g

        def kv(g, key, value, color=None):
            r = g.grid_size()[1]
            tk.Label(g, text=key, font=(FONT, 9), bg=bg, fg=C["muted"]).grid(row=r, column=0, sticky="nw",
                                                                             pady=px(3), padx=(0, px(12)))
            tk.Label(g, text=value or "—", font=(FONT, 9), bg=bg, fg=color or C["text"], wraplength=px(180),
                     justify="left", anchor="w").grid(row=r, column=1, sticky="w", pady=px(3))

        g = section("KONEKSI")
        direct = not (p.proxy.enabled and p.proxy.host)
        kv(g, "Proxy", "Tanpa proxy (IP asli)" if direct else p.proxy.display(), C["warn"] if direct else None)
        sp = self.proxies.get(p.proxy.saved_id) if not direct else None
        if sp:
            kv(g, "Dari menu Proxy", sp.label())
        kv(g, "Lokasi IP", fmt_loc(p))
        kv(g, "WebRTC", WEBRTC_LABELS.get(fp.webrtc, fp.webrtc).split(" (")[0])

        g = section("FINGERPRINT")
        kv(g, "Browser", BROWSER_LABELS.get(p.browser, p.browser).split(" (")[0])
        kv(g, "Layar", fp.summary())
        kv(g, "CPU / RAM", f"{fp.hardware_concurrency} core  ·  {fp.device_memory} GB")
        kv(g, "Kartu grafis", fp.gpu_short())
        kv(g, "Bahasa", fp.locale)
        kv(g, "Zona waktu", fp.timezone or "Ikut komputer")

        g = section("LAINNYA")
        kv(g, "Dibuat", time.strftime("%d %b %Y", time.localtime(p.created)))
        kv(g, "Terakhir dipakai",
           time.strftime("%d %b %Y, %H:%M", time.localtime(p.last_used)) if p.last_used else "Belum pernah")
        if p.notes:
            kv(g, "Catatan", p.notes if len(p.notes) < 160 else p.notes[:157] + "...")
        if st == "error" and msg:
            kv(g, "Error", msg.splitlines()[0][:160], C["danger"])

    # ------------------------------------------------------------ aksi
    def new_profile(self):
        d = ProfileDialog(self, Profile(fingerprint=fpgen.generate()), "Profil baru")
        self.wait_window(d)
        if d.result:
            self.store.put(d.result)
            self.refresh()
            self.tree.selection_set(d.result.id)
            self.tree.see(d.result.id)
            self.set_status(f"Profil '{d.result.name}' dibuat. Klik Buka untuk memakainya.")

    def bulk_create(self):
        d = BulkDialog(self)
        self.wait_window(d)
        if d.result:
            for p in d.result:
                self.store.profiles[p.id] = p
            self.store.save()
            self.refresh()
            self.set_status(f"{len(d.result)} profil dibuat.")

    def edit_selected(self):
        sel = self.selected()
        if len(sel) != 1:
            return
        p = sel[0]
        if self.engine.is_running(p.id):
            messagebox.showinfo(APP_NAME, "Tutup dulu browser profil ini sebelum mengedit.", parent=self)
            return
        d = ProfileDialog(self, p, f"Edit profil — {p.name}")
        self.wait_window(d)
        if d.result:
            self.store.put(d.result)
            self.refresh()
            self.set_status(f"Profil '{d.result.name}' disimpan.")

    def duplicate_selected(self):
        sel = self.selected()
        if len(sel) != 1:
            return
        src = sel[0]
        fp = fpgen.generate(src.fingerprint.locale, src.fingerprint.timezone)
        p = self.store.duplicate(src.id, fp)
        self.refresh()
        self.tree.selection_set(p.id)
        self.set_status(f"Disalin sebagai '{p.name}' dengan fingerprint baru (cookie/login tidak ikut disalin).")

    def delete_selected(self):
        sel = self.selected()
        if not sel:
            return
        if any(self.engine.is_running(p.id) for p in sel):
            messagebox.showinfo(APP_NAME, "Tutup dulu browser profil yang dipilih sebelum menghapus.", parent=self)
            return
        names = "\n".join(f"• {p.name}" for p in sel[:10]) + ("\n..." if len(sel) > 10 else "")
        if not messagebox.askyesno(APP_NAME, f"Hapus {len(sel)} profil berikut beserta cookie, login & riwayatnya?\n\n{names}\n\n"
                                              "Tindakan ini tidak bisa dibatalkan.", icon="warning", parent=self):
            return
        for p in sel:
            self.store.delete(p.id)
            self.state.pop(p.id, None)
        self.refresh()
        self.set_status(f"{len(sel)} profil dihapus.")

    def launch_selected(self):
        todo = [p for p in self.selected() if not self.engine.is_running(p.id)]
        if not todo or not self._confirm_direct(todo):
            return
        for p in todo:
            p.last_used = time.time()
            self.store.save()
            self.state[p.id] = ("starting", "Memulai...")
            self._refresh_row(p.id)
            self.engine.launch(p, self.store.userdata_dir(p.id))

    def _confirm_direct(self, todo: list[Profile]) -> bool:
        """Profil tanpa proxy memakai IP asli yang sama -> situs bisa menghubungkannya."""
        direct = lambda p: not (p.proxy.enabled and p.proxy.host)  # noqa: E731
        new = [p for p in todo if direct(p)]
        if not new:
            return True
        running = [p for p in self.store.profiles.values() if direct(p) and self.engine.is_running(p.id)]
        group = new + running
        if len(group) < 2:
            return True
        names = "\n".join(f"• {p.name}" for p in group[:10]) + ("\n..." if len(group) > 10 else "")
        return messagebox.askyesno(
            APP_NAME,
            f"{len(group)} profil berikut akan terbuka bersamaan TANPA proxy:\n\n{names}\n\n"
            "Semuanya memakai IP asli & zona waktu komputer ini, jadi situs bisa tahu "
            "profil-profil ini milik orang yang sama.\n\n"
            "Pasang proxy berbeda di tiap profil supaya benar-benar terpisah.\n\n"
            "Tetap buka?", icon="warning", parent=self)

    def stop_selected(self):
        for p in self.selected():
            if self.engine.is_running(p.id):
                self.engine.stop(p.id)

    def check_selected(self):
        sel = [p for p in self.selected() if p.proxy.enabled and p.proxy.host]
        if not sel:
            messagebox.showinfo(APP_NAME, "Profil yang dipilih tidak memakai proxy.", parent=self)
            return
        self.set_status(f"Mengecek {len(sel)} proxy...")
        results: list[str] = []

        def one(p: Profile):
            def done(geo, err):
                if p.id in self.store.profiles:
                    if geo:
                        p.proxy.last_ip, p.proxy.last_country = geo["ip"], geo.get("country", "")
                        self.store.save()
                        self._refresh_row(p.id)
                        results.append(f"✓ {p.name}: {fmt_geo(geo)}")
                    else:
                        results.append(f"✗ {p.name}: {str(err).splitlines()[0]}")
                if len(results) == len(sel):
                    self.set_status("Cek proxy selesai.")
                    messagebox.showinfo("Hasil cek proxy", "\n".join(results), parent=self)

            run_bg(self, lambda: proxy_check.check(p.proxy), done)

        for p in sel:
            one(p)

    def open_folder(self):
        sel = self.selected()
        path = self.store.userdata_dir(sel[0].id) if len(sel) == 1 else paths.data_dir()
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(path)

    # ------------------------------------------------------------ event dari engine
    def _poll(self):
        try:
            while True:
                self._handle(self.events.get_nowait())
        except queue.Empty:
            pass
        self.after(150, self._poll)

    def _handle(self, ev: tuple):
        kind, pid = ev[0], ev[1]
        p = self.store.profiles.get(pid)
        name = p.name if p else pid
        if kind == "status":
            state, msg = ev[2], ev[3]
            self.state[pid] = (state, msg)
            self._refresh_row(pid)
            if state == "error":
                self.set_status(f"Gagal membuka '{name}'.")
                messagebox.showerror(APP_NAME, f"Gagal membuka profil '{name}':\n\n{msg}", parent=self)
            elif state == "running":
                self.set_status(f"'{name}' berjalan.")
            elif state == "starting":
                self.set_status(f"'{name}': {msg}")
            elif state == "stopped":
                self.set_status(f"'{name}' ditutup.")
        elif kind == "geo" and p:
            geo, fp = ev[2], ev[3]
            p.proxy.last_ip, p.proxy.last_country = geo["ip"], geo.get("country", "")
            if fp is not None:
                fp.canvas_seed, fp.webgl_seed, fp.audio_seed = (
                    p.fingerprint.canvas_seed, p.fingerprint.webgl_seed, p.fingerprint.audio_seed)
                p.fingerprint = fp
            self.store.save()
            self._refresh_row(pid)
        elif kind == "log":
            self.set_status(f"'{name}': {ev[2]}")

    def _on_close(self):
        running = [pid for pid in self.store.profiles if self.engine.is_running(pid)]
        if running and not messagebox.askyesno(
                APP_NAME, f"{len(running)} browser masih terbuka. Tutup semuanya dan keluar?", parent=self):
            return
        self.set_status("Menutup semua browser...")
        self.update_idletasks()
        self.engine.shutdown()
        self.destroy()


def main():
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)  # teks tajam di layar ber-skala
    except Exception:
        pass
    App().mainloop()
