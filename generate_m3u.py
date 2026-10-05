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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
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
        "tom": "Tôm", "cay": "Cầy", "ngu": "Ngơ", "can": "Cận",
        "tuimu": "Túi Mù", "beo": "Béo", "mason": "Mason", "mickey": "Mickey", "riko": "Riko"
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

def extract_m3u8_from_text(text):
    """Tìm tất cả link .m3u8 hợp lệ trong chuỗi văn bản hoặc HTML"""
    if not text:
        return None
    # Xử lý ký tự escape trong JSON
    text = text.replace("\\/", "/")
    matches = re.findall(r'https?://[^\s"\'\\]+\.m3u8[^\s"\'\\]*', text)
    for m in matches:
        if "vcdn.cloud" in m or "index.m3u8" in m or ".m3u8" in m:
            return m
    return None

def get_stream_url(session, match):
    match_id = match.get("id") or match.get("fi")
    
    # 1. Kiểm tra trực tiếp dữ liệu match từ live.json
    for key in ["pc_stream_url", "mobile_stream_url", "stream_url", "m3u8", "link"]:
        val = match.get(key)
        if isinstance(val, str) and ".m3u8" in val:
            return val.replace("\\/", "/")

    if not match_id:
        return None

    # 2. Cào dữ liệu trực tiếp từ trang web trận đấu của Giờ Vàng
    web_urls = [
        f"https://giovang.rent/truc-tiep/{match_id}",
        f"https://giovang.rent/match/{match_id}",
        f"https://giovang.rent/room/{match_id}"
    ]
    for w_url in web_urls:
        try:
            res = session.get(w_url, timeout=6)
            if res.status_code == 200:
                m3u8 = extract_m3u8_from_text(res.text)
                if m3u8:
                    return m3u8
        except Exception:
            pass

    # 3. Thử gọi Widget API bằng Proxy
    target_url = WIDGET_API_URL.format(match_id=match_id)
    proxy_urls = [
        target_url,
        f"https://api.allorigins.win/raw?url={target_url}",
        f"https://api.codetabs.com/v1/proxy?quest={target_url}"
    ]

    for u in proxy_urls:
        try:
            res = session.get(u, timeout=6)
            if res.status_code == 200:
                m3u8 = extract_m3u8_from_text(res.text)
                if m3u8:
                    return m3u8
        except Exception:
            pass

    # Không tạo link đoán bừa nếu không bóc tách được link xịn
    return None

def generate_m3u():
    session = create_http_session()
    matches = fetch_matches(session)
    m3u_lines = ["#EXTM3U"]
    count = 0

    print(f"-> Quét được {len(matches)} trận đấu. Đang trích xuất link phát CDN chuẩn...")

    for match in matches:
        status_code = str(match.get("status_code", "")).upper()
        status_text = str(match.get("status", "")).lower()
        if status_code in ["FINISHED", "FT", "ENDED", "CANCELLED"] or "kết thúc" in status_text:
            continue

        # Lấy link stream chuẩn thực tế
        raw_stream_url = get_stream_url(session, match)

        # Bỏ qua nếu chưa có luồng phát thực sự (tránh đưa link hỏng vào TiviMate)
        if not raw_stream_url:
            match_id = match.get("id") or match.get("fi")
            print(f"  [X] Bỏ qua trận {match_id}: Luồng phát chưa sẵn sàng")
            continue

        # Định dạng URL cho TiviMate & OTT Players
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
        m3u_lines.append(f'#EXTHTTP:{{"User-Agent":"{USER_AGENT}","Referer":"{REFERER_URL}"}}')
        m3u_lines.append(stream_url_for_tivimate)
        m3u_lines.append("")
        count += 1
        print(f"  [OK] Đã bóc tách thành công: {title}")

    with open("giovang.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print(f"\n==========================================")
    print(f"Đã cập nhật {count} kênh chuẩn vào giovang.m3u")
    print(f"==========================================")

if __name__ == "__main__":
    generate_m3u()
    
