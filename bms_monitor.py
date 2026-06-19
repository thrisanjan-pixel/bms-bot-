import os
import re
import json
import time
import datetime
import random
import asyncio
import traceback
# Using curl_cffi's AsyncSession for ultra-fast non-blocking requests
from curl_cffi.requests import AsyncSession
from curl_cffi import requests as sync_curl
from bs4 import BeautifulSoup

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

CITY_CODE      = "HYD"
BASE_CHECK_INTERVAL = 45  # Pause between complete matrix sweep loops           

MOVIES = [
    {
        "name": "Spider-Man: Brand New Day",
        "code": "ET00502600",
        "slug": "spider-man-brand-new-day",
        "start_date": "20260730",  
        "days_to_track": 5         
    },
    {
        "name": "Supergirl",
        "code": "ET00475569",
        "slug": "supergirl",
        "start_date": "20260626",  
        "days_to_track": 5         
    }
]

STATE_DIR  = os.environ.get("STATE_DIR", "/data" if os.path.isdir("/data") else ".")
STATE_FILE = os.path.join(STATE_DIR, "known_theaters.json")

# ─── GEO-FENCED INDIAN PROXY SOURCES ──────────────────────────────────────
# All endpoints are strictly geo-fenced to pure HTTP endpoints inside India (country=IN)
PROXY_SOURCES = [
    "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text&protocol=http&timeout=8000&country=IN",
    "https://proxylist.geonode.com/api/proxy-list?country=IN&protocols=http&limit=100&page=1&sort_by=lastChecked&sort_type=desc",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/IN/data.txt"
]
# ──────────────────────────────────────────────────────────────────────────

PROXY_TRY_COUNT = int(os.environ.get("PROXY_TRY_COUNT", "25"))  
_proxy_cache = {"list": [], "fetched_at": 0}


def get_dates_to_track(movie: dict) -> list:
    start_str = movie["start_date"]
    days = movie.get("days_to_track", 5)
    
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


# ─── MULTI-SOURCE INDIAN EXTRACTOR WORKER ─────────────────────────────────
async def _scrape_single_source(session: AsyncSession, url: str) -> list:
    try:
        resp = await session.get(url, timeout=12)
        if resp.status_code == 200:
            # Check if source uses Geonode API structured JSON layouts
            if "geonode.com" in url:
                try:
                    nodes = []
                    data = resp.json()
                    for item in data.get("data", []):
                        ip = item.get("ip")
                        port = item.get("port")
                        if ip and port:
                            nodes.append(f"{ip}:{port}")
                    return nodes
                except Exception:
                    pass
            
            # Universal RegEx fallback scanner for raw flat text streams
            found = re.findall(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+\b", resp.text)
            return found
    except Exception:
        pass
    return []


async def get_free_proxies(force_refresh: bool = False) -> list:
    now = time.time()
    if not force_refresh and _proxy_cache["list"] and (now - _proxy_cache["fetched_at"] < 300):
        return _proxy_cache["list"]
    
    try:
        async with AsyncSession(impersonate="chrome110") as session:
            # Gather fresh Indian proxies from all endpoints concurrently
            tasks = [_scrape_single_source(session, url) for url in PROXY_SOURCES]
            results = await asyncio.gather(*tasks)
            
            # Combine and deduplicate
            master_set = set()
            for proxy_list in results:
                master_set.update(proxy_list)
                
            proxy_strs = list(master_set)
            random.shuffle(proxy_strs)
            
            _proxy_cache["list"] = proxy_strs
            _proxy_cache["fetched_at"] = now
            log(f"  [AGGREGATOR] Geo-Fenced India Pool Refreshed: {len(proxy_strs)} clean nodes active.")
            return proxy_strs
    except Exception as e:
        log(f"  [AGGREGATOR] Exception fetching list: {e}")
        return _proxy_cache["list"]
# ──────────────────────────────────────────────────────────────────────────


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
    },
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
        "sec-ch-ua": '"Microsoft Edge";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
        "sec-ch-ua-platform": '"Windows"'
    }
]

