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
    "vothuat": "🥊🥋",
    "esports": "🎮",
    "f1": "[formula1]", "formula1": "[formula1]", "racing": "[formula1]"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
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

def extract_vcdn_from_text(text):
    """Tìm tất cả đường dẫn vcdn.cloud .m3u8 trong chuỗi văn bản/JSON"""
    if not text:
        return []
    matches = re.findall(r'https?://[^\s"\'\\]*vcdn\.cloud[^\s"\'\\]*\.m3u8', text)
    clean_links = []
    for m in matches:
        clean = m.replace("\\/", "/").replace("\\u002F", "/").replace("\\u002f", "/")
        clean_links.append(clean)
    return list(set(clean_links))

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

def scrape_web_vcdn_map():
    """Cào trực tiếp trang chủ giovang.rent để map link vcdn.cloud"""
    session = create_http_session()
    vcdn_map = {}
    domains = ["https://giovang.rent/", "https://giovang.co/"]

    for domain in domains:
        try:
            res = session.get(domain, headers=HEADERS, timeout=10)
            if res.status_code == 200:
                html = res.text
                # Tìm các khối trận đấu hoặc iframe/script chứa m3u8
                page_urls = set(re.findall(r'["\'](https?://[^\s"\'\\]+truc-tiep[^\s"\'\\]*)["\']', html))
                rel_paths = set(re.findall(r'["\'](/truc-tiep[^\s"\'\\]*)["\']', html))
                for r in rel_paths:
                    page_urls.add(domain.rstrip('/') + r.replace("\\/", "/"))

                for page_url in page_urls:
                    try:
                        p_res = session.get(page_url, headers=HEADERS, timeout=6)
                        if p_res.status_code == 200:
                            v_links = extract_vcdn_from_text(p_res.text)
                            if v_links:
                                vcdn_map[page_url.lower()] = v_links
                    except Exception:
                        pass
                if vcdn_map:
                    break
        except Exception as e:
            print(f"[DEBUG] Lỗi tải {domain}: {e}")

    return vcdn_map

def format_blv_name(blv_input):
    if not blv_input:
        return "BLV"
    if isinstance(blv_input, list):
        blv_str = blv_input[0] if blv_input else "BLV"
    else:
        blv_str = str(blv_input)
    return blv_str.strip()

def generate_m3u():
    matches = fetch_matches()
    print("[INFO] Đang quét dữ liệu trang web để bắt link vcdn...")
    web_vcdn_map = scrape_web_vcdn_map()

    m3u_lines = ["#EXTM3U\n"]
    count_added = 0

    for match in matches:
        if not is_match_valid(match):
            continue

        # 1. Trích xuất link vcdn directly từ dữ liệu API của trận đấu
        match_str = json.dumps(match)
        vcdn_links = extract_vcdn_from_text(match_str)

        # 2. Thử tạo link từ stream_id / id nếu dạng 10 chữ số
        if not vcdn_links:
            stream_id = str(match.get("stream_id") or match.get("id_stream") or match.get("fi") or "")
            if re.match(r'^\d{9,11}$', stream_id):
                vcdn_links = [f"https://ftlh5sc02iliv.vcdn.cloud/{stream_id}_hd/{stream_id}_hd@720p.m3u8"]

        # 3. Tìm trong danh sách cào web
        if not vcdn_links:
            home_name = str(match.get("teams", {}).get("home", {}).get("name", "")).lower()
            for page_url, links in web_vcdn_map.items():
                if home_name and len(home_name) > 3 and home_name in page_url:
                    vcdn_links = links
                    break

        sport_type = str(match.get("type", "football")).lower()
        league_name = str(match.get("league", {}).get("name", "")).lower()
        
        if "f1" in league_name or "formula" in league_name or "grand prix" in league_name:
            icon = "[formula1]"
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

        blv_name = format_blv_name(match.get("blv"))

        is_live = match.get("is_live", False)
        status_code = str(match.get("status_code", "")).upper()

        if is_live or status_code == "LIVE":
            status_symbol = "🟢 "
        elif status_code == "UPCOMING" or status_code == "WAITING":
            status_symbol = "🟡 "
        else:
            status_symbol = ""

        if not vcdn_links:
            stream_urls = [DEFAULT_OFFLINE_STREAM]
        else:
            stream_urls = vcdn_links

        title = f"{status_symbol}{time_str} {day_month} {icon} {home_name} vs {away_name} ({blv_name}) [hls]"

        for idx, stream_url in enumerate(stream_urls):
            display_title = title if len(stream_urls) == 1 else title.replace(" [hls]", f" - Luồng {idx + 1} [hls]")
            
            # Format đúng mẫu chuẩn anh Sơn gửi
            m3u_lines.append(f'#EXTINF:-1 tvg-logo="{logo}" group-title="Giờ Vàng TV" , {display_title}')
            
            if "freem3u.xyz" in stream_url:
                m3u_lines.append("#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
                m3u_lines.append("#EXTVLCOPT:http-referrer=https://giovang.rent/")
                m3u_lines.append(stream_url)
            else:
                m3u_lines.append(stream_url)
            m3u_lines.append("")
        
        count_added += 1

    with open("giovang.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print(f"Đã cập nhật danh sách thành công: {count_added} trận (Đang & Sắp diễn ra).")

if __name__ == "__main__":
    generate_m3u()
    
