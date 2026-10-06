import json
import sys
import requests

# API target và Cloudflare Worker Proxy
API_TARGET = "https://live-api.keonhacaitp.one/storage/livestream/live.json"
WORKER_PROXY = f"https://vsc-proxy.sonnguyen90pro.workers.dev/?url={API_TARGET}"

# Domain CDN phát video của Giờ Vàng
CDN_BASE = "https://ftlh5sc02iliv.vcdn.cloud"

TYPE_MAP = {
    "football": "Bóng đá",
    "basketball": "Bóng rổ",
    "rugby": "Bóng bầu dục / NFL",
    "bongchay": "Bóng chày",
    "caulong": "Cầu lông / Trái cầu",
}

def get_group_title(sport_type, league_title=""):
    return TYPE_MAP.get(str(sport_type).lower(), league_title or "Giờ Vàng TV")

def extract_stream_url(match):
    # 1. Nếu API trả về trực tiếp đường dẫn .m3u8
    for key in ["stream_url", "hls", "hls_url", "play_url", "link"]:
        val = match.get(key)
        if isinstance(val, str) and ".m3u8" in val:
            return val

    # 2. Tìm ID luồng trong các field chuẩn của API
    TARGET_KEYS = ["room_id", "stream_id", "live_id", "room", "fi", "id"]
    candidate_id = None

    for key in TARGET_KEYS:
        val = str(match.get(key, "")).strip()
        if not val or val.lower() == "none":
            continue
            
        # Nếu là chuỗi số (Unix Timestamp trận đấu luôn > 1.7 tỷ và chia hết cho 60)
        if val.isdigit():
            num = int(val)
            if num > 1700000000 and num % 60 == 0:
                continue  # Bỏ qua vì đây là timestamp thời gian thi đấu
            candidate_id = val
            break
        elif len(val) >= 5: # ID dạng chuỗi
            candidate_id = val
            break

    if candidate_id:
        return f"{CDN_BASE}/{candidate_id}_hd/{candidate_id}_hd@720p.m3u8"

    # 3. Trường hợp trận chưa đến giờ hoặc chưa có luồng
    return "https://freem3u.xyz/static/no-signal/low.m3u8"

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
        
        time_raw = match.get("time", "")[:5] # Lấy HH:MM
        day_month = match.get("day_month", "")
        time_str = f"{time_raw} {day_month}".strip()
        
        blv_list = match.get("blv", [])
        commentator = ", ".join(blv_list) if isinstance(blv_list, list) and blv_list else "Thuyết minh"
        
        is_live = match.get("is_live", False) or match.get("status_code") == "LIVE"
        status_icon = "🟢 " if is_live else ""

        stream_url = extract_stream_url(match)

        m3u_content += f'#EXTINF:-1 tvg-logo="{logo_url}" group-title="{group_title}" , {status_icon}{time_str} ⚽ {match_name} ({commentator}) [hls]\n'
        m3u_content += f'{stream_url}\n\n'
        count += 1
        
    with open("giovang.m3u", "w", encoding="utf-8") as f:
        f.write(m3u_content)
    print(f"Đã xuất thành công file giovang.m3u với {count} luồng.")

if __name__ == "__main__":
    try:
        generate_m3u()
    except Exception as e:
        print(f"Lỗi khi chạy script Giờ Vàng: {e}", file=sys.stderr)
        sys.exit(1)
        
