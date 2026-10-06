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
    # 1. Nếu API có sẵn link full .m3u8
    for key in ["stream_url", "hls", "hls_url", "play_url"]:
        val = match.get(key)
        if isinstance(val, str) and ".m3u8" in val:
            return val

    # 2. Tìm ID luồng dạng DÃY SỐ (ví dụ: 1791214831)
    # Ưu tiên tìm trong các field phổ biến trước
    priority_keys = ["room_id", "stream_id", "room", "channel_id", "fi", "id"]
    for key in priority_keys:
        val = str(match.get(key, "")).strip()
        if val.isdigit() and len(val) >= 7:
            return f"{CDN_BASE}/{val}_hd/{val}_hd@720p.m3u8"

    # 3. Quét toàn bộ object để tìm bất kỳ giá trị nào là dãy số từ 7 chữ số trở lên
    for k, v in match.items():
        val_str = str(v).strip()
        if val_str.isdigit() and len(val_str) >= 7:
            return f"{CDN_BASE}/{val_str}_hd/{val_str}_hd@720p.m3u8"

    # 4. Fallback cuối cùng nếu trận chưa có luồng phát live
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
        