LIVE_SIGNALS = ["book tickets", "buyticketssection", "/buytickets/", "book-tickets-btn", "quickbook"]
NOT_LIVE_SIGNALS = [
    "no shows available", "no movies", "coming soon", "tickets not available", 
    "currently unavailable", "no shows", "shows not available", "be the first to know",
    "notify me", "notifyme", "mark interested", "i'm interested", "im interested",
    "know when bookings open", "bookings open", "releasing on", "releasing soon"
]


def log(msg: str):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


async def send_telegram(message: str) -> bool:
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        async with AsyncSession(impersonate="chrome110") as session:
            resp = await session.post(api_url, json=payload, timeout=10)
            data = resp.json()
            if resp.status_code == 200 and data.get("ok"):
                log("✅ Telegram message sent!")
                return True
            else:
                log(f"❌ Telegram error {resp.status_code}: {data.get('description', resp.text)}")
                return False
    except Exception as e:
        log(f"❌ Telegram exception: {e}")
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
            log(f"📩 Resend Email System Response: HTTP {resp.status_code} — {resp.text}")
            return resp.status_code in (200, 201)
    except Exception as e:
        log(f"❌ Email exception: {e}")
        return False


async def notify(telegram_html: str, email_subject: str = None) -> None:
    await send_telegram(telegram_html)
    if EMAIL_ENABLED:
        subject = email_subject or "🎬 BMS Bot Alert"
        await send_email(subject, telegram_html.replace("\n", "<br>"))


def is_state_key_missing(event_code: str, date: str) -> bool:
    state_key = f"{event_code}##{date}"
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                return state_key not in data
    except Exception:
        pass
    return True


def load_known_theaters(event_code: str, date: str) -> set:
    state_key = f"{event_code}##{date}"
    established_baselines = {
        "Cinepolis: TNR North City, Suchitra, Hyderabad",
        "PVR Lakeshore PXL 4K Laser ATMOS DTS-X Y Junction",
        "PVR Superplex Inorbit: LUXE, PXL, 4K, 4DX: Cyberabad"
    }
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
            file_theaters = set(data.get(state_key, []))
            return file_theaters | established_baselines
    except (FileNotFoundError, json.JSONDecodeError):
        return established_baselines


def save_known_theaters(event_code: str, date: str, theaters: set) -> None:
    state_key = f"{event_code}##{date}"
    data = {}
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
    except Exception:
        data = {}
        
    data[state_key] = sorted(list(theaters))
    
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        log(f"⚠️ Failed to save state snapshot file: {e}")


async def create_warmed_session() -> AsyncSession:
    session = AsyncSession(impersonate="chrome110")
    cfg = random.choice(HEADER_CONFIGS)
    
    session.headers.update({
        "User-Agent": cfg["User-Agent"],
        "sec-ch-ua": cfg["sec-ch-ua"],
        "sec-ch-ua-platform": cfg["sec-ch-ua-platform"],
        "sec-ch-ua-mobile": "?0",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    })
    try:
        await session.get("https://in.bookmyshow.com/", timeout=12)
        log("  ↳ Session credentials masked & authenticated ✓")
    except Exception as e:
        log(f"  ↳ Session signature mismatch warning: {e}")
    return session


def extract_theaters_from_html(html: str) -> set:
    soup = BeautifulSoup(html, "html.parser")
    names = set()
    selectors = [
        {"class_": re.compile(r"venue[-_]?name", re.I)},
        {"class_": re.compile(r"cinema[-_]?name", re.I)},
        {"class_": re.compile(r"__venue-name", re.I)},
    ]
    for sel in selectors:
        for tag in soup.find_all(attrs=sel):
            text = tag.get_text(strip=True)
            if text and len(text) < 80:
                names.add(text)
    return names


