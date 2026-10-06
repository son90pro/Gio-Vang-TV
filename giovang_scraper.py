import json
import re
import sys
import unicodedata
import requests

API_TARGET = "https://live-api.keonhacaitp.one/storage/livestream/live.json"
WORKER_PROXY = f"https://vsc-proxy.sonnguyen90pro.workers.dev/?url={API_TARGET}"

CDN_BASE = "https://ftlh5sc02iliv.vcdn.cloud"
USER_AGENT_HEADER = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

# Emoji icon chuẩn theo từng bộ môn
EMOJI_MAP = {
    "football": "⚽",
    "basketball": "🏀",
    "caulong": "🏸",
    "badminton": "🏸",
    "esports": "🎮",
    "game": "🎮",
    "bongchay": "⚾",
    "baseball": "⚾",
    "rugby": "🏈",
}

def get_sport_emoji(sport_type):
    return EMOJI_MAP.get(str(sport_type).lower(), "⚽")

def slugify(text):
    if not text:
        return ""
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text).strip('-')
    return text

def fetch_real_room_id(match, homepage_html=""):
    """Chỉ bóc mã phòng Live thực tế (dạng 10 chữ số 179xxxxxxx). Nếu không thấy trả về None."""
    headers = {"User-Agent": USER_AGENT_HEADER}
    match_id = str(match.get("id") or match.get("fi") or "").strip()
    
    teams = match.get("teams", {})
    home_name = teams.get("home", {}).get("name", "")
    away_name = teams.get("away", {}).get("name", "")
    day_month = match.get("day_month", "").replace("/", "-")
    
    test_urls = []
    
    # 1. Quét tìm URL trận đấu trực tiếp từ HTML trang chủ
    if homepage_html and match_id:
        found_links = re.findall(rf'href=["\'](https?://giovang\.rent/truc-tiep-[^"\']*-{match_id})["\']', homepage_html)
        for fl in found_links:
            if fl not in test_urls:
                test_urls.append(fl)

    # 2. Tạo URL Slug SEO
    if home_name and away_name:
        home_slug = slugify(home_name)
        away_slug = slugify(away_name)
        seo_url = f"https://giovang.rent/truc-tiep-{home_slug}-vs-{away_slug}-{day_month}-{match_id}"
        if seo_url not in test_urls:
            test_urls.append(seo_url)

    for url in test_urls:
        proxy_url = f"https://vsc-proxy.sonnguyen90pro.workers.dev/?url={url}"
        try:
            res = requests.get(proxy_url, headers=headers, timeout=6)
            if res.status_code == 200:
                html = res.text
                # Lấy mã phòng live 10 chữ số bắt đầu bằng 179
                room_ids = re.findall(r'179\d{7}', html)
                for rid in room_ids:
                    if rid != "1790675945": # Lọc mã quảng cáo tĩnh
                        return rid
        except Exception:
            pass

    return None

def extract_commentator(match):
    blv_list = match.get("blv", [])
    if isinstance(blv_list, list) and blv_list:
        clean_names = []
        for name in blv_list:
            if isinstance(name, str):
                c_name = name.replace("blv-", "").replace("blv_", "").strip()
                clean_names.append(c_name)
        if clean_names:
            return ", ".join(clean_names)
    return "Thuyết minh"

def generate_m3u():
    headers = {"User-Agent": USER_AGENT_HEADER}
    
    homepage_html = ""
    try:
        hp_res = requests.get("https://vsc-proxy.sonnguyen90pro.workers.dev/?url=https://giovang.rent", headers=headers, timeout=8)
        if hp_res.status_code == 200:
            homepage_html = hp_res.text
    except Exception:
        pass

    print("Đang lấy danh sách trận đấu từ API Giờ Vàng...")
    response = requests.get(WORKER_PROXY, timeout=15)
    response.raise_for_status()
    
    res_json = response.json()
    data = res_json.get("response", []) if isinstance(res_json, dict) else []
    
    m3u_content = "#EXTM3U\n\n"
    count = 0
    
    for match in data:
        teams = match.get("teams", {})
        home_name = teams.get("home", {}).get("name", "").strip()
        away_name = teams.get("away", {}).get("name", "").strip()
        
        if not home_name or not away_name:
            continue
            
        match_name = f"{home_name} vs {away_name}"
        logo_url = teams.get("home", {}).get("logo", "")
        
        sport_type = match.get("type", "")
        sport_emoji = get_sport_emoji(sport_type)
        
        time_raw = match.get("time", "")[:5]
        day_month = match.get("day_month", "")
        time_str = f"{time_raw} {day_month}".strip()
        
        commentator = extract_commentator(match)
        
        is_live = match.get("is_live", False) or match.get("status_code") == "LIVE"
        status_icon = "🟢 " if is_live else ""

        # Lấy room_id thực tế (179xxxxxxx)
        room_id = fetch_real_room_id(match, homepage_html)
        
        if room_id:
            # Xuất URL thuần sạch sẽ theo đúng format list chuẩn
            stream_url = f"{CDN_BASE}/{room_id}_hd/{room_id}_hd@720p.m3u8"
        else:
            stream_url = "https://freem3u.xyz/static/no-signal/low.m3u8"

        m3u_content += f'#EXTINF:-1 tvg-logo="{logo_url}" group-title="Giờ Vàng TV" , {status_icon}{time_str} {sport_emoji} {match_name} ({commentator}) [hls]\n'
        m3u_content += f'{stream_url}\n\n'
        count += 1
        
    with open("giovang.m3u", "w", encoding="utf-8") as f:
        f.write(m3u_content)
    print(f"Đã xuất thành công file giovang.m3u với {count} trận đấu.")

if __name__ == "__main__":
    try:
        generate_m3u()
    except Exception as e:
        print(f"Lỗi khi chạy script Giờ Vàng: {e}", file=sys.stderr)
        sys.exit(1)
        
