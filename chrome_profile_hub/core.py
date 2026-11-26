"""Core: every profile = a real Google Chrome user-data-dir with a FIXED remote-debugging port.

Why real Chrome: Google blocks sign-in inside the Chromium that Playwright launches
(automation flags), but a normal Chrome started by you is just a normal browser.
An AI agent then attaches to it over CDP (Chrome DevTools Protocol) with
`playwright.chromium.connect_over_cdp(...)` and reuses the logins a human already made.
"""
import json
import os
import re
import socket
import subprocess
import time
from pathlib import Path

from .config import CFG


def _norm(p):
    return str(p).rstrip("\\/").replace("/", "\\").lower() if os.name == "nt" else str(p).rstrip("/")


def _load(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def _save(p, data):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


PORTS = CFG.file("ports", "ports.json")
ACCOUNTS = CFG.file("accounts", "accounts.json")
LEASES = CFG.file("leases", "leases")


def catalog():
    """All known profiles: [{key, name, email, dir, port}]. Ports are assigned once and persisted."""
    ports = _load(PORTS, {})
    lo, hi = CFG.port_range
    skip = {s.lower() for s in CFG.skip}
    pinned_ports = {int(x["port"]) for x in CFG.pinned if x.get("port")}
    rows, seen, changed = [], set(), False

    def add(key, d, name="", email="", port=None):
        nonlocal changed
        k = _norm(d)
        if k in seen or Path(d).name.lower() in skip:
            return
        seen.add(k)
        if port is None:
            port = ports.get(k)
            if port is None:
                used = set(ports.values()) | pinned_ports
                port = next(x for x in range(lo, hi) if x not in used)
                ports[k] = port
                changed = True
        rows.append({"key": key, "name": name or key, "email": email, "dir": str(d), "port": int(port)})

    for x in CFG.pinned:
        add(x["key"], Path(os.path.expandvars(os.path.expanduser(x["dir"]))), x.get("name", ""), x.get("email", ""), x.get("port"))
    for key, v in _load(ACCOUNTS, {}).items():
        add(key, Path(v.get("dir") or CFG.profiles_root / key), v.get("name") or key, v.get("email") or "")
    for idx in CFG.index_files:
        base = Path(idx.get("base", ""))
        for key, v in _load(idx["path"], {}).items():
            add(key, Path(v.get("dir") or v.get("pw_dir") or base / key), v.get("name") or key, v.get("email") or "")
    for root in [CFG.profiles_root] + list(CFG.scan_roots):
        if root.exists():
            for d in sorted(root.iterdir(), key=lambda x: x.name.lower()):
                if d.is_dir():
                    add(d.name, d)
    if changed or not PORTS.exists():
        _save(PORTS, ports)
    return rows


def find(name):
    """Find by key, email, display name or folder path (exact first, then unique substring)."""
    q = str(name).strip().lower()
    rows = catalog()
    for f in ("key", "email", "name", "dir"):
        for r in rows:
            if (r[f] or "").lower() == q or (f == "dir" and _norm(r["dir"]) == _norm(name)):
                return r
    hits = [r for r in rows if q in f"{r['name']} {r['email']} {r['key']}".lower()]
    if len(hits) == 1:
        return hits[0]
    raise KeyError(f"Profile '{name}' not found" + (f" ({len(hits)} matches: {[h['key'] for h in hits][:6]})" if hits else ""))


def new_profile(email, name=""):
    """Create (or return) a dedicated profile for one Google account."""
    try:
        return find(email)
    except KeyError:
        pass
    key = re.sub(r"[^a-z0-9]+", "_", email.lower()).strip("_") + "_chrome"
    acc = _load(ACCOUNTS, {})
    acc[key] = {"email": email, "name": name or email, "dir": str(CFG.profiles_root / key)}
    _save(ACCOUNTS, acc)
    (CFG.profiles_root / key).mkdir(parents=True, exist_ok=True)
    return find(key)


def port_open(port):
    s = socket.socket()
    s.settimeout(0.5)
    try:
        return s.connect_ex(("127.0.0.1", int(port))) == 0
    finally:
        s.close()


def listening_ports():
    """All local listening TCP ports in one call (much faster than probing each port on Windows)."""
    try:
        import psutil
        return {c.laddr.port for c in psutil.net_connections("tcp") if c.status == "LISTEN"}
    except Exception:
        return None


def dir_in_use_without_port(d):
    """The folder is open in a Chrome window that has NO debugging port (opened outside the hub)."""
    try:
        import psutil
    except ImportError:
        return False
    k = _norm(d)
    for p in psutil.process_iter(["name", "cmdline"]):
        try:
            cl = p.info["cmdline"] or []
            if "chrome" in (p.info["name"] or "").lower() \
                    and any(a.lower().startswith("--user-data-dir=") and _norm(a.split("=", 1)[1].strip('"')) == k for a in cl) \
                    and not any(a.startswith("--type=") for a in cl) \
                    and not any(a.startswith("--remote-debugging-port") for a in cl):
                return True
        except Exception:
            continue
    return False


def start(name, url=None):
    """Start real Chrome for this profile with its fixed port (no-op if already running)."""
    r = find(name)
    if port_open(r["port"]):
        return r
    if dir_in_use_without_port(r["dir"]):
        raise RuntimeError(f"'{r['name']}' is already open in a window without a debugging port. Close it and open it from the hub.")
    Path(r["dir"]).mkdir(parents=True, exist_ok=True)
    args = [CFG.chrome_path, f"--user-data-dir={r['dir']}", f"--remote-debugging-port={r['port']}",
            "--no-first-run", "--no-default-browser-check", "--start-maximized"]
    if CFG.get("remote_allow_origins"):   # default: none -> only clients WITHOUT an Origin header (Playwright, scripts) may connect
        args.append(f"--remote-allow-origins={CFG.remote_allow_origins}")
    if url:
        args.append(url)
    subprocess.Popen(args, close_fds=True)
    for _ in range(60):
        if port_open(r["port"]):
            return r
        time.sleep(0.5)
    raise RuntimeError(f"Chrome '{r['name']}' did not open port {r['port']}")


def bring_window(r, url=None):
    """Already running: ask that Chrome to open one more window (same port, same session)."""
    subprocess.Popen([CFG.chrome_path, f"--user-data-dir={r['dir']}", "--new-window"] + ([url] if url else []), close_fds=True)


def open_url(name, url=None):
    r = find(name)
    if port_open(r["port"]):
        bring_window(r, url)
    else:
        start(r["key"], url)
    return r


def lease(r, task=""):
    """Mark 'an AI agent is using this profile' -> the hub shows the row in yellow.
    One file per process, removed automatically when the process exits."""
    import atexit
    LEASES.mkdir(parents=True, exist_ok=True)
    f = LEASES / f"{r['key']}__{os.getpid()}.json"
    f.write_text(json.dumps({"pid": os.getpid(), "ts": time.time(),
                             "task": (task or os.environ.get("CPH_TASK", ""))[:60]}, ensure_ascii=False), encoding="utf-8")
    atexit.register(lambda: f.unlink(missing_ok=True))


def leases_of(key):
    try:
        import psutil
    except ImportError:
        psutil = None
    out = []
    if not LEASES.exists():
        return out
    for f in list(LEASES.glob(f"{key}__*.json")) + [LEASES / f"{key}.json"]:
        L = _load(f, None)
        if not L:
            continue
        if time.time() - L.get("ts", 0) < CFG.lease_minutes * 60 and (psutil is None or psutil.pid_exists(L.get("pid", -1))):
            out.append(L)
        else:
            f.unlink(missing_ok=True)
    return out


def open_chrome(p, name, task=""):
    """For AI agents (Playwright sync API):
        with sync_playwright() as p:
            browser, ctx = open_chrome(p, "me@gmail.com", task="weekly GA4 report")
            page = agent_page(ctx, "https://analytics.google.com")
    Never call browser.close(): that would close the human's window too.
    """
    r = start(name)
    try:
        lease(r, task)
    except Exception:
        pass
    browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{r['port']}")
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    return browser, ctx


def agent_page(ctx, url=None):
    """A tab that belongs to this agent run only; closed automatically when the script exits."""
    import atexit
    pg = ctx.new_page()

    def _close():
        try:
            pg.close()
        except Exception:
            pass
    atexit.register(_close)
    if url:
        pg.goto(url)
    return pg


def close_profile(r):
    """Close Chrome gracefully over CDP (same as clicking X: session cookies are saved)."""
    import urllib.request
    import websocket
    info = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{r['port']}/json/version", timeout=3).read())
    ws = websocket.create_connection(info["webSocketDebuggerUrl"], timeout=5, suppress_origin=True)
    ws.send(json.dumps({"id": 1, "method": "Browser.close"}))
    try:
        ws.recv()
    except Exception:
        pass
    ws.close()
