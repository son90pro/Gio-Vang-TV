import re
import time
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
    "football": "⚽",
    "bongda": "⚽",
    "basketball": "🏀",
    "bongro": "🏀",
    "bongchuyen": "🏐",
    "tennis": "🥎",
    "vothuat": "🥊",
    "esports": "🎮",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://giovang.rent/",
}

def remove_accents(input_str):
    """Chuyển tiếng Việt có dấu thành không dấu để khớp URL slug"""
    if not input_str:
        return ""
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    no_accent = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    no_accent = no_accent.replace('đ', 'd').replace('Đ', 'D')
    clean_str = re.sub(r'[^a-zA-Z0-9\s-]', '', no_accent).lower()
    return re.sub(r'[\s-]+', '-', clean_str).strip('-')

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

def fetch_matches():
    timestamp = int(time.time())
    url = f"{LIVE_API_URL}?t={timestamp}"
    session = create_http_session()

    try:
        response = session.get(url, headers=HEADERS, timeout=12)
        print(f"[DEBUG] HTTP Status API chính: {response.status_code}")
        
        if response.status_code == 200:
            res_json = response.json()
            matches = res_json.get("response", [])
            print(f"[DEBUG] Tổng số trận nhận từ API: {len(matches)}")
            return matches
    except Exception as e:
        print(f"[ERR] Không thể kết nối tới API: {e}")
    return []

def scrape_all_streams():
    stream_map = {}
    match_page_urls = set()
    session = create_http_session()

    domains = ["https://giovang.rent/", "https://giovang.co/"]
    for domain in domains:
        try:
            res = session.get(domain, headers=HEADERS, timeout=10)
            print(f"[DEBUG] Tải trang chủ {domain} - Status: {res.status_code}")
            if res.status_code == 200:
                html = res.text
                
                # Quét tất cả đường dẫn dạng /truc-tiep... kể cả trong JS/JSON
                raw_paths = re.findall(r'["\'](/truc-tiep[^\s"\'\\]*)["\']', html)
                raw_urls = re.findall(r'["\'](https?://[^\s"\'\\]+truc-tiep[^\s"\'\\]*)["\']', html)
                
                for path in raw_paths:
                    clean_path = path.replace("\\/", "/")
                    match_page_urls.add(domain.rstrip('/') + clean_path)
                    
                for url in raw_urls:
                    clean_url = url.replace("\\/", "/")
                    match_page_urls.add(clean_url)

                if match_page_urls:
                    print(f"[DEBUG] Đã tìm thấy {len(match_page_urls)} đường dẫn trận đấu từ {domain}")
                    break
        except Exception as e:
            print(f"[DEBUG] Lỗi tải {domain}: {e}")

    # Bóc tách link .m3u8 trực tiếp từ từng trang trận đấu
    for page_url in match_page_urls:
        try:
            res = session.get(page_url, headers=HEADERS, timeout=8)
            if res.status_code == 200:
                html_content = res.text
                
                # Tìm tất cả link .m3u8 trong HTML/JS của trang
                m3u8_links = re.findall(r'https?://[^\s"\'\\]+\.m3u8[^\s"\'\\]*', html_content)
                valid_m3u8s = []
                for u in m3u8_links:
                    clean_u = u.replace("\\/", "/").replace("\\u002F", "/").replace("\\u002f", "/")
                    if "no-signal" not in clean_u and "freem3u" not in clean_u:
                        valid_m3u8s.append(clean_u)
                valid_m3u8s = list(set(valid_m3u8s))

                if valid_m3u8s:
                    print(f"[SUCCESS] Lấy thành công {len(valid_m3u8s)} link stream từ: {page_url}")
                    stream_map[page_url.lower()] = valid_m3u8s
        except Exception as e:
            print(f"[DEBUG] Lỗi cào trang {page_url}: {e}")

    return stream_map, list(match_page_urls)

def generate_m3u():
    matches = fetch_matches()
    
    print("[INFO] Đang dùng CloudScraper cào dữ liệu luồng m3u8...")
    stream_map, all_page_urls = scrape_all_streams()

    m3u_lines = ["#EXTM3U\n"]
    count_added = 0

    for match in matches:
        if not is_match_valid(match):
            continue

        sport_type = str(match.get("type", "football")).lower()
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

        blv_list = match.get("blv", [])
        blv_name = blv_list[0] if isinstance(blv_list, list) and blv_list else "BLV"

        is_live = match.get("is_live", False)
        status_code = str(match.get("status_code", "")).upper()
        status_symbol = "🟢 " if (is_live or status_code == "LIVE") else "🟡 "

        stream_urls = []
        
        # Chuyển tên đội sang slug không dấu để so sánh
        home_slug = remove_accents(home_name)
        away_slug = remove_accents(away_name)
        
        for purl in all_page_urls:
            purl_lower = purl.lower()
            # Khớp nếu tên 1 trong 2 đội xuất hiện trong URL trang web
            if (home_slug and len(home_slug) > 2 and home_slug in purl_lower) or \
               (away_slug and len(away_slug) > 2 and away_slug in purl_lower):
                if purl_lower in stream_map:
                    stream_urls = stream_map[purl_lower]
                    break

        if not stream_urls:
            stream_urls = [DEFAULT_OFFLINE_STREAM]

        title = f"{status_symbol}{time_str} {day_month} {icon} {home_name} vs {away_name} ({blv_name})"

        for idx, stream_url in enumerate(stream_urls):
            display_title = title if len(stream_urls) == 1 else f"{title} - Luồng {idx + 1}"
            
            m3u_lines.append(f'#EXTINF:-1 tvg-logo="{logo}" group-title="Giờ Vàng TV", {display_title}')
            m3u_lines.append("#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
            m3u_lines.append("#EXTVLCOPT:http-referrer=https://giovang.rent/")
            
            if "freem3u.xyz" in stream_url:
                m3u_lines.append(stream_url)
            else:
                m3u_lines.append(f"{stream_url}|Referer=https://giovang.rent/&User-Agent=Mozilla/5.0")
            m3u_lines.append("")
        
        count_added += 1

    with open("giovang.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print(f"Đã cập nhật danh sách thành công: {count_added} trận (Đang & Sắp diễn ra).")

if __name__ == "__main__":
    generate_m3u()
    
