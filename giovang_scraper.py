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

def is_valid_stream_id(val_str):
    """ID luồng chuẩn là mã Unix timestamp 10 chữ số (>1.79 tỷ) không chia hết cho 900 (15 phút thi đấu)"""
    if not val_str or not val_str.isdigit():
        return False
    num = int(val_str)
    if num > 1700000000 and num % 900 != 0:
        return True
    return False

def extract_stream_url(match):
    # 1. Nếu API trả về trực tiếp link .m3u8
    for key in ["stream_url", "hls", "hls_url", "play_url", "link"]:
        val = match.get(key)
        if isinstance(val, str) and ".m3u8" in val:
            return val

    # 2. Quét mảng lồng bên trong (blv, channels, streams, rooms, links)
    nested_items = []
    for key in ["blv", "channels", "streams", "rooms", "links", "servers"]:
        val = match.get(key)
        if isinstance(val, list):
            nested_items.extend(val)

    for item in nested_items:
        if isinstance(item, dict):
            for k in ["room_id", "stream_id", "id", "live_id", "channel_id"]:
                v = str(item.get(k, "")).strip()
                if is_valid_stream_id(v):
                    return f"{CDN_BASE}/{v}_hd/{v}_hd@720p.m3u8"
        elif isinstance(item, (int, str)):
            v = str(item).strip()
            if is_valid_stream_id(v):
                return f"{CDN_BASE}/{v}_hd/{v}_hd@720p.m3u8"

    # 3. Quét các trường ở cấp trận đấu
    for k in ["room_id", "stream_id", "live_id", "channel_id", "room"]:
        v = str(match.get(k, "")).strip()
        if is_valid_stream_id(v):
            return f"{CDN_BASE}/{v}_hd/{v}_hd@720p.m3u8"

    # 4. Nếu chưa có phòng live -> Trả về link no-signal
    return "https://freem3u.xyz/static/no-signal/low.m3u8"

def extract_commentator(match):
    blv_data = match.get("blv", [])
    if isinstance(blv_data, list) and blv_data:
        names = []
        for item in blv_data:
            if isinstance(item, dict):
                names.append(item.get("name") or item.get("nickname") or item.get("slug", ""))
            elif isinstance(item, str):
                clean_name = item.replace("blv-", "").strip().capitalize()
                names.append(clean_name)
        if names:
            return ", ".join(filter(None, names))
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
        
        time_raw = match.get("time", "")[:5] # Lấy HH:MM
        day_month = match.get("day_month", "")
        time_str = f"{time_raw} {day_month}".strip()
        
        commentator = extract_commentator(match)
        
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
        
