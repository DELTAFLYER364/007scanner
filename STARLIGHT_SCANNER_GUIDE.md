# StarLight Scanner V3 - User Guide
### Created by DELTASTB

---

## What is StarLight Scanner?

StarLight Scanner V3 is a desktop IPTV scanning tool that checks Xtream Codes and Stalker portal servers. It features a modern dark UI, high-speed multi-threaded scanning, proxy support, side host discovery, and URLScan integration.

---

## Installation

### Requirements
- Python 3.8 or higher (download from https://www.python.org/downloads/)
- Windows 10/11 (also works on Linux/Mac)

### Quick Start
1. Make sure Python is installed (tick "Add Python to PATH" during install)
2. Double-click **RUN_STARLIGHT.bat**
3. Dependencies install automatically on first run
4. The scanner window opens

### Manual Start
```
pip install requests customtkinter
python starlight_scanner_gui.py
```

---

## Scanner Tabs

### 1. Xtream Scan

This tab scans Xtream Codes servers using host + combo (username:password) combinations.

**How to use:**
1. Add hosts in the "DNS Hosts" box (one per line)
   - Format: `hostname` or `hostname:port`
   - If port is included (e.g. `iptv.example.com:8080`), only that port is scanned
   - If no port, all ports from Settings are tried
2. Add combos in the "Combos" box (one per line)
   - Format: `username:password`
3. Click **START SCAN**

**Buttons:**
- **Add** — adds the host from the entry field to the list
- **Load .txt** — load hosts or combos from a text file
- **Clear** — clears the host list
- **START SCAN** — begins the xtream scan
- **STOP XTREAM** — stops only the xtream scan
- **STOP ALL** — stops all running scans
- **Clear All** — resets everything (stats, hosts, combos, hits, log)

**Tips:**
- Press Enter in the DNS entry field to quickly add a host
- Hosts from URLScan already include the port, so they scan fast (1 port only)

---

### 2. Stalker Scan

This tab scans Stalker/MAG portals by trying random MAC addresses.

**How to use:**
1. Add portal hosts (one per line)
   - Format: `hostname:port` or just `hostname`
2. Set "MACs per host" — how many random MACs to try per host
   - Default: 1000
   - More MACs = more chance of finding active subscriptions
3. Click **START STALKER**

**What it checks:**
- Handshake with portal (gets token)
- Profile info (expiry, max connections)
- Channel counts (Live, VOD, Series)
- Only reports hits with actual content (anti false-positive)

**Current MAC display** shows the MAC being tested in real-time.

---

### 3. Hits

Shows all found results in two tables:
- **XTREAM HITS** — host, port, user, pass, expiry, days left, max connections, M3U link
- **STALKER HITS** — host, port, MAC, expiry, channel counts, portal URL

**Actions:**
- **Export All** — save all hits to a .txt file (choose location)
- **Auto-Save** — quick save to `starlight_hits/` folder with timestamp
- **Clear** — clear all hits and reset everything
- **Right-click** any row to copy M3U/Portal URL or Host:Port

---

### 4. URLScan

Search urlscan.io for IPTV servers. This finds publicly indexed Xtream and Stalker panels.

**How to use:**
1. Type a search query or use preset buttons:
   - **Xtream URL** — finds pages with `player_api.php`
   - **Stalker URL** — finds pages with `stalker_portal`
   - **XUI Panel** — finds XUI login panels
   - **All Hashes** — searches known IPTV panel file hashes
2. Click **Search** (or press Enter)
3. Results show TYPE, URL, Title, IP, and Date

**TYPE column:**
- XTREAM — detected as Xtream Codes server
- STALKER — detected as Stalker portal
- ? — unknown type

**Sending results to scanner:**
- **→ Xtream** — send all results to Xtream hosts
- **→ Stalker** — send all results to Stalker hosts
- **Smart Send** — auto-splits: XTREAM types go to Xtream tab, STALKER types go to Stalker tab, unknowns go to both

**Right-click options:**
- Open in Browser
- Copy URL
- Copy Host:Port
- Add to Xtream Scanner
- Add to Stalker Scanner
- Add to Both Scanners

**Double-click** any row to open the URL in your browser.

**API Key** (optional): Get a free key from urlscan.io for higher rate limits.

---

### 5. Settings

**Threads (1-200):** How many simultaneous connections. Default: 50. Higher = faster but more system load.

**Timeout (seconds):** How long to wait for each request. Default: 5. Lower = faster but may miss slow servers.

**Ports:** Comma-separated list of ports to try when no port is specified in the host. Default covers the most common IPTV ports.

**Telegram Bot Token / Chat ID:** Get notifications when hits are found. Set up a bot via @BotFather on Telegram.

**Side Host Scan:** Toggle on/off. When enabled, after each hit the scanner looks up other domains on the same IP address and adds them to the Xtream hosts list automatically. This finds additional servers to scan without any extra work.

**Proxies:** Paste or load proxy list to rotate IPs during scanning. This prevents rate limiting and IP bans from servers.
- Format: `ip:port` or `http://ip:port` or `socks5://ip:port`
- One proxy per line
- If empty, scans directly without proxy

---

## Stats Bar

The stats bar at the top shows real-time progress:

**Row 1 (Xtream):**
| Stat | Meaning |
|------|---------|
| XT Targets | Total xtream checks to perform |
| XT Scanned | Completed xtream checks |
| XT Hits | Xtream hits found |
| XT Speed | Checks per second |
| Elapsed | Total time running |
| ETA | Estimated time remaining |

**Row 2 (Stalker — appears when stalker scan is active):**
| Stat | Meaning |
|------|---------|
| SK Targets | Total stalker checks |
| SK Scanned | Completed stalker checks |
| SK Hits | Stalker hits found |
| SK Speed | Stalker checks per second |
| Total Hits | Combined hits from both |

---

## Dual Scanning

You can run Xtream and Stalker scans simultaneously:
1. Start an Xtream scan
2. Switch to Stalker tab and start a Stalker scan
3. Both run in parallel with separate stats
4. Stop them independently with STOP XTREAM or STOP STALKER

---

## Output Files

Hits are automatically saved to a `starlight_hits/` folder next to the script:
- `{host}_xtream.txt` — xtream hits per host
- `{host}_stalker.txt` — stalker hits per host
- `{host}_side_hosts.txt` — discovered side hosts
- `hits_{timestamp}_{count}.txt` — manual exports

---

## Tips for Best Results

1. **Use URLScan first** to find fresh targets, then send them to the scanner
2. **Load proxies** if scanning many hosts to avoid IP bans
3. **Keep threads at 50-100** for a good balance of speed and reliability
4. **Include the port** in hosts when known (e.g. `server.com:8080`) to skip testing 12 ports
5. **Side host discovery** can chain — a hit reveals new hosts, which may reveal more hits
6. **Timeout of 5s** works for most servers. Increase to 8-10s for slow/distant servers
7. **Save hits regularly** using Auto-Save in case the app crashes

---

## Troubleshooting

**Scanner says "Not Responding":**
- This happens briefly when loading very large combo lists. Wait a few seconds.

**No hits found:**
- Check your combos are valid (user:pass format)
- Check the hosts are reachable (try opening in browser)
- Try with proxies if servers might be blocking your IP

**URLScan shows "Rate limited":**
- Wait 30-60 seconds and search again
- Add a free API key for higher limits

**Slow scanning:**
- Increase threads in Settings
- Use proxies to avoid rate limiting
- Make sure hosts include ports to skip port scanning

---

## Files to Distribute

To share StarLight Scanner V3 with others, give them:
1. `starlight_scanner_gui.py` — the scanner
2. `RUN_STARLIGHT.bat` — double-click launcher
3. `STARLIGHT_SCANNER_GUIDE.md` — this guide

---

*StarLight Scanner V3 — Created by DELTASTB*
