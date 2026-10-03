import re
import time
import json
import unicodedata
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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://giovang.rent/",
}

def create_http_session():
    if HAS_CLOUDSCRAPER:
        return cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
        )
    session = requests.Session()
    session.headers.update(HEADERS)
    return session

def is_match_valid(match):
    status_code = str(match.get("status_code", "")).upper()
    status_text = str(match.get("status", "")).lower()

    finished_keywords = ["FINISHED", "FT", "ENDED", "CANCELLED", "POSTPONED"]
    if status_code in finished_keywords or "kết thúc" in status_text or "hoãn" in status_text:
        return False
    return True

def extract_stream_urls(match_dict):
    """Trích xuất link vcdn.cloud trực tiếp hoặc tự dựng từ Stream ID 10 chữ số"""
    match_str = json.dumps(match_dict)
    
    # 1. Tìm trực tiếp URL vcdn.cloud dạng .m3u8 trong JSON
    vcdn_urls = re.findall(r'https?://[^\s"\'\\]*vcdn\.cloud[^\s"\'\\]*\.m3u8', match_str)
    if vcdn_urls:
        clean_urls = [u.replace("\\/", "/") for u in vcdn_urls]
        return list(set(clean_urls))

    # 2. Tìm Stream ID dạng số (đặc trưng bắt đầu bằng 17xx, dài 9-11 chữ số của Giờ Vàng)
    ids = re.findall(r'\b(17\d{8,9})\b', match_str)
    
    if not ids:
        # Kiểm tra thêm các trường dữ liệu số phổ biến
        possible_keys = ["stream_id", "id_stream", "room_id", "channel_id", "fi", "stream_key"]
        for key in possible_keys:
            val = str(match_dict.get(key, ""))
            if re.match(r'^\d{8,11}$', val):
                ids.append(val)

    if ids:
        unique_ids = list(set(ids))
        return [f"https://ftlh5sc02iliv.vcdn.cloud/{sid}_hd/{sid}_hd@720p.m3u8" for sid in unique_ids]

    return []

def fetch_matches():
    timestamp = int(time.time())
    url = f"{LIVE_API_URL}?t={timestamp}"
    session = create_http_session()

    try:
        response = session.get(url, headers=HEADERS, timeout=12)
        if response.status_code == 200:
            res_json = response.json()
            matches = res_json.get("response", [])
            return matches
    except Exception as e:
        print(f"[ERR] Không thể kết nối API: {e}")
    return []

def generate_m3u():
    matches = fetch_matches()
    m3u_lines = ["#EXTM3U\n"]
    count_added = 0

    for match in matches:
        if not is_match_valid(match):
            continue

        # Lấy link stream thực tế
        stream_urls = extract_stream_urls(match)

        # Xử lý Icon môn thể thao
        sport_type = str(match.get("type", "football")).lower()
        league_name = str(match.get("league", {}).get("name", "")).lower()
        
        if any(k in league_name for k in ["f1", "formula", "grand prix", "racing"]):
            icon = "[formula1]"
        elif any(k in sport_type or k in league_name for k in ["esports", "game", "lol", "csgo", "dota"]):
            icon = "🎮"
        else:
            icon = SPORT_ICONS.get(sport_type, "⚽")

        # Thời gian và thông tin đội bóng
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
        blv_name = blv_raw[0] if isinstance(blv_raw, list) and blv_raw else str(blv_raw or "BLV")

        # Ký hiệu trạng thái phát trận đấu
        is_live = match.get("is_live", False)
        status_code = str(match.get("status_code", "")).upper()

        if is_live or status_code == "LIVE":
            status_symbol = "🟢 "
        elif status_code in ["UPCOMING", "WAITING"]:
            status_symbol = "🟡 "
        else:
            status_symbol = ""

        # Luồng mặc định nếu không tìm thấy stream
        if not stream_urls:
            stream_urls = [DEFAULT_OFFLINE_STREAM]

        title = f"{status_symbol}{time_str} {day_month} {icon} {home_name} vs {away_name} ({blv_name}) [hls]"

        for idx, stream_url in enumerate(stream_urls):
            display_title = title if len(stream_urls) == 1 else title.replace(" [hls]", f" - Luồng {idx + 1} [hls]")
            
            # Định dạng chính xác chuẩn 100% mẫu của anh Sơn
            m3u_lines.append(f'#EXTINF:-1 tvg-logo="{logo}" group-title="Giờ Vàng TV" , {display_title}')
            m3u_lines.append(stream_url)
            m3u_lines.append("")
        
        count_added += 1

    with open("giovang.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print(f"Đã cập nhật danh sách thành công: {count_added} trận.")

if __name__ == "__main__":
    generate_m3u()
    
