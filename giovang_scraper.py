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

def is_valid_stream_id(val):
    """Lọc ID phòng live chuẩn: Độ dài 7-11 chữ số và không chia hết cho 60 (loại trừ timestamp giờ đá)"""
    val_str = str(val).strip()
    if not val_str.isdigit():
        return False
    if not (7 <= len(val_str) <= 11):
        return False
    num = int(val_str)
    if num % 60 == 0:  # Giờ thi đấu tròn phút luôn chia hết cho 60 -> Bỏ qua
        return False
    return True

def deep_search_ids(obj, ignore_keys=None):
    """Đào sâu đệ quy toàn bộ cấu trúc JSON để tìm tất cả ID phòng live"""
    if ignore_keys is None:
        ignore_keys = {"time", "timestamp", "start_time", "match_time", "date", "created_at"}
    
    found_ids = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in ignore_keys:
                continue
            found_ids.extend(deep_search_ids(v, ignore_keys))
    elif isinstance(obj, list):
        for item in obj:
            found_ids.extend(deep_search_ids(item, ignore_keys))
        elif isinstance(obj, (int, str)):
            if is_valid_stream_id(obj):
                found_ids.append(str(obj).strip())
    return found_ids

def extract_stream_url(match):
    # 1. Nếu API trả về trực tiếp đường dẫn .m3u8
    for key in ["stream_url", "hls", "hls_url", "play_url", "link"]:
        val = match.get(key)
        if isinstance(val, str) and ".m3u8" in val:
            return val

    # 2. Ưu tiên đào sâu vào các mảng phòng live/BLV (blv, channels, streams, rooms)
    priority_obj = []
    for key in ["blv", "channels", "streams", "rooms", "servers", "links"]:
        if key in match:
            priority_obj.append(match[key])

    candidates = deep_search_ids(priority_obj)
    
    # 3. Nếu trong mảng ưu tiên không có thì đào toàn bộ thông tin trận đấu
    if not candidates:
        candidates = deep_search_ids(match)

    if candidates:
        stream_id = candidates[0]
        return f"{CDN_BASE}/{stream_id}_hd/{stream_id}_hd@720p.m3u8"

    # 4. Nếu chưa mở phòng live -> Trả về link no-signal
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
        valid_names = [n for n in names if n]
        if valid_names:
            return ", ".join(valid_names)
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
        
