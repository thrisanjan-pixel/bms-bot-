import os
import re
import json
import time
import datetime
import random
import string
import asyncio
import traceback
from curl_cffi.requests import AsyncSession

# ──────────────────────────────────────────────────────────
#  CONFIG — Direct credential engine defaults
# ──────────────────────────────────────────────────────────
BOT_TOKEN       = "8640561400:AAGoFl81jL6hxhEOVtrfAXpKu3mexjVT16g"
CHAT_ID         = "410880894"

EMAIL_ENABLED   = True
RESEND_API_KEY  = "re_caz97Ucb_FU7nSQuHaaPF9a7GxrGPqSfV"
EMAIL_FROM      = "onboarding@resend.dev"
EMAIL_TO        = "thrisanjan@gmail.com"
# ──────────────────────────────────────────────────────────

CITY_CODE  = "HYD"
BASE_CHECK_INTERVAL = 45  

MOVIES = [
    {
        "name": "Spider-Man: Brand New Day",
        "default_code": "ET00502600",
        "slug": "spider-man-brand-new-day",
        "start_date": "20260730",  
        "days_to_track": 3         
    },
    {
        "name": "Supergirl",
        "default_code": "ET00501636",      
        "slug": "supergirl",
        "start_date": "20260626",  
        "days_to_track": 3         
    },
    {
        "name": "The Odyssey",
        "default_code": "ET00452034",
        "slug": "the-odyssey",
        "start_date": "20260717",  
        "days_to_track": 3         
    }
]

STATE_DIR  = os.environ.get("STATE_DIR", "/data" if os.path.isdir("/data") else ".")
STATE_FILE = os.path.join(STATE_DIR, "known_theaters.json")

TOTAL_SWEEPS    = 0
LAST_USED_PROXY = "Determining status on next sweep..."

HEADER_CONFIGS = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "sec-ch-ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
        "sec-ch-ua-platform": '"Windows"'
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "sec-ch-ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
        "sec-ch-ua-platform": '"macOS"'
    }
]


def log(msg: str):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def get_dates_to_track(movie: dict) -> list:
    start_str = movie["start_date"]
    days = movie.get("days_to_track", 3)
    start_dt = datetime.datetime.strptime(start_str, "%Y%m%d")
    today_now = datetime.datetime.now()
    today_dt = datetime.datetime(today_now.year, today_now.month, today_now.day)
    effective_start = max(start_dt, today_dt)
    return [(effective_start + datetime.timedelta(days=i)).strftime("%Y%m%d") for i in range(days)]


def get_urls(movie: dict, date: str, active_code: str) -> tuple:
    slug = movie["slug"]
    page_url = f"https://in.bookmyshow.com/movies/hyderabad/{slug}/buytickets/{active_code}/{date}"
    info_page_url = f"https://in.bookmyshow.com/movies/hyderabad/{slug}/{active_code}"
    api_url = (
        f"https://in.bookmyshow.com/api/movies-data/showtimes-by-event"
        f"?appCode=MOBAND2&appVersion=14.3.4&language=en"
        f"&eventCode={active_code}&regionCode={CITY_CODE}&subRegion={CITY_CODE}"
        f"&bmsId=1.21.69&token=67x1xa33b4x422b361ba&dateCode={date}&availability=1"
    )
    return page_url, info_page_url, api_url


# ─── 🛠️ UPGRADED ADVANCED PROXIMITY DISCOVERY SCANNER ────────────────────
async def discover_event_code(session: AsyncSession, city_slug: str, slug: str, fallback_code: str) -> str:
    """Scans full page source block matrices to locate event keys near target slugs."""
    url = f"https://in.bookmyshow.com/{city_slug.lower()}/movies"
    cfg = random.choice(HEADER_CONFIGS)
    headers = {
        "User-Agent": cfg["User-Agent"],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://in.bookmyshow.com/",
    }
    try:
        resp = await session.get(url, headers=headers, timeout=8)
        if resp.status_code == 200:
            text = resp.text
            slug_idx = text.lower().find(slug.lower())
            
            # If slug is present anywhere (including JSON blocks), parse the surrounding window zone
            if slug_idx != -1:
                search_window = text[max(0, slug_idx - 300):min(len(text), slug_idx + 1500)]
                et_match = re.search(r'(ET[0-9]+)', search_window)
                if et_match:
                    detected_code = et_match.group(1).upper()
                    return detected_code
    except Exception:
        pass
    return fallback_code 
