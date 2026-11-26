"""Desktop table (Tkinter, no extra install): open / re-login / close profiles, see who is using what."""
import os
import threading
import time
import traceback

from .config import CFG
from . import core, scanner as S

T = {
    "en": {
        "title": "Chrome Profile Hub - shared by humans and AI agents", "search": "Search", "owner": "Owner", "all": "All",
        "logged": "Logged in to", "any": "(any)", "none": "(nothing yet)", "only_open": "Open only", "hide_empty": "Hide empty",
        "c_email": "Profile (Google email)", "c_name": "Old name", "c_owner": "Owner", "c_state": "Status", "c_by": "In use by",
        "c_note": "Note", "open": "● Open", "closed": "Closed", "human": "Human", "no_email": "no email",
        "legend": "✓ = login saved (cookie not expired). Green = open, yellow = an AI agent is using it (don't close). "
                  "Agents always work in their own tab; humans keep using their own window.",
        "scanning": "Scanning profiles…", "status": "{shown}/{total} profiles · {open} open · scanned {ts}", "old": "(cached)",
        "pick_row": "Select a row first.", "opened": "Opened {name} (port {port}).", "closed_msg": "Closed {name}.",
        "already_closed": "This profile is not running.", "agent_busy": "AI agent is using it",
        "agent_busy_q": "{by}\nClosing it will break the agent's work. Close anyway?",
        "m_open": "Open", "m_relogin": "Log in again…", "m_relogin_x": "Log in again: {svc}", "m_detail": "Details / expiry dates",
        "m_edit": "Edit owner / note / email", "m_close": "Close profile", "m_folder": "Open folder",
        "b_refresh": "Refresh", "b_new": "+ New account", "b_edit": "Edit", "b_close": "Close", "b_google": "Log in Google again", "b_open": "Open",
        "q_owner": "Owner of {name} ({owners}):", "q_note": "Note (what it is used for, whose phone has 2FA…):", "q_email": "Google email of this profile:",
        "q_new": "Google email (one email = one profile):", "new_done": "Created {key} - sign in to Google + 2FA in the new window.",
        "d_old": "Old name", "d_chrome": "Signed in to Chrome", "d_port": "Port", "d_dir": "Folder", "d_saved": "Saved logins",
        "everyday": "Everyday Chrome (human only)", "everyday_stale": "Everyday Chrome · Chrome open, logins from last scan",
        "d_none": "  (no saved logins)", "d_exp": "expires", "err": "Error", "scan_err": "Scan error: {e}",
    },
    "vi": {
        "title": "Chrome Profile Hub - Kho tài khoản dùng chung Người + AI", "search": "Tìm", "owner": "Chủ", "all": "Tất cả",
        "logged": "Có đăng nhập", "any": "(bất kỳ)", "none": "(chưa có gì)", "only_open": "Chỉ đang mở", "hide_empty": "Ẩn profile trống",
        "c_email": "Profile (email Google)", "c_name": "Tên cũ", "c_owner": "Chủ", "c_state": "Trạng thái", "c_by": "Đang dùng",
        "c_note": "Ghi chú", "open": "● Đang mở", "closed": "Đóng", "human": "Người", "no_email": "chưa có email",
        "legend": "✓ = đã lưu đăng nhập (cookie chưa hết hạn). Xanh = đang mở, vàng = AI đang dùng (đừng đóng). "
                  "AI luôn làm ở tab riêng; người cứ dùng cửa sổ của mình.",
        "scanning": "Đang quét các profile…", "status": "{shown}/{total} profile · đang mở {open} · quét lúc {ts}", "old": "(cũ)",
        "pick_row": "Chọn 1 dòng trước.", "opened": "Đã mở {name} (cổng {port}).", "closed_msg": "Đã đóng {name}.",
        "already_closed": "Profile đang đóng.", "agent_busy": "AI đang dùng",
        "agent_busy_q": "{by}\nĐóng sẽ làm hỏng việc AI đang chạy. Vẫn đóng?",
        "m_open": "Mở (bật profile)", "m_relogin": "Đăng nhập lại…", "m_relogin_x": "Đăng nhập lại {svc}", "m_detail": "Xem chi tiết / ngày hết hạn",
        "m_edit": "Sửa chủ / ghi chú / email", "m_close": "Đóng profile", "m_folder": "Mở thư mục",
        "b_refresh": "Làm mới", "b_new": "+ Tài khoản mới", "b_edit": "Sửa", "b_close": "Đóng", "b_google": "Đăng nhập lại Google", "b_open": "Mở",
        "q_owner": "Chủ của {name} ({owners}):", "q_note": "Ghi chú (dùng cho việc gì, 2FA ở máy ai…):", "q_email": "Email Google của profile:",
        "q_new": "Email Google (mỗi email 1 profile riêng):", "new_done": "Đã tạo {key} – đăng nhập Google + 2FA trong cửa sổ vừa mở.",
        "d_old": "Tên cũ", "d_chrome": "Chrome đăng nhập", "d_port": "Cổng", "d_dir": "Thư mục", "d_saved": "Đăng nhập đã lưu",
        "everyday": "Chrome thường (chỉ người)", "everyday_stale": "Chrome thường · đang mở, đăng nhập theo lần quét trước",
        "d_none": "  (chưa lưu đăng nhập dịch vụ nào)", "d_exp": "hết hạn", "err": "Lỗi", "scan_err": "Lỗi quét: {e}",
    },
}
L = T.get(CFG.lang, T["en"])

