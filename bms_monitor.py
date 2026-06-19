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
#  CONFIG — reads from Railway env vars if set
# ──────────────────────────────────────────────────────────
BOT_TOKEN       = os.environ.get("BOT_TOKEN",       "8640561400:AAGoFl81jL6hxhEOVtrfAXpKu3mexjVT16g")
CHAT_ID         = os.environ.get("CHAT_ID",         "410880894")

EMAIL_ENABLED   = os.environ.get("EMAIL_ENABLED", "true").lower() == "true"
RESEND_API_KEY  = os.environ.get("RESEND_API_KEY", "re_caz97Ucb_FU7nSQuHaaPF9a7GxrGPqSfV")
EMAIL_FROM      = os.environ.get("EMAIL_FROM", "onboarding@resend.dev")
EMAIL_TO        = os.environ.get("EMAIL_TO", "thrisanjan@gmail.com")
# ──────────────────────────────────────────────────────────

CITY_CODE  = "HYD"
BASE_CHECK_INTERVAL = 45  # Pause between complete matrix sweep loops           

MOVIES = [
    {
        "name": "Spider-Man: Brand New Day",
        "code": "ET00502600",
        "slug": "spider-man-brand-new-day",
        "start_date": "20260730",  
        "days_to_track": 3         
    },
    {
        "name": "Supergirl",
        "code": "ET00475569",
        "slug": "supergirl",
        "start_date": "20260626",  
        "days_to_track": 3         
    },
    {
        "name": "The Odyssey",
        "code": "ET00452034",
        "slug": "the-odyssey",
        "start_date": "20260626",  
        "days_to_track": 3         
    }
]

STATE_DIR  = os.environ.get("STATE_DIR", "/data" if os.path.isdir("/data") else ".")
STATE_FILE = os.path.join(STATE_DIR, "known_theaters.json")

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


def get_urls(movie: dict, date: str) -> tuple:
    slug = movie["slug"]
    code = movie["code"]
    page_url = f"https://in.bookmyshow.com/movies/hyderabad/{slug}/buytickets/{code}/{date}"
    info_page_url = f"https://in.bookmyshow.com/movies/hyderabad/{slug}/{code}"
    api_url = (
        f"https://in.bookmyshow.com/api/movies-data/showtimes-by-event"
        f"?appCode=MOBAND2&appVersion=14.3.4&language=en"
        f"&eventCode={code}&regionCode={CITY_CODE}&subRegion={CITY_CODE}"
        f"&bmsId=1.21.69&token=67x1xa33b4x422b361ba&dateCode={date}&availability=1"
    )
    return page_url, info_page_url, api_url


# ─── PROXY GATEWAY GENERATORS ─────────────────────────────────────────────
def get_mobile_proxy_url() -> str:
    """Generates a dynamic 12-char cellular session endpoint"""
    rand_session = "".join(random.choices(string.digits + "abcdef", k=12))
    username = f"on0xutsx1n-corp.mobile.res-country-IN-hold-session-session-{rand_session}"
    return f"http://{username}:SiGyraQjeRR7Y1tG@109.236.82.42:443"

def get_residential_proxy_url() -> str:
    """Generates a dynamic 4-char residential back-up endpoint"""
    rand_session = "".join(random.choices(string.ascii_letters + string.digits, k=4))
    username = f"asdasda-zone-resi-region-IN-st--city--session-{rand_session}-sessionTime-10"
    return f"http://{username}:asdasdasd@southasia.a1proxy.com:15122"
# ──────────────────────────────────────────────────────────────────────────


async def fetch_with_proxy(api_url: str, page_url: str, proxy_type: str) -> tuple:
    """Executes a target request using the chosen premium endpoint configuration"""
    proxy_endpoint = get_mobile_proxy_url() if proxy_type == "MOBILE" else get_residential_proxy_url()
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
        async with AsyncSession(impersonate="chrome110") as session:
            resp = await session.get(
                api_url,
                headers=api_headers,
                proxy=proxy_endpoint,
                timeout=7
            )
            if resp.status_code == 200:
                log(f"  [{proxy_type}] Routing breakthrough confirmed — Response: HTTP 200")
                return _parse_api_response(resp)
            return "ERROR", set()
    except Exception:
        return "ERROR", set()


async def send_telegram(message: str) -> bool:
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        async with AsyncSession(impersonate="chrome110") as session:
            resp = await session.post(api_url, json=payload, timeout=10)
            return resp.status_code == 200
    except Exception:
        return False


async def send_email(subject: str, html_body: str) -> bool:
    if not EMAIL_ENABLED or RESEND_API_KEY == "YOUR_RESEND_API_KEY_HERE":
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
    except Exception:
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
    baselines = {
        "Cinepolis: TNR North City, Suchitra, Hyderabad",
        "PVR Lakeshore PXL 4K Laser ATMOS DTS-X Y Junction",
        "PVR Superplex Inorbit: LUXE, PXL, 4K, 4DX: Cyberabad"
    }
    try:
        with open(STATE_FILE, "r") as f:
            return set(json.load(f).get(state_key, [])) | baselines
    except Exception:
        return baselines


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


async def fetch_theaters_via_api(session: AsyncSession, api_url: str, page_url: str) -> tuple:
    try:
        api_headers = {
            "x-bms-id": "IN-HYD",
            "x-region-code": CITY_CODE,
            "x-region-slug": "hyderabad",
            "Referer": page_url,
        }
        resp = await session.get(api_url, headers=api_headers, timeout=10)
        return _parse_api_response(resp)
    except Exception:
        return "ERROR", set()


