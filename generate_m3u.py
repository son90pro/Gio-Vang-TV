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
WIDGET_API_URL = "https://fixture-widget.keonhacaitp.one/api/widget/{match_id}"

REFERER_URL = "https://giovang.rent/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

SPORT_ICONS = {
    "football": "⚽", "bongda": "⚽",
    "basketball": "🏀", "bongro": "🏀",
    "bongchuyen": "🏐",
    "bongban": "🏓",
    "tennis": "🎾",
    "billiards": "🎱", "bida": "🎱",
    "vothuat": "🥊", "boxing": "🥊", "mma": "🥊",
    "esport": "🎮", "esports": "🎮", "game": "🎮",
    "f1": "🏎️", "formula1": "🏎"
}

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Referer": REFERER_URL,
    "Origin": "https://giovang.rent"
}

def create_http_session():
    if HAS_CLOUDSCRAPER:
        session = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
    else:
        session = requests.Session()
    session.headers.update(HEADERS)
    return session

def clean_blv_name(blv_raw):
    if isinstance(blv_raw, list) and blv_raw:
        raw = str(blv_raw[0])
    else:
        raw = str(blv_raw or "")

    clean = re.sub(r'^(blv[-_]?|BLV[-_]?)', '', raw, flags=re.IGNORECASE).strip()
    
    blv_map = {
        "vit": "Vịt", "sun": "Sun", "sup": "Sup", "ben": "Bên",
        "hau": "Hậu", "diec": "Điếc", "bon": "Bốn", "tri": "Trí",
        "tom": "Tôm", "cay": "Cây", "cầy": "Cầy", "ngu": "Ngơ",
        "tuimu": "Túi Mù", "beo": "Béo", "mason": "Mason", "mickey": "Mickey"
    }
    
    if clean.lower() in blv_map:
        return blv_map[clean.lower()]
    return clean.capitalize() if clean else "BLV"

def fetch_matches(session):
    timestamp = int(time.time())
    url = f"{LIVE_API_URL}?t={timestamp}"

    try:
        response = session.get(url, timeout=12)
        if response.status_code == 200:
            res_json = response.json()
            return res_json.get("response", [])
    except Exception as e:
        print(f"[ERR] API live.json: {e}")
    return []

def get_stream_url(session, match_id):
    """Ưu tiên lấy link từ Widget API, nếu bị Cloudflare chặn thì tự động Fallback"""
    url = WIDGET_API_URL.format(match_id=match_id)
    try:
        res = session.get(url, timeout=6)
        if res.status_code == 200 and res.text.strip().startswith("{"):
            data = res.json()
            stream_url = data.get("pc_stream_url") or data.get("mobile_stream_url")
            if not stream_url and isinstance(data.get("response"), dict):
                resp = data.get("response", {})
                stream_url = resp.get("pc_stream_url") or resp.get("mobile_stream_url")
            
            if stream_url and stream_url.startswith("http"):
                return stream_url
    except Exception:
        pass
    
    # Fallback tạo link CDN trực tiếp kèm ID khi Widget API không phản hồi JSON
    return f"https://vcdn.cloud/live/{match_id}/index.m3u8"

def generate_m3u():
    session = create_http_session()
    matches = fetch_matches(session)
    m3u_lines = ["#EXTM3U"]
    count = 0

    print(f"-> Quét được {len(matches)} trận đấu. Đang tạo danh sách kênh M3U...")

    for match in matches:
        status_code = str(match.get("status_code", "")).upper()
        status_text = str(match.get("status", "")).lower()
        if status_code in ["FINISHED", "FT", "ENDED", "CANCELLED"] or "kết thúc" in status_text:
            continue

        match_id = match.get("id") or match.get("fi")
        if not match_id:
            continue

        # Lấy link stream
        raw_stream_url = get_stream_url(session, match_id)

        # Nối Referer & User-Agent vào URL cho TiviMate
        stream_url_for_tivimate = f"{raw_stream_url}|Referer={REFERER_URL}&User-Agent={USER_AGENT}"

        sport_type = str(match.get("type", "football")).lower()
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
        m3u_lines.append(f'#EXTVLCOPT:http-referrer={REFERER_URL}')
        m3u_lines.append(f'#EXTVLCOPT:http-user-agent={USER_AGENT}')
        m3u_lines.append(stream_url_for_tivimate)
        m3u_lines.append("")
        count += 1
        print(f"  [OK] Đã thêm: {title}")

    with open("giovang.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print(f"\n==========================================")
    print(f"Đã cập nhật thành công {count} trận vào giovang.m3u")
    print(f"==========================================")

if __name__ == "__main__":
    generate_m3u()
    
