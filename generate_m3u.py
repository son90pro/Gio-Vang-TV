import re
import time
import json
import requests

try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False

LIVE_API_URL = "https://live-api.keonhacaitp.one/storage/livestream/live.json"
DEFAULT_OFFLINE_STREAM = "https://freem3u.xyz/static/no-signal/low.m3u8"

SPORT_ICONS = {
    "football": "⚽", "bongda": "⚽",
    "basketball": "🏀", "bongro": "🏀",
    "bongchuyen": "🏐",
    "tennis": "🥎",
    "vothuat": "🥊🥋", "boxing": "🥊🥋", "mma": "🥊🥋",
    "esports": "🎮", "game": "🎮",
    "f1": "[formula1]", "formula1": "[formula1]", "racing": "[formula1]"
}

REFERER_URL = "https://giovang.rent/"
ORIGIN_URL = "https://giovang.rent"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Referer": REFERER_URL,
    "Origin": ORIGIN_URL
}

def create_http_session():
    if HAS_CLOUDSCRAPER:
        return cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
        )
    session = requests.Session()
    session.headers.update(HEADERS)
    return session

def clean_blv_name(blv_raw):
    if isinstance(blv_raw, list) and blv_raw:
        name = str(blv_raw[0])
    else:
        name = str(blv_raw or "BLV")

    name = re.sub(r'^(blv[-_]?|BLV[-_]?)', '', name, flags=re.IGNORECASE).strip()
    blv_map = {
        "diec": "Điếc", "vit": "Vịt", "bon": "Bốn", "tri": "Trí",
        "tom": "Tôm", "cay": "Cây", "sun": "Sun", "ben": "Bên",
        "ngu": "Ngơ", "tuimu": "Túi Mù"
    }
    return blv_map.get(name.lower(), name.capitalize())

def is_match_valid(match):
    status_code = str(match.get("status_code", "")).upper()
    status_text = str(match.get("status", "")).lower()

    finished_keywords = ["FINISHED", "FT", "ENDED", "CANCELLED", "POSTPONED"]
    if status_code in finished_keywords or "kết thúc" in status_text or "hoãn" in status_text:
        return False
    return True

def extract_stream_urls_direct(match_dict):
    """Biroken dagiti direct m3u8 URLs wenno valid stream IDs manipud iti match object"""
    urls = []
    match_str = json.dumps(match_dict)

    # 1. Biroken no adda direct .m3u8 links iti JSON
    m3u8_links = re.findall(r'https?://[^\s"]+\.m3u8', match_str)
    if m3u8_links:
        for link in m3u8_links:
            if "no-signal" not in link:
                urls.append(link)

    # 2. No awan direct .m3u8 links, biroken dagiti 9-10 digit numbers
    if not urls:
        all_digits = re.findall(r'\b(\d{9,10})\b', match_str)
        for d in set(all_digits):
            # Isina dagiti unix timestamp nga agsardeng iti '00' wenno '000'
            if not (d.endswith("00") or d.endswith("000")):
                urls.append(f"https://ftlh5sc02iliv.vcdn.cloud/{d}_hd/{d}_hd@720p.m3u8")
                urls.append(f"https://ftlh5sc01iliv.vcdn.cloud/{d}_hd/{d}_hd@720p.m3u8")

    return list(dict.fromkeys(urls))

def fetch_matches():
    timestamp = int(time.time())
    url = f"{LIVE_API_URL}?t={timestamp}"
    session = create_http_session()

    try:
        response = session.get(url, headers=HEADERS, timeout=12)
        if response.status_code == 200:
            res_json = response.json()
            return res_json.get("response", [])
    except Exception as e:
        print(f"[ERR] Lỗi kết nối API: {e}")
    return []

def generate_m3u():
    matches = fetch_matches()
    m3u_lines = ["#EXTM3U\n"]
    count_added = 0

    ext_http_json = json.dumps({
        "headers": {
            "Referer": REFERER_URL,
            "User-Agent": USER_AGENT,
            "Origin": ORIGIN_URL
        }
    })

    for match in matches:
        if not is_match_valid(match):
            continue

        stream_urls = extract_stream_urls_direct(match)

        sport_type = str(match.get("type", "football")).lower()
        league_name = str(match.get("league", {}).get("name", "")).lower()
        
        if any(k in league_name for k in ["f1", "formula", "grand prix", "racing"]):
            icon = "[formula1]"
        elif any(k in sport_type or k in league_name for k in ["esports", "game", "lol", "csgo", "dota"]):
            icon = "🎮"
        else:
            icon = SPORT_ICONS.get(sport_type, "⚽")

        time_str = match.get("time", "00:00:00")[:5]
        day_month = match.get("day_month", "")

        teams = match.get("teams", {}) or {}
        home_team = teams.get("home", {}) if isinstance(teams, dict) else {}
        away_team = teams.get("away", {}) if isinstance(teams, dict) else {}

        home_name = home_team.get("name", "").strip() if home_team else ""
        away_name = away_team.get("name", "").strip() if away_team else ""

        logo = (
            (home_team.get("logo") if home_team else None)
            or (away_team.get("logo") if away_team else None)
            or match.get("league", {}).get("icon")
            or ""
        )

        blv_raw = match.get("blv", [])
        blv_formatted = clean_blv_name(blv_raw)

        is_live = match.get("is_live", False)
        status_code = str(match.get("status_code", "")).upper()

        if is_live or status_code == "LIVE":
            status_symbol = "🟢 "
        elif status_code in ["UPCOMING", "WAITING"]:
            status_symbol = "🟡 "
        else:
            status_symbol = ""

        if not stream_urls:
            stream_urls = [DEFAULT_OFFLINE_STREAM]

        title = f"{status_symbol}{time_str} {day_month} {icon} {home_name} vs {away_name} ({blv_formatted}) [hls]"

        for idx, stream_url in enumerate(stream_urls):
            display_title = title if len(stream_urls) == 1 else f"{title} - Luồng {idx + 1}"
            
            m3u_lines.append(
                f'#EXTINF:-1 tvg-logo="{logo}" group-title="Giờ Vàng TV" '
                f'http-referrer="{REFERER_URL}" http-user-agent="{USER_AGENT}" , {display_title}'
            )
            m3u_lines.append(f'#EXTHTTP:{ext_http_json}')
            m3u_lines.append(f'#EXTVLCOPT:http-user-agent={USER_AGENT}')
            m3u_lines.append(f'#EXTVLCOPT:http-referrer={REFERER_URL}')
            m3u_lines.append(f'#EXTVLCOPT:http-origin={ORIGIN_URL}')
            
            final_url = f"{stream_url}|Referer={REFERER_URL}&User-Agent={USER_AGENT}&Origin={ORIGIN_URL}"
            m3u_lines.append(final_url)
            m3u_lines.append("")
        
        count_added += 1

    with open("giovang.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print(f"Đã cập nhật thành công {count_added} trận vào giovang.m3u")

if __name__ == "__main__":
    generate_m3u()
    
