"""Command line.

  python -m chrome_profile_hub                       open the table (GUI)
  python -m chrome_profile_hub list [--owner X] [--service notion] [--open-only]
  python -m chrome_profile_hub json                  full scan as JSON (for agents)
  python -m chrome_profile_hub open <profile> [url]  start / focus a profile
  python -m chrome_profile_hub new <email> [owner]   create a profile for a Google account and open the sign-in page
  python -m chrome_profile_hub set <profile> owner=Team note="..." email=...
  python -m chrome_profile_hub pick <service> [--owner X]   which profile to use for a service
  python -m chrome_profile_hub screenshot <folder> [--demo]
"""
import json
import sys

from . import core, scanner as S


def opt(a, name):
    return a[a.index(name) + 1] if name in a and a.index(name) + 1 < len(a) else None


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    if sys.stdout:
        sys.stdout.reconfigure(encoding="utf-8")
    cmd = a[0] if a else "gui"
    if cmd in ("gui", "--demo"):
        from . import gui
        gui.run(demo="--demo" in a)
    elif cmd == "list":
        o, s = opt(a, "--owner"), opt(a, "--service")
        for r in S.scan():
            if o and r["owner"].lower() != o.lower():
                continue
            if s and s not in r["services"]:
                continue
            if "--open-only" in a and not r["open"]:
                continue
            if not (r["services"] or r["email"] or r["open"] or r["note"]) and not (o or s):
                continue
            print(f"{r['port']} {'OPEN' if r['open'] else '    '} {r['owner'][:8]:8} {(r['email'] or '(' + r['key'] + ')')[:36]:36} "
                  f"{','.join(r['services'])} {('· ' + r['by']) if r['by'] else ''}")
    elif cmd == "json":
        print(json.dumps(S.scan(), ensure_ascii=False, indent=1))
    elif cmd == "open":
        r = core.open_url(a[1], a[2] if len(a) > 2 else None)
        print(f"{r['email'] or r['name']} - port {r['port']}")
    elif cmd == "new":
        r = core.new_profile(a[1], a[1])
        S.set_meta(r["key"], email=a[1], owner=a[2] if len(a) > 2 else S.guess_owner(a[1], ""))
        core.start(r["key"], "https://accounts.google.com/AddSession?Email=" + a[1])
        print(f"created {r['key']} - port {r['port']} - sign in in the window that just opened")
    elif cmd == "set":
        kv = dict(x.split("=", 1) for x in a[2:])
        print("OK", S.set_meta(a[1], **kv))
    elif cmd == "pick":
        r = S.pick(a[1], owner=opt(a, "--owner"))
        print(json.dumps({k: r[k] for k in ("key", "email", "port", "owner", "open")} if r else None, ensure_ascii=False))
    elif cmd == "screenshot":
        from . import gui
        gui.run(screenshot_dir=a[1], demo="--demo" in a)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
