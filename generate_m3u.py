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
PRIMARY_CDN = "https://ftlh5sc02iliv.vcdn.cloud"

SPORT_ICONS = {
    "football": "⚽", "bongda": "⚽",
    "basketball": "🏀", "bongro": "🏀",
    "bongchuyen": "🏐",
    "tennis": "🥎",
    "vothuat": "🥊🥋", "boxing": "🥊🥋", "mma": "🥊🥋",
    "esports": "🎮", "game": "🎮",
    "f1": "[formula1]", "formula1": "[formula1]", "racing": "[formula1]",
    "baseball": "⚾", "bongchay": "⚾"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://giovang.rent/",
    "Origin": "https://giovang.rent"
}

def create_http_session():
    if HAS_CLOUDSCRAPER:
        return cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
    session = requests.Session()
    session.headers.update(HEADERS)
    return session

def clean_blv_name(blv_raw):
    if isinstance(blv_raw, list) and blv_raw:
        if isinstance(blv_raw[0], dict):
            name = str(blv_raw[0].get("name") or blv_raw[0].get("nickname") or "BLV")
        else:
            name = str(blv_raw[0])
    elif isinstance(blv_raw, dict):
        name = str(blv_raw.get("name") or blv_raw.get("nickname") or "BLV")
    else:
        name = str(blv_raw or "BLV")

    raw_strip = name.strip()
    raw_lower = raw_strip.lower()
    
    blv_map = {
        "diec": "Điếc", "vit": "Vịt", "bon": "Bốn", "tri": "Trí",
        "tom": "Tôm", "cay": "Cây", "cầy": "Cầy", "sun": "Sun", "ben": "Bên",
        "ngu": "Ngơ", "tuimu": "Túi Mù", "beo": "Béo", "mason": "Mason", "mickey": "Mickey",
        "dory": "Dory", "bee": "Bee", "riko": "riko", "sup": "sup", "ngong": "ngong", "can": "can"
    }

    clean_key = re.sub(r'^(blv[-_]?|BLV[-_]?)', '', raw_lower).strip()
    if clean_key in blv_map:
        return blv_map[clean_key]
    if raw_lower in blv_map:
        return blv_map[raw_lower]

    return raw_strip

def is_match_valid(match):
    status_code = str(match.get("status_code", "")).upper()
    status_text = str(match.get("status", "")).lower()

    finished_keywords = ["FINISHED", "FT", "ENDED", "CANCELLED", "POSTPONED"]
    if status_code in finished_keywords or "kết thúc" in status_text or "hoãn" in status_text:
        return False
    return True

def get_stream_url(match):
    match_id = match.get("id") or match.get("bitrate_id") or match.get("room_id") or match.get("stream_id")
    
    if match_id is None:
        m = re.search(r'"id"\s*:\s*"?(\d+)"?', json.dumps(match))
        if m:
            match_id = m.group(1)

    if match_id is not None:
        s_id = str(match_id).strip()
        digits = re.sub(r'\D', '', s_id)
        if digits:
            if len(digits) == 10 and digits.startswith("17"):
                return f"{PRIMARY_CDN}/{digits}_hd/{digits}_hd@720p.m3u8"
            
            ts = str(match.get("timestamp") or match.get("start_time") or match.get("time_stamp") or int(time.time())).strip()
            ts_digits = re.sub(r'\D', '', ts)
            prefix = ts_digits[:5] if len(ts_digits) >= 5 else "17910"
            
            full_id = f"{prefix}{digits.zfill(5)}"
            return f"{PRIMARY_CDN}/{full_id}_hd/{full_id}_hd@720p.m3u8"

    return DEFAULT_OFFLINE_STREAM

def fetch_matches():
    timestamp = int(time.time())
    url = f"{LIVE_API_URL}?t={timestamp}"
    session = create_http_session()

    try:
        response = session.get(url, headers=HEADERS, timeout=12)
        if response.status_code == 200:
            res_json = response.json()
            if isinstance(res_json, dict):
                return res_json.get("response", []) or res_json.get("data", [])
            elif isinstance(res_json, list):
                return res_json
    except Exception as e:
        print(f"[ERR] Lỗi kết nối API: {e}")
    return []

def generate_m3u():
    matches = fetch_matches()
    m3u_lines = ["#EXTM3U"]
    count_added = 0

    for match in matches:
        if not is_match_valid(match):
            continue

        stream_url = get_stream_url(match)

        sport_type = str(match.get("type", "football")).lower()
        league_name = str(match.get("league", {}).get("name", "")).lower()

        if any(k in league_name for k in ["f1", "formula", "grand prix", "racing"]):
            icon = "[formula1]"
        elif any(k in sport_type or k in league_name for k in ["esports", "game", "lol", "csgo", "dota"]):
            icon = "🎮"
        elif any(k in sport_type or k in league_name for k in ["baseball", "bongchay"]):
            icon = "⚾"
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

        is_live = match.get("is_live") in [True, 1, "1", "true", "True"]
        status_code = str(match.get("status_code", "")).upper()

        if is_live or status_code == "LIVE":
            status_symbol = "🟢 "
        elif status_code in ["WAITING", "UPCOMING", "0"]:
            status_symbol = "🟡 "
        else:
            status_symbol = ""

        title = f"{status_symbol}{time_str} {day_month} {icon} {home_name} vs {away_name} ({blv_formatted}) [hls]"

        m3u_lines.append(f'#EXTINF:-1 tvg-logo="{logo}" group-title="Giờ Vàng TV" , {title}')
        m3u_lines.append(stream_url)
        m3u_lines.append("")

        count_added += 1

    with open("giovang.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print(f"Đã cập nhật thành công {count_added} trận vào giovang.m3u")

if __name__ == "__main__":
    generate_m3u()
    
