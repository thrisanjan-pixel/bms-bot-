# 🎬 BookMyShow New-Theater Notifier — Spider-Man: Brand New Day, Hyderabad

A Railway worker that polls BookMyShow's booking page for *Spider-Man: Brand New Day* (Hyderabad, show date 30 Jul 2026) every 60 seconds and sends a **Telegram alert whenever a new theater starts selling tickets** — not just on first launch, but every time the venue list grows.

---

## ⚡ Quick Deploy

### Step 1 — Telegram Bot
Already configured with the token/chat ID baked into the script (from your previous bot), or override via env vars `BOT_TOKEN` / `CHAT_ID`.

### Step 2 — Deploy to Railway

```bash
npm i -g @railway/cli
railway login
railway init
railway up
```

### Step 3 — (Recommended) Add a Volume for persistence

Without a volume, the bot's "known theaters" list resets every time Railway restarts the worker — meaning you'd get a fresh "new theater" alert for every venue already live, every restart.

In Railway: **Settings → Volumes → Add Volume → Mount path: `/data`**

The bot automatically detects `/data` and stores `known_theaters.json` there.

### Step 4 — Environment Variables (optional overrides)

| Variable | Purpose |
|---|---|
| `BOT_TOKEN` | Telegram bot token |
| `CHAT_ID` | Telegram chat ID |
| `RESEND_API_KEY` | Free email API key (resend.com) — already set by default |
| `EMAIL_TO` | Destination email for alerts |
| `PROXY_TRY_COUNT` | How many free proxies to try per check if direct access is blocked (default 8) |
| `STATE_DIR` | Override the folder for `known_theaters.json` (defaults to `/data` if mounted, else current dir) |

---

## 🔔 What You'll Receive

**On startup:**
> 🤖 BMS Theater Monitor Started
> Movie: Spider-Man: Brand New Day — Hyderabad
> Show date: 20260730
> Tracking 0 known theater(s).

**Whenever a new theater opens bookings:**
> 🚨 NEW THEATER(S) OPENED!
> • AMB Cinemas: Gachibowli
> • PVR: Forum Mall
> 📊 Total theaters now live: 2

This keeps firing every time *additional* theaters get added — so as more cinemas roll out over the following days/weeks, you get pinged each time, not just once.

---

## 🛠 How It Works

1. Hits the BMS `buytickets` page for the event + show date directly.
2. Parses out theater/cinema names via two strategies: known BMS CSS class patterns (`venue-name`, `cinema-name`) and embedded JSON (`venueName` keys in `<script>` tags).
3. Falls back to BMS's internal JSON API directly, then to a pool of free public proxies (via ProxyScrape, no signup or API key needed) if direct access gets blocked. No paid services required anywhere in the chain.
4. Diffs the current theater list against the saved "known" set. Anything new triggers a Telegram alert and gets added to the known set (saved to disk).

---

## 🔧 Local Testing

```bash
pip install -r requirements.txt
export BOT_TOKEN="your_token"
export CHAT_ID="your_chat_id"
python bms_monitor.py
```

Delete `known_theaters.json` to reset and re-trigger alerts for all currently-live theaters (useful for testing the alert format).

---

## ⚠️ Changing the show date

`SHOW_DATE` is hardcoded to `20260730`. If you want to track a different date (or multiple dates), edit that constant near the top of `bms_monitor.py`, or extend the script to loop over several dates — ask if you'd like that added.
