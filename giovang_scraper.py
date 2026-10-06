import json
import re
import sys
import unicodedata
import requests

API_TARGET = "https://live-api.keonhacaitp.one/storage/livestream/live.json"
WORKER_PROXY = f"https://vsc-proxy.sonnguyen90pro.workers.dev/?url={API_TARGET}"

CDN_BASE = "https://ftlh5sc02iliv.vcdn.cloud"
REFERER_HEADER = "https://keobongvip.in/"
USER_AGENT_HEADER = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

# Danh sách mã rác/ID tĩnh cần loại bỏ hoàn toàn
BLACK_LIST_IDS = {"1790675945", "1790000000"}

TYPE_MAP = {
    "football": "Bóng đá",
    "basketball": "Bóng rổ",
    "rugby": "Bóng bầu dục / NFL",
    "bongchay": "Bóng chày",
    "caulong": "Cầu lông / Trái cầu",
}

def get_group_title(sport_type, league_title=""):
    return TYPE_MAP.get(str(sport_type).lower(), league_title or "Giờ Vàng TV")

def slugify(text):
    if not text:
        return ""
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text).strip('-')
    return text

def parse_m3u8_from_html(html):
    """Trích xuất chính xác link stream m3u8 từ player HTML"""
    if not html:
        return None

    # 1. Bóc trực tiếp link .m3u8 chứa vcdn.cloud
    m3u8_urls = re.findall(r'https?://[^\s"\'<>]*vcdn\.cloud[^\s"\'<>]*\.m3u8', html)
    for url in m3u8_urls:
        return url

    # 2. Tìm link .m3u8 bất kỳ khác trong config player
    any_m3u8 = re.findall(r'https?://[^\s"\'<>]+\.m3u8', html)
    for url in any_m3u8:
        if "no-signal" not in url:
            return url

    # 3. Tìm ID phòng live trong player config (dạng url: "...", src: "...")
    player_ids = re.findall(r'(?:url|src|file|id)\s*[:=]\s*["\'](?:https?://[^\s"\']*/)?(\d{7,10})(?:_hd)?(?:/|\.m3u8|["\'])', html, re.IGNORECASE)
    for pid in player_ids:
        if pid not in BLACK_LIST_IDS:
            return f"{CDN_BASE}/{pid}_hd/{pid}_hd@720p.m3u8"

    # 4. Quét fallback ID thuần số khác ngoại trừ danh sách đen
    all_ids = re.findall(r'179\d{7,10}', html)
    for r_id in all_ids:
        if r_id not in BLACK_LIST_IDS:
            return f"{CDN_BASE}/{r_id}_hd/{r_id}_hd@720p.m3u8"

    return None

def fetch_real_stream_url(match, homepage_html=""):
    headers = {"User-Agent": USER_AGENT_HEADER, "Referer": REFERER_HEADER}
    match_id = str(match.get("id") or match.get("fi") or "").strip()
    
    teams = match.get("teams", {})
    home_name = teams.get("home", {}).get("name", "")
    away_name = teams.get("away", {}).get("name", "")
    day_month = match.get("day_month", "").replace("/", "-")
    
    test_urls = []
    
    # 1. Slug SEO bài viết chuẩn
    if home_name and away_name:
        home_slug = slugify(home_name)
        away_slug = slugify(away_name)
        seo_url = f"https://giovang.rent/truc-tiep-{home_slug}-vs-{away_slug}-{day_month}-{match_id}"
        test_urls.append(seo_url)
        
    # 2. Link bài viết bóc từ trang chủ
    if homepage_html and match_id:
        found_links = re.findall(rf'href=["\'](https?://giovang\.rent/truc-tiep-[^"\']*-{match_id})["\']', homepage_html)
        for fl in found_links:
            if fl not in test_urls:
                test_urls.append(fl)

    for url in test_urls:
        proxy_url = f"https://vsc-proxy.sonnguyen90pro.workers.dev/?url={url}"
        try:
            res = requests.get(proxy_url, headers=headers, timeout=6)
            if res.status_code == 200:
                stream_url = parse_m3u8_from_html(res.text)
                if stream_url:
                    return stream_url
        except Exception:
            pass

    return None

def extract_commentator(match):
    blv_list = match.get("blv", [])
    if isinstance(blv_list, list) and blv_list:
        clean_names = []
        for name in blv_list:
            if isinstance(name, str):
                c_name = name.replace("blv-", "").replace("blv_", "").strip().title()
                clean_names.append(c_name)
        if clean_names:
            return ", ".join(clean_names)
    return "Thuyết minh"

def generate_m3u():
    headers = {"User-Agent": USER_AGENT_HEADER, "Referer": REFERER_HEADER}
    
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
        league_title = match.get("league", {}).get("title", "")
        group_title = get_group_title(sport_type, league_title)
        
        time_raw = match.get("time", "")[:5]
        day_month = match.get("day_month", "")
        time_str = f"{time_raw} {day_month}".strip()
        
        commentator = extract_commentator(match)
        
        is_live = match.get("is_live", False) or match.get("status_code") == "LIVE"
        status_icon = "🟢 " if is_live else ""

        real_stream_url = fetch_real_stream_url(match, homepage_html)
        
        if real_stream_url:
            stream_url = f"{real_stream_url}|Referer={REFERER_HEADER}&User-Agent={USER_AGENT_HEADER}"
        else:
            stream_url = "https://freem3u.xyz/static/no-signal/low.m3u8"

        m3u_content += f'#EXTINF:-1 tvg-logo="{logo_url}" group-title="{group_title}" http-referrer="{REFERER_HEADER}" http-user-agent="{USER_AGENT_HEADER}" , {status_icon}{time_str} ⚽ {match_name} ({commentator}) [hls]\n'
        m3u_content += f'#EXTVLCOPT:http-referrer={REFERER_HEADER}\n'
        m3u_content += f'#EXTVLCOPT:http-user-agent={USER_AGENT_HEADER}\n'
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
        