async def fetch_page(session: AsyncSession, page_url: str) -> tuple:
    try:
        session.headers["Referer"] = "https://in.bookmyshow.com/"
        resp = await session.get(page_url, timeout=12)
        log(f"  [DIRECT-HTML] HTTP {resp.status_code} — {len(resp.text)} bytes")

        if resp.status_code in (403, 429):
            return "BLOCKED", None
        if resp.status_code != 200:
            return "ERROR", None

        text_lower = BeautifulSoup(resp.text, "html.parser").get_text(" ").lower()
        for signal in NOT_LIVE_SIGNALS:
            if signal in text_lower:
                return "NOT_LIVE", None

        return "OK", resp.text
    except Exception as e:
        log(f"  [DIRECT-HTML] Exception: {e}")
        return "ERROR", None


def _parse_api_response(resp) -> tuple:
    if resp.status_code in (403, 429):
        return "BLOCKED", set()
    if resp.status_code != 200:
        return "ERROR", set()

    try:
        data = resp.json()
    except Exception:
        return "ERROR", set()

    cinemas = (
        data.get("ShowDetails")
        or data.get("cinemas")
        or data.get("BookMyShow", {}).get("arrEvents")
        or (data if isinstance(data, list) else [])
    )

    if isinstance(cinemas, dict):
        flattened = []
        for v in cinemas.values():
            if isinstance(v, list):
                flattened.extend(v)
            elif isinstance(v, dict):
                for vv in v.values():
                    if isinstance(vv, list):
                        flattened.extend(vv)
        cinemas = flattened

    names = set()

    for entry in cinemas or []:
        if not isinstance(entry, dict):
            continue

        venues = entry.get("Venues") or entry.get("venues")
        if isinstance(venues, list):
            for v in venues:
                if not isinstance(v, dict):
                    continue
                vname = (
                    v.get("VenueName") or v.get("venueName")
                    or v.get("CinemaName") or v.get("cinemaName")
                    or v.get("Name") or v.get("name")
                )
                if not vname:
                    continue
                vname = vname.strip()

                show_times = v.get("ShowTimes") or v.get("showtimes") or v.get("Session") or v.get("shows")
                if isinstance(show_times, list) and len(show_times) > 0:
                    formats_found = []
                    for st in show_times:
                        if not isinstance(st, dict):
                            continue
                        fmt = (
                            st.get("ShowFormat") or st.get("EventDimension")
                            or st.get("ScreenFormat") or st.get("Format")
                        )
                        if fmt and fmt not in formats_found:
                            formats_found.append(fmt.strip())

                    if formats_found:
                        for fmt in formats_found:
                            names.add(f"{vname} — {fmt}")
                    else:
                        names.add(vname)
        else:
            vname = entry.get("VenueName") or entry.get("venueName") or entry.get("name")
            show_times = entry.get("ShowTimes") or entry.get("showtimes") or entry.get("Session") or entry.get("shows")
            if vname and isinstance(show_times, list) and len(show_times) > 0:
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
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "Accept": "application/json, text/plain, */*",
            "Referer": page_url,
        }
        resp = await session.get(api_url, headers=api_headers, timeout=12)
        log(f"  [API] HTTP {resp.status_code} — {len(resp.text)} bytes")
        
        if resp.status_code in (403, 429):
            return "BLOCKED", set()
            
        return _parse_api_response(resp)
    except Exception as e:
        log(f"  [API] Exception: {e}")
        return "ERROR", set()


# ─── ASYNC PROXY RACING WORKER ──────────────────────────────────────────
async def _test_single_proxy_worker(proxy_addr: str, api_url: str, api_headers: dict) -> tuple:
    clean_addr = proxy_addr.replace("http://", "").replace("https://", "")
    proxy_url = f"http://{clean_addr}"
    try:
        async with AsyncSession(impersonate="chrome110") as session:
            resp = await session.get(
                api_url,
                headers=api_headers,
                proxies={"http": proxy_url, "https": proxy_url},
                timeout=4,  # Automatically drops laggy or offline nodes
            )
            if resp.status_code == 200:
                try:
                    text = resp.content.decode("utf-8")
                except UnicodeDecodeError:
                    import gzip as _gzip
                    try:
                        text = _gzip.decompress(resp.content).decode("utf-8")
                    except Exception:
                        return None
                
                resp._content = text.encode("utf-8")
                status, theaters = _parse_api_response(resp)
                if status in ("OK", "NOT_LIVE"):
                    return clean_addr, status, theaters
    except Exception:
        pass
    return None


