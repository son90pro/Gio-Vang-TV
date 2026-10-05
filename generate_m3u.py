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

HEX_24_REGEX = re.compile(r'^[0-9a-fA-F]{24}$')

SPORT_ICONS = {
    "football": "⚽", "bongda": "⚽",
    "basketball": "🏀", "bongro": "🏀",
    "bongchuyen": "🏐", "bongban": "🏓",
    "tennis": "🎾", "billiards": "🎱", "bida": "🎱",
    "vothuat": "🥊", "boxing": "🥊", "mma": "🥊",
    "esport": "🎮", "esports": "🎮", "game": "🎮",
    "f1": "🏎️", "formula1": "🏎"
}

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
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

def find_m3u8_deep(data):
    """Tìm link .m3u8 đệ quy trong dữ liệu JSON"""
    if isinstance(data, str):
        if ".m3u8" in data and "http" in data:
            return data.replace("\\/", "/")
        matches = re.findall(r'https?://[^\s"\'\\]+\.m3u8[^\s"\'\\]*', data)
        if matches:
            return matches[0].replace("\\/", "/")
    elif isinstance(data, dict):
        for v in data.values():
            res = find_m3u8_deep(v)
            if res:
                return res
    elif isinstance(data, list):
        for item in data:
            res = find_m3u8_deep(item)
            if res:
                return res
    return None

def find_24hex_deep(data):
    """Tìm mã CDN 24-character hex đệ quy trong dữ liệu JSON"""
    if isinstance(data, str):
        val = data.strip()
        if HEX_24_REGEX.match(val):
            return val
        matches = re.findall(r'/live/([0-9a-fA-F]{24})', data)
        if matches:
            return matches[0]
        matches_raw = re.findall(r'\b([0-9a-fA-F]{24})\b', data)
        if matches_raw:
            return matches_raw[0]
    elif isinstance(data, dict):
        for v in data.values():
            res = find_24hex_deep(v)
            if res:
                return res
    elif isinstance(data, list):
        for item in data:
            res = find_24hex_deep(item)
            if res:
                return res
    return None

def fetch_via_jina(url, session):
    """Bypasses Cloudflare hoàn toàn thông qua Jina AI Reader Proxy"""
    jina_url = f"https://r.jina.ai/{url}"
    try:
        res = session.get(jina_url, timeout=10)
        if res.status_code == 200:
            return res.text
    except Exception:
        pass
    return None

def get_stream_url(session, match):
    # 1. Tìm trực tiếp .m3u8 trong JSON trận đấu
    m3u8_direct = find_m3u8_deep(match)
    if m3u8_direct:
        return m3u8_direct

    # 2. Tìm mã CDN Hex 24 ký tự trong JSON trận đấu
    hex24 = find_24hex_deep(match)
    if hex24:
        return f"https://vcdn.cloud/live/{hex24}/index.m3u8"

    match_id = str(match.get("id") or match.get("fi") or "").strip()
    if not match_id:
        return None

    # Nếu match_id bản thân nó là 24 ký tự Hex chuẩn
    if HEX_24_REGEX.match(match_id):
        return f"https://vcdn.cloud/live/{match_id}/index.m3u8"

    # 3. Dùng Jina Reader để cào trang web trận đấu (Bypass Cloudflare)
    web_targets = [
        f"https://giovang.rent/truc-tiep/{match_id}",
        WIDGET_API_URL.format(match_id=match_id)
    ]

    for target in web_targets:
        page_text = fetch_via_jina(target, session)
        if page_text:
            m3u8_found = find_m3u8_deep(page_text)
            if m3u8_found:
                return m3u8_found
            
            hex_found = find_24hex_deep(page_text)
            if hex_found:
                return f"https://vcdn.cloud/live/{hex_found}/index.m3u8"

    # 4. Cổng Proxy dự phòng phụ
    proxy_urls = [
        f"https://api.allorigins.win/raw?url={WIDGET_API_URL.format(match_id=match_id)}",
        f"https://api.codetabs.com/v1/proxy?quest={WIDGET_API_URL.format(match_id=match_id)}"
    ]
    for p_url in proxy_urls:
        try:
            res = session.get(p_url, timeout=5)
            if res.status_code == 200:
                m3u8 = find_m3u8_deep(res.text)
                if m3u8:
                    return m3u8
                hex_p = find_24hex_deep(res.text)
                if hex_p:
                    return f"https://vcdn.cloud/live/{hex_p}/index.m3u8"
        except Exception:
            pass

    return None

def generate_m3u():
    session = create_http_session()
    matches = fetch_matches(session)
    m3u_lines = ["#EXTM3U"]
    count = 0

    print(f"-> Quét được {len(matches)} trận đấu. Đang trích xuất link CDN...")

    for match in matches:
        status_code = str(match.get("status_code", "")).upper()
        status_text = str(match.get("status", "")).lower()
        if status_code in ["FINISHED", "FT", "ENDED", "CANCELLED"] or "kết thúc" in status_text:
            continue

        raw_stream_url = get_stream_url(session, match)

        if not raw_stream_url:
            match_id = match.get("id") or match.get("fi")
            print(f"  [X] Chưa lấy được luồng phát: {match_id}")
            continue

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
        print(f"  [OK] Đã thêm thành công: {title}")

    with open("giovang.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print(f"\n==========================================")
    print(f"Tạo playlist thành công! Tổng cộng: {count} kênh")
    print(f"==========================================")

if __name__ == "__main__":
    generate_m3u()
    