# ──────────────────────────────────────────────────────────────────────────


def get_phone_tunnel_url() -> str:
    return "http://rpsfahqzwb.a.pinggy.link:24335"

def get_residential_proxy_url() -> str:
    chars = string.ascii_letters + string.digits
    rand_session = "".join(random.choice(chars) for _ in range(4))
    return f"http://ing0dcn3bdw16f5-zone-resi-region-IN-st--city--session-{rand_session}-sessionTime-10:hK8YUQQ@southasia.a1proxy.com:15128"


async def fetch_with_proxy(phone_session: AsyncSession, resi_session: AsyncSession, api_url: str, page_url: str, proxy_type: str) -> tuple:
    global LAST_USED_PROXY
    session = phone_session if proxy_type == "PHONE_TUNNEL" else resi_session
    cfg = random.choice(HEADER_CONFIGS)
    
    api_headers = {
        "x-bms-id": "IN-HYD",
        "x-region-code": CITY_CODE,
        "x-region-slug": "hyderabad",
        "Accept": "application/json, text/plain, */*",
        "Referer": page_url,
        "Origin": "https://in.bookmyshow.com",
        "User-Agent": cfg["User-Agent"],
        "sec-ch-ua": cfg["sec-ch-ua"],
        "sec-ch-ua-platform": cfg["sec-ch-ua-platform"],
    }
    
    try:
        resp = await session.get(api_url, headers=api_headers, timeout=7)
        status, theaters = _parse_api_response(resp)
        if status == "OK":
            log(f"   [{proxy_type}] Routing breakthrough confirmed — Response: HTTP 200")
            LAST_USED_PROXY = "🟢 Proxy 1: Phone Tunnel (Pinggy Data)" if proxy_type == "PHONE_TUNNEL" else "🔵 Proxy 2: Residential Backup (A1Proxy)"
        elif status == "BLOCKED":
            log(f"   ⚠️ [{proxy_type}] Gateway rate-limited or blocked — Response: HTTP {resp.status_code}")
        elif status == "NOT_LIVE":
            LAST_USED_PROXY = "🟢 Proxy 1: Phone Tunnel (Pinggy Data)" if proxy_type == "PHONE_TUNNEL" else "🔵 Proxy 2: Residential Backup (A1Proxy)"
            
        return status, theaters
    except Exception as e:
        log(f"   ❌ [{proxy_type}] Transport gateway error: {e}")
        return "ERROR", set()


async def send_telegram(message: str) -> bool:
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        async with AsyncSession(impersonate="chrome110") as session:
            resp = await session.post(api_url, json=payload, timeout=10)
            return resp.status_code == 200
    except Exception as e:
        log(f"❌ Telegram transmission failure: {e}")
        return False


async def telegram_listener():
    global LAST_USED_PROXY, TOTAL_SWEEPS
    offset = 0
    log("📬 Telegram Status Monitor Initialized. Standing by for commands...")
    
    async with AsyncSession(impersonate="chrome110") as session:
        while True:
            try:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=5"
                resp = await session.get(url, timeout=10)
                
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("ok") and data.get("result"):
                        for update in data["result"]:
                            offset = update["update_id"] + 1
                            message = update.get("message")
                            if not message:
                                continue
                            
                            sender_chat_id = str(message.get("chat", {}).get("id"))
                            text = message.get("text", "").strip().lower()
                            
                            if sender_chat_id == str(CHAT_ID):
                                if text in ["alive", "status", "/status", "ping", "proxy"]:
                                    log(f"📥 Received live health request from user: '{text}'")
                                    time_stamp = datetime.datetime.now().strftime("%I:%M %p")
                                    reply_msg = (
                                        f"❤️ <b>🤖 SERVER CLUSTER HEALTH STATUS</b>\n\n"
                                        f"• ⏱️ <b>Ping Time:</b> {time_stamp}\n"
                                        f"• 🔄 <b>Total Sweeps:</b> {TOTAL_SWEEPS} loops\n"
                                        f"• 🔌 <b>Active Channel:</b> {LAST_USED_PROXY}\n\n"
                                        f"🍿 <i>Status: Cloud engine active and scanning the matrix grids.</i>"
                                    )
                                    await send_telegram(reply_msg)
            except Exception:
                pass
            await asyncio.sleep(2)


