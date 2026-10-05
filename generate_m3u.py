import re
import time
import requests

try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False

LIVE_API_URL = "https://live-api.keonhacaitp.one/storage/livestream/live.json"
WIDGET_API_URL = "https://fixture-widget.keonhacaitp.one/api/widget/{match_id}"

# Link video màn hình chờ chuẩn HLS (không bị xoay tròn) dùng khi trận chưa có luồng phát
FALLBACK_WAITING_URL = "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
REFERER_URL = "https://giovang.rent/"

SPORT_ICONS = {
    "football": "⚽", "bongda": "⚽",
    "basketball": "🏀", "bongro": "🏀",
    "baseball": "⚾", "bongchay": "⚾",
    "rugby": "🏈",
    "bongchuyen": "🏐", "bongban": "🏓",
    "tennis": "🎾", "billiards": "🎱", "bida": "🎱",
    "vothuat": "🥊", "boxing": "🥊", "mma": "🥊",
    "esport": "🎮", "esports": "🎮", "game": "🎮",
    "f1": "🏎️", "formula1": "🏎"
}

HEADERS = {
    "User-Agent": USER_AGENT,
    "Referer": REFERER_URL,
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
        "tuimu": "Túi Mù", "beo": "Béo", "bee": "Bee", "mason": "Mason", "mickey": "Mickey", "riko": "Riko"
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
    """Tìm link .m3u8 trực tiếp nếu có"""
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

def extract_stream_id(data):
    """Bóc tách ID luồng CDN 10 chữ số (dạng 1791xxxxxx) hoặc 24 hex"""
    if isinstance(data, (int, str)):
        s = str(data).strip()
        # Tìm ID dạng số 10 chữ số của Giờ Vàng
        m = re.findall(r'\b(179\d{7}|180\d{7}|\d{10})\b', s)
        if m:
            return m[0]
        # Hoặc Hex 24 ký tự
        m_hex = re.findall(r'\b([0-9a-fA-F]{24})\b', s)
        if m_hex:
            return m_hex[0]
    elif isinstance(data, dict):
        for k in ['stream_id', 'stream', 'embed', 'link', 'id', 'room_id', 'fi']:
            if k in data and data[k]:
                res = extract_stream_id(data[k])
                if res:
                    return res
        for v in data.values():
            res = extract_stream_id(v)
            if res:
                return res
    elif isinstance(data, list):
        for item in data:
            res = extract_stream_id(item)
            if res:
                return res
    return None

def build_vcdn_url(stream_id):
    if not stream_id:
        return None
    sid = str(stream_id).strip()
    if len(sid) == 10 and sid.isdigit():
        return f"https://ftlh5sc02iliv.vcdn.cloud/{sid}_hd/{sid}_hd@720p.m3u8"
    elif len(sid) == 24:
        return f"https://vcdn.cloud/live/{sid}/index.m3u8"
    return None

def fetch_via_jina(url, session):
    jina_url = f"https://r.jina.ai/{url}"
    try:
        res = session.get(jina_url, timeout=10)
        if res.status_code == 200:
            return res.text
    except Exception:
        pass
    return None

def get_stream_url(session, match):
    # 1. Nếu trong JSON có sẵn link .m3u8
    m3u8_direct = find_m3u8_deep(match)
    if m3u8_direct:
        return m3u8_direct

    # 2. Tìm ID luồng 10 chữ số trong JSON trận
    sid = extract_stream_id(match)
    vcdn_url = build_vcdn_url(sid)
    if vcdn_url:
        return vcdn_url

    # 3. Cào qua Widget API nếu chưa lấy được ID
    match_id = str(match.get("id") or match.get("fi") or "").strip()
    if match_id:
        target = WIDGET_API_URL.format(match_id=match_id)
        page_text = fetch_via_jina(target, session)
        if page_text:
            m3u8_found = find_m3u8_deep(page_text)
            if m3u8_found:
                return m3u8_found
            sid_web = extract_stream_id(page_text)
            vcdn_web = build_vcdn_url(sid_web)
            if vcdn_web:
                return vcdn_web

    # 4. Nếu match_id chính là ID luồng 10 chữ số
    if match_id and len(match_id) == 10 and match_id.isdigit():
        return build_vcdn_url(match_id)

    # Fallback an toàn nếu trận chưa tới giờ
    return FALLBACK_WAITING_URL

def generate_m3u():
    session = create_http_session()
    matches = fetch_matches(session)
    m3u_lines = ["#EXTM3U\n"]
    count = 0

    print(f"-> Quét được {len(matches)} trận đấu...")

    for match in matches:
        status_code = str(match.get("status_code", "")).upper()
        status_text = str(match.get("status", "")).lower()
        if status_code in ["FINISHED", "FT", "ENDED", "CANCELLED"] or "kết thúc" in status_text:
            continue

        raw_stream_url = get_stream_url(session, match)

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
        m3u_lines.append(f'{raw_stream_url}\n')
        count += 1
        print(f"  [OK] {title} -> {raw_stream_url}")

    with open("giovang.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print(f"\n==========================================")
    print(f"Tạo playlist thành công! Tổng cộng: {count} kênh")
    print(f"==========================================")

if __name__ == "__main__":
    generate_m3u()
    