DEMO = [  # fake data for screenshots (--demo)
    {"key": "a", "name": "Work", "email": "alex@example.com", "owner": "Me", "open": True, "by": "", "agent": False, "note": "Ads + GA4",
     "services": {"google": "2027-11-30", "facebook": "2027-08-01", "slack": "2027-11-20", "notion": "2027-10-02"}},
    {"key": "b", "name": "Marketing", "email": "marketing@example.com", "owner": "Team", "open": True, "by": "AI: weekly GA4 report", "agent": True,
     "note": "", "services": {"google": "2027-11-28", "tiktok": "2027-05-01", "instagram": "2027-06-11", "hubspot": "session"}},
    {"key": "c", "name": "Client A", "email": "ads@client-a.example", "owner": "Client", "open": False, "by": "", "agent": False,
     "note": "2FA on Sam's phone", "services": {"google": "2027-09-14", "facebook": "2027-07-21"}},
    {"key": "d", "name": "Personal", "email": "alex.personal@example.org", "owner": "Me", "open": False, "by": "", "agent": False, "note": "",
     "services": {"google": "2027-12-01", "github": "2027-03-03", "claude": "2027-01-09", "linkedin": "2027-10-10"}},
    {"key": "e", "name": "Shop", "email": "owner@shop.example", "owner": "Shared", "open": False, "by": "", "agent": False, "note": "",
     "services": {"google": "2027-10-10", "shopee": "2027-02-02", "zalo": "session", "lark": "2027-04-04"}},
    {"key": "f", "name": "Old test", "email": "", "owner": "?", "open": False, "by": "", "agent": False, "note": "", "services": {}},
]
for _r in DEMO:
    _r.update(port=9400 + DEMO.index(_r), dir=f"C:\\profiles\\{_r['key']}", exists=True, chrome_login=[])