async def send_email(subject: str, html_body: str) -> bool:
    if not EMAIL_ENABLED:
        return False
    try:
        async with AsyncSession(impersonate="chrome110") as session:
            resp = await session.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
                json={"from": f"BMS Bot <{EMAIL_FROM}>", "to": [EMAIL_TO], "subject": subject, "html": html_body},
                timeout=15,
            )
            return resp.status_code in (200, 201)
    except Exception as e:
        log(f"❌ Email transport system error: {e}")
        return False


async def notify(telegram_html: str, email_subject: str = None) -> None:
    await send_telegram(telegram_html)
    if EMAIL_ENABLED:
        subject = email_subject or "🎬 BMS Bot Alert"
        await send_email(subject, telegram_html.replace("\n", "<br>"))


def is_state_key_missing(event_code: str, date: str) -> bool:
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                return f"{event_code}##{date}" not in json.load(f)
    except Exception:
        pass
    return True


def load_known_theaters(event_code: str, date: str) -> set:
    state_key = f"{event_code}##{date}"
    try:
        with open(STATE_FILE, "r") as f:
            return set(json.load(f).get(state_key, []))
    except Exception:
        return set()


def save_known_theaters(event_code: str, date: str, theaters: set) -> None:
    data = {}
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
    except Exception:
        pass
    data[f"{event_code}##{date}"] = sorted(list(theaters))
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        log(f"⚠️ Failed to save baseline state file: {e}")


def _parse_api_response(resp) -> tuple:
    if resp.status_code in (403, 429):
        return "BLOCKED", set()
    if resp.status_code != 200:
        return "ERROR", set()
    try:
        data = resp.json()
    except Exception:
        return "ERROR", set()

    cinemas = data.get("ShowDetails") or data.get("cinemas") or data.get("BookMyShow", {}).get("arrEvents") or []
    if isinstance(cinemas, dict):
        flattened = []
        for v in cinemas.values():
            if isinstance(v, list): flattened.extend(v)
            elif isinstance(v, dict):
                for vv in v.values():
                    if isinstance(vv, list): flattened.extend(vv)
        cinemas = flattened

    names = set()
    for entry in cinemas:
        if not isinstance(entry, dict): continue
        venues = entry.get("Venues") or entry.get("venues") or [entry]
        for v in venues:
            if not isinstance(v, dict): continue
            vname = v.get("VenueName") or v.get("venueName") or v.get("CinemaName") or v.get("name")
            if not vname: continue
            
            show_times = v.get("ShowTimes") or v.get("showtimes") or v.get("Session") or v.get("shows") or []
            if show_times:
                names.add(vname.strip())
    
    if names:
        return "OK", names
    return "NOT_LIVE", set()


async def get_current_theaters(phone_session: AsyncSession, resi_session: AsyncSession, page_url: str, api_url: str) -> tuple:
    log("  ↳ Routing through Primary Phone Tunnel...")
    status, theaters = await fetch_with_proxy(phone_session, resi_session, api_url, page_url, "PHONE_TUNNEL")
    if status in ("OK", "NOT_LIVE"):
        return status, theaters

    log("  ↳ Primary phone tunnel down. Routing to Hardcoded Residential Backup (A1Proxy)...")
    return await fetch_with_proxy(phone_session, resi_session, api_url, page_url, "RESIDENTIAL")


