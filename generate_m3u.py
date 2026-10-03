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
PRIMARY_CDN = "https://ftlh5sc02iliv.vcdn.cloud"
DEFAULT_OFFLINE = "https://freem3u.xyz/static/no-signal/low.m3u8"

SPORT_ICONS = {
    "football": "⚽", "bongda": "⚽",
    "basketball": "🏀", "bongro": "🏀",
    "bongchuyen": "🏐", "tennis": "🥎",
    "vothuat": "🥊", "boxing": "🥊", "mma": "🥊",
    "esports": "🎮", "game": "🎮",
    "f1": "[formula1]", "formula1": "[formula1]",
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
        item = blv_raw[0]
        name = item.get("name") or item.get("nickname") if isinstance(item, dict) else str(item)
    elif isinstance(blv_raw, dict):
        name = blv_raw.get("name") or blv_raw.get("nickname")
    else:
        name = str(blv_raw or "")

    if not name:
        return "BLV"

    raw_strip = name.strip()
    clean_key = re.sub(r'^(blv[-_]?|BLV[-_]?)', '', raw_strip, flags=re.IGNORECASE).strip()
    
    blv_map = {
        "diec": "Điếc", "vit": "Vịt", "bon": "Bốn", "tri": "Trí",
        "tom": "Tôm", "cay": "Cây", "cầy": "Cầy", "sun": "Sun", "ben": "Bên",
        "ngu": "Ngơ", "tuimu": "Túi Mù", "beo": "Béo", "mason": "Mason", "mickey": "Mickey",
        "dory": "Dory", "bee": "Bee", "riko": "riko", "sup": "sup", "ngong": "ngong", "can": "can"
    }
    
    return blv_map.get(clean_key.lower(), clean_key.capitalize() if clean_key else raw_strip)

def get_exact_stream_url(match):
    # 1. Nếu API có sẵn thuộc tính chứa link m3u8 trực tiếp
    for key in ["link_m3u8", "stream_url", "m3u8", "play_url", "link"]:
        val = match.get(key)
        if isinstance(val, str) and ".m3u8" in val:
            return val.strip()

    # 2. Lấy bitrate_id / room_id / id để tạo link CDN chuẩn
    raw_id = match.get("bitrate_id") or match.get("room_id") or match.get("id")
    if raw_id:
        s_id = str(raw_id).strip()
        digits = re.sub(r'\D', '', s_id)
        if digits:
            if len(digits) == 10 and digits.startswith("17"):
                return f"{PRIMARY_CDN}/{digits}_hd/{digits}_hd@720p.m3u8"
            
            ts = str(match.get("timestamp") or match.get("start_time") or match.get("time_stamp") or int(time.time())).strip()
            ts_digits = re.sub(r'\D', '', ts)
            prefix = ts_digits[:5] if len(ts_digits) >= 5 else "17910"
            
            full_id = f"{prefix}{digits.zfill(5)}"
            return f"{PRIMARY_CDN}/{full_id}_hd/{full_id}_hd@720p.m3u8"

    return DEFAULT_OFFLINE

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
        print(f"[ERR] API: {e}")
    return []

def generate_m3u():
    matches = fetch_matches()
    m3u_lines = ["#EXTM3U"]
    count = 0

    for match in matches:
        status_code = str(match.get("status_code", "")).upper()
        status_text = str(match.get("status", "")).lower()
        if status_code in ["FINISHED", "FT", "ENDED", "CANCELLED"] or "kết thúc" in status_text:
            continue

        stream_url = get_exact_stream_url(match)

        sport_type = str(match.get("type", "football")).lower()
        league_name = str(match.get("league", {}).get("name", "")).lower()

        if "f1" in league_name or "racing" in league_name:
            icon = "[formula1]"
        elif any(k in sport_type or k in league_name for k in ["esports", "game", "lol"]):
            icon = "🎮"
        else:
            icon = SPORT_ICONS.get(sport_type, "⚽")

        time_str = str(match.get("time", "00:00"))[:5]
        day_month = match.get("day_month", "")

        teams = match.get("teams", {}) or {}
        home_name = teams.get("home", {}).get("name", "").strip() if isinstance(teams, dict) else ""
        away_name = teams.get("away", {}).get("name", "").strip() if isinstance(teams, dict) else ""

        logo = (
            (teams.get("home", {}).get("logo") if isinstance(teams, dict) else None)
            or (teams.get("away", {}).get("logo") if isinstance(teams, dict) else None)
            or match.get("league", {}).get("icon")
            or ""
        )

        blv = clean_blv_name(match.get("blv", []))
        is_live = match.get("is_live") in [True, 1, "1", "true", "True"] or status_code == "LIVE"
        status_symbol = "🟢 " if is_live else "🟡 "

        title = f"{status_symbol}{time_str} {day_month} {icon} {home_name} vs {away_name} ({blv}) [hls]"

        m3u_lines.append(f'#EXTINF:-1 tvg-logo="{logo}" group-title="Giờ Vàng TV" , {title}')
        m3u_lines.append(stream_url)
        m3u_lines.append("")
        count += 1

    with open("giovang.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print(f"Đã cập nhật {count} trận vào giovang.m3u")

if __name__ == "__main__":
    generate_m3u()
    