def run(screenshot_dir=None, demo=False):
    import tkinter as tk
    from tkinter import ttk, messagebox, simpledialog
    win = tk.Tk()
    win.title(L["title"])
    win.geometry(f"{min(1560, win.winfo_screenwidth() - 40)}x760")
    icon = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icon.ico")
    if os.path.exists(icon):
        try:
            win.iconbitmap(icon)
        except Exception:
            pass
    st = ttk.Style(win)
    st.configure("Treeview", rowheight=26, font=("Segoe UI", 10))
    st.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    top = ttk.Frame(win, padding=(10, 10, 10, 4))
    top.pack(fill="x")
    ttk.Label(top, text=L["search"]).pack(side="left")
    q = tk.StringVar()
    ent = ttk.Entry(top, textvariable=q, width=34, font=("Segoe UI", 11))
    ent.pack(side="left", padx=6)
    ttk.Label(top, text=L["owner"]).pack(side="left", padx=(12, 0))
    own = tk.StringVar(value=L["all"])
    ttk.Combobox(top, textvariable=own, values=[L["all"]] + CFG.owners, width=9, state="readonly").pack(side="left", padx=6)
    ttk.Label(top, text=L["logged"]).pack(side="left", padx=(12, 0))
    svc = tk.StringVar(value=L["any"])
    ttk.Combobox(top, textvariable=svc, values=[L["any"], L["none"]] + [s[1] for s in S.SERVICES], width=11, state="readonly").pack(side="left", padx=6)
    only_open = tk.BooleanVar()
    ttk.Checkbutton(top, text=L["only_open"], variable=only_open).pack(side="left", padx=12)
    hide_empty = tk.BooleanVar(value=True)
    ttk.Checkbutton(top, text=L["hide_empty"], variable=hide_empty).pack(side="left")

    mid = ttk.Frame(win, padding=(10, 0, 10, 0))
    mid.pack(fill="both", expand=True)
    cols = ["email", "name", "owner", "state", "by"] + [s[0] for s in S.SERVICES] + ["note"]
    heads = {"email": (L["c_email"], 250), "name": (L["c_name"], 120), "owner": (L["c_owner"], 60), "state": (L["c_state"], 80),
             "by": (L["c_by"], 150), "note": (L["c_note"], 160)}
    tree = ttk.Treeview(mid, columns=cols, show="headings", selectmode="browse")
    for c in cols:
        t, w = heads.get(c, (S.SVC[c][1] if c in S.SVC else c, 52))
        tree.heading(c, text=t, command=lambda c=c: sort_by(c))
        tree.column(c, width=w, anchor="w" if c in heads else "center", stretch=c in ("email", "note"))
    sb = ttk.Scrollbar(mid, command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    if win.winfo_screenwidth() < 1500:   # small screen: hide the two least important columns
        tree["displaycolumns"] = [c for c in cols if c not in ("name", "note")]
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    tree.tag_configure("open", background="#e6f4ea")
    tree.tag_configure("agent", background="#fff4d6")
    tree.tag_configure("everyday", foreground="#555577")

    bot = ttk.Frame(win, padding=10)
    bot.pack(fill="x")
    status = tk.StringVar()
    ttk.Label(bot, textvariable=status).pack(side="left", fill="x", expand=True)
    ttk.Label(win, padding=(10, 0, 10, 8), foreground="#555", text=L["legend"]).pack(fill="x")
    data, shown, order = {"rows": []}, {}, {"col": None, "rev": False}

    def is_empty(r):
        return not r["services"] and not r["email"] and not r["open"] and not r["note"]

    def render(*_):
        term, o, s = q.get().strip().lower(), own.get(), svc.get()
        skey = next((x[0] for x in S.SERVICES if x[1] == s), None)
        tree.delete(*tree.get_children())
        shown.clear()
        rows, c = data["rows"], order["col"]
        if c is None:   # default: open first -> most logins -> by owner
            rows = sorted(rows, key=lambda r: (not r["open"], -len(r["services"]), r["owner"] == "?", r["owner"], (r["email"] or "~" + r["name"]).lower()))
        else:
            rows = sorted(rows, key=lambda r: (str(r.get(c) if c not in S.SVC else (c not in r["services"])).lower(), r["name"].lower()), reverse=order["rev"])
        for r in rows:
            if term and term not in f"{r['name']} {r['email']} {r['key']} {r['note']}".lower():
                continue
            if o != L["all"] and r["owner"] != o:
                continue
            if skey and skey not in r["services"]:
                continue
            if s == L["none"] and r["services"]:
                continue
            if only_open.get() and not r["open"]:
                continue
            if hide_empty.get() and is_empty(r) and not term:
                continue
            by = L["human"] if r["by"] == "human" else (L["everyday_stale" if r.get("stale") else "everyday"] if r["by"] == "everyday" else r["by"])
            vals = [r["email"] or f"({r['name']} - {L['no_email']})", r["name"] if r["name"] != r["email"] else "", r["owner"],
                    L["open"] if r["open"] else L["closed"], by]
            vals += ["✓" if k in r["services"] else "" for k in S.SVC] + [r["note"]]
            tag = ("agent",) if r.get("agent") else (("open",) if r["open"] else (("everyday",) if r.get("everyday") else ()))
            shown[tree.insert("", "end", values=vals, tags=tag)] = r
        status.set(L["status"].format(shown=len(shown), total=len(data["rows"]), open=sum(r["open"] for r in data["rows"]), ts=data.get("ts", "")))

    def sort_by(c):
        order["rev"] = not order["rev"] if order["col"] == c else False
        order["col"] = c
        render()

    def refresh(*_):
        if demo:
            data.update(rows=DEMO, ts=time.strftime("%H:%M:%S"))
            render()
            return
        status.set(L["scanning"])

        def work():
            try:
                rows = S.scan()
                win.after(0, lambda: (data.update(rows=rows, ts=time.strftime("%H:%M:%S")), render()))
            except Exception as e:
                S.log(traceback.format_exc())
                win.after(0, lambda: status.set(L["scan_err"].format(e=e)))
        threading.Thread(target=work, daemon=True).start()

    def cur():
        s = tree.selection()
        return shown.get(s[0]) if s else None

    def need(f):
        def g(*a):
            r = cur()
            if not r:
                status.set(L["pick_row"])
                return
            try:
                f(r)
            except Exception as e:
                S.log(traceback.format_exc())
                messagebox.showerror(L["err"], str(e))
        return g

    def do_open(r, url=None):
        core.open_url(r["key"], url)
        status.set(L["opened"].format(name=r["email"] or r["name"], port=r["port"] or "-"))
        win.after(4000, refresh)

    def do_login(r, key):
        do_open(r, S.SVC[key][4].format(email=r["email"] if "@" in r["email"] else ""))

    def do_close(r):
        if not r["open"]:
            status.set(L["already_closed"])
            return
        if r.get("agent") and not messagebox.askyesno(L["agent_busy"], L["agent_busy_q"].format(by=r["by"])):
            return
        core.close_profile(r)
        status.set(L["closed_msg"].format(name=r["email"] or r["name"]))
        win.after(1500, refresh)

    def do_edit(r):
        o = simpledialog.askstring(L["owner"], L["q_owner"].format(name=r["email"] or r["name"], owners="/".join(CFG.owners)), initialvalue=r["owner"], parent=win)
        if o is None:
            return
        n = simpledialog.askstring(L["c_note"], L["q_note"], initialvalue=r["note"], parent=win)
        e = simpledialog.askstring("Email", L["q_email"], initialvalue=r["email"], parent=win)
        S.set_meta(r["key"], owner=o.strip(), note=(n or "").strip(), email=(e or "").strip())
        refresh()

    def do_detail(r):
        s = "\n".join(f"  {S.SVC[k][1]}: {L['d_exp']} {v}" for k, v in r["services"].items()) or L["d_none"]
        messagebox.showinfo(r["email"] or r["name"],
                            f"{L['d_old']}: {r['name']}\nEmail: {r['email']}\n{L['d_chrome']}: {', '.join(r['chrome_login']) or '-'}\n"
                            f"{L['d_port']}: {r['port']}\n{L['d_dir']}: {r['dir']}\n{L['owner']}: {r['owner']}\n\n{L['d_saved']}:\n{s}")

    def do_new():
        e = simpledialog.askstring(L["b_new"], L["q_new"], parent=win)
        if not e:
            return
        o = simpledialog.askstring(L["owner"], L["q_owner"].format(name=e, owners="/".join(CFG.owners)), initialvalue=S.guess_owner(e, ""), parent=win) or "?"
        r = core.new_profile(e.strip(), e.strip())
        S.set_meta(r["key"], owner=o.strip(), email=e.strip())
        core.start(r["key"], "https://accounts.google.com/AddSession?Email=" + e.strip())
        status.set(L["new_done"].format(key=r["key"]))
        win.after(4000, refresh)

    menu = tk.Menu(win, tearoff=0)
    menu.add_command(label=L["m_open"], command=need(do_open))
    sub = tk.Menu(menu, tearoff=0)
    for k, lab, *_ in S.SERVICES:
        sub.add_command(label=L["m_relogin_x"].format(svc=lab), command=need(lambda r, k=k: do_login(r, k)))
    menu.add_cascade(label=L["m_relogin"], menu=sub)
    menu.add_command(label=L["m_detail"], command=need(do_detail))
    menu.add_command(label=L["m_edit"], command=need(do_edit))
    menu.add_separator()
    menu.add_command(label=L["m_close"], command=need(do_close))
    menu.add_command(label=L["m_folder"], command=need(lambda r: os.startfile(r["dir"])))

    def popup(e):
        iid = tree.identify_row(e.y)
        if iid:
            tree.selection_set(iid)
            menu.tk_popup(e.x_root, e.y_root)

    tree.bind("<Button-3>", popup)
    tree.bind("<Double-1>", need(do_open))
    tree.bind("<Return>", need(do_open))
    for t, f in ((L["b_refresh"], refresh), (L["b_new"], do_new), (L["b_edit"], need(do_edit)), (L["b_close"], need(do_close)),
                 (L["b_google"], need(lambda r: do_login(r, "google"))), (L["b_open"], need(do_open))):
        ttk.Button(bot, text=t, command=f).pack(side="right", padx=(6, 0))
    for v in (q, own, svc, only_open, hide_empty):
        v.trace_add("write", render)

    old = S.cached()
    if old.get("rows") and not demo:
        data.update(rows=old["rows"], ts=old.get("scanned", "")[-8:] + " " + L["old"])
        render()
    ent.focus_set()

    if screenshot_dir:   # python -m chrome_profile_hub --screenshot <folder> [--demo]
        from PIL import ImageGrab
        if demo:
            refresh()
        else:
            data.update(rows=S.scan(), ts=time.strftime("%H:%M:%S"))
            render()
        box = lambda: (win.winfo_rootx(), win.winfo_rooty(), win.winfo_rootx() + win.winfo_width(), win.winfo_rooty() + win.winfo_height())

        def shot(name):
            win.update()
            win.lift()
            win.attributes("-topmost", True)
            time.sleep(0.8)
            win.update()
            ImageGrab.grab(box()).save(os.path.join(screenshot_dir, name))
        shot("1_table.png")
        svc.set("Google")
        shot("2_filter_service.png")
        svc.set(L["any"])
        own.set(CFG.owners[0])
        shot("3_filter_owner.png")
        win.destroy()
        return

    refresh()

    def periodic():
        refresh()
        win.after(60000, periodic)
    win.after(60000, periodic)
    win.mainloop()