async def get_current_theaters(session: AsyncSession, page_url: str, api_url: str) -> tuple:
    # Tier 1: Try raw server connection first
    status, theaters = await fetch_theaters_via_api(session, api_url, page_url)
    if status in ("OK", "NOT_LIVE"):
        return status, theaters

    # Tier 2: Engage Premium Cellular Mobile Gateway
    log("  ↳ Server IP rejected. Engaging Premium Mobile Tunnel...")
    status, theaters = await fetch_with_proxy(api_url, page_url, "MOBILE")
    if status in ("OK", "NOT_LIVE"):
        return status, theaters

    # Tier 3: Engage Premium Residential Backup Gateway
    log("  ↳ Cellular lane flickered. Routing to Premium Residential Backup...")
    return await fetch_with_proxy(api_url, page_url, "RESIDENTIAL")


async def process_movie_date(session: AsyncSession, semaphore: asyncio.Semaphore, movie: dict, target_date: str) -> bool:
    """Returns True if the check succeeded, False if it was an absolute error failure"""
    async with semaphore:
        await asyncio.sleep(random.uniform(0.2, 1.0))
        page_url, _, api_url = get_urls(movie, target_date)
        human_date = datetime.datetime.strptime(target_date, "%Y%m%d").strftime("%B %d, %Y")
        log(f"   ↳ Auditing Layout Grid: {target_date} ({human_date}) for {movie['name']}")
        
        is_first_run = is_state_key_missing(movie["code"], target_date)
        known_theaters = load_known_theaters(movie["code"], target_date)
        status, current_theaters = await get_current_theaters(session, page_url, api_url)

        if status == "OK":
            new_theaters = current_theaters - known_theaters
            if new_theaters:
                if is_first_run:
                    log(f"      📥 [Silent Init] Cached baseline grid snapshot ({len(current_theaters)} nodes) for {movie['name']}.")
                else:
                    # TRIGGER ALERT ON TICKET SEAT OPENINGS
                    theater_list = "\n".join(f"• {t}" for t in sorted(new_theaters))
                    alert_msg = (
                        f"🚨🎬 <b>NEW CHANNELS OPENED ON {target_date}!</b>\n\n"
                        f"🎬 <b>{movie['name']}</b>\n"
                        f"📅 Date: <b>{human_date}</b>\n\n"
                        f"<b>New Channels:</b>\n{theater_list}\n\n"
                        f"👉 <a href='{page_url}'>SECURE SEATS NOW →</a>"
                    )
                    await notify(alert_msg, email_subject=f"🚨 NEW SEATS OPEN FOR {movie['name'].upper()}!")
                save_known_theaters(movie["code"], target_date, known_theaters | current_theaters)
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
    session = AsyncSession(impersonate="chrome110")
    log("=" * 60)
    log(f"🎬 Dual-Premium Failover BookMyShow Monitor Active")
    log(f"   Multi-tier Mobile and Residential backup cluster online.")
    log("=" * 60)

    # Startup verification email alert block with direct embedded links
    for movie in MOVIES:
        movie_name = movie["name"]
        dates_to_track = get_dates_to_track(movie)
        page_url, _, _ = get_urls(movie, dates_to_track[0])
        readable_dates = ", ".join([datetime.datetime.strptime(d, "%Y%m%d").strftime("%b %d") for d in dates_to_track])
        
        startup_alert = (
            f"🚀 <b>BMS Dual-Premium Monitor Online!</b>\n\n"
            f"🎬 <b>Movie:</b> {movie_name}\n"
            f"📅 <b>Horizon Map:</b> {readable_dates}\n\n"
            f"🛡️ Multi-tier failover cluster engaged and routing cleanly.\n\n"
            f"👉 <a href='{page_url}'>OPEN BOOKING PAGE →</a>"
        )
        await notify(startup_alert, email_subject=f"🚀 BMS Failover Monitor Online: {movie_name}")

    check_count = 0
    consecutive_failures = 0
    
    while True:
        check_count += 1
        log(f"Matrix Sweep Check #{check_count} starting...")
        
        semaphore = asyncio.Semaphore(1)  
        tasks = []
        for movie in MOVIES:
            for target_date in get_dates_to_track(movie):
                tasks.append(process_movie_date(session, semaphore, movie, target_date))
        
        results = await asyncio.gather(*tasks)
        
        # Check if all dates in the matrix sweep failed completely
        if results and all(res is False for res in results):
            consecutive_failures += 1
            log(f"⚠️ Entire matrix sweep missed. Consecutive failure counter: {consecutive_failures}/5")
            
            # TRIGGER EMAIL WHEN BOT FAILS (5 consecutive full failures)
            if consecutive_failures >= 5:
                fail_alert = (
                    f"⚠️ <b>CRITICAL: BMS MONITOR DAEMON FALLING BACK!</b>\n\n"
                    f"The tracker has failed 5 complete sweeps in a row.\n"
                    f"Both Premium Mobile and Residential tunnels are currently down.\n\n"
                    f"💡 <b>Action Required:</b> Please log into your proxy panel dashboards and check if your 200MB trial traffic caps have been exhausted."
                )
                await notify(fail_alert, email_subject="⚠️ CRITICAL ERROR: BMS Tracker Daemon Failing")
                consecutive_failures = 0  
        else:
            consecutive_failures = 0  
            
        await asyncio.sleep(BASE_CHECK_INTERVAL + random.randint(5, 15))


if __name__ == "__main__":
    try:
        asyncio.run(main_async())
    except Exception as e:
        print(f"Daemon Exit: {e}")
