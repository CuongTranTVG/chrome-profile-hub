"""Configuration: one JSON file, every path overridable.

Lookup order for the config file:
  1. environment variable CPH_CONFIG
  2. %APPDATA%\\ChromeProfileHub\\config.json  (Windows) / ~/.config/chrome-profile-hub/config.json
Missing file = sensible defaults (everything lives under the data dir).
"""
import json
import os
import shutil
import sys
from pathlib import Path


def _default_data_dir():
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "ChromeProfileHub"
    return Path.home() / ".local" / "share" / "chrome-profile-hub"


def config_path():
    if os.environ.get("CPH_CONFIG"):
        return Path(os.environ["CPH_CONFIG"])
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", Path.home())) / "ChromeProfileHub" / "config.json"
    return Path.home() / ".config" / "chrome-profile-hub" / "config.json"


def find_chrome():
    cands = []
    if os.name == "nt":
        for base in (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")):
            if base:
                cands.append(Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe")
    elif sys.platform == "darwin":
        cands.append(Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"))
    else:
        for n in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
            p = shutil.which(n)
            if p:
                cands.append(Path(p))
    for c in cands:
        if c.exists():
            return str(c)
    return str(cands[0]) if cands else "chrome"


DEFAULTS = {
    "lang": "en",                 # "en" or "vi"
    "agent_label": "AI",          # shown in the "In use" column, e.g. "Claude"
    "chrome_path": None,          # auto-detect real Google Chrome
    "data_dir": None,             # ports, metadata, scan cache, leases, logs
    "profiles_root": None,        # where "+ New account" creates profiles (default: <data_dir>/profiles)
    "scan_roots": [],             # extra folders: every sub-folder is treated as a Chrome user-data-dir
    "pinned": [],                 # [{"key","dir","port","name","email"}] fixed profiles with fixed ports
    "index_files": [],            # [{"path": "...json", "base": "folder"}]  {key: {"name","email","dir"|"pw_dir"}}
    "skip": [],                   # folder names to ignore (case-insensitive)
    "port_range": [9400, 9999],
    "owners": ["Me", "Team", "Client", "Shared", "?"],
    "owner_rules": [],            # [["substring-in-email-or-name", "Owner"], ...]  first match wins
    "files": {},                  # override single files: ports, meta, status, leases, accounts, log
    "lease_minutes": 30,
    "everyday_chrome": False,     # also list the profiles of your normal Chrome (human-only rows, see README)
    "everyday_user_data": None,   # default: %LOCALAPPDATA%\\Google\\Chrome\\User Data
    "remote_allow_origins": None, # leave empty unless an old tool needs it (e.g. "*"); the port only listens on 127.0.0.1
}


class Config(dict):
    def __getattr__(self, k):
        return self[k]

    def file(self, name, default):
        f = self["files"].get(name)
        return Path(f) if f else self.data_dir / default


def load():
    cfg = dict(DEFAULTS)
    p = config_path()
    if p.exists():
        user = json.loads(p.read_text(encoding="utf-8-sig"))
        cfg.update({k: v for k, v in user.items() if not k.startswith("_")})
    c = Config(cfg)
    c["data_dir"] = Path(os.path.expandvars(os.path.expanduser(c["data_dir"]))) if c["data_dir"] else _default_data_dir()
    c["profiles_root"] = Path(os.path.expandvars(os.path.expanduser(c["profiles_root"]))) if c["profiles_root"] else c["data_dir"] / "profiles"
    c["chrome_path"] = c["chrome_path"] or find_chrome()
    c["scan_roots"] = [Path(os.path.expandvars(os.path.expanduser(x))) for x in c["scan_roots"]]
    if not c.get("everyday_user_data"):
        c["everyday_user_data"] = str(Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Google" / "Chrome" / "User Data") if os.name == "nt" \
            else str(Path.home() / ("Library/Application Support/Google/Chrome" if sys.platform == "darwin" else ".config/google-chrome"))
    c["config_file"] = p
    c["data_dir"].mkdir(parents=True, exist_ok=True)
    return c


CFG = load()
