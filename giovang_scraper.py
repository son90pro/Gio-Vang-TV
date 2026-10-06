import json
import re
import sys
import requests

API_TARGET = "https://live-api.keonhacaitp.one/storage/livestream/live.json"
WORKER_PROXY = f"https://vsc-proxy.sonnguyen90pro.workers.dev/?url={API_TARGET}"

CDN_BASE = "https://ftlh5sc02iliv.vcdn.cloud"
REFERER_HEADER = "https://keobongvip.in/"
USER_AGENT_HEADER = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

TYPE_MAP = {
    "football": "Bóng đá",
    "basketball": "Bóng rổ",
    "rugby": "Bóng bầu dục / NFL",
    "bongchay": "Bóng chày",
    "caulong": "Cầu lông / Trái cầu",
}

def get_group_title(sport_type, league_title=""):
    return TYPE_MAP.get(str(sport_type).lower(), league_title or "Giờ Vàng TV")

def is_stream_valid(m3u8_url):
    """Kiểm tra xem link .m3u8 có thực sự tồn tại (HTTP 200) trên CDN hay không"""
    headers = {"User-Agent": USER_AGENT_HEADER, "Referer": REFERER_HEADER}
    try:
        res = requests.head(m3u8_url, headers=headers, timeout=4, allow_redirects=True)
        if res.status_code == 200:
            return True
        res = requests.get(m3u8_url, headers=headers, timeout=4, stream=True)
        return res.status_code == 200
    except Exception:
        return False

def fetch_real_stream_url(match_id):
    """Tìm và kiểm chứng link m3u8 trực tiếp từ web/API"""
    headers = {"User-Agent": USER_AGENT_HEADER, "Referer": REFERER_HEADER}
    
    test_urls = [
        f"https://giovang.rent/{match_id}",
        f"https://giovang.rent/truc-tiep/{match_id}",
    ]
    
    for url in test_urls:
        try:
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                html = res.text
                # 1. Tìm link .m3u8 trực tiếp
                m3u8_matches = re.findall(r'https?://[^\s"\']*vcdn\.cloud[^\s"\']*\.m3u8', html)
                for candidate in m3u8_matches:
                    if is_stream_valid(candidate):
                        return candidate
                
                # 2. Tìm ID dạng 179... và test link
                room_ids = re.findall(r'179\d{7}', html)
                for r_id in room_ids:
                    candidate = f"{CDN_BASE}/{r_id}_hd/{r_id}_hd@720p.m3u8"
                    if is_stream_valid(candidate):
                        return candidate
        except Exception:
            pass

    # 3. Nếu match_id gốc là chuỗi số, kiểm tra trực tiếp CDN
    if str(match_id).isdigit():
        candidate = f"{CDN_BASE}/{match_id}_hd/{match_id}_hd@720p.m3u8"
        if is_stream_valid(candidate):
            return candidate

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
    print("Đang lấy danh sách trận đấu Giờ Vàng TV...")
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

        match_id = str(match.get("id") or match.get("fi") or "").strip()
        
        print(f"Đang kiểm tra luồng phát: {match_name} (ID: {match_id})...")
        real_stream_url = fetch_real_stream_url(match_id)
        
        if real_stream_url:
            print(f" -> [Thành công] Tìm thấy luồng HLS sống: {real_stream_url}")
            stream_url = f"{real_stream_url}|Referer={REFERER_HEADER}&User-Agent={USER_AGENT_HEADER}"
        else:
            print(f" -> [Bỏ qua] Trận đấu không có luồng HLS trực tiếp. Gán link No-Signal.")
            stream_url = "https://freem3u.xyz/static/no-signal/low.m3u8"

        m3u_content += f'#EXTINF:-1 tvg-logo="{logo_url}" group-title="{group_title}" http-referrer="{REFERER_HEADER}" http-user-agent="{USER_AGENT_HEADER}" , {status_icon}{time_str} ⚽ {match_name} ({commentator}) [hls]\n'
        m3u_content += f'#EXTVLCOPT:http-referrer={REFERER_HEADER}\n'
        m3u_content += f'#EXTVLCOPT:http-user-agent={USER_AGENT_HEADER}\n'
        m3u_content += f'{stream_url}\n\n'
        count += 1
        
    with open("giovang.m3u", "w", encoding="utf-8") as f:
        f.write(m3u_content)
    print(f"\nĐã xuất thành công file giovang.m3u với {count} trận đấu.")

if __name__ == "__main__":
    try:
        generate_m3u()
    except Exception as e:
        print(f"Lỗi khi chạy script Giờ Vàng: {e}", file=sys.stderr)
        sys.exit(1)
        
