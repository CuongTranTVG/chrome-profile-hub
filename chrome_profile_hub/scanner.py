"""Which services is each profile logged in to?

We only read cookie NAMES and EXPIRY dates (never values, never decrypt anything):
- closed profile: read the Cookies SQLite file read-only;
- running profile (file is locked): ask Chrome itself over CDP (Storage.getCookies).
A check mark means "a session cookie exists and has not expired" - the site may still
have logged you out on its side (password change, remote sign-out).
"""
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from .config import CFG
from . import core

# key, column label, cookie domain suffixes, session cookie names, login URL
SERVICES = [
    ("google",    "Google",   ("google.com",),             ("SID", "__Secure-1PSID"), "https://accounts.google.com/AddSession?Email={email}"),
    ("notion",    "Notion",   ("notion.so", "notion.com"), ("token_v2",),             "https://www.notion.so/login"),
    ("facebook",  "FB/Meta",  ("facebook.com",),           ("c_user",),               "https://www.facebook.com/login"),
    ("slack",     "Slack",    ("slack.com",),              ("d",),                    "https://slack.com/signin"),
    ("zalo",      "Zalo",     ("zalo.me",),                ("zpw_sek",),              "https://chat.zalo.me"),
    ("tiktok",    "TikTok",   ("tiktok.com",),             ("sessionid",),            "https://www.tiktok.com/login"),
    ("lark",      "Lark",     ("larksuite.com",),          ("session", "sl_session"), "https://www.larksuite.com/"),
    ("hubspot",   "HubSpot",  ("hubspot.com",),            ("hubspotapi",),           "https://app.hubspot.com/login"),
    ("instagram", "IG",       ("instagram.com",),          ("sessionid",),            "https://www.instagram.com/accounts/login/"),
    ("github",    "GitHub",   ("github.com",),             ("user_session",),         "https://github.com/login"),
    ("claude",    "Claude",   ("claude.ai",),              ("sessionKey",),           "https://claude.ai/login"),
    ("linkedin",  "LinkedIn", ("linkedin.com",),           ("li_at",),                "https://www.linkedin.com/login"),
    ("x",         "X",        ("x.com", "twitter.com"),    ("auth_token",),           "https://x.com/i/flow/login"),
    ("shopee",    "Shopee",   ("shopee.vn", "shopee.com"), ("SPC_EC",),               "https://shopee.vn/buyer/login"),
]
SVC = {s[0]: s for s in SERVICES}

META = CFG.file("meta", "meta.json")
STATUS = CFG.file("status", "status.json")
LOG = CFG.file("log", "hub.log")


def log(msg):
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except OSError:
        pass


def match(host, name):
    h = host.lstrip(".").lower()
    for key, _, doms, names, _ in SERVICES:
        if name in names and any(h == x or h.endswith("." + x) or (key == "google" and h.startswith("google.")) for x in doms):
            return key
    return None


def _fmt(best, epoch_offset):
    return {k: ("session" if not e else datetime.fromtimestamp(e - epoch_offset).strftime("%Y-%m-%d")) for k, e in best.items()}


def services_from_cdp(port):
    import urllib.request
    import websocket
    info = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=3).read())
    ws = websocket.create_connection(info["webSocketDebuggerUrl"], timeout=8, suppress_origin=True)
    ws.send(json.dumps({"id": 1, "method": "Storage.getCookies"}))
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == 1:
            break
    ws.close()
    best = {}
    for c in m.get("result", {}).get("cookies", []):
        k = match(c["domain"], c["name"])
        if k:
            best[k] = max(best.get(k, 0), c["expires"] if c.get("expires", -1) > 0 else 0)
    return _fmt(best, 0)


def services_from_disk(d, port=None):
    for rel in ("Default/Network/Cookies", "Default/Cookies"):
        p = Path(d) / rel
        if not p.exists():
            continue
        try:
            c = sqlite3.connect("file:" + p.as_posix() + "?mode=ro&immutable=1", uri=True)
            rows = c.execute("select host_key, name, expires_utc, has_expires from cookies").fetchall()
            c.close()
        except Exception as e:      # locked by a running Chrome -> ask Chrome instead
            if port:
                try:
                    return services_from_cdp(port)
                except Exception as e2:
                    log(f"cdp {port}: {e2}")
            log(f"cookies {d}: {e}")
            return {}
        now = (datetime.now(timezone.utc) - datetime(1601, 1, 1, tzinfo=timezone.utc)).total_seconds() * 1e6
        best = {}
        for host, name, exp, has_exp in rows:
            k = match(host, name)
            if k and not (has_exp and exp and exp < now):
                best[k] = max(best.get(k, 0), exp / 1e6 if has_exp and exp else 0)
        return _fmt(best, 11644473600)   # Chrome time starts 1601-01-01
    return {}


def chrome_signed_in(d):
    pr = core._load(Path(d) / "Default" / "Preferences", {})
    return [a.get("email") for a in pr.get("account_info", []) if a.get("email")]


def guess_owner(email, name):
    t = f"{email} {name}".lower()
    for sub, owner in CFG.owner_rules:
        if sub.lower() in t:
            return owner
    return "?"


def scan():
    meta = core._load(META, {})
    listening = core.listening_ports()
    rows = []
    for r in core.catalog():
        m = meta.get(r["key"], {})
        exists = Path(r["dir"]).exists()
        ce = chrome_signed_in(r["dir"]) if exists else []
        email = m.get("email") or r["email"] or (ce[0] if ce else "")
        is_open = (r["port"] in listening) if listening is not None else core.port_open(r["port"])
        L = core.leases_of(r["key"]) if is_open else []
        tasks = "; ".join(x["task"] for x in L if x.get("task"))
        by = ""
        if L:
            by = f"{CFG.agent_label}" + (f" x{len(L)}" if len(L) > 1 else "") + (f": {tasks}" if tasks else "")
        elif is_open:
            by = "human"
        rows.append({
            "key": r["key"], "name": m.get("name") or r["name"], "email": email, "port": r["port"], "dir": r["dir"],
            "owner": m.get("owner") or guess_owner(email, r["name"]), "note": m.get("note", ""),
            "open": is_open, "by": by, "agent": bool(L), "exists": exists, "chrome_login": ce,
            "services": services_from_disk(r["dir"], r["port"] if is_open else None) if exists else {},
        })
    core._save(STATUS, {"scanned": time.strftime("%Y-%m-%d %H:%M:%S"), "rows": rows})
    return rows


def cached():
    return core._load(STATUS, {})


def set_meta(key, **kv):
    meta = core._load(META, {})
    r = core.find(key)
    m = meta.setdefault(r["key"], {})
    for k, v in kv.items():
        if v in (None, ""):
            m.pop(k, None)
        else:
            m[k] = v
    core._save(META, meta)
    return r["key"]


def pick(service, owner=None, email=None):
    """For agents: best profile already logged in to `service` (running ones first)."""
    hits = [r for r in scan() if service in r["services"]
            and (not owner or r["owner"].lower() == owner.lower())
            and (not email or email.lower() in r["email"].lower())]
    hits.sort(key=lambda r: (not r["open"], r["key"]))
    return hits[0] if hits else None