async def process_movie_date(phone_session: AsyncSession, resi_session: AsyncSession, semaphore: asyncio.Semaphore, movie: dict, target_date: str, check_count: int, active_code: str) -> bool:
    async with semaphore:
        await asyncio.sleep(random.uniform(0.2, 1.0))
        page_url, _, api_url = get_urls(movie, target_date, active_code)
        human_date = datetime.datetime.strptime(target_date, "%Y%m%d").strftime("%B %d, %Y")
        log(f"   ↳ Auditing Layout Grid: {target_date} ({human_date}) for {movie['name']} [Code: {active_code}]")
        
        is_first_run = is_state_key_missing(active_code, target_date)
        known_theaters = load_known_theaters(active_code, target_date)
        status, current_theaters = await get_current_theaters(phone_session, resi_session, page_url, api_url)

        if status == "OK":
            new_theaters = current_theaters - known_theaters
            if new_theaters:
                # 🛠️ FORCED INITIAL ALERT: If tickets are already live when the server fires up, push a summary instead of staying silent!
                if is_first_run and check_count == 1:
                    theater_list = "\n".join(f"• {t}" for t in sorted(current_theaters))
                    alert_msg = (
                        f"📥 <b>BMS CLUSTER ONLINE — CURRENT OPEN TRACKS FOUND!</b>\n\n"
                        f"🎬 <b>{movie['name']}</b>\n"
                        f"📅 Date: <b>{human_date}</b>\n\n"
                        f"<b>Active Venues Detected:</b>\n{theater_list}\n\n"
                        f"👉 <a href='{page_url}'>SECURE SEATS NOW →</a>"
                    )
                    await notify(alert_msg, email_subject=f"📥 TRACKER INITIALIZED: {movie['name'].upper()} LIVE")
                else:
                    theater_list = "\n".join(f"• {t}" for t in sorted(new_theaters))
                    alert_msg = (
                        f"🚨🎬 <b>NEW CHANNELS OPENED ON {target_date}!</b>\n\n"
                        f"🎬 <b>{movie['name']}</b>\n"
                        f"📅 Date: <b>{human_date}</b>\n\n"
                        f"<b>New Channels:</b>\n{theater_list}\n\n"
                        f"👉 <a href='{page_url}'>SECURE SEATS NOW →</a>"
                    )
                    await notify(alert_msg, email_subject=f"🚨 NEW SEATS OPEN FOR {movie['name'].upper()}!")
                save_known_theaters(active_code, target_date, known_theaters | current_theaters)
            else:
                log(f"      ↳ Balanced matrix state for {movie['name']} on {target_date}. No structural changes.")
            return True
        elif status == "NOT_LIVE":
            log(f"      ↳ Matrix verified for {movie['name']} on {target_date}: clear structure, zero active listings.")
            return True
        else:
            log(f"      ❌ Absolute check failure logged for {movie['name']} on {target_date}.")
            return False


async def main_async():
    global TOTAL_SWEEPS
    async with AsyncSession(impersonate="chrome110", proxy=get_phone_tunnel_url()) as phone_session, \
               AsyncSession(impersonate="chrome110", proxy=get_residential_proxy_url()) as resi_session:
               
        log("=" * 60)
        log(f"🎬 Optimized Code-Independent Proxy Monitor Active")
        log(f"   Dynamic Auto-Discovery Mapping Modules Online.")
        log("=" * 60)

        asyncio.create_task(telegram_listener())

        check_count = 0
        consecutive_failures = 0
        
        while True:
            check_count += 1
            TOTAL_SWEEPS = check_count
            log(f"Matrix Sweep Check #{check_count} starting...")
            
            resolved_codes = {}
            for movie in MOVIES:
                slug = movie["slug"]
                resolved_codes[slug] = await discover_event_code(phone_session, "hyderabad", slug, movie["default_code"])
                if resolved_codes[slug] != movie["default_code"]:
                    log(f"   🎯 Auto-Discovery: Code shift detected for {movie['name']} -> {resolved_codes[slug]}")
            
            semaphore = asyncio.Semaphore(1)  
            tasks = []
            for movie in MOVIES:
                active_code = resolved_codes[movie["slug"]]
                for target_date in get_dates_to_track(movie):
                    tasks.append(process_movie_date(phone_session, resi_session, semaphore, movie, target_date, check_count, active_code))
            
            results = await asyncio.gather(*tasks)
            
            if results and all(res is False for res in results):
                consecutive_failures += 1
                log(f"⚠️ Entire matrix sweep missed. Consecutive failure counter: {consecutive_failures}/5")
                
                if consecutive_failures >= 5:
                    fail_alert = (
                        f"⚠️ <b>CRITICAL: BMS TRACKER CLUSTER DOWN!</b>\n\n"
                        f"The daemon has dropped 5 tracking passes consecutively.\n"
                        f"Both internal mobile and residential clusters are reporting authentication blocks.\n\n"
                        f"💡 <b>Action Required:</b> Data allowances on proxy platforms may be spent."
                    )
                    await notify(fail_alert, email_subject="⚠️ CRITICAL ERROR: BMS Tracker Failing")
                    consecutive_failures = 0  
            else:
                consecutive_failures = 0  
                
            await asyncio.sleep(BASE_CHECK_INTERVAL + random.randint(5, 15))


if __name__ == "__main__":
    try:
        asyncio.run(main_async())
    except Exception as e:
        print(f"Daemon Exit: {e}")