async def fetch_theaters_via_free_proxy(api_url: str, page_url: str) -> tuple:
    proxies_list = await get_free_proxies()
    if not proxies_list:
        return "ERROR", set()

    # ─── FIXED CONCURRENCY TRAP ──────────────────────────────────────────────
    # random.sample extracts a unique permutation subset of proxy locations per task
    # to stop simultaneous date sweeps from knocking each other offline.
    # ─────────────────────────────────────────────────────────────────────────
    attempts = random.sample(proxies_list, min(PROXY_TRY_COUNT, len(proxies_list)))
    log(f"  [FREE-PROXY] Racing {len(attempts)} randomized Indian proxy lanes concurrently...")

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

    # Race all selected proxy lanes at the exact same time
    tasks = [_test_single_proxy_worker(p, api_url, api_headers) for p in attempts]
    
    for future in asyncio.as_completed(tasks):
        result = await future
        if result is not None:
            clean_addr, status, theaters = result
            log(f"  [FREE-PROXY] ✅ Verified Indian routing endpoint: {clean_addr}")
            return status, theaters
    
    await get_free_proxies(force_refresh=True)
    return "ERROR", set()
# ──────────────────────────────────────────────────────────────────────────


async def check_info_page_live(session: AsyncSession, info_page_url: str) -> bool:
    try:
        session.headers["Referer"] = "https://in.bookmyshow.com/"
        resp = await session.get(info_page_url, timeout=12)
        if resp.status_code != 200:
            return False

        html_lower = resp.text.lower()
        visible_text = BeautifulSoup(resp.text, "html.parser").get_text(" ").lower()

        for signal in NOT_LIVE_SIGNALS:
            if signal in visible_text:
                return False

        for signal in LIVE_SIGNALS:
            if signal in html_lower:
                return True
        return False
    except Exception:
        return False


async def get_current_theaters(session: AsyncSession, page_url: str, api_url: str) -> tuple:
    status, theaters = await fetch_theaters_via_api(session, api_url, page_url)
    if status == "OK":
        return "OK", theaters
    if status == "NOT_LIVE":
        return "NOT_LIVE", set()

    log("  ↳ Direct API blocked or flagged. Activating Proxy Fallback Cluster...")
    proxy_status, proxy_theaters = await fetch_theaters_via_free_proxy(api_url, page_url)
    if proxy_status == "OK":
        return "OK", proxy_theaters
    if proxy_status == "NOT_LIVE":
        return "NOT_LIVE", set()

    log("  ↳ Proxies exhausted. Triggering Direct HTML parsing fallback...")
    html_status, html = await fetch_page(session, page_url)
    if html_status == "OK":
        theaters = extract_theaters_from_html(html)
        if theaters:
            return "OK", theaters
        return "NOT_LIVE", set()
    
    return status, set()


def validate_config():
    if not BOT_TOKEN or "YOUR" in BOT_TOKEN or ":" not in BOT_TOKEN:
        print("❌ BOT_TOKEN configuration error.")
        exit(1)
    if not CHAT_ID or "YOUR" in CHAT_ID:
        print("❌ CHAT_ID configuration error.")
        exit(1)


