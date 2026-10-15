import sys


def selftest() -> int:
    """Uji cepat: buka browser dengan profil sementara, cek fingerprint, tulis hasil ke selftest.log."""
    import json
    import queue
    import tempfile
    import time
    from pathlib import Path

    from privacy_browser import fingerprint as fpgen
    from privacy_browser import paths
    from privacy_browser.engine import Engine, resolve_browser
    from privacy_browser.models import Profile

    log = paths.data_dir() / "selftest.log"
    lines = [f"browser: {resolve_browser('auto')}"]
    q: queue.Queue = queue.Queue()
    eng = Engine(q.put)
    p = Profile(name="selftest", start_url="", fingerprint=fpgen.generate())
    ok = False
    with tempfile.TemporaryDirectory() as tmp:
        eng.launch(p, Path(tmp) / "ud")
        end = time.time() + 60
        while time.time() < end:
            try:
                ev = q.get(timeout=1)
            except queue.Empty:
                continue
            if ev[0] == "status" and ev[2] in ("running", "error"):
                lines.append(f"status: {ev[2]} {ev[3]}")
                break
        if p.id in eng.instances:
            async def probe():
                page = eng.instances[p.id].context.pages[0]
                await page.goto("data:text/html,<p>ok</p>")
                return await page.evaluate("({cores: navigator.hardwareConcurrency, w: screen.width, webdriver: navigator.webdriver})")
            r = eng.submit(probe()).result(30)
            lines.append("probe: " + json.dumps(r))
            ok = (r["cores"] == p.fingerprint.hardware_concurrency and r["w"] == p.fingerprint.screen_width
                  and r["webdriver"] is False)
        eng.shutdown()
    lines.append("RESULT: " + ("OK" if ok else "GAGAL"))
    log.write_text("\n".join(lines), "utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    from privacy_browser.gui import main

    main()
