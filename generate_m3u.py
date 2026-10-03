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
    "f1": "[formula1]", "formula1": "[formula1]", "racing": "[formula1]"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://giovang.rent/",
    "Origin": "https://giovang.rent"
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
        "ngu": "Ngơ", "tuimu": "Túi Mù", "beo": "Béo", "mason": "Mason", "mickey": "Mickey"
    }
    return blv_map.get(name.lower(), name.capitalize())

def is_match_valid(match):
    status_code = str(match.get("status_code", "")).upper()
    status_text = str(match.get("status", "")).lower()

    finished_keywords = ["FINISHED", "FT", "ENDED", "CANCELLED", "POSTPONED"]
    if status_code in finished_keywords or "kết thúc" in status_text or "hoãn" in status_text:
        return False
    return True

def extract_real_room_id(match):
    """Bóc tách chính xác room_id, phân biệt triệt để với Unix Timestamp"""
    match_str = json.dumps(match)

    # 1. Nếu trong JSON API có sẵn URL .m3u8, bóc trực tiếp room_id từ URL
    m3u8_urls = re.findall(r'https?://[^\s"]+\.m3u8', match_str)
    for url in m3u8_urls:
        room_match = re.findall(r'/(\d{8,10})_hd/', url)
        if room_match:
            return room_match[0]

    # 2. Tìm tất cả chuỗi số 8-10 chữ số bắt đầu bằng 17
    all_ids = re.findall(r'\b17\d{6,8}\b', match_str)
    
    valid_room_ids = []
    for sid in all_ids:
        try:
            val = int(sid)
            # Timestamp mốc giờ trận đấu (như 1791043200) luôn chia hết cho 60
            # Room ID thực tế (như 1791011626) KHÔNG chia hết cho 60
            if val % 60 != 0:
                valid_room_ids.append(sid)
        except ValueError:
            continue

    if valid_room_ids:
        return valid_room_ids[0]

    # Nếu không lọc được theo % 60, ưu tiên lấy số xuất hiện sau cùng trong match object
    if all_ids:
        return all_ids[-1]

    return None

def extract_stream_url(match):
    room_id = extract_real_room_id(match)
    if room_id:
        return f"{PRIMARY_CDN}/{room_id}_hd/{room_id}_hd@720p.m3u8"
    return DEFAULT_OFFLINE_STREAM

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
    m3u_lines = ["#EXTM3U"]
    count_added = 0

    for match in matches:
        if not is_match_valid(match):
            continue

        stream_url = extract_stream_url(match)

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
    