async def process_movie_date(session: AsyncSession, semaphore: asyncio.Semaphore, movie: dict, target_date: str):
    movie_name = movie["name"]
    event_code = movie["code"]
    
    page_url, _, api_url = get_urls(movie, target_date)
    human_date = datetime.datetime.strptime(target_date, "%Y%m%d").strftime("%B %d, %Y")
    
    async with semaphore:
        await asyncio.sleep(random.uniform(0.3, 2.5))
        log(f"   ↳ Processing Date Code: {target_date} ({human_date}) for {movie_name}")
        
        is_first_run_for_date = is_state_key_missing(event_code, target_date)
        known_theaters = load_known_theaters(event_code, target_date)

        status, current_theaters = await get_current_theaters(session, page_url, api_url)

        if status == "OK":
            new_theaters = current_theaters - known_theaters

            if new_theaters:
                if is_first_run_for_date:
                    log(f"      📥 [Silent Init] Cached {len(current_theaters)} existing active theaters as baseline context for {movie_name}.")
                else:
                    theater_list = "\n".join(f"• {t}" for t in sorted(new_theaters))
                    alert_msg = (
                        f"🚨🎬 <b>NEW CHANNELS OPENED ON {target_date}!</b> 🎬🚨\n\n"
                        f"🎬 <b>{movie_name}</b>\n"
                        f"📅 Targeted Date: <b>{human_date}</b>\n\n"
                        f"<b>New Channels Opened:</b>\n{theater_list}\n\n"
                        f"👉 <a href='{page_url}'>SECURE SEATS NOW →</a>\n\n"
                        f"📊 Total Active Count for this date: {len(current_theaters)}"
                    )
                    await notify(alert_msg, email_subject=f"🚨 NEW SEATS OPEN FOR {movie_name.upper()} ON {target_date}!")

                known_theaters = known_theaters | current_theaters
                save_known_theaters(event_code, target_date, known_theaters)
            else:
                log(f"      ↳ Balanced map state for {movie_name} on {target_date}. Zero payload changes.")
            return "SUCCESS"

        elif status == "NOT_LIVE":
            log(f"      ↳ Matrix verified for {movie_name} on {target_date}: clear layout, zero listings active.")
            return "SUCCESS"

        elif status == "BLOCKED":
            log(f"      ❌ [BLOCKED/403] Total sweep wall hit for {movie_name} on {target_date}.")
            return "BLOCKED"

        elif status == "ERROR":
            log(f"      ⚠️ Execution loss noted for {movie_name} on {target_date}.")
            return "ERROR"


