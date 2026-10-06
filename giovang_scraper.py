import json
import re
import sys
import requests

# API target và Cloudflare Worker Proxy
API_TARGET = "https://live-api.keonhacaitp.one/storage/livestream/live.json"
WORKER_PROXY = f"https://vsc-proxy.sonnguyen90pro.workers.dev/?url={API_TARGET}"

# Domain CDN phát video của Giờ Vàng
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

def fetch_real_stream_url(match_id):
    """Tự động truy vấn trang chi tiết trận đấu để tìm link .m3u8 chuẩn hoặc ID phòng live thật (dạng 1791215852)"""
    headers = {"User-Agent": USER_AGENT_HEADER, "Referer": REFERER_HEADER}
    
    # 1. Thử truy vấn các endpoint API chi tiết
    detail_api_urls = [
        f"https://live-api.keonhacaitp.one/storage/livestream/detail/{match_id}.json",
        f"https://live-api.keonhacaitp.one/api/match/{match_id}",
    ]
    
    for api_url in detail_api_urls:
        proxy_url = f"https://vsc-proxy.sonnguyen90pro.workers.dev/?url={api_url}"
        try:
            res = requests.get(proxy_url, headers=headers, timeout=5)
            if res.status_code == 200:
                text = res.text
                # Tìm trực tiếp đường dẫn .m3u8 từ CDN
                m3u8_match = re.search(r'https?://[^\s"\']*vcdn\.cloud[^\s"\']*\.m3u8', text)
                if m3u8_match:
                    return m3u8_match.group(0)
                
                # Tìm ID phòng live 10 chữ số bắt đầu bằng 179...
                ids = re.findall(r'179\d{7}', text)
                if ids:
                    real_id = ids[0]
                    return f"{CDN_BASE}/{real_id}_hd/{real_id}_hd@720p.m3u8"
        except Exception:
            pass

    # 2. Thử quét mã nguồn trang xem trận đấu trên giovang.rent
    web_urls = [
        f"https://giovang.rent/?p={match_id}",
        f"https://giovang.rent/truc-tiep/{match_id}",
    ]
    for web_url in web_urls:
        try:
            res = requests.get(web_url, headers=headers, timeout=5)
            if res.status_code == 200:
                text = res.text
                m3u8_match = re.search(r'https?://[^\s"\']*vcdn\.cloud[^\s"\']*\.m3u8', text)
                if m3u8_match:
                    return m3u8_match.group(0)
                
                ids = re.findall(r'179\d{7}', text)
                if ids:
                    real_id = ids[0]
                    return f"{CDN_BASE}/{real_id}_hd/{real_id}_hd@720p.m3u8"
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
    print("Đang lấy dữ liệu Giờ Vàng TV qua Worker Proxy...")
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
        
        # Tự động truy tìm link stream thực tế
        real_stream_url = fetch_real_stream_url(match_id)
        
        if real_stream_url:
            stream_url = f"{real_stream_url}|Referer={REFERER_HEADER}&User-Agent={USER_AGENT_HEADER}"
        else:
            # Nếu chưa bóc được ID thực thì giữ link dự phòng
            if match_id.isdigit():
                base_m3u8 = f"{CDN_BASE}/{match_id}_hd/{match_id}_hd@720p.m3u8"
                stream_url = f"{base_m3u8}|Referer={REFERER_HEADER}&User-Agent={USER_AGENT_HEADER}"
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
        