async def main_async():
    validate_config()
    SESSION = await create_warmed_session()

    log("=" * 60)
    log(f"🎬 BookMyShow Adaptive Monitor Online [ASYNC MODE]")
    log(f"   Base Loop Pause: {BASE_CHECK_INTERVAL}s + Anti-Fingerprinting Jitter")
    for m in MOVIES:
        target_dates = get_dates_to_track(m)
        log(f"   • Node: {m['name']} -> Matrix Map: {target_dates}")
    log("=" * 60)

    for movie in MOVIES:
        movie_name = movie["name"]
        dates_to_track = get_dates_to_track(movie)
        _, info_page_url, _ = get_urls(movie, dates_to_track[0])
        readable_dates = ", ".join([datetime.datetime.strptime(d, "%Y%m%d").strftime("%b %d") for d in dates_to_track])
        
        startup_alert = (
            f"🤖 <b>BMS Async Multi-Date Monitor Online</b> (Railway)\n\n"
            f"🎬 <b>Movie:</b> {movie_name}\n"
            f"📍 <b>City:</b> Hyderabad\n"
            f"📅 <b>Monitoring Horizon:</b> {readable_dates}\n"
            f"🔗 <a href='{info_page_url}'>Landing Page</a>\n\n"
            f"⚡ Concurrency engine initialized safely. Controlled worker semaphore active."
        )
        await notify(startup_alert, email_subject=f"🚀 BMS Async Monitor Online: {movie_name}")

    check_count = 0
    consecutive_failures = 0
    info_alerts_map = {m["code"]: False for m in MOVIES}

    while True:
        check_count += 1
        log(f"Matrix Check #{check_count} — structure layout scanning active [CONCURRENT]")

        # 1. Check Info Landing Status Pages Concurrently First
        info_tasks = []
        for movie in MOVIES:
            movie_name = movie["name"]
            event_code = movie["code"]
            dates_to_track = get_dates_to_track(movie)
            _, info_page_url, _ = get_urls(movie, dates_to_track[0])
            
            if not info_alerts_map[event_code]:
                async def check_and_notify(m_name, ev_code, url):
                    if await check_info_page_live(SESSION, url):
                        await notify(
                            f"🚨🎬 <b>BOOKING ARRANGEMENTS LIVE FOR {m_name.upper()}!</b> 🎬🚨\n\n"
                            f"🎬 <b>{m_name}</b> — Hyderabad\n"
                            "Main structural interface signals active layouts.\n\n"
                            f"👉 <a href='{url}'>Verify Manual Link →</a>",
                            email_subject=f"🚨 Booking Active Notice: {m_name}"
                        )
                        info_alerts_map[ev_code] = True
                info_tasks.append(check_and_notify(movie_name, event_code, info_page_url))
        
        if info_tasks:
            await asyncio.gather(*info_tasks)

        # 2. Check Layout Grid Array Horizons Concurrently
        semaphore = asyncio.Semaphore(3)  
        tasks = []
        for movie in MOVIES:
            dates_to_track = get_dates_to_track(movie)
            for target_date in dates_to_track:
                tasks.append(process_movie_date(SESSION, semaphore, movie, target_date))
        
        results = await asyncio.gather(*tasks)

        if "SUCCESS" in results:
            consecutive_failures = 0  
        else:
            consecutive_failures += 1
            log(f"⚠️ Warning: Full monitoring sweep missed. Consecutive Failure Count: {consecutive_failures}/5")
            if consecutive_failures >= 5:
                warn_subject = "⚠️ WARNING: BookMyShow Bot Failing to Track Data"
                warn_body = (
                    f"<h3>Tracking Horizon Alert</h3>"
                    f"<p>The bot has failed <b>{consecutive_failures} consecutive matrix sweeps</b>.</p>"
                    f"<p>This means proxy endpoints are blocked or BookMyShow's code layout structure shifted.</p>"
                    f"<p>Check your platform container log outputs on Railway.</p>"
                )
                await send_email(warn_subject, warn_body)
                consecutive_failures = 0  

        if "BLOCKED" in results:
            log("      ❌ Active block flagged during execution cycle. Recycling session and introducing deep back-off...")
            await SESSION.close()
            SESSION = await create_warmed_session()
            await asyncio.sleep(120)

        jitter = random.randint(5, 15)
        await asyncio.sleep(BASE_CHECK_INTERVAL + jitter)


if __name__ == "__main__":
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        log("Bot execution killed manually. Exiting tracking daemon state context gracefully.")
    except Exception as e:
        error_trace = traceback.format_exc()
        log(f"💥 CRITICAL DAEMON CRASH:\n{error_trace}")
        
        if EMAIL_ENABLED and RESEND_API_KEY != "YOUR_RESEND_API_KEY_HERE":
            try:
                subject = "💥 CRITICAL: BookMyShow Bot Crashed!"
                body = (
                    f"<h2>Your Bot Has Suffered an Unhandled Execution Crash!</h2>"
                    f"<p>The application engine stopped running on Railway.</p>"
                    f"<h4>Error Stack Trace:</h4>"
                    f"<pre style='background:#f4f4f4; padding:10px; border:1px solid #ddd;'>{error_trace}</pre>"
                )
                sync_curl.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
                    json={"from": f"BMS Bot Failure <{EMAIL_FROM}>", "to": [EMAIL_TO], "subject": subject, "html": body},
                    impersonate="chrome110",
                    timeout=15,
                )
                log("📩 Emergency failure diagnosis dispatch sent to email.")
            except Exception as mail_err:
                print(f"Could not dispatch failure diagnosis email: {mail_err}")
